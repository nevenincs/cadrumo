"""Derive wire shapes from validated render-profile rules."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final, Literal

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_value_policy import ExportValuePolicy
from cadrumo.domain.calculations.registry.fixed_width_codec import (
    ExportJustification,
    ExportPadding,
    ExportSignPosition,
)

from .export_field_numeric_derivation import _DATE_FORMAT_BY_POLICY
from .export_field_schema import _is_required, _schema_field
from .export_fragment_provenance import ExportFieldDerivation
from .joined_record_design import JoinedRecordDesignField
from .render_profile_model import RenderProfile
from .render_profile_model_base import RenderProfileAnchor
from .render_profile_rules import SignedMonetaryCompositeRule, SingletonNumericRule, Width17MembershipRule

_SINGLETON_POLICY_SHAPES: Final[
    Mapping[ExportValuePolicy, Literal["integer", "decimal", "date", "digit_identity", "text"]]
] = {
    ExportValuePolicy.SELECTED_1_UNSELECTED_0: "integer",
    ExportValuePolicy.FOUR_DIGIT_YEAR_FINAL_TWO_DIGITS: "integer",
    ExportValuePolicy.UNSIGNED_INTEGER: "integer",
    ExportValuePolicy.IMPLIED_DECIMAL: "decimal",
    ExportValuePolicy.YYYYMMDD: "date",
    ExportValuePolicy.DDMMYYYY: "date",
    ExportValuePolicy.ENUMERATED_DIGITS: "integer",
    ExportValuePolicy.DIGIT_STRING: "digit_identity",
    ExportValuePolicy.IDENTIFIER_DIGITS: "digit_identity",
    ExportValuePolicy.FOUR_DIGIT_YEAR: "integer",
    ExportValuePolicy.TWO_DIGIT_MONTH: "integer",
    ExportValuePolicy.TWO_DIGIT_DAY: "integer",
    ExportValuePolicy.MISTYPED_ALPHANUMERIC_TEXT: "text",
    ExportValuePolicy.INTEGER_PART: "integer",
    ExportValuePolicy.FRACTIONAL_DIGITS: "integer",
    ExportValuePolicy.SIGNED_COMPONENT_MAGNITUDE: "decimal",
    ExportValuePolicy.SIGNED_COMPONENT_INTEGER_PART: "integer",
    ExportValuePolicy.SIGNED_COMPONENT_FRACTIONAL_DIGITS: "integer",
    ExportValuePolicy.YYYYMMDD_TEXT_YEAR: "integer",
    ExportValuePolicy.YYYYMMDD_TEXT_MONTH: "integer",
    ExportValuePolicy.YYYYMMDD_TEXT_DAY: "integer",
}


#: The width-17 sign policies this derivation distinguishes. ``signed`` below is a
#: boolean coercion of a two-member set, and it drives ``data_type``, ``signed``
#: and ``decimals`` together -- so a third policy admitted by
#: ``Width17MembershipRule.sign_policy`` without a decision here would not refuse;
#: it would render as an unsigned decimal carrying the rule's scale, wrong in all
#: three at once. The owning test holds this pair exhaustive against that field.
_WIDTH_17_SIGNED_POLICY: Final[str] = "n-prefix-negative-blank-nonnegative"


_WIDTH_17_UNSIGNED_POLICY: Final[str] = "unsigned"


type _SingletonNumericShape = tuple[
    Literal["text", "integer", "decimal", "money", "date", "boolean"],
    ExportPadding,
    ExportJustification,
    str | None,
    int | None,
    bool,
]


def _render_profile_numeric_derivation(
    joined_field: JoinedRecordDesignField,
    profile: RenderProfile,
    *,
    export_record_id: str,
) -> ExportFieldDerivation:
    anchor = _render_profile_anchor(joined_field)
    # The sign subdivision is stated in the cell prose, so a composite governs
    # its anchor even where the naturaleza column prints the slot as numeric.
    composite = profile.signed_composite_rule_by_anchor.get(anchor)
    if composite is not None:
        return _profile_signed_composite_derivation(joined_field, composite, export_record_id=export_record_id)
    # Indexed on the profile, not scanned here: a scan compared this anchor
    # against every anchor of every rule, and anchors are pydantic models whose
    # equality is not cheap.
    width_rule = profile.width_17_rule_by_anchor.get(anchor)
    if width_rule is not None:
        return _profile_width_17_derivation(
            joined_field,
            width_rule,
            export_record_id=export_record_id,
        )
    singleton = profile.singleton_rule_by_anchor.get(anchor)
    if singleton is None:
        raise RegistryValidationError(
            f"validated render profile has no exact rule for blank numeric anchor {anchor!r}",
        )
    return _profile_singleton_derivation(
        joined_field,
        singleton,
        export_record_id=export_record_id,
    )


def _profile_width_17_derivation(
    joined_field: JoinedRecordDesignField,
    rule: Width17MembershipRule,
    *,
    export_record_id: str,
) -> ExportFieldDerivation:
    signed = rule.sign_policy == _WIDTH_17_SIGNED_POLICY
    return _schema_field(
        joined_field,
        data_type="money" if signed else "decimal",
        required=_is_required(joined_field.parser_field.validation),
        padding=ExportPadding.LEFT_ZERO,
        justification=ExportJustification.RIGHT,
        signed=signed,
        export_record_id=export_record_id,
        # `money` carries its scale in the type; only `decimal` declares one, and
        # the schema refuses a field that declares decimals beside any other
        # data_type. Passing the rule's scale unconditionally would make every
        # signed width-17 amount unrepresentable.
        decimals=None if signed else rule.decimal_digits,
        derivation_code="render-profile-width-17-v1",
    )


def _profile_singleton_derivation(
    joined_field: JoinedRecordDesignField,
    rule: SingletonNumericRule,
    *,
    export_record_id: str,
) -> ExportFieldDerivation:
    data_type, padding, justification, date_format, decimals, signed = _singleton_numeric_shape(rule)
    allowed_values = rule.allowed_values or None if rule.value_policy is ExportValuePolicy.ENUMERATED_DIGITS else None
    return _schema_field(
        joined_field,
        data_type=data_type,
        required=_is_required(joined_field.parser_field.validation),
        padding=padding,
        justification=justification,
        signed=signed,
        export_record_id=export_record_id,
        derivation_code="render-profile-singleton-v1",
        date_format=date_format,
        decimals=decimals,
        value_policy=None if signed else rule.value_policy,
        allowed_values=allowed_values,
    )


def _singleton_numeric_shape(
    rule: SingletonNumericRule,
) -> _SingletonNumericShape:
    """Resolve a reviewed singleton's closed value policy to its wire shape."""
    signed = rule.aeat_type == "N"
    policy_shape = _SINGLETON_POLICY_SHAPES.get(rule.value_policy)
    if policy_shape is None:
        raise RegistryValidationError(f"unsupported singleton export value policy {rule.value_policy!r}")
    if policy_shape == "date":
        return _date_singleton_shape(rule, signed)
    if policy_shape == "decimal":
        return _decimal_singleton_shape(rule, signed)
    if policy_shape == "digit_identity":
        return "text", ExportPadding.NONE, ExportJustification.NONE, None, None, signed
    if policy_shape == "text":
        return "text", ExportPadding.RIGHT_SPACE, ExportJustification.LEFT, None, None, signed
    if policy_shape == "integer":
        return "integer", ExportPadding.LEFT_ZERO, ExportJustification.RIGHT, None, None, signed
    raise RegistryValidationError(f"unsupported singleton export policy shape {policy_shape!r}")


