"""Calendar completeness and evidence-warning helpers.

These helpers inspect already-built :class:`OverviewCalendarEntry` and
:class:`OverviewCalendarEvent` DTOs to derive :class:`CalendarWarning`
and :class:`CalendarCompleteness` payloads. They do not read remote state;
warnings about censo provenance, missing justificante verification, and
conflicting AEAT evidence only describe gaps in the local projection.

:func:`application.overview.calendar.build_overview_calendar` appends these warnings
after legal deadline rows and additive events have already been projected. Each
warning names the catalogue action that answers it - profile edit, filed-history
pull, or modelo description - rather than a command string; this module never
starts those operations.

See Also:
    :mod:`~application.overview.next_actions`
        Owns the shared declaration helper these remedies are built with.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable, Mapping
from threading import RLock
from types import MappingProxyType
from typing import TYPE_CHECKING

from ...core.modelo import Modelo as _Modelo
from ...core.period import Period as _Period
from ...domain.calculations.registry.applicability import (
    iter_modelo_applicability_rules as _iter_modelo_applicability_rules,
)
from ...domain.calculations.registry.applicability import (
    modelo_requires_iva_regime as _modelo_requires_iva_regime,
)
from ...domain.calculations.registry.applicability_payer_facts import payer_fact_profile_keys
from ...domain.calculations.registry.irpf_regimes import irpf_estimation_regime_objetiva_token
from ...domain.calculations.registry.iva_schema_vocabulary import iva_regime_simplificado_token
from ...domain.deadlines.models import IVARegime as _IVARegime
from ..operator_actions.models import DeclaredNextAction
from .calendar_models import (
    CalendarCompleteness,
    CalendarWarning,
    OverviewAeatSubmissionState,
    OverviewCalendarEntry,
    OverviewCalendarEvent,
    OverviewCalendarEventType,
    OverviewCensoEnrolmentState,
)
from .next_actions import declare_next_action

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.schema import ModeloRevision
    from ...domain.calculations.registry.schema_deadlines import DeadlineWindowDefinition

#: Every profile-fact gap this module reports is answered by one surface, so the
#: warnings name that surface's catalogue action rather than nine copies of a
#: command string.
_PROFILE_EDIT_ACTION_ID = "operator.profile.edit"

_PROFILE_FIELD_WARNING_META: MappingProxyType[str, tuple[str, str]] = MappingProxyType(
    {
        "has_employees": ("cli.overview.warning.has_employees_unset", _PROFILE_EDIT_ACTION_ID),
        "pays_professionals_with_retencion": (
            "cli.overview.warning.retencion_profesionales_unset",
            _PROFILE_EDIT_ACTION_ID,
        ),
        "art109_activity_income_withholding_ge_70pct": (
            "cli.overview.warning.art109_activity_income_withholding_ge_70pct_unset",
            _PROFILE_EDIT_ACTION_ID,
        ),
        "pays_rent_with_retencion": (
            "cli.overview.warning.retencion_arrendamientos_unset",
            _PROFILE_EDIT_ACTION_ID,
        ),
        "pays_capital_income_with_retencion": (
            "cli.overview.warning.retencion_capital_unset",
            _PROFILE_EDIT_ACTION_ID,
        ),
        "does_intracomunitario": ("cli.overview.warning.intracomunitario_unset", _PROFILE_EDIT_ACTION_ID),
        "third_party_transactions_above_347_threshold": (
            "cli.overview.warning.terceros_threshold_unset",
            _PROFILE_EDIT_ACTION_ID,
        ),
        "irpf.estimation_regime": ("cli.overview.warning.estimacion_objetiva_unset", _PROFILE_EDIT_ACTION_ID),
        "iva.regime": ("cli.overview.warning.iva_regime_unset", _PROFILE_EDIT_ACTION_ID),
    },
)


def _estimation_regime_profile_key(operation: PinnedAuthorityOperation) -> Mapping[str, tuple[str, str]]:
    """Return the objective-estimation profile mapping from the pinned authority."""
    return {
        irpf_estimation_regime_objetiva_token(authority=operation): (
            "irpf.estimation_regime",
            "cli.overview.warning.estimacion_objetiva_unset",
        ),
    }


_CORPORATE_CENSO_ENROLMENT_PROFILE_KEYS: MappingProxyType[str, frozenset[str]] = MappingProxyType(
    {
        _Modelo("200").value: frozenset(
            {
                "taxpayer_type.legal_entity_form",
            },
        ),
        _Modelo("202").value: frozenset(
            {
                "taxpayer_type.legal_entity_form",
                "taxpayer_type.incn_prior_12_months",
                "taxpayer_type.new_entity_first_two_profit_periods",
            },
        ),
    },
)


def _record_gating_field(
    *,
    profile_key: str,
    modelo: str,
    key_to_modelos: dict[str, set[str]],
    key_to_meta: dict[str, tuple[str, str]],
) -> None:
    meta = _PROFILE_FIELD_WARNING_META.get(profile_key)
    if meta is None:
        return
    key_to_modelos.setdefault(profile_key, set()).add(modelo)
    key_to_meta[profile_key] = meta


def _collect_deadline_window_profile_keys(
    windows_by_modelo: Iterable[tuple[str, Iterable[DeadlineWindowDefinition]]],
) -> MappingProxyType[str, tuple[str, ...]]:
    keys_by_modelo: dict[str, set[str]] = {}
    for modelo, windows in windows_by_modelo:
        for window in windows:
            for condition in window.applicability_conditions:
                if condition.field in _PROFILE_FIELD_WARNING_META:
                    keys_by_modelo.setdefault(modelo, set()).add(condition.field)
    return MappingProxyType({modelo: tuple(sorted(keys)) for modelo, keys in sorted(keys_by_modelo.items())})


def _deadline_window_profile_keys_by_modelo(
    *,
    operation: PinnedAuthorityOperation,
    revision_inventory: Iterable[tuple[str, ModeloRevision]] | None = None,
    modelo: str | None = None,
) -> MappingProxyType[str, tuple[str, ...]]:
    """Return deadline condition keys from an explicit inventory or the modelo directory.

    A pinned operation answers one modelo from its compact directory, whose
    selection metadata carries every revision's deadline windows with their
    applicability conditions, so no revision is hydrated. Whole-registry
    callers may provide an explicit revision inventory, but still supply the
    operation owned by the surrounding workflow.
    """
    if revision_inventory is not None:
        return _collect_deadline_window_profile_keys(
            (inventory_modelo, revision.deadline_windows) for inventory_modelo, revision in revision_inventory
        )
    if modelo is None:
        raise ValueError("calendar deadline metadata requires modelo or an explicit revision inventory")
    return _collect_deadline_window_profile_keys(_operation_deadline_windows(operation, (modelo,)))


def _operation_deadline_windows(
    operation: PinnedAuthorityOperation,
    modelos: Iterable[str],
) -> Iterable[tuple[str, tuple[DeadlineWindowDefinition, ...]]]:
    """Enumerate each revision's deadline windows from the directory metadata alone."""
    for modelo in modelos:
        for metadata in operation.modelo_directory(modelo).revisions:
            yield modelo, metadata.deadline_windows


