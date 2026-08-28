"""Strict Pydantic records for the centralized user-profile schema.

Each schema section declares a :class:`SensitivityClass` that governs
the encryption tier applied when the section's data is persisted to the
secure DB backend.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from functools import lru_cache
from typing import Annotated, Final, Self

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Modelo
from ...core.classification import SensitivityClass
from ...core.decimal import coerce_decimal_strict
from ...core.parsing import parse_bool, parse_iso8601_date
from .errors import UserProfileNotFoundError, UserProfileValidationError

_SchemaId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_.-]*$"),
]
_SectionKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$"),
]
_FieldKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$"),
]
_FieldPath = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=3,
        max_length=160,
        pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+$",
    ),
]
_Selector = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=256),
]
#: A canonical dotted path carrying at least one ``{placeholder}`` segment.
#: Shaped like ``_FieldPath`` plus braces, so a pattern that accidentally
#: carries no placeholder -- or stray uppercase / whitespace -- is refused at
#: schema load rather than silently declaring a single literal path.
_DerivedSelectorPattern = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=3,
        max_length=160,
        pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z0-9_{}]+)+$",
    ),
]
_Description = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=512),
]


class ProfileFieldType(StrEnum):
    """Closed catalogue of field types allowed by the profile schema TOML."""

    STRING = "string"
    BOOLEAN = "boolean"
    INTEGER = "integer"
    DECIMAL = "decimal"
    MONEY = "money"
    DATE = "date"
    EMAIL = "email"
    ENUM = "enum"
    ARRAY = "array"
    OBJECT = "object"


class ProfileSnapshotPolicy(StrEnum):
    """Accepted profile snapshot stale-check policies."""

    IMMUTABLE_SECURE_SNAPSHOT_HASH = "immutable_secure_snapshot_hash"


class ProfileRemovePolicy(StrEnum):
    """Accepted profile removal policies."""

    LIVE_PROFILE_TOMBSTONE_RETAIN_SNAPSHOTS = "live_profile_tombstone_retain_snapshots"


def _parse_str_enum(enum_type: type[StrEnum], value: object) -> object:
    if isinstance(value, enum_type):
        return value
    if isinstance(value, str):
        return enum_type(value)
    return value


def _parse_sensitivity(value: object) -> object:
    if isinstance(value, SensitivityClass):
        return value
    if isinstance(value, str):
        return SensitivityClass(value)
    return value


class ProfileFieldDefinition(BaseModel):
    """One field declared inside a user-profile schema section."""

    model_config = _STRICT_FROZEN

    key: _FieldKey
    type: ProfileFieldType
    required: bool = False
    nullable: bool = False
    sensitivity: SensitivityClass
    effective_dated: bool = False
    description: _Description
    enum_values: tuple[str, ...] = Field(default=())
    model_selectors: tuple[_Selector, ...] = Field(default=())
    #: Modelos that require this field even though it is not globally required.
    #:
    #: ``required`` is a property of the field across the whole profile: it
    #: drives completeness, overview and presentation, so setting it to satisfy
    #: one modelo demands the fact from every taxpayer, including those with no
    #: such obligation. This axis carries the modelo-scoped requirement instead,
    #: and ONLY the filing-preflight walk consults it.
    required_for_modelos: tuple[Modelo, ...] = Field(default=())
    schedule_predicates: tuple[_Selector, ...] = Field(default=())
    legal_refs: tuple[_Description, ...] = Field(default=())
    minimum: Decimal | None = None
    maximum: Decimal | None = None

    @field_validator("type", mode="before")
    @classmethod
    def _parse_type(cls, value: object) -> object:
        return _parse_str_enum(ProfileFieldType, value)

    @field_validator("required_for_modelos", mode="before")
    @classmethod
    def _hydrate_required_for_modelos(cls, value: object) -> object:
        """Hydrate the free-form registry tokens into typed modelo members."""
        if isinstance(value, str):
            raise UserProfileValidationError("required_for_modelos must be a sequence of modelo ids")
        if isinstance(value, Iterable):
            return tuple(_parse_str_enum(Modelo, item) for item in value)
        return value

    @field_validator("sensitivity", mode="before")
    @classmethod
    def _coerce_sensitivity(cls, value: object) -> object:
        return _parse_sensitivity(value)

    @field_validator("minimum", "maximum", mode="before")
    @classmethod
    def _parse_decimal_bound(cls, value: object) -> object:
        if value is None or isinstance(value, Decimal):
            return value
        if isinstance(value, str | int):
            try:
                return coerce_decimal_strict(value)
            except (InvalidOperation, ValueError) as exc:
                raise UserProfileValidationError(f"invalid decimal bound {value!r}") from exc
        return value

    @model_validator(mode="after")
    def _validate_enum_values(self) -> Self:
        if self.type is ProfileFieldType.ENUM and not self.enum_values:
            raise UserProfileValidationError(f"field {self.key!r}: enum fields must declare enum_values")
        if self.type is not ProfileFieldType.ENUM and self.enum_values:
            raise UserProfileValidationError(f"field {self.key!r}: enum_values are only valid for enum fields")
        if len(set(self.enum_values)) != len(self.enum_values):
            raise UserProfileValidationError(f"field {self.key!r}: duplicate enum_values are not allowed")
        numeric_types = {ProfileFieldType.INTEGER, ProfileFieldType.DECIMAL, ProfileFieldType.MONEY}
        if (self.minimum is not None or self.maximum is not None) and self.type not in numeric_types:
            raise UserProfileValidationError(f"field {self.key!r}: numeric bounds are only valid for numeric fields")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise UserProfileValidationError(f"field {self.key!r}: minimum must be less than or equal to maximum")
        return self


class ProfileSectionDefinition(BaseModel):
    """A top-level section in the user-profile schema."""

    model_config = _STRICT_FROZEN

    key: _SectionKey
    title: _Description
    sensitivity: SensitivityClass
    effective_dated: bool = False
    repeatable: bool = False
    fields: tuple[ProfileFieldDefinition, ...] = Field(min_length=1)

    @field_validator("sensitivity", mode="before")
    @classmethod
    def _coerce_sensitivity(cls, value: object) -> object:
        return _parse_sensitivity(value)

    @model_validator(mode="after")
    def _validate_unique_fields(self) -> Self:
        keys = tuple(field.key for field in self.fields)
        if len(set(keys)) != len(keys):
            duplicates = sorted({key for key in keys if keys.count(key) > 1})
            raise UserProfileValidationError(f"section {self.key!r}: duplicate field keys {duplicates!r}")
        return self


#: Regex fragment each declared derived-selector placeholder expands to.
#:
#: ``filing_year`` is deliberately ``\d{4}`` rather than a wildcard. Two of the
#: declared patterns are prefixes of one another
#: (``descendientes_minimos_aggregate_{filing_year}`` and the ``_autonomico_``
#: variant), so under a looser fragment the shorter pattern would swallow the
#: longer one's paths -- every gate would stay green while the longer pattern's
#: coverage silently vanished.
_DERIVED_SELECTOR_PLACEHOLDERS: Final[Mapping[str, str]] = {"filing_year": r"\d{4}"}

_DERIVED_SELECTOR_PLACEHOLDER_RE: Final[re.Pattern[str]] = re.compile(r"\{([^{}]+)\}")


@lru_cache(maxsize=64)
def _compiled_derived_selector_pattern(pattern: str) -> re.Pattern[str]:
    r"""Compile a declared derived-selector pattern into an anchored regex.

    Literal segments between placeholders are individually :func:`re.escape`-d
    and the placeholder fragments spliced in raw. That ordering matters:
    escaping the whole template first would mangle the fragments' own regex
    metacharacters. The result carries a terminal ``\Z`` anchor so a pattern
    can never match a longer sibling path.

    An unrecognised placeholder raises rather than matching anything, so a
    typo in the schema TOML fails the load instead of quietly widening or
    narrowing the namespace.

    Raises:
        :class:`UserProfileValidationError`: If *pattern* names a placeholder
            with no declared regex fragment.
    """
    parts: list[str] = []
    position = 0
    for match in _DERIVED_SELECTOR_PLACEHOLDER_RE.finditer(pattern):
        parts.append(re.escape(pattern[position : match.start()]))
        token = match.group(1)
        fragment = _DERIVED_SELECTOR_PLACEHOLDERS.get(token)
        if fragment is None:
            raise UserProfileValidationError(
                f"derived selector pattern {pattern!r} names placeholder {{{token}}}, "
                f"which has no declared regex fragment; declared placeholders are "
                f"{sorted(_DERIVED_SELECTOR_PLACEHOLDERS)}",
            )
        parts.append(fragment)
        position = match.end()
    parts.append(re.escape(pattern[position:]))
    return re.compile("".join(parts) + r"\Z")


class ProfileDerivedSelectorDefinition(BaseModel):
    """A namespace of profile paths the calculation engine owns and computes.

    A derived path is NOT taxpayer data. Its value is computed at calculate
    time from the source facts named in :attr:`derived_from`, so the schema
    declares the namespace as a pattern rather than one field per filing year.
    The pattern exists so registry binding selectors targeting these paths
    still resolve once the per-year field declarations are gone.

    This is a DECLARATION of engine ownership, never a resolution route for
    values: nothing here supplies a value to the binding resolver.
    """

    model_config = _STRICT_FROZEN

    pattern: _DerivedSelectorPattern
    derived_from: tuple[_FieldPath, ...] = Field(min_length=1)
    entry_surface: _Description
    description: _Description
    legal_refs: tuple[_Description, ...] = ()

    @model_validator(mode="after")
    def _validate_pattern_compiles(self) -> Self:
        # Compile eagerly so an unknown placeholder is a schema-load failure
        # rather than a silent non-match discovered at validation time.
        _compiled_derived_selector_pattern(self.pattern)
        return self

    def matches(self, selector: str) -> bool:
        """Return whether *selector* falls inside this derived namespace."""
        return _compiled_derived_selector_pattern(self.pattern).match(selector) is not None


def derived_selector_for_path(
    path: str,
    derived_selectors: Iterable[ProfileDerivedSelectorDefinition],
) -> ProfileDerivedSelectorDefinition | None:
    """Return the declared namespace owning *path*, or ``None`` if it is not derived.

    The single written-once judgment on whether a profile path is engine-derived.
    Every consumer -- the registry contract validator and the write-door refusal --
    asks through here, so the two can never disagree about what "derived" means.

    Deliberately NOT routed through :func:`profile_value_refusal`, which is the
    authority on whether a VALUE may be stored at a declared field. That judgment
    is value-scoped against a :class:`ProfileFieldDefinition` and expressly
    declines to judge absence; this one is path-scoped, refuses every value
    including a clear, and must keep answering once the per-year field
    declarations are gone and there is no declaration left to judge against. The
    two live in one module because they are both schema-level judgments, not
    because they are the same judgment.

    The definition is returned rather than a bare bool so a caller can name the
    surface that edits the real source facts without re-scanning the namespace.
    """
    for definition in derived_selectors:
        if definition.matches(path):
            return definition
    return None


class ProfileSchemaDefinition(BaseModel):
    """The committed centralized user-profile schema."""

    model_config = _STRICT_FROZEN

    id: _SchemaId
    version: int = Field(ge=1)
    title: _Description
    snapshot_policy: ProfileSnapshotPolicy
    remove_policy: ProfileRemovePolicy
    sections: tuple[ProfileSectionDefinition, ...] = Field(min_length=1)
    derived_selectors: tuple[ProfileDerivedSelectorDefinition, ...] = ()

    @field_validator("snapshot_policy", mode="before")
    @classmethod
    def _parse_snapshot_policy(cls, value: object) -> object:
        return _parse_str_enum(ProfileSnapshotPolicy, value)

    @field_validator("remove_policy", mode="before")
    @classmethod
    def _parse_remove_policy(cls, value: object) -> object:
        return _parse_str_enum(ProfileRemovePolicy, value)

    @model_validator(mode="after")
    def _validate_unique_sections(self) -> Self:
        keys = tuple(section.key for section in self.sections)
        if len(set(keys)) != len(keys):
            duplicates = sorted({key for key in keys if keys.count(key) > 1})
            raise UserProfileValidationError(f"duplicate section keys {duplicates!r}")
        return self

    @property
    def field_paths(self) -> tuple[str, ...]:
        """Canonical dotted field paths declared by the schema."""
        return tuple(f"{section.key}.{field.key}" for section in self.sections for field in section.fields)

    def section(self, key: str) -> ProfileSectionDefinition:
        """Return a :class:`ProfileSectionDefinition` by canonical section key."""
        for section in self.sections:
            if section.key == key:
                return section
        raise UserProfileNotFoundError(f"unknown user-profile section {key!r}")

    def field(self, path: _FieldPath) -> ProfileFieldDefinition:
        """Return a field by canonical dotted path.

        Returns:
            The :class:`ProfileFieldDefinition` for the given path.
        """
        section_key, field_key = path.split(".", 1)
        section = self.section(section_key)
        for field in section.fields:
            if field.key == field_key:
                return field
        raise UserProfileNotFoundError(f"unknown user-profile field {path!r}")

    def path_for_model_selector(self, selector: str) -> str | None:
        """Return the canonical dotted path of the field declaring ``selector``.

        The inverse of the ``model_selectors`` declaration. Surfaces that hold
        a selector token rather than a path - a deadline-engine gating key, a
        registry binding's consumed profile key - need the path before they can
        resolve the field's operator label and legal grounding, and every other
        schema lookup here runs path-first.

        Ambiguity is refused rather than guessed: the schema does not
        constrain a token to one declaring field, so a token declared by two
        fields has no single correct answer and returning either would
        mislabel one of them. An unknown token is likewise not an error - the
        callers mix selector tokens with identifiers from other namespaces and
        must be able to ask without knowing which they hold.

        Returns:
            The ``section.field`` path when exactly one field declares
            ``selector``, otherwise ``None``.
        """
        token = selector.strip()
        if not token:
            return None
        matches = [
            f"{section.key}.{field.key}"
            for section in self.sections
            for field in section.fields
            if token in field.model_selectors
        ]
        if len(matches) != 1:
            return None
        return matches[0]


NUMERIC_PROFILE_FIELD_TYPES: frozenset[ProfileFieldType] = frozenset(
    {ProfileFieldType.INTEGER, ProfileFieldType.DECIMAL, ProfileFieldType.MONEY},
)
"""The field types whose values are numbers, and whose bounds therefore bind.

