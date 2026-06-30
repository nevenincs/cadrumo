"""Profile readiness gate for filing-grade modelo work.

Loads the active :class:`aeat.domain.user_profile.UserProfileRecord`, builds a
:class:`aeat.application.user_profile.ProfilePreflightReport`, projects
local-work applicability through :class:`aeat.domain.deadlines.TaxpayerProfile`,
and raises :class:`aeat.application.modelo.ModeloProfileReadinessError` before
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
        :class:`aeat.domain.modelos.WorkUnit`.
    :class:`aeat.application.user_profile.ProfilePreflightReport`:
        User-profile preflight result consumed by this application gate.
"""

from __future__ import annotations

from datetime import date

from ...core import Modelo, Period
from ...core.errors import BaseSeverity
from ...core.parsing import parse_iso8601_date
from ...core.resources import resources
from ...domain.calculations.registry import (
    ApplicabilityVerdict,
    ModeloRevision,
    RegistrySnapshotError,
    derive_modelo_applicability,
)
from ...domain.modelos._work_unit import WorkUnit
from ...domain.user_profile import ProfileNotFoundError, UserProfileRecord
from ..user_profile import (
    ProfilePreflightReport,
    ProfilePreflightRequirement,
    ProfileValidationIssue,
    ProfileValidationService,
    UserProfileLifecycleRepository,
    projection_for_taxpayer,
    record_to_path_values,
)
from ..user_profile._preflight import ProfilePreflightService
from ._action_errors import ModeloProfileReadinessError

_PROFILE_ACTIVITY_START_PATH = "censo.activity_start_date"
_PRE_ACTIVITY_LIFECYCLE_MODELOS = frozenset({Modelo.M130.value, Modelo.M303.value})
_FILING_BASELINE_PROFILE_PATHS = ("identity.tax_id", "activities.description")
_BLOCKING_APPLICABILITY_VERDICTS = frozenset(
    {
        ApplicabilityVerdict.NOT_APPLICABLE,
        ApplicabilityVerdict.ATTRIBUTION_PASS_THROUGH,
    },
)


def _split_profile_path(path: str) -> tuple[str, str]:
    section_key, _, field_key = path.partition(".")
    if not field_key:
        return "profile", section_key
    return section_key, field_key