_GATING_FIELDS_CACHE_SIZE = 4
_registry_gating_fields_cache: OrderedDict[object, MappingProxyType[str, tuple[tuple[str, ...], str, str]]] = (
    OrderedDict()
)
_registry_gating_fields_cache_lock = RLock()


def _gating_fields(
    *,
    operation: PinnedAuthorityOperation,
    revision_inventory: Iterable[tuple[str, ModeloRevision]] | None = None,
    modelos: Iterable[str] | None = None,
) -> MappingProxyType[str, tuple[tuple[str, ...], str, str]]:
    """Return every profile key that gates an obligation, with its modelos and warning metadata.

    The whole-registry answer depends only on the authority generation, yet
    deriving it decodes every revision; it is reused per generation pin so one
    workbench generation, which builds several calendars, pays for it once.
    """
    if revision_inventory is not None or modelos is not None:
        return _derive_gating_fields(operation=operation, revision_inventory=revision_inventory, modelos=modelos)
    key = operation.pin()
    with _registry_gating_fields_cache_lock:
        cached = _registry_gating_fields_cache.get(key)
        if cached is not None:
            _registry_gating_fields_cache.move_to_end(key)
            return cached
    derived = _derive_gating_fields(operation=operation)
    with _registry_gating_fields_cache_lock:
        _registry_gating_fields_cache[key] = derived
        _registry_gating_fields_cache.move_to_end(key)
        while len(_registry_gating_fields_cache) > _GATING_FIELDS_CACHE_SIZE:
            _registry_gating_fields_cache.popitem(last=False)
    return derived


