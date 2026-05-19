"""Typed answer projection for the ``setup`` wizard flow.

Each question in the ``setup`` flow maps one-to-one to a field on
:class:`SetupAnswers`. Cross-field invariants (spouse fields required
when taxation type is joint, EU/EEA country required when spouse
is EU/EEA-resident) live as model validators.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ...domain.deadlines._models import IVARegime
from ...domain.profile import RentaDeclaracionType, RentaDisabilityGrade, RentaMaritalStatus, RentaSexCode
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
    taxation_type: RentaDeclaracionType | str = ""
    output_language: str = "es"

    # ── taxpayer biographic ──────────────────────────────────────────────
    taxpayer_sex: RentaSexCode | str = ""
    taxpayer_marital_status: RentaMaritalStatus | str = ""
    taxpayer_birth_date: str = ""
    taxpayer_disability_grade: RentaDisabilityGrade | str = ""
    taxpayer_death_date: str = ""

    # ── spouse (taxation_type == "2") ────────────────────────────────────
    spouse_tax_id: str = ""
    spouse_name: str = ""
    spouse_surnames: str = ""
    spouse_birth_date: str = ""
    spouse_sex: RentaSexCode | str = ""
    spouse_disability_grade: RentaDisabilityGrade | str = ""
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

    # ── retencion / modelo obligation booleans ───────────────────────────
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

    @field_validator("iva_regime", mode="before")
    @classmethod
    def _parse_iva_regime(cls, value: object) -> IVARegime:
        if isinstance(value, IVARegime):
            return value
        if isinstance(value, str):
            return IVARegime(value)
        raise TypeError("iva_regime must be an IVARegime member or string token")

    @field_validator("taxation_type", mode="before")
    @classmethod
    def _parse_taxation_type(cls, value: object) -> RentaDeclaracionType | str:
        if value == "":
            return ""
        if isinstance(value, RentaDeclaracionType):
            return value
        if isinstance(value, str):
            return RentaDeclaracionType(value)
        raise TypeError("taxation_type must be a RentaDeclaracionType member, string token, or blank")

    @field_validator("taxpayer_sex", "spouse_sex", mode="before")
    @classmethod
    def _parse_sex_code(cls, value: object) -> RentaSexCode | str:
        if value == "":
            return ""
        if isinstance(value, RentaSexCode):
            return value
        if isinstance(value, str):
            return RentaSexCode(value)
        raise TypeError("sex code must be a RentaSexCode member, string token, or blank")

    @field_validator("taxpayer_marital_status", mode="before")
    @classmethod
    def _parse_marital_status(cls, value: object) -> RentaMaritalStatus | str:
        if value == "":
            return ""
        if isinstance(value, RentaMaritalStatus):
            return value
        if isinstance(value, str):
            return RentaMaritalStatus(value)
        raise TypeError("taxpayer_marital_status must be a RentaMaritalStatus member, string token, or blank")

    @field_validator("taxpayer_disability_grade", "spouse_disability_grade", mode="before")
    @classmethod
    def _parse_disability_grade(cls, value: object) -> RentaDisabilityGrade | str:
        if value == "":
            return ""
        if isinstance(value, RentaDisabilityGrade):
            return value
        if isinstance(value, str):
            return RentaDisabilityGrade(value)
        raise TypeError("disability grade must be a RentaDisabilityGrade member, string token, or blank")

    @field_validator("tax_residence_ccaa", mode="before")
    @classmethod
    def _parse_tax_residence_ccaa(cls, value: object) -> CCAA:
        if isinstance(value, CCAA):
            return value
        if isinstance(value, str):
            return CCAA(value)
        raise TypeError("tax_residence_ccaa must be a CCAA member or string token")

    @field_validator("output_language")
    @classmethod
    def _validate_output_language(cls, value: str) -> str:
        from ...core.i18n import SUPPORTED_OUTPUT_LANGUAGES

        if value not in SUPPORTED_OUTPUT_LANGUAGES:
            valid = ", ".join(SUPPORTED_OUTPUT_LANGUAGES)
            raise ValueError(f"output_language must be one of: {valid}")
        return value

    @model_validator(mode="after")
    def _validate_spouse_fields_when_joint(self) -> SetupAnswers:
        if self.taxation_type == RentaDeclaracionType.JOINT and not self.spouse_tax_id:
            raise ValueError("spouse_tax_id is required when taxation_type is joint (taxation_type='2')")
        return self

    @model_validator(mode="after")
    def _validate_eu_eea_country_when_resident(self) -> SetupAnswers:
        if self.spouse_eu_eea_resident and not self.spouse_eu_eea_country:
            raise ValueError("spouse_eu_eea_country is required when spouse_eu_eea_resident is true")
        return self


__all__ = ["SetupAnswers"]
