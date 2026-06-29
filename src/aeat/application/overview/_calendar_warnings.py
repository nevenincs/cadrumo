"""Calendar completeness and evidence-warning helpers.

These helpers inspect already-built :class:`OverviewCalendarEntry` and
:class:`OverviewCalendarEvent` DTOs to derive :class:`CalendarWarning`
and :class:`CalendarCompleteness` payloads. They do not read remote state;
warnings about censo provenance, missing justificante verification, and
conflicting AEAT evidence only describe gaps in the local projection.

:func:`aeat.application.overview.build_overview_calendar` appends these warnings
after legal deadline rows and additive events have already been projected. The
fix commands point operators at existing profile-edit, censo-read, or
filed-history pull surfaces; this module never starts those operations.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from ...core import Modelo as _Modelo
from ...core import Period as _Period
from ...core.external_constants import IVA_REGIME_MODELOS
from ...domain.calculations.registry.applicability import PayerFact as _PayerFact
from ...domain.calculations.registry.applicability import (
    iter_modelo_applicability_rules as _iter_modelo_applicability_rules,
)
from ...domain.deadlines.taxpayer_model import IrpfEstimationRegime as _IrpfEstimationRegime
from ._calendar_models import (
    CalendarCompleteness,
    CalendarWarning,
    OverviewAeatSubmissionState,
    OverviewCalendarEntry,
    OverviewCalendarEvent,
    OverviewCalendarEventType,
    OverviewCensoEnrolmentState,
)

_PAYER_FACT_PROFILE_KEY: dict[_PayerFact, tuple[str, str]] = {
    _PayerFact.PAYS_WITHHELD_INCOME: (
        "pays_professionals_with_retencion",
        "cli.overview.warning.retencion_profesionales_unset",
    ),
    _PayerFact.PAYS_RENT_WITH_RETENCION: (
        "pays_rent_with_retencion",
        "cli.overview.warning.retencion_arrendamientos_unset",
    ),
    _PayerFact.TRADES_INTRACOMMUNITY: (
        "does_intracomunitario",
        "cli.overview.warning.intracomunitario_unset",
    ),
    _PayerFact.EXCEEDS_THIRD_PARTY_THRESHOLD: (
        "third_party_transactions_above_347_threshold",
        "cli.overview.warning.terceros_threshold_unset",
    ),
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


def _gating_fields() -> MappingProxyType[str, tuple[tuple[str, ...], str, str]]:
    _fix = "aeat config profile edit"
    key_to_modelos: dict[str, set[str]] = {}
    key_to_meta: dict[str, tuple[str, str]] = {}

    for rule in _iter_modelo_applicability_rules():
        if rule.required_payer_fact is not None:
            payer_fact_meta = _PAYER_FACT_PROFILE_KEY.get(rule.required_payer_fact)
            if payer_fact_meta is not None:
                profile_key, locale_key = payer_fact_meta
                key_to_modelos.setdefault(profile_key, set()).add(rule.modelo)
                key_to_meta[profile_key] = (locale_key, _fix)

        if len(rule.required_estimation_regimes) == 1:
            (regime,) = rule.required_estimation_regimes
            if regime in _ESTIMATION_REGIME_PROFILE_KEY:
                profile_key, locale_key = _ESTIMATION_REGIME_PROFILE_KEY[regime]
                key_to_modelos.setdefault(profile_key, set()).add(rule.modelo)
                key_to_meta[profile_key] = (locale_key, _fix)

    key_to_modelos["iva.regime"] = set(_IVA_REGIME_MODELOS)
    key_to_meta["iva.regime"] = ("cli.overview.warning.iva_regime_unset", _fix)

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


_GATING_FIELDS: MappingProxyType[str, tuple[tuple[str, ...], str, str]] = _gating_fields()
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
_CENSO_ENROLMENT_FIX_COMMAND = "aeat config profile censo pull && aeat config profile censo apply"
_JUSTIFICANTE_UNVERIFIED_WARNING_CODE = "filing.justificante_unverified"
_JUSTIFICANTE_UNVERIFIED_WARNING_MESSAGE = "cli.overview.warning.justificante_unverified"
_JUSTIFICANTE_UNVERIFIED_FIX_COMMAND = "aeat app live filed pull --modelo MODELO --year YEAR --period PERIOD"
_AEAT_EVIDENCE_CONFLICT_WARNING_CODE = "filing.aeat_evidence_conflict"
_AEAT_EVIDENCE_CONFLICT_WARNING_MESSAGE = "cli.overview.warning.aeat_evidence_conflict"
_AEAT_EVIDENCE_CONFLICT_FIX_COMMAND = "aeat app live filed pull --modelo MODELO --year YEAR --period PERIOD"


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
            payer_fact_meta = _PAYER_FACT_PROFILE_KEY.get(rule.required_payer_fact)
            if payer_fact_meta is not None:
                keys.add(payer_fact_meta[0])
        break
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
            fix_command=_CENSO_ENROLMENT_FIX_COMMAND,
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
    :class:`OverviewCalendarEvent` rows are scanned. Period-specific
    remediation is used only when all affected rows collapse to one
    ``aeat app live filed pull`` command.
    """
    affected_modelos: set[str] = set()
    fix_commands: set[str] = set()
    unresolved_states = {
        OverviewAeatSubmissionState.SUBMITTED_OBSERVED,
        OverviewAeatSubmissionState.ACCEPTED,
    }
    for entry in entries:
        evidence = entry.filing_evidence
        if evidence.aeat_submission_state in unresolved_states and not evidence.justificante_verified:
            affected_modelos.add(entry.modelo)
            fix_commands.add(
                _filed_pull_command(
                    modelo=entry.modelo,
                    filing_year=entry.filing_year,
                    period=entry.period,
                    fallback=_JUSTIFICANTE_UNVERIFIED_FIX_COMMAND,
                ),
            )
    for event in events:
        if event.event_type is not OverviewCalendarEventType.FILING or event.modelo is None:
            continue
        if event.aeat_submission_state in unresolved_states and event.justificante_verified is not True:
            affected_modelos.add(event.modelo)
            fix_commands.add(
                _filed_pull_command(
                    modelo=event.modelo,
                    filing_year=event.filing_year,
                    period=event.period,
                    fallback=_JUSTIFICANTE_UNVERIFIED_FIX_COMMAND,
                ),
            )
    if not affected_modelos:
        return ()
    return (
        CalendarWarning(
            code=_JUSTIFICANTE_UNVERIFIED_WARNING_CODE,
            message=_JUSTIFICANTE_UNVERIFIED_WARNING_MESSAGE,
            fix_command=_single_fix_command_or_fallback(fix_commands, fallback=_JUSTIFICANTE_UNVERIFIED_FIX_COMMAND),
            affected_modelos=tuple(sorted(affected_modelos)),
        ),
    )


