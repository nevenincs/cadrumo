"""Binding prefill: resolve `previous_filing` bindings from prior filings.

Used by: :mod:`~aeat.application.calculations._calculate` (model calculation orchestrator).

Sister module to `_relation_prefill`. The runtime distinguishes
`relation` leaves (cross-revision aggregations declared as
`RelationDefinition` records) from `previous_filing` bindings
(declared as `DataBindingDefinition` with `source = "previous_filing"`).
Modelo 390 uses bindings — modelo 200 uses relations — both express
"sum a prior modelo's casilla across periods" but route through
different schema entities.

Prior-filing values are gathered as :class:`CasillaObservation` records and
merged with casilla-level provenance before the binding is resolved.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Final

from pydantic import BaseModel, ConfigDict

from ...core import Modelo, Period
from ...core.resources import resources
from ...core.time import now
from ...domain.calculations.registry import (
    BindingId,
    CasillaObservation,
    RegistryModeloObservation,
    RegistrySnapshot,
    previous_filing_observation_requirements,
    resolve_previous_filing_binding_values,
)
from ...domain.iva_compensation._carry_forward import IvaCompensationPeriodState
from ._errors import BindingPrefillTypeError
from ._iva_compensation_history import IvaCompensationHistoryRepository
from ._observations_repository import CalculationObservationRepository, _ObservationEnvelopePayload


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
    raise BindingPrefillTypeError(f"binding selector 'filing_year_delta' must be int|str, got {type(value).__name__}")


def _selector_periods(value: object) -> tuple[str, ...]:
    """Normalise a binding-selector ``source_periods`` into a tuple of strings."""
    if isinstance(value, str):
        return (value,)
    if isinstance(value, tuple) and all(isinstance(item, str) for item in value):
        return tuple(str(item) for item in value)
    raise BindingPrefillTypeError(
        f"binding selector 'source_periods' must be str|tuple[str,...], got {type(value).__name__}",
    )


_LOCAL_FILING_PROVENANCE: Final = "local_filing"
_IVA_COMPENSATION_HISTORY_SOURCE_KIND: Final = "aeat_sede_iva_compensation_history"
_MIXED_OBSERVATION_SOURCE_KIND: Final = "mixed_observation_sources"
_MODELO_303_IVA_COMPENSATION_BINDING_ID: Final = "modelo-303-compensacion-pendiente-anteriores"

_STRICT_FROZEN: Final = ConfigDict(strict=True, frozen=True, extra="forbid")


def _revision_carry_outcome(payload: _ObservationEnvelopePayload) -> tuple[bool, bool]:
    """Return ``(diverges, advisory)`` for a payload's revision stamp.

    ADR 2026-06-10-period-revision-resolution-adr, Ruling 3 / R2:

    - Missing stamp (legacy record) → ``(False, True)``: carry proceeds, advisory set.
    - Indeterminate (source context fails to resolve) → ``(False, True)``: carry
      proceeds, but the stamp could not be re-confirmed so the advisory MUST be set
      rather than carrying silently clean.
    - Divergent stamp → ``(True, False)``: carry refused (caller drops the observation).
    - Matching stamp → ``(False, False)``: clean carry, no advisory.
    """
    if payload.stamped_revision_id is None:
        return False, True
    obs = payload.observation
    try:
        snapshot = resources().modelos.authority.snapshot(obs.modelo, filing_year=obs.filing_year, period=obs.period)
    except Exception:
        # Indeterminate: the source context will not resolve, so the stamp cannot be
        # re-confirmed. Surface the advisory rather than silently carrying a clean,
        # unverifiable stamp.
        return False, True
    return payload.stamped_revision_id != snapshot.revision.id, False


def _revision_prefill_divergence(payload: _ObservationEnvelopePayload) -> bool:
    """Return True when the payload's stamped revision diverges from the law-determined revision.

    See :func:`_revision_carry_outcome` — a divergent stamp means the prior was filed
    under a revision that is no longer the law-determined revision for its source
    context; the carry must be refused (the caller drops the observation).
    """
    return _revision_carry_outcome(payload)[0]


class _GatheredObservation(BaseModel):
    """Registry observation plus the persisted source channel that produced it."""

    model_config = _STRICT_FROZEN

    observation: RegistryModeloObservation
    source_kind: str
    casilla_source_kinds: Mapping[str, str]
    unstamped_revision_advisory: bool = False
    """Non-blocking advisory: source observation has no revision stamp (legacy record)."""


def _gathered_observation(
    observation: RegistryModeloObservation,
    *,
    source_kind: str,
    unstamped_revision_advisory: bool = False,
) -> _GatheredObservation:
    return _GatheredObservation(
        observation=observation,
        source_kind=source_kind,
        casilla_source_kinds={item.casilla_id: source_kind for item in observation.observations},
        unstamped_revision_advisory=unstamped_revision_advisory,
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
            "cannot merge previous_filing observations with different modelo/year/period keys",
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
    """One binding's resolved value with provenance for downstream stamping."""

    model_config = _STRICT_FROZEN

    binding_id: BindingId
    value: Decimal
    provenance: str = _LOCAL_FILING_PROVENANCE
    source_kind: str = _LOCAL_FILING_PROVENANCE
    source_modelo: str
    source_filing_year: int
    source_periods: tuple[str, ...]
    resolved_at: datetime
    unstamped_revision_advisory: bool = False
    """Non-blocking advisory: source observation has no revision stamp (legacy record).

    True when the carry proceeded from a legacy observation without a revision
    provenance stamp (ADR 2026-06-10-period-revision-resolution-adr, Ruling 3 / R2).
    Operators should re-file the source period to obtain a stamped record.
    """