def _derive_gating_fields(
    *,
    operation: PinnedAuthorityOperation,
    revision_inventory: Iterable[tuple[str, ModeloRevision]] | None = None,
    modelos: Iterable[str] | None = None,
) -> MappingProxyType[str, tuple[tuple[str, ...], str, str]]:
    windows_by_modelo: Iterable[tuple[str, Iterable[DeadlineWindowDefinition]]]
    if revision_inventory is None:
        windows_by_modelo = _operation_deadline_windows(
            operation,
            operation.modelo_ids() if modelos is None else modelos,
        )
    else:
        windows_by_modelo = ((modelo, revision.deadline_windows) for modelo, revision in revision_inventory)
    key_to_modelos: dict[str, set[str]] = {}
    key_to_meta: dict[str, tuple[str, str]] = {}

    for rule in _iter_modelo_applicability_rules():
        if rule.required_payer_fact is not None:
            for profile_key in payer_fact_profile_keys(rule.required_payer_fact):
                _record_gating_field(
                    profile_key=profile_key,
                    modelo=rule.modelo,
                    key_to_modelos=key_to_modelos,
                    key_to_meta=key_to_meta,
                )

        if len(rule.required_estimation_regimes) == 1:
            (regime,) = rule.required_estimation_regimes
            estimation_profile_keys = _estimation_regime_profile_key(operation)
            if regime in estimation_profile_keys:
                profile_key, _locale_key = estimation_profile_keys[regime]
                _record_gating_field(
                    profile_key=profile_key,
                    modelo=rule.modelo,
                    key_to_modelos=key_to_modelos,
                    key_to_meta=key_to_meta,
                )
        if rule.applicable_iva_regimes:
            _record_gating_field(
                profile_key="iva.regime",
                modelo=rule.modelo,
                key_to_modelos=key_to_modelos,
                key_to_meta=key_to_meta,
            )

    deadline_keys = _collect_deadline_window_profile_keys(windows_by_modelo)
    for modelo, profile_keys in deadline_keys.items():
        for profile_key in profile_keys:
            _record_gating_field(
                profile_key=profile_key,
                modelo=modelo,
                key_to_modelos=key_to_modelos,
                key_to_meta=key_to_meta,
            )

    return MappingProxyType(
        {
            profile_key: (
                tuple(sorted(key_to_modelos[profile_key])),
                key_to_meta[profile_key][0],
                key_to_meta[profile_key][1],
            )
            for profile_key in sorted(key_to_modelos)
        },
    )


_CENSO_ENROLMENT_PROFILE_KEYS = frozenset(
    {
        "activities.iae_epigraph",
        "taxpayer_type.entity_type",
        "taxpayer_type.irpf_income_categories",
        "taxpayer_type.legal_entity_form",
        "taxpayer_type.incn_prior_12_months",
        "taxpayer_type.new_entity_first_two_profit_periods",
        "iva.regime",
    },
)