Mirrors the set :meth:`ProfileFieldDefinition._validate_enum_values` already
uses to decide where ``minimum`` / ``maximum`` may be declared, so the types
that may CARRY a bound and the types that are CHECKED against one cannot
drift apart.
"""


def numeric_value_refusal(field: ProfileFieldDefinition, value: object) -> str | None:
    """Return why ``value`` fails ``field``'s numeric declaration, or ``None``.

    The single authority for "is this a legal value for this numeric field".
    It exists because the declaration was inert: ``minimum`` and ``maximum``
    were validated for their own coherence at schema build and then never
    compared to anything, so a participation percentage declared ``0..100``
    accepted ``999`` on write and carried it into an attribution calculation
    unchallenged. Both the write door and the readers that consume these
    facts ask this one function, rather than each forming its own opinion.

    Numbers are :class:`~decimal.Decimal` (or :class:`int`), never
    :class:`float`. These are financial quantities -- a participation
    percentage and an assigned base that divide a taxable amount between
    members -- so binary floating point is the wrong carrier: its rounding
    is invisible at the point of entry and shows up as a cent that does not
    reconcile in a filing. ``bool`` is rejected despite being an ``int``
    subclass, because ``True`` is an answer to a different question and
    would otherwise silently satisfy a numeric field as ``1``.

    Absence is not this rule's business. A ``None`` value is a cleared or
    unanswered field, which the required-field check judges; refusing it
    here would report one missing field as two unrelated faults.

    Non-finite values need no check: the fact carrier's own union rejects a
    ``NaN`` or infinite :class:`~decimal.Decimal` before it can be
    constructed, so an unorderable value cannot reach a bound comparison.

    Args:
        field: The declaration the value must satisfy.
        value: The value carried by the fact, after the fact carrier has
            restored its type.

    Returns:
        An instructive message naming the field and the range it accepts,
        or ``None`` when the value is admissible or the field is not
        numeric.
    """
    if field.type not in NUMERIC_PROFILE_FIELD_TYPES or value is None:
        return None
    accepted = _accepted_range_clause(field)
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        return f"{field.key} must be a number{accepted}; got {value!r}"
    if field.minimum is not None and value < field.minimum:
        return f"{field.key} must be a number{accepted}; got {value}"
    if field.maximum is not None and value > field.maximum:
        return f"{field.key} must be a number{accepted}; got {value}"
    return None


def boolean_value_refusal(field: ProfileFieldDefinition, value: object) -> str | None:
    """Return why ``value`` fails ``field``'s boolean declaration, or ``None``.

    The single authority for "is this a legal value for this boolean field",
    the counterpart to :func:`numeric_value_refusal`. It exists because the
    declaration was inert: a field declared ``boolean`` accepted ``banana``,
    ``placeholder`` and ``''`` on write and stored them unchallenged, while
    every reader then had to decide for itself what an unreadable value
    meant. Readers that resolve a stored boolean default an unreadable one
    to ``False`` -- safe only if a value this door admitted can always be
    read, which is what this function makes true.

    Readability, not spelling, is the test. A taxpayer answering ``sí`` is
    saying yes, and refusing that while accepting ``true`` would be a
    vocabulary rule dressed up as a type rule. The judgement therefore comes
    from :func:`~cadrumo.core.parsing.parse_bool`, the one boolean vocabulary
    the rest of the codebase already reads answers with, rather than a set
    spelled out here that could drift from it.

    A real :class:`bool` is admissible by construction: it needs no parsing
    and carries no ambiguity.

    Absence is not this rule's business. A ``None`` value is a cleared or
    unanswered field, which the required-field check judges. An empty string
    is NOT absence -- it is an answer that says nothing -- and is refused, as
    the enum and date declarations already refuse it.

    Args:
        field: The declaration the value must satisfy.
        value: The value carried by the fact, after the fact carrier has
            restored its type.

    Returns:
        An instructive message naming the field and what it accepts, or
        ``None`` when the value is admissible or the field is not boolean.
    """
    if field.type is not ProfileFieldType.BOOLEAN or value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, str) and parse_bool(value) is not None:
        return None
    return f"{field.key} must be a yes/no answer (true/false, sí/no, 1/0); got {value!r}"


class ProfileValueRefusalKind(StrEnum):
    """Which declaration a refused value failed.

    A closed set, because it is the join between the one rule that judges a
    value and the two surfaces that have to say something about the verdict:
    the validation service turns a kind into its issue code, and an operator
    surface turns the same kind into the sentence it shows and the editor it
    offers. Both read the kind rather than matching on the message, so the
    prose stays free to change without either one silently stopping working.
    """

    ENUM = "enum"
    DATE = "date"
    NUMERIC = "numeric"
    BOOLEAN = "boolean"
    EMAIL = "email"


class ProfileValueRefusal(BaseModel):
    """Why one value fails its field's declaration.

    Carries the kind as well as the message so a caller can classify the
    refusal without parsing the sentence: the codes an issue report uses and
    the copy an operator reads are both decided from
    :attr:`kind`.
    """

    model_config = _STRICT_FROZEN

    kind: ProfileValueRefusalKind
    message: str


_ISO_DATE_LAYOUT = re.compile(r"^\d{4}-\d{2}-\d{2}$")
"""The single accepted date layout: zero-padded ``YYYY-MM-DD``.

