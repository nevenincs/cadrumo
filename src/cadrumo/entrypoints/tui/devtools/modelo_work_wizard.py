"""The live Modelo work-wizard development surface.

This devtool creates a real, Modelo-capable profile and work unit through the
public application contracts, then asks the canonical application wizard
factory for the flow definition. The full-screen app is only the renderer;
registry discovery and run-scoped copy ownership stay with
``application.modelo.work_wizard``.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

from ....application.modelo import ensure_modelo_work_unit_for_active_target
from ....application.modelo.work_wizard import ModeloWorkWizardRun, open_modelo_work_wizard
from ....core import Period
from ....core.flows import FlowMode
from ....domain.user_profile import UserProfileFact
from ..flows.app import FlowTuiApp
from ._fixture import harness_storage, passphrase

if TYPE_CHECKING:
    from ....domain.modelos import WorkUnit

_MODELO = "130"
_FILING_YEAR = 2025
_PERIOD_CODE = "1T"
_MODEL_WORK_PROFILE_FACTS = (
    UserProfileFact(path="preferences.output_language", value="es"),
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
    from ....application.user_profile import login_profile, register_profile_with_credentials
    from ....application.user_profile.manager_projection import persist_active_profile_manager_field
    from ....application.workflow import list_profile_buckets

    profiles = list_profile_buckets()
    if profiles:
        bucket_id = next(iter(profiles))
        login_profile(name=bucket_id, passphrase_callback=lambda *_args, **_kwargs: passphrase())
    else:
        outcome = register_profile_with_credentials(
            label="Modelo Work Wizard",
            passphrase=passphrase(),
            facts=_MODEL_WORK_PROFILE_FACTS,
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
        )
        bucket_id = outcome.bucket_id
    for fact in _MODEL_WORK_PROFILE_FACTS:
        value = str(fact.value).lower() if isinstance(fact.value, bool) else str(fact.value)
        persist_active_profile_manager_field(fact.path, value)
    return bucket_id


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
    )
    return result.work_unit


@contextmanager
def provision_modelo_work_wizard() -> Iterator[str]:
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
