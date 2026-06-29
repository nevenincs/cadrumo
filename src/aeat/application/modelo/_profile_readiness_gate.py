"""Profile readiness gate for filing-grade modelo work.

Loads the active :class:`UserProfileRecord`, builds a
:class:`ProfilePreflightReport`, projects local-work applicability through
:class:`TaxpayerProfile`, and raises :class:`ModeloProfileReadinessError`
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
from ...core.parsing import parse_iso8601_date
from ...core.resources import resources
from ...domain.calculations.registry import ApplicabilityVerdict, RegistrySnapshotError, derive_modelo_applicability
from ...domain.deadlines import (
    EntityType,
    FiscalResidency,
    IrpfEstimationRegime,
    IrpfIncomeCategory,
    IVARegime,
    LegalEntityForm,
    TaxpayerProfile,
)
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
_LOCAL_WORK_APPLICABILITY_MODELOS = frozenset({Modelo.M200.value, Modelo.M202.value})
_FILING_BASELINE_PROFILE_PATHS = ("identity.tax_id", "activities.description")
_BLOCKING_APPLICABILITY_VERDICTS = frozenset(
    {
        ApplicabilityVerdict.NOT_APPLICABLE,
        ApplicabilityVerdict.ATTRIBUTION_PASS_THROUGH,
    },
)


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


def _local_work_taxpayer_profile(record: UserProfileRecord) -> TaxpayerProfile:
    """Project a :class:`UserProfileRecord` into the :class:`TaxpayerProfile` applicability model."""
    values = record_to_path_values(record)
    entity_type = values.get("taxpayer_type.entity_type")
    legal_entity_form = values.get("taxpayer_type.legal_entity_form")
    income_categories = tuple(
        token.strip()
        for token in values.get("taxpayer_type.irpf_income_categories", "").split(",")
        if token.strip()
    )
    estimation_regime = values.get("irpf.estimation_regime")
    fiscal_residency = values.get("taxpayer_type.fiscal_residency")
    iva_regime = values.get("iva.regime", IVARegime.GENERAL.value).strip().upper().replace("-", "_")
    return TaxpayerProfile(
        tax_id=values.get("identity.tax_id", "00000000T"),
        entity_type=EntityType(entity_type) if entity_type else None,
        legal_entity_form=LegalEntityForm(legal_entity_form) if legal_entity_form else None,
        irpf_income_categories=frozenset(IrpfIncomeCategory(token) for token in income_categories),
        irpf_estimation_regime=IrpfEstimationRegime(estimation_regime) if estimation_regime else None,
        iva_regime=IVARegime(iva_regime),
        fiscal_residency=FiscalResidency(fiscal_residency) if fiscal_residency else None,
        country_of_fiscal_residence=values.get("taxpayer_type.country_of_fiscal_residence") or None,
        representante_fiscal_nif=values.get("taxpayer_type.representante_fiscal_nif") or None,
        representante_fiscal_nombre=values.get("taxpayer_type.representante_fiscal_nombre") or None,
    )


def modelo_applicability_refusal(
    *,
    record: UserProfileRecord,
    bucket_id: str,
    modelo: str,
) -> tuple[str, dict[str, str]] | None:
    """Return the local-work applicability refusal for a target, if any.

    Args:
        record: Active :class:`UserProfileRecord` projected into taxpayer facts
            for the modelo applicability check.
        bucket_id: Active profile bucket identifier included in the refusal
            context.
        modelo: Modelo code being checked.
    """
    modelo_code = modelo.strip()
    if modelo_code not in _LOCAL_WORK_APPLICABILITY_MODELOS:
        return None
    profile = _local_work_taxpayer_profile(record)
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
        record: Active :class:`UserProfileRecord` carrying the profile facts
            used to resolve ``censo.activity_start_date``.
        bucket_id: Active profile bucket identifier included in the refusal
            context.
        modelo: Modelo code being checked.
        filing_year: Filing year for the target period.
        period: Target :class:`Period` whose date span is compared against the
            profile activity-start date.
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
    _require_modelo_applicable_for_local_work(
        record=record,
        bucket_id=bucket_id,
        modelo=modelo,
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
    "modelo_applicability_refusal",
    "pre_activity_period_refusal",
    "require_profile_ready_for_modelo_work",
    "require_profile_ready_for_work_unit",
]
