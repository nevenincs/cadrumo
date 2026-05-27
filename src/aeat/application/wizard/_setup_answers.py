"""Typed answer projection for the ``setup`` wizard flow.

Each question in the ``setup`` flow maps one-to-one to a field on
:class:`SetupAnswers`. Cross-field invariants (spouse fields required
when taxation type is joint, EU/EEA country required when spouse
is EU/EEA-resident) live as model validators.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ...domain.deadlines._models import (
    EntityType,
    IrpfEstimationRegime,
    IrpfIncomeCategory,
    IrpfSpecialRegime,
    IVARegime,
    LegalEntityForm,
)
from ...domain.profile import RentaDeclaracionType, RentaDisabilityGrade, RentaMaritalStatus, RentaSexCode, SituacionFamiliar
from ...domain.profile._ccaa import CCAA


class SetupAnswers(BaseModel):
    """Typed answers collected by the ``setup`` flow."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    # ── profile identity ─────────────────────────────────────────────────
    tax_id: str = Field(min_length=1)
    name: str = ""
    surnames: str = ""
    activity: str = ""
    """Free-text actividad económica / epígrafe IAE description.

    Optional: only a taxpayer that carries on an economic activity (a
    legal entity, or a natural person who declared the
    ``actividad_economica`` IRPF income category) is asked for it. A
    pure landlord, a salaried-only taxpayer, and a pensioner have no
    actividad económica and leave it blank."""
    address_postcode: str = ""
    activity_start_date: str = ""
    """Optional ISO-8601 census alta date for the economic activity.

    When set, the deadline engine suppresses any filing obligation
    whose AEAT window closes before this date — a taxpayer owes no
    return for a period that precedes their registration. Blank for
    every profile that has not declared an alta date; the deadline
    behaviour is then unchanged. The typed ``date`` projection lives
    on :class:`~aeat.domain.deadlines.TaxpayerProfile`."""
    taxation_type: RentaDeclaracionType | str = ""
    output_language: str = "es"

    # ── taxpayer type (three-axis taxpayer model) ────────────────────────
    entity_type: EntityType | str = ""
    legal_entity_form: LegalEntityForm | str = ""
    incn_prior_12_months: str = ""
    """Optional INCN (importe neto de la cifra de negocios) of the
    prior 12 months as a canonical decimal string.

    Gates the Modelo 202 pago-fraccionado modality split at the
    6.000.000 EUR threshold (LIS Art. 40.3). Blank when the operator
    has not declared the figure; downstream the engine returns
    INCOMPLETE rather than guessing. The typed ``Decimal`` projection
    lives on :class:`~aeat.domain.deadlines.TaxpayerProfile`."""
    new_entity_first_two_profit_periods: bool | str = ""
    """Optional three-state bool flagging the LIS Art. 29
    first-two-profit-making-periods state of a newly-created legal
    entity.

    Opts the entity into the 15 percent new-entity rate override; the
    override is opt-in, so an undeclared value (blank string) leaves
    the entity on the otherwise-applicable sub-form rate. Carrying the
    ``str`` arm of the union preserves the absent-vs-false distinction
    that a plain ``bool`` field would collapse, mirroring the
    ``entity_type`` / ``legal_entity_form`` pattern."""
    irpf_income_categories: str = ""
    """Comma-separated set of :class:`IrpfIncomeCategory` tokens, e.g.
    ``"trabajo,pension"``. The CHECKBOX widget produces and the
    persistence layer stores this canonical string; the typed
    ``frozenset`` projection lives on ``TaxpayerProfile``."""

    # ── taxpayer biographic ──────────────────────────────────────────────
    taxpayer_sex: RentaSexCode | str = ""
    taxpayer_marital_status: RentaMaritalStatus | str = ""
    taxpayer_marriage_date: str = ""
    """ISO-8601 date when the current marriage began.

    Optional; only relevant when ``taxpayer_marital_status`` is ``"2"``
    (casado/a).  Used to derive casillas 0245/0246/0247 (matrimonio
    sobrevenido) during profile-binding resolution."""
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
    situacion_familiar: SituacionFamiliar | str = ""
    """Art. 82 LIRPF family situation governing conjunta eligibility.

    Blank when undeclared. The verifier checks this against
    ``taxation_type`` and emits an ERROR when conjunta is requested
    but the declared situation does not permit it (e.g.
    ``pareja_hecho_no_registrada``)."""
    unidad_familiar_descendientes_exclusivos: bool | str = ""
    """In custodia compartida, the progenitor who claims the children
    for the monoparental unidad familiar (Art. 82.1.2° LIRPF second
    indent). Only relevant when ``situacion_familiar`` is
    ``separado_divorciado`` or ``soltero`` and ``taxation_type`` is
    ``"2"``. Blank when undeclared."""

    # ── IVA ──────────────────────────────────────────────────────────────
    iva_regime: IVARegime = IVARegime.GENERAL
    iva_roi_enrolled: bool = False
    iva_oss_enrolled: bool = False
    iva_sii_enrolled: bool = False
    iva_redeme_enrolled: bool = False
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
    irpf_estimation_regime: IrpfEstimationRegime | str = ""
    irpf_special_regime: IrpfSpecialRegime | str = ""
    """IRPF special-regime axis. Blank for the general regime; ``impatriado``
    activates the Ley Beckham path (LIRPF Art. 93)."""
    special_regime_start_date: str = ""
    """ISO-8601 opt-in election date for the special regime. Blank when undeclared."""
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

    @field_validator("entity_type", mode="before")
    @classmethod
    def _parse_entity_type(cls, value: object) -> EntityType | str:
        if value == "":
            return ""
        if isinstance(value, EntityType):
            return value
        if isinstance(value, str):
            return EntityType(value)
        raise TypeError("entity_type must be an EntityType member, string token, or blank")

    @field_validator("legal_entity_form", mode="before")
    @classmethod
    def _parse_legal_entity_form(cls, value: object) -> LegalEntityForm | str:
        if value == "":
            return ""
        if isinstance(value, LegalEntityForm):
            return value
        if isinstance(value, str):
            return LegalEntityForm(value)
        raise TypeError("legal_entity_form must be a LegalEntityForm member, string token, or blank")

    @field_validator("irpf_estimation_regime", mode="before")
    @classmethod
    def _parse_irpf_estimation_regime(cls, value: object) -> IrpfEstimationRegime | str:
        if value == "":
            return ""
        if isinstance(value, IrpfEstimationRegime):
            return value
        if isinstance(value, str):
            return IrpfEstimationRegime(value)
        raise TypeError("irpf_estimation_regime must be an IrpfEstimationRegime member, string token, or blank")

    @field_validator("situacion_familiar", mode="before")
    @classmethod
    def _parse_situacion_familiar(cls, value: object) -> SituacionFamiliar | str:
        if value == "":
            return ""
        if isinstance(value, SituacionFamiliar):
            return value
        if isinstance(value, str):
            return SituacionFamiliar(value)
        raise TypeError("situacion_familiar must be a SituacionFamiliar member, string token, or blank")

    @field_validator("unidad_familiar_descendientes_exclusivos", mode="before")
    @classmethod
    def _parse_unidad_familiar_descendientes_exclusivos(cls, value: object) -> bool | str:
        if value == "":
            return ""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            if value.lower() == "true":
                return True
            if value.lower() == "false":
                return False
        raise TypeError("unidad_familiar_descendientes_exclusivos must be a bool, 'true', 'false', or blank")

    @field_validator("irpf_special_regime", mode="before")
    @classmethod
    def _parse_irpf_special_regime(cls, value: object) -> IrpfSpecialRegime | str:
        if value == "":
            return ""
        if isinstance(value, IrpfSpecialRegime):
            return value
        if isinstance(value, str):
            return IrpfSpecialRegime(value)
        raise TypeError("irpf_special_regime must be an IrpfSpecialRegime member, string token, or blank")

    @field_validator("irpf_income_categories")
    @classmethod
    def _validate_irpf_income_categories(cls, value: str) -> str:
        """Reject any token outside the closed IRPF income-category set.

        The CHECKBOX widget already validates against its choices; this
        re-validates the canonical comma-separated string at the typed
        boundary so a directly-constructed :class:`SetupAnswers` cannot
        carry an unknown category.
        """

        tokens = [token.strip() for token in value.split(",") if token.strip()]
        for token in tokens:
            IrpfIncomeCategory(token)
        return ",".join(tokens)

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

    @field_validator("taxpayer_marriage_date")
    @classmethod
    def _validate_taxpayer_marriage_date(cls, value: str) -> str:
        """Reject a non-ISO marriage date at the typed boundary.

        Optional: a blank string is accepted unchanged.  A non-blank
        value must be a valid ISO-8601 date so the profile binding
        resolver can derive the matrimonio-sobrevenido facts.
        """

        from datetime import date

        if value == "":
            return value
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(
                f"taxpayer_marriage_date must be an ISO-8601 date (YYYY-MM-DD), got {value!r}"
            ) from exc
        return value

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

    @field_validator("incn_prior_12_months")
    @classmethod
    def _validate_incn_prior_12_months(cls, value: str) -> str:
        """Reject a non-decimal INCN at the typed boundary.

        Optional: a blank string is accepted unchanged. A non-blank
        value must parse as a :class:`~decimal.Decimal` so the downstream
        Modelo 202 modality gate can compare it against the
        6.000.000 EUR threshold without re-parsing.
        """

        from decimal import Decimal, InvalidOperation

        if value == "":
            return value
        try:
            Decimal(value)
        except InvalidOperation as exc:
            raise ValueError(
                f"incn_prior_12_months must be a decimal number, got {value!r}"
            ) from exc
        return value

    @field_validator("new_entity_first_two_profit_periods", mode="before")
    @classmethod
    def _parse_new_entity_first_two_profit_periods(cls, value: object) -> bool | str:
        """Coerce raw input into the three-state bool / blank-string union.

        ``""`` represents the undeclared state (no override); ``True``
        and ``False`` are the positively-declared states. Any other
        scalar is rejected at the typed boundary.
        """

        if value == "" or value is None:
            return ""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            token = value.strip().lower()
            if token == "":
                return ""
            if token in {"true", "1", "yes", "y", "si", "sí"}:
                return True
            if token in {"false", "0", "no", "n"}:
                return False
        raise ValueError(
            "new_entity_first_two_profit_periods must be a boolean, blank, "
            "or a recognised canonical token"
        )

    @field_validator("activity_start_date")
    @classmethod
    def _validate_activity_start_date(cls, value: str) -> str:
        """Reject a non-ISO census alta date at the typed boundary.

        The field is optional: a blank string is accepted unchanged. A
        non-blank value must be a valid ISO-8601 date so the deadline
        engine's pre-registration gate receives a parseable date.
        """

        from datetime import date

        if value == "":
            return value
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(
                f"activity_start_date must be an ISO-8601 date (YYYY-MM-DD), got {value!r}"
            ) from exc
        return value

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