def _requirement_for_profile_path(path: str, *, selector: str | None = None) -> ProfilePreflightRequirement:
    section_key, field_key = _split_profile_path(path)
    return ProfilePreflightRequirement(
        selector=selector or path,
        section_key=section_key,
        field_key=field_key,
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


def modelo_work_profile_baseline_missing_paths(record: UserProfileRecord) -> tuple[str, ...]:
    """Return profile facts required before any filing-grade modelo work starts.

    Args:
        record: Active :class:`aeat.domain.user_profile.UserProfileRecord`
            projected into schema-path values.
    """
    values = record_to_path_values(record)
    return tuple(path for path in _FILING_BASELINE_PROFILE_PATHS if not values.get(path, "").strip())


def modelo_work_profile_baseline_validation_issues(record: UserProfileRecord) -> tuple[ProfileValidationIssue, ...]:
    """Return validate-surface issues for the central modelo work profile baseline.

    Args:
        record: Active :class:`aeat.domain.user_profile.UserProfileRecord`
            checked against the filing-grade baseline.

    Returns:
        Tuple of :class:`aeat.application.user_profile.ProfileValidationIssue`
        instances for missing filing-grade baseline facts.
    """
    return tuple(
        ProfileValidationIssue(
            severity=BaseSeverity.ERROR,
            code="modelo_work_profile_baseline_missing",
            path=path,
            message=f"modelo work profile baseline field {path} is missing",
        )
        for path in modelo_work_profile_baseline_missing_paths(record)
    )


def _validation_missing_requirements(record: UserProfileRecord) -> tuple[ProfilePreflightRequirement, ...]:
    validation = ProfileValidationService(schema=resources().user_profile_schema.singleton).validate_record(record)
    requirements: list[ProfilePreflightRequirement] = []
    for issue in validation.issues:
        if issue.severity.value != "error":
            continue
        path = issue.path or issue.code
        requirements.append(
            _requirement_for_profile_path(
                path,
                selector=issue.path or f"profile.validation.{issue.code}",
            ),
        )
    return tuple(requirements)


def modelo_work_profile_preflight_report(
    *,
    record: UserProfileRecord,
    modelo: str,
    revision_id: str,
    filing_year: int,
    period: Period,
    revision: ModeloRevision | None = None,
    resolve_revision_when_missing: bool = True,
) -> ProfilePreflightReport:
    """Return the profile-field report enforced by the modelo work creation gate.

    This combines the filing-grade baseline that every modelo work unit needs
    with the modelo/revision-specific profile selectors. Public readiness
    surfaces consume this function so they cannot claim profile readiness before
    :func:`aeat.application.modelo.create_work_unit` would reject the same active
    profile.

    Args:
        record: Active :class:`aeat.domain.user_profile.UserProfileRecord`.
        modelo: Modelo code being checked.
        revision_id: Registry revision identifier for the target modelo work.
        filing_year: Filing year for the target period.
        period: Target :class:`aeat.core.Period` used for registry revision
            resolution and profile selector evaluation.
        revision: Optional :class:`ModeloRevision` supplied when the caller has
            already resolved the target revision.
        resolve_revision_when_missing: Whether to resolve the registry
            revision when ``revision`` is not supplied.

    Returns:
        :class:`aeat.application.user_profile.ProfilePreflightReport` combining
        baseline, validation, and modelo/revision-specific missing requirements.
    """
    if revision is None and resolve_revision_when_missing:
        report = _report_for_target(
            record=record,
            modelo=modelo,
            revision_id=revision_id,
            filing_year=filing_year,
            period=period,
        )
    else:
        report = ProfilePreflightService(schema=resources().user_profile_schema.singleton).report(
            record=record,
            modelo=modelo,
            revision_id=revision_id,
            period=period,
            revision=revision,
        )
    baseline = tuple(_requirement_for_profile_path(path) for path in modelo_work_profile_baseline_missing_paths(record))
    missing = _dedupe_requirements((*baseline, *_validation_missing_requirements(record), *report.missing))
    return report.model_copy(update={"missing": missing, "ready": not missing})


def _report_for_target(
    *,
    record: UserProfileRecord,
    modelo: str,
    revision_id: str,
    filing_year: int,
    period: Period,
) -> ProfilePreflightReport:
    try:
        snapshot = resources().modelos.authority.snapshot(
            modelo,
            filing_year=filing_year,
            period=period.registry_token,
        )
        revision = snapshot.revision if snapshot.revision.id == revision_id else None
    except (FileNotFoundError, RegistrySnapshotError):
        revision = None
    return ProfilePreflightService(schema=resources().user_profile_schema.singleton).report(
        record=record,
        modelo=modelo,
        revision_id=revision_id,
        period=period,
        revision=revision,
    )


def _profile_activity_start_date(record: UserProfileRecord) -> date | None:
    for fact in reversed(record.facts):
        if fact.path != _PROFILE_ACTIVITY_START_PATH or fact.value is None:
            continue
        if isinstance(fact.value, date):
            return fact.value
        if isinstance(fact.value, str):
            try:
                return parse_iso8601_date(fact.value)
            except ValueError:
                return None
        return None
    return None


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
        suggestion=f"aeat config profile edit {bucket_id}",
    )


def _require_modelo_applicable_for_local_work(
    *,
    record: UserProfileRecord,
    bucket_id: str,
    modelo: str,
) -> None:
    refusal = modelo_applicability_refusal(record=record, bucket_id=bucket_id, modelo=modelo)
    if refusal is None:
        return
    message, context = refusal
    raise ModeloProfileReadinessError(
        message,
        context=context,
        suggestion=f"aeat app modelo describe {modelo.strip()}",
    )


