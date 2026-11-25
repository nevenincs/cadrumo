"""Source resolver for the annual prorrata regularisation (LIVA arts. 101 and 104-106).

Resolves the Modelo 303 regularisation box (Regularización prorrata por
porcentaje definitivo - Cuota) and the Modelo 390 annual regularisation field
for a taxpayer under prorrata, general or especial, whole-entity or with
differentiated sectors. The settlement liquidation of the year
-- the fourth quarter, or month 12 for a monthly filer -- deducts its own
cuotas at the definitive percentages through the IVA ledger; the box
regularises only the earlier liquidations, whose gross cuotas are re-derived
from the ledger and whose practised deductions are read from their filed
observations. The Modelo 390 field restates the filed settlement box.

The definitive percentage comes from the current calculation's full-year
volume casillas, never from a single quarter. Missing or contradicted inputs
stay unresolved with a finding that names them; nothing defaults to zero.

See Also:
    :func:`~domain.iva.prorrata.compute_regularizacion_prorrata_particionada`
        Pure LIVA art. 105.Cuatro computation the resolver feeds, one
        partition per differentiated sector or regularisable slice.
    :func:`~domain.iva.m303_settlement.m303_liquidation_periods`
        Registry cadence the regularised liquidations are read from.
    :mod:`~application.aggregation.iva_ledger_apportionment`
        Ledger apportionment that deducts the settlement liquidation at the
        definitive percentage.
    :mod:`~domain.prorrata_register`
        Cross-period carry home for provisional and definitive prorrata
        percentages;
:class:`RegistrySnapshot`, the pinned registry snapshot.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import ClassVar, Final

from pydantic import BaseModel

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...core.casilla_id import CasillaId
from ...core.decimal.constants import MONEY_ZERO
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import normalise_supported_language, output_language, tr
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.bienes_inversion.register import BienesInversionIvaRegister
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.binding_targets import casillas_by_binding
from ...domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ...domain.calculations.registry.ids import (
    BindingId,
    LegalRefId,
    SourceRefId,
)
from ...domain.calculations.registry.prorrata_register_catalogue import (
    regime_apportions_deduction,
)
from ...domain.calculations.registry.prorrata_regularizacion_bindings import (
    ProrrataRegularizacionOutput,
    ProrrataRegularizacionProvider,
    ProrrataSourceRole,
    prorrata_source_casilla_id,
)
from ...domain.calculations.registry.schema import (
    ModeloRevision,
    RegistrySnapshot,
)
from ...domain.invoices.errors import InvoicePersistenceError
from ...domain.iva.m303_settlement import is_m303_annual_settlement_period, m303_liquidation_periods
from ...domain.iva.prorrata import RegularizacionProrrataParticion, compute_regularizacion_prorrata_particionada
from ...domain.prorrata_register.protocols import ProrrataRegisterRepositoryProtocol
from ...domain.prorrata_register.register import (
    ProrrataOperatorGrossDeclaration,
    ProrrataProvisionalResolution,
    ProrrataRegister,
    ProrrataRegisterEntry,
    ProrrataRegisterError,
)
from ...domain.transactions.errors import TransactionPersistenceError
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..aggregation.source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)
from ..aggregation.source_resolution_operations import (
    storage_degradation_resolution,
    unresolved_binding_diagnostics,
)
from ..invoices.catalogue_reads_ports import InvoiceCatalogueReader, InvoiceCatalogueReadPersistenceError
from ..persistence_errors import PersistenceDegradationError
from ..prorrata_register.service import require_prorrata_register_coordinates_current
from .m303_settlement_observation import M303SettlementObservationState, m303_annual_settlement_observation
from .observations_repository import CalculationObservationRepositoryProtocol
from .prorrata_regularizacion_periods import (
    RegularisedPeriodLedger,
    RegularisedPeriodRefusal,
    format_period_list,
    partition_definitive_percentages,
)
from .revision_carry_gate import revision_carry_outcome

# Registry-owned prorrata declarations are read from the selected Modelo 303/390
# revision through the query boundary below. This module retains aggregation and
# evidence mechanics only.

_SOURCE_KIND: Final = BindingSourceKind.PRORRATA_REGULARIZACION


def _prorrata_source_id(revision: ModeloRevision, role: ProrrataSourceRole) -> CasillaId:
    """Read one role's casilla from the revision's typed prorrata declaration."""
    casilla_id = prorrata_source_casilla_id(revision.bindings, role)
    if casilla_id is None:
        raise ValueError("selected prorrata binding does not declare the required source casillas")
    return casilla_id


def _prorrata_target_casilla(revision: ModeloRevision, output: str) -> CasillaId | None:
    """Resolve a printed target number from the selected revision's casillas."""
    marker = "_casilla_"
    if marker not in output:
        return None
    number = output.rsplit(marker, 1)[-1]
    return next((casilla.id for casilla in revision.casillas if casilla.number == number), None)


@dataclass(frozen=True, slots=True)
class _PriorDefinitivaCarry:
    percentage: Decimal
    source_filing_year: int
    source_period: str


@dataclass(frozen=True, slots=True)
class _ProrrataProvisionalSource:
    percentage: Decimal | None
    provenance: tuple[CalculationSourceProvenance, ...]


