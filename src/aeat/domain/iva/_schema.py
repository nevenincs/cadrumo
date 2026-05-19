"""Strict pydantic v2 schema for the :mod:`aeat.domain.vat` subpackage.

Every record the subpackage exposes — enumerations, per-rate values,
citations, regulations, catalogues, verification reports — is defined here.
The schema is frozen and strict wherever the loader idiom permits it,
mirroring the pattern established by :mod:`aeat.domain.normatives._schema`.

Closed catalogues (:class:`VATCategory`, :class:`EUMemberState`,
:class:`VATRateKind`, :class:`VatCitationSource`) are :class:`enum.StrEnum`
subclasses. Multilingual fields use :class:`aeat.core.i18n.tr` to ensure
the internationalization engine can dynamically resolve the correct locale
at runtime for UI labels and descriptions. Legal quotes remain Spanish-
authoritative.
"""

from __future__ import annotations

from collections.abc import Iterator
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

from ...core.i18n import Translatable as tr
from .errors import VatValidationError


class VATCategory(StrEnum):
    """Closed catalogue of Spanish VAT (IVA) situations.

    The member names and string values are the authoritative identifiers used
    by the downstream classifier layers (financial providers, the spending
    category taxonomy, and the transaction-data-pipeline engine) to tag a
    transaction.
    """

    DOMESTIC_GENERAL_21 = "domestic_general_21"
    DOMESTIC_REDUCED_10 = "domestic_reduced_10"
    DOMESTIC_SUPER_REDUCED_4 = "domestic_super_reduced_4"
    DOMESTIC_ZERO = "domestic_zero"
    DOMESTIC_EXEMPT = "domestic_exempt"
    DOMESTIC_NOT_SUBJECT = "domestic_not_subject"
    DOMESTIC_REVERSE_CHARGE = "domestic_reverse_charge"
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

    Alphabetically ordered by ISO code. The list reflects the composition of
    the European Union after Brexit and after Croatia's accession; Schengen
    membership is irrelevant to this taxonomy.
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


class VatCitationSource(StrEnum):
    """Closed catalogue of legal/regulatory sources cited by VAT rules."""

    LEY_37_1992 = "ley-37-1992"
    MANUAL_IVA_2025 = "manual-iva-2025"
    DIRECTIVE_2006_112_EC = "directive-2006-112-ec"
    OTHER = "other"


_ArticleRef = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
"""Free-form article reference shape, for example ``Art. 91.Uno.2.1º``."""


_BoeOrDirectiveRef = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=256),
]
"""Free-form reference to the BOE entry or Council Directive backing a rate."""


_NormativeId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[a-z0-9][a-z0-9-]*$",
    ),
]
"""Kebab-case normative id shared with :mod:`aeat.domain.normatives`."""


_ManualRef = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=256),
]
"""Free-form reference to a Manual práctico IVA rule id or section reference."""


def _require_translatable(translatable: tr, field_name: str) -> None:
    """Assert a :class:`aeat.core.i18n.tr` carries a non-empty translation key.

    Args:
        translatable: The translatable mapping under validation.
        field_name: Dotted field name surfaced in the error message.

    Raises:
        :exc:`ValueError`: If the translation key is missing or empty.
    """
    if not translatable:
        raise VatValidationError(f"{field_name}: missing authoritative translation key")


class _VatStrictFrozen(BaseModel):
    """Shared base config: strict validation, immutable, extras forbidden."""

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
    )


class _VatStrictMutable(BaseModel):
    """Strict validation but mutable; used for aggregate catalogues that the
    loader populates incrementally."""

    model_config = ConfigDict(
        strict=True,
        frozen=False,
        extra="forbid",
    )


