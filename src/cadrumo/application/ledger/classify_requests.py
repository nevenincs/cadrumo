"""Closed request schemas for exact-profile ledger classification."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

from ...core.country_code import CountryCodeAlpha2
from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.parsing.codes import normalise_iso_3166_alpha2_jurisdiction
from ...domain.transactions.enums import BusinessClassification, is_classified
from .actions_common import display_decimal

LEDGER_CLASSIFY_OPERATION_DEFINITION_ID = "ledger.classify.single"

LEDGER_CLASSIFY_PHASE = "ledger.classify.single"

LedgerClassifyPatchField = Literal[
    "business_classification",
    "business_pct",
    "category_id",
    "taxable_base",
    "iva_rate",
    "iva_amount",
    "irpf_category",
    "m210_income_classification",
    "iva_category",
    "deduction_fact_kind",
    "investment_asset_id",
    "counterparty_country",
    "counterparty_identification_state",
    "notes",
]

_CLASSIFY_FIELDS = frozenset(
    {
        "business_classification",
        "business_pct",
        "category_id",
        "taxable_base",
        "iva_rate",
        "iva_amount",
        "irpf_category",
        "m210_income_classification",
        "iva_category",
        "deduction_fact_kind",
        "investment_asset_id",
        "counterparty_country",
        "counterparty_identification_state",
        "notes",
    },
)

_ClassifyFields = Annotated[tuple[LedgerClassifyPatchField, ...], Field(min_length=1, max_length=14)]

LedgerClassifyDecimalText = Annotated[str, Field(min_length=1, max_length=128)]

LedgerClassifyShortText = Annotated[str, Field(max_length=128)]

LedgerClassifyLongText = Annotated[str, Field(max_length=4096)]

LedgerClassifyTransactionPrefix = Annotated[str, Field(min_length=1, max_length=96)]


class LedgerClassifyPatch(BaseModel):
    """Bounded JSON-stable values for the manual classification patch."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    business_classification: Annotated[str, Field(min_length=1, max_length=32)] | None = None
    business_pct: LedgerClassifyDecimalText | None = None
    category_id: LedgerClassifyShortText | None = None
    taxable_base: LedgerClassifyDecimalText | None = None
    iva_rate: LedgerClassifyDecimalText | None = None
    iva_amount: LedgerClassifyDecimalText | None = None
    irpf_category: LedgerClassifyLongText | None = None
    iva_category: LedgerClassifyShortText | None = None
    deduction_fact_kind: LedgerClassifyShortText | None = None
    investment_asset_id: LedgerClassifyShortText | None = None
    counterparty_country: CountryCodeAlpha2 | None = None
    counterparty_identification_state: Annotated[str, Field(max_length=2)] | None = None
    notes: LedgerClassifyLongText | None = None

    @field_validator("business_classification")
    @classmethod
    def _manual_classification_only(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            classification = BusinessClassification(value)
        except ValueError:
            raise ValueError("ledger classify requires a canonical business classification") from None
        if not is_classified(classification):
            raise ValueError("ledger classify cannot assign a pipeline-owned disposition")
        return classification.value

    @field_validator("business_pct", "taxable_base", "iva_rate", "iva_amount")
    @classmethod
    def _canonical_decimal_text(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is None:
            return None
        parsed = try_parse_canonical_decimal(value, signed=False)
        if parsed is None or display_decimal(parsed) != value:
            raise ValueError(f"ledger classify {info.field_name} must use canonical decimal text")
        if info.field_name == "business_pct" and not Decimal("0") <= parsed <= Decimal("1"):
            raise ValueError("ledger classify business_pct must be within 0..1")
        return value

    @field_validator("counterparty_country")
    @classmethod
    def _canonical_country(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalise_iso_3166_alpha2_jurisdiction(value)
        if normalized != value:
            raise ValueError("ledger classify counterparty country must be canonical ISO alpha-2 text")
        return value


class LedgerClassifyM210Options(BaseModel):
    """Bounded string-only representation of the explicit CLI M210 options."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    tipo_renta_code: Annotated[str, Field(max_length=32)] | None = None
    gross_income_amount: LedgerClassifyDecimalText | None = None
    applicable_rate: LedgerClassifyDecimalText | None = None
    payer_mode: Annotated[str, Field(max_length=64)] | None = None
    payer_id: LedgerClassifyShortText | None = None
    asset_or_right_id: LedgerClassifyShortText | None = None

    @field_validator("gross_income_amount", "applicable_rate")
    @classmethod
    def _canonical_m210_decimal(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is None:
            return None
        parsed = try_parse_canonical_decimal(value, signed=False)
        if parsed is None or display_decimal(parsed) != value:
            raise ValueError(f"M210 {info.field_name} must use canonical decimal text")
        if info.field_name == "applicable_rate" and parsed > Decimal("1"):
            raise ValueError("M210 applicable_rate must be within 0..1")
        return value

    @field_validator("payer_id", "asset_or_right_id")
    @classmethod
    def _normalise_optional_identity(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class LedgerClassifyRequest(BaseModel):
    """Exact-profile single-classify request; optional nulls use an explicit mask."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    transaction_id: LedgerClassifyTransactionPrefix
    patch: LedgerClassifyPatch
    patch_fields: _ClassifyFields
    m210: LedgerClassifyM210Options | None = None
    actor: Annotated[str, Field(min_length=1, max_length=64)] | None = None
    reaffirm: bool = False

    @field_validator("patch_fields")
    @classmethod
    def _unique_canonical_patch_fields(
        cls,
        value: tuple[LedgerClassifyPatchField, ...],
    ) -> tuple[LedgerClassifyPatchField, ...]:
        if len(set(value)) != len(value) or not set(value) <= _CLASSIFY_FIELDS:
            raise ValueError("ledger classify fields must be unique supported fields")
        if value != tuple(sorted(value)):
            raise ValueError("ledger classify fields must use canonical sorted order")
        return value

    @model_validator(mode="after")
    def _selected_values_match_mask(self) -> LedgerClassifyRequest:
        _require_primary_classification(self)
        _require_selected_patch_values(self)
        _require_m210_selection(self)
        _require_m210_declaration_answers(self)
        return self


def _require_primary_classification(request: LedgerClassifyRequest) -> None:
    selected = set(request.patch_fields)
    classification_value = request.patch.business_classification
    if "business_classification" not in selected or classification_value is None:
        raise ValueError("ledger classify must select one business classification")
    classification = BusinessClassification(classification_value)
    business_pct_selected = "business_pct" in selected and request.patch.business_pct is not None
    if (classification is BusinessClassification.MIXED) != business_pct_selected:
        raise ValueError("mixed classification requires exactly one business percentage")


def _require_selected_patch_values(request: LedgerClassifyRequest) -> None:
    selected = set(request.patch_fields)
    patch_values = request.patch.model_dump()
    unselected_fields = _CLASSIFY_FIELDS - {"m210_income_classification"} - selected
    if any(patch_values[name] is not None for name in unselected_fields):
        raise ValueError("ledger classify request contains an unselected patch value")


def _m210_has_requested_option(options: LedgerClassifyM210Options) -> bool:
    return any(
        getattr(options, field_name) is not None
        for field_name in (
            "tipo_renta_code",
            "gross_income_amount",
            "applicable_rate",
            "payer_mode",
            "payer_id",
            "asset_or_right_id",
        )
    )


def _require_m210_selection(request: LedgerClassifyRequest) -> None:
    m210_selected = "m210_income_classification" in request.patch_fields
    m210_options_requested = request.m210 is not None and _m210_has_requested_option(request.m210)
    if m210_selected != m210_options_requested:
        raise ValueError("ledger classify M210 options and patch selection must agree")


def _m210_has_declaration_answers(options: LedgerClassifyM210Options) -> bool:
    return any(
        getattr(options, field_name) is not None
        for field_name in ("tipo_renta_code", "gross_income_amount", "applicable_rate", "payer_mode")
    )


def _require_m210_declaration_answers(request: LedgerClassifyRequest) -> None:
    if (
        request.m210 is not None
        and not _m210_has_declaration_answers(request.m210)
        and any((request.m210.payer_id, request.m210.asset_or_right_id))
    ):
        raise ValueError("M210 payer and asset identifiers require the four declaration answers")
