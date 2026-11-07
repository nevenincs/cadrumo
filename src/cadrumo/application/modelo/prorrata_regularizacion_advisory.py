"""Calculate-path advisories for the annual prorrata regularisation.

The Modelo 303 regularisation box itself (LIVA art. 105.Cuatro) is filled by
the ``BindingSourceKind.PRORRATA_REGULARIZACION`` source resolver, which
refuses visibly whenever a governed input is missing. This collector keeps the
advisories that are not a box value:

* for every period, a missing-carry advisory when prorrata applies but the
  provisional percentage ladder in the profile-scoped register is unresolved;
* at the annual settlement liquidation, the declared-volume reconciliation
  against the ledger and the LIVA art. 103.Dos.2.º mandatory-especial check.

It does not recompute the regularisation: a second computation here could
only disagree with the resolver's value.

See Also:
    :mod:`~application.modelo.calculation_diagnostics`:
        Post-calculation coordinator that calls this collector with the
        computed casilla values.
    :mod:`~application.calculations.prorrata_regularizacion`:
        Source resolver that owns the regularisation value and its refusals.
    :mod:`~application.modelo.bienes_inversion_advisory`:
        Sibling advisory collector for the capital-goods IVA regularización
        (LIVA arts. 107-110), whose settlement-period gating this module
        mirrors.
"""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import nullcontext
from decimal import Decimal

from ...core.aggregation import BindingSourceKind
from ...core.casilla_id import CasillaId
from ...core.external_constants import OutputLanguage
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.iva.m303_settlement import is_m303_annual_settlement_period
from ...domain.iva.prorrata import especial_mandatory_rule
from ...domain.iva.prorrata_especial_parameters import (
    resolve_prorrata_especial_mandatory_parameters,
)
from ...domain.prorrata_register.register import ProrrataRegisterError
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..aggregation.iva_ledger import aggregate_iva_ledger_observations_from_repositories
from ..aggregation.iva_ledger_classification import compute_annual_deducible_totals_by_regime
from ..aggregation.prorrata_volume import project_prorrata_declared_volume_rollup
from ..aggregation.source_mesh import CalculationSourceDiagnostic
from ..bienes_inversion.ports import BienesInversionIvaRegisterRepositoryProtocol
from ..calculations.prorrata_especial_advisory import build_prorrata_especial_mandatory_advisory
from ..calculations.prorrata_regularizacion import (
    ProrrataDeclaredVolumeLedgerRollup,
    build_prorrata_declared_volume_advisory,
    build_prorrata_missing_provisional_advisory,
    derive_prorrata_applicability,
)
from ..prorrata_register.ports import ProrrataRegisterServiceRepositoryProtocol
from ..prorrata_register.service import require_prorrata_register_coordinates_current
from .semantic_role_resolution import casilla_id_for_unambiguous_revision_semantic_role

__all__ = ["collect_prorrata_regularizacion_diagnostics"]

#: Modelo 303 registry period tokens at which the LIVA art. 105.Cuatro annual
#: regularización settles: the fourth quarter for standard quarterly filers,
#: and the annual period for filers on an annual-only cadence. A mid-year
#: quarter (1T/2T/3T) is never a regularisation event, so this collector is
#: silent on those periods (no noise for a compute that is not yet due).
_VOLUMEN_TOTAL_SEMANTIC_ROLE = "iva_prorrata_volumen_total"
_VOLUMEN_CON_DERECHO_SEMANTIC_ROLE = "iva_prorrata_volumen_con_derecho"

#: Shared ``source_kind`` for both LIVA art. 103.Dos.2.º mandatory-especial
#: settlement diagnostics — the CHECK-branch obligation advisory and the
#: PROMPT-branch classify-to-enable advisory. The distinguishing ``reason``
#: (``prorrata_especial_obligatoria`` vs ``prorrata_especial_check_unavailable``)
#: rides alongside on ``Notice.context`` at the CLI projection.
_ESPECIAL_MANDATORY_SOURCE_KIND = "prorrata_especial_mandatory"


