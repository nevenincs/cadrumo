"""Configure synthetic income-tax profile facts through visible installed controls."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .financial_contracts import ProfileFactEntry
from .financial_navigation import _activate_button, _wait_for_refreshed_home
from .installed_tui_child import (
    InstalledTuiChildError,
    public_surface_diagnostic,
    query_public_selector,
    set_profile_manager_field,
    wait_for_public_selector,
)
from .scenario import IncomeTaxScenario

if TYPE_CHECKING:
    pass


def required_profile_facts(scenario: IncomeTaxScenario) -> tuple[ProfileFactEntry, ...]:
    """Return the canonical profile paths required by this income scenario."""
    return (
        ProfileFactEntry("identity.tax_id", value=scenario.taxpayer.tax_id),
        ProfileFactEntry("identity.name", value="Income"),
        ProfileFactEntry("identity.surnames", value="Acceptance"),
        ProfileFactEntry("contact.postcode", value="28001"),
        ProfileFactEntry("tax_residence.ccaa", option_index=13),
        ProfileFactEntry("tax_residence.jurisdiction_scope", option_index=0),
        ProfileFactEntry("censo.activity_start_date", value=scenario.taxpayer.activity_start.isoformat()),
        ProfileFactEntry("taxpayer_type.entity_type", option_index=0),
        ProfileFactEntry("taxpayer_type.fiscal_residency", option_index=0),
        ProfileFactEntry("taxpayer_type.irpf_income_categories", value="actividad_economica"),
        ProfileFactEntry("renta_taxpayer.sex", option_index=1),
        ProfileFactEntry("renta_taxpayer.marital_status", option_index=0),
        ProfileFactEntry("renta_taxpayer.birth_date", value=scenario.taxpayer.birth_date.isoformat()),
        ProfileFactEntry("renta_family.situacion_familiar", option_index=3),
        ProfileFactEntry("irpf.estimation_regime", option_index=0),
        ProfileFactEntry("irpf.special_regime", option_index=0),
        ProfileFactEntry("iva.regime", option_index=0),
        ProfileFactEntry("iva.m303_regime_composition", option_index=0),
        ProfileFactEntry("iva.redeme_enrolled", option_index=1),
        ProfileFactEntry("iva.cash_accounting_regime_enrolled", option_index=1),
        ProfileFactEntry("iva.voluntary_sii_enrolled", option_index=1),
        ProfileFactEntry("iva.hydrocarbon_deposit_advance_payment_deduction_entitled", option_index=1),
        ProfileFactEntry("withholding.has_employees", option_index=1),
        ProfileFactEntry("withholding.pays_professionals_with_retencion", option_index=1),
        ProfileFactEntry("withholding.pays_rent_with_retencion", option_index=1),
        ProfileFactEntry("withholding.pays_capital_income_with_retencion", option_index=1),
        ProfileFactEntry("iva.does_intracomunitario", option_index=1),
        ProfileFactEntry("obligations.third_party_transactions_above_347_threshold", option_index=1),
        ProfileFactEntry("obligations.bienes_extranjero_above_threshold", option_index=1),
        ProfileFactEntry("obligations.monedas_virtuales_extranjero_above_threshold", option_index=1),
        ProfileFactEntry("obligations.premio_loteria_gravamen_especial_sin_retencion", option_index=1),
    )


async def _configure_profile(pilot: Any, *, scenario: IncomeTaxScenario) -> None:
    """Set the required income facts through Profile Manager row-key edits."""
    from textual.widgets import Input

    await pilot.press("f4")
    await wait_for_public_selector(pilot, "#manager-status", polls=180)
    await _activate_button(pilot, "#manager-add-row-activities")
    await wait_for_public_selector(pilot, "#row-input-0")
    query_public_selector(pilot, "#row-input-0", Input).value = "income-tax acceptance activity"
    await _activate_button(pilot, "#btn-row-save")
    await pilot.app.workers.wait_for_complete()
    await wait_for_public_selector(pilot, "#manager-status", polls=180)
    for fact in required_profile_facts(scenario):
        try:
            await set_profile_manager_field(
                pilot=pilot,
                path=fact.path,
                value=fact.value,
                option_index=fact.option_index,
            )
        except InstalledTuiChildError as exc:
            raise InstalledTuiChildError(
                f"installed Profile Manager failed to persist {fact.path}: {exc}",
                diagnostic=public_surface_diagnostic(pilot),
            ) from exc
    await pilot.press("f8")
    await pilot.app.workers.wait_for_complete()
    await pilot.press("escape")
    await _wait_for_refreshed_home(pilot)
