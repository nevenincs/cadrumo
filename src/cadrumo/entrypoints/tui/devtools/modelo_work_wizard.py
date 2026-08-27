"""The live Modelo work-wizard development surface.

This devtool creates a real, Modelo-capable profile and work unit through the
public application contracts, then asks the canonical application wizard
factory for the flow definition. The full-screen app is only the renderer;
registry discovery and run-scoped copy ownership stay with
``application.modelo.work_wizard``.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

from ....application.modelo.work_addressing import ensure_modelo_work_unit_for_active_target
from ....application.modelo.work_wizard import ModeloWorkWizardRun, open_modelo_work_wizard
from ....core import Modelo, Period
from ....core.flows import FlowMode
from ....core.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from ....domain.user_profile.values import UserProfileFact
from ..flows.app import FlowTuiApp
from ..launcher import load_modelo_work_unit_catalogue
from .fixture import harness_storage, passphrase

if TYPE_CHECKING:
    from ....domain.modelos import WorkUnit

_MODELO = Modelo.M130.value
_FILING_YEAR = 2025
_PERIOD_CODE = "1T"
_PROFILE_LABEL = "Modelo Work Wizard fixture"
_MODEL_WORK_PROFILE_FACTS = (
    UserProfileFact(path=PROFILE_OUTPUT_LANGUAGE_PATH, value="es"),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="identity.tax_id", value="12345678Z"),
    UserProfileFact(path="identity.name", value="Operator"),
    UserProfileFact(path="identity.surnames", value="Wizard"),
    UserProfileFact(path="activities.description", value="design"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="iva.m303_regime_composition", value="general"),
    UserProfileFact(path="iva.redeme_enrolled", value=False),
    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
    UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
    UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
    UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
    UserProfileFact(path="censo.activity_start_date", value="2025-01-01"),
)
_ACTIVE_WIZARD: ContextVar[ModeloWorkWizardRun | None] = ContextVar("active_modelo_work_wizard", default=None)


def _ensure_modelo_work_profile() -> str:
    """Return an unlocked harness profile with the full M130 readiness facts."""
    from cadrumo.application.workflow.profile_bucket_scan import list_profile_buckets

    from ....application.user_profile.login_session import login_profile
    from ....application.user_profile.registration import register_profile_with_credentials

    existing = next(
        (pointer for pointer in list_profile_buckets().values() if pointer.label == _PROFILE_LABEL),
        None,
    )
    if existing is not None:
        bucket_id = existing.bucket_id
    else:
        outcome = register_profile_with_credentials(
            label=_PROFILE_LABEL,
            passphrase=passphrase(),
            facts=_MODEL_WORK_PROFILE_FACTS,
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
        )
        bucket_id = outcome.bucket_id

    # Both branches log in, not just the resuming one. Reading or promoting a
    # committed profile capsule needs an authenticated session, and a freshly
    # registered profile does not carry one that satisfies that door.
    login_profile(name=bucket_id, passphrase_callback=lambda *_args, **_kwargs: passphrase())

    # Registration mints a profile SETUP_INCOMPLETE by design, and every
    # filing-grade modelo gate refuses one. Without this promotion the wizard
    # surface could never open at all -- it failed with
    # `profile_readiness_setup_incomplete` at every terminal size, which is
    # also why the only flow-driven screens in the product went unrendered.
    #
    # Promoted through the real door, which re-applies the complete-profile
    # contract: if the fixture's fact set were ever short of a required field,
    # this refuses rather than publishing a false COMPLETE claim.
    _promote_setup_state(bucket_id)
    return bucket_id


def _promote_setup_state(bucket_id: str) -> None:
    """Mark the harness profile setup-complete, if it is not already."""
    from ....application.user_profile.profile_record_repository import ProfileRecordRepository
    from ....domain.user_profile.values import ProfileSetupState

    profiles = ProfileRecordRepository.for_current_session(bucket_id)
    record = profiles.load(bucket_id)
    if record.setup_state is ProfileSetupState.COMPLETE:
        return
    profiles.complete_setup(
        bucket_id,
        expected_revision=record.record_revision,
        expected_content_digest=record.content_digest,
    )


def _ensure_modelo_work_unit(bucket_id: str) -> WorkUnit:
    """Resume or create the live M130 work unit through the application door."""
    period = Period.from_year_and_code(_FILING_YEAR, _PERIOD_CODE)
    result = ensure_modelo_work_unit_for_active_target(
        bucket_id=bucket_id,
        modelo=_MODELO,
        filing_year=_FILING_YEAR,
        period=period,
        registry_revision_id=None,
        actor="tui-devtools",
        catalogue=load_modelo_work_unit_catalogue(bucket_id),
    )
    return result.work_unit


@contextmanager
def provision_modelo_work_wizard() -> Generator[str]:
    """Provision the real work unit and hold its canonical copy run open."""
    with harness_storage(namespace="modelo-work-wizard"):
        bucket_id = _ensure_modelo_work_profile()
        unit = _ensure_modelo_work_unit(bucket_id)
        with open_modelo_work_wizard(unit) as wizard:
            token = _ACTIVE_WIZARD.set(wizard)
            try:
                yield bucket_id
            finally:
                _ACTIVE_WIZARD.reset(token)


def build_modelo_work_wizard() -> FlowTuiApp:
    """Build the installed renderer over the provisioned canonical wizard run."""
    wizard = _ACTIVE_WIZARD.get()
    if wizard is None:
        raise RuntimeError("modelo-work-wizard surface requires its provisioned run")
    return FlowTuiApp(wizard.definition_for(), mode=FlowMode.CREATE)


__all__ = ["build_modelo_work_wizard", "provision_modelo_work_wizard"]
