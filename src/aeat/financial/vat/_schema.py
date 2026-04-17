"""Strict pydantic v2 schema for the ``aeat.financial.vat`` subpackage.

Every record the subpackage exposes — enumerations, per-rate values,
citations, regulations, catalogues, verification reports — is defined
here. The schema is frozen and strict wherever the loader idiom
permits it, mirroring the pattern established by
:mod:`aeat.normatives._schema`.

Closed catalogues (:class:`VATCategory`, :class:`EUMemberState`,
:class:`VATRateKind`, :class:`CitationSource`) are
:class:`enum.StrEnum`. Trilingual fields use
:class:`aeat.i18n.Translatable` and the authoritative ``es`` key is
enforced at construction time on every ``VATRegulation``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from ...i18n import Translatable


class VATCategory(StrEnum):
    """Closed catalogue of Spanish VAT (IVA) situations.

    Drawn from the TDP Step R-1 contract on issue #85. The member
    names and string values are the authoritative identifiers the
    downstream classifier layers (providers #73, categories #77,
    TDP engine) use to tag a transaction.
    """

    DOMESTIC_GENERAL_21 = "domestic_general_21"
    DOMESTIC_REDUCED_10 = "domestic_reduced_10"
    DOMESTIC_SUPER_REDUCED_4 = "domestic_super_reduced_4"
    DOMESTIC_ZERO = "domestic_zero"
    DOMESTIC_EXEMPT = "domestic_exempt"
    DOMESTIC_NOT_SUBJECT = "domestic_not_subject"
    INTRA_COMMUNITY_SUPPLY = "intra_community_supply"
    INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE = "intra_community_acquisition_reverse_charge"
    INTRA_COMMUNITY_TRIANGULATION = "intra_community_triangulation"
    EXPORT_THIRD_COUNTRY_ZERO_RATED = "export_third_country_zero_rated"
    IMPORT_THIRD_COUNTRY = "import_third_country"
    RECARGO_EQUIVALENCIA = "recargo_equivalencia"
    REGIMEN_SIMPLIFICADO = "regimen_simplificado"
    OPERACION_NO_SUJETA = "operacion_no_sujeta"
    ERRONEOUS_INVOICE = "erroneous_invoice"
    UNKNOWN = "unknown"


class EUMemberState(StrEnum):
    """Current 27 EU member states, ISO 3166-1 alpha-2 (lowercase).

    Alphabetically ordered by ISO code. The list reflects the
    composition of the European Union as of 2025 (post-Brexit,
    post-Croatia, Schengen-irrelevant).
    """

    AT = "at"
    BE = "be"
    BG = "bg"
    CY = "cy"
    CZ = "cz"
    DE = "de"
    DK = "dk"
    EE = "ee"
    ES = "es"
    FI = "fi"
    FR = "fr"
    GR = "gr"
    HR = "hr"
    HU = "hu"
    IE = "ie"
    IT = "it"
    LT = "lt"
    LU = "lu"
    LV = "lv"
    MT = "mt"
    NL = "nl"
    PL = "pl"
    PT = "pt"
    RO = "ro"
    SE = "se"
    SI = "si"
    SK = "sk"


class VATRateKind(StrEnum):
    """Closed catalogue of rate tiers referenced by :class:`VATRate`."""

    GENERAL = "general"
    REDUCED = "reduced"
    SUPER_REDUCED = "super_reduced"
    ZERO = "zero"
    EXEMPT = "exempt"


class CitationSource(StrEnum):
    """Closed catalogue of legal/regulatory sources cited by VAT rules."""

    LEY_37_1992 = "ley-37-1992"
    MANUAL_IVA_2025 = "manual-iva-2025"
    DIRECTIVE_2006_112_EC = "directive-2006-112-ec"
    OTHER = "other"


_ArticleRef = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
"""Free-form article reference shape, e.g. ``Art. 91.Uno.2.1º``."""


_SpanishQuote = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2048),
]
"""Non-empty Spanish quote extracted from (or paraphrased for) the citation."""


_BoeOrDirectiveRef = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=256),
]
"""Free-form reference to the BOE or Council Directive backing a rate."""


_ModeloRef = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^[0-9]{3}$"),
]
"""AEAT modelo number shape (three ASCII digits, e.g. ``303``)."""


_NormativeId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[a-z0-9][a-z0-9-]*$",
    ),
]
"""Kebab-case normative id shared with :mod:`aeat.normatives`."""


_ManualRef = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=256),
]
"""Free-form reference to a Manual práctico IVA rule id or section ref."""


def _require_spanish(translatable: Translatable, field_name: str) -> None:
    """Assert a translatable carries the authoritative ``es`` key.

    Args:
        translatable: The translatable mapping under validation.
        field_name: Dotted field name surfaced in the error message.

    Raises:
        ValueError: If the ``es`` key is missing or empty.
    """
    if not translatable.get("es"):
        raise ValueError(f"{field_name}: missing authoritative Spanish ('es') translation")


class _StrictFrozen(BaseModel):
    """Shared base config: strict validation, immutable, no extras."""

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
    )


class _StrictMutable(BaseModel):
    """Strict validation but mutable; used for aggregate catalogues."""

    model_config = ConfigDict(
        strict=True,
        frozen=False,
        extra="forbid",
    )


class VATRate(_StrictFrozen):
    """A single VAT rate line item keyed by member state + kind."""

    member_state: EUMemberState = Field(description="Issuing member state.")
    kind: VATRateKind = Field(description="Rate tier (general / reduced / ...).")
    pct: Decimal = Field(
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Rate percentage as a decimal in [0, 100].",
    )
    effective_from: date = Field(description="First date the rate applies.")
    effective_until: date | None = Field(
        default=None,
        description="Last date the rate applies, or ``None`` for open-ended.",
    )
    boe_or_directive_reference: _BoeOrDirectiveRef = Field(
        description=(
            "Free-form reference to the BOE entry or Council Directive "
            "article that backs this rate (e.g. 'Ley 37/1992 Art. 90.Uno')."
        ),
    )

    @model_validator(mode="after")
    def _validate_window(self) -> VATRate:
        """Ensure ``effective_from <= effective_until`` when both are set."""
        if self.effective_until is not None and self.effective_from > self.effective_until:
            raise ValueError(
                f"VATRate[{self.member_state.value}/{self.kind.value}]: "
                f"effective_from {self.effective_from} is after effective_until {self.effective_until}"
            )
        return self


class Citation(_StrictFrozen):
    """A legal / regulatory citation backing a :class:`VATRegulation`.

    The ``quoted_text_es`` field must be a non-empty Spanish string.
    It MAY be a faithful paraphrase of the article's statutory
    language when a verbatim extract is not practical; the
    paraphrase must match the article's subject matter and preserve
    the operative fiscal meaning. Auditability relies on the
    combination of ``source``, ``article`` and ``quoted_text_es``.
    """

    source: CitationSource = Field(description="Legal source of the citation.")
    article: _ArticleRef = Field(
        description="Article reference, e.g. 'Art. 91.Uno.2.1º'.",
    )
    url: AnyHttpUrl | None = Field(
        default=None,
        description="Optional deep link to the cited article.",
    )
    quoted_text_es: _SpanishQuote = Field(
        description="Non-empty Spanish quote (or faithful paraphrase).",
    )
    retrieval_date: date = Field(
        description="Date the citation was retrieved / last reviewed.",
    )


class VATRegulation(_StrictFrozen):
    """A single codified VAT rule for a :class:`VATCategory`.

    Every regulation carries at least one :class:`Citation`; the
    substrate-level invariant enforced by :func:`verify_catalogue`
    additionally requires every shipped regulation to cite real
    Ley 37/1992 articles so downstream tools can surface the legal
    backing of any classification.
    """

    category: VATCategory = Field(description="The VAT situation codified by this rule.")
    label: Translatable = Field(description="Short human-readable label.")
    description: Translatable = Field(description="One-paragraph plain-language description.")
    triggers_when: Translatable = Field(
        description="Plain-language description of when this rule fires.",
    )
    iva_treatment: Translatable = Field(
        description="Plain-language description of the fiscal treatment.",
    )
    declares_in_modelos: tuple[_ModeloRef, ...] = Field(
        description="AEAT modelo numbers (e.g. ('303', '349')) where this appears.",
    )
    requires_reverse_charge: bool = Field(
        description="Whether the rule triggers inversión del sujeto pasivo.",
    )
    requires_supplier_vat_id: bool = Field(
        description="Whether a supplier NIF-VAT is mandatory for this rule.",
    )
    boe_references: tuple[_NormativeId, ...] = Field(
        description="Normative ids (shared with aeat.normatives) backing this rule.",
    )
    manual_references: tuple[_ManualRef, ...] = Field(
        description="Optional Manual práctico IVA rule ids or section refs.",
    )
    citations: tuple[Citation, ...] = Field(
        description="At least one Citation is required.",
    )
    notes: str = Field(
        default="",
        description="Free-form reviewer notes.",
    )

    @model_validator(mode="after")
    def _validate(self) -> VATRegulation:
        """Enforce trilingual + citation invariants."""
        _require_spanish(self.label, f"VATRegulation[{self.category.value}].label")
        _require_spanish(self.description, f"VATRegulation[{self.category.value}].description")
        _require_spanish(self.triggers_when, f"VATRegulation[{self.category.value}].triggers_when")
        _require_spanish(self.iva_treatment, f"VATRegulation[{self.category.value}].iva_treatment")
        if not self.citations:
            raise ValueError(f"VATRegulation[{self.category.value}]: at least one Citation is required")
        return self


class VATCatalogue(_StrictMutable):
    """Aggregate view over a collection of :class:`VATRegulation`.

    The aggregate is mutable to keep the loader idiom simple (the
    loader populates the mapping incrementally). Individual
    :class:`VATRegulation` records remain frozen.
    """

    regulations: dict[VATCategory, VATRegulation] = Field(
        default_factory=dict,
        description="Regulations keyed by their VATCategory.",
    )

    @model_validator(mode="after")
    def _check_key_alignment(self) -> VATCatalogue:
        """Ensure every mapping key matches its record's category."""
        for key, regulation in self.regulations.items():
            if key != regulation.category:
                raise ValueError(
                    f"VATCatalogue: key {key!r} does not match regulation.category {regulation.category!r}"
                )
        return self

    def __iter__(self):  # type: ignore[override]
        """Iterate over every loaded :class:`VATRegulation`."""
        return iter(self.regulations.values())

    def __len__(self) -> int:
        """Return the number of loaded regulations."""
        return len(self.regulations)

    def __contains__(self, key: object) -> bool:
        """Check whether ``key`` names a loaded :class:`VATCategory`."""
        return key in self.regulations

    def get(self, category: VATCategory) -> VATRegulation | None:
        """Return the regulation for ``category`` or ``None`` if absent."""
        return self.regulations.get(category)


class VerificationIssue(_StrictFrozen):
    """A single finding produced by :func:`verify_catalogue`."""

    level: str = Field(description="'error' or 'warning'.")
    code: str = Field(description="Short, stable issue code.")
    message: str = Field(description="Human-readable detail.")
    category_id: str | None = Field(
        default=None,
        description="Affected VAT category value, if any.",
    )


class VerificationReport(_StrictFrozen):
    """Aggregate verification report for :class:`VATCatalogue`."""

    issues: tuple[VerificationIssue, ...] = Field(default_factory=tuple)

    @property
    def errors(self) -> tuple[VerificationIssue, ...]:
        """Return the subset of issues whose level is ``error``."""
        return tuple(issue for issue in self.issues if issue.level == "error")

    @property
    def clean(self) -> bool:
        """Return ``True`` when no error-level issues were found."""
        return not self.errors
