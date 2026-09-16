"""Profile readiness gate for filing-grade modelo work.

Loads the active :class:`domain.user_profile.values.UserProfileRecord`, builds a
:class:`application.user_profile.ProfilePreflightReport`, projects
local-work applicability through :class:`domain.deadlines.TaxpayerProfile`,
and raises :class:`application.modelo.ModeloProfileReadinessError` before
filing-grade work proceeds when required profile facts are missing. The
revision-specific preflight branch may receive a :class:`ModeloRevision` that
has already been resolved by an operator-facing readiness surface. The same gate
also refuses Modelo 130 and Modelo 303 target periods whose date span ends
before the profile's ``censo.activity_start_date``; those pre-activity periods
have no filing obligation and must not produce stale work, calculation,
verification, filing, or export state.

See Also:
    :func:`require_profile_ready_for_work_unit`:
        Replays the same readiness checks for an existing
        :class:`~WorkUnit`.
    :class:`application.user_profile.ProfilePreflightReport`:
        User-profile preflight result consumed by this application gate.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import TYPE_CHECKING

from ...core.errors.severity import BaseSeverity
from ...core.modelo import Modelo
from ...core.parsing.dates import parse_iso8601_date
from ...core.period import Period
from ...domain.calculations.registry.applicability import (
    ApplicabilityVerdict,
    derive_modelo_applicability,
)
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.errors import RegistrySnapshotError
from ...domain.calculations.registry.ids import RevisionId
from ...domain.calculations.registry.irpf_income_categories import irpf_income_category_actividad_economica_token
from ...domain.calculations.registry.profile_grounding import (
    ProfileKeyGrounding,
    build_profile_grounding_index,
)
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.contribuyente.entity_type import entity_type_natural_person_token
from ...domain.modelos.work_unit import WorkUnit
from ...domain.user_profile.errors import ProfileNotFoundError
from ...domain.user_profile.values import ProfileSetupState, UserProfileRecord
from ..user_profile.commands import ProfilePreflightReport, ProfilePreflightRequirement, ProfileValidationIssue
from ..user_profile.completeness import missing_required_field_paths
from ..user_profile.preflight import (
    ProfilePreflightService,
    build_profile_preflight_requirement,
    format_profile_preflight_requirement,
)
from ..user_profile.profile_record_repository import ProfileRecordRepository
from ..user_profile.projections import projection_for_taxpayer, record_to_path_values
from ..user_profile.validation import MODELO_WORK_PROFILE_BASELINE_MISSING_CODE, ProfileValidationService
from .action_errors import ModeloProfileReadinessError
from .work_profile import ModeloWorkProfile

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority_artifact import ProfileDecodeContext

_PROFILE_ACTIVITY_START_PATH = "censo.activity_start_date"
_PRE_ACTIVITY_LIFECYCLE_MODELOS = frozenset({Modelo("130").value, Modelo("303").value})
_FILING_BASELINE_PROFILE_PATHS = ("identity.tax_id",)
_PROFILE_ACTIVITY_DESCRIPTION_PATH = "activities.description"
#: Shared with :mod:`.work_create_policy`, which runs the same applicability
#: block ahead of work-unit provisioning; kept public so that cross-module use
#: is a declared contract rather than a private-symbol reach.
BLOCKING_APPLICABILITY_VERDICTS = frozenset(
    {
        ApplicabilityVerdict.NOT_APPLICABLE,
        ApplicabilityVerdict.ATTRIBUTION_PASS_THROUGH,
    },
)


def _requirement_for_profile_path(
    path: str,
    *,
    selector: str | None = None,
    grounding_index: Mapping[str, ProfileKeyGrounding] | None = None,
    profile_decode_context: ProfileDecodeContext,
) -> ProfilePreflightRequirement:
    """Build one requirement row for a raw (possibly row-indexed) profile path.

    Thin call-site wrapper over the shared
    :func:`application.user_profile.build_profile_preflight_requirement`,
    resolving the live schema singleton - the one requirement-row builder
    this package and :class:`application.user_profile.ProfilePreflightService`
    both route through.
    """
    return build_profile_preflight_requirement(
        path,
        schema=profile_decode_context.schema,
        selector=selector,
        grounding_index=grounding_index,
    )


def _dedupe_requirements(
    requirements: tuple[ProfilePreflightRequirement, ...] | list[ProfilePreflightRequirement],
) -> tuple[ProfilePreflightRequirement, ...]:
    seen: set[tuple[str, str]] = set()
    deduped: list[ProfilePreflightRequirement] = []
    for requirement in requirements:
        key = (requirement.section_key, requirement.field_key)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(requirement)
    return tuple(deduped)


def _modelo_work_baseline_paths(record: UserProfileRecord, *, modelo: str | None) -> tuple[str, ...]:
    """Return the universal and target-aware profile baseline paths.

    ``activities.description`` is a real censo fact for economic-activity
    work, but it is not a universal filing precondition. A resident
    pensioner/landlord can legitimately have Modelo 100 as their only
    applicable return and must not invent an activity merely to create it.
    """
    values = record_to_path_values(record)
    income_categories = frozenset(
        token.strip() for token in values.get("taxpayer_type.irpf_income_categories", "").split(",") if token.strip()
    )
    declares_economic_activity = irpf_income_category_actividad_economica_token().value in income_categories
    if modelo is None:
        if (
            values.get("taxpayer_type.entity_type") != entity_type_natural_person_token().value
            or not income_categories
            or declares_economic_activity
        ):
            return (*_FILING_BASELINE_PROFILE_PATHS, _PROFILE_ACTIVITY_DESCRIPTION_PATH)
        return _FILING_BASELINE_PROFILE_PATHS
    if modelo.strip() != Modelo("100").value or not income_categories or declares_economic_activity:
        return (*_FILING_BASELINE_PROFILE_PATHS, _PROFILE_ACTIVITY_DESCRIPTION_PATH)
    return _FILING_BASELINE_PROFILE_PATHS


def modelo_work_profile_baseline_missing_paths(
    record: UserProfileRecord,
    *,
    modelo: str | None = None,
) -> tuple[str, ...]:
    """Return profile facts required before filing-grade work for a target.

    Without a target this returns the profile-status baseline: every
    non-natural entity, an economically active natural person, and an
    incompletely declared natural person need an activity description. A
    natural person with declared non-business income needs only a tax id.
    Targeted Modelo 100 checks use the same distinction; all other targets
    retain the existing censo-activity baseline.

    Args:
        record: Active :class:`domain.user_profile.values.UserProfileRecord`
            projected into schema-path values.
        modelo: Optional target modelo used to resolve conditional baseline
            requirements.
    """
    values = record_to_path_values(record)
    return tuple(
        path for path in _modelo_work_baseline_paths(record, modelo=modelo) if not values.get(path, "").strip()
    )


def modelo_work_profile_baseline_validation_issues(record: UserProfileRecord) -> tuple[ProfileValidationIssue, ...]:
    """Return profile-status issues for universal modelo-work baseline fields.

    Args:
        record: Active :class:`domain.user_profile.values.UserProfileRecord`
            checked against the filing-grade baseline.

    Returns:
        Tuple of :class:`application.user_profile.ProfileValidationIssue`
        instances for missing filing-grade baseline facts.
    """
    return tuple(
        ProfileValidationIssue(
            severity=BaseSeverity.ERROR,
            code=MODELO_WORK_PROFILE_BASELINE_MISSING_CODE,
            path=path,
            message=f"modelo work profile baseline field {path} is missing",
        )
        for path in modelo_work_profile_baseline_missing_paths(record)
    )


def _validation_missing_requirements(
    record: UserProfileRecord,
    *,
    grounding_index: Mapping[str, ProfileKeyGrounding] | None = None,
    profile_decode_context: ProfileDecodeContext,
) -> tuple[ProfilePreflightRequirement, ...]:
    validation = ProfileValidationService(schema=profile_decode_context.schema).validate_record(record)
    requirements: list[ProfilePreflightRequirement] = []
    for issue in validation.issues:
        if issue.severity.value != "error":
            continue
        path = issue.path or issue.code
        requirements.append(
            _requirement_for_profile_path(
                path,
                selector=issue.path or f"profile.validation.{issue.code}",
                grounding_index=grounding_index,
                profile_decode_context=profile_decode_context,
            ),
        )
    return tuple(requirements)


def modelo_work_profile_preflight_report(
    *,
    record: UserProfileRecord,
    modelo: str,
    revision_id: RevisionId,
    filing_year: int,
    period: Period,
    revision: ModeloRevision | None = None,
    resolve_revision_when_missing: bool = True,
    profile_decode_context: ProfileDecodeContext,
    operation: PinnedAuthorityOperation,
) -> ProfilePreflightReport:
    """Return the profile-field report enforced by the modelo work creation gate.

    This combines the filing-grade baseline that every modelo work unit needs
    with the modelo/revision-specific profile selectors. Public readiness
    surfaces consume this function so they cannot claim profile readiness before
    :func:`application.modelo.create_work_unit` would reject the same active
    profile.

    Args:
        record: Active :class:`domain.user_profile.values.UserProfileRecord`.
        modelo: Modelo code being checked.
        revision_id: Registry revision identifier for the target modelo work.
        filing_year: Filing year for the target period.
        period: Target :class:`core.Period` used for registry revision
            resolution and profile selector evaluation.
        revision: Optional :class:`ModeloRevision` supplied when the caller has
            already resolved the target revision.
        resolve_revision_when_missing: Whether to resolve the registry
            revision when ``revision`` is not supplied.
        profile_decode_context: Decode context from the caller-held authority
            operation used to interpret the encrypted profile.
        operation: Caller-held pinned authority operation used to select the
            target revision and profile schema.

    Returns:
        :class:`application.user_profile.ProfilePreflightReport` combining
        baseline, validation, and modelo/revision-specific missing requirements.
    """
    if revision is None and resolve_revision_when_missing:
        report = _report_for_target(
            record=record,
            modelo=modelo,
            revision_id=revision_id,
            filing_year=filing_year,
            period=period,
            profile_decode_context=profile_decode_context,
            operation=operation,
        )
    else:
        report = ProfilePreflightService(schema=profile_decode_context.schema).report(
            record=record,
            modelo=modelo,
            revision_id=revision_id,
            period=period,
            revision=revision,
        )
    grounding_index = build_profile_grounding_index(operation)
    baseline = tuple(
        _requirement_for_profile_path(
            path,
            grounding_index=grounding_index,
            profile_decode_context=profile_decode_context,
        )
        for path in modelo_work_profile_baseline_missing_paths(record, modelo=modelo)
    )
    missing = _dedupe_requirements(
        (
            *baseline,
            *_validation_missing_requirements(
                record,
                grounding_index=grounding_index,
                profile_decode_context=profile_decode_context,
            ),
            *report.missing,
        ),
    )
    return report.model_copy(update={"missing": missing, "ready": not missing})


def _report_for_target(
    *,
    record: UserProfileRecord,
    modelo: str,
    revision_id: RevisionId,
    filing_year: int,
    period: Period,
    profile_decode_context: ProfileDecodeContext,
    operation: PinnedAuthorityOperation,
) -> ProfilePreflightReport:
    try:
        revision = operation.revision_for_context(
            modelo,
            filing_year=filing_year,
            period=period.registry_token,
            revision_id=revision_id,
        )
    except (FileNotFoundError, RegistrySnapshotError):
        revision = None
    return ProfilePreflightService(schema=profile_decode_context.schema).report(
        record=record,
        modelo=modelo,
        revision_id=revision_id,
        period=period,
        revision=revision,
    )


def profile_activity_start_date(record: UserProfileRecord) -> date | None:
    """Read the effective ``censo.activity_start_date`` through the canonical projection.

    Which of several live facts at one path is *effective* is owned by
    :func:`application.user_profile.record_to_path_values`, which orders them by
    ``valid_from`` so the chronologically last window wins. Scanning declaration
    order answers a different question: a record whose later window was declared
    first resolves to the earlier date, and because this value decides whether a
    target period is refused as pre-activity, the disagreement fails open — a
    period before the effective activity start is admitted for work.
    """
    rendered = record_to_path_values(record).get(_PROFILE_ACTIVITY_START_PATH)
    if rendered is None:
        return None
    return parse_iso8601_date(rendered)


def _require_not_pre_activity_period(
    *,
    record: UserProfileRecord,
    bucket_id: str,
    modelo: str,
    filing_year: int,
    period: Period,
) -> None:
    refusal = pre_activity_period_refusal(
        record=record,
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
    )
    if refusal is None:
        return
    message, context = refusal
    raise ModeloProfileReadinessError(
        message,
        context=context,
    )


def _require_modelo_applicable_for_local_work(
    *,
    record: UserProfileRecord,
    bucket_id: str,
    modelo: str,
    operation: PinnedAuthorityOperation,
) -> None:
    refusal = modelo_applicability_refusal(
        record=record,
        bucket_id=bucket_id,
        modelo=modelo,
        operation=operation,
    )
    if refusal is None:
        return
    message, context = refusal
    raise ModeloProfileReadinessError(
        message,
        context=context,
    )


def modelo_applicability_refusal(
    *,
    record: UserProfileRecord,
    bucket_id: str,
    modelo: str,
    operation: PinnedAuthorityOperation,
) -> tuple[str, dict[str, str]] | None:
    """Return the local-work applicability refusal for a target, if any.

    Args:
        record: Active :class:`domain.user_profile.values.UserProfileRecord`
            projected into taxpayer facts for the modelo applicability check.
        bucket_id: Active profile bucket identifier included in the refusal
            context.
        modelo: Modelo code being checked.
        operation: Caller-held pinned operation for applicability facts.
    """
    modelo_code = modelo.strip()
    profile = projection_for_taxpayer(record, schema=operation.profile_schema())
    applicability = derive_modelo_applicability(profile, modelo_code, operation=operation)
    if applicability.verdict not in BLOCKING_APPLICABILITY_VERDICTS:
        return None
    return (
        f"Modelo {modelo_code} is not applicable to the active profile: {applicability.reason}",
        {
            "bucket_id": bucket_id,
            "modelo": modelo_code,
            "applicability_verdict": applicability.verdict.value,
            "legal_refs": ", ".join(applicability.legal_refs),
        },
    )


def pre_activity_period_refusal(
    *,
    record: UserProfileRecord,
    bucket_id: str,
    modelo: str,
    filing_year: int,
    period: Period,
) -> tuple[str, dict[str, str | int]] | None:
    """Return the pre-activity lifecycle refusal for a target, if any.

    Args:
        record: Active :class:`domain.user_profile.values.UserProfileRecord`
            carrying the profile facts used to resolve
            ``censo.activity_start_date``.
        bucket_id: Active profile bucket identifier included in the refusal
            context.
        modelo: Modelo code being checked.
        filing_year: Filing year for the target period.
        period: Target :class:`core.Period` whose date span is compared
            against the profile activity-start date.
    """
    modelo_code = modelo.strip()
    if modelo_code not in _PRE_ACTIVITY_LIFECYCLE_MODELOS or not period.has_date_span():
        return None
    activity_start_date = profile_activity_start_date(record)
    if activity_start_date is None:
        return None
    period_end_date = period.end_date
    if period_end_date >= activity_start_date:
        return None
    return (
        f"Modelo {modelo_code} {filing_year} {period.registry_token} is before the profile "
        f"activity-start date {activity_start_date.isoformat()}; the filing period ends on "
        f"{period_end_date.isoformat()}, so no Modelo {modelo_code} work unit, calculation, or verification "
        "may proceed for this pre-activity period.",
        {
            "bucket_id": bucket_id,
            "modelo": modelo_code,
            "filing_year": filing_year,
            "period": period.registry_token,
            "activity_start_date": activity_start_date.isoformat(),
            "period_end_date": period_end_date.isoformat(),
        },
    )


def _require_profile_filing_ready(
    *,
    record: UserProfileRecord,
    bucket_id: str,
    modelo: str,
    filing_year: int,
    period: Period,
    grounding_index: Mapping[str, ProfileKeyGrounding] | None = None,
    profile_decode_context: ProfileDecodeContext,
) -> None:
    """Refuse when a baseline or validation-required profile fact is missing.

    ``grounding_index`` is optional and, when omitted, this stays the
    registry-free check :func:`require_existing_profile_baseline_ready_for_modelo_work`
    relies on. :func:`require_profile_ready_for_modelo_work` passes the
    memoised grounding index so its refusal carries real legal grounding
    instead of a bare label.
    """
    missing: list[ProfilePreflightRequirement] = [
        _requirement_for_profile_path(
            path,
            grounding_index=grounding_index,
            profile_decode_context=profile_decode_context,
        )
        for path in modelo_work_profile_baseline_missing_paths(record, modelo=modelo)
    ]
    seen = {(item.section_key, item.field_key) for item in missing}
    for requirement in _validation_missing_requirements(
        record,
        grounding_index=grounding_index,
        profile_decode_context=profile_decode_context,
    ):
        key = (requirement.section_key, requirement.field_key)
        if key not in seen:
            seen.add(key)
            missing.append(requirement)
    if not missing:
        return
    raise ModeloProfileReadinessError(
        translated_message="application.modelo.errors.profile_readiness_missing",
        context={
            "modelo": modelo,
            "filing_year": filing_year,
            "period": period.registry_token,
            "missing": ", ".join(format_profile_preflight_requirement(requirement) for requirement in missing),
        },
    )


def _render_missing_requirement(requirement: ProfilePreflightRequirement) -> str:
    """Render one missing requirement as its label plus the articles demanding it.

    A label alone tells an operator WHICH field is missing; the refusal's job is
    also to say on whose authority. Where the registry grounds the field, the
    refs follow the label in parentheses; where it grounds nothing, the label
    stands alone rather than trailing an empty bracket.
    """
    if not requirement.legal_refs:
        return requirement.label
    return f"{requirement.label} ({', '.join(requirement.legal_refs)})"


def load_modelo_work_profile(
    *,
    bucket_id: str,
    profile_decode_context: ProfileDecodeContext,
) -> ModeloWorkProfile | None:
    """Load the bucket's profile for modelo work, or ``None`` when no session serves it."""
    try:
        repository = ProfileRecordRepository.for_current_session(
            bucket_id,
            profile_decode_context=profile_decode_context,
        )
        return ModeloWorkProfile(
            record=repository.load(bucket_id),
            profile_decode_context=repository.session.profile_decode_context,
        )
    except ProfileNotFoundError:
        return None