class ProrrataDeclaredVolumeLedgerRollup(BaseModel):
    """Ledger-side annual volume rollup used only as a divergence advisory.

    Declared annual volume casillas remain the filing authority. This projection
    records the currently classifiable ledger output-volume view so settlement
    can warn when it contradicts those declared values.
    """

    model_config = STRICT_FROZEN_CONFIG

    declared_volume_total: Decimal | None
    declared_volume_con_derecho: Decimal | None
    declared_volume_sin_derecho: Decimal | None
    ledger_volume_total: Decimal
    ledger_volume_con_derecho: Decimal
    ledger_volume_sin_derecho: Decimal
    included_ledger_ids: tuple[str, ...] = ()
    unclassified_ledger_ids: tuple[str, ...] = ()
    #: Ledger ids skipped from the rollup because they carry an operator-declared
    #: LIVA art. 104.Tres judgment exclusion (foreign PE, non-habitual
    #: inmobiliario/financiero). Recorded so the exclusion is auditable and the
    #: proposal is never a silent substitution of the declared volumes.
    art_104_tres_excluded_ledger_ids: tuple[str, ...] = ()


def build_prorrata_declared_volume_advisory(
    rollup: ProrrataDeclaredVolumeLedgerRollup, *, ejercicio: int
) -> CalculationSourceDiagnostic | None:
    """Disclose incomplete classification separately from an actual volume disagreement."""
    present = rollup.declared_volume_total is not None and rollup.declared_volume_con_derecho is not None
    if not rollup.included_ledger_ids and not rollup.unclassified_ledger_ids:
        return None
    if rollup.unclassified_ledger_ids:
        reason = "prorrata_volume_check_unavailable"
        message = (
            f"La comparación anual de prorrata de {ejercicio} no es completa: "
            f"{len(rollup.unclassified_ledger_ids)} operaciones de salida no tienen clasificación suficiente. "
            "Revise sus hechos de IVA y las exclusiones del art. 104.Tres; no se afirma una divergencia."
        )
    elif not present:
        reason = "prorrata_volume_declaration_missing"
        message = (
            f"Declare los volúmenes anuales de prorrata de {ejercicio} para compararlos con "
            f"{len(rollup.included_ledger_ids)} operaciones de salida clasificadas del libro."
        )
    elif (
        rollup.declared_volume_total == rollup.ledger_volume_total
        and rollup.declared_volume_con_derecho == rollup.ledger_volume_con_derecho
        and rollup.declared_volume_sin_derecho == rollup.ledger_volume_sin_derecho
    ):
        return None
    else:
        reason = "prorrata_volume_divergence"
        message = (
            f"Los volúmenes declarados de prorrata de {ejercicio} difieren de las "
            f"{len(rollup.included_ledger_ids)} operaciones de salida clasificadas del libro: "
            f"total {rollup.ledger_volume_total}, con derecho {rollup.ledger_volume_con_derecho}, "
            f"sin derecho {rollup.ledger_volume_sin_derecho}. "
            f"Se han excluido {len(rollup.art_104_tres_excluded_ledger_ids)} operaciones con declaración "
            "de exclusión del art. 104.Tres. Revise también las exclusiones que el libro no puede inferir; "
            "los volúmenes declarados siguen siendo la autoridad y no se sustituyen."
        )
    return CalculationSourceDiagnostic(
        reason=reason,
        source_kind=BindingSourceKind.PRORRATA_REGULARIZACION.value,
        message=message,
        message_language=OutputLanguage.ES,
        asserted_legal_refs=("ley-37-1992:art-94", "ley-37-1992:art-104"),
    )


class ProrrataApplicabilityProjection(BaseModel):
    """Fail-closed-to-visible prorrata applicability evidence for one ejercicio.

    Prorrata applies when the taxpayer has an active register entry or the
    ejercicio shows exempt-without-right operations through declared annual
    volumes or the ledger rollup. This projection is deliberately pure; later
    steps turn an applicable-but-unresolved state into calculate/verify
    diagnostics.
    """

    model_config = STRICT_FROZEN_CONFIG

    applies: bool
    register_active: bool
    declared_volume_sin_derecho: Decimal
    ledger_volume_sin_derecho: Decimal
    evidence_kinds: tuple[str, ...] = ()


def derive_prorrata_applicability(
    *,
    register_entries: Iterable[ProrrataRegisterEntry] = (),
    declared_volume_total: Decimal | None = None,
    declared_volume_con_derecho: Decimal | None = None,
    ledger_rollup: ProrrataDeclaredVolumeLedgerRollup | None = None,
) -> ProrrataApplicabilityProjection:
    """Derive whether prorrata applies for an ejercicio.

    The rule is intentionally fail-closed-to-visible: any active register entry
    (``general`` or ``especial``), any positive declared sin-derecho annual
    volume, or any positive ledger-projected sin-derecho annual volume means
    prorrata applies and later steps must not silently assume a full-deduction
    default.
    """
    if (declared_volume_total is None) != (declared_volume_con_derecho is None):
        raise ValueError("declared_volume_total and declared_volume_con_derecho must be supplied together")

    entries = tuple(register_entries)
    register_active = any(regime_apportions_deduction(entry.regime) for entry in entries)
    declared_volume_sin_derecho = (
        Decimal("0")
        if declared_volume_total is None or declared_volume_con_derecho is None
        else declared_volume_total - declared_volume_con_derecho
    )
    ledger_volume_sin_derecho = Decimal("0") if ledger_rollup is None else ledger_rollup.ledger_volume_sin_derecho

    evidence: list[str] = []
    if register_active:
        evidence.append("register_active")
    if declared_volume_sin_derecho > Decimal("0"):
        evidence.append("declared_sin_derecho_volume")
    if ledger_volume_sin_derecho > Decimal("0"):
        evidence.append("ledger_sin_derecho_volume")

    return ProrrataApplicabilityProjection(
        applies=bool(evidence),
        register_active=register_active,
        declared_volume_sin_derecho=declared_volume_sin_derecho,
        ledger_volume_sin_derecho=ledger_volume_sin_derecho,
        evidence_kinds=tuple(evidence),
    )


