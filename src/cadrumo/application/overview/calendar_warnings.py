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
from datetime import date
from threading import RLock
from types import MappingProxyType
from typing import TYPE_CHECKING

from ...core.modelo import Modelo
from ...core.period import Period
from ...domain.calculations.registry.applicability import (
    iter_modelo_applicability_rules,
    modelo_requires_iva_regime,
)
from ...domain.calculations.registry.applicability_models import ModeloApplicabilityRule
from ...domain.calculations.registry.applicability_payer_facts import payer_fact_profile_keys
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.calculations.registry.irpf_regimes import irpf_estimation_regime_objetiva_token
from ...domain.calculations.registry.iva_regime_vocabulary import iva_regime_simplificado_token
from ...domain.deadlines.models import IVARegime
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
    from ...domain.calculations.registry.schema_live_verification import ProfilePredicateDefinition
    from ...domain.user_profile.schema import ProfileSchemaDefinition

#: Every profile-fact gap this module reports is answered by one surface, so the
#: warnings name that surface's catalogue action rather than a copy of a
#: command string per field.
_PROFILE_EDIT_ACTION_ID = "operator.profile.edit"

#: The residency axis is not a payer fact: a rule names the residencies it
#: applies to, so the gating key is the profile's own residency selector.
_FISCAL_RESIDENCY_PROFILE_KEY = "taxpayer.fiscal_residency"

