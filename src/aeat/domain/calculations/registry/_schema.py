"""Strict schema authority for AEAT registry definitions."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from enum import StrEnum
from itertools import pairwise
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator

from ....core.classification import SensitivityClass
from ....core.identity._documents import IdentityError
from ....core.identity._tax_id import validate_spanish_tax_id
from ._aeat_hosts import first_aeat_host
from ._errors import RegistryValidationError
from ._ids import (
    ApplicationLinkId,
    BindingId,
    CasillaId,
    ConstructId,
    CrossReferenceId,
    DeadlineWindowId,
    DependencyClassificationId,
    ExportFieldId,
    ExportLayoutId,
    ExtractionProfileId,
    FormulaId,
    LegalRefId,
    ModeloId,
    OracleId,
    ParameterId,
    RecordId,
    RelationId,
    RevisionId,
    SourceRefId,
    SupportRemovalDecisionId,
    VerificationExpectationId,
    WorkbookFixtureId,
    WorkbookParityRefId,
)


def _coerce_decimal(value: object) -> object:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool | float):
        raise RegistryValidationError("decimal values must not be booleans or floats")
    if isinstance(value, int | str):
        return Decimal(value)
    return value


DecimalValue = Annotated[Decimal, BeforeValidator(_coerce_decimal)]


def _validate_nif_string(value: object) -> object:
    """Validate a Spanish NIF / NIE / CIF identifier and return its canonical form.

    Delegates to the shared `validate_spanish_tax_id` algorithm in
    `aeat.core.identity._tax_id` and re-raises domain `IdentityError`
    as `RegistryValidationError` so the schema boundary surfaces
    identifier-format problems through its established error type.
    """

    if not isinstance(value, str):
        raise RegistryValidationError(f"NIF value must be a string, got {type(value).__name__}")
    try:
        return validate_spanish_tax_id(value)
    except IdentityError as exc:
        raise RegistryValidationError(f"invalid NIF / NIE / CIF identifier: {exc}") from exc


NifString = Annotated[str, BeforeValidator(_validate_nif_string)]
"""Canonical Spanish tax-identifier string.

Used as the value type for casillas declaring `data_type = "nif"`,
and by any cross-domain consumer (filing draft assembly, oracle
replay, export layouts) that needs to validate a NIF, NIE, or CIF
identifier independently of a casilla declaration.
"""


class InputKind(StrEnum):
    """Registry-authoritative classification of how a casilla value is supplied.

    Each member's string value matches the TOML literal used in registry
    source files so serialisation is transparent across every persistence
    boundary (TOML, JSON, SQL, CLI).
    """

    MANUAL = "manual"
    BOUND = "bound"
    COMPUTED = "computed"
    INFORMATIONAL = "informational"


def _coerce_input_kind(value: object) -> object:
    """Coerce a TOML string literal to the canonical InputKind member.

    Accepts an ``InputKind`` instance directly (no-op) or a plain string
    matching one of the declared member values.  Rejects non-string and
    non-member inputs at the schema boundary so every persisted and
    deserialised casilla carries a typed enum value.
    """
    if isinstance(value, InputKind):
        return value
    if isinstance(value, str):
        try:
            return InputKind(value)
        except ValueError:
            raise RegistryValidationError(
                f"input_kind {value!r} is not a recognised InputKind member; "
                f"expected one of {[m.value for m in InputKind]}"
            ) from None
    raise RegistryValidationError(
        f"input_kind must be a string, got {type(value).__name__!r}"
    )


InputKindValue = Annotated[InputKind, BeforeValidator(_coerce_input_kind)]
"""Annotated InputKind that coerces TOML string literals to enum members.

Use this as the field type on pydantic models that ingest TOML or JSON
payloads where ``input_kind`` is stored as a plain string.
"""


def _coerce_modelo_year(value: object) -> object:
    """Coerce a fiscal-year input to an int within the registry-supported window.

    Accepts an int directly or a non-empty string of digits. Rejects
    booleans (which are int subclasses in Python), floats, and any
    value outside ``RegistrySnapshotRef.modelo_year``'s declared
    ``ge=2000, le=2099`` range.
    """

    if isinstance(value, bool):
        raise RegistryValidationError("year value must not be a boolean")
    if isinstance(value, float):
        raise RegistryValidationError("year value must not be a float")
    if isinstance(value, str):
        if not value.strip():
            raise RegistryValidationError("year value must not be blank")
        try:
            value = int(value)
        except ValueError as exc:
            raise RegistryValidationError(f"year value {value!r} is not a valid integer") from exc
    return value


ModeloYear = Annotated[int, BeforeValidator(_coerce_modelo_year), Field(ge=2000, le=2099)]
"""Canonical fiscal-year integer for the registry boundary.

Mirrors the ``RegistrySnapshotRef.modelo_year`` bound so a casilla
declaring ``data_type = "year"`` and the snapshot coordinate agree
on the supported window. Consumers that need to validate a year
value independently of a casilla declaration should type their
field as ``ModeloYear``.
"""


_PERIOD_CODE_RE = re.compile(r"^(?:[1-4]T|[1-4]P|0A|0[1-9]|1[0-2]|EXT-[1-4]T|AD-HOC|EVENT-\d+)$")


def _validate_period_code(value: object) -> object:
    """Validate a filing-period code against the registry-supported set.

    Accepted forms (from the fiscal-period inventory):

    - ``1T``-``4T``: quarterly (canonical).
    - ``1P``-``4P``: corporate-tax (IS) instalment periods (modelo 202).
    - ``0A``: annual.
    - ``01``-``12``: monthly.
    - ``EXT-1T``-``EXT-4T``: OSS extra-Union scheme quarters (modelo 369).
    - ``AD-HOC``: ad-hoc / event-driven (modelos 308, 309).
    - ``EVENT-N``: numbered event filings.

    Modellers introducing a new form must extend this validator.
    """

    if not isinstance(value, str):
        raise RegistryValidationError(f"period_code value must be a string, got {type(value).__name__}")
    if not _PERIOD_CODE_RE.match(value):
        raise RegistryValidationError(f"period_code value {value!r} does not match a supported filing-period form")
    return value


PeriodCode = Annotated[str, BeforeValidator(_validate_period_code)]
"""Canonical filing-period code for the registry boundary.

Used as the value type for casillas declaring
``data_type = "period_code"``, and by any cross-domain consumer
(snapshot coordinates, oracle replay, export layouts) that needs to
validate a period token independently of a casilla declaration.
"""


_COUNTRY_CODE_RE = re.compile(r"^[A-Z]{2}$")


def _validate_country_code(value: object) -> object:
    """Validate a two-character ISO 3166-1 alpha-2 country code.

    Format-only validation: enforces uppercase ASCII letters and
    exact length 2. Membership against the AEAT-supported country
    list is delegated to per-casilla `constraints.enum` declarations
    (Plan B) and to the semantic-role consistency layer (Plan C).
    Country casillas declaring `data_type = "country_code"` are
    expected to either (a) carry an `enum` constraint enumerating
    the supported codes, or (b) accept any ISO alpha-2 code with
    downstream business validation.
    """

    if not isinstance(value, str):
        raise RegistryValidationError(f"country_code value must be a string, got {type(value).__name__}")
    if not _COUNTRY_CODE_RE.match(value):
        raise RegistryValidationError(
            f"country_code value {value!r} must be a two-character uppercase ISO alpha-2 code"
        )
    return value


CountryCode = Annotated[str, BeforeValidator(_validate_country_code)]
"""Two-character country code for the registry boundary.

Used as the value type for casillas declaring
``data_type = "country_code"``. Membership against the
AEAT-supported country list is layered through per-casilla `enum`
constraints (Plan B) and semantic-role consistency (Plan C); this
alias enforces only the alpha-2 shape.
"""


_IBAN_SHAPE_RE = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$")


def _iban_mod_97(canonical: str) -> int:
    """Compute the IBAN mod-97 check residue for an already-canonical IBAN."""
    rearranged = canonical[4:] + canonical[:4]
    numeric = "".join(ch if ch.isdigit() else str(ord(ch) - ord("A") + 10) for ch in rearranged)
    return int(numeric) % 97


def _validate_iban_string(value: object) -> object:
    """Validate an IBAN: country code, check digits, BBAN, and mod-97 residue.

    The validator strips whitespace and hyphens, uppercases, then
    enforces ISO 13616 shape (`CC kk BBAN`, total 15-34 chars) and
    the mod-97 check (the integer formed by moving the leading
    four chars to the tail and converting letters to digits must be
    congruent to 1 mod 97).
    """

    if not isinstance(value, str):
        raise RegistryValidationError(f"iban value must be a string, got {type(value).__name__}")
    canonical = value.replace(" ", "").replace("-", "").upper()
    if not canonical:
        raise RegistryValidationError("iban value must not be blank")
    if not _IBAN_SHAPE_RE.match(canonical):
        raise RegistryValidationError(f"iban value {value!r} does not match the ISO 13616 shape")
    if _iban_mod_97(canonical) != 1:
        raise RegistryValidationError(f"iban value {value!r} fails the mod-97 check")
    return canonical


IbanString = Annotated[str, BeforeValidator(_validate_iban_string)]
"""Canonical IBAN string for the registry boundary.