:meth:`datetime.date.fromisoformat` alone would also accept the compact
basic form (``19780315``), which nothing downstream canonicalises back to a
:class:`datetime.date`. Anchoring the extended hyphenated layout keeps every
persisted date fact in one shape.
"""


def date_value_refusal(field: ProfileFieldDefinition, value: object) -> str | None:
    """Return why ``value`` fails ``field``'s date declaration, or ``None``.

    The sibling of :func:`boolean_value_refusal` and
    :func:`numeric_value_refusal`, and here for the same reason: the rule
    lived only inside the validation service, so a surface wanting to refuse
    a bad date at the box the operator typed it into had nowhere to ask and
    would have had to restate the layout itself.

    A real :class:`datetime.date` is admissible by construction. A string is
    accepted only when it matches the zero-padded extended layout AND parses
    as a calendar day, which together reject a non-ISO layout
    (``15/03/1978``), the compact basic form (``19780315``), an impossible
    month or day (``1978-13-45``), a non-calendar day (``1978-02-30``), and
    plain garbage -- without any hand-rolled calendar maths.
    """
    if field.type is not ProfileFieldType.DATE or value is None:
        return None
    if isinstance(value, date):
        return None
    if isinstance(value, str) and _ISO_DATE_LAYOUT.match(value):
        try:
            parse_iso8601_date(value)
        except ValueError:
            return _invalid_date_message(field, value)
        return None
    return _invalid_date_message(field, value)


def _invalid_date_message(field: ProfileFieldDefinition, value: object) -> str:
    return f"{field.key} must be a valid ISO-8601 calendar date (YYYY-MM-DD); got {value!r}"


_EMAIL_SHAPE = re.compile(r"^[^@\s]+@[^@\s.]+(?:\.[^@\s.]+)+$")
"""Deliberately permissive: one ``@``, something either side, a dotted domain.