def _calendar_aeat_evidence_conflict_warnings(
    *,
    entries: tuple[OverviewCalendarEntry, ...],
) -> tuple[CalendarWarning, ...]:
    """Return warnings for conflicting AEAT references on calendar entries."""
    affected_modelos: set[str] = set()
    fix_commands: set[str] = set()
    for entry in entries:
        if not entry.filing_evidence.aeat_evidence_conflict_reference_ids:
            continue
        affected_modelos.add(entry.modelo)
        fix_commands.add(
            _filed_pull_command(
                modelo=entry.modelo,
                filing_year=entry.filing_year,
                period=entry.period,
                fallback=_AEAT_EVIDENCE_CONFLICT_FIX_COMMAND,
            ),
        )
    if not affected_modelos:
        return ()
    return (
        CalendarWarning(
            code=_AEAT_EVIDENCE_CONFLICT_WARNING_CODE,
            message=_AEAT_EVIDENCE_CONFLICT_WARNING_MESSAGE,
            fix_command=_single_fix_command_or_fallback(fix_commands, fallback=_AEAT_EVIDENCE_CONFLICT_FIX_COMMAND),
            affected_modelos=tuple(sorted(affected_modelos)),
        ),
    )


def _filed_pull_command(
    *,
    modelo: str,
    filing_year: int | None,
    period: _Period | None,
    fallback: str,
) -> str:
    """Return the period-specific filed-history pull command when possible."""
    if filing_year is None or period is None:
        return fallback
    return f"aeat app live filed pull --modelo {modelo} --year {filing_year} --period {period.registry_token}"


def _single_fix_command_or_fallback(commands: set[str], *, fallback: str) -> str:
    """Return one concrete remediation command, otherwise the generic fallback."""
    commands.discard(fallback)
    if len(commands) == 1:
        return next(iter(commands))
    return fallback


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
    for key, (affected_modelos, message_key, fix_command) in _GATING_FIELDS.items():
        raw = raw_values.get(key)
        if raw is not None and str(raw).strip():
            explicitly_set.append(key)
            continue
        defaulted.append(key)
        warnings.append(
            CalendarWarning(
                code=key,
                message=message_key,
                fix_command=fix_command,
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
    "_calendar_unverified_justificante_warnings",
    "calendar_applicability_profile_keys_for_modelo",
    "calendar_censo_enrolment_profile_keys",
]