_CENSO_ENROLMENT_WARNING_CODE = "censo.enrolment_unverified"
_CENSO_ENROLMENT_WARNING_MESSAGE = "cli.overview.warning.censo_enrolment_unverified"
_CENSO_ENROLMENT_ACTION_ID = "operator.profile.edit"
_JUSTIFICANTE_UNVERIFIED_WARNING_CODE = "filing.justificante_unverified"
_JUSTIFICANTE_UNVERIFIED_WARNING_MESSAGE = "cli.overview.warning.justificante_unverified"
_FILED_PULL_ACTION_ID = "operator.live.filed.pull"
_AEAT_EVIDENCE_CONFLICT_WARNING_CODE = "filing.aeat_evidence_conflict"
_AEAT_EVIDENCE_CONFLICT_WARNING_MESSAGE = "cli.overview.warning.aeat_evidence_conflict"
_M303_SIMPLIFICADO_FORFAIT_WARNING_CODE = "iva.regime.m303_simplificado_forfait_unavailable"
_M303_SIMPLIFICADO_FORFAIT_WARNING_LOCALE_KEY = "cli.overview.warning.m303_simplificado_forfait_unavailable"
_M303_SIMPLIFICADO_FORFAIT_ACTION_ID = "operator.modelo.describe"


def calendar_applicability_profile_keys_for_modelo(
    modelo: str,
    *,
    operation: PinnedAuthorityOperation,
    revision_inventory: Iterable[tuple[str, ModeloRevision]] | None = None,
) -> tuple[str, ...]:
    """Return profile keys that can influence calendar applicability for ``modelo``.

    The result combines registry applicability rules, IVA-regime coverage, and
    corporate censo axes so calendar provenance warnings use the same profile
    facts that determine legal obligation rows.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
    """
    keys: set[str] = set()
    estimation_profile_keys = _estimation_regime_profile_key(operation)
    for rule in _iter_modelo_applicability_rules():
        if rule.modelo != modelo:
            continue
        keys.add("taxpayer_type.entity_type")
        if rule.required_income_categories:
            keys.add("taxpayer_type.irpf_income_categories")
        if len(rule.required_estimation_regimes) == 1:
            (regime,) = rule.required_estimation_regimes
            if regime in estimation_profile_keys:
                keys.add(estimation_profile_keys[regime][0])
        if rule.required_payer_fact is not None:
            keys.update(payer_fact_profile_keys(rule.required_payer_fact))
        break
    keys.update(
        _deadline_window_profile_keys_by_modelo(
            operation=operation,
            revision_inventory=revision_inventory,
            modelo=modelo,
        ).get(modelo, ()),
    )
    if _modelo_requires_iva_regime(modelo):
        keys.add("iva.regime")
    keys.update(_CORPORATE_CENSO_ENROLMENT_PROFILE_KEYS.get(modelo, frozenset()))
    return tuple(sorted(keys))


def _calendar_censo_reconciliation_warnings(
    *,
    entries: tuple[OverviewCalendarEntry, ...],
    live_censo_verified_profile_keys: tuple[str, ...] | None,
) -> tuple[CalendarWarning, ...]:
    """Return censo-enrolment warnings for unverified active obligations."""
    if live_censo_verified_profile_keys is None or not entries:
        return ()
    affected_modelos: set[str] = set()
    for entry in entries:
        if entry.censo_enrolment_state is OverviewCensoEnrolmentState.UNVERIFIED:
            affected_modelos.add(entry.modelo)
    if not affected_modelos:
        return ()
    return (
        CalendarWarning(
            code=_CENSO_ENROLMENT_WARNING_CODE,
            message=_CENSO_ENROLMENT_WARNING_MESSAGE,
            fix_action=declare_next_action(_CENSO_ENROLMENT_ACTION_ID),
            affected_modelos=tuple(sorted(affected_modelos)),
        ),
    )


