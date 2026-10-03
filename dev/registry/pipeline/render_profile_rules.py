"""Canonical typed wire and literal rules for reviewed render profiles."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from cadrumo.domain.calculations.registry.export_value_policy import (
    ExportValuePolicy,
    RequiredExportValuePolicyValue,
)

from .render_profile_evidence import ReviewedEvidence, ReviewedPolicyDecision, SourceStatedCompositeEvidence
from .render_profile_model_base import RenderProfileAnchor, RenderProfileDesignIdentity, _StrictModel


class Width17MembershipRule(_StrictModel):
    """Reviewed enumeration of width-17 amount anchors of one AEAT type."""

    rule_kind: Literal["width_17_membership"]
    aeat_type: Literal["Num", "N"]
    integer_digits: Literal[15, 14]
    decimal_digits: Literal[2]
    sign_policy: Literal["unsigned", "n-prefix-negative-blank-nonnegative"]
    anchors: tuple[RenderProfileAnchor, ...] = Field(min_length=1)
    evidence: ReviewedEvidence

    @model_validator(mode="after")
    def _require_explicit_type_specific_representation(self) -> Width17MembershipRule:
        # A membership rule may rest on either authority kind, exactly as a
        # singleton may. Demanding official-source evidence here did not make the
        # membership better grounded: an official design that states the amount
        # type, alignment and sign but never its integer/decimal split cannot
        # ground the split, so the requirement only forced the split's reviewed
        # inference to be labelled as quoted official text. The label then
        # asserted an authority the quoted statement does not carry, which is the
        # under-declaration this authority kind exists to make visible.
        if isinstance(self.evidence, ReviewedPolicyDecision) and self.evidence.governed_anchor is not None:
            raise ValueError("width-17 membership policy governs its anchor enumeration, not one named anchor")
        expected = (15, "unsigned") if self.aeat_type == "Num" else (14, "n-prefix-negative-blank-nonnegative")
        if (self.integer_digits, self.sign_policy) != expected:
            raise ValueError(f"{self.aeat_type} width-17 representation conflicts with its explicit sign policy")
        return self


class SingletonNumericRule(_StrictModel):
    """One reviewed smaller numeric field; grouping is deliberately impossible."""

    rule_kind: Literal["singleton_numeric"]
    aeat_type: Literal["Num", "N"]
    semantic_kind: Literal[
        "integer",
        "decimal",
        "date_yyyymmdd",
        "date_ddmmyyyy",
        "enumeration",
        "percentage_decimal",
        "digit_string",
        "identifier_digits",
        "checkbox",
        "year_yyyy",
        "year_last_two_digits",
        "month_mm",
        "day_dd",
        "mistyped_alphanumeric_text",
        #: One HALF of a quantity AEAT prints as a subdivided pair -- a printed
        #: "Parte entera" row and a printed "Parte decimal" row that exactly tile
        #: their parent. The export IR descends to those leaves, so the layout
        #: carries two fields for one casilla, and each half states which part of
        #: the value it writes. Reserved for parts of ONE quantity: where the
        #: printed subdivision carries distinct FACTS, the registry gains a
        #: casilla per fact instead.
        "amount_integer_part",
        "amount_fractional_digits",
        "signed_component_magnitude",
        "signed_amount_integer_part",
        "signed_amount_fractional_digits",
        "date_text_year",
        "date_text_month",
        "date_text_day",
    ]
    value_policy: RequiredExportValuePolicyValue
    integer_digits: int = Field(ge=0)
    decimal_digits: int = Field(ge=0)
    sign_policy: Literal["unsigned", "n-prefix-negative-blank-nonnegative"]
    allowed_values: tuple[str, ...]
    anchor: RenderProfileAnchor
    evidence: ReviewedEvidence

    @model_validator(mode="after")
    def _require_kind_specific_declaration(self) -> SingletonNumericRule:
        _validate_singleton_sign_policy(self)
        _validate_singleton_allowed_values(self)
        _validate_singleton_value_policy(self)
        _validate_singleton_date_shape(self)
        _validate_singleton_integer_shapes(self)
        _validate_singleton_decimal_shape(self)
        _validate_singleton_digit_shape(self)
        _validate_singleton_enumeration_shape(self)
        _validate_singleton_exact_shape(self)
        _validate_singleton_evidence(self)
        return self


def _validate_singleton_sign_policy(rule: SingletonNumericRule) -> None:
    if rule.aeat_type == "N":
        if (
            rule.sign_policy != "n-prefix-negative-blank-nonnegative"
            or rule.semantic_kind != "decimal"
            or rule.decimal_digits != 2
        ):
            raise ValueError("signed singleton rules require an N-prefix two-decimal monetary representation")
    elif rule.sign_policy != "unsigned":
        raise ValueError("Num singleton rules require an unsigned representation")


def _validate_singleton_allowed_values(rule: SingletonNumericRule) -> None:
    if rule.semantic_kind in {"enumeration", "checkbox"}:
        if not rule.allowed_values or any(
            not item or not item.isascii() or not item.isdigit() or str(int(item)) != item
            for item in rule.allowed_values
        ):
            raise ValueError(
                f"{rule.semantic_kind} rules require explicit canonical ASCII-integer allowed_values",
            )
        if len(set(rule.allowed_values)) != len(rule.allowed_values):
            raise ValueError("enumeration allowed_values must be unique")
    elif rule.allowed_values:
        raise ValueError("allowed_values must be explicitly empty outside an enumeration rule")


def _validate_singleton_value_policy(rule: SingletonNumericRule) -> None:
    required_policy = {
        "integer": ExportValuePolicy.UNSIGNED_INTEGER,
        "decimal": ExportValuePolicy.IMPLIED_DECIMAL,
        "percentage_decimal": ExportValuePolicy.IMPLIED_DECIMAL,
        "date_yyyymmdd": ExportValuePolicy.YYYYMMDD,
        "date_ddmmyyyy": ExportValuePolicy.DDMMYYYY,
        "enumeration": ExportValuePolicy.ENUMERATED_DIGITS,
        "digit_string": ExportValuePolicy.DIGIT_STRING,
        "identifier_digits": ExportValuePolicy.IDENTIFIER_DIGITS,
        "checkbox": ExportValuePolicy.SELECTED_1_UNSELECTED_0,
        "year_yyyy": ExportValuePolicy.FOUR_DIGIT_YEAR,
        "year_last_two_digits": ExportValuePolicy.FOUR_DIGIT_YEAR_FINAL_TWO_DIGITS,
        "month_mm": ExportValuePolicy.TWO_DIGIT_MONTH,
        "day_dd": ExportValuePolicy.TWO_DIGIT_DAY,
        "mistyped_alphanumeric_text": ExportValuePolicy.MISTYPED_ALPHANUMERIC_TEXT,
        "amount_integer_part": ExportValuePolicy.INTEGER_PART,
        "amount_fractional_digits": ExportValuePolicy.FRACTIONAL_DIGITS,
        "signed_component_magnitude": ExportValuePolicy.SIGNED_COMPONENT_MAGNITUDE,
        "signed_amount_integer_part": ExportValuePolicy.SIGNED_COMPONENT_INTEGER_PART,
        "signed_amount_fractional_digits": ExportValuePolicy.SIGNED_COMPONENT_FRACTIONAL_DIGITS,
        "date_text_year": ExportValuePolicy.YYYYMMDD_TEXT_YEAR,
        "date_text_month": ExportValuePolicy.YYYYMMDD_TEXT_MONTH,
        "date_text_day": ExportValuePolicy.YYYYMMDD_TEXT_DAY,
    }[rule.semantic_kind]
    if rule.value_policy != required_policy:
        raise ValueError(f"{rule.semantic_kind} requires value_policy {required_policy!r}")


def _validate_singleton_date_shape(rule: SingletonNumericRule) -> None:
    if rule.semantic_kind in {"date_yyyymmdd", "date_ddmmyyyy"} and (
        rule.integer_digits,
        rule.decimal_digits,
    ) != (8, 0):
        raise ValueError(f"{rule.semantic_kind} requires exactly 8 integer digits and 0 decimal digits")


def _validate_singleton_integer_shapes(rule: SingletonNumericRule) -> None:
    _validate_unsigned_integer_parts(rule)
    _validate_signed_amount_parts(rule)


def _validate_unsigned_integer_parts(rule: SingletonNumericRule) -> None:
    if rule.semantic_kind == "integer" and (rule.integer_digits <= 0 or rule.decimal_digits != 0):
        raise ValueError("integer requires positive integer digits and 0 decimal digits")
    if rule.semantic_kind == "amount_integer_part" and (rule.integer_digits <= 0 or rule.decimal_digits != 0):
        raise ValueError("amount_integer_part requires positive integer digits and 0 decimal digits")
    if rule.semantic_kind == "amount_fractional_digits" and (rule.integer_digits != 0 or rule.decimal_digits <= 0):
        raise ValueError("amount_fractional_digits requires 0 integer digits and positive decimal digits")


def _validate_signed_amount_parts(rule: SingletonNumericRule) -> None:
    if rule.semantic_kind == "signed_amount_integer_part" and (
        rule.integer_digits not in {8, 13} or rule.decimal_digits != 0
    ):
        raise ValueError("signed amount integer part requires 8 or 13 integer digits")
    if rule.semantic_kind == "signed_amount_fractional_digits" and (
        rule.integer_digits != 0 or rule.decimal_digits != 2
    ):
        raise ValueError("signed amount fractional part requires two decimal digits")


def _validate_singleton_decimal_shape(rule: SingletonNumericRule) -> None:
    if rule.semantic_kind in {"decimal", "percentage_decimal"} and (
        rule.integer_digits <= 0 or rule.decimal_digits <= 0
    ):
        raise ValueError(f"{rule.semantic_kind} requires positive integer and decimal digits")


def _validate_singleton_digit_shape(rule: SingletonNumericRule) -> None:
    if rule.semantic_kind in {"digit_string", "identifier_digits"} and (
        rule.integer_digits <= 0 or rule.decimal_digits != 0
    ):
        raise ValueError(f"{rule.semantic_kind} requires positive integer digits and 0 decimal digits")


def _validate_singleton_enumeration_shape(rule: SingletonNumericRule) -> None:
    if rule.semantic_kind == "enumeration" and rule.decimal_digits != 0:
        raise ValueError("enumeration requires 0 decimal digits")
    if rule.semantic_kind == "enumeration" and any(len(item) > rule.integer_digits for item in rule.allowed_values):
        raise ValueError("enumeration allowed_values must fit the declared integer width")


def _validate_singleton_exact_shape(rule: SingletonNumericRule) -> None:
    exact_shapes = {
        "mistyped_alphanumeric_text": (0, 0),
        "checkbox": (1, 0),
        "year_yyyy": (4, 0),
        "year_last_two_digits": (2, 0),
        "month_mm": (2, 0),
        "day_dd": (2, 0),
        "signed_component_magnitude": (11, 2),
        "date_text_year": (4, 0),
        "date_text_month": (2, 0),
        "date_text_day": (2, 0),
    }
    expected_shape = exact_shapes.get(rule.semantic_kind)
    if expected_shape is not None and (rule.integer_digits, rule.decimal_digits) != expected_shape:
        raise ValueError(f"{rule.semantic_kind} requires exactly {expected_shape!r} integer/decimal digits")
    if rule.semantic_kind == "checkbox" and rule.allowed_values != ("0", "1"):
        raise ValueError("checkbox requires allowed_values ('0', '1')")


def _validate_singleton_evidence(rule: SingletonNumericRule) -> None:
    if isinstance(rule.evidence, ReviewedPolicyDecision) and (
        rule.evidence.governed_anchor is None or rule.evidence.governed_anchor != rule.anchor
    ):
        raise ValueError("reviewed policy must name the exact governed anchor")


class LiteralNumericRule(_StrictModel):
    """The reviewed numeric scale of one exact constant; its wire bytes stay literal."""

    rule_kind: Literal["literal_numeric"]
    literal: str = Field(pattern=r"^[0-9]+$")
    decimal_digits: int = Field(ge=0)
    anchor: RenderProfileAnchor
    evidence: ReviewedEvidence

    @model_validator(mode="after")
    def _require_numeric_scale(self) -> LiteralNumericRule:
        if self.decimal_digits >= len(self.literal):
            raise ValueError("literal numeric scale must leave at least one integer digit")
        if isinstance(self.evidence, ReviewedPolicyDecision) and self.evidence.governed_anchor != self.anchor:
            raise ValueError("reviewed policy must name the exact governed anchor")
        return self


class SignedMonetaryCompositeRule(_StrictModel):
    """One reviewed unsplit PDF amount with a reserved blank-or-N leading sign."""

    rule_kind: Literal["signed_monetary_composite"]
    integer_digits: int = Field(gt=0)
    decimal_digits: Literal[2]
    sign_policy: Literal["blank-or-n-leading"]
    anchor: RenderProfileAnchor
    evidence: SourceStatedCompositeEvidence

    @model_validator(mode="after")
    def _require_exact_governed_anchor(self) -> SignedMonetaryCompositeRule:
        if self.evidence.governed_anchor != self.anchor:
            raise ValueError("source-stated composite evidence must name the exact governed anchor")
        return self


class TelematicTransportChoiceRule(_StrictModel):
    """A source-pinned choice of the official telematic transport code."""

    rule_kind: Literal["telematic_transport_choice"]
    selected_literal: Literal["T"]
    alternative_literals: tuple[str, ...] = Field(min_length=1)
    selection_condition: Literal["telematic_transmission"]
    expected_source_content: str = Field(min_length=1)
    anchor: RenderProfileAnchor
    evidence: ReviewedPolicyDecision

    @model_validator(mode="after")
    def _require_reviewed_choice(self) -> TelematicTransportChoiceRule:
        if self.evidence.governed_anchor != self.anchor:
            raise ValueError("transport choice policy must name its exact governed anchor")
        if len(set(self.alternative_literals)) != len(self.alternative_literals) or "T" in self.alternative_literals:
            raise ValueError("transport alternatives must be distinct from the selected literal")
        if any(len(value) != 1 or not value.isascii() or not value.isupper() for value in self.alternative_literals):
            raise ValueError("transport alternatives must be single uppercase ASCII letters")
        return self


class RenderProfileFragment(_StrictModel):
    """One deterministic, independently reviewable profile fragment."""

    schema_version: Literal[1]
    fragment_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")
    design_identity: RenderProfileDesignIdentity
    width_17_rules: tuple[Width17MembershipRule, ...]
    singleton_rules: tuple[SingletonNumericRule, ...]
    signed_composite_rules: tuple[SignedMonetaryCompositeRule, ...] = ()
    literal_numeric_rules: tuple[LiteralNumericRule, ...] = ()
    telematic_transport_choice_rules: tuple[TelematicTransportChoiceRule, ...] = ()
    empty_rule_assertion: Literal["canonical_eligibility_empty"] | None = None

    @model_validator(mode="after")
    def _require_authored_rules(self) -> RenderProfileFragment:
        has_rules = bool(
            self.width_17_rules
            or self.singleton_rules
            or self.signed_composite_rules
            or self.literal_numeric_rules
            or self.telematic_transport_choice_rules
        )
        if has_rules == (self.empty_rule_assertion is not None):
            raise ValueError("render profile fragment requires rules or an exclusive empty eligibility assertion")
        return self
