"""Strict pydantic v2 schema for the :mod:`aeat.domain.iva` subpackage.

Every record the subpackage exposes — enumerations, per-rate values,
citations, regulations, catalogues, verification reports — is defined here.
The schema is frozen and strict wherever the loader idiom permits it,
mirroring the pattern established by :mod:`aeat.domain.normatives._schema`.

Closed catalogues (:class:`IvaCategory`, :class:`EUMemberState`,
:class:`IvaRateKind`, :class:`IvaCitationSource`) are :class:`enum.StrEnum`
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
from typing import Annotated, override

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from ...core import STRICT_FROZEN_CONFIG
from ...core.i18n import Translatable as tr
from ._errors import IvaValidationError


class IvaCategory(StrEnum):
    """Closed catalogue of Spanish IVA (IVA) situations.

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


# IVA categories that legitimately bear no Modelo 303 cuota by law, so a
# ledger observation in one of these categories correctly matches no
# ``ledger_iva_aggregation`` cuota binding and MUST NOT be treated as a
# modelling gap. They are exempt, zero-rated, not-subject, exempt
# intra-community supplies/exports, or filed under a separate regime:
#
# - DOMESTIC_ZERO / DOMESTIC_EXEMPT / DOMESTIC_NOT_SUBJECT: no cuota
#   devengada arises (Ley 37/1992 arts. 7, 20, 26 exemptions / tipo cero).
# - OPERACION_NO_SUJETA: operación no sujeta — outside the IVA hecho
#   imponible (Ley 37/1992 art. 7).
# - INTRA_COMMUNITY_SUPPLY: entrega intracomunitaria exenta — zero cuota,
#   declared as base only (Ley 37/1992 art. 25, casilla 59).
# - EXPORT_THIRD_COUNTRY_ZERO_RATED: exportación exenta — zero cuota,
#   base only (Ley 37/1992 art. 21, casilla 60).
# - INTRA_COMMUNITY_TRIANGULATION: operación triangular informativa — no
#   cuota for the Spanish intermediary.
# - REGIMEN_SIMPLIFICADO: settled under the régimen simplificado modulo
#   path (Modelo 131), not the general 303 cuota bindings.
#
# This set is the cuota-less companion to the non-declarable sentinel set
# (recargo de equivalencia / unknown / erroneous) consumed at the
# application boundary. It exists so the #64 unconsumed-declarable advisory
# fires only on categories that genuinely SHOULD produce a 303 cuota but
# currently have no binding (reverse-charge / acquisitions / imports),
# never on these by-law cuota-less categories.
CUOTA_LESS_M303_IVA_CATEGORIES: frozenset[IvaCategory] = frozenset(
    {
        IvaCategory.DOMESTIC_ZERO,
        IvaCategory.DOMESTIC_EXEMPT,
        IvaCategory.DOMESTIC_NOT_SUBJECT,
        IvaCategory.OPERACION_NO_SUJETA,
        IvaCategory.INTRA_COMMUNITY_SUPPLY,
        IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
        IvaCategory.INTRA_COMMUNITY_TRIANGULATION,
        IvaCategory.REGIMEN_SIMPLIFICADO,
    },
)


class IvaExemptionArticle(StrEnum):
    """Closed catalogue of Ley 37/1992 Art. 20 sub-articles.

    Differentiates downstream-deduction routing on operations
    classified as :attr:`IvaCategory.DOMESTIC_EXEMPT`.

    The MVP set covers the three sub-articles whose deduction-right or
    Modelo 303 routing semantics diverge from the default
    ``DOMESTIC_EXEMPT`` collapse, plus a catch-all for other Art. 20
    cases. The discriminator is OPTIONAL on the classification result:
    ``None`` means the operation is exempt with no further sub-article
    distinction needed; a stamped value means the calculation chain can
    route to the sub-article-specific casilla (e.g. Modelo 303 casilla
    61 for `ART_20_UNO_26` artistas plena con prorrata).

    The discriminator's legal grounding follows Ley 37/1992
    (BOE-A-1992-28740). Each sub-article cites the matching article in
    its docstring; the registry-side casilla bindings carry the
    full ``legal_refs`` chain per the
    ``registry-calculation-legal-grounding`` rule.

    Authority: ``2026-06-03-iva-exemption-article-adr``.
    """

    ART_20_UNO_8 = "art_20_uno_8"
    """Enseñanza — exenta sin derecho a deducción (Ley 37/1992 Art. 20.Uno.8)."""

    ART_20_UNO_14 = "art_20_uno_14"
    """Sanitarios — exenta sin derecho a deducción (Ley 37/1992 Art. 20.Uno.14)."""

    ART_20_UNO_26 = "art_20_uno_26"
    """Servicios artísticos — exenta con plena prorrata (Ley 37/1992 Art. 20.Uno.26).
    Routes to Modelo 303 casilla 61."""

    ART_20_OTHER = "art_20_other"
    """Other Art. 20 sub-articles whose routing semantics do not yet
    warrant a dedicated enum slot. New slots open as their routing
    demands surface."""


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