Used as the value type for casillas declaring ``data_type = "iban"``
and by any cross-domain consumer that needs to validate an IBAN
independently of a casilla declaration.
"""


def _validate_name_string(value: object) -> object:
    """Validate a personal or entity name: non-empty unicode within length bounds."""

    if not isinstance(value, str):
        raise RegistryValidationError(f"name value must be a string, got {type(value).__name__}")
    stripped = value.strip()
    if not stripped:
        raise RegistryValidationError("name value must not be blank")
    if len(stripped) > 200:
        raise RegistryValidationError(f"name value exceeds 200 characters: {len(stripped)}")
    return stripped


PersonOrEntityName = Annotated[str, BeforeValidator(_validate_name_string)]
"""Personal or entity name for the registry boundary."""


_NIF_IVA_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{2,12}$")


def _validate_nif_iva_string(value: object) -> object:
    """Validate an intracomunitario NIF-IVA: ISO country prefix plus identifier body."""

    if not isinstance(value, str):
        raise RegistryValidationError(f"nif_iva value must be a string, got {type(value).__name__}")
    canonical = value.replace(" ", "").replace("-", "").upper()
    if not _NIF_IVA_RE.match(canonical):
        raise RegistryValidationError(
            f"nif_iva value {value!r} must start with a two-letter country code "
            "followed by 2-12 alphanumeric characters"
        )
    return canonical


NifIvaString = Annotated[str, BeforeValidator(_validate_nif_iva_string)]
"""Intracomunitario NIF-IVA string for the registry boundary."""


_CCAA_CODES = frozenset(
    {
        "01",
        "02",
        "03",
        "04",
        "05",
        "06",
        "07",
        "08",
        "09",
        "10",
        "11",
        "12",
        "13",
        "14",
        "15",
        "16",
        "17",
        "18",
        "19",
    }
)


def _validate_ccaa_code(value: object) -> object:
    """Validate an autonomous-community code against the AEAT-supported set."""

    if not isinstance(value, str):
        raise RegistryValidationError(f"ccaa_code value must be a string, got {type(value).__name__}")
    if value not in _CCAA_CODES:
        raise RegistryValidationError(
            f"ccaa_code value {value!r} is not in the supported AEAT autonomous-community set"
        )
    return value


CCAACode = Annotated[str, BeforeValidator(_validate_ccaa_code)]
"""Autonomous-community code for the registry boundary."""


_PROVINCE_CODE_RE = re.compile(r"^(0[1-9]|[1-4][0-9]|5[0-2])$")


def _validate_province_code(value: object) -> object:
    """Validate a Spanish province code (01-52)."""

    if not isinstance(value, str):
        raise RegistryValidationError(f"province_code value must be a string, got {type(value).__name__}")
    if not _PROVINCE_CODE_RE.match(value):
        raise RegistryValidationError(
            f"province_code value {value!r} must be a two-digit Spanish province code (01-52)"
        )
    return value


ProvinceCode = Annotated[str, BeforeValidator(_validate_province_code)]
"""Two-digit Spanish province code for the registry boundary."""


_POSTAL_CODE_RE = re.compile(r"^\d{5}$")


def _validate_postal_code(value: object) -> object:
    """Validate a Spanish postal code (five digits)."""

    if not isinstance(value, str):
        raise RegistryValidationError(f"postal_code value must be a string, got {type(value).__name__}")
    if not _POSTAL_CODE_RE.match(value):
        raise RegistryValidationError(f"postal_code value {value!r} must be a five-digit Spanish postal code")
    return value


PostalCode = Annotated[str, BeforeValidator(_validate_postal_code)]
"""Five-digit Spanish postal code for the registry boundary."""


_MUNICIPALITY_CODE_RE = re.compile(r"^\d{5}$")


def _validate_municipality_code(value: object) -> object:
    """Validate a five-digit INE municipality code."""

    if not isinstance(value, str):
        raise RegistryValidationError(f"municipality_code value must be a string, got {type(value).__name__}")
    if not _MUNICIPALITY_CODE_RE.match(value):
        raise RegistryValidationError(f"municipality_code value {value!r} must be a five-digit INE municipality code")
    return value


MunicipalityCode = Annotated[str, BeforeValidator(_validate_municipality_code)]
"""Five-digit INE municipality code for the registry boundary."""


_BIC_RE = re.compile(r"^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$")


def _validate_bic_string(value: object) -> object:
    """Validate a SWIFT BIC (ISO 9362): 8 or 11 characters."""

    if not isinstance(value, str):
        raise RegistryValidationError(f"bic value must be a string, got {type(value).__name__}")
    canonical = value.replace(" ", "").upper()
    if not _BIC_RE.match(canonical):
        raise RegistryValidationError(f"bic value {value!r} must be 8 or 11 alphanumeric characters per ISO 9362")
    return canonical


BicString = Annotated[str, BeforeValidator(_validate_bic_string)]
"""SWIFT BIC for the registry boundary."""


_DATE_DDMMAAAA_RE = re.compile(r"^(0[1-9]|[12]\d|3[01])(0[1-9]|1[0-2])\d{4}$")
_DATE_ISO_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")


def _validate_calendar_date(value: object) -> object:
    """Validate a calendar date in either ISO 8601 or AEAT `ddmmaaaa` form."""

    if not isinstance(value, str):
        raise RegistryValidationError(f"date value must be a string, got {type(value).__name__}")
    if not (_DATE_ISO_RE.match(value) or _DATE_DDMMAAAA_RE.match(value)):
        raise RegistryValidationError(f"date value {value!r} must be ISO 8601 (yyyy-mm-dd) or AEAT ddmmaaaa")
    return value


CalendarDate = Annotated[str, BeforeValidator(_validate_calendar_date)]
"""Calendar date string in ISO 8601 or AEAT `ddmmaaaa` form."""

_WORKBOOK_CELL_REF_RE = re.compile(r"^(?:(?P<sheet>'[^']+'|[^!]+)!)?(?P<coordinate>\$?[A-Z]{1,3}\$?\d+)$")


def _validate_workbook_cell_ref_str(value: object) -> object:
    if isinstance(value, str) and not _WORKBOOK_CELL_REF_RE.match(value):
        raise RegistryValidationError(f"invalid workbook cell reference {value!r}")
    return value


WorkbookCellRefStr = Annotated[str, BeforeValidator(_validate_workbook_cell_ref_str)]


BindingSelectorValue = str | int | DecimalValue | bool | tuple[str, ...]
"""Closed union of the value shapes a binding-selector entry can hold.

The selector field on :class:`DataBindingDefinition` and related
selector fields on relation definitions store this union. Per-source
typed selector models (declared in :mod:`_bindings`) consume the
raw mapping and re-validate against a strict frozen schema for the
binding's declared ``source``; the snapshot-time
``_validate_binding_selector_shapes`` gate runs that check on every
binding once at snapshot build.
"""

BindingSelectorMap = Mapping[str, BindingSelectorValue]
"""Mapping shape for an as-stored binding selector.

Named alias rather than an inline ``Mapping[str, ...]`` so consumer
code can express the type intent and discover the per-source typed
companion models declared in :mod:`_bindings` via the alias name.
"""


def _coerce_sensitivity_class(value: object) -> object:
    if isinstance(value, SensitivityClass):
        return value
    if isinstance(value, str):
        return SensitivityClass(value)
    return value


SensitivityClassField = Annotated[SensitivityClass, BeforeValidator(_coerce_sensitivity_class)]

CalculationClass = Literal["filing", "informative", "summary"]
ModeloCapability = Literal["borrador", "renta_ledger_default"]
"""Discriminator for the calculation role of a ModeloDefinition.

- ``filing``: The modelo computes and submits filing-grade amounts.
  Most modelos fall into this class.
- ``informative``: The modelo collects and reports data but does not
  compute filing-grade amounts. Revisions must have empty ``formulas``
  and empty ``relations``; every casilla must be ``manual`` or
  ``informational``. Modelo 232 is the canonical example.
- ``summary``: The modelo aggregates other modelos (e.g. 390 over 303)
  and may declare cross-model relations but is not a filing modelo.
"""

ReviewStatus = Literal["reviewed"]
DateAxis = Literal["filing_period", "devengo_date", "transaction_date", "invoice_date", "submission_date"]
EvidenceTier = Literal[
    "legal_authority",
    "official_source_guidance",
    "executable_parity_evidence",
    "layout_authority",
]
LegalRefs = Annotated[tuple[LegalRefId, ...], Field(min_length=1)]
SourceRefs = Annotated[tuple[SourceRefId, ...], Field(min_length=1)]
SourceCitationText = Annotated[tuple[str, ...], Field(min_length=1)]
ContinuidadId = Annotated[
    str,
    Field(
        min_length=1,
        max_length=128,
        pattern=r"^[a-z0-9][a-z0-9._:-]*[a-z0-9]$|^[a-z0-9]$",
    ),
]
FormulaOperator = Literal[
    "add",
    "subtract",
    "multiply",
    "divide",
    "percent",
    "less_than",
    "less_equal",
    "greater_than",
    "greater_equal",
    "equal",
    "sum",
    "min",
    "max",
    "clamp",
    "negate",
    "copy",
    "if_then_else",
    "lookup_parameter",
    "lookup_bracket",
    "lookup_bracket_by_ccaa",
    "lookup_parameter_by_entity_type",
    "lookup_bracket_by_entity_type",
    "previous_period_value",
    "previous_period_sum",
    "cross_model_sum",
    "age_at_year_end",
]


class RegistryModel(BaseModel):
    """Strict frozen base for registry schema objects."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")


class RegistrySnapshotRef(RegistryModel):
    """Typed coordinates that identify a registry snapshot.

    Replaces opaque ``schema_version: str`` strings in persisted records
    (filing drafts, justificantes, etc.) with the four-axis registry
    coordinate ``(modelo, revision_id, modelo_year, period)``. A persisted
    record carrying a ``RegistrySnapshotRef`` can be re-resolved against
    the live registry catalogue with a single
    :meth:`ValidatedRegistryAuthority.snapshot` call; an opaque schema
    version cannot.
    """

    modelo: ModeloId
    revision_id: RevisionId
    modelo_year: int = Field(ge=2000, le=2099)
    period: str = Field(min_length=1, max_length=32)


class PeriodSelector(RegistryModel):
    years: tuple[int, ...] = ()
    year_from: int | None = None
    year_to: int | None = None
    periods: tuple[str, ...] = Field(min_length=1)

    @field_validator("periods")
    @classmethod
    def _periods_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("period_selector periods must be unique")
        return value

    @model_validator(mode="after")
    def _validate_year_selector(self) -> PeriodSelector:
        if self.years and self.year_from is not None:
            raise RegistryValidationError("period_selector must use either years or year_from/year_to")
        if not self.years and self.year_from is None:
            raise RegistryValidationError("period_selector must declare years or year_from")
        if len(set(self.years)) != len(self.years):
            raise RegistryValidationError("period_selector years must be unique")
        if self.year_to is not None and self.year_from is None:
            raise RegistryValidationError("period_selector year_to requires year_from")
        if self.year_from is not None and self.year_to is not None and self.year_to < self.year_from:
            raise RegistryValidationError("period_selector year_to must be on or after year_from")
        return self

    def includes_year(self, year: int) -> bool:
        """Return whether the selector covers a filing year."""

        if self.years:
            return year in self.years
        if self.year_from is None:
            return False
        return year >= self.year_from and (self.year_to is None or year <= self.year_to)


class TemporalApplicability(RegistryModel):
    date_axis: DateAxis
    valid_from: date
    valid_to: date | None = None
    period_selector: PeriodSelector | None = None

    @model_validator(mode="after")
    def _validate_window(self) -> TemporalApplicability:
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise RegistryValidationError("valid_to must be on or after valid_from")
        return self


class LegalReference(RegistryModel):
    id: LegalRefId
    evidence_tier: Literal["legal_authority"]
    authority: Literal["boe", "aeat", "eu", "autonomous_community", "other"]
    kind: Literal[
        "ley",
        "real_decreto",
        "real_decreto_ley",
        "orden",
        "reglamento",
        "directiva",
        "manual",
        "instruction",
    ]
    corpus_ref: str
    document_id: str
    article: str | None = None
    section: str | None = None
    permalink: str
    published_at: date | None = None
    effective_from: date
    effective_to: date | None = None
    consolidated_as_of: date | None = None
    review_status: ReviewStatus
    reviewed_at: date | None = None
    reviewed_by: str | None = None
    notes: str | None = None
    required_text: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _validate_legal_reference(self) -> LegalReference:
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise RegistryValidationError("legal reference effective_to must be on or after effective_from")
        if any(not item.strip() for item in self.required_text):
            raise RegistryValidationError("legal reference required_text entries must be non-empty")
        if len(set(self.required_text)) != len(self.required_text):
            raise RegistryValidationError("legal reference required_text entries must be unique")
        if "#" not in self.corpus_ref:
            raise RegistryValidationError(
                f"legal reference {self.id!r} corpus_ref must be of the form 'path#anchor' (got {self.corpus_ref!r})"
            )
        path_part, _, anchor_part = self.corpus_ref.partition("#")
        if not path_part or not anchor_part:
            raise RegistryValidationError(f"legal reference {self.id!r} corpus_ref must have non-empty path and anchor")
        return self


class SourceReference(RegistryModel):
    id: SourceRefId
    evidence_tier: EvidenceTier
    authority: Literal["aeat", "boe", "eu", "autonomous_community", "other"]
    kind: Literal["record_design", "manual_pdf", "instructions", "xsd", "dictionary", "form_spec"]
    corpus_path: str
    sha256: str = Field(min_length=64, max_length=64)
    bytes: int = Field(gt=0)
    retrieved_at: date
    published_at: date | None = None
    applies_from: date | None = None
    applies_to: date | None = None
    source_url: str
    review_status: ReviewStatus

    @model_validator(mode="after")
    def _validate_source_reference(self) -> SourceReference:
        if self.applies_to is not None and self.applies_from is not None and self.applies_to < self.applies_from:
            raise RegistryValidationError("source reference applies_to must be on or after applies_from")
        if "\\" in self.corpus_path or self.corpus_path.startswith(("/", ".")):
            raise RegistryValidationError("source reference corpus_path must be repository-relative POSIX style")
        return self

    @field_validator("sha256")
    @classmethod
    def _sha256_lower_hex(cls, value: str) -> str:
        lowered = value.lower()
        if lowered != value or any(char not in "0123456789abcdef" for char in value):
            raise RegistryValidationError("sha256 must be lowercase hexadecimal")
        return value


