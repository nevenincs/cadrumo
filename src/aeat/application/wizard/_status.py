"""Profile-status projection and the active-profile to ``TaxpayerProfile`` bridge.

``build_wizard_status`` projects the active workflow state into a
strict :class:`WizardStatusReport` consumed by the config repair surface
and the ``aeat config profile status`` command. ``load_active_taxpayer_profile``
is the typed bridge the deadline engine and the filing runtime call
to obtain an ``TaxpayerProfile`` from the active profile bucket.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, ValidationError

from ...core import resolve_active_bucket_id
from ...core.setup_answers import SetupAnswers
from ...domain.deadlines._models import (
    IVARegime,
    ModeloEnrollment,
    ModeloIVAProfile,
    TaxpayerProfile,
)
from ..user_profile._keys_validation import list_profile_key_records, validate_profile_values
from ..user_profile._projections import record_to_path_values
from ..workflow._models import WorkflowState
from . import _compiler as _compiler  # side-effect: registers PROFILE_KEYS before _keys_validation
from ._catalogue import SETUP_FLOW
from ._errors import WizardError
from ._persistence import project_answers

_ENROLMENT_KEY = "iva.regime"
"""Profile key whose presence flips the operator profile from ``identity-only``
into ``ready-to-file``. Without an IVA regime declared, the deadline engine
cannot compute IVA obligations, so ``profile_ready`` must NOT report ``true``."""


class WizardStatusReport(BaseModel):
    """Readiness summary for the active configuration profile.

    Surfaces both the structural readiness (identity-required keys
    present) and the enrolment readiness (IVA regime declared) so the
    config repair's profile + auth checks can render a precise
    ``next_action`` for the operator. The semantic shape is the
    contract that the repair renderer reads from.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    active_profile: str | None
    profile_ready: bool
    identity_ready: bool = False
    enrolment_ready: bool = False
    missing_required: tuple[str, ...] = ()
    missing_enrolment: tuple[str, ...] = ()
    profile_present_keys: int
    profile_total_keys: int
    auth_provider: str
    login_ready: bool
    next_action: str


class WizardStatusError(WizardError):
    """Raised when the wizard status projection cannot resolve the active profile."""


def build_wizard_status(state: WorkflowState) -> WizardStatusReport:
    """Return the :class:`WizardStatusReport` readiness for the current workflow state.

    ``profile_ready`` is true only when both the registry-required keys
    (identity) AND the deadline-engine enrolment key (IVA regime) are
    present. A profile carrying just the identity keys is recognised
    as identity-ready but never as profile-ready, because the deadline
    engine cannot compute IVA obligations without a regime declaration.
    """
    record = state.active_profile_record()
    identity_ready = False
    missing_required: tuple[str, ...] = ()
    profile_present_keys = 0
    profile_total_keys = len(list_profile_key_records())
    enrolment_ready = False
    missing_enrolment: tuple[str, ...] = ()
    if record is not None:
        values = record_to_path_values(record)
        validation = validate_profile_values(values)
        identity_ready = validation.valid
        missing_required = validation.missing_required
        profile_present_keys = validation.present_keys
        profile_total_keys = validation.total_keys
        enrolment_value = (values.get(_ENROLMENT_KEY) or "").strip()
        enrolment_ready = bool(enrolment_value)
        if not enrolment_ready:
            missing_enrolment = (_ENROLMENT_KEY,)

    profile_ready = identity_ready and enrolment_ready

    auth_provider = state.auth.provider or ""
    login_ready = state.auth.authenticated_at is not None
    return WizardStatusReport(
        active_profile=resolve_active_bucket_id(),
        profile_ready=profile_ready,
        identity_ready=identity_ready,
        enrolment_ready=enrolment_ready,
        missing_required=missing_required,
        missing_enrolment=missing_enrolment,
        profile_present_keys=profile_present_keys,
        profile_total_keys=profile_total_keys,
        auth_provider=auth_provider,
        login_ready=login_ready,
        next_action=_next_wizard_action(
            has_profile=record is not None,
            missing_required=missing_required,
            missing_enrolment=missing_enrolment,
            auth_provider=auth_provider,
            login_ready=login_ready,
        ),
    )


