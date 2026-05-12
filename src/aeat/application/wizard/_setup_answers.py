"""Typed answer projection for the ``setup`` wizard flow.

Each question in the ``setup`` flow maps one-to-one to a field on
:class:`SetupAnswers`. Cross-field invariants (spouse fields required
when declaration type is joint, EU/EEA country required when spouse
is EU/EEA-resident) live as model validators.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...domain.deadlines._models import IVARegime
from ...domain.profile._ccaa import CCAA


class SetupAnswers(BaseModel):
    """Typed answers collected by the ``setup`` flow."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    # ── profile identity ─────────────────────────────────────────────────
    tax_id: str = Field(min_length=1)
    name: str = ""
    surnames: str = ""
    activity: str = Field(min_length=1)
    address_postcode: str = ""
    declaration_type: str = ""

    # ── taxpayer biographic ──────────────────────────────────────────────
    taxpayer_sex: str = ""
    taxpayer_marital_status: str = ""
    taxpayer_birth_date: str = ""
    taxpayer_disability_grade: str = ""
    taxpayer_death_date: str = ""

    # ── spouse (declaration_type == "2") ─────────────────────────────────
    spouse_tax_id: str = ""
    spouse_name: str = ""
    spouse_surnames: str = ""
    spouse_birth_date: str = ""
    spouse_sex: str = ""
    spouse_disability_grade: str = ""
    spouse_non_resident_irpf: bool = False
    spouse_eu_eea_resident: bool = False
    spouse_eu_eea_country: str = ""

    # ── family ───────────────────────────────────────────────────────────
    family_descendants_eu_eea_deduction: bool = False
    family_minor_children_in_unit: bool = False

    # ── IVA ──────────────────────────────────────────────────────────────
    iva_regime: IVARegime = IVARegime.GENERAL
    iva_roi_enrolled: bool = False
    iva_oss_enrolled: bool = False
    iva_intracommunity_operations_exceed_50000_eur: bool = False

    # ── enrollment ───────────────────────────────────────────────────────
    enrollment_large_company: bool = False
    enrollment_public_administration_budget_gt_6000000: bool = False

    # ── retencion / declaration booleans ────────────────────────────────
    has_employees: bool = False
    pays_professionals_with_retencion: bool = False
    professional_income_withholding_ge_70pct: bool = False
    pays_rent_with_retencion: bool = False
    pays_capital_income_with_retencion: bool = False
    uses_objective_estimation_irpf: bool = False
    does_intracomunitario: bool = False
    third_party_transactions_above_347_threshold: bool = False
    bienes_extranjero_above_threshold: bool = False

    # ── residence ────────────────────────────────────────────────────────
    tax_residence_ccaa: CCAA = CCAA.MADRID

    # ── notes ────────────────────────────────────────────────────────────
    notes: str = ""

    @model_validator(mode="after")
    def _validate_spouse_fields_when_joint(self) -> SetupAnswers:
        if self.declaration_type == "2" and not self.spouse_tax_id:
            raise ValueError("spouse_tax_id is required when declaration_type is joint (declaration_type='2')")
        return self

    @model_validator(mode="after")
    def _validate_eu_eea_country_when_resident(self) -> SetupAnswers:
        if self.spouse_eu_eea_resident and not self.spouse_eu_eea_country:
            raise ValueError("spouse_eu_eea_country is required when spouse_eu_eea_resident is true")
        return self


__all__ = ["SetupAnswers"]