def build_prorrata_missing_provisional_advisory(
    *,
    applicability: ProrrataApplicabilityProjection,
    provisional_resolution: ProrrataProvisionalResolution,
    ejercicio: int,
    revision: ModeloRevision,
    first_ejercicio: bool = False,
) -> CalculationSourceDiagnostic | None:
    """Build the visible advisory for an applicable prorrata with no provisional percentage.

    This is the per-period no-silent-under-declaration warning. It does not
    fabricate a percentage: an applicable-but-unresolved prorrata tells the
    operator to record the inicio-de-actividad percentage for a first ejercicio
    or seed/record the prior definitive percentage for subsequent ejercicios.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
    """
    if not applicability.applies or provisional_resolution.resolved:
        return None

    operator_action = (
        "registre el porcentaje provisional de inicio de actividad"
        if first_ejercicio
        else "siembre o registre la prorrata definitiva del ejercicio anterior"
    )
    evidence = ", ".join(applicability.evidence_kinds) or "prorrata_applicability"
    target = _modelo_303_regularizacion_target(revision)
    message = (
        f"Prorrata aplicable en {ejercicio} sin porcentaje provisional resuelto "
        f"({evidence}); {_regularizacion_target_label(revision, target)} no puede regularizarse. "
        f"{operator_action}; no se aplica un porcentaje por defecto."
    )
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=BindingSourceKind.PRORRATA_REGULARIZACION.value,
        message=message,
        message_language=OutputLanguage.ES,
        casilla_id=target,
    )


def _modelo_303_regularizacion_target(revision: ModeloRevision) -> CasillaId | None:
    """Return the casilla the revision declares for the Modelo 303 prorrata regularisation."""
    targets = casillas_by_binding(revision)
    candidates = {
        casilla_id
        for binding in revision.bindings
        if isinstance(binding.provider, ProrrataRegularizacionProvider)
        and binding.provider.regularizacion_output is ProrrataRegularizacionOutput.MODELO_303_CASILLA_44
        for casilla_id in targets.get(binding.id, ())
    }
    return next(iter(candidates)) if len(candidates) == 1 else None


def _regularizacion_target_label(revision: ModeloRevision, casilla_id: CasillaId | None) -> str:
    """Name the registry-declared target casilla by its printed number for operator messages."""
    number = next((casilla.number for casilla in revision.casillas if casilla.id == casilla_id), None)
    if number is not None and number:
        return tr("application.calculations.prorrata_regularizacion.target_casilla", number=number)
    return tr("application.calculations.prorrata_regularizacion.target_declared")


def _binding_legal_refs(revision: ModeloRevision) -> tuple[LegalRefId, ...]:
    refs: list[LegalRefId] = []
    for binding in revision.bindings:
        if binding.source != _SOURCE_KIND:
            continue
        for ref in getattr(binding, "legal_refs", ()):
            if ref not in refs:
                refs.append(ref)
    return tuple(refs)


def _binding_source_refs(revision: ModeloRevision) -> tuple[SourceRefId, ...]:
    refs: list[SourceRefId] = []
    for binding in revision.bindings:
        if binding.source != _SOURCE_KIND:
            continue
        for ref in getattr(binding, "source_refs", ()):
            if ref not in refs:
                refs.append(ref)
    return tuple(refs)


def _prorrata_bindings_by_output(revision: ModeloRevision) -> dict[str, BindingId]:
    bindings: dict[str, BindingId] = {}
    for binding in revision.bindings:
        if not isinstance(binding.provider, ProrrataRegularizacionProvider):
            continue
        bindings[binding.provider.regularizacion_output] = binding.id
    return bindings


def _prorrata_declared_binding_ids(revision: ModeloRevision) -> tuple[BindingId, ...]:
    return tuple(sorted(binding.id for binding in revision.bindings if binding.source == _SOURCE_KIND))


def _prorrata_source_modelo(revision: ModeloRevision) -> str:
    """Return the one modelo the revision's prorrata bindings declare as their source."""
    modelos = {
        str(binding.provider.source_modelo)
        for binding in revision.bindings
        if isinstance(binding.provider, ProrrataRegularizacionProvider)
    }
    if len(modelos) != 1:
        raise ValueError("selected prorrata bindings must declare exactly one source modelo")
    return next(iter(modelos))


def _entry_for_register_provenance(
    register: ProrrataRegister,
    *,
    ejercicio: int,
) -> ProrrataRegisterEntry | None:
    entry = register.entry_for(ejercicio)
    if entry is not None:
        return entry
    entries = register.entries_for_ejercicio(ejercicio)
    return entries[0] if entries else None


