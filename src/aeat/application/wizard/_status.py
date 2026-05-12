"""Profile-status projection and the active-profile to ``AutonomoProfile`` bridge.

``build_wizard_status`` projects the active profile into a strict
record that the ``aeat config status`` renderer consumes.
``load_active_autonomo_profile`` is the typed bridge the deadline
engine and the filing runtime call to obtain an ``AutonomoProfile``
without round-tripping through a JSON envelope on disk.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ...domain.deadlines._models import (
    AutonomoProfile,
    FilingEnrollment,
    FilingIVAProfile,
    IVARegime,
)
from ..workflow._models import WorkflowState
from ._catalogue import SETUP_FLOW
from ._models import WizardFlow
from ._persistence import project_answers
from ._setup_answers import SetupAnswers


class WizardStatusReport(BaseModel):
    """Readiness summary for the active configuration profile."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    active_profile: str | None
    tax_id_present: bool
    activity_present: bool
    iva_regime: str = Field(default="")
    tax_residence_ccaa: str = Field(default="")


def build_wizard_status(flow: WizardFlow, state: WorkflowState) -> WizardStatusReport:
    """Project the active profile into a :class:`WizardStatusReport`."""

    record = state.active_profile_record()
    values: dict[str, str] = dict(record.values) if record is not None else {}
    del flow  # the projection only consumes the canonical-token dict
    return WizardStatusReport(
        active_profile=state.active_profile,
        tax_id_present=bool(values.get("tax.id")),
        activity_present=bool(values.get("activity")),
        iva_regime=values.get("iva.regime", ""),
        tax_residence_ccaa=values.get("tax.residence.ccaa", ""),
    )


def load_active_autonomo_profile(state: WorkflowState) -> AutonomoProfile:
    """Build an :class:`AutonomoProfile` from the active profile values.

    The bridge runs the canonical-token dict through ``project_answers``
    and re-shapes the typed fields onto the ``AutonomoProfile`` record
    consumed by the deadline engine and the filing runtime. Values come
    from the workflow state.

    Raises:
        ValueError: When no profile is active or the active profile
            does not carry a ``tax.id``.
    """

    record = state.active_profile_record()
    if record is None:
        raise ValueError("no active profile configured")
    values: dict[str, str] = dict(record.values)
    typed = project_answers(SETUP_FLOW, values)
    if not isinstance(typed, SetupAnswers):
        raise TypeError("setup flow answers did not project to SetupAnswers")
    if not typed.tax_id:
        raise ValueError("active profile is missing tax.id")
    return AutonomoProfile(
        tax_id=typed.tax_id,
        iva_regime=IVARegime(values.get("iva.regime", IVARegime.GENERAL.value)),
        has_employees=typed.has_employees,
        pays_professionals_with_retencion=typed.pays_professionals_with_retencion,
        professional_income_withholding_ge_70pct=typed.professional_income_withholding_ge_70pct,
        pays_rent_with_retencion=typed.pays_rent_with_retencion,
        pays_capital_income_with_retencion=typed.pays_capital_income_with_retencion,
        uses_objective_estimation_irpf=typed.uses_objective_estimation_irpf,
        does_intracomunitario=typed.does_intracomunitario,
        third_party_transactions_above_347_threshold=typed.third_party_transactions_above_347_threshold,
        bienes_extranjero_above_threshold=typed.bienes_extranjero_above_threshold,
        iva=FilingIVAProfile(
            roi_enrolled=typed.iva_roi_enrolled,
            oss_enrolled=typed.iva_oss_enrolled,
            intracommunity_operations_exceed_50000_eur=typed.iva_intracommunity_operations_exceed_50000_eur,
        ),
        enrollment=FilingEnrollment(
            large_company=typed.enrollment_large_company,
            public_administration_budget_gt_6000000=typed.enrollment_public_administration_budget_gt_6000000,
        ),
        notes=typed.notes,
    )


__all__ = ["WizardStatusReport", "build_wizard_status", "load_active_autonomo_profile"]