def _load_profile_for_modelo_work(
    *,
    bucket_id: str,
    profile_decode_context: ProfileDecodeContext,
    profile: ModeloWorkProfile | None,
) -> ModeloWorkProfile:
    loaded = profile or load_modelo_work_profile(bucket_id=bucket_id, profile_decode_context=profile_decode_context)
    if loaded is None:
        raise ModeloProfileReadinessError(
            translated_message="application.modelo.errors.profile_readiness_profile_missing",
            context={"bucket_id": bucket_id},
        )
    return loaded


def _require_profile_setup_complete(
    *,
    record: UserProfileRecord,
    bucket_id: str,
    modelo: str,
    profile_decode_context: ProfileDecodeContext,
    grounding_index: Mapping[str, ProfileKeyGrounding] | None = None,
) -> None:
    """Refuse setup profiles before any filing-grade readiness checks run."""
    if record.setup_state is not ProfileSetupState.INCOMPLETE:
        return
    schema = profile_decode_context.schema
    missing_paths = missing_required_field_paths(schema, record_to_path_values(record))
    if missing_paths:
        grounding = grounding_index or {}
        missing_labels = ", ".join(
            _render_missing_requirement(
                build_profile_preflight_requirement(path, schema=schema, grounding_index=grounding),
            )
            for path in missing_paths
        )
        raise ModeloProfileReadinessError(
            translated_message="application.modelo.errors.profile_readiness_setup_incomplete_missing",
            context={"bucket_id": bucket_id, "modelo": modelo, "missing": missing_labels},
        )
    raise ModeloProfileReadinessError(
        translated_message="application.modelo.errors.profile_readiness_setup_incomplete",
        context={"bucket_id": bucket_id, "modelo": modelo},
    )