def _date_singleton_shape(rule: SingletonNumericRule, signed: bool) -> _SingletonNumericShape:
    date_format = _DATE_FORMAT_BY_POLICY.get(rule.value_policy)
    if date_format is None:
        raise RegistryValidationError(f"date singleton export policy lacks a date format {rule.value_policy!r}")
    return "date", ExportPadding.NONE, ExportJustification.NONE, date_format, None, signed


def _decimal_singleton_shape(rule: SingletonNumericRule, signed: bool) -> _SingletonNumericShape:
    component_money = rule.value_policy is ExportValuePolicy.SIGNED_COMPONENT_MAGNITUDE
    data_type: Literal["decimal", "money"] = "money" if signed or component_money else "decimal"
    decimals = None if signed or component_money else rule.decimal_digits
    return data_type, ExportPadding.LEFT_ZERO, ExportJustification.RIGHT, None, decimals, signed


def _profile_signed_composite_derivation(
    joined_field: JoinedRecordDesignField,
    rule: SignedMonetaryCompositeRule,
    *,
    export_record_id: str,
) -> ExportFieldDerivation:
    return _schema_field(
        joined_field,
        data_type="money",
        required=_is_required(joined_field.parser_field.validation),
        padding=ExportPadding.LEFT_ZERO,
        justification=ExportJustification.RIGHT,
        signed=True,
        sign_position=ExportSignPosition.BLANK_OR_N,
        export_record_id=export_record_id,
        derivation_code="render-profile-signed-monetary-composite-v1",
    )


def _render_profile_anchor(joined_field: JoinedRecordDesignField) -> RenderProfileAnchor:
    field = joined_field.parser_field
    # DERIVED, not authored: this anchor is built from the parser field, so a
    # missing ordinal is an observed fact about the design rather than a claim,
    # exactly as in ``render_profile._field_anchor``.
    return RenderProfileAnchor(
        sheet=field.sheet,
        source_row=field.source_row,
        semantic_part_offset=field.semantic_part_offset,
        source_cell=field.source_cell,
        ordinal=field.ordinal,
        ordinal_absent=field.ordinal is None,
        record_identity=field.record_identity,
    )
