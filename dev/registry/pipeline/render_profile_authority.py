"""Canonical authority validation for reviewed render-profile rules and source statements."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from typing import Final

from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from .record_design_intermediate import RecordDesignIntermediateField
from .render_profile_eligibility import (
    RenderProfileEligibility,
    _has_absent_naturaleza,
    _is_numeric_aeat_type,
    normalise_aeat_type,
)
from .render_profile_evidence import (
    RenderProfileSourceEvidence,
    ReviewedPolicyDecision,
)
from .render_profile_model import RenderProfile
from .render_profile_model_base import RenderProfileAnchor, RenderProfileDesignIdentity
from .render_profile_rules import (
    SignedMonetaryCompositeRule,
    SingletonNumericRule,
)
from .render_profile_validation import _anchor_key, _duplicates, _field_anchor


def validate_render_profile_authority(
    profile: RenderProfile,
    expected_identity: RenderProfileDesignIdentity,
    eligibility: RenderProfileEligibility,
    source_evidence: RenderProfileSourceEvidence,
) -> None:
    """Validate a complete profile against source-owned identity and eligibility."""
    _require_profile_identities(profile, expected_identity, source_evidence)
    _validate_reviewed_evidence(profile, source_evidence)
    fixed = {_field_anchor(field): field for field in eligibility.fixed_fields}
    _validate_literal_numeric_authority(profile, fixed)
    eligible = {_field_anchor(field): field for field in eligibility.all_fields}
    _require_exact_profile_coverage(profile, eligible)
    _validate_width_17_authority(profile, eligibility, eligible)
    _validate_singleton_authority(profile, eligible)
    _validate_signed_composite_authority(profile, eligible)


def _require_profile_identities(
    profile: RenderProfile,
    expected_identity: RenderProfileDesignIdentity,
    source_evidence: RenderProfileSourceEvidence,
) -> None:
    if profile.design_identity != expected_identity:
        raise RegistryValidationError(
            f"render profile identity {profile.design_identity!r} does not match exact official design "
            f"{expected_identity!r}",
        )
    if source_evidence.design_identity != expected_identity:
        raise RegistryValidationError(
            "render profile source evidence does not match the exact official design identity"
        )


def _validate_literal_numeric_authority(
    profile: RenderProfile,
    fixed: Mapping[RenderProfileAnchor, RecordDesignIntermediateField],
) -> None:
    literal_anchors = tuple(rule.anchor for rule in profile.literal_numeric_rules)
    if _duplicates(literal_anchors):
        raise RegistryValidationError("literal numeric rules contain duplicate exact anchors")
    for rule in profile.literal_numeric_rules:
        field = fixed.get(rule.anchor)
        if field is None or not _is_numeric_aeat_type(field.aeat_type) or field.length != len(rule.literal):
            raise RegistryValidationError("literal numeric rule conflicts with its official numeric slot")


def _require_exact_profile_coverage(
    profile: RenderProfile,
    eligible: Mapping[RenderProfileAnchor, RecordDesignIntermediateField],
) -> None:
    governed = (
        tuple(anchor for rule in profile.width_17_rules for anchor in rule.anchors)
        + tuple(rule.anchor for rule in profile.singleton_rules)
        + tuple(rule.anchor for rule in profile.signed_composite_rules)
    )
    duplicates = _duplicates(governed)
    if duplicates:
        raise RegistryValidationError(f"render profile contains duplicate or overlapping exact anchors: {duplicates!r}")
    governed_set = set(governed)
    eligible_set = set(eligible)
    if governed_set != eligible_set:
        missing = sorted(eligible_set - governed_set, key=_anchor_key)
        unknown = sorted(governed_set - eligible_set, key=_anchor_key)
        raise RegistryValidationError(
            "render profile must cover exactly the eligible blank numeric fields; "
            f"missing={missing!r}, unknown={unknown!r}",
        )


def _validate_width_17_authority(
    profile: RenderProfile,
    eligibility: RenderProfileEligibility,
    eligible: Mapping[RenderProfileAnchor, RecordDesignIntermediateField],
) -> None:
    width_17_types = tuple(rule.aeat_type for rule in profile.width_17_rules)
    duplicate_width_17_types = _duplicates(width_17_types)
    if duplicate_width_17_types:
        raise RegistryValidationError(
            "render profile splits one width-17 AEAT type across multiple membership rules: "
            f"{duplicate_width_17_types!r}",
        )
    eligible_width_17_types = {field.aeat_type for field in eligibility.width_17_fields}
    if set(width_17_types) != eligible_width_17_types:
        raise RegistryValidationError(
            "render profile must declare one explicit width-17 membership rule for each eligible AEAT type",
        )
    for rule in profile.width_17_rules:
        for anchor in rule.anchors:
            field = eligible[anchor]
            if field.length != 17 or field.aeat_type != rule.aeat_type:
                raise RegistryValidationError(
                    f"width-17 {rule.aeat_type} membership conflicts with official field at {anchor!r}",
                )


def _validate_singleton_authority(
    profile: RenderProfile,
    eligible: Mapping[RenderProfileAnchor, RecordDesignIntermediateField],
) -> None:
    for rule in profile.singleton_rules:
        _validate_one_singleton_authority(rule, eligible[rule.anchor])


def _validate_one_singleton_authority(
    rule: SingletonNumericRule,
    field: RecordDesignIntermediateField,
) -> None:
    # PDF numeric spellings canonicalize to ``Numerico``; blank naturezas are
    # eligible for reviewed rules because the source states no type to compare.
    if field.length == 17 or not (_is_numeric_aeat_type(field.aeat_type) or _has_absent_naturaleza(field)):
        raise RegistryValidationError(f"smaller singleton rule conflicts with official field at {rule.anchor!r}")
    if (field.aeat_type == "N") != (rule.aeat_type == "N"):
        raise RegistryValidationError(f"singleton sign conflicts with official type at {rule.anchor!r}")
    if rule.semantic_kind != "mistyped_alphanumeric_text" and (
        rule.integer_digits + rule.decimal_digits != field.length
    ):
        raise RegistryValidationError(
            f"smaller singleton representation width conflicts with official length at {rule.anchor!r}",
        )
    if any(len(item) > field.length for item in rule.allowed_values):
        raise RegistryValidationError(
            f"enumeration value width conflicts with official length at {rule.anchor!r}",
        )


def _validate_signed_composite_authority(
    profile: RenderProfile,
    eligible: Mapping[RenderProfileAnchor, RecordDesignIntermediateField],
) -> None:
    for rule in profile.signed_composite_rules:
        _validate_signed_composite_source_agreement(rule, eligible[rule.anchor])


def _validate_reviewed_evidence(
    profile: RenderProfile,
    source_evidence: RenderProfileSourceEvidence,
) -> None:
    actual_by_locator = {(entry.sheet, entry.cell): entry.normalized_statement for entry in source_evidence.entries}
    reviewed = (
        tuple(rule.evidence for rule in profile.width_17_rules)
        + tuple(rule.evidence for rule in profile.singleton_rules)
        + tuple(rule.evidence for rule in profile.literal_numeric_rules)
    )
    for evidence in reviewed:
        if isinstance(evidence, ReviewedPolicyDecision):
            continue
        locator = evidence.source_sheet, evidence.source_cell
        actual_statement = actual_by_locator.get(locator)
        if actual_statement is None:
            raise RegistryValidationError(f"render profile evidence locator does not exist: {locator!r}")
        if actual_statement != evidence.expected_normalized_statement:
            raise RegistryValidationError(
                f"render profile evidence statement does not match verified source at {locator!r}",
            )


_COMPOSITE_DEFINITION_RE: Final[re.Pattern[str]] = re.compile(
    r'(?P<framing>[a-z][a-z "]{0,399}\.?)\s+este campo se subdivide en\s*:\s*'
    r"(?P<sign_position>\d+)\s+signo\s*:\s*(?P<sign_nature>[a-z]+)\.\s*"
    r"se cumplimentara cuando el resultado anteriormente mencionado sea menor de 0 \(cero\)\.\s*"
    r'en este caso se consignara una "(?P<sign_token>[a-z])", en cualquier otro caso el contenido de este '
    r"campo sera un espacio\.\s*"
    r"(?P<magnitude_start>\d+)\s*-\s*(?P<magnitude_end>\d+)\s+importe\s*:\s*"
    r"campo numerico de (?P<magnitude_digits>\d+) posiciones\.\s*"
    r"se consignara sin signo y sin coma decimal, el importe mencionado anteriormente\.\s*"
    r"este campo se subdivide en dos\s*:\s*"
    r"(?P<integer_start>\d+)\s*-\s*(?P<integer_end>\d+)\s+parte entera del importe"
    r"(?P<integer_qualifier> de [a-z ]{1,200})?,\s*"
    r"si no tiene contenido se consignara a ceros\.\s*"
    r"(?P<decimal_start>\d+)\s*-\s*(?P<decimal_end>\d+)\s+parte decimal del importe"
    r"(?P<decimal_qualifier> de [a-z ]{1,200})?,\s*"
    r"si no tiene contenido se consignara a ceros\.",
    re.IGNORECASE,
)


_COMPOSITE_NON_POLICY_WIRE_TERMS: Final[re.Pattern[str]] = re.compile(
    r"\b(?:alfabetico|ceros|coma|decimal|digitos?|entera|espacio|importe|menor|numerico|parte|posiciones?|signo)\b",
    re.IGNORECASE,
)


def _validate_signed_composite_source_agreement(
    rule: SignedMonetaryCompositeRule,
    field: RecordDesignIntermediateField,
) -> None:
    """Verify a reviewed rule against source prose without deriving policy from it."""
    normalised_source, definition = _signed_composite_source_definition(field)
    _validate_composite_wire_terms(definition)
    _validate_composite_sign_statement(definition, normalised_source)
    _validate_composite_geometry(rule, field, definition)


def _signed_composite_source_definition(
    field: RecordDesignIntermediateField,
) -> tuple[str, re.Match[str]]:
    if field.source_cell is not None or normalise_aeat_type(field.aeat_type) != "alfanumerico":
        raise RegistryValidationError("signed monetary composite requires an unsplit alphanumeric PDF anchor")
    source_text = (field.content or "").replace("�", '"').replace("�", '"')
    normalised_source = " ".join(
        unicodedata.normalize("NFKD", source_text).encode("ascii", "ignore").decode("ascii").split()
    )
    definition = _COMPOSITE_DEFINITION_RE.fullmatch(normalised_source)
    if definition is None:
        raise RegistryValidationError(
            "signed monetary composite source must exactly match the reviewed complete wire definition"
        )
    return normalised_source, definition


def _validate_composite_wire_terms(definition: re.Match[str]) -> None:
    non_policy_segments = (
        definition.group("framing"),
        definition.group("integer_qualifier") or "",
        definition.group("decimal_qualifier") or "",
    )
    if any(_COMPOSITE_NON_POLICY_WIRE_TERMS.search(segment) is not None for segment in non_policy_segments):
        raise RegistryValidationError("signed monetary composite source non-policy framing contains a wire instruction")
    if definition.group("integer_qualifier") != definition.group("decimal_qualifier"):
        raise RegistryValidationError("signed monetary composite source partition descriptions do not agree")


def _validate_composite_sign_statement(definition: re.Match[str], normalised_source: str) -> None:
    if normalise_aeat_type(definition.group("sign_nature")) != "alfabetico":
        raise RegistryValidationError("signed monetary composite source sign slot must be alphabetic")
    # Prose spelling and case are normalized by the grammar, but the wire token
    # is not: the existing codec emits uppercase N.
    if definition.group("sign_token") != "N":
        raise RegistryValidationError("signed monetary composite source must declare uppercase N as its wire token")
    quoted_sign_tokens = tuple(
        token for token in re.findall(r'"([^"]+)"', normalised_source) if token.casefold() == "n"
    )
    if quoted_sign_tokens != ("N",):
        raise RegistryValidationError(
            "signed monetary composite source must declare exactly one uppercase N wire token"
        )


def _validate_composite_geometry(
    rule: SignedMonetaryCompositeRule,
    field: RecordDesignIntermediateField,
    definition: re.Match[str],
) -> None:
    sign_position = int(definition.group("sign_position"))
    magnitude_start = int(definition.group("magnitude_start"))
    magnitude_end = int(definition.group("magnitude_end"))
    integer_start = int(definition.group("integer_start"))
    integer_end = int(definition.group("integer_end"))
    decimal_start = int(definition.group("decimal_start"))
    decimal_end = int(definition.group("decimal_end"))
    magnitude_digits = int(definition.group("magnitude_digits"))
    expected_end = field.offset + field.length - 1
    if not _composite_bounds_match(
        field,
        sign_position=sign_position,
        magnitude_start=magnitude_start,
        magnitude_end=magnitude_end,
        magnitude_digits=magnitude_digits,
        expected_end=expected_end,
    ) or not _composite_parts_match(
        rule,
        magnitude_start=magnitude_start,
        magnitude_end=magnitude_end,
        magnitude_digits=magnitude_digits,
        integer_start=integer_start,
        integer_end=integer_end,
        decimal_start=decimal_start,
        decimal_end=decimal_end,
    ):
        raise RegistryValidationError("signed monetary composite source ranges do not exactly partition its anchor")


def _composite_bounds_match(
    field: RecordDesignIntermediateField,
    *,
    sign_position: int,
    magnitude_start: int,
    magnitude_end: int,
    magnitude_digits: int,
    expected_end: int,
) -> bool:
    return (
        sign_position == field.offset
        and magnitude_start == field.offset + 1
        and magnitude_end == expected_end
        and magnitude_digits == field.length - 1
    )


def _composite_parts_match(
    rule: SignedMonetaryCompositeRule,
    *,
    magnitude_start: int,
    magnitude_end: int,
    magnitude_digits: int,
    integer_start: int,
    integer_end: int,
    decimal_start: int,
    decimal_end: int,
) -> bool:
    return (
        integer_start == magnitude_start
        and integer_end + 1 == decimal_start
        and decimal_end == magnitude_end
        and integer_end - integer_start + 1 == rule.integer_digits
        and decimal_end - decimal_start + 1 == rule.decimal_digits
        and rule.integer_digits + rule.decimal_digits == magnitude_digits
    )