class VATRate(_VatStrictFrozen):
    """A single VAT rate line item keyed by member state and rate kind.

    Attributes:
        member_state: Issuing member state.
        kind: Rate tier (general / reduced / ...).
        pct: Rate percentage as a :class:`~decimal.Decimal` in ``[0, 100]``.
        effective_from: First date the rate applies.
        effective_until: Last date the rate applies, or ``None`` for
            open-ended.
        boe_or_directive_reference: Free-form reference to the BOE entry or
            Council Directive article that backs this rate.
    """

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
        """Ensure :attr:`effective_from` precedes :attr:`effective_until`."""
        if self.effective_until is not None and self.effective_from > self.effective_until:
            raise VatValidationError(
                f"VATRate[{self.member_state.value}/{self.kind.value}]: "
                f"effective_from {self.effective_from} is after effective_until {self.effective_until}"
            )
        return self


class VatCitation(_VatStrictFrozen):
    """A legal or regulatory citation backing a :class:`VATRegulation`.

    The :attr:`quoted_text` field must be an authoritative translation key
    pointing to a non-empty Spanish string. It may be a faithful paraphrase
    of the article's statutory language when a verbatim extract is not
    practical. Auditability relies on the combination of :attr:`source`,
    :attr:`article` and :attr:`quoted_text`.

    Attributes:
        source: Legal source of the citation.
        article: Article reference, for example ``Art. 91.Uno.2.1º``.
        url: Optional deep link to the cited article.
        quoted_text: Non-empty Spanish quote or faithful paraphrase.
        retrieval_date: Date the citation was retrieved or last reviewed.
    """

    source: VatCitationSource = Field(description="Legal source of the citation.")
    article: _ArticleRef = Field(
        description="Article reference, e.g. 'Art. 91.Uno.2.1º'.",
    )
    url: AnyHttpUrl | None = Field(
        default=None,
        description="Optional deep link to the cited article.",
    )
    quoted_text: tr = Field(
        description="Non-empty Spanish quote (or faithful paraphrase).",
    )
    retrieval_date: date = Field(
        description="Date the citation was retrieved / last reviewed.",
    )


class VATRegulation(_VatStrictFrozen):
    """A single codified VAT rule for a :class:`VATCategory`.

    Every regulation carries at least one :class:`VatCitation`. The
    substrate-level invariant enforced by
    :func:`aeat.domain.vat.verify_catalogue` additionally requires every
    shipped regulation to cite real legal articles so downstream tools
    can surface the legal backing of any classification.

    Attributes:
        category: The VAT situation codified by this rule.
        label: Short human-readable label key.
        description: One-paragraph plain-language description key.
        triggers_when: Plain-language description of when this rule fires (key).
        iva_treatment: Plain-language description of the fiscal treatment (key).
        requires_reverse_charge: Whether the rule triggers
            *inversión del sujeto pasivo*.
        requires_supplier_vat_id: Whether a supplier NIF-VAT is mandatory.
        boe_references: Normative ids (shared with
            :mod:`aeat.domain.normatives`) backing this rule.
        manual_references: Optional Manual práctico IVA rule ids or section
            references.
        citations: At least one :class:`VatCitation` is required.
        notes: Free-form reviewer notes.
    """

    category: VATCategory = Field(description="The VAT situation codified by this rule.")
    label: tr = Field(description="Short human-readable label key.")
    description: tr = Field(description="One-paragraph plain-language description key.")
    triggers_when: tr = Field(
        description="Plain-language description of when this rule fires (key).",
    )
    iva_treatment: tr = Field(
        description="Plain-language description of the fiscal treatment (key).",
    )
    requires_reverse_charge: bool = Field(
        description="Whether the rule triggers inversión del sujeto pasivo.",
    )
    requires_supplier_vat_id: bool = Field(
        description="Whether a supplier NIF-VAT is mandatory for this rule.",
    )
    boe_references: tuple[_NormativeId, ...] = Field(
        description="Normative ids (shared with aeat.domain.normatives) backing this rule.",
    )
    manual_references: tuple[_ManualRef, ...] = Field(
        description="Optional Manual práctico IVA rule ids or section refs.",
    )
    citations: tuple[VatCitation, ...] = Field(
        description="At least one VatCitation is required.",
    )
    notes: str = Field(
        default="",
        description="Free-form reviewer notes.",
    )

    @model_validator(mode="after")
    def _validate(self) -> VATRegulation:
        """Enforce the translation-key and at-least-one-citation invariants."""
        _require_translatable(self.label, f"VATRegulation[{self.category.value}].label")
        _require_translatable(self.description, f"VATRegulation[{self.category.value}].description")
        _require_translatable(self.triggers_when, f"VATRegulation[{self.category.value}].triggers_when")
        _require_translatable(self.iva_treatment, f"VATRegulation[{self.category.value}].iva_treatment")
        if not self.citations:
            raise VatValidationError(f"VATRegulation[{self.category.value}]: at least one VatCitation is required")
        return self