def _register_provenance(
    *,
    context: CalculationSourceContext,
    entry: ProrrataRegisterEntry | None,
    provisional_resolution: ProrrataProvisionalResolution,
    revision: ModeloRevision,
) -> CalculationSourceProvenance:
    provenance = provisional_resolution.provenance
    provenance_token = provenance.value if provenance is not None else "resolved"
    suffix = provenance_token
    if entry is not None and entry.source_observation_ref is not None:
        suffix = f"{provenance_token}:{entry.source_observation_ref}"
    elif entry is not None and entry.authorisation_reference is not None:
        suffix = f"{provenance_token}:{entry.authorisation_reference}"
    return CalculationSourceProvenance(
        resolver_id=ProrrataRegularizacionSourceResolver.resolver_id,
        resolved_binding_source=_SOURCE_KIND,
        contributor_source_kind=_SOURCE_KIND.value,
        contributor_binding_source=_SOURCE_KIND,
        lineage_role=CalculationSourceLineageRole.PRIMARY,
        source_ref=f"prorrata-register:{context.filing_year}:{suffix}",
        parent_source_ref=None,
        terminal_origin=TerminalOriginClass.DERIVED_CALCULATION,
        source_filing_year=context.filing_year,
        legal_refs=_binding_legal_refs(revision),
        source_refs=_binding_source_refs(revision),
    )


def _prior_definitiva_provenance(
    *,
    carry: _PriorDefinitivaCarry,
    revision: ModeloRevision,
    source_modelo: str,
) -> CalculationSourceProvenance:
    definitive_id = _prorrata_source_id(revision, ProrrataSourceRole.PORCENTAJE_DEFINITIVO)
    return CalculationSourceProvenance(
        resolver_id=ProrrataRegularizacionSourceResolver.resolver_id,
        resolved_binding_source=_SOURCE_KIND,
        contributor_source_kind=_SOURCE_KIND.value,
        contributor_binding_source=_SOURCE_KIND,
        lineage_role=CalculationSourceLineageRole.PRIMARY,
        source_ref=f"{source_modelo}:{carry.source_filing_year}:{carry.source_period}:{definitive_id}",
        parent_source_ref=None,
        terminal_origin=TerminalOriginClass.DERIVED_CALCULATION,
        source_modelo=source_modelo,
        source_filing_year=carry.source_filing_year,
        source_periods=(carry.source_period,),
        source_casilla_ids=(definitive_id,),
        legal_refs=_binding_legal_refs(revision),
        source_refs=_binding_source_refs(revision),
    )


def _stamped_prior_year_definitiva(
    repository: CalculationObservationRepositoryProtocol,
    *,
    operation: PinnedAuthorityOperation,
    filing_year: int,
    modelo: str,
    revision: ModeloRevision,
) -> _PriorDefinitivaCarry | None:
    prior_year = filing_year - 1
    candidates: list[tuple[datetime, _PriorDefinitivaCarry]] = []
    for payload in repository.iter_modelo(modelo):
        observation = payload.observation
        if observation.filing_year != prior_year:
            continue
        percentage = observation.casilla_values.get(
            _prorrata_source_id(revision, ProrrataSourceRole.PORCENTAJE_DEFINITIVO)
        )
        if percentage is None:
            continue
        refused = revision_carry_outcome(payload.registry_snapshot_ref, operation=operation).refused
        if refused:
            continue
        candidates.append(
            (
                payload.captured_at,
                _PriorDefinitivaCarry(
                    percentage=percentage,
                    source_filing_year=observation.filing_year,
                    source_period=observation.period,
                ),
            )
        )
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def _target_inputs(
    revision: ModeloRevision,
    *,
    binding_values: Mapping[BindingId, Decimal],
    modelo: str,
) -> dict[CasillaId, Decimal]:
    binding_by_output = _prorrata_bindings_by_output(revision)
    model_prefix = f"modelo_{modelo}_"
    output = next(
        (candidate for candidate in binding_by_output if candidate.startswith(model_prefix)),
        None,
    )
    if output is None:
        return {}
    binding_id = binding_by_output[output]
    target_casilla = _prorrata_target_casilla(revision, output)
    if target_casilla is None or binding_id not in binding_values:
        return {}
    return {target_casilla: binding_values[binding_id]}


def _revision_for_context(
    context: CalculationSourceContext,
    registry_snapshot: RegistrySnapshot | None,
) -> ModeloRevision:
    revision = registry_snapshot.revision if registry_snapshot is not None else None
    if revision is not None:
        return revision
    # The source mesh already selected this exact revision before invoking the
    # resolver.  Re-selecting through a process-wide catalogue could cross a
    # generation boundary and would make a persisted calculation depend on a
    # later authority edition.
    return context.revision


def _resolve_prorrata_provisional_source(
    register: ProrrataRegister,
    prior_definitiva: _PriorDefinitivaCarry | None,
    *,
    context: CalculationSourceContext,
    revision: ModeloRevision,
    current_provenance: CalculationSourceProvenance,
) -> _ProrrataProvisionalSource:
    provisional = register.resolve_provisional(context.filing_year)
    if provisional.resolved:
        register_entry = _entry_for_register_provenance(register, ejercicio=context.filing_year)
        provenance = (
            current_provenance,
            _register_provenance(
                context=context,
                entry=register_entry,
                provisional_resolution=provisional,
                revision=revision,
            ),
        )
        if provisional.percentage is None:
            raise ValueError(
                "prorrata register reported a resolved provisional percentage without a value",
            )
        return _ProrrataProvisionalSource(percentage=provisional.percentage, provenance=provenance)
    if prior_definitiva is not None:
        return _ProrrataProvisionalSource(
            percentage=prior_definitiva.percentage,
            provenance=(
                current_provenance,
                _prior_definitiva_provenance(
                    carry=prior_definitiva,
                    revision=revision,
                    source_modelo=_prorrata_source_modelo(revision),
                ),
            ),
        )
    return _ProrrataProvisionalSource(percentage=None, provenance=(current_provenance,))


