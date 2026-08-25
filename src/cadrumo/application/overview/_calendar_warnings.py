"""Calendar completeness and evidence-warning helpers.

These helpers inspect already-built :class:`OverviewCalendarEntry` and
:class:`OverviewCalendarEvent` DTOs to derive :class:`CalendarWarning`
and :class:`CalendarCompleteness` payloads. They do not read remote state;
warnings about censo provenance, missing justificante verification, and
conflicting AEAT evidence only describe gaps in the local projection.

:func:`application.overview.build_overview_calendar` appends these warnings
after legal deadline rows and additive events have already been projected. Each
warning names the catalogue action that answers it - profile edit, filed-history
pull, or modelo description - rather than a command string; this module never
starts those operations.

See Also:
    :mod:`~application.overview._next_actions`
        Owns the shared declaration helper these remedies are built with.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from types import MappingProxyType

from cadrumo.domain.calculations.registry.applicability_payer_facts import PayerFact as _PayerFact

from ...core import Modelo as _Modelo
from ...core import Period as _Period
from ...core.external_constants import IVA_REGIME_MODELOS
from ...domain.calculations.registry.applicability import (
    iter_modelo_applicability_rules as _iter_modelo_applicability_rules,
)
from ...domain.deadlines import IrpfEstimationRegime as _IrpfEstimationRegime
from ...domain.deadlines import IVARegime as _IVARegime
from ..operator_actions import DeclaredNextAction
from ._calendar_models import (
    CalendarCompleteness,
    CalendarWarning,
    OverviewAeatSubmissionState,
    OverviewCalendarEntry,
    OverviewCalendarEvent,
    OverviewCalendarEventType,
    OverviewCensoEnrolmentState,
)
from ._next_actions import declare_next_action

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

_PAYER_FACT_PROFILE_KEYS: dict[_PayerFact, tuple[str, ...]] = {
    _PayerFact.PAYS_WITHHELD_INCOME: (
        "has_employees",
        "pays_professionals_with_retencion",
    ),
    _PayerFact.PAYS_RENT_WITH_RETENCION: ("pays_rent_with_retencion",),
    _PayerFact.TRADES_INTRACOMMUNITY: ("does_intracomunitario",),
    _PayerFact.EXCEEDS_THIRD_PARTY_THRESHOLD: ("third_party_transactions_above_347_threshold",),
}

_ESTIMATION_REGIME_PROFILE_KEY: dict[_IrpfEstimationRegime, tuple[str, str]] = {
    _IrpfEstimationRegime.OBJETIVA: (
        "irpf.estimation_regime",
        "cli.overview.warning.estimacion_objetiva_unset",
    ),
}

_IVA_REGIME_MODELOS = IVA_REGIME_MODELOS
_CORPORATE_CENSO_ENROLMENT_PROFILE_KEYS: MappingProxyType[str, frozenset[str]] = MappingProxyType(
    {
        _Modelo.M200.value: frozenset(
            {
                "taxpayer_type.legal_entity_form",
            },
        ),
        _Modelo.M202.value: frozenset(
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


@lru_cache(maxsize=1)
def _deadline_window_profile_keys_by_modelo() -> MappingProxyType[str, tuple[str, ...]]:
    from ...core.resources import resources

    keys_by_modelo: dict[str, set[str]] = {}
    for modelo_definition in resources().modelos.all():
        modelo = str(modelo_definition.id)
        for revision in modelo_definition.revisions.values():
            for window in revision.deadline_windows:
                for condition in window.applicability_conditions:
                    if condition.field in _PROFILE_FIELD_WARNING_META:
                        keys_by_modelo.setdefault(modelo, set()).add(condition.field)
    return MappingProxyType({modelo: tuple(sorted(keys)) for modelo, keys in sorted(keys_by_modelo.items())})


@lru_cache(maxsize=1)
def _gating_fields() -> MappingProxyType[str, tuple[tuple[str, ...], str, str]]:
    key_to_modelos: dict[str, set[str]] = {}
    key_to_meta: dict[str, tuple[str, str]] = {}

    for rule in _iter_modelo_applicability_rules():
        if rule.required_payer_fact is not None:
            for profile_key in _PAYER_FACT_PROFILE_KEYS.get(rule.required_payer_fact, ()):
                _record_gating_field(
                    profile_key=profile_key,
                    modelo=rule.modelo,
                    key_to_modelos=key_to_modelos,
                    key_to_meta=key_to_meta,
                )

        if len(rule.required_estimation_regimes) == 1:
            (regime,) = rule.required_estimation_regimes
            if regime in _ESTIMATION_REGIME_PROFILE_KEY:
                profile_key, _locale_key = _ESTIMATION_REGIME_PROFILE_KEY[regime]
                _record_gating_field(
                    profile_key=profile_key,
                    modelo=rule.modelo,
                    key_to_modelos=key_to_modelos,
                    key_to_meta=key_to_meta,
                )

    for modelo, profile_keys in _deadline_window_profile_keys_by_modelo().items():
        for profile_key in profile_keys:
            _record_gating_field(
                profile_key=profile_key,
                modelo=modelo,
                key_to_modelos=key_to_modelos,
                key_to_meta=key_to_meta,
            )

    for modelo in _IVA_REGIME_MODELOS:
        _record_gating_field(
            profile_key="iva.regime",
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


def calendar_censo_enrolment_profile_keys() -> tuple[str, ...]:
    """Return profile paths whose censo provenance can witness enrolment.

    The paths are compared with live Modelo 036 / censo-stamped profile facts
    before :class:`OverviewCensoEnrolmentState` and
    :class:`CalendarWarning` values are produced.
    """
    return tuple(sorted(_CENSO_ENROLMENT_PROFILE_KEYS))


def calendar_applicability_profile_keys_for_modelo(modelo: str) -> tuple[str, ...]:
    """Return profile keys that can influence calendar applicability for ``modelo``.

    The result combines registry applicability rules, IVA-regime coverage, and
    corporate censo axes so calendar provenance warnings use the same profile
    facts that determine legal obligation rows.
    """
    keys: set[str] = set()
    for rule in _iter_modelo_applicability_rules():
        if rule.modelo != modelo:
            continue
        keys.add("taxpayer_type.entity_type")
        if rule.required_income_categories:
            keys.add("taxpayer_type.irpf_income_categories")
        if len(rule.required_estimation_regimes) == 1:
            (regime,) = rule.required_estimation_regimes
            if regime in _ESTIMATION_REGIME_PROFILE_KEY:
                keys.add(_ESTIMATION_REGIME_PROFILE_KEY[regime][0])
        if rule.required_payer_fact is not None:
            keys.update(_PAYER_FACT_PROFILE_KEYS.get(rule.required_payer_fact, ()))
        break
    keys.update(_deadline_window_profile_keys_by_modelo().get(modelo, ()))
    if modelo in _IVA_REGIME_MODELOS:
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
) -> OverviewCensoEnrolmentState:
    """Classify whether censo-stamped profile paths witness ``modelo`` enrolment."""
    if live_censo_verified_profile_keys is None:
        return OverviewCensoEnrolmentState.NOT_CHECKED
    required = set(calendar_applicability_profile_keys_for_modelo(modelo)) & _CENSO_ENROLMENT_PROFILE_KEYS
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
) -> tuple[CalendarWarning, ...]:
    """Return warnings where a surfaced modelo row lacks regime-specific calculation support."""
    if iva_regime is not _IVARegime.SIMPLIFICADO:
        return ()
    if not any(entry.modelo == _Modelo.M303.value for entry in entries):
        return ()
    return (
        CalendarWarning(
            code=_M303_SIMPLIFICADO_FORFAIT_WARNING_CODE,
            message=_M303_SIMPLIFICADO_FORFAIT_WARNING_LOCALE_KEY,
            fix_action=declare_next_action(
                _M303_SIMPLIFICADO_FORFAIT_ACTION_ID,
                modelo=_Modelo.M303.value,
            ),
            affected_modelos=(_Modelo.M303.value,),
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
    for key, (affected_modelos, message_key, action_id) in _gating_fields().items():
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
    "calendar_censo_enrolment_profile_keys",
]