class LegalParameter(RegistryModel):
    """Authoritative numeric/categorical constant grounded in BOE law.

    Distinct from :class:`LegalReference` (which catalogues articles) and
    from per-modelo ``[[revisions.parameters]]`` blocks (which carry
    revision-scoped parameter values). A ``LegalParameter`` is a global
    constant tied to a specific legal article — e.g., the 19 percent
    urban-rental retention rate, the 1.1 percent imputación rate, the
    €400 8th-Directive refund threshold.

    Lives in ``registry/aeat/legal/*.toml`` under top-level
    ``[parameters."slug"]`` tables and is loaded into
    :class:`RegistryCatalogues.parameters` so consumers go through the
    single validated registry-load surface instead of opening the TOML
    file directly.
    """

    id: str
    evidence_tier: Literal["legal_authority"]
    value: str
    unit: str
    applies_to: str
    legal_refs: LegalRefs
    review_status: ReviewStatus
    reviewed_at: date | None = None
    reviewed_by: str | None = None
    notes: str | None = None


class SourceCitation(RegistryModel):
    source_ref: SourceRefId
    required_text: SourceCitationText

    @field_validator("required_text")
    @classmethod
    def _required_text_non_empty(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item.strip() for item in value):
            raise RegistryValidationError("source citation required_text entries must be non-empty")
        if len(set(value)) != len(value):
            raise RegistryValidationError("source citation required_text entries must be unique")
        return value


class BboxAnchorSpec(RegistryModel):
    """Spatial anchor configuration for the ``bbox_anchored`` extraction strategy.

    The bbox_anchored strategy locates a printed box number in the PDF word
    stream and resolves the associated monetary value by its positional
    relationship to that anchor word.

    Attributes:
        box_number_pattern: Regex matched against each word's text to locate
            the line-end box number (e.g. ``r"\\b01\\b"`` or a casilla id
            string).  Only anchor words whose x-coordinate falls within
            ``[anchor_x_min, anchor_x_max]`` (if set) are considered; when
            both are ``None`` the full page is searched.  Zero resolved hits
            produce a ``missing`` error; multiple resolved hits produce an
            ``ambiguous`` error.
        value_offset: Direction from the anchor word to the value word.
            ``"right_of_number"`` selects the closest word to the right on
            the same y-row (AEAT multi-column tables with values in a
            right-hand column).  ``"left_of_number"`` and
            ``"above_number"`` are reserved for future form layouts.
        anchor_x_min: Optional minimum x0 coordinate (points) for the anchor
            word search.  Used to restrict the box-number search to a specific
            column when the same two-digit text appears in multiple columns
            (e.g. in formula references embedded in label lines).
        anchor_x_max: Optional maximum x0 coordinate (points) for the anchor
            word search.  Paired with ``anchor_x_min`` to form an x-range gate.
        value_x_max: Optional maximum x0 coordinate (points) for the resolved
            value word.  Used in multi-column layouts to prevent the parser
            from selecting a word from the next column (e.g. the next box
            number) when the current cell is empty.  When ``None`` only the
            general ``_BBOX_X_GAP_TOLERANCE`` limit applies.
        column_anchor: Optional column-header text for multi-column tables
            where the same box number may appear in multiple columns.
            When set, the search is constrained to words whose x-coordinate
            falls within the column identified by this text.
    """

    box_number_pattern: str
    value_offset: Literal["left_of_number", "above_number", "right_of_number"]
    anchor_x_min: float | None = None
    anchor_x_max: float | None = None
    value_x_max: float | None = None
    column_anchor: str | None = None


class ExtractionTargetDefinition(RegistryModel):
    """Per-target descriptor for a registry extraction profile.

    Each entry in :attr:`ExtractionProfileDefinition.target_casillas` is one
    of these records, pairing a stable ``casilla_id`` with the matching
    strategy and value kind the parser uses for that target.

    Attributes:
        casilla_id: Stable casilla identifier the parser resolves to.
        match_strategy: How the parser anchors on this target.
            ``"numeric_casilla"`` anchors on the casilla id printed literally
            at line start (numeric forms, e.g. ``"01"``).
            ``"named_label"`` anchors on the human-readable printed label
            (for text-field modelos where a slug id is never printed).
            ``"bbox_anchored"`` locates the box number in the PDF word stream
            by position and reads the adjacent value word; requires
            ``bbox_anchor`` to be populated.
        value_kind: The type of value the capture group returns.
            ``"amount"`` expects a Spanish-formatted decimal amount;
            ``"text"`` expects the last whitespace-delimited token on the line;
            ``"enum"`` is a text token from a bounded enumeration.
        label_pattern: Required regex string anchoring the ``named_label``
            strategy.  The parser inserts this pattern where the casilla-id
            literal would appear in the numeric path.  Must be ``None`` for
            the ``"numeric_casilla"`` strategy.
        bbox_anchor: Required spatial anchor config for the ``bbox_anchored``
            strategy.  Must be ``None`` for ``"numeric_casilla"`` and
            ``"named_label"`` strategies.
    """

    casilla_id: CasillaId
    match_strategy: Literal["numeric_casilla", "named_label", "bbox_anchored"]
    value_kind: Literal["amount", "text", "enum"]
    label_pattern: str | None = None
    bbox_anchor: BboxAnchorSpec | None = None

    @model_validator(mode="after")
    def _field_strategy_consistency(self) -> ExtractionTargetDefinition:
        if self.match_strategy == "named_label" and not self.label_pattern:
            raise RegistryValidationError("named_label extraction targets require label_pattern")
        if self.match_strategy == "numeric_casilla" and self.label_pattern is not None:
            raise RegistryValidationError("numeric_casilla extraction targets must not define label_pattern")
        if self.match_strategy == "bbox_anchored" and self.bbox_anchor is None:
            raise RegistryValidationError("bbox_anchored extraction targets require bbox_anchor")
        if self.match_strategy != "bbox_anchored" and self.bbox_anchor is not None:
            raise RegistryValidationError("bbox_anchor must be None for non-bbox_anchored strategies")
        return self


class ExtractionProfileDefinition(RegistryModel):
    id: ExtractionProfileId
    surface: Literal["borrador_pdf", "declaracion_pdf", "justificante_pdf", "export_record", "official_workbook"]
    artefact_kind: str
    accepted_artefact_kinds: tuple[
        Literal["submitted_file", "declaration_pdf", "justificante_pdf", "official_workbook"],
        ...,
    ] = Field(min_length=1)
    parser: str
    target_casillas: tuple[ExtractionTargetDefinition, ...] = Field(min_length=1)
    confidence: Literal["strict", "review_required"]
    provisional_pending_specimen: bool = False
    corpus_round_trip_verified: bool = False
    verification_source: Literal[
        "real_aeat_corpus_pdf",
        "synthetic_from_aeat_published_text",
        "historical_suppression",
        "not_applicable",
    ] | None = None
    min_coverage: DecimalValue = Field(ge=Decimal("0"), le=Decimal("1"))
    failure_semantics: Literal["fail_hard"]
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @field_validator("accepted_artefact_kinds")
    @classmethod
    def _accepted_artefact_kinds_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("extraction profile accepted_artefact_kinds entries must be unique")
        return value

    @field_validator("target_casillas")
    @classmethod
    def _target_casillas_unique(
        cls, value: tuple[ExtractionTargetDefinition, ...]
    ) -> tuple[ExtractionTargetDefinition, ...]:
        casilla_ids = [t.casilla_id for t in value]
        if len(set(casilla_ids)) != len(casilla_ids):
            raise RegistryValidationError("extraction profile target_casillas casilla_id entries must be unique")
        return value


ProfileFactValue = bool | int | str


class ProfilePredicateDefinition(RegistryModel):
    field: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z_][A-Za-z0-9_.-]*$")
    op: Literal["equals", "not_equals"]
    value: ProfileFactValue
    explanation: str = Field(min_length=1)
    legal_refs: LegalRefs
    source_refs: SourceRefs


class LiveCrossReferenceDecision(RegistryModel):
    id: CrossReferenceId
    evidence_tier: EvidenceTier
    surface: Literal[
        "open_simulator",
        "integration_test_service",
        "public_read_surface",
        "authenticated_read_surface",
        "authenticated_simulator",
        "static_official_documentation",
    ]
    guard_policy_id: str
    allowed_hosts: tuple[str, ...] = ()
    allowed_methods: tuple[str, ...] = ()
    forbidden_actions: tuple[str, ...] = Field(min_length=1)
    synthetic_data_allowed: bool
    requires_authentication: bool
    requires_aeat_authorization: bool
    legal_refs: LegalRefs
    source_refs: SourceRefs
    # Optional: id of an oracle adapter registered in LiveParityCatalogue.
    # When set, the calculation engine looks up the bound adapter to drive
    # synthetic-payload verification under the cross-reference's policy.
    # Resolution against the catalogue happens at calculation time, not at
    # registry-load time, so the registry remains loadable when adapters
    # are imported lazily.
    oracle_id: OracleId | None = None
    # Optional applicability gate: when non-empty the cross-reference is
    # only applicable to a taxpayer profile whose values satisfy these
    # predicates under the chosen mode. An empty tuple (the default) means
    # the cross-reference is unconditionally applicable, preserving the
    # behaviour of every binding declared before this field existed. Used
    # to gate optional surfaces (GROI / IXVI for ROI-enrolled subjects,
    # OSS bindings for OSS-enrolled subjects, etc.).
    applicability_condition_mode: Literal["all", "any"] = "all"
    applicability_predicates: tuple[ProfilePredicateDefinition, ...] = ()

    @field_validator("oracle_id")
    @classmethod
    def _oracle_id_shape(cls, value: str | None) -> str | None:
        if value is None:
            return None
        # kebab-case ASCII identifier: lowercase alpha start, alphanumerics
        # plus hyphens, no trailing hyphen.
        if not value[0].isalpha() or not value[0].islower():
            raise RegistryValidationError("oracle_id must start with a lowercase ASCII letter")
        if value.endswith("-"):
            raise RegistryValidationError("oracle_id must not end with a hyphen")
        for char in value:
            if not (char.islower() and char.isascii()) and not char.isdigit() and char != "-":
                raise RegistryValidationError(
                    f"oracle_id contains unsupported character {char!r}; "
                    f"only lowercase ASCII letters, digits, and hyphens are permitted"
                )
        return value

    @model_validator(mode="after")
    def _validate_cross_reference(self) -> LiveCrossReferenceDecision:
        self._validate_evidence_tier_alignment()
        self._validate_allowed_hosts_declared()
        self._validate_authentication_constraints()
        self._validate_synthetic_data_constraints()
        for method in self.allowed_methods:
            self._validate_allowed_method(method)
        if self.applicability_condition_mode == "any" and not self.applicability_predicates:
            raise RegistryValidationError(f"cross-reference {self.id!r} any-mode requires applicability predicates")
        return self

    def _validate_evidence_tier_alignment(self) -> None:
        """The evidence_tier must match the surface's regulatory class.

        Live surfaces (simulators, integration test services) carry
        executable parity evidence; read surfaces and static
        documentation carry observation evidence only.
        """
        if (
            self.surface in {"open_simulator", "integration_test_service", "authenticated_simulator"}
            and self.evidence_tier != "executable_parity_evidence"
        ):
            raise RegistryValidationError(
                f"cross-reference {self.id!r} live surface requires executable parity evidence"
            )
        if (
            self.surface in {"public_read_surface", "authenticated_read_surface"}
            and self.evidence_tier == "executable_parity_evidence"
        ):
            raise RegistryValidationError(
                f"cross-reference {self.id!r} read surface is observation evidence, not parity"
            )
        if self.surface == "static_official_documentation" and self.evidence_tier == "executable_parity_evidence":
            raise RegistryValidationError(
                f"cross-reference {self.id!r} static documentation is not executable parity evidence"
            )

    def _validate_allowed_hosts_declared(self) -> None:
        """Every non-static surface must declare its allowed_hosts."""
        if (
            self.surface
            in {
                "open_simulator",
                "integration_test_service",
                "public_read_surface",
                "authenticated_read_surface",
                "authenticated_simulator",
            }
            and not self.allowed_hosts
        ):
            raise RegistryValidationError(f"cross-reference {self.id!r} must declare allowed_hosts")

    def _validate_authentication_constraints(self) -> None:
        """Per-surface auth + AEAT-authorization requirements.

        Open simulators and public reads must not require auth;
        authenticated reads must require both auth and AEAT
        authorization; authenticated simulators must require auth.
        """
        if self.surface == "open_simulator" and self.requires_authentication:
            raise RegistryValidationError(f"cross-reference {self.id!r} open simulator must not require authentication")
        if self.surface == "public_read_surface" and self.requires_authentication:
            raise RegistryValidationError(
                f"cross-reference {self.id!r} public read surface must not require authentication"
            )
        if self.surface == "authenticated_read_surface" and not self.requires_authentication:
            raise RegistryValidationError(
                f"cross-reference {self.id!r} authenticated read surface must require authentication"
            )
        if self.surface == "authenticated_read_surface" and not self.requires_aeat_authorization:
            raise RegistryValidationError(
                f"cross-reference {self.id!r} authenticated read surface must require authorization"
            )
        if self.surface == "authenticated_simulator" and not self.requires_authentication:
            raise RegistryValidationError(
                f"cross-reference {self.id!r} authenticated simulator must require authentication"
            )

    def _validate_synthetic_data_constraints(self) -> None:
        """Read surfaces and static docs must not accept synthetic data.

        Additionally, no cross-reference whose ``allowed_hosts`` include an
        AEAT-owned host (suffix match against ``agenciatributaria.gob.es``
        or ``aeat.es``) may declare ``synthetic_data_allowed = true``.
        Synthetic taxpayer, counterparty, declaration, profile, or form
        data is prohibited on AEAT-hosted live surfaces; the surface
        shape (``open_simulator`` / ``authenticated_simulator``) does not
        license synthetic input against AEAT infrastructure.
        """
        if self.surface in {"public_read_surface", "authenticated_read_surface"} and self.synthetic_data_allowed:
            raise RegistryValidationError(f"cross-reference {self.id!r} read surface must not accept synthetic data")
        if self.surface == "static_official_documentation" and self.synthetic_data_allowed:
            raise RegistryValidationError(
                f"cross-reference {self.id!r} static documentation cannot accept synthetic data"
            )
        if self.synthetic_data_allowed:
            aeat_host = first_aeat_host(self.allowed_hosts)
            if aeat_host is not None:
                raise RegistryValidationError(
                    f"cross-reference {self.id!r} declares synthetic_data_allowed = true "
                    f"on AEAT-hosted allowed host {aeat_host!r}; synthetic data is prohibited "
                    f"on AEAT-hosted live surfaces"
                )

    def _validate_allowed_method(self, method: str) -> None:
        """Per-surface HTTP method allowlist + uppercase shape requirement."""
        if method.upper() != method:
            raise RegistryValidationError(f"cross-reference {self.id!r} allowed_methods must be uppercase")
        if self.surface in {"public_read_surface", "authenticated_read_surface"} and method not in {
            "GET",
            "HEAD",
            "OPTIONS",
        }:
            raise RegistryValidationError(
                f"cross-reference {self.id!r} read surface method {method!r} is not read-only"
            )
        # authenticated_simulator declares the AEAT-prescribed query
        # method (POST is the GROI / IXVI form-submit mechanism). The
        # remote-state guard's HTTP-method check stays strict for
        # ``kind="http"`` operations; only the cross-reference's
        # allowed_methods declaration is widened.
        if self.surface == "authenticated_simulator" and method not in {"GET", "HEAD", "OPTIONS", "POST"}:
            raise RegistryValidationError(
                f"cross-reference {self.id!r} authenticated simulator method "
                f"{method!r} not in (GET, HEAD, OPTIONS, POST)"
            )