def _catalogue_language() -> OutputLanguage:
    """The language a finding rendered from the catalogue here is worded in: the one ``tr`` renders."""
    return OutputLanguage(normalise_supported_language(output_language()) or OutputLanguage.EN.value)


def _unresolved_resolution(
    *,
    revision: ModeloRevision,
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
    declared_binding_ids: tuple[BindingId, ...],
    message: str,
    provenance: tuple[CalculationSourceProvenance, ...] = (),
) -> CalculationSourceResolution:
    """Leave every declared regularisation binding unresolved with one named reason, worded from the catalogue."""
    return CalculationSourceResolution(
        resolver_id=resolver_id,
        owned_sources=owned_sources,
        unresolved_binding_ids=declared_binding_ids,
        diagnostics=unresolved_binding_diagnostics(
            source_kind=_SOURCE_KIND.value,
            revision=revision,
            binding_ids=declared_binding_ids,
            resolver_id=resolver_id,
            message=message,
            message_language=_catalogue_language(),
        ),
        provenance=provenance,
    )


def _zero_prorrata_resolution(
    *,
    revision: ModeloRevision,
    context: CalculationSourceContext,
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
    declared_binding_ids: tuple[BindingId, ...],
    provenance: CalculationSourceProvenance,
) -> CalculationSourceResolution:
    """Resolve a proven zero: prorrata does not apply, or the period is not the settlement."""
    zero_values = {binding_id: MONEY_ZERO for binding_id in declared_binding_ids}
    return CalculationSourceResolution(
        resolver_id=resolver_id,
        owned_sources=owned_sources,
        binding_values=zero_values,
        bound_inputs_by_casilla_id=_target_inputs(
            revision,
            binding_values=zero_values,
            modelo=context.modelo,
        ),
        provenance=(provenance,),
    )


def _valued_prorrata_resolution(
    *,
    revision: ModeloRevision,
    context: CalculationSourceContext,
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
    declared_binding_ids: tuple[BindingId, ...],
    value: Decimal,
    provenance: tuple[CalculationSourceProvenance, ...],
) -> CalculationSourceResolution:
    """Fan one regularisation value out to every registry-declared output binding."""
    binding_values = {binding_id: value for binding_id in _prorrata_bindings_by_output(revision).values()}
    unresolved = tuple(binding_id for binding_id in declared_binding_ids if binding_id not in binding_values)
    return CalculationSourceResolution(
        resolver_id=resolver_id,
        owned_sources=owned_sources,
        binding_values=binding_values,
        bound_inputs_by_casilla_id=_target_inputs(
            revision,
            binding_values=binding_values,
            modelo=context.modelo,
        ),
        unresolved_binding_ids=unresolved,
        diagnostics=unresolved_binding_diagnostics(
            source_kind=_SOURCE_KIND.value,
            revision=revision,
            binding_ids=unresolved,
            resolver_id=resolver_id,
            message=tr("application.calculations.prorrata_regularizacion.unresolved.selector_unmapped"),
            message_language=_catalogue_language(),
        ),
        provenance=provenance,
    )


def _source_provenance(
    *,
    context: CalculationSourceContext,
    revision: ModeloRevision,
    source_ref: str,
    source_periods: tuple[str, ...],
    source_casilla_ids: tuple[CasillaId, ...],
) -> CalculationSourceProvenance:
    return CalculationSourceProvenance(
        resolver_id=ProrrataRegularizacionSourceResolver.resolver_id,
        resolved_binding_source=_SOURCE_KIND,
        contributor_source_kind=_SOURCE_KIND.value,
        contributor_binding_source=_SOURCE_KIND,
        lineage_role=CalculationSourceLineageRole.PRIMARY,
        source_ref=source_ref,
        parent_source_ref=None,
        terminal_origin=TerminalOriginClass.DERIVED_CALCULATION,
        source_modelo=_prorrata_source_modelo(revision),
        source_filing_year=context.filing_year,
        source_periods=source_periods,
        source_casilla_ids=source_casilla_ids,
        legal_refs=_binding_legal_refs(revision),
        source_refs=_binding_source_refs(revision),
    )


def _operator_declared_provenance(
    *,
    context: CalculationSourceContext,
    revision: ModeloRevision,
    declarations: Iterable[ProrrataOperatorGrossDeclaration],
    parent: CalculationSourceProvenance,
) -> tuple[CalculationSourceProvenance, ...]:
    """Name each operator-declared gross base the regularised periods rest on.

    A declaration stands in for an empty ledger, so it contributes to the
    regularised-periods node rather than replacing it, and its terminal origin
    is the operator's own input.
    """
    return tuple(
        CalculationSourceProvenance(
            resolver_id=ProrrataRegularizacionSourceResolver.resolver_id,
            resolved_binding_source=_SOURCE_KIND,
            contributor_source_kind=_SOURCE_KIND.value,
            contributor_binding_source=_SOURCE_KIND,
            lineage_role=CalculationSourceLineageRole.CONTRIBUTOR,
            source_ref=(
                f"prorrata-register:{declaration.ejercicio}:{declaration.provenance}:"
                f"{declaration.period.registry_token}"
                + (f":{declaration.sector_id}" if declaration.sector_id is not None else "")
            ),
            parent_source_ref=parent.source_ref,
            terminal_origin=TerminalOriginClass.OPERATOR_INPUT,
            source_filing_year=context.filing_year,
            source_periods=(declaration.period.registry_token,),
            legal_refs=_binding_legal_refs(revision),
            source_refs=_binding_source_refs(revision),
        )
        for declaration in declarations
    )