class IvaRateKind(StrEnum):
    """Closed catalogue of rate tiers referenced by :class:`IvaRateRecord`."""

    GENERAL = "general"
    REDUCED = "reduced"
    SUPER_REDUCED = "super_reduced"
    ZERO = "zero"
    EXEMPT = "exempt"


class IvaCitationSource(StrEnum):
    """Closed catalogue of legal/regulatory sources cited by IVA rules."""

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
        IvaValidationError: If the translation key is missing or empty.
    """
    if not translatable:
        raise IvaValidationError(f"{field_name}: missing authoritative translation key")


class _IvaStrictFrozen(BaseModel):
    """Shared base config: strict validation, immutable, extras forbidden."""

    model_config = STRICT_FROZEN_CONFIG


class _IvaStrictMutable(BaseModel):
    """Strict validation mixin with mutable config for incrementally populated catalogues."""

    model_config = ConfigDict(
        strict=True,
        frozen=False,
        extra="forbid",
    )


class IvaRateRecord(_IvaStrictFrozen):
    """A single IVA rate line item keyed by member state and rate kind.

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
    kind: IvaRateKind = Field(description="Rate tier (general / reduced / ...).")
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
    def _validate_window(self) -> IvaRateRecord:
        """Ensure :attr:`effective_from` precedes :attr:`effective_until`."""
        if self.effective_until is not None and self.effective_from > self.effective_until:
            raise IvaValidationError(
                f"IvaRateRecord[{self.member_state.value}/{self.kind.value}]: "
                f"effective_from {self.effective_from} is after effective_until {self.effective_until}",
            )
        return self