class WorkbookParityReference(RegistryModel):
    id: WorkbookParityRefId
    workbook_source: SourceRefId
    fixture_id: WorkbookFixtureId
    formula_coverage: Literal["formula_form", "static_layout", "record_design_layout", "unsupported_binary_xls"]
    runner_required: bool
    output_cells: Mapping[str, WorkbookCellRefStr] = Field(default_factory=dict)
    tolerance: DecimalValue = Decimal("0.00")
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @model_validator(mode="after")
    def _validate_workbook_reference(self) -> WorkbookParityReference:
        if self.formula_coverage == "formula_form" and not self.runner_required:
            raise RegistryValidationError(f"workbook parity reference {self.id!r} formula coverage requires a runner")
        if self.formula_coverage != "formula_form" and self.runner_required:
            raise RegistryValidationError(f"workbook parity reference {self.id!r} runner requires formula coverage")
        if self.runner_required and not self.output_cells:
            raise RegistryValidationError(f"workbook parity reference {self.id!r} requires output_cells")
        if self.workbook_source not in self.source_refs:
            raise RegistryValidationError(
                f"workbook parity reference {self.id!r} source_refs must include workbook_source"
            )
        return self


class VerificationExpectationDefinition(RegistryModel):
    id: VerificationExpectationId
    computed_casillas: tuple[CasillaId, ...]
    reconciliation_totals: Mapping[Literal["ingresar", "devolver"], CasillaId] = Field(default_factory=dict)
    tolerance: DecimalValue
    rounding: str
    min_coverage: DecimalValue = Field(ge=Decimal("0"), le=Decimal("1"))
    discrepancy_causes: tuple[
        Literal["extraction_unreliable", "unmodelled_rule", "rounding", "correctness_divergence"],
        ...,
    ] = Field(min_length=1)
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @field_validator("computed_casillas")
    @classmethod
    def _computed_casillas_unique(cls, value: tuple[CasillaId, ...]) -> tuple[CasillaId, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("verification expectation computed_casillas must be unique")
        return value


class ApplicationLinkDefinition(RegistryModel):
    id: ApplicationLinkId
    surface: Literal[
        "calculation",
        "filing",
        "review",
        "verification",
        "approval",
        "reconciliation",
        "export",
        "deadline",
        "portal",
        "extractor",
        "workflow",
        "communication",
        "payer_delivery",
    ]
    consumer: str
    requires_snapshot: Literal[True]
    legal_refs: LegalRefs
    source_refs: SourceRefs


class SupportRemovalDecisionDefinition(RegistryModel):
    id: SupportRemovalDecisionId
    subject_type: Literal[
        "export_layout",
        "extraction_profile",
        "filing_path",
        "application_link",
        "live_cross_reference",
        "workbook_parity_ref",
        "verification_expectation",
        "deadline_window",
        "filing_schedule",
    ]
    subject_id: str = Field(min_length=1, max_length=160)
    decision: Literal["remove_from_filing_grade"]
    reason: Literal[
        "missing_legal_authority",
        "missing_official_source",
        "unsafe_remote_state",
        "unsupported_official_format",
        "out_of_scope",
    ]
    evidence_note: str = Field(min_length=1, max_length=2048)
    legal_refs: LegalRefs
    source_refs: SourceRefs


class ConstructDefinition(RegistryModel):
    id: ConstructId
    title: str = Field(min_length=1, max_length=200)
    legal_refs: LegalRefs
    source_refs: SourceRefs
    casillas: tuple[CasillaId, ...] = ()
    formulas: tuple[FormulaId, ...] = ()
    parameters: tuple[ParameterId, ...] = ()
    bindings: tuple[BindingId, ...] = ()
    algorithm_providers: tuple[str, ...] = ()
    algorithm_bindings: tuple[str, ...] = ()
    relations: tuple[RelationId, ...] = ()
    export_layouts: tuple[ExportLayoutId, ...] = ()
    extraction_profiles: tuple[ExtractionProfileId, ...] = ()
    live_cross_references: tuple[CrossReferenceId, ...] = ()
    workbook_parity_refs: tuple[WorkbookParityRefId, ...] = ()
    verification_expectations: tuple[VerificationExpectationId, ...] = ()
    application_links: tuple[ApplicationLinkId, ...] = ()
    deadline_windows: tuple[DeadlineWindowId, ...] = ()
    filing_schedules: tuple[str, ...] = ()
    support_removal_decisions: tuple[SupportRemovalDecisionId, ...] = ()
    dependency_classifications: tuple[DependencyClassificationId, ...] = ()

    @field_validator(
        "casillas",
        "formulas",
        "parameters",
        "bindings",
        "algorithm_providers",
        "algorithm_bindings",
        "relations",
        "export_layouts",
        "extraction_profiles",
        "live_cross_references",
        "workbook_parity_refs",
        "verification_expectations",
        "application_links",
        "deadline_windows",
        "filing_schedules",
        "support_removal_decisions",
        "dependency_classifications",
    )
    @classmethod
    def _member_ids_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("construct member ids must be unique")
        return value

    @model_validator(mode="after")
    def _validate_membership(self) -> ConstructDefinition:
        member_groups = (
            self.casillas,
            self.formulas,
            self.parameters,
            self.bindings,
            self.algorithm_providers,
            self.algorithm_bindings,
            self.relations,
            self.export_layouts,
            self.extraction_profiles,
            self.live_cross_references,
            self.workbook_parity_refs,
            self.verification_expectations,
            self.application_links,
            self.deadline_windows,
            self.filing_schedules,
            self.support_removal_decisions,
            self.dependency_classifications,
        )
        if not any(member_groups):
            raise RegistryValidationError(f"construct {self.id!r} must declare at least one revision member")
        return self


class DependencyClassificationDefinition(RegistryModel):
    id: DependencyClassificationId
    source_modelo: ModeloId
    treatment: Literal["direct_annual_settlement", "factual_evidence", "non_dependency"]
    target_constructs: tuple[ConstructId, ...] = ()
    relation_refs: tuple[RelationId, ...] = ()
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @field_validator("target_constructs", "relation_refs")
    @classmethod
    def _tuple_values_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("dependency classification tuple entries must be unique")
        return value

    @model_validator(mode="after")
    def _validate_classification(self) -> DependencyClassificationDefinition:
        if self.treatment == "non_dependency":
            if self.target_constructs or self.relation_refs:
                raise RegistryValidationError(
                    f"non-dependency classification {self.id!r} must not declare target members"
                )
            return self
        if not self.target_constructs:
            raise RegistryValidationError(f"dependency classification {self.id!r} must declare target_constructs")
        if self.treatment == "direct_annual_settlement" and not self.relation_refs:
            raise RegistryValidationError(f"dependency classification {self.id!r} must declare relation_refs")
        return self


class DeadlineWindowDefinition(RegistryModel):
    id: DeadlineWindowId
    filing_year: int = Field(ge=1900, le=2999)
    period: str = Field(min_length=1)
    period_kind: Literal["monthly", "quarterly", "annual", "ad_hoc"]
    opens_on: date
    closes_on: date
    payment_cutoff_on: date | None = None
    applicability_condition_mode: Literal["all", "any"] = "all"
    applicability_conditions: tuple[ProfilePredicateDefinition, ...] = ()
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @model_validator(mode="after")
    def _validate_window(self) -> DeadlineWindowDefinition:
        if self.opens_on > self.closes_on:
            raise RegistryValidationError(f"deadline window {self.id!r} opens_on must not be after closes_on")
        if self.payment_cutoff_on is not None and self.payment_cutoff_on > self.closes_on:
            raise RegistryValidationError(f"deadline window {self.id!r} payment_cutoff_on must not be after closes_on")
        if self.applicability_condition_mode == "any" and not self.applicability_conditions:
            raise RegistryValidationError(f"deadline window {self.id!r} any-mode requires applicability conditions")
        return self


class ModeloScheduleDefinition(RegistryModel):
    id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.-]+$")
    period_kind: Literal["monthly", "quarterly", "annual", "ad_hoc"]
    periods: tuple[str, ...] = Field(min_length=1)
    profile_condition_mode: Literal["all", "any"] = "all"
    profile_conditions: tuple[ProfilePredicateDefinition, ...] = ()
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @field_validator("periods")
    @classmethod
    def _periods_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("filing schedule periods must be unique")
        return value

    @model_validator(mode="after")
    def _validate_schedule(self) -> ModeloScheduleDefinition:
        if self.profile_condition_mode == "any" and not self.profile_conditions:
            raise RegistryValidationError(f"filing schedule {self.id!r} any-mode requires profile conditions")
        return self


