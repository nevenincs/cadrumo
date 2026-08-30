"""Binding prefill: resolve ``previous_filing`` bindings from prior filings.

Used by :class:`~._multi_year.PreviousFilingSourceResolver` for the source-mesh
calculation path and by
:func:`~application.calculations.extract_modelo_303_local_iva_compensation_recurrence`
for the IVA wallet comparison path.

One of three distinct prefill tiers, NOT to be merged: this is the
PREVIOUS-FILING direct-carry tier. The other two are the relation tier
(:mod:`~application.calculations._relation_prefill`) and the AEAT borrador
pre-fill tier (the registry ``aeat_prefilled`` flag, an AEAT-live source). They
share only the word "prefill"; each routes a different source through a
different mechanism.

Sister module to :mod:`~._relation_prefill`. The runtime distinguishes
``relation`` leaves (cross-revision aggregations declared as
:class:`~domain.calculations.registry.RelationDefinition` records) from
``previous_filing`` bindings (declared as
:class:`~domain.calculations.registry.DataBindingDefinition` with
``source = "previous_filing"``).
Modelo 390 uses bindings — modelo 200 uses relations — both express
"sum a prior modelo's casilla across periods" but route through
different schema entities.

Prior-filing values are gathered as :class:`CasillaObservation` records and
merged inside
:class:`~domain.calculations.registry.RegistryModeloObservation` rows before
the binding is resolved.

The strict registry boundary remains
:func:`~domain.calculations.registry.previous_filing_observation_requirements`
and
:func:`~domain.calculations.registry.resolve_previous_filing_binding_values`;
this module is the application reader that supplies local observations from
:class:`~.observations_repository.CalculationObservationRepository` and returns
:class:`BindingPrefillReport` coverage.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Final

from pydantic import BaseModel, TypeAdapter

from ...core import STR_KEYED_MAPPING_ADAPTER, Modelo, Period
from ...core.casilla_id import CasillaId
from ...core.aggregation import BindingSourceKind
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.resources import bundled_path
from ...core.time import now
from ...domain.calculations.registry.bindings import (
    CasillaObservation,
    RegistryModeloObservation,
    binding_source_casilla_ids,
)
from ...domain.calculations.registry.bindings_previous_filing import (
    previous_filing_observation_requirements,
    resolve_previous_filing_binding_values,
)
from ...domain.calculations.registry.ids import (
    BindingId,
    RevisionId,
)
from ...domain.calculations.registry.iva_wallet_relation_targets import MODELO_303_IVA_COMPENSATION_BINDING_ID
from ...domain.calculations.registry.loader import load_registry_tree
from ...domain.calculations.registry.relations import RegistryFoldRequirement
from ...domain.calculations.registry.runtime_graph import expression_casilla_refs
from ...domain.calculations.registry.schema import FormulaDefinition, RegistrySnapshot
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from ...domain.calculations.registry.temporal import select_revision
from ...domain.iva_compensation.carry_forward import IvaCompensationPeriodState
from ...domain.iva_compensation.errors import IvaCompensationCasillaReferenceError
from ._iva_compensation_casillas import (
    M303_COMPENSACION_APLICADA_CASILLA as _M303_COMPENSACION_APLICADA_CASILLA,
)
from ._iva_compensation_casillas import (
    M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA as _M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA,
)
from ._iva_compensation_casillas import (
    M303_DISPONIBLE_CASILLA as _M303_DISPONIBLE_CASILLA,
)
from ._iva_compensation_casillas import (
    M303_GENERADA_CASILLA as _M303_GENERADA_CASILLA,
)
from ._iva_compensation_casillas import (
    M303_POSTERIOR_CASILLA as _M303_POSTERIOR_CASILLA,
)
from ._iva_compensation_casillas import (
    M303_RESULTADO_CASILLA as _M303_RESULTADO_CASILLA,
)
from ._iva_compensation_casillas import (
    M303_RESULTADO_FINAL_CASILLA as _M303_RESULTADO_FINAL_CASILLA,
)
from ._per_grupo_member_keys import per_grupo_member_requirement_keys
from ._revision_carry_gate import revision_carry_outcome
from .errors import BindingPrefillTypeError
from .iva_compensation_history import IvaCompensationHistoryRepository
from .observations_repository import CalculationObservationRepository, ObservationEnvelopePayload

_STRING_SEQUENCE = TypeAdapter(tuple[str, ...])


def _selector_year_delta(value: object) -> int:
    """Narrow a binding-selector ``filing_year_delta`` to ``int``.

    Selectors flow through pydantic with a union value type, so static
    analysis loses the per-key shape; an explicit guard restores it and
    rejects unexpected payloads at runtime.
    """
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        return int(value)
    raise BindingPrefillTypeError(
        translated_message="application.calculations.binding_prefill.errors.selector_filing_year_delta_type",
        context={"selector_key": "filing_year_delta", "observed_type": type(value).__name__},
    )


def _selector_periods(value: object) -> tuple[str, ...]:
    """Normalise a binding-selector ``source_periods`` into a tuple of strings."""
    if isinstance(value, str):
        return (value,)
    if isinstance(value, tuple):
        try:
            return _STRING_SEQUENCE.validate_python(value)
        except ValueError as exc:
            raise BindingPrefillTypeError(
                translated_message="application.calculations.binding_prefill.errors.selector_source_periods_member_type",
                context={"selector_key": "source_periods"},
            ) from exc
    raise BindingPrefillTypeError(
        translated_message="application.calculations.binding_prefill.errors.selector_source_periods_type",
        context={"selector_key": "source_periods", "observed_type": type(value).__name__},
    )


_LOCAL_FILING_PROVENANCE: Final = "local_filing"
_PRE_ACTIVITY_NO_PRIOR_OBLIGATION_SOURCE_KIND: Final = "pre_activity_no_prior_obligation"
_IVA_COMPENSATION_HISTORY_SOURCE_KIND: Final = "aeat_sede_iva_compensation_history"
_MIXED_OBSERVATION_SOURCE_KIND: Final = "mixed_observation_sources"


def _revision_carry_outcome(payload: ObservationEnvelopePayload) -> bool:
    """Return whether a payload's revision stamp must be refused.

    Thin adapter over the single shared
    :func:`~application.calculations._revision_carry_gate.revision_carry_outcome`
    gate: it extracts the source context off the payload's observation and
    delegates the refusal decision so the binding-prefill, cross-period
    clean-state, and relation-prefill carry reads share one law-determined
    re-confirmation rather than three parallel copies.
    """
    obs = payload.observation
    return revision_carry_outcome(
        payload.stamped_revision_id,
        source_modelo=obs.modelo,
        source_filing_year=obs.filing_year,
        source_period=obs.period,
    ).refused


class _GatheredObservation(BaseModel):
    """Registry observation plus the persisted source channel that produced it."""

    model_config = _STRICT_FROZEN

    observation: RegistryModeloObservation
    source_kind: str
    casilla_source_kinds: Mapping[CasillaId, str]


def _gathered_observation(
    observation: RegistryModeloObservation,
    *,
    source_kind: str,
) -> _GatheredObservation:
    return _GatheredObservation(
        observation=observation,
        source_kind=source_kind,
        casilla_source_kinds={item.casilla_id: source_kind for item in observation.observations},
    )


def _merge_gathered_observations(
    primary: _GatheredObservation,
    overlay: _GatheredObservation,
) -> _GatheredObservation:
    """Merge same-filing observations while preserving casilla-level provenance.

    The registry previous-filing resolver accepts one observation for each
    single-filer ``(modelo, filing_year, period)``. Secure IVA-history
    projections therefore have to be folded into the app-filing observation
    before resolution, otherwise one source shadows the other.
    """
    primary_key = (primary.observation.modelo, primary.observation.filing_year, primary.observation.period)
    overlay_key = (overlay.observation.modelo, overlay.observation.filing_year, overlay.observation.period)
    if primary_key != overlay_key:
        raise BindingPrefillTypeError(
            translated_message="application.calculations.binding_prefill.errors.observation_merge_key_conflict",
            context={
                "primary_modelo": primary.observation.modelo,
                "primary_filing_year": primary.observation.filing_year,
                "primary_period": str(primary.observation.period),
                "overlay_modelo": overlay.observation.modelo,
                "overlay_filing_year": overlay.observation.filing_year,
                "overlay_period": str(overlay.observation.period),
            },
        )

    observations_by_casilla = {item.casilla_id: item for item in primary.observation.observations}
    observations_by_casilla.update({item.casilla_id: item for item in overlay.observation.observations})
    casilla_source_kinds = {
        **dict(primary.casilla_source_kinds),
        **dict(overlay.casilla_source_kinds),
    }
    source_kinds = {primary.source_kind, overlay.source_kind}
    source_kind = primary.source_kind if len(source_kinds) == 1 else _MIXED_OBSERVATION_SOURCE_KIND
    return _GatheredObservation(
        observation=primary.observation.model_copy(update={"observations": tuple(observations_by_casilla.values())}),
        source_kind=source_kind,
        casilla_source_kinds=casilla_source_kinds,
    )


class PrefilledBinding(BaseModel):
    """One resolved previous-filing binding with local-source provenance.

    Emitted by :func:`resolve_bindings_from_local_store` and collected in
    :class:`BindingPrefillReport`. The ``source_*`` fields point back to the
    :class:`~domain.calculations.registry.RegistryModeloObservation` rows
    that satisfied the registry previous-filing requirement.
    """

    model_config = _STRICT_FROZEN

    binding_id: BindingId
    value: Decimal
    #: The registry's declared dependency treatment for this carry, empty when the
    #: revision declares none. A ``factual_evidence`` carry is a fact to reconcile
    #: against rather than a figure that settles the return, and a consumer must be
    #: able to tell it from a ``direct_annual_settlement`` one. Carried here rather
    #: than gated here: the value is NOT withheld, because a taxpayer is entitled to
    #: a suffered retención and dropping it silently is an over-declaration. Empty
    #: means the revision declared no treatment, which is not the same as any
    #: particular one and must never be read as one.
    dependency_treatment: str = ""
    provenance: str = _LOCAL_FILING_PROVENANCE
    source_kind: str = _LOCAL_FILING_PROVENANCE
    source_modelo: str
    source_filing_year: int
    source_periods: tuple[str, ...]
    resolved_at: datetime


class UnsatisfiedBinding(BaseModel):
    """One ``previous_filing`` binding the local store could not supply a value for.

    Carries the coordinates the operator needs to act: which prior filing was
    looked for, and for which year and periods. Emitted so an unsatisfiable carry
    is reported rather than dropped -- every ``previous_filing`` carry is a
    liability-reducing quantity (a payment already made, a loss carried forward,
    a prior valuation baseline), so a silent one produces a return declaring more
    tax than is owed and looking entirely ordinary while it does so.
    """

    model_config = _STRICT_FROZEN

    binding_id: BindingId
    source_modelo: str
    source_filing_year: int
    source_periods: tuple[str, ...]


class BindingPrefillReport(BaseModel):
    """Outcome of one direct previous-filing binding-prefill pass.

    ``binding_values`` is the mapping passed to
    :func:`~domain.calculations.registry.calculate_registry_snapshot`;
    ``prefilled`` keeps the :class:`PrefilledBinding` provenance used by
    :class:`~._multi_year.PreviousFilingSourceResolver` when stamping source-mesh
    results; ``unsatisfied`` names the declared ``previous_filing`` bindings the
    store supplied nothing for, which the same resolver projects onto the
    diagnostics channel.
    """

    model_config = _STRICT_FROZEN

    prefilled: tuple[PrefilledBinding, ...]
    binding_values: Mapping[BindingId, Decimal]
    unsatisfied: tuple[UnsatisfiedBinding, ...] = ()


class LocalIvaCompensationRecurrence(BaseModel):
    """Local Modelo 303 recurrence evidence extracted for wallet reconciliation only.

    This is comparison evidence. It does not choose the effective casilla `110`
    value; the :class:`~._iva_wallet_reconciliation.IvaWalletDecisionSourceResolver`
    and wallet reconciliation decision remain the only selectors.
    """

    model_config = _STRICT_FROZEN

    binding_id: BindingId
    amount: Decimal
    source_kind: str = _LOCAL_FILING_PROVENANCE
    source_modelo: str
    source_filing_year: int
    source_periods: tuple[Period, ...]
    resolved_at: datetime
    source_locator: str | None = None


def _gather_grouped_member_observations(
    req_key: tuple[str, int, str],
    *,
    repository: CalculationObservationRepository,
    needed: dict[tuple[str, int, str, int], _GatheredObservation],
    seen_member: dict[tuple[str, int, str], int],
) -> None:
    """Fold every member's filing for ``req_key`` into ``needed``, member-distinct.

    Cross-member fan-in for the 353<-322 aggregation: enumerate every stored row
    for the modelo (including member-NIF-widened keys) via ``iter_modelo`` rather
    than loading one observation by key, so the resolver can sum across members.
    Mutates the shared ``needed`` and ``seen_member`` accumulators in place to
    preserve the caller's member-index sequencing.
    """
    requirement_modelo = req_key[0]
    for payload in repository.iter_modelo(requirement_modelo):
        obs = payload.observation
        if (obs.modelo, obs.filing_year, obs.period) != req_key:
            continue
        # R2 carry gate: divergent or unreconfirmable stamp -> skip.
        if _revision_carry_outcome(payload):
            continue
        member_idx = seen_member.get(req_key, 0)
        seen_member[req_key] = member_idx + 1
        needed[(obs.modelo, obs.filing_year, obs.period, member_idx)] = _gathered_observation(
            obs,
            source_kind=payload.source_kind,
        )


def _gathered_from_payload(payload: ObservationEnvelopePayload | None) -> _GatheredObservation | None:
    """Apply the R2 carry gate to a single-key payload.

    Divergent or unreconfirmable source revision stamps refuse the carry.
    """
    if payload is None:
        return None
    if _revision_carry_outcome(payload):
        return None
    return _gathered_observation(
        payload.observation,
        source_kind=payload.source_kind,
    )


def _gather_single_key_observation(
    requirement_modelo: str,
    requirement_filing_year: int,
    requirement_period: str,
    *,
    repository: CalculationObservationRepository,
    iva_history_repository: IvaCompensationHistoryRepository | None,
) -> _GatheredObservation | None:
    """Load one observation by key, folding in any secure Modelo 303 IVA history.

    The single-filer path: one observation per ``(modelo, filing_year, period)``.
    For Modelo 303 a secure IVA-compensation-history projection is merged into the
    app-filing observation (when both exist) so neither source shadows the other.
    """
    gathered = _gathered_from_payload(
        repository.load_observation(
            requirement_modelo,
            Period.from_year_and_code(requirement_filing_year, requirement_period),
        ),
    )
    if requirement_modelo == Modelo.M303.value and iva_history_repository is not None:
        state = iva_history_repository.load_period(
            Period.from_year_and_code(requirement_filing_year, requirement_period),
        )
        if state is not None:
            history_gathered = _gathered_observation(
                _observation_from_iva_compensation_history(state),
                source_kind=_IVA_COMPENSATION_HISTORY_SOURCE_KIND,
            )
            gathered = (
                _merge_gathered_observations(gathered, history_gathered) if gathered is not None else history_gathered
            )
    return gathered


def _gather_observations(
    snapshot: RegistrySnapshot,
    *,
    repository: CalculationObservationRepository,
    iva_history_repository: IvaCompensationHistoryRepository | None = None,
    excluded_binding_ids: frozenset[BindingId] | None = None,
) -> tuple[_GatheredObservation, ...]:
    """Walk every previous_filing binding in the revision and pull matching observations from the local store.

    For ordinary single-filer requirements one observation per
    ``(modelo, filing_year, period)`` is loaded by key
    (:func:`_gather_single_key_observation`). For a requirement whose binding
    declares ``grouping = "per_grupo_member"`` (the 353<-322 cross-member
    aggregation), EVERY member's filing for that ``(modelo, filing_year, period)``
    must be gathered (:func:`_gather_grouped_member_observations`), so the resolver
    can sum across members.
    """
    grouped_keys = per_grupo_member_requirement_keys(
        snapshot.revision,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    )
    excluded = excluded_binding_ids or frozenset()
    needed: dict[tuple[str, int, str, int], _GatheredObservation] = {}
    seen_member: dict[tuple[str, int, str], int] = {}
    for requirement in previous_filing_observation_requirements(
        snapshot.revision,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    ):
        if requirement.binding_ids and all(binding_id in excluded for binding_id in requirement.binding_ids):
            continue
        req_key = (requirement.source_modelo, requirement.filing_year, requirement.periods[0])
        if req_key in grouped_keys:
            _gather_grouped_member_observations(
                req_key,
                repository=repository,
                needed=needed,
                seen_member=seen_member,
            )
            continue
        gathered = _gather_single_key_observation(
            requirement.source_modelo,
            requirement.filing_year,
            requirement.periods[0],
            repository=repository,
            iva_history_repository=iva_history_repository,
        )
        if gathered is None:
            continue
        obs = gathered.observation
        needed.setdefault(
            (obs.modelo, obs.filing_year, obs.period, 0),
            gathered,
        )
    return tuple(needed.values())


def _observation_from_iva_compensation_history(
    state: IvaCompensationPeriodState,
) -> RegistryModeloObservation:
    """Project secure IVA compensation history into the registry resolver contract."""
    modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(candidate for candidate in modelos if candidate.id == Modelo.M303.value)
    revision = select_revision(
        modelo,
        filing_year=state.filing_year,
        period=state.period.registry_token,
    )
    casillas = {item.id: item for item in revision.casillas}
    formulas = {item.target_casilla_id: item for item in revision.formulas}

    def observed(casilla_id: CasillaId, value: Decimal | None) -> tuple[CasillaObservation, ...]:
        if value is None:
            return ()
        operand_refs: tuple[CasillaId, ...] = ()
        operand_values: tuple[Decimal, ...] = ()
        if casilla_id == _M303_POSTERIOR_CASILLA and (
            state.prior_pending_amount is not None and state.applied_amount is not None
        ):
            operand_refs = (_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA, _M303_COMPENSACION_APLICADA_CASILLA)
            operand_values = (state.prior_pending_amount, state.applied_amount)
        elif casilla_id == _M303_GENERADA_CASILLA and state.period_result_amount is not None:
            operand_refs = (_M303_RESULTADO_CASILLA,)
            operand_values = (state.period_result_amount,)
        elif casilla_id == _M303_DISPONIBLE_CASILLA and state.pending_for_later_amount is not None:
            operand_refs = (_M303_POSTERIOR_CASILLA, _M303_GENERADA_CASILLA)
            operand_values = (state.pending_for_later_amount, state.generated_amount)
        return _iva_compensation_history_observation(
            modelo_id=Modelo.M303.value,
            revision_id=revision.id,
            casillas=casillas,
            formulas=formulas,
            casilla_id=casilla_id,
            value=value,
            operand_refs=operand_refs,
            operand_values=operand_values,
        )

    return RegistryModeloObservation(
        modelo=Modelo.M303.value,
        filing_year=state.filing_year,
        period=state.period.registry_token,
        observations=(
            *observed(_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA, state.prior_pending_amount),
            *observed(_M303_COMPENSACION_APLICADA_CASILLA, state.applied_amount),
            *observed(_M303_POSTERIOR_CASILLA, state.pending_for_later_amount),
            *observed(_M303_RESULTADO_CASILLA, state.period_result_amount),
            *observed(_M303_RESULTADO_FINAL_CASILLA, state.final_result_amount),
            *observed(_M303_GENERADA_CASILLA, state.generated_amount),
            *observed(_M303_DISPONIBLE_CASILLA, state.available_end_amount),
        ),
    )


def _iva_compensation_history_observation(
    *,
    modelo_id: str,
    revision_id: RevisionId,
    casillas: Mapping[CasillaId, CasillaDefinition],
    formulas: Mapping[CasillaId, FormulaDefinition],
    casilla_id: CasillaId,
    value: Decimal,
    operand_refs: tuple[CasillaId, ...] = (),
    operand_values: tuple[Decimal, ...] = (),
) -> tuple[CasillaObservation, ...]:
    """Project one IVA history casilla, failing if registry provenance is missing."""
    casilla = casillas.get(casilla_id)
    if casilla is None:
        raise IvaCompensationCasillaReferenceError(
            translated_message="application.calculations.iva_compensation.errors.history_casilla_undeclared",
            context={
                "modelo": modelo_id,
                "revision_id": revision_id,
                "casilla_id": casilla_id,
            },
        )
    formula = formulas.get(casilla_id)
    formula_id = None
    if len(operand_values) != len(operand_refs):
        raise IvaCompensationCasillaReferenceError(
            translated_message="application.calculations.iva_compensation.errors.history_operand_ref_value_arity",
            context={
                "modelo": modelo_id,
                "revision_id": revision_id,
                "casilla_id": casilla_id,
                "operand_ref_count": len(operand_refs),
                "operand_value_count": len(operand_values),
            },
        )
    if operand_refs and formula is None:
        raise IvaCompensationCasillaReferenceError(
            translated_message="application.calculations.iva_compensation.errors.history_operand_refs_without_formula",
            context={
                "modelo": modelo_id,
                "revision_id": revision_id,
                "casilla_id": casilla_id,
            },
        )
    if formula is not None:
        expected_operand_refs = expression_casilla_refs(formula.expression)
        if operand_refs:
            if operand_refs != expected_operand_refs:
                raise IvaCompensationCasillaReferenceError(
                    translated_message=(
                        "application.calculations.iva_compensation.errors.history_operand_refs_diverge_from_formula"
                    ),
                    context={
                        "modelo": modelo_id,
                        "revision_id": revision_id,
                        "casilla_id": casilla_id,
                        "formula_id": formula.id,
                        "supplied_operand_refs": operand_refs,
                        "formula_operand_refs": expected_operand_refs,
                    },
                )
            formula_id = formula.id
        elif not expected_operand_refs:
            formula_id = formula.id
    return (
        CasillaObservation(
            casilla_id=casilla_id,
            value=value,
            formula_id=formula_id,
            operand_refs=operand_refs,
            operand_casilla_refs=operand_refs,
            operand_values=operand_values,
            legal_refs=tuple(casilla.legal_refs),
            source_refs=tuple(casilla.source_refs),
        ),
    )


def _requirements_by_binding(
    snapshot: RegistrySnapshot,
) -> dict[str, tuple[str, int, tuple[str, ...], str]]:
    grouped: dict[str, tuple[str, int, set[str], str]] = {}
    for requirement in previous_filing_observation_requirements(
        snapshot.revision,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    ):
        for binding_id in requirement.binding_ids:
            current = grouped.setdefault(
                binding_id,
                (
                    requirement.source_modelo,
                    requirement.filing_year,
                    set(),
                    requirement.dependency_treatment or "",
                ),
            )
            current[2].add(requirement.periods[0])
    return {
        binding_id: (source_modelo, source_year, tuple(sorted(periods)), dependency_treatment)
        for binding_id, (source_modelo, source_year, periods, dependency_treatment) in grouped.items()
    }


def _unsatisfied_previous_filing_bindings(
    snapshot: RegistrySnapshot,
    *,
    resolved_binding_ids: frozenset[BindingId],
    excluded_binding_ids: frozenset[BindingId] | None,
) -> tuple[UnsatisfiedBinding, ...]:
    """Name every declared ``previous_filing`` binding this pass supplied no value for.

    Derived from the revision's own declared bindings rather than from the
    requirement index, so a binding whose requirement produced no row at all -- the
    case where nothing was even looked for -- is reported rather than being
    invisible for the same reason it failed.

    Bindings another authority owns (``excluded_binding_ids``, the IVA wallet's
    compensación slot being the standing case) are not this resolver's to report.
    """
    excluded = excluded_binding_ids or frozenset()
    requirement_index = _requirements_by_binding(snapshot)
    unsatisfied: list[UnsatisfiedBinding] = []
    for binding in snapshot.revision.bindings:
        if binding.source != BindingSourceKind.PREVIOUS_FILING:
            continue
        if binding.id in resolved_binding_ids or binding.id in excluded:
            continue
        selector = binding.selector
        source_modelo, source_filing_year, source_periods, _dependency_treatment = requirement_index.get(
            binding.id,
            (
                str(_selector_value(selector, "source_modelo", "") or ""),
                snapshot.filing_year + _selector_year_delta(_selector_value(selector, "filing_year_delta", 0)),
                _selector_periods(_selector_value(selector, "source_periods", ())),
                "",
            ),
        )
        unsatisfied.append(
            UnsatisfiedBinding(
                binding_id=binding.id,
                source_modelo=source_modelo,
                source_filing_year=source_filing_year,
                source_periods=source_periods,
            ),
        )
    return tuple(unsatisfied)


def _requirement_strictly_before_activity_start(
    requirement: RegistryFoldRequirement,
    activity_start_date: date,
) -> bool:
    """Return whether every source period in a previous-filing requirement is pre-activity."""
    filing_periods = requirement.filing_periods or tuple(
        Period.from_year_and_code(requirement.filing_year, token) for token in requirement.periods
    )
    if not filing_periods:
        return False
    return all(period.has_date_span() and period.end_date < activity_start_date for period in filing_periods)


def _pre_activity_scoped_binding_ids(
    snapshot: RegistrySnapshot,
    activity_start_date: date | None,
) -> frozenset[BindingId]:
    """Binding ids whose every required previous-filing source period is pre-activity."""
    if activity_start_date is None:
        return frozenset[BindingId]()
    requirements_by_binding: dict[BindingId, list[RegistryFoldRequirement]] = {}
    for requirement in previous_filing_observation_requirements(
        snapshot.revision,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    ):
        for binding_id in requirement.binding_ids:
            requirements_by_binding.setdefault(binding_id, []).append(requirement)
    return frozenset(
        binding_id
        for binding_id, requirements in requirements_by_binding.items()
        if requirements
        and all(
            _requirement_strictly_before_activity_start(requirement, activity_start_date)
            for requirement in requirements
        )
    )


def _selector_value(selector: object, key: str, default: object) -> object:
    if isinstance(selector, dict):
        return STR_KEYED_MAPPING_ADAPTER.validate_python(selector).get(key, default)
    return getattr(selector, key, default)


def _source_kind_for_binding(
    gathered: tuple[_GatheredObservation, ...],
    *,
    source_modelo: str,
    source_filing_year: int,
    source_periods: tuple[str, ...],
    source_casilla_ids: tuple[CasillaId, ...] = (),
) -> str:
    required_periods = set(source_periods)
    matched_source_kinds: set[str] = set()
    for item in gathered:
        if (
            item.observation.modelo != source_modelo
            or item.observation.filing_year != source_filing_year
            or item.observation.period not in required_periods
        ):
            continue
        if source_casilla_ids:
            matched_source_kinds.update(
                item.casilla_source_kinds.get(casilla_id, item.source_kind)
                for casilla_id in source_casilla_ids
                if casilla_id in item.observation.casilla_values
            )
        else:
            matched_source_kinds.add(item.source_kind)
    if len(matched_source_kinds) == 1:
        return next(iter(matched_source_kinds))
    if matched_source_kinds:
        return _MIXED_OBSERVATION_SOURCE_KIND
    return _LOCAL_FILING_PROVENANCE


def _prefilled_bindings(
    snapshot: RegistrySnapshot,
    resolved_map: Mapping[BindingId, Decimal],
    *,
    observations: tuple[_GatheredObservation, ...],
    activity_start_date: date | None,
    resolved_at: datetime,
) -> tuple[PrefilledBinding, ...]:
    """Project each resolved previous-filing binding into its provenance record.

    A binding the revision no longer declares is dropped rather than reported
    with a synthesised definition. The source coordinate prefers the registry
    requirement the resolver already matched and falls back to the binding's own
    selector, so a binding resolved outside a requirement still names where its
    value came from.
    """
    binding_index = {binding.id: binding for binding in snapshot.revision.bindings}
    requirement_index = _requirements_by_binding(snapshot)
    pre_activity_zero_binding_ids = _pre_activity_scoped_binding_ids(snapshot, activity_start_date)

    prefilled: list[PrefilledBinding] = []
    for binding_id, value in resolved_map.items():
        binding = binding_index.get(binding_id)
        if binding is None:
            continue
        selector = binding.selector
        source_modelo, source_filing_year, source_periods, dependency_treatment = requirement_index.get(
            binding_id,
            (
                str(_selector_value(selector, "source_modelo", "") or ""),
                snapshot.filing_year + _selector_year_delta(_selector_value(selector, "filing_year_delta", 0)),
                _selector_periods(_selector_value(selector, "source_periods", ())),
                "",
            ),
        )
        source_kind = (
            _PRE_ACTIVITY_NO_PRIOR_OBLIGATION_SOURCE_KIND
            if binding_id in pre_activity_zero_binding_ids
            else _source_kind_for_binding(
                observations,
                source_modelo=source_modelo,
                source_filing_year=source_filing_year,
                source_periods=source_periods,
                source_casilla_ids=binding_source_casilla_ids(binding),
            )
        )
        prefilled.append(
            PrefilledBinding(
                binding_id=binding_id,
                value=Decimal(value),
                source_kind=source_kind,
                source_modelo=source_modelo,
                source_filing_year=source_filing_year,
                source_periods=source_periods,
                dependency_treatment=dependency_treatment,
                resolved_at=resolved_at,
            ),
        )
    return tuple(prefilled)


def resolve_bindings_from_local_store(
    snapshot: RegistrySnapshot,
    *,
    repository: CalculationObservationRepository | None = None,
    iva_history_repository: IvaCompensationHistoryRepository | None = None,
    captured_at: datetime | None = None,
    activity_start_date: date | None = None,
    excluded_binding_ids: frozenset[BindingId] | None = None,
) -> BindingPrefillReport:
    """Resolve every ``previous_filing`` binding the revision declares against observations in the local store.

    The caller provides a :class:`RegistrySnapshot`; this function asks the
    registry for
    :class:`~domain.calculations.registry.RegistryFoldRequirement` records,
    loads matching :class:`RegistryModeloObservation` rows, then delegates the
    final value calculation to
    :func:`~domain.calculations.registry.resolve_previous_filing_binding_values`.

    Args:
        snapshot: The :class:`RegistrySnapshot` whose revision's ``previous_filing``
            bindings are resolved from the local calculation observation store.
        repository: Optional :class:`CalculationObservationRepository`;
            defaults to the active-bucket repository when ``None``.
        iva_history_repository: Optional
            :class:`IvaCompensationHistoryRepository` consulted for the IVA
            compensation prior-balance bindings; defaults to the
            active-bucket repository when ``None``.
        captured_at: Optional capture timestamp recorded on the produced
            prefill records; defaults to the canonical clock when ``None``.
        activity_start_date: Optional operator-declared activity start. Source
            periods strictly before this date are no-prior-obligation periods
            and resolve to a neutral zero instead of requiring observed filings.
        excluded_binding_ids: Optional previous-filing binding ids to leave
            unresolved because another authority owns them.

    Returns a :class:`BindingPrefillReport` carrying the resolved
    ``binding_values`` mapping (suitable for passing through
    ``calculate_registry_snapshot``'s ``binding_values=`` argument) plus
    a tuple of ``PrefilledBinding`` records with provenance per entry.

    Bindings the local store cannot satisfy are skipped silently —
    the engine emits blank cells the operator fills by hand. Strict
    enforcement (refusing the export when prior filings are missing)
    is the caller's choice via the prefill report's coverage.

    See Also:
        :class:`~._multi_year.PreviousFilingSourceResolver` adapts this report
        to :class:`~application.aggregation.CalculationSourceResolution`;
        :func:`~._relation_prefill.resolve_relations_from_local_store` resolves
        the separate ``relation_prefill`` source family over the same
        observation repository.
    """
    repo = repository if repository is not None else CalculationObservationRepository()
    # The Modelo 303 IVA-compensation-history merge is NO LONGER an implicit
    # default: the live calculate path's compensación value is owned exclusively
    # by the iva-wallet decision (ruling D3), so the previous_filing gather stays
    # pure (registry observations only). Only the explicit wallet-feeding path
    # (extract_modelo_303_local_iva_compensation_recurrence) passes the history
    # repository to reconstruct the local recurrence the reconciliation consumes.
    when = captured_at if captured_at is not None else now()
    observations = _gather_observations(
        snapshot,
        repository=repo,
        iva_history_repository=iva_history_repository,
        excluded_binding_ids=excluded_binding_ids,
    )

    if not observations and activity_start_date is None:
        # The most consequential path, and the one that used to return in silence:
        # nothing is in the store, so every declared carry is unsatisfied.
        return BindingPrefillReport(
            prefilled=(),
            binding_values={},
            unsatisfied=_unsatisfied_previous_filing_bindings(
                snapshot,
                resolved_binding_ids=frozenset(),
                excluded_binding_ids=excluded_binding_ids,
            ),
        )

    resolved_map = resolve_previous_filing_binding_values(
        snapshot.revision,
        tuple(item.observation for item in observations),
        filing_year=snapshot.filing_year,
        period=snapshot.period,
        activity_start_date=activity_start_date,
        excluded_binding_ids=excluded_binding_ids,
    )

    return BindingPrefillReport(
        prefilled=_prefilled_bindings(
            snapshot,
            resolved_map,
            observations=observations,
            activity_start_date=activity_start_date,
            resolved_at=when,
        ),
        binding_values=dict(resolved_map),
        unsatisfied=_unsatisfied_previous_filing_bindings(
            snapshot,
            resolved_binding_ids=frozenset(resolved_map),
            excluded_binding_ids=excluded_binding_ids,
        ),
    )


def extract_modelo_303_local_iva_compensation_recurrence(
    snapshot: RegistrySnapshot,
    *,
    repository: CalculationObservationRepository | None = None,
    iva_history_repository: IvaCompensationHistoryRepository | None = None,
    captured_at: datetime | None = None,
) -> tuple[LocalIvaCompensationRecurrence | None, BindingPrefillReport]:
    """Extract the local Modelo 303 compensation recurrence for comparison.

    This is the explicit wallet-feeding path over
    :class:`IvaCompensationHistoryRepository`: it reconstructs the local
    previous-filing amount so
    :func:`~._iva_wallet_reconciliation.reconcile_modelo_303_iva_compensation`
    can compare it with current AEAT wallet evidence.

    Args:
        snapshot: The :class:`RegistrySnapshot` identifying the Modelo 303 target revision.
        repository: Optional :class:`CalculationObservationRepository`;
            defaults to the active-bucket repository when ``None``.
        iva_history_repository: Optional
            :class:`IvaCompensationHistoryRepository` consulted for prior
            compensation balances; defaults to the active-bucket repository
            when ``None``.
        captured_at: Optional capture timestamp recorded on the produced
            prefill records; defaults to the canonical clock when ``None``.

    The returned amount is the locally reconstructed prior compensation balance
    for the target Modelo 303 period. Callers must feed it into
    reconciliation; they must not use it directly as the effective value while
    fresh AEAT wallet evidence exists.

    Returns a 2-tuple of a :class:`LocalIvaCompensationRecurrence` (or
    ``None`` when no compensation binding is present) and the underlying
    :class:`BindingPrefillReport`.
    """
    if str(getattr(snapshot.modelo, "id", snapshot.modelo)) != Modelo.M303.value:
        from ..modelo._action_errors import ModeloApplicabilityFilterError

        raise ModeloApplicabilityFilterError(
            translated_message="application.calculations.iva_compensation.errors.local_recurrence_modelo_303_only",
            context={"modelo": str(getattr(snapshot.modelo, "id", snapshot.modelo))},
        )
    # This is the explicit wallet-feeding path: reconstruct the local Modelo 303
    # compensation recurrence from the secure IVA-compensation history so the
    # iva-wallet reconciliation can compare it against live wallet evidence. The
    # history repository is defaulted to the active bucket here (no longer
    # implicitly inside resolve_bindings_from_local_store) so the generic
    # previous_filing gather stays pure for every other caller.
    iva_repo = iva_history_repository if iva_history_repository is not None else IvaCompensationHistoryRepository()
    report = resolve_bindings_from_local_store(
        snapshot,
        repository=repository,
        iva_history_repository=iva_repo,
        captured_at=captured_at,
    )
    amount = report.binding_values.get(MODELO_303_IVA_COMPENSATION_BINDING_ID)
    if amount is None:
        return None, report
    prefilled = next(
        (item for item in report.prefilled if item.binding_id == MODELO_303_IVA_COMPENSATION_BINDING_ID),
        None,
    )
    if prefilled is None:
        source_modelo, source_year, source_periods, _dependency_treatment = _requirements_by_binding(snapshot)[
            MODELO_303_IVA_COMPENSATION_BINDING_ID
        ]
        resolved_at = captured_at if captured_at is not None else now()
        prefilled = PrefilledBinding(
            binding_id=MODELO_303_IVA_COMPENSATION_BINDING_ID,
            value=Decimal(amount),
            source_modelo=source_modelo,
            source_filing_year=source_year,
            source_periods=source_periods,
            resolved_at=resolved_at,
        )
    return (
        LocalIvaCompensationRecurrence(
            binding_id=prefilled.binding_id,
            amount=Decimal(amount),
            source_kind=prefilled.source_kind,
            source_modelo=prefilled.source_modelo,
            source_filing_year=prefilled.source_filing_year,
            source_periods=tuple(
                Period.from_year_and_code(prefilled.source_filing_year, period) for period in prefilled.source_periods
            ),
            resolved_at=prefilled.resolved_at,
        ),
        report,
    )


__all__ = [
    "BindingPrefillReport",
    "LocalIvaCompensationRecurrence",
    "PrefilledBinding",
    "extract_modelo_303_local_iva_compensation_recurrence",
    "resolve_bindings_from_local_store",
]