def _next_wizard_action(
    *,
    has_profile: bool,
    missing_required: tuple[str, ...],
    missing_enrolment: tuple[str, ...],
    auth_provider: str,
    login_ready: bool,
) -> str:
    if not has_profile:
        return "aeat config profile create NAME"
    if missing_required:
        return "aeat config profile edit NAME"
    if missing_enrolment:
        return "aeat config profile edit NAME"
    if not auth_provider:
        return "aeat config auth configure --provider certificate --file PATH"
    if not login_ready:
        return f"aeat config auth test --provider {auth_provider}"
    return "aeat app overview status"


def load_active_taxpayer_profile(state: WorkflowState) -> TaxpayerProfile:
    """Build an :class:`TaxpayerProfile` from the active profile values.

    The bridge runs the canonical-token dict through ``project_answers``
    and re-shapes the typed fields onto the ``TaxpayerProfile`` record
    consumed by the deadline engine and the filing runtime. Values come
    from the profile bucket selected by the workflow state.

    Args:
        state: The current :class:`WorkflowState` from which the active
            profile record is resolved.

    Returns:
        A :class:`TaxpayerProfile` populated from the active profile's
        canonical answer values.

    Raises:
        WizardStatusError: When no profile is active or the active
            profile does not carry a ``tax.id``.
    """
    record = state.active_profile_record()
    if record is None:
        raise WizardStatusError(
            translated_message="application.wizard.status.errors.no_active_profile",
            context={"workflow_state": "no_active_profile"},
        )
    values: dict[str, str] = dict(record_to_path_values(record))
    try:
        typed = project_answers(SETUP_FLOW, values)
    except ValidationError as exc:
        raise WizardStatusError(
            translated_message="application.wizard.status.errors.projection_failed",
            context={"active_profile": resolve_active_bucket_id(), "errors": exc.error_count()},
        ) from exc
    if not isinstance(typed, SetupAnswers):
        raise WizardStatusError(
            translated_message="application.wizard.status.errors.unexpected_projection_type",
            context={"flow_id": SETUP_FLOW.id, "projection_type": type(typed).__name__},
        )
    if not typed.tax_id:
        raise WizardStatusError(
            translated_message="application.wizard.status.errors.missing_tax_id",
            context={"active_profile": resolve_active_bucket_id()},
        )
    return TaxpayerProfile(
        tax_id=typed.tax_id,
        iva_regime=IVARegime(
            values.get("iva.regime", IVARegime.GENERAL.value),
        ),  # iva.regime path unchanged in canonical schema
        has_employees=typed.has_employees,
        pays_professionals_with_retencion=typed.pays_professionals_with_retencion,
        professional_income_withholding_ge_70pct=typed.professional_income_withholding_ge_70pct,
        pays_rent_with_retencion=typed.pays_rent_with_retencion,
        pays_capital_income_with_retencion=typed.pays_capital_income_with_retencion,
        uses_objective_estimation_irpf=typed.uses_objective_estimation_irpf,
        does_intracomunitario=typed.does_intracomunitario,
        third_party_transactions_above_347_threshold=typed.third_party_transactions_above_347_threshold,
        bienes_extranjero_above_threshold=typed.bienes_extranjero_above_threshold,
        iva=ModeloIVAProfile(
            roi_enrolled=typed.iva_roi_enrolled,
            oss_enrolled=typed.iva_oss_enrolled,
            intracommunity_operations_exceed_50000_eur=typed.iva_intracommunity_operations_exceed_50000_eur,
        ),
        enrollment=ModeloEnrollment(
            large_company=typed.enrollment_large_company,
            public_administration_budget_gt_6000000=typed.enrollment_public_administration_budget_gt_6000000,
        ),
        notes=typed.notes,
    )


__all__ = [
    "WizardStatusError",
    "WizardStatusReport",
    "build_wizard_status",
    "load_active_taxpayer_profile",
]