def _normalise_dispatch_table_entries(value: object) -> object:
    if not isinstance(value, Mapping) or "dispatch_table_entries" not in value:
        return value
    # TOML fragments always parse to string-keyed tables; ``isinstance`` narrows
    # to Mapping[Unknown, object] because the key type is erased by the object
    # parameter.  The annotation below re-attaches the known str key type at
    # this single TOML deserialization boundary.
    mapping: Mapping[str, object] = value  # type: ignore[assignment]
    if "dispatch_table" in mapping:
        raise RegistryValidationError("formula leaf must use dispatch_table or dispatch_table_entries, not both")

    raw_entries = mapping["dispatch_table_entries"]
    if not isinstance(raw_entries, tuple | list):
        raise RegistryValidationError("dispatch_table_entries must be an array")

    dispatch_table: dict[str, object] = {}
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, Mapping):
            raise RegistryValidationError("dispatch_table_entries entries must be tables")
        entry: Mapping[str, object] = raw_entry  # type: ignore[assignment]  # same TOML key-type boundary as above
        if set(entry) != {"key", "parameter"}:
            raise RegistryValidationError("dispatch_table_entries entries must declare key and parameter")
        key = entry["key"]
        if not isinstance(key, str):
            raise RegistryValidationError("dispatch_table_entries key must be a string")
        if key in dispatch_table:
            raise RegistryValidationError(f"dispatch_table_entries duplicate key {key!r}")
        dispatch_table[key] = entry["parameter"]

    normalised = dict(mapping)
    normalised.pop("dispatch_table_entries")
    normalised["dispatch_table"] = dispatch_table
    return normalised


class FormulaExpression(RegistryModel):
    op: FormulaOperator | None = None
    args: tuple[FormulaExpression, ...] = ()
    casilla: CasillaId | None = None
    binding: BindingId | None = None
    date_binding: BindingId | None = None
    parameter: ParameterId | None = None
    relation: RelationId | None = None
    literal: DecimalValue | None = None
    dispatch_table: Mapping[str, ParameterId] | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalise_dispatch_table_entries(cls, value: object) -> object:
        return _normalise_dispatch_table_entries(value)

    @model_validator(mode="after")
    def _validate_expression(self) -> FormulaExpression:
        populated_leaves = [
            self.casilla is not None,
            self.binding is not None,
            self.date_binding is not None,
            self.parameter is not None,
            self.relation is not None,
            self.literal is not None,
            self.dispatch_table is not None,
        ]
        if self.op is None:
            if self.args:
                raise RegistryValidationError("formula leaf must not declare args")
            if sum(populated_leaves) != 1:
                raise RegistryValidationError("formula leaf must declare exactly one source")
            if self.dispatch_table is not None and not self.dispatch_table:
                raise RegistryValidationError("dispatch_table leaf must declare at least one entry")
            return self
        if sum(populated_leaves):
            raise RegistryValidationError("formula operator must not declare leaf sources")
        if not self.args:
            raise RegistryValidationError("formula operator must declare args")
        return self


class DatedValue(RegistryModel):
    value: DecimalValue
    date_axis: DateAxis
    valid_from: date
    valid_to: date | None = None

    @model_validator(mode="after")
    def _validate_window(self) -> DatedValue:
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise RegistryValidationError("dated value valid_to must be on or after valid_from")
        return self


class BracketEntry(RegistryModel):
    """One row of a piecewise-linear bracket schedule (e.g. an IRPF escala).

    Each entry encodes a half-open base-amount interval ``[lower_bound, upper_bound]``
    plus the cuota previously accumulated up to ``lower_bound`` (``fixed_addition``)
    and the marginal rate applied to the slice above ``lower_bound``. A ``None``
    ``upper_bound`` declares the open-ended top bracket.

    Cuota for a base amount ``base`` resolved by `lookup_bracket`:
        cuota = fixed_addition + marginal_rate * (base - lower_bound)
    """

    lower_bound: DecimalValue
    upper_bound: DecimalValue | None = None
    fixed_addition: DecimalValue
    marginal_rate: DecimalValue
    valid_from: date
    valid_to: date | None = None

    @model_validator(mode="after")
    def _validate_bracket(self) -> BracketEntry:
        if self.upper_bound is not None and self.upper_bound < self.lower_bound:
            raise RegistryValidationError("bracket upper_bound must be on or after lower_bound")
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise RegistryValidationError("bracket valid_to must be on or after valid_from")
        if self.lower_bound < Decimal("0"):
            raise RegistryValidationError("bracket lower_bound must be non-negative")
        if self.marginal_rate < Decimal("0"):
            raise RegistryValidationError("bracket marginal_rate must be non-negative")
        return self


class KeyedBracketEntry(RegistryModel):
    """One row of a string-keyed rate-lookup table.

    Sister shape to :class:`BracketEntry` for parameters that dispatch on
    a categorical enum value rather than a piecewise-linear numeric
    interval. Each row binds a ``key`` (e.g. an IRNR ``tipo_renta`` code:
    ``general`` / ``ue_residente`` / ``ganancia_patrimonial`` /
    ``inmobiliaria``) to a ``value`` (typically a Decimal rate) within a
    ``valid_from``/``valid_to`` window. Lookup is exact-match on
    ``(key, year)`` — there is no notion of interval overlap because the
    domain is enum-discrete, not numeric-continuous.

    First consumer: M210 IRNR Phase 1 ``m210-tipo-gravamen-2025`` per
    the m210-irnr-full-engine ADR.
    """

    key: str = Field(min_length=1, max_length=64)
    value: DecimalValue
    valid_from: date
    valid_to: date | None = None

    @model_validator(mode="after")
    def _validate_keyed_bracket(self) -> KeyedBracketEntry:
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise RegistryValidationError("keyed_bracket valid_to must be on or after valid_from")
        return self


