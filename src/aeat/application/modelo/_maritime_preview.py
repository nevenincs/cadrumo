"""Application service for the modelo maritime exemption preview.

This module uses :class:`MaritimeWorkerFacts`, :class:`ModeloMaritimeExemptionPreview`,
and :class:`ProfileCompletenessError` for the maritime exemption preview.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Literal, cast

from ...application.calculations import resolve_maritime_exemption
from ...application.calculations._maritime_exemption_service import MaritimeExemptionResult
from ...application.user_profile import fact_value
from ...application.workflow import workflow_state_repository
from ...domain.renta import MaritimeWorkerFacts, ProfileCompletenessError


@dataclass(frozen=True)
class ModeloMaritimeExemptionPreview:
    """Resolved maritime exemption preview for the active profile."""

    facts: MaritimeWorkerFacts
    result: MaritimeExemptionResult
    retmar_warning_error: ProfileCompletenessError | None = None


def maritime_facts_from_active_profile() -> MaritimeWorkerFacts:
    """Read maritime worker facts off the active profile record and return a :class:`MaritimeWorkerFacts`."""
    state = workflow_state_repository().load()
    record = state.active_profile_record()

    def _raw(path: str) -> str | None:
        raw = fact_value(record, path)
        return raw.strip() if raw else None

    def _bool(path: str) -> bool:
        raw = fact_value(record, path)
        if raw is None:
            return False
        return raw.strip().lower() in {"true", "1", "yes"}

    # fact_value() returns unvalidated str from encrypted profile storage.
    # Each Literal field on MaritimeWorkerFacts carries a closed value set;
    # membership tests below narrow the runtime value and cast bridges the
    # str→Literal narrowing that ty cannot express from a membership test.
    # This is a genuine profile-storage adapter boundary.
    _vf_raw = _raw("maritime_worker.vessel_flag")
    # CAST-RATIONALE-MARITIME-LITERAL-FIELD: str->Literal narrowing at profile-storage boundary.
    vessel_flag = cast(
        "Literal['ES', 'foreign'] | None",
        _vf_raw if _vf_raw in ("ES", "foreign") else None,
    )
    _wt_raw = _raw("maritime_worker.waters_type")
    # CAST-RATIONALE-MARITIME-LITERAL-FIELD: str->Literal narrowing at profile-storage boundary.
    waters_type = cast(
        "Literal['national', 'international'] | None",
        _wt_raw if _wt_raw in ("national", "international") else None,
    )
    _vr_raw = _raw("maritime_worker.vessel_registry")
    # CAST-RATIONALE-MARITIME-LITERAL-FIELD: str->Literal narrowing at profile-storage boundary.
    vessel_registry = cast(
        "Literal['REBECA', 'rebeca_eu_eea', 'scheduled_canary_route'] | None",
        _vr_raw if _vr_raw in ("REBECA", "rebeca_eu_eea", "scheduled_canary_route") else None,
    )
    return MaritimeWorkerFacts(
        worker_class=_raw("maritime_worker.worker_class"),
        vessel_flag=vessel_flag,
        waters_type=waters_type,
        vessel_registry=vessel_registry,
        tuna_fleet=_bool("maritime_worker.tuna_fleet"),
        pending_eu_clearance=_bool("maritime_worker.pending_eu_clearance"),
        retmar_registered=_bool("maritime_worker.retmar_registered"),
    )


def preview_maritime_exemption_for_active_profile(
    *,
    annual_salary: Decimal | None,
    qualifying_days: int | None,
    gross_navigation_income: Decimal | None,
) -> ModeloMaritimeExemptionPreview:
    """Resolve the active profile maritime exemption preview and return a :class:`ModeloMaritimeExemptionPreview`.

    The RETMAR completeness gate is intentionally handled here rather than in
    the CLI transport. RETMAR registration is a non-blocking warning for this
    preview: the service re-runs the legal calculation with that single fact
    cleared so the operator still receives the observation payload.
    """
    facts = maritime_facts_from_active_profile()
    try:
        result = resolve_maritime_exemption(
            facts=facts,
            annual_salary=annual_salary,
            qualifying_days=qualifying_days,
            gross_navigation_income=gross_navigation_income,
        )
    except ProfileCompletenessError as exc:
        facts_without_retmar = replace(facts, retmar_registered=False)
        result = resolve_maritime_exemption(
            facts=facts_without_retmar,
            annual_salary=annual_salary,
            qualifying_days=qualifying_days,
            gross_navigation_income=gross_navigation_income,
        )
        return ModeloMaritimeExemptionPreview(
            facts=facts,
            result=result,
            retmar_warning_error=exc,
        )

    return ModeloMaritimeExemptionPreview(facts=facts, result=result)