def modelo_applicability_refusal(
    *,
    record: UserProfileRecord,
    bucket_id: str,
    modelo: str,
) -> tuple[str, dict[str, str]] | None:
    """Return the local-work applicability refusal for a target, if any.

    Args:
        record: Active :class:`aeat.domain.user_profile.UserProfileRecord`
            projected into taxpayer facts for the modelo applicability check.
        bucket_id: Active profile bucket identifier included in the refusal
            context.
        modelo: Modelo code being checked.
    """
    modelo_code = modelo.strip()
    profile = projection_for_taxpayer(record, tax_id_default="00000000T")
    applicability = derive_modelo_applicability(profile, modelo_code)
    if applicability.verdict not in _BLOCKING_APPLICABILITY_VERDICTS:
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
        record: Active :class:`aeat.domain.user_profile.UserProfileRecord`
            carrying the profile facts used to resolve
            ``censo.activity_start_date``.
        bucket_id: Active profile bucket identifier included in the refusal
            context.
        modelo: Modelo code being checked.
        filing_year: Filing year for the target period.
        period: Target :class:`aeat.core.Period` whose date span is compared
            against the profile activity-start date.
    """
    modelo_code = modelo.strip()
    if modelo_code not in _PRE_ACTIVITY_LIFECYCLE_MODELOS or not period.has_date_span():
        return None
    activity_start_date = _profile_activity_start_date(record)
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
) -> None:
    missing: list[str] = list(modelo_work_profile_baseline_missing_paths(record))
    for requirement in _validation_missing_requirements(record):
        path = f"{requirement.section_key}.{requirement.field_key}"
        if path not in missing:
            missing.append(path)
    if not missing:
        return
    raise ModeloProfileReadinessError(
        translated_message="application.modelo.errors.profile_readiness_missing",
        context={
            "modelo": modelo,
            "filing_year": filing_year,
            "period": period.registry_token,
            "missing": ", ".join(missing),
        },
        suggestion=f"aeat config profile edit {bucket_id}",
    )


def require_profile_ready_for_modelo_work(
    *,
    bucket_id: str,
    modelo: str,
    revision_id: str,
    filing_year: int,
    period: Period,
    enforce_applicability: bool = True,
) -> None:
    """Refuse filing-grade modelo work when the active profile is not eligible.

    Loads the bucket's :class:`aeat.domain.user_profile.UserProfileRecord`,
    evaluates modelo-specific profile requirements through
    :class:`aeat.application.user_profile.ProfilePreflightReport`, and then
    applies the pre-activity period check for lifecycle modelos whose obligation
    starts at ``censo.activity_start_date``.
    """
    try:
        record = UserProfileLifecycleRepository(bucket_id=bucket_id).load(bucket_id)
    except ProfileNotFoundError as exc:
        raise ModeloProfileReadinessError(
            translated_message="application.modelo.errors.profile_readiness_profile_missing",
            context={"bucket_id": bucket_id},
            suggestion="aeat config profile create NAME",
        ) from exc
    _require_profile_filing_ready(
        record=record,
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
    )
    if enforce_applicability:
        _require_modelo_applicable_for_local_work(
            record=record,
            bucket_id=bucket_id,
            modelo=modelo,
        )
    report = modelo_work_profile_preflight_report(
        record=record,
        modelo=modelo,
        revision_id=revision_id,
        filing_year=filing_year,
        period=period,
    )
    if not report.ready:
        missing = tuple(f"{requirement.section_key}.{requirement.field_key}" for requirement in report.missing)
        raise ModeloProfileReadinessError(
            translated_message="application.modelo.errors.profile_readiness_missing",
            context={
                "modelo": modelo,
                "filing_year": filing_year,
                "period": period.registry_token,
                "missing": ", ".join(missing),
            },
            suggestion=f"aeat config profile edit {bucket_id}",
        )
    _require_not_pre_activity_period(
        record=record,
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
    )


def require_existing_profile_baseline_ready_for_modelo_work(
    *,
    bucket_id: str,
    modelo: str,
    filing_year: int,
    period: Period,
    enforce_applicability: bool = True,
) -> None:
    """Refuse plainly incomplete existing profiles before registry work.

    This early gate is used by :func:`aeat.application.modelo.create_work_unit`
    before the registry revision and period are validated. It catches missing
    baseline profile facts, local-work applicability refusals, and pre-activity
    lifecycle periods without requiring a resolvable :class:`ModeloRevision`.
    Missing profiles still pass through so the later full readiness gate can
    raise the canonical missing-profile error.
    """
    try:
        record = UserProfileLifecycleRepository(bucket_id=bucket_id).load(bucket_id)
    except ProfileNotFoundError:
        return
    _require_profile_filing_ready(
        record=record,
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
    )
    if enforce_applicability:
        _require_modelo_applicable_for_local_work(
            record=record,
            bucket_id=bucket_id,
            modelo=modelo,
        )
    _require_not_pre_activity_period(
        record=record,
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
    )


def require_profile_ready_for_work_unit(work_unit: WorkUnit, *, enforce_applicability: bool = True) -> None:
    """Run the profile readiness gate for an existing work unit.

    Calculation, verification, filing, and export services call this wrapper so
    a previously created :class:`aeat.domain.modelos.WorkUnit` is rechecked
    against the current :class:`aeat.domain.user_profile.UserProfileRecord`
    before any filing-grade mutation proceeds.
    """
    require_profile_ready_for_modelo_work(
        bucket_id=work_unit.bucket_id,
        modelo=str(work_unit.modelo),
        revision_id=work_unit.revision_id,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        enforce_applicability=enforce_applicability,
    )


__all__ = [
    "modelo_applicability_refusal",
    "modelo_work_profile_baseline_missing_paths",
    "modelo_work_profile_baseline_validation_issues",
    "modelo_work_profile_preflight_report",
    "pre_activity_period_refusal",
    "require_existing_profile_baseline_ready_for_modelo_work",
    "require_profile_ready_for_modelo_work",
    "require_profile_ready_for_work_unit",
]