class BindingPrefillReport(BaseModel):
    """Outcome of one binding-prefill pass."""

    model_config = _STRICT_FROZEN

    prefilled: tuple[PrefilledBinding, ...]
    binding_values: Mapping[str, Decimal]

    @property
    def has_unstamped_revision_advisory(self) -> bool:
        """True when any prefilled binding carries a legacy unstamped-revision advisory."""
        return any(item.unstamped_revision_advisory for item in self.prefilled)


class LocalIvaCompensationRecurrence(BaseModel):
    """Local Modelo 303 recurrence extracted for wallet reconciliation only.

    This is comparison evidence. It does not choose the effective casilla `110`
    value; the wallet reconciliation decision remains the only selector.
    """

    model_config = _STRICT_FROZEN

    binding_id: BindingId
    amount: Decimal
    source_kind: str = _LOCAL_FILING_PROVENANCE
    source_modelo: str
    source_filing_year: int
    source_periods: tuple[Period, ...]
    resolved_at: datetime


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
        # R2 carry gate: divergent stamp → skip; missing/indeterminate stamp → advisory.
        diverges, advisory = _revision_carry_outcome(payload)
        if diverges:
            continue
        member_idx = seen_member.get(req_key, 0)
        seen_member[req_key] = member_idx + 1
        needed[(obs.modelo, obs.filing_year, obs.period, member_idx)] = _gathered_observation(
            obs,
            source_kind=payload.source_kind,
            unstamped_revision_advisory=advisory,
        )