Not an RFC 5322 grammar, and not an attempt at one. The addresses this field
holds are the taxpayer's own contact details, and the cost of the two errors
is asymmetric: refusing a legitimate address makes the field uneditable for
whoever holds it, while admitting an odd-but-real one costs nothing here,
because nothing in this application sends mail. A strict grammar buys
accuracy on inputs nobody types and loses on the unusual ones people
genuinely have.

So this catches the entry that is plainly not an address — no ``@`` at all, a
bare local part, whitespace in the middle, a domain with no dot — and admits
everything else. Quoted local parts, plus-addressing, and internationalised
labels all pass.
"""


def email_value_refusal(field: ProfileFieldDefinition, value: object) -> str | None:
    """Return why ``value`` fails ``field``'s email declaration, or ``None``.

    The declaration was inert before this: a field declared ``email``
    accepted ``banana`` and stored it, so the one type in the schema that
    names its own content format was the one type nothing checked.

    Only a string can be an address. A non-string reaching an ``email`` field
    is a fact carrier that promoted the value to something else — a bare
    numeral, a date-shaped token — and is refused as the same fault rather
    than allowed through for want of a branch.
    """
    if field.type is not ProfileFieldType.EMAIL or value is None:
        return None
    if isinstance(value, str) and _EMAIL_SHAPE.match(value):
        return None
    return f"{field.key} must be an email address (name@example.com); got {value!r}"


def enum_value_refusal(field: ProfileFieldDefinition, value: object) -> str | None:
    """Return why ``value`` is outside ``field``'s declared token set, or ``None``.

    Comparison is exact rather than case-folded. The declared sets are
    case-significant and inconsistent between fields by design -- some carry
    AEAT's own uppercase tokens, others the profile's lowercase vocabulary --
    so folding would silently admit a spelling the declaring authority does
    not use.
    """
    if field.type is not ProfileFieldType.ENUM or value is None:
        return None
    if str(value) in field.enum_values:
        return None
    return f"{field.key} must be one of {list(field.enum_values)}; got {value!r}"


def profile_value_refusal(field: ProfileFieldDefinition, value: object) -> ProfileValueRefusal | None:
    """Return why ``value`` fails ``field``'s declaration, or ``None``.

    THE authority on whether a value may be stored at a field, gathering the
    four per-type rules behind one call so that every surface asks the same
    question in the same words. The write door asks it to build its issue
    report; an operator surface asks it to refuse a value at the box it was
    typed into, before a round trip to storage. Two surfaces judging a value
    apart is how one comes to accept what the other rejects, and the operator
    meets that as a dialog that closes on a value the record then refuses.

    Absence is not this rule's business. A ``None`` value is a cleared or
    unanswered field, which the required-field check judges.

    Args:
        field: The declaration the value must satisfy.
        value: The value carried by the fact, after the fact carrier has
            restored its type. Passing a raw string a fact would have
            promoted (``"true"``, ``"1978-03-15"``) asks a different question
            from the one the write door asks.

    Returns:
        A :class:`ProfileValueRefusal` naming what failed and what the field
        accepts, or ``None`` when the value is admissible.
    """
    if value is None:
        return None
    for kind, refusal in (
        (ProfileValueRefusalKind.ENUM, enum_value_refusal(field, value)),
        (ProfileValueRefusalKind.NUMERIC, numeric_value_refusal(field, value)),
        (ProfileValueRefusalKind.BOOLEAN, boolean_value_refusal(field, value)),
        (ProfileValueRefusalKind.DATE, date_value_refusal(field, value)),
        (ProfileValueRefusalKind.EMAIL, email_value_refusal(field, value)),
    ):
        if refusal is not None:
            return ProfileValueRefusal(kind=kind, message=refusal)
    return None


def _accepted_range_clause(field: ProfileFieldDefinition) -> str:
    """Render the declared bounds as an operator-facing phrase.

    Both bounds are INCLUSIVE, and the wording says so: a percentage
    declared ``0..100`` must accept exactly ``0`` and exactly ``100``, and
    a refusal that does not state which end is included leaves the operator
    guessing at the boundary that just refused them.
    """
    minimum, maximum = field.minimum, field.maximum
    if minimum is not None and maximum is not None:
        return f" from {minimum} to {maximum} inclusive"
    if minimum is not None:
        return f" no less than {minimum}"
    if maximum is not None:
        return f" no greater than {maximum}"
    return ""