def _calendar_censo_enrolment_state(
    *,
    modelo: str,
    live_censo_verified_profile_keys: tuple[str, ...] | None,
    operation: PinnedAuthorityOperation,
    revision_inventory: Iterable[tuple[str, ModeloRevision]] | None = None,
) -> OverviewCensoEnrolmentState:
    """Classify whether censo-stamped profile paths witness ``modelo`` enrolment."""
    if live_censo_verified_profile_keys is None:
        return OverviewCensoEnrolmentState.NOT_CHECKED
    required = (
        set(
            calendar_applicability_profile_keys_for_modelo(
                modelo,
                operation=operation,
                revision_inventory=revision_inventory,
            ),
        )
        & _CENSO_ENROLMENT_PROFILE_KEYS
    )
    if "taxpayer_type.irpf_income_categories" in required:
        required.add("activities.iae_epigraph")
    if not required:
        return OverviewCensoEnrolmentState.NOT_REQUIRED
    verified = {key.strip() for key in live_censo_verified_profile_keys if key.strip()}
    if required <= verified:
        return OverviewCensoEnrolmentState.VERIFIED
    return OverviewCensoEnrolmentState.UNVERIFIED


def _calendar_unverified_justificante_warnings(
    *,
    entries: tuple[OverviewCalendarEntry, ...],
    events: tuple[OverviewCalendarEvent, ...],
) -> tuple[CalendarWarning, ...]:
    """Return warnings for AEAT-observed filings lacking justificante proof.

    Both entry-level ``OverviewCalendarEntry.filing_evidence`` rows and filing
    :class:`OverviewCalendarEvent` rows are scanned. Scope-specific remediation
    is used only when all affected rows collapse to one filed-history pull.
    """
    affected_modelos: set[str] = set()
    fix_actions: list[DeclaredNextAction] = []
    unresolved_states = {
        OverviewAeatSubmissionState.SUBMITTED_OBSERVED,
        OverviewAeatSubmissionState.ACCEPTED,
    }
    for entry in entries:
        evidence = entry.filing_evidence
        if evidence.aeat_submission_state in unresolved_states and not evidence.justificante_verified:
            affected_modelos.add(entry.modelo)
            fix_actions.append(
                _filed_pull_action(
                    modelo=entry.modelo,
                    filing_year=entry.filing_year,
                    period=entry.period,
                ),
            )
    for event in events:
        if event.event_type is not OverviewCalendarEventType.FILING or event.modelo is None:
            continue
        if event.aeat_submission_state in unresolved_states and event.justificante_verified is not True:
            affected_modelos.add(event.modelo)
            fix_actions.append(
                _filed_pull_action(
                    modelo=event.modelo,
                    filing_year=event.filing_year,
                    period=event.period,
                ),
            )
    if not affected_modelos:
        return ()
    return (
        CalendarWarning(
            code=_JUSTIFICANTE_UNVERIFIED_WARNING_CODE,
            message=_JUSTIFICANTE_UNVERIFIED_WARNING_MESSAGE,
            fix_action=_single_fix_action_or_unscoped_pull(fix_actions),
            affected_modelos=tuple(sorted(affected_modelos)),
        ),
    )


def _calendar_aeat_evidence_conflict_warnings(
    *,
    entries: tuple[OverviewCalendarEntry, ...],
) -> tuple[CalendarWarning, ...]:
    """Return warnings for conflicting AEAT references on calendar entries."""
    affected_modelos: set[str] = set()
    fix_actions: list[DeclaredNextAction] = []
    for entry in entries:
        if not entry.filing_evidence.aeat_evidence_conflict_reference_ids:
            continue
        affected_modelos.add(entry.modelo)
        fix_actions.append(
            _filed_pull_action(
                modelo=entry.modelo,
                filing_year=entry.filing_year,
                period=entry.period,
            ),
        )
    if not affected_modelos:
        return ()
    return (
        CalendarWarning(
            code=_AEAT_EVIDENCE_CONFLICT_WARNING_CODE,
            message=_AEAT_EVIDENCE_CONFLICT_WARNING_MESSAGE,
            fix_action=_single_fix_action_or_unscoped_pull(fix_actions),
            affected_modelos=tuple(sorted(affected_modelos)),
        ),
    )