class ConvenioRateRow(RegistryModel):
    """One row of an IRNR Convenio doble imposición rate-override table.

    Sister shape to :class:`KeyedBracketEntry` for parameters that
    dispatch on a ``(country_code, tipo_renta)`` pair returning the
    treaty rate that REPLACES the TRLIRNR baseline when a profile
    declares ``convenio_doble_imposicion_country``. The replacement
    semantics (not stacking) is enforced at lookup time by the runtime
    helper authored in S389b.

    The ``rate`` field is a string carrying either a parseable Decimal
    (e.g. ``"0.10"``) or the literal ``"NOT_YET_AUTHORED"`` sentinel
    that triggers a BLOCKING finding at lookup time. The sentinel
    allows the parameter to carry a placeholder row for a country +
    tipo_renta combination whose Convenio article number is known
    but whose rate has not been corpus-verified yet, without
    deferring the entire row to a follow-up Step.

    First consumer: M210 IRNR Phase 1 ``m210-convenio-rates`` per
    the m210-irnr-full-engine ADR §D2.4.
    """

    country_code: str = Field(min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")
    tipo_renta: str = Field(min_length=1, max_length=64)
    rate: str = Field(min_length=1, max_length=32)
    legal_ref_anchor: str = Field(min_length=1, max_length=128)
    notes: str | None = Field(default=None, max_length=512)
    valid_from: date
    valid_to: date | None = None

    @model_validator(mode="after")
    def _validate_convenio_rate_row(self) -> ConvenioRateRow:
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise RegistryValidationError(
                "convenio_rate_row valid_to must be on or after valid_from"
            )
        # The rate field is either the NOT_YET_AUTHORED sentinel or a
        # parseable Decimal string. Parsing here surfaces malformed
        # values at construction time rather than at lookup time.
        if self.rate != "NOT_YET_AUTHORED":
            try:
                Decimal(self.rate)
            except (ArithmeticError, ValueError) as exc:
                raise RegistryValidationError(
                    f"convenio_rate_row rate must be a parseable Decimal or "
                    f"'NOT_YET_AUTHORED'; got {self.rate!r}"
                ) from exc
        return self


def _brackets_overlap_in_same_window(prev: BracketEntry, current: BracketEntry) -> bool:
    """Return True when two adjacent brackets share a valid_from window and overlap.

    The pre-sorted iteration walks ``(valid_from, lower_bound)``
    order so two brackets only need to be compared when they share
    the ``valid_from`` key. Overlap is defined against a closed-
    open interval: ``prev.upper_bound`` is exclusive, so
    ``current.lower_bound`` reaching strictly below it is the
    violation. A ``prev.upper_bound`` of ``None`` (open-ended)
    short-circuits to "no overlap" — the open right edge is the
    caller's escape hatch.
    """
    if prev.valid_from != current.valid_from:
        return False
    if prev.upper_bound is None:
        return False
    return current.lower_bound < prev.upper_bound


class ParameterDefinition(RegistryModel):
    id: ParameterId
    data_type: Literal[
        "decimal",
        "money",
        "integer",
        "ratio",
        "text",
        "boolean",
        "bracket_table",
        "keyed_bracket_table",
        "convenio_rate_table",
    ]
    unit: str
    values: tuple[DatedValue, ...] = Field(default_factory=tuple)
    brackets: tuple[BracketEntry, ...] = Field(default_factory=tuple)
    keyed_brackets: tuple[KeyedBracketEntry, ...] = Field(default_factory=tuple)
    convenio_rates: tuple[ConvenioRateRow, ...] = Field(default_factory=tuple)
    bracket_axis: DateAxis | None = None
    legal_refs: LegalRefs
    source_refs: SourceRefs
    source_citations: tuple[SourceCitation, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _validate_bracket_table(self) -> ParameterDefinition:
        if self.data_type == "bracket_table":
            self._validate_bracket_table_shape()
        elif self.data_type == "keyed_bracket_table":
            self._validate_keyed_bracket_table_shape()
        elif self.data_type == "convenio_rate_table":
            self._validate_convenio_rate_table_shape()
        else:
            self._validate_non_bracket_table_shape()
        return self

    def _validate_bracket_table_shape(self) -> None:
        """Verify a bracket_table parameter has brackets, no values, an axis, and no overlaps.

        Four contracts:
        * non-empty ``brackets`` tuple
        * no ``values`` (dated scalar map is mutually exclusive)
        * ``bracket_axis`` declared
        * no two brackets sharing the same ``valid_from`` window
          overlap on their ``lower_bound`` / ``upper_bound``
          interval (closed-open)
        """
        if not self.brackets:
            raise RegistryValidationError(f"parameter {self.id!r} declares bracket_table but has no brackets")
        if self.values:
            raise RegistryValidationError(f"parameter {self.id!r} cannot mix bracket_table and dated values")
        if self.keyed_brackets:
            raise RegistryValidationError(
                f"parameter {self.id!r} cannot mix bracket_table and keyed_brackets"
            )
        if self.convenio_rates:
            raise RegistryValidationError(
                f"parameter {self.id!r} cannot mix bracket_table and convenio_rates"
            )
        if self.bracket_axis is None:
            raise RegistryValidationError(f"parameter {self.id!r} bracket_table requires a bracket_axis")
        sorted_brackets = sorted(self.brackets, key=lambda b: (b.valid_from, b.lower_bound))
        for prev, current in pairwise(sorted_brackets):
            if _brackets_overlap_in_same_window(prev, current):
                raise RegistryValidationError(
                    f"parameter {self.id!r} brackets {prev.lower_bound}-{prev.upper_bound} "
                    f"and {current.lower_bound}-{current.upper_bound} overlap within the same window"
                )

    def _validate_keyed_bracket_table_shape(self) -> None:
        """Verify a keyed_bracket_table parameter has a valid keyed shape.

        Four contracts mirror the numeric ``bracket_table`` shape:
        * non-empty ``keyed_brackets`` tuple
        * no ``values`` (dated scalar map is mutually exclusive)
        * no ``brackets`` (numeric-interval table is mutually exclusive)
        * no two ``keyed_brackets`` share the same ``(key, valid_from)``
          pair (exact-match lookup requires a unique row per key per
          window; duplicates would make the lookup non-deterministic)
        """
        if not self.keyed_brackets:
            raise RegistryValidationError(
                f"parameter {self.id!r} declares keyed_bracket_table but has no keyed_brackets"
            )
        if self.values:
            raise RegistryValidationError(
                f"parameter {self.id!r} cannot mix keyed_bracket_table and dated values"
            )
        if self.brackets:
            raise RegistryValidationError(
                f"parameter {self.id!r} cannot mix keyed_bracket_table and numeric brackets"
            )
        if self.convenio_rates:
            raise RegistryValidationError(
                f"parameter {self.id!r} cannot mix keyed_bracket_table and convenio_rates"
            )
        seen: set[tuple[str, date]] = set()
        for row in self.keyed_brackets:
            pair = (row.key, row.valid_from)
            if pair in seen:
                raise RegistryValidationError(
                    f"parameter {self.id!r} keyed_brackets contains duplicate "
                    f"(key, valid_from) pair {pair!r}"
                )
            seen.add(pair)

    def _validate_convenio_rate_table_shape(self) -> None:
        """Verify a convenio_rate_table parameter carries unique convenio rate rows.

        Mirrors the keyed_bracket_table contract structure:
        * non-empty ``convenio_rates`` tuple
        * no ``values`` (dated scalar map is mutually exclusive)
        * no ``brackets`` (numeric-interval table is mutually exclusive)
        * no ``keyed_brackets`` (single-key shape is mutually exclusive)
        * no two ``convenio_rates`` share the same
          ``(country_code, tipo_renta, valid_from)`` triple — the
          runtime lookup is exact-match on the pair within the active
          window, so duplicates would make the result non-deterministic
        """
        if not self.convenio_rates:
            raise RegistryValidationError(
                f"parameter {self.id!r} declares convenio_rate_table but has no convenio_rates"
            )
        if self.values:
            raise RegistryValidationError(
                f"parameter {self.id!r} cannot mix convenio_rate_table and dated values"
            )
        if self.brackets:
            raise RegistryValidationError(
                f"parameter {self.id!r} cannot mix convenio_rate_table and numeric brackets"
            )
        if self.keyed_brackets:
            raise RegistryValidationError(
                f"parameter {self.id!r} cannot mix convenio_rate_table and keyed_brackets"
            )
        seen: set[tuple[str, str, date]] = set()
        for row in self.convenio_rates:
            triple = (row.country_code, row.tipo_renta, row.valid_from)
            if triple in seen:
                raise RegistryValidationError(
                    f"parameter {self.id!r} convenio_rates contains duplicate "
                    f"(country_code, tipo_renta, valid_from) triple {triple!r}"
                )
            seen.add(triple)

    def _validate_non_bracket_table_shape(self) -> None:
        """Reject brackets / keyed_brackets / convenio_rates / bracket_axis on a non-bracket-table parameter."""
        if self.brackets:
            raise RegistryValidationError(
                f"parameter {self.id!r} declares brackets but data_type is {self.data_type!r}; use 'bracket_table'"
            )
        if self.keyed_brackets:
            raise RegistryValidationError(
                f"parameter {self.id!r} declares keyed_brackets but data_type is {self.data_type!r}; "
                "use 'keyed_bracket_table'"
            )
        if self.convenio_rates:
            raise RegistryValidationError(
                f"parameter {self.id!r} declares convenio_rates but data_type is {self.data_type!r}; "
                "use 'convenio_rate_table'"
            )
        if self.bracket_axis is not None:
            raise RegistryValidationError(f"parameter {self.id!r} declares bracket_axis but is not a bracket_table")


class DataBindingDefinition(RegistryModel):
    id: BindingId
    source: Literal[
        "invoice",
        "profile",
        "previous_filing",
        "manual_input",
        "ledger_oss_aggregation",
        "ledger_iva_aggregation",
        "ledger_renta_expense_aggregation",
        "ledger_renta_income_aggregation",
        "payable_invoice",
        "collectible_invoice",
        "ledger_transaction",
        "purchase_invoice_evidence",
        "withholding",
        "related_party_operation",
        "foreign_asset",
        "atribucion_member",
        "refund_operation",
    ]
    selector: BindingSelectorMap
    aggregation: Mapping[str, str | int | DecimalValue | bool] | None = None
    typed_enum: str | None = None
    legal_refs: LegalRefs
    source_refs: SourceRefs
    source_citations: tuple[SourceCitation, ...] = Field(default_factory=tuple)
    aeat_prefilled: bool = False


class FormulaDefinition(RegistryModel):
    id: FormulaId
    target: CasillaId
    expression: FormulaExpression
    rounding: str | None = None
    legal_refs: LegalRefs
    source_refs: SourceRefs
    source_citations: tuple[SourceCitation, ...] = Field(default_factory=tuple)


class CasillaContinuidadEvolutionDefinition(RegistryModel):
    """Declared cross-revision evolution for one casilla continuity chain."""

    id: RecordId
    continuidad_id: ContinuidadId
    from_revision: RevisionId
    to_revision: RevisionId
    evolution_kind: Literal[
        "unchanged",
        "label_evolved",
        "legal_refs_evolved",
        "label_and_legal_refs_evolved",
        "repurposed",
        "retired",
    ]
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @model_validator(mode="after")
    def _validate_revision_pair(self) -> CasillaContinuidadEvolutionDefinition:
        if self.from_revision == self.to_revision:
            raise RegistryValidationError(
                f"casilla continuidad evolution {self.id!r} must span two different revisions"
            )
        return self


class CasillaAlias(RegistryModel):
    """A label variant for a casilla, carrying its own legal grounding.

    Used by Plan C's semantic-role validator: two casillas in
    different modelos can share a ``semantic_role`` even though
    their primary ``label`` strings differ verbatim, provided each
    declares the divergent phrasing via an ``aliases`` entry with
    a documented BOE or AEAT source.
    """

    label: str = Field(min_length=1, max_length=512)
    legal_refs: LegalRefs
    source_refs: SourceRefs


class CasillaConstraints(RegistryModel):
    """Declarative value constraints applied after a casilla is evaluated.

    Captures the legal sign / range rules AEAT mandates per LIRPF /
    LIVA / LIS articles: a withholding casilla cannot carry a
    negative value, a deductibility cap restricts the maximum, a
    non-negativity floor on a cuota líquida prevents arithmetic
    underflow propagating through downstream formulas.

    Each constraint declares its own legal grounding so the engine
    can surface a BOE permalink in the violation envelope when a
    computed value falls outside the declared bounds. The runtime
    raises a typed `CasillaConstraintViolationError`; the Sheets apply
    adapter renders the same record as a `setDataValidation` rule
    on the corresponding cell so the operator sees the constraint
    directly in the workbook UI.
    """

    sign: Literal["any", "non_negative", "non_positive"] = "any"
    min_value: DecimalValue | None = None
    max_value: DecimalValue | None = None
    pattern: str | None = None
    min_length: int | None = Field(default=None, ge=0)
    max_length: int | None = Field(default=None, ge=0)
    enum: tuple[str, ...] | None = None
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @model_validator(mode="after")
    def _validate_bounds(self) -> CasillaConstraints:
        if self.min_value is not None and self.max_value is not None and self.min_value > self.max_value:
            raise RegistryValidationError(
                f"casilla constraints: min_value {self.min_value} > max_value {self.max_value}"
            )
        if self.sign == "non_negative" and self.max_value is not None and self.max_value < Decimal("0"):
            raise RegistryValidationError(
                "casilla constraints: sign='non_negative' is incompatible with negative max_value"
            )
        if self.sign == "non_positive" and self.min_value is not None and self.min_value > Decimal("0"):
            raise RegistryValidationError(
                "casilla constraints: sign='non_positive' is incompatible with positive min_value"
            )
        if self.min_length is not None and self.max_length is not None and self.min_length > self.max_length:
            raise RegistryValidationError(
                f"casilla constraints: min_length {self.min_length} > max_length {self.max_length}"
            )
        if self.enum is not None and len(self.enum) == 0:
            raise RegistryValidationError("casilla constraints: enum must declare at least one value")
        if self.enum is not None and len(set(self.enum)) != len(self.enum):
            raise RegistryValidationError("casilla constraints: enum values must be unique")
        if self.pattern is not None:
            try:
                re.compile(self.pattern)
            except re.error as exc:
                raise RegistryValidationError(
                    f"casilla constraints: pattern {self.pattern!r} is not a valid regex: {exc}"
                ) from exc
        return self

    def violates(self, value: Decimal) -> str | None:
        """Return a short reason string if a Decimal `value` violates this constraint, else None.

        Numeric-only violation check preserved for downstream consumers
        of computed casilla values. Text constraints (`pattern`,
        `min_length`, `max_length`, `enum`) are surfaced through the
        sibling :meth:`violates_text` method.
        """

        if self.sign == "non_negative" and value < Decimal("0"):
            return f"value {value} violates sign=non_negative"
        if self.sign == "non_positive" and value > Decimal("0"):
            return f"value {value} violates sign=non_positive"
        if self.min_value is not None and value < self.min_value:
            return f"value {value} below min_value {self.min_value}"
        if self.max_value is not None and value > self.max_value:
            return f"value {value} above max_value {self.max_value}"
        return None

    def violates_text(self, value: str) -> str | None:
        """Return a short reason string if a text `value` violates the text constraints, else None.

        Checks the four text-shape constraints introduced by Plan B:
        ``pattern``, ``min_length``, ``max_length``, and ``enum``. Used
        by consumers that resolve a casilla value into a string at
        evaluation time.
        """

        length = len(value)
        if self.min_length is not None and length < self.min_length:
            return f"value length {length} below min_length {self.min_length}"
        if self.max_length is not None and length > self.max_length:
            return f"value length {length} above max_length {self.max_length}"
        if self.pattern is not None and not re.fullmatch(self.pattern, value):
            return f"value {value!r} does not match pattern {self.pattern!r}"
        if self.enum is not None and value not in self.enum:
            return f"value {value!r} not in enum {self.enum!r}"
        return None


class CasillaDefinition(RegistryModel):
    """A single AEAT casilla within a modelo revision.

    A casilla's identity is the pair ``(segmento, number)``. For
    single-segment modelos ``segmento`` is unset and ``number`` alone is
    unique within the revision. Multi-segment AEAT modelos (e.g. Modelo
    200) reuse the same five-digit ``number`` across distinct record
    segments with a different meaning in each; those casillas carry the
    AEAT record-segment code in ``segmento`` to disambiguate.
    """

    id: CasillaId
    number: str
    segmento: str | None = Field(
        default=None,
        min_length=1,
        max_length=32,
        description=(
            "AEAT record-segment code (e.g. 'DP200014') for multi-segment "
            "modelos that reuse a casilla number across record segments. "
            "Unset for single-segment modelos; a casilla's identity is the "
            "pair (segmento, number)."
        ),
    )
    label: str
    section: tuple[str, ...]
    data_type: Literal[
        "decimal",
        "money",
        "integer",
        "ratio",
        "text",
        "boolean",
        "nif",
        "year",
        "period_code",
        "country_code",
        "iban",
        "name",
        "nif_iva",
        "ccaa_code",
        "province_code",
        "postal_code",
        "municipality_code",
        "bic",
        "date",
    ] = "money"
    required: bool = False
    input_kind: InputKindValue = InputKind.MANUAL
    formula: FormulaId | None = None
    binding: BindingId | None = None
    export_refs: tuple[ExportFieldId, ...] = ()
    constraints: CasillaConstraints | None = None
    form_number: str | None = Field(default=None, min_length=1, max_length=16)
    continuidad_id: ContinuidadId | None = Field(
        default=None,
        description=(
            "Stable cross-revision continuity key for non-overlapping annual "
            "forms. When present, it identifies the legal concept continuity "
            "chain independently of the revision-local casilla id."
        ),
    )
    semantic_role: str | None = Field(default=None, min_length=1, max_length=128)
    semantic_role_cardinality: Literal["shared", "intentional_singleton"] = "shared"
    semantic_role_cardinality_reason: str | None = Field(default=None, min_length=1, max_length=256)
    aliases: tuple[CasillaAlias, ...] = ()
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @model_validator(mode="after")
    def _validate_input_kind(self) -> CasillaDefinition:
        if self.input_kind == "computed" and self.formula is None:
            raise RegistryValidationError(f"computed casilla {self.id!r} must declare formula")
        if self.input_kind == "computed" and self.binding is not None:
            raise RegistryValidationError(f"computed casilla {self.id!r} must not declare binding")
        if self.input_kind == "bound" and self.binding is None:
            raise RegistryValidationError(f"bound casilla {self.id!r} must declare binding")
        if self.input_kind == "bound" and self.formula is not None:
            raise RegistryValidationError(f"bound casilla {self.id!r} must not declare formula")
        if self.semantic_role_cardinality == "intentional_singleton":
            if self.semantic_role is None:
                raise RegistryValidationError(
                    f"casilla {self.id!r} declares intentional singleton role cardinality without semantic_role"
                )
            if self.semantic_role_cardinality_reason is None:
                raise RegistryValidationError(
                    f"casilla {self.id!r} declares intentional singleton role cardinality without reason"
                )
        elif self.semantic_role_cardinality_reason is not None:
            raise RegistryValidationError(
                f"casilla {self.id!r} declares semantic_role_cardinality_reason "
                "without intentional singleton cardinality"
            )
        return self


class CalculationCompletenessCasilla(RegistryModel):
    """One required ``(segmento, number)`` casilla in a calculation-completeness manifest.

    A casilla's identity is the pair ``(segmento, number)``. A
    single-segment modelo leaves ``segmento`` unset, so the pair degrades
    to ``(None, number)`` and the manifest enumerates bare numbers.

    ``number`` carries the registry ``number`` of the closure casilla
    verbatim. Only Modelo 200's casilla numbers are five-digit AEAT
    Diseño tags; the other calculation-bearing modelos identify casillas
    by semantic slug (``iva.cuota-devengada-total``) or short ordinal
    (``01``-``19``), so the manifest carries whatever vocabulary the
    modelo's registry uses. The field is unbounded above to match the
    unconstrained ``CasillaDefinition.number``.

    The manifest enumerates only the casillas inside a modelo's
    *calculation closure* — formula targets, the casillas referenced
    inside any formula expression, formula and binding endpoint casillas,
    and verification-expectation operands. Pure accounting-statement
    data-entry fields that feed no calculation are intentionally absent
    from this required set.
    """

    number: str = Field(min_length=1)
    segmento: str | None = Field(
        default=None,
        min_length=1,
        max_length=32,
        description=(
            "AEAT record-segment code (e.g. 'DP200014') for multi-segment "
            "modelos that reuse a casilla number across record segments. "
            "Unset for single-segment modelos."
        ),
    )

    def identity(self) -> tuple[str | None, str]:
        """Return the ``(segmento, number)`` identity pair for this casilla."""
        return (self.segmento, self.number)


class CalculationCompletenessManifest(RegistryModel):
    """The required calculation-closure casilla set for a modelo revision.

    Enumerates the ``(segmento, number)`` casillas in a modelo's
    *calculation closure* — the casillas the cross-connecting
    calculation engine traverses: every formula target, every casilla
    referenced inside a formula expression, every binding and relation
    endpoint casilla, and every verification-expectation operand. It is
    derived from the official AEAT Diseño de Registros *intersected
    with* the modelo's calculation surface — Diseño-authoritative on
    each casilla's segment, number, and label, but bounded to what the
    engine needs (an off-load-path derivation step, never parsed on the
    snapshot-build hot path) and checked into the registry as reviewed
    data.

    The registry validator enforces ``manifest-required ⊆ declared``
    plus a ``(segmento, number)`` identity check and a
    ``legal_refs`` / ``source_refs`` grounding check on each required
    casilla. A casilla the revision declares but the manifest does not
    list (a pure accounting-statement field) is *not* a failure.

    ``manual_extraction`` flags a manifest authored from a manual read
    of a PDF-only Diseño that resists machine extraction; the
    off-load-path drift re-verification skips the machine re-derivation
    for such manifests and records ``manual_extraction_reason`` instead
    of failing silently.
    """

    source_ref: SourceRefId = Field(
        description="Catalogue source id of the AEAT Diseño de Registros the manifest was derived from."
    )
    casillas: tuple[CalculationCompletenessCasilla, ...]
    manual_extraction: bool = False
    manual_extraction_reason: str | None = Field(default=None, min_length=1, max_length=512)
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @model_validator(mode="after")
    def _validate_manifest(self) -> CalculationCompletenessManifest:
        if not self.casillas:
            raise RegistryValidationError("calculation-completeness manifest must enumerate at least one casilla")
        identities = [casilla.identity() for casilla in self.casillas]
        duplicates = sorted({pair for pair in identities if identities.count(pair) > 1})
        if duplicates:
            rendered = ", ".join(
                f"{number!r}" if segmento is None else f"{number!r} within segmento {segmento!r}"
                for segmento, number in duplicates
            )
            raise RegistryValidationError(
                f"calculation-completeness manifest declares duplicate casilla identities: {rendered}"
            )
        if self.source_ref not in self.source_refs:
            raise RegistryValidationError(
                "calculation-completeness manifest source_ref must be included in source_refs"
            )
        if self.manual_extraction and self.manual_extraction_reason is None:
            raise RegistryValidationError(
                "calculation-completeness manifest with manual_extraction must declare manual_extraction_reason"
            )
        if not self.manual_extraction and self.manual_extraction_reason is not None:
            raise RegistryValidationError(
                "calculation-completeness manifest declares manual_extraction_reason without manual_extraction"
            )
        return self

    def identities(self) -> frozenset[tuple[str | None, str]]:
        """Return the frozenset of required ``(segmento, number)`` identity pairs."""
        return frozenset(casilla.identity() for casilla in self.casillas)


class AlgorithmProviderDefinition(RegistryModel):
    id: str
    import_path: str
    callable_name: str
    deterministic: Literal[True]
    side_effect_free: Literal[True]
    allowed_input_schema: Mapping[str, str]
    output_schema: Mapping[str, str]
    trace_contract: str
    legal_refs: LegalRefs
    source_refs: SourceRefs


class AlgorithmBindingDefinition(RegistryModel):
    id: str
    provider: str
    target: CasillaId | str
    inputs: Mapping[str, BindingId | CasillaId | ParameterId | RelationId]
    outputs: Mapping[str, CasillaId | str]
    constants: tuple[ParameterId, ...] = ()
    legal_refs: LegalRefs
    source_refs: SourceRefs


class RelationDefinition(RegistryModel):
    id: RelationId
    kind: Literal["previous_period", "annual_summary", "cross_model_output"]
    dependency_role: Literal[
        "profile_schedule",
        "periodic_to_annual_summary",
        "instalment_to_final_settlement",
        "direct_calculation",
        "factual_evidence",
    ]
    source_modelo: ModeloId
    source_revision_selector: Mapping[str, str | int]
    source_output: CasillaId
    target_binding: BindingId
    period_alignment: Mapping[str, str | int]
    source_periods: tuple[str, ...] = ()
    target_periods: tuple[str, ...] = ()
    source_period_offset_from_target: int | None = None
    aggregation: Mapping[str, str | int | DecimalValue | bool] | None = None
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @field_validator("source_periods", "target_periods")
    @classmethod
    def _relation_periods_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("relation periods must be unique")
        return value

    @model_validator(mode="after")
    def _validate_dependency_role(self) -> RelationDefinition:
        if self.kind == "annual_summary" and self.dependency_role != "periodic_to_annual_summary":
            raise RegistryValidationError(
                f"annual summary relation {self.id!r} must use periodic_to_annual_summary role"
            )
        if self.source_period_offset_from_target is not None:
            # The offset declares "for each target_period, derive source_period
            # by adding the offset to the target's ordinal". It is incompatible
            # with explicit source_periods which fixes a single static source set.
            if self.source_periods:
                raise RegistryValidationError(
                    f"relation {self.id!r} cannot declare source_periods together with source_period_offset_from_target"
                )
            if self.source_period_offset_from_target == 0:
                raise RegistryValidationError(f"relation {self.id!r} source_period_offset_from_target must be non-zero")
        return self


class ExportFieldDefinition(RegistryModel):
    id: ExportFieldId
    offset: int | None = Field(default=None, ge=0)
    length: int | None = Field(default=None, gt=0)
    kind: Literal["literal", "casilla", "binding", "computed", "draft", "filler", "header", "checksum"]
    casilla: CasillaId | None = None
    binding: BindingId | None = None
    literal: str | None = None
    header_key: str | None = None
    draft_attribute: Literal["modelo", "period", "profile_tax_id", "filing_year", "period_code"] | None = None
    computed_key: Literal["envelope_closing_tag"] | None = None
    data_type: Literal["text", "integer", "decimal", "money", "date", "boolean"]
    required: bool
    padding: Literal["left_zero", "left_space", "right_space", "none"]
    justification: Literal["left", "right", "none"]
    date_format: str | None = None
    signed: bool
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @model_validator(mode="after")
    def _validate_field_kind(self) -> ExportFieldDefinition:
        if self.kind == "casilla" and self.casilla is None:
            raise RegistryValidationError(f"export field {self.id!r} must declare casilla")
        if self.kind == "binding" and self.binding is None:
            raise RegistryValidationError(f"export field {self.id!r} must declare binding")
        if self.kind == "literal" and self.literal is None:
            raise RegistryValidationError(f"export field {self.id!r} must declare literal")
        if self.kind == "header" and self.header_key is None:
            raise RegistryValidationError(f"export field {self.id!r} must declare header_key")
        if self.kind == "draft" and self.draft_attribute is None:
            raise RegistryValidationError(f"export field {self.id!r} must declare draft_attribute")
        if self.kind == "computed" and self.computed_key is None:
            raise RegistryValidationError(f"export field {self.id!r} must declare computed_key")
        if self.kind == "filler" and self.length is None:
            raise RegistryValidationError(f"export field {self.id!r} filler must declare length")
        return self


class RecordDiscriminator(RegistryModel):
    """Record-shape discriminator for record types that share literal prefixes.

    A record's literal-prefix matcher cannot tell two records apart when they
    share their leading literal fields (AEAT models several Tipo-2 record
    sub-shapes that all start with the same record-type literal). The
    discriminator declares a contiguous byte range whose populated-or-blank
    pattern uniquely identifies this record subtype, letting the parser pick
    the correct record while reading binding-row sequences.
    """

    offset: int = Field(ge=1)
    length: int = Field(gt=0)
    requires: Literal["blank", "non_blank"]


class ExportRecordDefinition(RegistryModel):
    id: RecordId
    record_type: str
    order: int = Field(ge=0)
    encoding: str
    line_ending: Literal["crlf", "lf", "none"]
    required: bool = True
    repeat: Literal["binding_rows"] | None = None
    binding_record: str | None = None
    row_field_casillas: Mapping[str, CasillaId] = Field(default_factory=dict)
    discriminator: RecordDiscriminator | None = None
    requires_positive_casilla: CasillaId | None = None
    fields: tuple[ExportFieldDefinition, ...] = Field(default_factory=tuple)

    @field_validator("binding_record")
    @classmethod
    def _binding_record_non_empty(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise RegistryValidationError("export record binding_record must be non-empty")
        return value


class ExportLayoutDefinition(RegistryModel):
    id: ExportLayoutId
    format: Literal["fixed_width", "xml_dictionary"] = "fixed_width"
    dictionary_source_ref: SourceRefId | None = None
    source_refs: SourceRefs
    legal_refs: LegalRefs
    records: tuple[ExportRecordDefinition, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _validate_layout_format(self) -> ExportLayoutDefinition:
        if self.format == "xml_dictionary":
            if self.dictionary_source_ref is None:
                raise RegistryValidationError(f"export layout {self.id!r} must declare dictionary_source_ref")
            if self.dictionary_source_ref not in self.source_refs:
                raise RegistryValidationError(
                    f"export layout {self.id!r} dictionary source must be included in source_refs"
                )
        return self

    @model_validator(mode="after")
    def _validate_encoding_consistency(self) -> ExportLayoutDefinition:
        """Enforce one encoding per fixed-width export layout.

        AEAT publishes one wire encoding per modelo-year fichero-BOE
        spec; mixing encodings across records inside a single layout
        is a registry-author error that would produce a payload no
        single decoder can faithfully re-parse. ``latin-1`` and
        ``iso-8859-1`` are normalised to the same encoding before
        comparison (Python codec aliases for the same charset).

        Cross-domain encoding-lock: every record within one layout
        must declare an encoding that normalises to the same value.
        XML-dictionary layouts have no record-level encoding (the
        records tuple is typically empty), so this check is a no-op
        for them.
        """

        if self.format != "fixed_width":
            return self
        normalised: dict[str, str] = {}
        for record in self.records:
            normalised[record.id] = _normalise_fichero_boe_encoding(record.encoding)
        unique_encodings = set(normalised.values())
        if len(unique_encodings) > 1:
            per_record = ", ".join(f"{record_id}={encoding!r}" for record_id, encoding in sorted(normalised.items()))
            raise RegistryValidationError(
                f"export layout {self.id!r} declares inconsistent encodings "
                f"across its records: {per_record}. A single fichero-BOE "
                f"layout must use one wire encoding so the published payload "
                f"decodes uniformly."
            )
        return self


_FICHERO_BOE_ENCODING_ALIASES: Mapping[str, str] = {
    "latin-1": "iso-8859-1",
    "latin_1": "iso-8859-1",
    "iso-8859-1": "iso-8859-1",
    "iso_8859_1": "iso-8859-1",
    "cp1252": "cp1252",
    "windows-1252": "cp1252",
    "iso-8859-15": "iso-8859-15",
    "iso_8859_15": "iso-8859-15",
    "latin-9": "iso-8859-15",
}
"""Canonical-encoding map for fichero-BOE registry encoding declarations.

AEAT treats Windows-1252 and ISO-8859-1 as equivalent for fichero-BOE
purposes; Python codec aliases (``latin-1`` ↔ ``iso-8859-1``,
``windows-1252`` ↔ ``cp1252``, ``latin-9`` ↔ ``iso-8859-15``) resolve
to the same wire encoding. The encoding-consistency validator
compares declared encodings through this map so a layout that mixes
``latin-1`` and ``iso-8859-1`` is treated as consistent rather than
flagged as a layout error.
"""


def _normalise_fichero_boe_encoding(declared: str) -> str:
    """Return the canonical form of a fichero-BOE encoding declaration."""

    return _FICHERO_BOE_ENCODING_ALIASES.get(declared.strip().lower(), declared.strip().lower())


# P10.S68: single source of truth for the predicate-DSL operator
# names. The registry-load validator
# (_validate_surfaces.validate_verification_expectation_section)
# uses this set to reject unknown operators at authoring time.
# The runtime evaluator
# (aeat.application.modelo._actions._evaluate_predicate_expression)
# carries its own regex per operator but MUST keep its set of
# operators identical to this constant — drift between the two
# sets is a silent-pass hazard at the predicate layer (a typo
# would silently pass the gate that's missing the operator). A
# gate test asserts the runtime evaluator recognises every name
# in this constant.
KNOWN_VERIFICATION_PREDICATE_OPERATORS: frozenset[str] = frozenset(
    {
        "all_nonzero",
        "any_nonzero",
        "cap_le_when_positive",
        "advisory_when_ratio_ge",
        "implies_nonzero",
    }
)


class VerificationPredicateDefinition(RegistryModel):
    """A cross-casilla invariant that must hold for VERIFICADO_COMPLETO to be granted.

    Layer 2 of the hybrid verification strategy.  Layer 1 handles
    single-casilla required gates via ``CasillaDefinition.required``; this
    class handles multi-casilla structural invariants (e.g. ``if ingresos
    is non-zero then rendimiento neto must also be present``).

    ``expression`` uses a minimal W04 DSL:

    - ``all_nonzero(["id1", "id2", ...])`` — every listed casilla value must
      be non-zero (i.e. the filing invariant requires them all to be present
      and non-zero simultaneously).
    - ``any_nonzero(["id1", "id2", ...])`` — at least one listed casilla
      value must be non-zero.
    - ``cap_le_when_positive(["limited_id", "ceiling_id"])`` — when the
      ceiling casilla is strictly positive, the limited casilla MUST NOT
      exceed the ceiling. Added by P08.S47 to enforce AEAT cap rules like
      Modelo 131 C11 ≤ C10 and Modelo 130 C15 ≤ C14 ("en ningún caso podrá
      figurar... un importe superior a la cantidad positiva consignada").
      Predicate holds when ceiling ≤ 0; the cap applies only when the
      operator's gross liability is positive.
    - ``implies_nonzero(["antecedent_id", "consequent_id"])`` — material
      implication with a strictly-positive antecedent test: predicate
      holds iff ``casilla_values[antecedent] <= 0`` OR
      ``casilla_values[consequent] != 0``. Authored for AEAT cuota-mínima
      invariants of the shape "cuando C01 sea positivo, C07 debe ser
      distinta de cero" (M131 EO cuota mínima, M130/M303 régimen
      simplificado analogues). The antecedent is strictly-positive rather
      than non-zero to mirror the regulatory phrasing; a casilla with a
      negative value does not trigger the implication. A missing
      consequent value evaluates to ``Decimal(0)`` and therefore
      violates the predicate when the antecedent is positive. Added by
      the dsl-conditional-predicate ADR.
    """

    predicate_id: str = Field(min_length=1, max_length=128)
    legal_refs: LegalRefs
    expression: str = Field(min_length=1, max_length=512)
    finding_kind: Literal["BLOCKING_RULE", "ADVISORY"] = "BLOCKING_RULE"


class ModeloRevision(RegistryModel):
    id: RevisionId
    label: str | None = None
    valid_from: date
    valid_to: date | None = None
    period_selector: PeriodSelector
    legal_refs: LegalRefs
    source_refs: SourceRefs
    parameters: tuple[ParameterDefinition, ...] = ()
    casillas: tuple[CasillaDefinition, ...] = ()
    formulas: tuple[FormulaDefinition, ...] = ()
    bindings: tuple[DataBindingDefinition, ...] = ()
    algorithm_providers: tuple[AlgorithmProviderDefinition, ...] = ()
    algorithm_bindings: tuple[AlgorithmBindingDefinition, ...] = ()
    relations: tuple[RelationDefinition, ...] = ()
    export_layouts: tuple[ExportLayoutDefinition, ...] = ()
    extraction_profiles: tuple[ExtractionProfileDefinition, ...] = ()
    live_cross_references: tuple[LiveCrossReferenceDecision, ...] = ()
    workbook_parity_refs: tuple[WorkbookParityReference, ...] = ()
    verification_expectations: tuple[VerificationExpectationDefinition, ...] = ()
    application_links: tuple[ApplicationLinkDefinition, ...] = ()
    deadline_windows: tuple[DeadlineWindowDefinition, ...] = ()
    filing_schedules: tuple[ModeloScheduleDefinition, ...] = ()
    support_removal_decisions: tuple[SupportRemovalDecisionDefinition, ...] = ()
    constructs: tuple[ConstructDefinition, ...] = ()
    dependency_classifications: tuple[DependencyClassificationDefinition, ...] = ()
    completeness_manifest: CalculationCompletenessManifest | None = None
    verification_predicates: tuple[VerificationPredicateDefinition, ...] = ()
    continuidad_validation: Literal["advisory", "strict"] = "advisory"
    casilla_continuidad_evolutions: tuple[CasillaContinuidadEvolutionDefinition, ...] = ()

    @model_validator(mode="after")
    def _validate_window(self) -> ModeloRevision:
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise RegistryValidationError("revision valid_to must be on or after valid_from")
        return self


class ModeloDefinition(RegistryModel):
    id: ModeloId
    title: str
    official_name: str
    tax_domain: str
    cadence: Literal["monthly", "quarterly", "annual", "ad_hoc", "profile_based"]
    jurisdiction: Literal["ES-AEAT"]
    calculation_class: CalculationClass = "filing"
    output_sensitivity: SensitivityClassField = SensitivityClass.FINANCIAL
    capabilities: Annotated[frozenset[ModeloCapability], BeforeValidator(frozenset)] = frozenset()
    legal_refs: LegalRefs
    source_refs: SourceRefs
    revisions: Mapping[RevisionId, ModeloRevision]

    def has_capability(self, name: ModeloCapability) -> bool:
        """Return whether this modelo declares the given capability."""
        return name in self.capabilities

    @model_validator(mode="after")
    def _validate_revisions(self) -> ModeloDefinition:
        if not self.revisions:
            raise RegistryValidationError(f"modelo {self.id!r} must declare at least one revision")
        for key, revision in self.revisions.items():
            if key != revision.id:
                raise RegistryValidationError(f"revision key {key!r} does not match revision id {revision.id!r}")
        return self


class RegistryCatalogues(RegistryModel):
    legal: Mapping[LegalRefId, LegalReference]
    sources: Mapping[SourceRefId, SourceReference]
    parameters: Mapping[str, LegalParameter] = Field(default_factory=dict)


class RegistrySnapshot(RegistryModel):
    modelo: ModeloDefinition
    revision: ModeloRevision
    filing_year: int = Field(ge=2000, le=2099)
    # Accommodates time-codes ("1T", "2T", "0A", "01"-"12", "EXT-1T") and
    # event-period names from ad_hoc modelos (M036 "alta", "modificacion",
    # "baja"; M308 "AD-HOC"; M115 etc.). The 32-char ceiling is generous
    # enough for descriptive future event names without becoming a free-text
    # field — the matching constraint is enforced upstream in
    # PeriodSelector + ModeloScheduleDefinition (which validate against
    # each modelo's declared periods).
    #
    # Audit note on the layered max_length contract across the codebase:
    #
    #   - RegistrySnapshot.period (this field): max_length=32 — the
    #     registry-side surface where event-period names live.
    #   - Application-side serialization buffers (filing/_calculate.py,
    #     filing/_export.py, aggregation/_service.py, etc.): max_length=16
    #     — sufficient for every period name registered today
    #     ("modificacion" is 12).
    #   - Sede outbound models (sede/_declarations.py, sede/_schema.py):
    #     max_length=8 — AEAT-side period codes from the sede HTML are
    #     always ≤ 8 chars (e.g. "1T", "0A"). M036 events never traverse
    #     these models (census events do not flow through the
    #     filed-declaration sede surface).
    #
    # Verified end-to-end: M036's "modificacion" period builds a
    # RegistrySnapshot, threads through the application/filing layer
    # (16 ≥ 12), and never reaches the sede 8-cap models.
    # the modelo's declared periods).
    period: str = Field(min_length=1, max_length=32)
    legal: Mapping[LegalRefId, LegalReference]
    sources: Mapping[SourceRefId, SourceReference]
    extraction_profiles: Mapping[ExtractionProfileId, ExtractionProfileDefinition]
    live_cross_references: Mapping[CrossReferenceId, LiveCrossReferenceDecision]
    workbook_parity_refs: Mapping[WorkbookParityRefId, WorkbookParityReference]
    verification_expectations: Mapping[VerificationExpectationId, VerificationExpectationDefinition]
    application_links: Mapping[ApplicationLinkId, ApplicationLinkDefinition]
    deadline_windows: Mapping[DeadlineWindowId, DeadlineWindowDefinition]
    filing_schedules: Mapping[str, ModeloScheduleDefinition]
    support_removal_decisions: Mapping[SupportRemovalDecisionId, SupportRemovalDecisionDefinition]
    constructs: Mapping[ConstructId, ConstructDefinition]
    dependency_classifications: Mapping[DependencyClassificationId, DependencyClassificationDefinition]