class IvaCitation(_IvaStrictFrozen):
    """A legal or regulatory citation backing a :class:`IvaRegulation`.

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

    source: IvaCitationSource = Field(description="Legal source of the citation.")
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


class IvaRegulation(_IvaStrictFrozen):
    """A single codified IVA rule for a :class:`IvaCategory`.

    Every regulation carries at least one :class:`IvaCitation`. The
    substrate-level invariant enforced by
    :func:`aeat.domain.iva.verify_catalogue` additionally requires every
    shipped regulation to cite real legal articles so downstream tools
    can surface the legal backing of any classification.

    Attributes:
        category: The IVA situation codified by this rule.
        label: Short human-readable label key.
        description: One-paragraph plain-language description key.
        triggers_when: Plain-language description of when this rule fires (key).
        iva_treatment: Plain-language description of the fiscal treatment (key).
        requires_reverse_charge: Whether the rule triggers
            *inversión del sujeto pasivo*.
        requires_supplier_iva_id: Whether a supplier NIF-IVA is mandatory.
        boe_references: Normative ids (shared with
            :mod:`aeat.domain.normatives`) backing this rule.
        manual_references: Optional Manual práctico IVA rule ids or section
            references.
        citations: At least one :class:`IvaCitation` is required.
        notes: Free-form reviewer notes.
    """

    category: IvaCategory = Field(description="The IVA situation codified by this rule.")
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
    requires_supplier_iva_id: bool = Field(
        description="Whether a supplier NIF-IVA is mandatory for this rule.",
    )
    boe_references: tuple[_NormativeId, ...] = Field(
        description="Normative ids (shared with aeat.domain.normatives) backing this rule.",
    )
    manual_references: tuple[_ManualRef, ...] = Field(
        description="Optional Manual práctico IVA rule ids or section refs.",
    )
    citations: tuple[IvaCitation, ...] = Field(
        description="At least one IvaCitation is required.",
    )
    notes: str = Field(
        default="",
        description="Free-form reviewer notes.",
    )

    @model_validator(mode="after")
    def _validate(self) -> IvaRegulation:
        """Enforce the translation-key and at-least-one-citation invariants."""
        _require_translatable(self.label, f"IvaRegulation[{self.category.value}].label")
        _require_translatable(self.description, f"IvaRegulation[{self.category.value}].description")
        _require_translatable(self.triggers_when, f"IvaRegulation[{self.category.value}].triggers_when")
        _require_translatable(self.iva_treatment, f"IvaRegulation[{self.category.value}].iva_treatment")
        if not self.citations:
            raise IvaValidationError(f"IvaRegulation[{self.category.value}]: at least one IvaCitation is required")
        return self


class IvaCatalogue(_IvaStrictMutable):
    """Aggregate view over a collection of :class:`IvaRegulation` records.

    The aggregate is mutable to keep the loader idiom simple — the loader
    populates the mapping incrementally. Individual :class:`IvaRegulation`
    records remain frozen.

    Attributes:
        regulations: Regulations keyed by their
            :class:`IvaCategory`.
    """

    regulations: dict[IvaCategory, IvaRegulation] = Field(
        default_factory=dict,
        description="Regulations keyed by their IvaCategory.",
    )

    @model_validator(mode="after")
    def _check_key_alignment(self) -> IvaCatalogue:
        """Ensure every mapping key matches its record's :attr:`IvaRegulation.category`."""
        for key, regulation in self.regulations.items():
            if key != regulation.category:
                raise IvaValidationError(
                    f"IvaCatalogue: key {key!r} does not match regulation.category {regulation.category!r}",
                )
        return self

    @override
    def __iter__(self) -> Iterator[IvaRegulation]:  # pyright: ignore[reportIncompatibleMethodOverride]  # ty: ignore[invalid-method-override]  # pyrefly: ignore[bad-override]  # reason: intentional pydantic catalogue iteration shim — yields domain items not field-value tuples
        """Iterate over every loaded :class:`IvaRegulation`."""
        return iter(self.regulations.values())

    def __len__(self) -> int:
        """Return the number of loaded :class:`IvaRegulation` records."""
        return len(self.regulations)

    def __contains__(self, key: object) -> bool:
        """Return ``True`` when ``key`` names a loaded :class:`IvaCategory`."""
        return key in self.regulations

    def get(self, category: IvaCategory) -> IvaRegulation | None:
        """Return the :class:`IvaRegulation` for ``category`` or ``None`` if absent."""
        return self.regulations.get(category)


class IvaVerificationIssue(_IvaStrictFrozen):
    """A single finding produced by :func:`aeat.domain.iva.verify_catalogue`.

    Attributes:
        level: Severity, either ``"error"`` or ``"warning"``.
        code: Short stable issue code.
        message: Human-readable detail.
        category_id: Affected IVA category value, if any.
    """

    level: str = Field(description="'error' or 'warning'.")
    code: str = Field(description="Short, stable issue code.")
    message: str = Field(description="Human-readable detail.")
    category_id: str | None = Field(
        default=None,
        description="Affected IVA category value, if any.",
    )


class IvaVerificationReport(_IvaStrictFrozen):
    """Aggregate verification report for a :class:`IvaCatalogue`.

    Attributes:
        issues: All findings produced by
            :func:`aeat.domain.iva.verify_catalogue`.
    """

    issues: tuple[IvaVerificationIssue, ...] = Field(default_factory=tuple)

    @property
    def errors(self) -> tuple[IvaVerificationIssue, ...]:
        """Return the subset of issues whose :attr:`IvaVerificationIssue.level` is ``"error"``.

        Returns:
            Tuple of :class:`IvaVerificationIssue` objects with error-level severity.
        """
        return tuple(issue for issue in self.issues if issue.level == "error")

    @property
    def clean(self) -> bool:
        """Return ``True`` when no error-level issues were found."""
        return not self.errors