class VATCatalogue(_VatStrictMutable):
    """Aggregate view over a collection of :class:`VATRegulation` records.

    The aggregate is mutable to keep the loader idiom simple — the loader
    populates the mapping incrementally. Individual :class:`VATRegulation`
    records remain frozen.

    Attributes:
        regulations: Regulations keyed by their
            :class:`VATCategory`.
    """

    regulations: dict[VATCategory, VATRegulation] = Field(
        default_factory=dict,
        description="Regulations keyed by their VATCategory.",
    )

    @model_validator(mode="after")
    def _check_key_alignment(self) -> VATCatalogue:
        """Ensure every mapping key matches its record's :attr:`VATRegulation.category`."""
        for key, regulation in self.regulations.items():
            if key != regulation.category:
                raise VatValidationError(
                    f"VATCatalogue: key {key!r} does not match regulation.category {regulation.category!r}"
                )
        return self

    def __iter__(self) -> Iterator[VATRegulation]:  # pyright: ignore[reportIncompatibleMethodOverride]  # ty: ignore[invalid-method-override]  # pyrefly: ignore[bad-override]  # reason: intentional pydantic catalogue iteration shim — yields domain items not field-value tuples
        """Iterate over every loaded :class:`VATRegulation`."""
        return iter(self.regulations.values())

    def __len__(self) -> int:
        """Return the number of loaded :class:`VATRegulation` records."""
        return len(self.regulations)

    def __contains__(self, key: object) -> bool:
        """Return ``True`` when ``key`` names a loaded :class:`VATCategory`."""
        return key in self.regulations

    def get(self, category: VATCategory) -> VATRegulation | None:
        """Return the regulation for ``category`` or ``None`` if absent."""
        return self.regulations.get(category)


class VatVerificationIssue(_VatStrictFrozen):
    """A single finding produced by :func:`aeat.domain.vat.verify_catalogue`.

    Attributes:
        level: Severity, either ``"error"`` or ``"warning"``.
        code: Short stable issue code.
        message: Human-readable detail.
        category_id: Affected VAT category value, if any.
    """

    level: str = Field(description="'error' or 'warning'.")
    code: str = Field(description="Short, stable issue code.")
    message: str = Field(description="Human-readable detail.")
    category_id: str | None = Field(
        default=None,
        description="Affected VAT category value, if any.",
    )


class VatVerificationReport(_VatStrictFrozen):
    """Aggregate verification report for a :class:`VATCatalogue`.

    Attributes:
        issues: All findings produced by
            :func:`aeat.domain.vat.verify_catalogue`.
    """

    issues: tuple[VatVerificationIssue, ...] = Field(default_factory=tuple)

    @property
    def errors(self) -> tuple[VatVerificationIssue, ...]:
        """Return the subset of issues whose :attr:`VatVerificationIssue.level` is ``"error"``."""
        return tuple(issue for issue in self.issues if issue.level == "error")

    @property
    def clean(self) -> bool:
        """Return ``True`` when no error-level issues were found."""
        return not self.errors