PROFILE_FIELD_WARNING_LOCALE_KEYS: MappingProxyType[str, str] = MappingProxyType(
    {
        "has_employees": "cli.overview.warning.has_employees_unset",
        "pays_professionals_with_retencion": "cli.overview.warning.retencion_profesionales_unset",
        "art109_activity_income_withholding_ge_70pct": (
            "cli.overview.warning.art109_activity_income_withholding_ge_70pct_unset"
        ),
        "pays_rent_with_retencion": "cli.overview.warning.retencion_arrendamientos_unset",
        "pays_capital_income_with_retencion": "cli.overview.warning.retencion_capital_unset",
        "pays_non_resident_income_with_retencion": "cli.overview.warning.retencion_no_residentes_unset",
        "does_intracomunitario": "cli.overview.warning.intracomunitario_unset",
        "third_party_transactions_above_347_threshold": "cli.overview.warning.terceros_threshold_unset",
        "bienes_extranjero_above_threshold": "cli.overview.warning.bienes_extranjero_unset",
        "monedas_virtuales_extranjero_above_threshold": "cli.overview.warning.monedas_virtuales_extranjero_unset",
        "patrimonio_declaration_threshold_met": "cli.overview.warning.patrimonio_umbral_unset",
        "premio_loteria_gravamen_especial_sin_retencion": "cli.overview.warning.premio_loteria_unset",
        "premio_loteria_gravamen_especial_trimestres": "cli.overview.warning.premio_loteria_trimestres_unset",
        "irpf.estimation_regime": "cli.overview.warning.estimacion_objetiva_unset",
        "iva.regime": "cli.overview.warning.iva_regime_unset",
        "iva.oss_enrolled": "cli.overview.warning.oss_unset",
        "iva.sii_enrolled": "cli.overview.warning.sii_unset",
        "iva.voluntary_sii_enrolled": "cli.overview.warning.sii_voluntario_unset",
        "iva.redeme_enrolled": "cli.overview.warning.redeme_unset",
        "iva.group_member_enrolled": "cli.overview.warning.grupo_entidades_dependiente_unset",
        "iva.group_dominant_entity_enrolled": "cli.overview.warning.grupo_entidades_dominante_unset",
        "iva.intracommunity_operations_exceed_50000_eur": "cli.overview.warning.intracomunitario_umbral_unset",
        "enrollment.large_company": "cli.overview.warning.gran_empresa_unset",
        "enrollment.public_administration_budget_gt_6000000": "cli.overview.warning.administracion_publica_unset",
        "taxpayer.entity_type": "cli.overview.warning.tipo_entidad_unset",
        _FISCAL_RESIDENCY_PROFILE_KEY: "cli.overview.warning.residencia_fiscal_unset",
    },
)
"""The named unset warning for every profile key that can gate an obligation.

Keyed by the selector token the registry names the fact under, which is what
:func:`_gating_field_raw_value` resolves against either projection shape. The
mapping must stay complete: a gating key with no entry is dropped silently by
:func:`_record_gating_field`, so the operator would be left with an obligation
the projection could not scope and no statement of which answer is missing.
``tests/test_calendar_payer_fact_warnings.py`` derives the reachable keys from
the registry and fails when one is unnamed.
"""


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
        Modelo("200").value: frozenset(
            {
                "taxpayer_type.legal_entity_form",
            },
        ),
        Modelo("202").value: frozenset(
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
    message_key = PROFILE_FIELD_WARNING_LOCALE_KEYS.get(profile_key)
    if message_key is None:
        return
    key_to_modelos.setdefault(profile_key, set()).add(modelo)
    key_to_meta[profile_key] = (message_key, _PROFILE_EDIT_ACTION_ID)


def _collect_condition_profile_keys(
    conditions_by_modelo: Iterable[tuple[str, Iterable[ProfilePredicateDefinition]]],
) -> MappingProxyType[str, tuple[str, ...]]:
    """Group the named profile keys a registry predicate tuple reads, by modelo."""
    keys_by_modelo: dict[str, set[str]] = {}
    for modelo, conditions in conditions_by_modelo:
        for condition in conditions:
            if condition.field in PROFILE_FIELD_WARNING_LOCALE_KEYS:
                keys_by_modelo.setdefault(modelo, set()).add(condition.field)
    return MappingProxyType({modelo: tuple(sorted(keys)) for modelo, keys in sorted(keys_by_modelo.items())})


def _collect_deadline_window_profile_keys(
    windows_by_modelo: Iterable[tuple[str, Iterable[DeadlineWindowDefinition]]],
) -> MappingProxyType[str, tuple[str, ...]]:
    return _collect_condition_profile_keys(
        (modelo, window.applicability_conditions) for modelo, windows in windows_by_modelo for window in windows
    )


def deadline_window_profile_keys_by_modelo(
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

    ``revision_inventory`` is a :class:`ModeloRevision`.
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


def _operation_filing_schedule_conditions(
    operation: PinnedAuthorityOperation,
    modelos: Iterable[str],
) -> Iterable[tuple[str, tuple[ProfilePredicateDefinition, ...]]]:
    """Enumerate each revision's filing-schedule predicates from the directory metadata alone.

    A filing schedule is the third way a profile fact decides what the
    operator is shown, beside an applicability rule and a deadline window:
    an unmatched schedule removes the modelo's windows for the period, so an
    unanswered schedule fact silently produces no obligation rather than a
    cadence. Its keys are reported as gaps for exactly that reason.
    """
    for modelo in modelos:
        for metadata in operation.modelo_directory(modelo).revisions:
            for schedule in metadata.filing_schedules:
                yield modelo, schedule.profile_conditions


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
        return derive_gating_fields(operation=operation, revision_inventory=revision_inventory, modelos=modelos)
    key = operation.pin()
    with _registry_gating_fields_cache_lock:
        cached = _registry_gating_fields_cache.get(key)
        if cached is not None:
            _registry_gating_fields_cache.move_to_end(key)
            return cached
    derived = derive_gating_fields(operation=operation)
    with _registry_gating_fields_cache_lock:
        _registry_gating_fields_cache[key] = derived
        _registry_gating_fields_cache.move_to_end(key)
        while len(_registry_gating_fields_cache) > _GATING_FIELDS_CACHE_SIZE:
            _registry_gating_fields_cache.popitem(last=False)
    return derived


def derive_gating_fields(
    *,
    operation: PinnedAuthorityOperation,
    revision_inventory: Iterable[tuple[str, ModeloRevision]] | None = None,
    modelos: Iterable[str] | None = None,
) -> MappingProxyType[str, tuple[tuple[str, ...], str, str]]:
    """Derive the gating fields keyed by applicability rules across the published modelos.

    ``revision_inventory`` is a :class:`ModeloRevision`.
    """
    key_to_modelos: dict[str, set[str]] = {}
    key_to_meta: dict[str, tuple[str, str]] = {}
    for rule in iter_modelo_applicability_rules(operation=operation):
        _record_applicability_gating_fields(
            rule=rule,
            operation=operation,
            key_to_modelos=key_to_modelos,
            key_to_meta=key_to_meta,
        )
    _record_deadline_gating_fields(
        operation=operation,
        revision_inventory=revision_inventory,
        modelos=modelos,
        key_to_modelos=key_to_modelos,
        key_to_meta=key_to_meta,
    )
    _record_filing_schedule_gating_fields(
        operation=operation,
        revision_inventory=revision_inventory,
        modelos=modelos,
        key_to_modelos=key_to_modelos,
        key_to_meta=key_to_meta,
    )
    return _freeze_gating_fields(key_to_modelos=key_to_modelos, key_to_meta=key_to_meta)


def _record_applicability_gating_fields(
    *,
    rule: ModeloApplicabilityRule,
    operation: PinnedAuthorityOperation,
    key_to_modelos: dict[str, set[str]],
    key_to_meta: dict[str, tuple[str, str]],
) -> None:
    for payer_fact in rule.gating_payer_facts:
        for profile_key in payer_fact_profile_keys(payer_fact):
            _record_gating_field(
                profile_key=profile_key,
                modelo=rule.modelo,
                key_to_modelos=key_to_modelos,
                key_to_meta=key_to_meta,
            )
    if len(rule.required_estimation_regimes) == 1:
        regime = next(iter(rule.required_estimation_regimes))
        estimation_profile_key = _estimation_regime_profile_key(operation).get(regime)
        if estimation_profile_key is not None:
            profile_key, _locale_key = estimation_profile_key
            _record_gating_field(
                profile_key=profile_key,
                modelo=rule.modelo,
                key_to_modelos=key_to_modelos,
                key_to_meta=key_to_meta,
            )
    if rule.applicable_fiscal_residencies:
        _record_gating_field(
            profile_key=_FISCAL_RESIDENCY_PROFILE_KEY,
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


def _record_deadline_gating_fields(
    *,
    operation: PinnedAuthorityOperation,
    revision_inventory: Iterable[tuple[str, ModeloRevision]] | None,
    modelos: Iterable[str] | None,
    key_to_modelos: dict[str, set[str]],
    key_to_meta: dict[str, tuple[str, str]],
) -> None:
    if revision_inventory is None:
        windows_by_modelo = _operation_deadline_windows(
            operation,
            operation.modelo_ids() if modelos is None else modelos,
        )
    else:
        windows_by_modelo = ((modelo, revision.deadline_windows) for modelo, revision in revision_inventory)
    deadline_keys = _collect_deadline_window_profile_keys(windows_by_modelo)
    for modelo, profile_keys in deadline_keys.items():
        for profile_key in profile_keys:
            _record_gating_field(
                profile_key=profile_key,
                modelo=modelo,
                key_to_modelos=key_to_modelos,
                key_to_meta=key_to_meta,
            )


def _record_filing_schedule_gating_fields(
    *,
    operation: PinnedAuthorityOperation,
    revision_inventory: Iterable[tuple[str, ModeloRevision]] | None,
    modelos: Iterable[str] | None,
    key_to_modelos: dict[str, set[str]],
    key_to_meta: dict[str, tuple[str, str]],
) -> None:
    if revision_inventory is None:
        conditions_by_modelo = _operation_filing_schedule_conditions(
            operation,
            operation.modelo_ids() if modelos is None else modelos,
        )
    else:
        conditions_by_modelo = (
            (modelo, schedule.profile_conditions)
            for modelo, revision in revision_inventory
            for schedule in revision.filing_schedules
        )
    for modelo, profile_keys in _collect_condition_profile_keys(conditions_by_modelo).items():
        for profile_key in profile_keys:
            _record_gating_field(
                profile_key=profile_key,
                modelo=modelo,
                key_to_modelos=key_to_modelos,
                key_to_meta=key_to_meta,
            )


def _freeze_gating_fields(
    *,
    key_to_modelos: dict[str, set[str]],
    key_to_meta: dict[str, tuple[str, str]],
) -> MappingProxyType[str, tuple[tuple[str, ...], str, str]]:
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
_CENSO_ENROLMENT_WARNING_LOCALE_KEY = "cli.overview.warning.censo_enrolment_unverified"
_CENSO_ENROLMENT_ACTION_ID = "operator.profile.edit"
_JUSTIFICANTE_UNVERIFIED_WARNING_CODE = "filing.justificante_unverified"
_JUSTIFICANTE_UNVERIFIED_WARNING_LOCALE_KEY = "cli.overview.warning.justificante_unverified"
_FILED_PULL_ACTION_ID = "operator.live.filed.pull"
_AEAT_EVIDENCE_CONFLICT_WARNING_CODE = "filing.aeat_evidence_conflict"
_AEAT_EVIDENCE_CONFLICT_WARNING_LOCALE_KEY = "cli.overview.warning.aeat_evidence_conflict"
_M303_SIMPLIFICADO_FORFAIT_WARNING_CODE = "iva.regime.m303_simplificado_forfait_unavailable"
_M303_SIMPLIFICADO_FORFAIT_WARNING_LOCALE_KEY = "cli.overview.warning.m303_simplificado_forfait_unavailable"
_M303_SIMPLIFICADO_FORFAIT_ACTION_ID = "operator.modelo.describe"
_PERIODIC_IVA_ROLE = "iva.periodic"
_APPLICABILITY_DISAGREEMENT_WARNING_CODE = "applicability.evidence_disagreement"
_APPLICABILITY_DISAGREEMENT_WARNING_LOCALE_KEY = "cli.overview.warning.applicability_evidence_disagreement"
_DEADLINE_WINDOWS_UNAVAILABLE_WARNING_CODE_PREFIX = "deadline.windows_unavailable"
_DEADLINE_WINDOWS_UNAVAILABLE_WARNING_LOCALE_KEY = "cli.overview.warning.deadline_windows_unavailable"
_DEADLINE_WINDOWS_UNAVAILABLE_ACTION_ID = "operator.overview.status"


def calendar_applicability_profile_keys_for_modelo(
    modelo: str,
    *,
    operation: PinnedAuthorityOperation,
    revision_inventory: Iterable[tuple[str, ModeloRevision]] | None = None,
) -> tuple[str, ...]:
    """Return profile keys that can influence calendar applicability for ``modelo``.

    The result combines registry applicability rules, IVA-regime coverage, and
    corporate censo axes so calendar provenance warnings use the same profile
    facts that determine legal obligation rows. The rule's payer facts are
    read through
    :attr:`~cadrumo.domain.calculations.registry.applicability_models.ModeloApplicabilityRule.gating_payer_facts`,
    so a fact an exclusion reads counts as well: it decides the modelo's
    verdict, which is what censo enrolment is judged against.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
    """
    keys: set[str] = set()
    estimation_profile_keys = _estimation_regime_profile_key(operation)
    for rule in iter_modelo_applicability_rules(operation=operation):
        if rule.modelo != modelo:
            continue
        keys.add("taxpayer_type.entity_type")
        if rule.required_income_categories:
            keys.add("taxpayer_type.irpf_income_categories")
        if len(rule.required_estimation_regimes) == 1:
            (regime,) = rule.required_estimation_regimes
            if regime in estimation_profile_keys:
                keys.add(estimation_profile_keys[regime][0])
        for payer_fact in rule.gating_payer_facts:
            keys.update(payer_fact_profile_keys(payer_fact))
        break
    keys.update(
        deadline_window_profile_keys_by_modelo(
            operation=operation,
            revision_inventory=revision_inventory,
            modelo=modelo,
        ).get(modelo, ()),
    )
    if modelo_requires_iva_regime(modelo, operation=operation):
        keys.add("iva.regime")
    keys.update(_CORPORATE_CENSO_ENROLMENT_PROFILE_KEYS.get(modelo, frozenset()))
    return tuple(sorted(keys))


def calendar_censo_reconciliation_warnings(
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
            message=_CENSO_ENROLMENT_WARNING_LOCALE_KEY,
            fix_action=declare_next_action(_CENSO_ENROLMENT_ACTION_ID),
            affected_modelos=tuple(sorted(affected_modelos)),
        ),
    )


def calendar_applicability_disagreement_warnings(affected_modelos: Iterable[str]) -> tuple[CalendarWarning, ...]:
    """Return the warning for obligations whose profile answer and ledger derivation disagree.

    The rows stay in the calendar; this warning is what keeps the contradiction
    from passing as either source's answer. The remedy is a profile edit
    because the profile answer is what the operator states, though correcting
    the ledger resolves it as well.
    """
    modelos = tuple(sorted(set(affected_modelos)))
    if not modelos:
        return ()
    return (
        CalendarWarning(
            code=_APPLICABILITY_DISAGREEMENT_WARNING_CODE,
            message=_APPLICABILITY_DISAGREEMENT_WARNING_LOCALE_KEY,
            fix_action=declare_next_action(_PROFILE_EDIT_ACTION_ID),
            affected_modelos=modelos,
        ),
    )


def calendar_deadline_windows_unavailable_warnings(filing_years: Iterable[int]) -> tuple[CalendarWarning, ...]:
    """Return one warning per covered filing year whose deadline windows could not be resolved.

    A year that yields no entries because the registry has no windows for it is
    an unknown answer, not an answer of "nothing is due". The year is carried in
    the warning code so a consumer can tell which part of the range is unresolved.
    """
    return tuple(
        CalendarWarning(
            code=f"{_DEADLINE_WINDOWS_UNAVAILABLE_WARNING_CODE_PREFIX}.{year}",
            message=_DEADLINE_WINDOWS_UNAVAILABLE_WARNING_LOCALE_KEY,
            fix_action=declare_next_action(_DEADLINE_WINDOWS_UNAVAILABLE_ACTION_ID),
        )
        for year in sorted(set(filing_years))
    )


def calendar_censo_enrolment_state(
    *,
    modelo: str,
    live_censo_verified_profile_keys: tuple[str, ...] | None,
    operation: PinnedAuthorityOperation,
    revision_inventory: Iterable[tuple[str, ModeloRevision]] | None = None,
) -> OverviewCensoEnrolmentState:
    """Classify whether censo-stamped profile paths witness ``modelo`` enrolment.

    ``revision_inventory`` is a :class:`ModeloRevision`.
    """
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


def calendar_unverified_justificante_warnings(
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
            message=_JUSTIFICANTE_UNVERIFIED_WARNING_LOCALE_KEY,
            fix_action=_single_fix_action_or_unscoped_pull(fix_actions),
            affected_modelos=tuple(sorted(affected_modelos)),
        ),
    )


def calendar_aeat_evidence_conflict_warnings(
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
            message=_AEAT_EVIDENCE_CONFLICT_WARNING_LOCALE_KEY,
            fix_action=_single_fix_action_or_unscoped_pull(fix_actions),
            affected_modelos=tuple(sorted(affected_modelos)),
        ),
    )