def _gathered_from_payload(payload: _ObservationEnvelopePayload | None) -> _GatheredObservation | None:
    """Apply the R2 carry gate to a single-key payload.

    Divergent stamp → refuse the carry (return ``None``); missing/indeterminate
    stamp → carry with the non-blocking advisory set.
    """
    if payload is None:
        return None
    diverges, advisory = _revision_carry_outcome(payload)
    if diverges:
        return None
    return _gathered_observation(
        payload.observation,
        source_kind=payload.source_kind,
        unstamped_revision_advisory=advisory,
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
    grouped_keys = _per_grupo_member_requirement_keys(snapshot.revision, snapshot)
    needed: dict[tuple[str, int, str, int], _GatheredObservation] = {}
    seen_member: dict[tuple[str, int, str], int] = {}
    for requirement in previous_filing_observation_requirements(
        snapshot.revision,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    ):
        req_key = (requirement.modelo, requirement.filing_year, requirement.period)
        if req_key in grouped_keys:
            _gather_grouped_member_observations(
                req_key,
                repository=repository,
                needed=needed,
                seen_member=seen_member,
            )
            continue
        gathered = _gather_single_key_observation(
            requirement.modelo,
            requirement.filing_year,
            requirement.period,
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


def _per_grupo_member_requirement_keys(revision: object, snapshot: RegistrySnapshot) -> set[tuple[str, int, str]]:
    """Return the (modelo, filing_year, period) requirement keys whose binding declares per_grupo_member.

    These keys must be gathered by enumeration (every member's filing), not by
    single-key load — the cross-member fan-in for the 353<-322 aggregation.
    """

    def _is_per_grupo_member(binding: object) -> bool:
        if getattr(binding, "source", None) != "previous_filing":
            return False
        selector = getattr(binding, "selector", None)
        if isinstance(selector, dict):
            return selector.get("grouping") == "per_grupo_member"
        return getattr(selector, "grouping", None) == "per_grupo_member"

    grouped_binding_ids = {binding.id for binding in snapshot.revision.bindings if _is_per_grupo_member(binding)}
    if not grouped_binding_ids:
        return set()
    keys: set[tuple[str, int, str]] = set()
    for requirement in previous_filing_observation_requirements(
        snapshot.revision,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    ):
        if any(bid in grouped_binding_ids for bid in requirement.binding_ids):
            keys.add((requirement.modelo, requirement.filing_year, requirement.period))
    return keys


def _observation_from_iva_compensation_history(
    state: IvaCompensationPeriodState,
) -> RegistryModeloObservation:
    """Project secure IVA compensation history into the registry resolver contract."""
    snapshot = resources().modelos.authority.snapshot(
        Modelo.M303.value,
        filing_year=state.filing_year,
        period=state.period.registry_token,
    )
    casillas = {item.id: item for item in snapshot.revision.casillas}
    formulas = {item.target: item for item in snapshot.revision.formulas}

    def observed(casilla_id: str, value: Decimal | None) -> tuple[CasillaObservation, ...]:
        if value is None:
            return ()
        casilla = casillas.get(casilla_id)
        formula = formulas.get(casilla_id)
        operand_refs: tuple[str, ...] = ()
        operand_values: tuple[Decimal, ...] = ()
        if casilla_id == "iva.compensacion-disponible-fin-periodo" and (
            state.pending_for_later_amount is not None and state.period_result_amount is not None
        ):
            operand_refs = ("87", "69")
            operand_values = (state.pending_for_later_amount, state.period_result_amount)
        return (
            CasillaObservation(
                casilla_id=casilla_id,
                value=value,
                formula_id=formula.id if formula is not None else None,
                operand_refs=operand_refs,
                operand_values=operand_values,
                legal_refs=tuple(casilla.legal_refs) if casilla is not None else (),
                source_refs=tuple(casilla.source_refs) if casilla is not None else (),
            ),
        )

    return RegistryModeloObservation(
        modelo=Modelo.M303.value,
        filing_year=state.filing_year,
        period=state.period.registry_token,
        observations=(
            *observed("110", state.prior_pending_amount),
            *observed("78", state.applied_amount),
            *observed("87", state.pending_for_later_amount),
            *observed("69", state.period_result_amount),
            *observed("71", state.final_result_amount),
            *observed("iva.compensacion-generada-periodo", state.generated_amount),
            *observed("iva.compensacion-disponible-fin-periodo", state.available_end_amount),
        ),
    )


def _requirements_by_binding(
    snapshot: RegistrySnapshot,
) -> dict[str, tuple[str, int, tuple[str, ...]]]:
    grouped: dict[str, tuple[str, int, set[str]]] = {}
    for requirement in previous_filing_observation_requirements(
        snapshot.revision,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    ):
        for binding_id in requirement.binding_ids:
            current = grouped.setdefault(binding_id, (requirement.modelo, requirement.filing_year, set()))
            current[2].add(requirement.period)
    return {
        binding_id: (source_modelo, source_year, tuple(sorted(periods)))
        for binding_id, (source_modelo, source_year, periods) in grouped.items()
    }


def _selector_source_casillas(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, tuple) and all(isinstance(item, str) for item in value):
        return tuple(str(item) for item in value)
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return tuple(str(item) for item in value)
    return ()


def _selector_value(selector: object, key: str, default: object) -> object:
    if isinstance(selector, dict):
        # items() yields (Unknown, object) pairs; filter by key to preserve None-valued entries.
        return next((v for k, v in selector.items() if k == key), default)
    return getattr(selector, key, default)


def _advisory_for_binding(
    gathered: tuple[_GatheredObservation, ...],
    *,
    source_modelo: str,
    source_filing_year: int,
    source_periods: tuple[str, ...],
) -> bool:
    """Return True when any gathered observation matching this binding's source carries the unstamped advisory.

    ADR 2026-06-10-period-revision-resolution-adr, Ruling 3 / R2:
    propagates the legacy-record non-blocking advisory from the source observation
    through to the :class:`PrefilledBinding` so callers can surface it to operators.
    """
    required_periods = set(source_periods)
    for item in gathered:
        if (
            item.observation.modelo == source_modelo
            and item.observation.filing_year == source_filing_year
            and item.observation.period in required_periods
            and item.unstamped_revision_advisory
        ):
            return True
    return False


def _source_kind_for_binding(
    gathered: tuple[_GatheredObservation, ...],
    *,
    source_modelo: str,
    source_filing_year: int,
    source_periods: tuple[str, ...],
    source_casillas: tuple[str, ...] = (),
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
        if source_casillas:
            matched_source_kinds.update(
                item.casilla_source_kinds.get(casilla_id, item.source_kind)
                for casilla_id in source_casillas
                if casilla_id in item.observation.casilla_values
            )
        else:
            matched_source_kinds.add(item.source_kind)
    if len(matched_source_kinds) == 1:
        return next(iter(matched_source_kinds))
    if matched_source_kinds:
        return _MIXED_OBSERVATION_SOURCE_KIND
    return _LOCAL_FILING_PROVENANCE


def resolve_bindings_from_local_store(
    snapshot: RegistrySnapshot,
    *,
    repository: CalculationObservationRepository | None = None,
    iva_history_repository: IvaCompensationHistoryRepository | None = None,
    captured_at: datetime | None = None,
) -> BindingPrefillReport:
    """Resolve every ``previous_filing`` binding the revision declares against observations in the local store.

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

    Returns a :class:`BindingPrefillReport` carrying the resolved
    ``binding_values`` mapping (suitable for passing through
    ``calculate_registry_snapshot``'s ``binding_values=`` argument) plus
    a tuple of ``PrefilledBinding`` records with provenance per entry.

    Bindings the local store cannot satisfy are skipped silently —
    the engine emits blank cells the operator fills by hand. Strict
    enforcement (refusing the export when prior filings are missing)
    is the caller's choice via the prefill report's coverage.
    """
    repo = repository if repository is not None else CalculationObservationRepository()
    iva_repo = iva_history_repository if iva_history_repository is not None else IvaCompensationHistoryRepository()
    when = captured_at if captured_at is not None else now()
    observations = _gather_observations(snapshot, repository=repo, iva_history_repository=iva_repo)

    if not observations:
        return BindingPrefillReport(prefilled=(), binding_values={})

    resolved_map = resolve_previous_filing_binding_values(
        snapshot.revision,
        tuple(item.observation for item in observations),
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    )

    prefilled: list[PrefilledBinding] = []
    binding_index = {binding.id: binding for binding in snapshot.revision.bindings}
    requirement_index = _requirements_by_binding(snapshot)
    for binding_id, value in resolved_map.items():
        binding = binding_index.get(binding_id)
        if binding is None:
            continue
        selector = binding.selector
        source_modelo, source_filing_year, source_periods = requirement_index.get(
            binding_id,
            (
                str(_selector_value(selector, "source_modelo", "") or ""),
                snapshot.filing_year + _selector_year_delta(_selector_value(selector, "filing_year_delta", 0)),
                _selector_periods(_selector_value(selector, "source_periods", ())),
            ),
        )
        source_casillas = _selector_source_casillas(_selector_value(selector, "source_casillas", ()))
        # Propagate the unstamped-revision advisory from the gathered source observation
        # for this binding's (modelo, filing_year, periods) to the prefilled record
        # (ADR 2026-06-10-period-revision-resolution-adr, Ruling 3 / R2).
        unstamped_advisory = _advisory_for_binding(
            observations,
            source_modelo=source_modelo,
            source_filing_year=source_filing_year,
            source_periods=source_periods,
        )
        prefilled.append(
            PrefilledBinding(
                binding_id=binding_id,
                value=Decimal(value),
                source_kind=_source_kind_for_binding(
                    observations,
                    source_modelo=source_modelo,
                    source_filing_year=source_filing_year,
                    source_periods=source_periods,
                    source_casillas=source_casillas,
                ),
                source_modelo=source_modelo,
                source_filing_year=source_filing_year,
                source_periods=source_periods,
                resolved_at=when,
                unstamped_revision_advisory=unstamped_advisory,
            ),
        )
    return BindingPrefillReport(
        prefilled=tuple(prefilled),
        binding_values=dict(resolved_map),
    )


def extract_modelo_303_local_iva_compensation_recurrence(
    snapshot: RegistrySnapshot,
    *,
    repository: CalculationObservationRepository | None = None,
    iva_history_repository: IvaCompensationHistoryRepository | None = None,
    captured_at: datetime | None = None,
) -> tuple[LocalIvaCompensationRecurrence | None, BindingPrefillReport]:
    """Extract the local Modelo 303 compensation recurrence for comparison.

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
        from ..modelo._actions import ModeloApplicabilityFilterError

        raise ModeloApplicabilityFilterError("local IVA compensation recurrence extraction only applies to Modelo 303")
    report = resolve_bindings_from_local_store(
        snapshot,
        repository=repository,
        iva_history_repository=iva_history_repository,
        captured_at=captured_at,
    )
    amount = report.binding_values.get(_MODELO_303_IVA_COMPENSATION_BINDING_ID)
    if amount is None:
        return None, report
    prefilled = next(
        (item for item in report.prefilled if item.binding_id == _MODELO_303_IVA_COMPENSATION_BINDING_ID),
        None,
    )
    if prefilled is None:
        source_modelo, source_year, source_periods = _requirements_by_binding(snapshot)[
            _MODELO_303_IVA_COMPENSATION_BINDING_ID
        ]
        resolved_at = captured_at if captured_at is not None else now()
        prefilled = PrefilledBinding(
            binding_id=_MODELO_303_IVA_COMPENSATION_BINDING_ID,
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