def _raise_if_profile_preflight_missing(
    report: ProfilePreflightReport,
    *,
    modelo: str,
    filing_year: int,
    period: Period,
) -> None:
    if report.ready:
        return
    raise ModeloProfileReadinessError(
        translated_message="application.modelo.errors.profile_readiness_missing",
        context={
            "modelo": modelo,
            "filing_year": filing_year,
            "period": period.registry_token,
            "missing": ", ".join(format_profile_preflight_requirement(requirement) for requirement in report.missing),
        },
    )


def require_profile_ready_for_modelo_work(
    *,
    bucket_id: str,
    modelo: str,
    revision_id: RevisionId,
    filing_year: int,
    period: Period,
    enforce_applicability: bool = True,
    profile_decode_context: ProfileDecodeContext,
    operation: PinnedAuthorityOperation,
    profile: ModeloWorkProfile | None = None,
) -> ModeloWorkProfile:
    """Refuse filing-grade modelo work when the active profile is not eligible.

    Loads the bucket's :class:`domain.user_profile.values.UserProfileRecord`,
    evaluates modelo-specific profile requirements through
    :class:`application.user_profile.ProfilePreflightReport`, and then
    applies the pre-activity period check for lifecycle modelos whose obligation
    starts at ``censo.activity_start_date``. Unlike
    :func:`require_existing_profile_baseline_ready_for_modelo_work`, this gate
    passes the live registry authority through both the baseline/validation
    refusal and the full preflight report, so a raised
    :class:`ModeloProfileReadinessError` carries real ``legal_refs`` for every
    missing field the registry grounds - the memoised
    ``build_profile_grounding_index`` keeps the added per-call cost bounded on
    this hot path. ``profile`` is the record the calling command already
    loaded for this target; when omitted the gate loads it. Returns the record
    the gate checked, so a caller that let the gate load it passes that same
    record on instead of decrypting it again.
    """
    loaded = _load_profile_for_modelo_work(
        bucket_id=bucket_id,
        profile_decode_context=profile_decode_context,
        profile=profile,
    )
    record, resolved_profile_decode_context = loaded.record, loaded.profile_decode_context
    _require_profile_setup_complete(
        record=record,
        bucket_id=bucket_id,
        modelo=modelo,
        profile_decode_context=resolved_profile_decode_context,
        grounding_index=build_profile_grounding_index(operation),
    )
    grounding_index: Mapping[str, ProfileKeyGrounding] = build_profile_grounding_index(operation)
    applicability_first = enforce_applicability and modelo.strip() in _PRE_ACTIVITY_LIFECYCLE_MODELOS
    if applicability_first:
        _require_modelo_applicable_for_local_work(
            record=record,
            bucket_id=bucket_id,
            modelo=modelo,
            operation=operation,
        )
    _require_profile_filing_ready(
        record=record,
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        grounding_index=grounding_index,
        profile_decode_context=resolved_profile_decode_context,
    )
    if enforce_applicability and not applicability_first:
        _require_modelo_applicable_for_local_work(
            record=record,
            bucket_id=bucket_id,
            modelo=modelo,
            operation=operation,
        )
    report = modelo_work_profile_preflight_report(
        record=record,
        modelo=modelo,
        revision_id=revision_id,
        filing_year=filing_year,
        period=period,
        profile_decode_context=resolved_profile_decode_context,
        operation=operation,
    )
    _raise_if_profile_preflight_missing(report, modelo=modelo, filing_year=filing_year, period=period)
    _require_not_pre_activity_period(
        record=record,
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
    )
    return loaded