def calendar_regime_incompatibility_warnings(
    *,
    iva_regime: IVARegime | None,
    entries: tuple[OverviewCalendarEntry, ...],
    evaluated_on: date,
    operation: PinnedAuthorityOperation,
) -> tuple[CalendarWarning, ...]:
    """Return warnings where a surfaced modelo row lacks regime-specific calculation support."""
    if iva_regime != iva_regime_simplificado_token(effective_date=evaluated_on, authority=operation):
        return ()
    periodic_iva_modelo = form_for_role(_PERIODIC_IVA_ROLE, authority=operation)
    if not any(entry.modelo == periodic_iva_modelo for entry in entries):
        return ()
    return (
        CalendarWarning(
            code=_M303_SIMPLIFICADO_FORFAIT_WARNING_CODE,
            message=_M303_SIMPLIFICADO_FORFAIT_WARNING_LOCALE_KEY,
            fix_action=declare_next_action(
                _M303_SIMPLIFICADO_FORFAIT_ACTION_ID,
                modelo=periodic_iva_modelo,
            ),
            affected_modelos=(periodic_iva_modelo,),
        ),
    )


def _filed_pull_action(
    *,
    modelo: str,
    filing_year: int | None,
    period: Period | None,
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


def _gating_field_raw_value(
    raw_values: Mapping[str, object],
    key: str,
    *,
    schema: ProfileSchemaDefinition,
) -> object | None:
    """Read one gating field from ``raw_values``, under either key shape it arrives in.

    Every applicability rule and deadline condition names ``key`` as the
    registry selector token (``operator.profile.edit``-style completeness
    keys such as ``"has_employees"``), which is what a selector-keyed
    projection (:func:`~cadrumo.application.user_profile.projections.record_to_values`)
    stores raw values under. A caller that instead projects the profile
    record through
    :func:`~cadrumo.application.user_profile.projections.record_to_path_values`
    stores the same fact under its canonical dotted schema path (for example
    ``"withholding.has_employees"``), which only coincides with the selector
    token when the field sits at the schema root. The schema is the single
    source for that path - :meth:`ProfileSchemaDefinition.path_for_model_selector`
    - so no second spelling table is kept here.
    """
    raw = raw_values.get(key)
    if raw is not None:
        return raw
    path = schema.path_for_model_selector(key)
    if path is None or path == key:
        return None
    return raw_values.get(path)


def build_completeness_and_warnings(
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

    ``revision_inventory`` is a :class:`ModeloRevision`.
    """
    if raw_values is None:
        return CalendarCompleteness(), ()
    schema = operation.profile_schema()
    explicitly_set: list[str] = []
    defaulted: list[str] = []
    warnings: list[CalendarWarning] = []
    defaulted_modelos: set[str] = set()
    for key, (affected_modelos, message_key, action_id) in _gating_fields(
        operation=operation,
        revision_inventory=revision_inventory,
    ).items():
        raw = _gating_field_raw_value(raw_values, key, schema=schema)
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
    "build_completeness_and_warnings",
    "calendar_aeat_evidence_conflict_warnings",
    "calendar_applicability_disagreement_warnings",
    "calendar_applicability_profile_keys_for_modelo",
    "calendar_censo_enrolment_state",
    "calendar_censo_reconciliation_warnings",
    "calendar_deadline_windows_unavailable_warnings",
    "calendar_regime_incompatibility_warnings",
    "calendar_unverified_justificante_warnings",
]