def _settlement_prorrata_diagnostics(
    revision: ModeloRevision,
    *,
    modelo: str,
    filing_year: int,
    missing_carry_diagnostics: tuple[CalculationSourceDiagnostic, ...],
    prorrata_register_repository: ProrrataRegisterServiceRepositoryProtocol,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    bienes_inversion_repository: BienesInversionIvaRegisterRepositoryProtocol,
    bucket_id: str | None,
    operation: PinnedAuthorityOperation,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Append settlement-only prorrata diagnostics in their canonical order."""
    especial_diagnostics = _especial_mandatory_diagnostics(
        revision,
        modelo=modelo,
        filing_year=filing_year,
        prorrata_register_repository=prorrata_register_repository,
        transaction_repository=transaction_repository,
        bienes_inversion_repository=bienes_inversion_repository,
        bucket_id=bucket_id,
        operation=operation,
    )
    return (*missing_carry_diagnostics, *especial_diagnostics)


def collect_prorrata_regularizacion_diagnostics(
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    modelo: str,
    period_token: str,
    filing_year: int,
    prorrata_register_repository: ProrrataRegisterServiceRepositoryProtocol,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    bienes_inversion_repository: BienesInversionIvaRegisterRepositoryProtocol,
    bucket_id: str | None = None,
    operation: PinnedAuthorityOperation | None = None,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return the annual prorrata advisories for one Modelo 303 calculation.

    Args:
        revision: The :class:`ModeloRevision` whose casillas are inspected for
            the prorrata semantic roles. Only Modelo 303 revisions declare
            them; every other modelo returns an empty tuple immediately.
        casilla_values: Computed engine values keyed by :class:`CasillaId`.
        modelo: The modelo identifier of the filing being calculated.
        period_token: Bare registry period token for the filing being
            calculated (e.g. ``"4T"``, ``"1T"``, ``"12"``).
        filing_year: The ejercicio being calculated.
        prorrata_register_repository: Required bucket-bound register capability
            used for the provisional carry and annual regime comparison.
        transaction_repository: Required bucket-bound transaction catalogue
            capability used by the annual IVA settlement comparison.
        bienes_inversion_repository: Required bucket-bound capital-goods
            register the annual IVA settlement comparison proves the year's
            investment acquisitions against.
        bucket_id: Optional bucket identifier for loading the profile-scoped
            prorrata register. When supplied, unresolved provisional register
            state emits a per-period missing-carry advisory before settlement.
        operation: The calculation's pinned registry authority. Standalone
            callers may omit it to lease one for this collector.

    Returns:
        The per-period missing-provisional-carry advisory and, at the annual
        settlement liquidation, the declared-volume reconciliation and the
        LIVA art. 103.Dos.2.º mandatory-especial advisory (the obligation
        check when both regime totals are computable, or the
        classify-to-enable prompt while any deducible input is unclassified).
        Empty when no advisory fires.
    """
    if modelo != form_for_role("iva.periodic"):
        return ()

    with nullcontext(operation) if operation is not None else bundled_indexed_authority().operation() as authority:
        try:
            rollup = _annual_volume_rollup(
                revision,
                casilla_values,
                modelo=modelo,
                filing_year=filing_year,
                bucket_id=bucket_id,
                transaction_repository=transaction_repository,
                prorrata_register_repository=prorrata_register_repository,
                bienes_inversion_repository=bienes_inversion_repository,
                operation=authority,
            )
        except ProrrataRegisterError as exc:
            return (_prorrata_storage_degraded_diagnostic(bucket_id, exc),)
        missing_carry_diagnostics = _missing_carry_diagnostics(
            revision,
            casilla_values,
            modelo=modelo,
            filing_year=filing_year,
            prorrata_register_repository=prorrata_register_repository,
            bucket_id=bucket_id,
            operation=authority,
            ledger_rollup=rollup,
        )
        if not is_m303_annual_settlement_period(Period.from_year_and_code(filing_year, period_token)):
            return missing_carry_diagnostics

        volume_diagnostic = (
            build_prorrata_declared_volume_advisory(rollup, ejercicio=filing_year) if rollup is not None else None
        )
        volume_diagnostics = () if volume_diagnostic is None else (volume_diagnostic,)
        # Settlement-only checks keep their own canonical order: the regularización
        # advisory (or pending carry) precedes the mandatory-especial diagnostic.
        return (
            *volume_diagnostics,
            *_settlement_prorrata_diagnostics(
                revision,
                modelo=modelo,
                filing_year=filing_year,
                missing_carry_diagnostics=missing_carry_diagnostics,
                prorrata_register_repository=prorrata_register_repository,
                transaction_repository=transaction_repository,
                bienes_inversion_repository=bienes_inversion_repository,
                bucket_id=bucket_id,
                operation=authority,
            ),
        )


def _especial_mandatory_diagnostics(
    revision: ModeloRevision,
    *,
    modelo: str,
    filing_year: int,
    prorrata_register_repository: ProrrataRegisterServiceRepositoryProtocol,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    bienes_inversion_repository: BienesInversionIvaRegisterRepositoryProtocol,
    bucket_id: str | None,
    operation: PinnedAuthorityOperation,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return the LIVA art. 103.Dos.2.º mandatory-especial settlement diagnostic.

    Computes the ejercicio's whole-year deducible IVA cuota under both prorrata
    regimes (one annual aggregation, two apportionment passes) and branches on
    whether the especial total is honestly computable:

    * CHECK branch (every deducible soportado row classified, whatever the
      register regime): run the
      real art. 103.Dos.2.º comparison through
      :func:`~application.calculations.prorrata_especial_advisory.build_prorrata_especial_mandatory_advisory`
      and surface its message verbatim as a ``prorrata_especial_obligatoria``
      diagnostic. A non-breach returns nothing (no noise).
    * PROMPT branch (any unclassified deducible soportado row, so the especial
      total is not derivable): emit one ``prorrata_especial_check_unavailable`` diagnostic that
      names the obligation and the enabling ``--input-classification`` /
      ``elect-especial`` actions, carrying NO fabricated amounts.

    Returns an empty tuple when no register apportionment resolves, the register
    is sectorized (a named v1 deferral), or the bucket id is absent.
    """
    if bucket_id is None:
        return ()
    totals = compute_annual_deducible_totals_by_regime(
        bucket_id=bucket_id,
        ejercicio=filing_year,
        revision=revision,
        prorrata_register_repository=prorrata_register_repository,
        transaction_repository=transaction_repository,
        investment_asset_register=bienes_inversion_repository.load(),
        investment_asset_profile_id=bucket_id,
        operation=operation,
    )
    if totals is None:
        return ()

    # Art. 106 gives no percentage to an input whose use is undeclared, so the
    # especial total is honest only once every deducible row is classified,
    # whatever regime the register records.
    especial_total = totals.deduction_under_especial if totals.unclassified_deducible_count == 0 else None
    # Resolved BEFORE the branch because both arms need it: the advisory arm
    # passes it to the predicate, and the prompt arm below quotes the margin in
    # its operator-facing wording. Binding it inside the branch left the prompt
    # arm reading an unbound name.
    #
    # A refusal here is a genuine grounding defect: this path is gated to a
    # modelo 303 annual settlement period, and every modelo 303 revision
    # declares the art-103.Dos.2 margin. It carries a registered error code and
    # an operator-facing message, so it is allowed to surface rather than being
    # swallowed into an empty diagnostic tuple.
    especial_parameters = resolve_prorrata_especial_mandatory_parameters(
        revision,
        modelo_id=modelo,
        ejercicio=filing_year,
    )
    if especial_total is not None:
        notice = build_prorrata_especial_mandatory_advisory(
            deduction_under_general=totals.deduction_under_general,
            deduction_under_especial=especial_total,
            ejercicio=filing_year,
            parameters=especial_parameters,
            operation=operation,
        )
        if notice is None:
            return ()
        return (
            CalculationSourceDiagnostic(
                reason="prorrata_especial_obligatoria",
                source_kind=_ESPECIAL_MANDATORY_SOURCE_KIND,
                message=notice.message,
                message_language=OutputLanguage.ES,
                # Advisory-asserted: this diagnostic holds no casilla (the annual
                # comparison runs across the whole ejercicio's ledger, not one
                # revision casilla), and its message -- built by
                # build_prorrata_especial_mandatory_advisory -- states the art.
                # 103.Dos.2.º mandatory-especial obligation verbatim.
                asserted_legal_refs=("ley-37-1992:art-103",),
            ),
        )

    rule = especial_mandatory_rule(filing_year, parameters=especial_parameters)
    exceso = (
        f"en un {rule.margin_percentage} por ciento o más"
        if rule.inclusive
        else f"en más de un {rule.margin_percentage} por ciento"
    )
    return (
        CalculationSourceDiagnostic(
            reason="prorrata_especial_check_unavailable",
            source_kind=_ESPECIAL_MANDATORY_SOURCE_KIND,
            message_language=OutputLanguage.ES,
            message=(
                f"La prorrata especial puede ser obligatoria en {filing_year} (LIVA art. 103.Dos.2.º: "
                f"cuando la deducción por prorrata general excede {exceso} la de la regla especial). "
                "Para comprobarlo, clasifica el uso de cada cuota soportada (art. 106): declara "
                "'--input-classification' en las operaciones del ejercicio y, en su caso, ejecuta "
                f"'app ledger prorrata elect-especial --ejercicio {filing_year}'. "
                f"Quedan {totals.unclassified_deducible_count} operaciones sin clasificar."
            ),
            # Advisory-asserted, no casilla here either: the message states both
            # the art. 103.Dos.2.º mandatory-especial threshold AND the art. 106
            # per-input classification the prompt asks the operator to perform.
            asserted_legal_refs=("ley-37-1992:art-103", "ley-37-1992:art-106"),
        ),
    )


def _missing_carry_diagnostics(
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    modelo: str,
    filing_year: int,
    prorrata_register_repository: ProrrataRegisterServiceRepositoryProtocol,
    bucket_id: str | None,
    operation: PinnedAuthorityOperation,
    ledger_rollup: ProrrataDeclaredVolumeLedgerRollup | None,
) -> tuple[CalculationSourceDiagnostic, ...]:
    if bucket_id is None:
        return ()

    volumen_total_id = casilla_id_for_unambiguous_revision_semantic_role(
        revision,
        _VOLUMEN_TOTAL_SEMANTIC_ROLE,
        modelo_id=modelo,
    )
    volumen_con_derecho_id = casilla_id_for_unambiguous_revision_semantic_role(
        revision,
        _VOLUMEN_CON_DERECHO_SEMANTIC_ROLE,
        modelo_id=modelo,
    )
    declared_volume_total = casilla_values.get(volumen_total_id) if volumen_total_id is not None else None
    declared_volume_con_derecho = (
        casilla_values.get(volumen_con_derecho_id) if volumen_con_derecho_id is not None else None
    )

    try:
        register = require_prorrata_register_coordinates_current(
            prorrata_register_repository.load(),
            operation=operation,
        )
    except ProrrataRegisterError as exc:
        return (_prorrata_storage_degraded_diagnostic(bucket_id, exc),)

    declarations_present = declared_volume_total is not None and declared_volume_con_derecho is not None
    applicability = derive_prorrata_applicability(
        register_entries=register.entries_for_ejercicio(filing_year),
        ledger_rollup=ledger_rollup,
        declared_volume_total=declared_volume_total if declarations_present else None,
        declared_volume_con_derecho=declared_volume_con_derecho if declarations_present else None,
    )
    diagnostic = build_prorrata_missing_provisional_advisory(
        applicability=applicability,
        provisional_resolution=register.resolve_provisional(filing_year),
        ejercicio=filing_year,
        revision=revision,
    )
    return () if diagnostic is None else (diagnostic,)


def _annual_volume_rollup(
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    modelo: str,
    filing_year: int,
    bucket_id: str | None,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    prorrata_register_repository: ProrrataRegisterServiceRepositoryProtocol,
    bienes_inversion_repository: BienesInversionIvaRegisterRepositoryProtocol,
    operation: PinnedAuthorityOperation,
) -> ProrrataDeclaredVolumeLedgerRollup | None:
    if bucket_id is None:
        return None
    total_id = casilla_id_for_unambiguous_revision_semantic_role(
        revision,
        _VOLUMEN_TOTAL_SEMANTIC_ROLE,
        modelo_id=modelo,
    )
    right_id = casilla_id_for_unambiguous_revision_semantic_role(
        revision,
        _VOLUMEN_CON_DERECHO_SEMANTIC_ROLE,
        modelo_id=modelo,
    )
    aggregation = aggregate_iva_ledger_observations_from_repositories(
        bucket_id=bucket_id,
        period=Period.from_year_and_code(filing_year, "0A"),
        prorrata_register_repository=prorrata_register_repository,
        transaction_repository=transaction_repository,
        investment_asset_register=bienes_inversion_repository.load(),
        investment_asset_profile_id=bucket_id,
        operation=operation,
    )
    return project_prorrata_declared_volume_rollup(
        aggregation,
        declared_volume_total=casilla_values.get(total_id) if total_id is not None else None,
        declared_volume_con_derecho=casilla_values.get(right_id) if right_id is not None else None,
        operation=operation,
    )


def _prorrata_storage_degraded_diagnostic(
    bucket_id: str | None, error: ProrrataRegisterError
) -> CalculationSourceDiagnostic:
    """Retain the existing observable refusal when the register cannot be read."""
    return CalculationSourceDiagnostic(
        reason="storage_degraded",
        source_kind=BindingSourceKind.PRORRATA_REGULARIZACION.value,
        message=f"prorrata register could not be read (bucket {bucket_id!r}): {error}",
    )
