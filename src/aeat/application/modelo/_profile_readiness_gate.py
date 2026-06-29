"""Profile readiness gate for filing-grade modelo work.

Loads the active :class:`UserProfileRecord`, builds a
:class:`ProfilePreflightReport`, and raises :class:`ModeloProfileReadinessError`
before filing-grade work proceeds when required profile facts are missing. The
same gate also refuses Modelo 130 and Modelo 303 target periods whose date span
ends before the profile's ``censo.activity_start_date``; those pre-activity
periods have no filing obligation and must not produce stale work, calculation,
verification, filing, or export state.

See Also:
    :func:`require_profile_ready_for_work_unit`:
        Replays the same readiness checks for an existing :class:`WorkUnit`.
    :class:`ProfilePreflightReport`:
        User-profile preflight result consumed by this application gate.
"""

from __future__ import annotations

from datetime import date

from ...core import Modelo, Period
from ...core.resources import resources
from ...domain.calculations.registry import RegistrySnapshotError
from ...domain.modelos._work_unit import WorkUnit
from ...domain.user_profile import ProfileNotFoundError, UserProfileRecord
from ..user_profile import (
    ProfilePreflightReport,
    ProfileValidationService,
    UserProfileLifecycleRepository,
    record_to_path_values,
)
from ..user_profile._preflight import ProfilePreflightService
from ._action_errors import ModeloProfileReadinessError

_PROFILE_ACTIVITY_START_PATH = "censo.activity_start_date"
_PRE_ACTIVITY_LIFECYCLE_MODELOS = frozenset({Modelo.M130.value, Modelo.M303.value})
_FILING_BASELINE_PROFILE_PATHS = ("identity.tax_id", "activities.description")


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
                return date.fromisoformat(fact.value.strip())
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
    modelo_code = modelo.strip()
    if modelo_code not in _PRE_ACTIVITY_LIFECYCLE_MODELOS or not period.has_date_span():
        return
    activity_start_date = _profile_activity_start_date(record)
    if activity_start_date is None:
        return
    period_end_date = period.end_date
    if period_end_date >= activity_start_date:
        return
    raise ModeloProfileReadinessError(
        (
            f"Modelo {modelo_code} {filing_year} {period.registry_token} is before the profile "
            f"activity-start date {activity_start_date.isoformat()}; the filing period ends on "
            f"{period_end_date.isoformat()}, so no Modelo {modelo_code} work unit, calculation, or verification "
            "may proceed for this pre-activity period."
        ),
        context={
            "bucket_id": bucket_id,
            "modelo": modelo_code,
            "filing_year": filing_year,
            "period": period.registry_token,
            "activity_start_date": activity_start_date.isoformat(),
            "period_end_date": period_end_date.isoformat(),
        },
        suggestion=f"aeat config profile edit {bucket_id}",
    )


def _require_profile_filing_ready(
    *,
    record: UserProfileRecord,
    bucket_id: str,
    modelo: str,
    filing_year: int,
    period: Period,
) -> None:
    values = record_to_path_values(record)
    missing: list[str] = [path for path in _FILING_BASELINE_PROFILE_PATHS if not values.get(path, "").strip()]
    validation = ProfileValidationService(schema=resources().user_profile_schema.singleton).validate_record(record)
    for issue in validation.issues:
        if issue.severity.value != "error":
            continue
        path = issue.path or issue.code
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
) -> None:
    """Refuse filing-grade modelo work when the active profile is not eligible.

    Loads the bucket's :class:`UserProfileRecord`, evaluates modelo-specific
    profile requirements through :class:`ProfilePreflightReport`, and then
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
    report = _report_for_target(
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


def require_profile_ready_for_work_unit(work_unit: WorkUnit) -> None:
    """Run the profile readiness gate for an existing :class:`WorkUnit`.

    Calculation, verification, filing, and export services call this wrapper so
    a previously created work unit is rechecked against the current
    :class:`UserProfileRecord` before any filing-grade mutation proceeds.
    """
    require_profile_ready_for_modelo_work(
        bucket_id=work_unit.bucket_id,
        modelo=str(work_unit.modelo),
        revision_id=work_unit.revision_id,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
    )


__all__ = [
    "require_profile_ready_for_modelo_work",
    "require_profile_ready_for_work_unit",
]