def _calendar_regime_incompatibility_warnings(
    *,
    iva_regime: _IVARegime | None,
    entries: tuple[OverviewCalendarEntry, ...],
    operation: PinnedAuthorityOperation,
) -> tuple[CalendarWarning, ...]:
    """Return warnings where a surfaced modelo row lacks regime-specific calculation support."""
    if iva_regime != iva_regime_simplificado_token(authority=operation):
        return ()
    if not any(entry.modelo == _Modelo("303").value for entry in entries):
        return ()
    return (
        CalendarWarning(
            code=_M303_SIMPLIFICADO_FORFAIT_WARNING_CODE,
            message=_M303_SIMPLIFICADO_FORFAIT_WARNING_LOCALE_KEY,
            fix_action=declare_next_action(
                _M303_SIMPLIFICADO_FORFAIT_ACTION_ID,
                modelo=_Modelo("303").value,
            ),
            affected_modelos=(_Modelo("303").value,),
        ),
    )


def _filed_pull_action(
    *,
    modelo: str,
    filing_year: int | None,
    period: _Period | None,
) -> DeclaredNextAction:
    """Declare the filed-history pull, scoped when the row states its scope.

    A row that states no year or no period cannot narrow the pull, so the
    declaration keeps the modelo alone rather than inventing a scope.
    """
    if filing_year is None or period is None:
        return declare_next_action(_FILED_PULL_ACTION_ID, modelos=modelo)
    return declare_next_action(
        _FILED_PULL_ACTION_ID,
        modelos=modelo,
        year=filing_year,
        period=period.registry_token,
    )


def _single_fix_action_or_unscoped_pull(actions: list[DeclaredNextAction]) -> DeclaredNextAction:
    """Return the one shared remediation, otherwise the unscoped pull.

    Affected rows may name different scopes. Handing the operator one of them
    would silently drop the others, so a divergent set collapses to the
    unscoped pull, which reaches every affected row.
    """
    distinct = {action.model_dump_json(): action for action in actions}
    if len(distinct) == 1:
        return next(iter(distinct.values()))
    return declare_next_action(_FILED_PULL_ACTION_ID)


def _build_completeness_and_warnings(
    raw_values: Mapping[str, object] | None,
    entries: tuple[OverviewCalendarEntry, ...],
    *,
    operation: PinnedAuthorityOperation,
    revision_inventory: Iterable[tuple[str, ModeloRevision]] | None = None,
) -> tuple[CalendarCompleteness, tuple[CalendarWarning, ...]]:
    """Build explicit/defaulted profile completeness and related warnings.

    Missing profile values produce :class:`CalendarWarning` rows and populate
    ``CalendarCompleteness.defaulted_modelos`` only for modelos that also appear
    in the already-computed :class:`OverviewCalendarEntry` rows.
    """
    if raw_values is None:
        return CalendarCompleteness(), ()
    explicitly_set: list[str] = []
    defaulted: list[str] = []
    warnings: list[CalendarWarning] = []
    defaulted_modelos: set[str] = set()
    for key, (affected_modelos, message_key, action_id) in _gating_fields(
        operation=operation,
        revision_inventory=revision_inventory,
    ).items():
        raw = raw_values.get(key)
        if raw is not None and str(raw).strip():
            explicitly_set.append(key)
            continue
        defaulted.append(key)
        warnings.append(
            CalendarWarning(
                code=key,
                message=message_key,
                fix_action=declare_next_action(action_id),
                affected_modelos=affected_modelos,
            ),
        )
        defaulted_modelos.update(affected_modelos)
    computable_modelos = tuple(sorted({entry.modelo for entry in entries}))
    completeness = CalendarCompleteness(
        explicitly_set_keys=tuple(explicitly_set),
        defaulted_keys=tuple(defaulted),
        computable_modelos=computable_modelos,
        defaulted_modelos=tuple(sorted(defaulted_modelos & set(computable_modelos))),
    )
    return completeness, tuple(warnings)


__all__ = [
    "_build_completeness_and_warnings",
    "_calendar_aeat_evidence_conflict_warnings",
    "_calendar_censo_enrolment_state",
    "_calendar_censo_reconciliation_warnings",
    "_calendar_regime_incompatibility_warnings",
    "_calendar_unverified_justificante_warnings",
    "calendar_applicability_profile_keys_for_modelo",
]
