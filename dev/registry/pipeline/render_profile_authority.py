"""Canonical authority validation for reviewed render-profile rules and source statements."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from typing import Final, cast

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
from .source_defects import adjudicated_integer_range_for
from .source_stated_composites import source_stated_composite_integer_digits_for


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
        _validate_signed_composite_source_agreement(rule, eligible[rule.anchor], profile.design_identity)


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


#: Running BOE page furniture the PDF text layer splices into a cell when the
#: printed description crosses a page boundary. It is print, never a wire
#: statement, and it is removed before the grammar reads the cell.
_BOE_PAGE_FURNITURE_RE: Final[re.Pattern[str]] = re.compile(
    r"\s*cve: BOE-[A-Z]-\d{4}-\d+ BOLETIN OFICIAL DEL ESTADO Num\. \d+ "
    r"(?:Lunes|Martes|Miercoles|Jueves|Viernes|Sabado|Domingo) \d{1,2} de [a-z]+ de \d{4} "
    r"Sec\. [IVX]+\. Pag\. \d+\s*",
    re.IGNORECASE,
)

#: The complete signed-composite definition: optional descriptive framing, the
#: sign slot, the magnitude range and its two partition statements. Every
#: policy-bearing clause is a fixed phrase; the free segments between them are
#: classified sentence by sentence and may not carry a wire instruction.
_COMPOSITE_DEFINITION_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:(?P<framing>.+?)\s+)?"
    r"este campo se subdivide en(?: dos)?\s*:\s*"
    r"(?P<sign_position>\d+)\s+signo\s*:\s*(?:campo\s+)?(?P<sign_nature>[a-z]+)\s*[.,]?\s*"
    r"(?P<sign_statement>.+?)\s+"
    r"(?P<magnitude_start>\d+)\s*-\s*(?P<magnitude_end>\d+)\s+importe\s*[:.]\s*"
    r"(?P<magnitude_body>.+?)\s+"
    r"(?:este campo se subdivide en dos\s*:\s*)?"
    r"(?P<integer_start>\d+)\s*-\s*(?P<integer_end>\d+)\s*parte entera del importe"
    r"(?P<integer_qualifier> [a-z ]{1,200}?)?[,.]\s*si no tiene contenido se consignara a ceros\.\s*"
    r"(?:(?P<interstitial>.+?)\s+)?"
    r"(?P<decimal_start>\d+)\s*-\s*(?P<decimal_end>\d+)\s*parte decimal del importe"
    r"(?P<decimal_qualifier> [a-z ]{1,200}?)?[,.]\s*si no tiene contenido se consignara a ceros\."
    r"(?:\s+(?P<trailer>.+))?",
    re.IGNORECASE,
)

#: The two published orders of one sign statement: the condition before the
#: token, or the token before the condition.
_COMPOSITE_SIGN_STATEMENT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:que\s+)?se cumplimentara (?:este campo )?cuando (?P<condition_first>.+?)\s*[.;]\s*"
    r'en este caso se consignara una "(?P<token_after>[a-z])"\s*[.,]\s*'
    r"en cualquier otro caso el contenido (?:de este|del) campo sera un espacio\."
    r'|se consignara una "(?P<token_first>[a-z])" cuando (?P<condition_after>.+?)\.\s*'
    r"en cualquier otro caso el contenido (?:de este|del) campo sera un espacio\.",
    re.IGNORECASE,
)

_COMPOSITE_NEGATIVE_CONDITION_RE: Final[re.Pattern[str]] = re.compile(
    r"(?P<subject>.+?) sea menor (?:de|que) 0 \(cero\)",
    re.IGNORECASE,
)

#: The one non-arithmetic sign condition the designs print: a perceptor amount
#: returned for an earlier year. The composite writes "N" for a negative value,
#: so the reintegro is carried as a negative amount.
_COMPOSITE_REINTEGRO_CONDITION: Final = (
    "las percepciones correspondan a cantidades reintegradas por el perceptor en el ejercicio, "
    "como consecuencia de haber sido indebida o excesivamente percibidas en ejercicios anteriores"
)

_COMPOSITE_WIDTH_RE: Final[re.Pattern[str]] = re.compile(
    r"campo (?P<nature>alfanumerico|numerico) de (?P<digits>\d+) posiciones",
    re.IGNORECASE,
)
_COMPOSITE_UNSIGNED_MAGNITUDE_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:se consignara|se hara constar) sin signo y sin coma decimal\b(?P<rest>.*)"
    r"|el importe no ira precedido de signo alguno \(\+/-\), ni incluira coma decimal",
    re.IGNORECASE,
)
_COMPOSITE_MAGNITUDE_SUBJECT_RE: Final[re.Pattern[str]] = re.compile(
    r"campo numerico en el que se consignara\b(?P<rest>.*)",
    re.IGNORECASE,
)
_COMPOSITE_SUM_MAGNITUDE_RE: Final[re.Pattern[str]] = re.compile(
    r"campo numerico en el que se consignara la suma de las cantidades, sin coma decimal, "
    r"(?P<rest>reflejadas en las percepciones integras satisfechas .+)",
    re.IGNORECASE,
)
# The four source epochs of Modelo 190 state the same multi-component sum.
# Recognize the complete clause; a changed sign or arithmetic instruction must
# not be classified as harmless descriptive prose.
_COMPOSITE_PERCEPTOR_SIGNED_SUM: Final[str] = (
    'En el supuesto de que en los registros de perceptores se hubiera consignado "N" en los campos '
    '"Signo de la percepcion integra", "Signo de la percepcion en especie", '
    '"Signo de la percepcion integra derivada de incapacidad laboral" y '
    '"Signo de la percepcion en especie derivada de incapacidad laboral" '
    "(posiciones 81, 108, 255 y 282, respectivamente, del registro de tipo 2), "
    "por corresponder al reintegro de percepciones indebida o excesivamente satisfechas en ejercicios anteriores, "
    "dichas cantidades se computaran igualmente con signo menos al totalizar los importes que deben reflejarse "
    "en esta suma"
)
_COMPOSITE_CURRENCY_RE: Final[re.Pattern[str]] = re.compile(r"los importes deben consignarse en euros", re.IGNORECASE)
#: A total's statement that its source records' "N" amounts are summed as
#: negative: aggregation semantics of the total, not this field's wire form.
_COMPOSITE_SIGNED_SUM_RE: Final[re.Pattern[str]] = re.compile(
    r'en el supuesto de que en (?:estos|los) registros de [a-z]+ se hubiera consignado "N" en el campo '
    r'"?signo [a-z ]+"?,? \(posicion \d+ del registro de tipo 2\),? '
    r"(?:por corresponder al reintegro de [a-z ,]+, dichas cantidades|las cantidades) "
    r"se computaran (?:igualmente )?con signo menos "
    r"(?:a efecto de esta suma|al totalizar los importes que deben reflejarse en esta suma)",
    re.IGNORECASE,
)
#: A quoted upper-case field name is a cross-reference, not a wire token.
_COMPOSITE_QUOTED_FIELD_NAME_RE: Final[re.Pattern[str]] = re.compile(r'"[A-Z][A-Z ]+"')
_COMPOSITE_DESCRIPTIVE_WIRE_TERMS: Final[re.Pattern[str]] = re.compile(
    r"\bsigno\b|\bcoma\b|\bdigitos?\b|\bparte (?:entera|decimal)\b|\bespacio\b|\bceros?\b|\bmenor\b|\bmayor\b"
    r'|\bdecimal(?:es)?\b|\bposicion(?:es)?\b(?!\s+\d)|\b(?:alfa)?numerico\b|\balfabetico\b|"',
    re.IGNORECASE,
)


def _validate_signed_composite_source_agreement(
    rule: SignedMonetaryCompositeRule,
    field: RecordDesignIntermediateField,
    identity: RenderProfileDesignIdentity,
) -> None:
    """Verify a reviewed rule against source prose without deriving policy from it."""
    exact_whole_digits = source_stated_composite_integer_digits_for(field, identity)
    if exact_whole_digits is not None:
        if (rule.integer_digits, rule.decimal_digits, rule.sign_policy) != (
            exact_whole_digits,
            2,
            "blank-or-n-leading",
        ):
            raise RegistryValidationError("signed monetary composite rule conflicts with the complete source reading")
        return
    definition = _signed_composite_source_definition(field)
    _validate_composite_sign_statement(definition)
    magnitude_digits = _validate_composite_free_prose(definition, field)
    _validate_composite_geometry(rule, field, definition, identity, magnitude_digits=magnitude_digits)


def _signed_composite_source_definition(field: RecordDesignIntermediateField) -> re.Match[str]:
    if field.source_cell is not None or normalise_aeat_type(field.aeat_type) not in {"alfanumerico", "numerico"}:
        raise RegistryValidationError("signed monetary composite requires an unsplit PDF amount anchor")
    source_text = field.content or ""
    for quote in ("“", "”", "«", "»", "�"):
        source_text = source_text.replace(quote, '"')
    ascii_text = unicodedata.normalize("NFKD", source_text).encode("ascii", "ignore").decode("ascii")
    normalised_source = re.sub(r'"+', '"', " ".join(ascii_text.split()))
    normalised_source = _BOE_PAGE_FURNITURE_RE.sub(" ", normalised_source).strip()
    definition = _COMPOSITE_DEFINITION_RE.fullmatch(normalised_source)
    if definition is None:
        raise RegistryValidationError(
            "signed monetary composite source must exactly match the reviewed complete wire definition"
        )
    return definition


def _validate_composite_sign_statement(definition: re.Match[str]) -> None:
    if normalise_aeat_type(definition.group("sign_nature")) != "alfabetico":
        raise RegistryValidationError("signed monetary composite source sign slot must be alphabetic")
    statement = _COMPOSITE_SIGN_STATEMENT_RE.fullmatch(definition.group("sign_statement"))
    if statement is None:
        raise RegistryValidationError("signed monetary composite source sign statement is not a reviewed form")
    # Prose spelling and case are normalized by the grammar, but the wire token
    # is not: the existing codec emits uppercase N.
    if (statement.group("token_after") or statement.group("token_first")) != "N":
        raise RegistryValidationError("signed monetary composite source must declare uppercase N as its wire token")
    condition = statement.group("condition_first") or statement.group("condition_after")
    negative = _COMPOSITE_NEGATIVE_CONDITION_RE.fullmatch(condition)
    if negative is None:
        if condition != _COMPOSITE_REINTEGRO_CONDITION:
            raise RegistryValidationError("signed monetary composite source sign condition is not a reviewed form")
        return
    subject = negative.group("subject")
    _require_descriptive_composite_prose(subject)
    if re.search(r"\bno\b", subject, re.IGNORECASE) is not None:
        raise RegistryValidationError("signed monetary composite source sign condition is negated")


def _validate_composite_free_prose(definition: re.Match[str], field: RecordDesignIntermediateField) -> int | None:
    """Classify every free sentence; return the magnitude width the source states, if any."""
    _validate_composite_segment(definition.group("framing"), width_nature="alfanumerico", width=field.length)
    magnitude_width = int(definition.group("magnitude_end")) - int(definition.group("magnitude_start")) + 1
    stated = _validate_composite_segment(
        definition.group("magnitude_body"),
        width_nature="numerico",
        width=magnitude_width,
        magnitude=True,
    )
    _validate_composite_segment(definition.group("interstitial"), width_nature=None, width=None)
    _validate_composite_segment(definition.group("trailer"), width_nature=None, width=None)
    integer_qualifier = definition.group("integer_qualifier") or ""
    decimal_qualifier = definition.group("decimal_qualifier") or ""
    _require_descriptive_composite_prose(integer_qualifier)
    if integer_qualifier.casefold() != decimal_qualifier.casefold():
        raise RegistryValidationError("signed monetary composite source partition descriptions do not agree")
    return stated


def _validated_composite_width(
    width_statement: re.Match[str],
    *,
    width_nature: str | None,
    stated: int | None,
    width: int | None,
) -> int:
    """Admit one source width only in its own slot and against the exact anchor."""
    if width_nature is None or stated is not None or width_statement.group("nature").casefold() != width_nature:
        raise RegistryValidationError("signed monetary composite source states a width outside its slot")
    parsed = int(width_statement.group("digits"))
    if parsed != width:
        raise RegistryValidationError("signed monetary composite source width conflicts with its anchor")
    return parsed


def _validate_composite_segment(
    segment: str | None,
    *,
    width_nature: str | None,
    width: int | None,
    magnitude: bool = False,
) -> int | None:
    stated: int | None = None
    for sentence in _composite_sentences(segment):
        width_statement = _COMPOSITE_WIDTH_RE.fullmatch(sentence)
        if width_statement is not None:
            stated = _validated_composite_width(
                width_statement,
                width_nature=width_nature,
                stated=stated,
                width=width,
            )
            continue
        if (
            _COMPOSITE_CURRENCY_RE.fullmatch(sentence)
            or _COMPOSITE_SIGNED_SUM_RE.fullmatch(sentence)
            or sentence == _COMPOSITE_PERCEPTOR_SIGNED_SUM
        ):
            continue
        described = (
            _COMPOSITE_UNSIGNED_MAGNITUDE_RE.fullmatch(sentence)
            or _COMPOSITE_SUM_MAGNITUDE_RE.fullmatch(sentence)
            or _COMPOSITE_MAGNITUDE_SUBJECT_RE.fullmatch(sentence)
            if magnitude
            else None
        )
        _require_descriptive_composite_prose(sentence if described is None else described.group("rest") or "")
    return stated


def _composite_sentences(segment: str | None) -> tuple[str, ...]:
    if not segment:
        return ()
    sentences = cast(list[str], re.split(r"(?<=[.;])\s+", segment.strip()))
    parts = (part.strip(" .;") for part in sentences)
    return tuple(part for part in parts if part)


def _require_descriptive_composite_prose(text: str) -> None:
    if _COMPOSITE_DESCRIPTIVE_WIRE_TERMS.search(_COMPOSITE_QUOTED_FIELD_NAME_RE.sub(" ", text)) is not None:
        raise RegistryValidationError("signed monetary composite source non-policy framing contains a wire instruction")


def _validate_composite_geometry(
    rule: SignedMonetaryCompositeRule,
    field: RecordDesignIntermediateField,
    definition: re.Match[str],
    identity: RenderProfileDesignIdentity,
    *,
    magnitude_digits: int | None,
) -> None:
    sign_position = int(definition.group("sign_position"))
    magnitude_start = int(definition.group("magnitude_start"))
    magnitude_end = int(definition.group("magnitude_end"))
    integer_start, integer_end = adjudicated_integer_range_for(
        source_ref=identity.source_ref,
        source_sha256=identity.source_sha256,
        sheet=field.sheet,
        source_row=field.source_row,
        published_integer_range=(int(definition.group("integer_start")), int(definition.group("integer_end"))),
    )
    decimal_start = int(definition.group("decimal_start"))
    decimal_end = int(definition.group("decimal_end"))
    digits = magnitude_end - magnitude_start + 1 if magnitude_digits is None else magnitude_digits
    bounds_match = _composite_bounds_match(
        field,
        sign_position=sign_position,
        magnitude_start=magnitude_start,
        magnitude_end=magnitude_end,
        magnitude_digits=digits,
        expected_end=field.offset + field.length - 1,
    )
    parts_match = _composite_parts_match(
        rule,
        magnitude_start=magnitude_start,
        magnitude_end=magnitude_end,
        magnitude_digits=digits,
        integer_start=integer_start,
        integer_end=integer_end,
        decimal_start=decimal_start,
        decimal_end=decimal_end,
    )
    if not bounds_match or not parts_match:
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