def require_existing_profile_baseline_ready_for_modelo_work(
    *,
    bucket_id: str,
    modelo: str,
    filing_year: int,
    period: Period,
    enforce_applicability: bool = True,
    profile_decode_context: ProfileDecodeContext,
    operation: PinnedAuthorityOperation,
    profile: ModeloWorkProfile | None = None,
) -> None:
    """Refuse plainly incomplete existing profiles before registry work.

    This early gate is used by :func:`application.modelo.create_work_unit`
    before the registry revision and period are validated. It catches missing
    baseline profile facts, local-work applicability refusals, and pre-activity
    lifecycle periods without requiring a resolvable :class:`ModeloRevision`.
    Missing profiles still pass through so the later full readiness gate can
    raise the canonical missing-profile error. ``profile`` is the record the
    calling command already loaded; when omitted the gate loads it.
    """
    loaded = profile or load_modelo_work_profile(bucket_id=bucket_id, profile_decode_context=profile_decode_context)
    if loaded is None:
        return
    record = loaded.record
    applicability_first = enforce_applicability and modelo.strip() in _PRE_ACTIVITY_LIFECYCLE_MODELOS
    if applicability_first:
        _require_modelo_applicable_for_local_work(
            record=record,
            bucket_id=bucket_id,
            modelo=modelo,
            operation=operation,
        )
    _require_profile_filing_ready(
        record=record,
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        profile_decode_context=loaded.profile_decode_context,
    )
    if enforce_applicability and not applicability_first:
        _require_modelo_applicable_for_local_work(
            record=record,
            bucket_id=bucket_id,
            modelo=modelo,
            operation=operation,
        )
    _require_not_pre_activity_period(
        record=record,
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
    )