class ProrrataRegularizacionSourceResolver:
    """Resolve the annual prorrata-general regularisation from governed sources.

    Modelo 303 (LIVA art. 105.Cuatro; the AEAT instructions fill the box
    "únicamente en el 4T o mes 12"): outside the settlement liquidation the box
    is a structural zero. At the settlement liquidation, whose own cuotas the
    IVA ledger already deducts at the definitive percentage, the box
    regularises the earlier liquidations of the same cadence::

        box = sum over partitions of round(definitiva_k% x gross cuotas_k)
              - deductions practised on those cuotas

    A whole-entity general register is one partition. Each differentiated
    sector is its own partition at its settled definitive percentage
    (art. 101.Uno), and under prorrata especial only the common-use slice is
    regularised (art. 106.Uno regla 3.ª). The gross cuotas come from the ledger
    for each earlier liquidation, partitioned exactly as the in-year
    apportionment deducted them, and the practised deductions from its filed
    observation; a liquidation whose filed deducible boxes do not equal that
    apportionment is refused rather than guessed. Any missing input -- an
    undeclared volume, an absent or refused earlier liquidation, an unsettled
    sector, cross-sector common use, a negative gross base -- leaves the box
    unresolved with a finding naming it.

    Modelo 390: the annual regularisation restates the filed settlement
    liquidation's own box, so the summary and the periodic return cannot
    disagree.
    """

    resolver_id: ClassVar[str] = _SOURCE_KIND.value
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (_SOURCE_KIND,)

    def __init__(
        self,
        *,
        current_year_values: Mapping[CasillaId, Decimal] | None = None,
        missing_current_year_casilla_ids: Iterable[CasillaId] = (),
        unresolved_current_year_casilla_ids: Iterable[CasillaId] = (),
        undeclared_current_year_casilla_ids: Iterable[CasillaId] = (),
        prorrata_register_repository: ProrrataRegisterRepositoryProtocol,
        observation_repository: CalculationObservationRepositoryProtocol,
        transaction_repository: TransactionCatalogueRepositoryProtocol,
        invoice_reader: InvoiceCatalogueReader,
        investment_asset_register: BienesInversionIvaRegister | None = None,
        investment_asset_profile_id: str | None = None,
        operation: PinnedAuthorityOperation,
        registry_snapshot: RegistrySnapshot | None = None,
    ) -> None:
        """Bind the current calculation's prorrata inputs and the repositories behind the carries.

        ``current_year_values`` holds the volumes and definitive percentage the
        current calculation computed. ``missing_current_year_casilla_ids`` and
        ``unresolved_current_year_casilla_ids`` keep an absent input distinct
        from one present but not computable, and
        ``undeclared_current_year_casilla_ids`` names the volume casillas the
        operator never supplied, whose engine value is a default rather than a
        fact. The transaction repository and capital-goods register re-derive
        the earlier liquidations' gross ledger cuotas.
        """
        self._current_year_values = dict(current_year_values or {})
        self._missing_current_year_casilla_ids = tuple(missing_current_year_casilla_ids)
        self._unresolved_current_year_casilla_ids = tuple(unresolved_current_year_casilla_ids)
        self._undeclared_current_year_casilla_ids = frozenset(undeclared_current_year_casilla_ids)
        self._prorrata_register_repository = prorrata_register_repository
        self._observation_repository = observation_repository
        self._operation = operation
        self._periods = RegularisedPeriodLedger(
            prorrata_register_repository=prorrata_register_repository,
            observation_repository=observation_repository,
            transaction_repository=transaction_repository,
            invoice_reader=invoice_reader,
            investment_asset_register=investment_asset_register,
            investment_asset_profile_id=investment_asset_profile_id,
            operation=operation,
        )
        self._registry_snapshot = registry_snapshot

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        """Resolve the revision's declared regularisation output, or say why it cannot."""
        revision = _revision_for_context(context, self._registry_snapshot)
        declared_binding_ids = _prorrata_declared_binding_ids(revision)
        if not declared_binding_ids:
            return CalculationSourceResolution(resolver_id=self.resolver_id, owned_sources=self.owned_sources)
        outputs = frozenset(_prorrata_bindings_by_output(revision))
        try:
            if ProrrataRegularizacionOutput.MODELO_390_REGULARIZACION_ANUAL in outputs:
                return self._resolve_annual_summary(context, revision, declared_binding_ids)
            return self._resolve_settlement(context, revision, declared_binding_ids)
        except (
            InvoiceCatalogueReadPersistenceError,
            InvoicePersistenceError,
            PersistenceDegradationError,
            ProrrataRegisterError,
            TransactionPersistenceError,
        ) as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )

    def _unresolved(
        self,
        revision: ModeloRevision,
        declared_binding_ids: tuple[BindingId, ...],
        message: str,
        provenance: tuple[CalculationSourceProvenance, ...] = (),
    ) -> CalculationSourceResolution:
        return _unresolved_resolution(
            revision=revision,
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            declared_binding_ids=declared_binding_ids,
            message=message,
            provenance=provenance,
        )

    def _resolve_annual_summary(
        self,
        context: CalculationSourceContext,
        revision: ModeloRevision,
        declared_binding_ids: tuple[BindingId, ...],
    ) -> CalculationSourceResolution:
        settlement = m303_annual_settlement_observation(
            self._observation_repository,
            filing_year=context.filing_year,
            operation=self._operation,
        )
        periods = format_period_list(settlement.periods)
        if settlement.state is M303SettlementObservationState.MISSING:
            return self._unresolved(
                revision,
                declared_binding_ids,
                tr(
                    "application.calculations.prorrata_regularizacion.unresolved.settlement_observation_missing",
                    periods=periods,
                ),
            )
        if settlement.state is M303SettlementObservationState.AMBIGUOUS:
            return self._unresolved(
                revision,
                declared_binding_ids,
                tr(
                    "application.calculations.prorrata_regularizacion.unresolved.settlement_observation_ambiguous",
                    periods=periods,
                ),
            )
        if settlement.payload is None:
            return self._unresolved(
                revision,
                declared_binding_ids,
                tr(
                    "application.calculations.prorrata_regularizacion.unresolved.settlement_observation_refused",
                    periods=periods,
                ),
            )
        period = settlement.periods[0]
        source_modelo = _prorrata_source_modelo(revision)
        settlement_revision = self._operation.revision_for_context(
            source_modelo,
            filing_year=context.filing_year,
            period=period.registry_token,
            on=period.end_date,
        )
        target = _modelo_303_regularizacion_target(settlement_revision)
        value = None if target is None else settlement.payload.observation.casilla_values.get(target)
        if target is None or value is None:
            return self._unresolved(
                revision,
                declared_binding_ids,
                tr(
                    "application.calculations.prorrata_regularizacion.unresolved.settlement_observation_without_regularizacion",
                    periods=periods,
                ),
            )
        provenance = _source_provenance(
            context=context,
            revision=revision,
            source_ref=f"{source_modelo}:{context.filing_year}:{period.registry_token}:{target}",
            source_periods=(period.registry_token,),
            source_casilla_ids=(target,),
        )
        return _valued_prorrata_resolution(
            revision=revision,
            context=context,
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            declared_binding_ids=declared_binding_ids,
            value=value,
            provenance=(provenance,),
        )

    def _settlement_only_zero(
        self,
        context: CalculationSourceContext,
        revision: ModeloRevision,
        declared_binding_ids: tuple[BindingId, ...],
    ) -> CalculationSourceResolution:
        return _zero_prorrata_resolution(
            revision=revision,
            context=context,
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            declared_binding_ids=declared_binding_ids,
            provenance=_source_provenance(
                context=context,
                revision=revision,
                source_ref=(
                    f"{context.modelo}:{context.filing_year}:{context.period.registry_token}:"
                    "prorrata-regularizacion-settlement-only"
                ),
                source_periods=(context.period.registry_token,),
                source_casilla_ids=(),
            ),
        )

    def _missing_current_year_inputs(
        self,
        revision: ModeloRevision,
        undeclared: tuple[CasillaId, ...],
    ) -> tuple[CasillaId, ...]:
        required = tuple(_prorrata_source_id(revision, role) for role in ProrrataSourceRole)
        return tuple(
            casilla_id
            for casilla_id in required
            if casilla_id not in undeclared
            and (
                casilla_id not in self._current_year_values
                or casilla_id in self._missing_current_year_casilla_ids
                or casilla_id in self._unresolved_current_year_casilla_ids
            )
        )

    def _resolve_settlement(
        self,
        context: CalculationSourceContext,
        revision: ModeloRevision,
        declared_binding_ids: tuple[BindingId, ...],
    ) -> CalculationSourceResolution:
        if not is_m303_annual_settlement_period(context.period, authority=self._operation):
            return self._settlement_only_zero(context, revision, declared_binding_ids)
        volumen_con_derecho_id = _prorrata_source_id(revision, ProrrataSourceRole.VOLUMEN_CON_DERECHO)
        volumen_total_id = _prorrata_source_id(revision, ProrrataSourceRole.VOLUMEN_TOTAL)
        definitiva_id = _prorrata_source_id(revision, ProrrataSourceRole.PORCENTAJE_DEFINITIVO)
        undeclared = tuple(
            casilla_id
            for casilla_id in (volumen_con_derecho_id, volumen_total_id)
            if casilla_id in self._undeclared_current_year_casilla_ids
        )
        missing = self._missing_current_year_inputs(revision, undeclared)
        if missing:
            return self._unresolved(
                revision,
                declared_binding_ids,
                tr(
                    "application.calculations.prorrata_regularizacion.unresolved.current_year_inputs",
                    casillas=", ".join(missing),
                ),
            )

        register = require_prorrata_register_coordinates_current(
            self._prorrata_register_repository.load(),
            operation=self._operation,
        )
        applicability = derive_prorrata_applicability(
            register_entries=register.entries_for_ejercicio(context.filing_year),
            declared_volume_total=None if undeclared else self._current_year_values[volumen_total_id],
            declared_volume_con_derecho=None if undeclared else self._current_year_values[volumen_con_derecho_id],
        )
        current_provenance = _source_provenance(
            context=context,
            revision=revision,
            source_ref=f"{context.modelo}:{context.filing_year}:{context.period.registry_token}:prorrata-current-year",
            source_periods=(context.period.registry_token,),
            source_casilla_ids=(volumen_con_derecho_id, volumen_total_id, definitiva_id),
        )
        if not applicability.applies:
            return _zero_prorrata_resolution(
                revision=revision,
                context=context,
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                declared_binding_ids=declared_binding_ids,
                provenance=current_provenance,
            )
        refusal = self._applicable_settlement_refusal(context, register, undeclared, applicability)
        if refusal is not None:
            return self._unresolved(revision, declared_binding_ids, refusal)

        prior_definitiva = _stamped_prior_year_definitiva(
            self._observation_repository,
            operation=self._operation,
            filing_year=context.filing_year,
            modelo=_prorrata_source_modelo(revision),
            revision=revision,
        )
        provisional_source = _resolve_prorrata_provisional_source(
            register,
            prior_definitiva,
            context=context,
            revision=revision,
            current_provenance=current_provenance,
        )
        if provisional_source.percentage is None:
            return self._unresolved(
                revision,
                declared_binding_ids,
                tr(
                    "application.calculations.prorrata_regularizacion.unresolved.provisional_missing",
                    year=context.filing_year,
                ),
                provisional_source.provenance,
            )

        return self._regularised_resolution(
            context,
            revision,
            declared_binding_ids,
            register,
            provisional_percentage=provisional_source.percentage,
            provisional_provenance=provisional_source.provenance,
            whole_entity_definitive=self._current_year_values[definitiva_id],
        )

    def _regularised_resolution(
        self,
        context: CalculationSourceContext,
        revision: ModeloRevision,
        declared_binding_ids: tuple[BindingId, ...],
        register: ProrrataRegister,
        *,
        provisional_percentage: Decimal,
        provisional_provenance: tuple[CalculationSourceProvenance, ...],
        whole_entity_definitive: Decimal,
    ) -> CalculationSourceResolution:
        """Regularise the earlier liquidations at each partition's definitive percentage."""
        liquidation_periods = m303_liquidation_periods(context.period, authority=self._operation)
        regularised_periods = liquidation_periods[:-1]
        source_modelo = _prorrata_source_modelo(revision)
        totals = self._periods.totals(
            context,
            regularised_periods,
            source_modelo=source_modelo,
            provisional_percentage=provisional_percentage,
        )
        if isinstance(totals, RegularisedPeriodRefusal):
            return self._unresolved(revision, declared_binding_ids, totals.message, provisional_provenance)
        definitives = partition_definitive_percentages(
            context,
            register,
            totals,
            whole_entity_definitive=whole_entity_definitive,
            cross_sector_common_use=register.is_sectorized
            and (
                totals.common_use_sector_input
                or self._periods.settlement_common_use_input(context, liquidation_periods[-1])
            ),
        )
        if isinstance(definitives, RegularisedPeriodRefusal):
            return self._unresolved(revision, declared_binding_ids, definitives.message, provisional_provenance)
        result = compute_regularizacion_prorrata_particionada(
            particiones=tuple(
                RegularizacionProrrataParticion(
                    cuotas_soportadas_deducibles=gross,
                    prorrata_definitiva_pct=definitives[sector_id],
                )
                for sector_id, gross in totals.gross_by_partition.items()
            ),
            deducciones_provisionales_practicadas=totals.practised,
        )
        tokens = tuple(period.registry_token for period in regularised_periods)
        periods_provenance = _source_provenance(
            context=context,
            revision=revision,
            source_ref=f"{source_modelo}:{context.filing_year}:{','.join(tokens)}:prorrata-regularised-periods",
            source_periods=tokens,
            source_casilla_ids=totals.casilla_ids,
        )
        return _valued_prorrata_resolution(
            revision=revision,
            context=context,
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            declared_binding_ids=declared_binding_ids,
            value=result.importe,
            provenance=(
                *provisional_provenance,
                periods_provenance,
                *_operator_declared_provenance(
                    context=context,
                    revision=revision,
                    declarations=totals.operator_declared,
                    parent=periods_provenance,
                ),
            ),
        )

    def _applicable_settlement_refusal(
        self,
        context: CalculationSourceContext,
        register: ProrrataRegister,
        undeclared: tuple[CasillaId, ...],
        applicability: ProrrataApplicabilityProjection,
    ) -> str | None:
        """Name why an applicable prorrata cannot be regularised from the current inputs."""
        if undeclared:
            return tr(
                "application.calculations.prorrata_regularizacion.unresolved.volumes_undeclared",
                year=context.filing_year,
                casillas=", ".join(undeclared),
            )
        if applicability.declared_volume_sin_derecho <= Decimal("0"):
            return tr(
                "application.calculations.prorrata_regularizacion.unresolved.sin_derecho_volume_absent",
                year=context.filing_year,
            )
        entry = _entry_for_register_provenance(register, ejercicio=context.filing_year)
        if entry is not None and not regime_apportions_deduction(entry.regime, authority=self._operation):
            return tr(
                "application.calculations.prorrata_regularizacion.unresolved.register_regime_not_apportioning",
                year=context.filing_year,
            )
        return None


__all__ = [
    "ProrrataApplicabilityProjection",
    "ProrrataDeclaredVolumeLedgerRollup",
    "ProrrataRegularizacionSourceResolver",
    "build_prorrata_declared_volume_advisory",
    "build_prorrata_missing_provisional_advisory",
    "derive_prorrata_applicability",
]
