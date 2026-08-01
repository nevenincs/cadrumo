"""Profile-status projection and the active-profile to ``TaxpayerProfile`` bridge.

``build_wizard_status`` projects the active workflow state into a
strict :class:`WizardStatusReport` consumed by the config repair surface
and the ``aeat config profile status`` command. ``load_active_taxpayer_profile``
is the typed bridge the deadline engine and the filing runtime call
to obtain an ``TaxpayerProfile`` from the active profile bucket.
"""

from __future__ import annotations

from pydantic import BaseModel

from ...core import STRICT_FROZEN_CONFIG, resolve_active_bucket_id
from ...domain.deadlines import TaxpayerProfile
from ..state_projection import build_auth_readiness
from ..user_profile import (
    iva_regime_required,
    list_profile_key_records,
    projection_for_taxpayer,
    record_to_path_values,
    validate_profile_values,
)
from ..workflow import WorkflowState
from . import _compiler as _compiler  # side-effect: registers PROFILE_KEYS before _keys_validation
from ._errors import WizardError

_ENROLMENT_KEY = "iva.regime"
"""Profile key whose presence flips an IVA-liable operator profile into
``ready-to-file``.

Natural-person profiles without economic-activity income do not need this
fact to be ready: they are not silently enrolled into a Modelo 303 path.
"""


class WizardStatusReport(BaseModel):
    """Readiness summary for the active configuration profile.

    Surfaces both the structural readiness (identity-required keys
    present) and the enrolment readiness (IVA regime declared) so the
    config repair's profile + auth checks can render a precise
    ``next_action`` for the operator. The semantic shape is the
    contract that the repair renderer reads from.
    """

    model_config = STRICT_FROZEN_CONFIG

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

    ``profile_ready`` is true only when the registry-required keys
    (identity) are present and, when the taxpayer shape requires IVA
    enrolment, the IVA regime is also present. A natural-person
    non-activity profile must not be blocked on a regime declaration it
    does not need.
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
        enrolment_required = iva_regime_required(values)
        enrolment_value = (values.get(_ENROLMENT_KEY) or "").strip()
        enrolment_ready = not enrolment_required or bool(enrolment_value)
        if enrolment_required and not enrolment_ready:
            missing_enrolment = (_ENROLMENT_KEY,)

    profile_ready = identity_ready and enrolment_ready

    # Project the auth fields from the canonical readiness authority rather
    # than reading state.auth directly. Copying the persisted selector
    # verbatim republishes an unrecognised provider as though it were a real
    # one, and treating any non-null authenticated_at as readiness reports a
    # session for a provider that cannot be used -- a certificate selection
    # whose certificate is gone reads as "session ready". The canonical
    # projection fails closed on both counts and does not expose the raw
    # invalid selector.
    auth_readiness = build_auth_readiness(
        state,
        provider_kind=None,
        provider_kind_is_authoritative=False,
        requested_provider=None,
        probe_live_backend=False,
        credential_bucket_id=None,
        certificate_credentials=None,
    )
    auth_provider = auth_readiness.provider
    login_ready = auth_readiness.authenticated
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

    The bridge runs the active profile record through the canonical
    user-profile taxpayer projection, which in turn builds the
    ``TaxpayerProfile`` consumed by the deadline engine and filing runtime.
    Values come from the profile bucket selected by the workflow state.

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
    if not values.get("identity.tax_id"):
        raise WizardStatusError(
            translated_message="application.wizard.status.errors.missing_tax_id",
            context={"active_profile": resolve_active_bucket_id()},
        )
    return projection_for_taxpayer(record)


__all__ = [
    "WizardStatusError",
    "WizardStatusReport",
    "build_wizard_status",
    "load_active_taxpayer_profile",
]