def require_profile_ready_for_work_unit(
    work_unit: WorkUnit,
    *,
    enforce_applicability: bool = True,
    profile_decode_context: ProfileDecodeContext,
    operation: PinnedAuthorityOperation,
    profile: ModeloWorkProfile | None = None,
) -> ModeloWorkProfile:
    """Run the profile readiness gate for an existing work unit.

    Calculation, verification, filing, and export services call this wrapper so
    a previously created :class:`~WorkUnit` is rechecked
    against the current :class:`domain.user_profile.values.UserProfileRecord`
    before any filing-grade mutation proceeds. Returns the checked record.
    """
    return require_profile_ready_for_modelo_work(
        bucket_id=work_unit.bucket_id,
        modelo=str(work_unit.modelo),
        revision_id=work_unit.revision_id,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        enforce_applicability=enforce_applicability,
        profile_decode_context=profile_decode_context,
        operation=operation,
        profile=profile,
    )


__all__ = [
    "BLOCKING_APPLICABILITY_VERDICTS",
    "load_modelo_work_profile",
    "modelo_applicability_refusal",
    "modelo_work_profile_baseline_missing_paths",
    "modelo_work_profile_baseline_validation_issues",
    "modelo_work_profile_preflight_report",
    "pre_activity_period_refusal",
    "profile_activity_start_date",
    "require_existing_profile_baseline_ready_for_modelo_work",
    "require_profile_ready_for_modelo_work",
    "require_profile_ready_for_work_unit",
]
