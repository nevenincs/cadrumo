"""LLM classifier contracts with a parametric prompt builder.

Defines the :class:`LLMClassifier` and :class:`LLMSplitProposer` protocols and
the allow-list-guarded response parsing every classifier answer passes through.
Concrete transports live outside this module: the on-host readers in the gated
inference package, and a subprocess harness on the test side. The subprocess
CLI implementations that once lived here were the off-host route, and they were
deleted with it.

This module keeps the part that is a SAFETY contract rather than a transport --
the prompt spec and the parse that confine a model to selecting
``classification`` / ``category`` / ``iva_category`` and never emitting a
regulated number. That belongs in the domain, not behind an optional install.

The prompt is built
PROGRAMMATICALLY from the available enum values so the LLM prompt
stays in sync with :class:`cadrumo.domain.transactions.BusinessClassification`:
adding a new value automatically requires a developer to decide
whether it belongs in the default LLM choice set.

The prompt spec is parametrized:

- ``classifications``: which :class:`cadrumo.domain.transactions.BusinessClassification`
  values the LLM may pick. Defaults to the four *decision* states
  (``BUSINESS`` / ``PERSONAL`` / ``MIXED`` / ``PROCESSED_UNCLASSIFIED``).
  Pipeline-state values (``NOT_YET_PROCESSED``, ``SKIPPED_BY_RULE``,
  ``FAILED_VALIDATION``) are excluded because they are not LLM
  decisions -- they are internal pipeline bookkeeping.
- ``categories``: optional :class:`cadrumo.domain.categories.SpendingCategory`
  values the LLM may additionally attach. Empty by default
  (classification-only). When populated, the response includes a
  ``category`` field.

Every decision the LLM emits is validated against the spec's
allow-list via :func:`parse_response`: a response that picks a value
outside the allowed set raises :class:`LLMClassifierError`, so a
hallucinating model cannot corrupt the catalogue.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field, field_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.i18n import tr as _tr
from ...core.logging import get_logger
from ..categories import SpendingCategory, resolve_category_profiles
from ..iva import IvaCategory
from ._enums import BusinessClassification
from .errors import LLMClassifierError, TransactionValidationError
from ._model_tier import MINIMUM_CLASSIFICATION_TIER, ModelProfile, ModelTier
from ._models import Transaction

_logger = get_logger(__name__)

_CONFIDENCE_MIN = Decimal("0")
_CONFIDENCE_MAX = Decimal("1")
_DEFAULT_TIMEOUT_SECONDS = 120.0
_REASON_MAX_LENGTH = 2048

# ── response model ────────────────────────────────────────────────


class LLMClassificationResponse(BaseModel):
    """One LLM-emitted classification result for a transaction."""

    model_config = _STRICT_FROZEN

    classification: BusinessClassification
    confidence: Decimal
    reason: str = Field(min_length=1, max_length=_REASON_MAX_LENGTH)
    category: SpendingCategory | None = None
    iva_category: IvaCategory | None = None
    business_pct: Decimal | None = None
    multiple_components: bool | None = None
    """Evidence-read multiplicity judgement: True when the attached invoice carries
    multiple distinct rate/category lines that warrant a split into independently
    filable base/IVA children. ``None`` when no evidence was read (the model cannot
    judge multiplicity from the bank row alone). A boolean judgement, not an
    allow-list value, so hallucination containment is unaffected; it only drives a
    non-blocking split *recommendation*, never a write."""

    @field_validator("confidence")
    @classmethod
    def _check_confidence_range(cls, value: Decimal) -> Decimal:
        """Restrict confidence to the inclusive 0..1 range."""
        if not _CONFIDENCE_MIN <= value <= _CONFIDENCE_MAX:
            raise TransactionValidationError("confidence must be within the inclusive 0..1 range")
        return value

    @field_validator("business_pct")
    @classmethod
    def _check_business_pct_range(cls, value: Decimal | None) -> Decimal | None:
        """Restrict the proposed MIXED business percentage to the inclusive 0..1 range.

        The model only *proposes* the split direction; the percentage is a
        non-regulated hint the operator confirms. ``None`` is the common case
        (BUSINESS / PERSONAL suggestions carry no percentage).
        """
        if value is not None and not _CONFIDENCE_MIN <= value <= _CONFIDENCE_MAX:
            raise TransactionValidationError("business_pct must be within the inclusive 0..1 range")
        return value

    @field_validator("reason")
    @classmethod
    def _strip_reason(cls, value: str) -> str:
        """Trim whitespace and reject empty reasons."""
        trimmed = value.strip()
        if not trimmed:
            raise TransactionValidationError("reason must not be empty")
        return trimmed


class LLMSplitChild(BaseModel):
    """One proposed child of an evidence-driven transaction split.

    The model proposes a *proportion* of the parent (a fraction, like
    ``business_pct``) plus the selections for that child; the application derives
    each child's euro amount from the parent gross and the regulated tax substrate
    from the registry. The model never emits a euro amount or a regulated number
    (``llm-selects-system-derives-tax-numbers``).
    """

    model_config = _STRICT_FROZEN

    proportion: Decimal
    category: SpendingCategory | None = None
    iva_category: IvaCategory | None = None
    evidence_citation: str = Field(default="", max_length=_REASON_MAX_LENGTH)

    @field_validator("proportion")
    @classmethod
    def _check_proportion(cls, value: Decimal) -> Decimal:
        """Restrict each child proportion to the half-open (0, 1] range."""
        if not (_CONFIDENCE_MIN < value <= _CONFIDENCE_MAX):
            raise TransactionValidationError("each split child proportion must be within (0, 1]")
        return value


class LLMSplitResponse(BaseModel):
    """An evidence-driven split proposal: children whose proportions sum to one.

    A proposal of **one** child (proportion ``1.0``) is the "no split warranted"
    verdict — the model read the invoice and judged it a single line/rate. The
    application surfaces that verdict for review and never applies a degenerate
    one-way split. Two or more children is a genuine split recommendation.
    """

    model_config = _STRICT_FROZEN

    children: tuple[LLMSplitChild, ...]
    reason: str = Field(min_length=1, max_length=_REASON_MAX_LENGTH)

    @property
    def recommends_split(self) -> bool:
        """True when the model proposes more than one child (a genuine split)."""
        return len(self.children) > 1

    @field_validator("children")
    @classmethod
    def _check_children(cls, value: tuple[LLMSplitChild, ...]) -> tuple[LLMSplitChild, ...]:
        """Require at least one child whose proportions sum to ~1.0.

        One child is the no-split verdict; two or more is a split. Either way the
        proportions must sum to approximately 1.0 (a single child must therefore
        carry proportion 1.0).
        """
        if not value:
            raise TransactionValidationError("a split proposal must carry at least one child")
        total = sum((child.proportion for child in value), Decimal("0"))
        if abs(total - _CONFIDENCE_MAX) > Decimal("0.01"):
            raise TransactionValidationError("split child proportions must sum to approximately 1.0")
        return value

    @field_validator("reason")
    @classmethod
    def _strip_reason(cls, value: str) -> str:
        """Trim whitespace and reject empty reasons."""
        trimmed = value.strip()
        if not trimmed:
            raise TransactionValidationError("reason must not be empty")
        return trimmed


# ── protocol ──────────────────────────────────────────────────────


class LLMClassifier(Protocol):
    """Classify one transaction with an LLM-generated decision."""

    @property
    def decided_by(self) -> str:
        """Return the ``classified_by`` identifier this classifier emits."""
        ...

    def classify(self, transaction: Transaction, *, evidence_text: str | None = None) -> LLMClassificationResponse:
        """Return one classification decision for ``transaction``.

        Args:
            transaction: The transaction to classify.
            evidence_text: Optional on-host-extracted attached-evidence text to
                inject into the prompt. Gating of whether evidence may reach a given
                (on-host vs cloud) classifier is the caller's responsibility.

        Returns:
            A :class:`LLMClassificationResponse` with the classification result.
        """
        ...


@runtime_checkable
class LLMSplitProposer(Protocol):
    """Propose an evidence-driven N-way split for one transaction."""

    @property
    def decided_by(self) -> str:
        """Return the ``classified_by`` identifier this proposer emits."""
        ...

    def propose_split(self, transaction: Transaction, *, evidence_text: str | None = None) -> LLMSplitResponse:
        """Return an N-way split proposal for ``transaction``.

        Args:
            transaction: The transaction to split.
            evidence_text: Optional on-host-extracted attached-evidence text to
                inject into the prompt.

        Returns:
            A validated :class:`LLMSplitResponse`.
        """
        ...


# ── parametric prompt builder ─────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ClassificationChoice:
    """One allowed :class:`BusinessClassification` paired with an LLM-facing hint."""

    value: BusinessClassification
    hint: str


@dataclass(frozen=True, slots=True)
class CategoryChoice:
    """One allowed :class:`SpendingCategory` paired with an LLM-facing hint."""

    value: SpendingCategory
    hint: str


@dataclass(frozen=True, slots=True)
class IvaCategoryChoice:
    """One allowed :class:`cadrumo.domain.iva.IvaCategory` paired with an LLM-facing hint."""

    value: IvaCategory
    hint: str


# Descriptive hints for the four LLM-addressable classification states. Kept
# as module constants so the descriptions live next to their values and can
# be overridden by callers that build a custom PromptSpec.
_DEFAULT_CLASSIFICATION_HINTS: dict[BusinessClassification, str] = {
    BusinessClassification.BUSINESS: "certain business expense or income",
    BusinessClassification.PERSONAL: "certain personal expense or income",
    BusinessClassification.MIXED: "partially business, partially personal",
    BusinessClassification.PROCESSED_UNCLASSIFIED: ("you looked at it carefully but cannot decide either way"),
}

# Pipeline-internal states the LLM must never pick. Any classification in
# this set in an LLM response is rejected as a hallucination.
PIPELINE_ONLY_CLASSIFICATIONS: frozenset[BusinessClassification] = frozenset(
    {
        BusinessClassification.NOT_YET_PROCESSED,
        BusinessClassification.SKIPPED_BY_RULE,
        BusinessClassification.FAILED_VALIDATION,
    },
)


def default_classification_choices() -> tuple[ClassificationChoice, ...]:
    """Return the default allowed-classifications tuple used by the prompt.

    Returns:
        Tuple of :class:`ClassificationChoice` objects for each allowed category.
    """
    return tuple(ClassificationChoice(value=value, hint=hint) for value, hint in _DEFAULT_CLASSIFICATION_HINTS.items())


@dataclass(frozen=True)
class PromptSpec:
    """Parametrized classification prompt spec.

    The prompt and the response allow-list are derived from the same
    tuple of choices so they cannot drift. A response whose
    classification is not in ``allowed_classifications()`` is rejected
    by :func:`parse_response` regardless of how well-formed the JSON is.
    """

    classifications: tuple[ClassificationChoice, ...] = field(
        default_factory=default_classification_choices,
    )
    categories: tuple[CategoryChoice, ...] = ()
    iva_categories: tuple[IvaCategoryChoice, ...] = ()
    header: str = "You are classifying a Spanish autónomo's bank transaction for tax purposes."

    def allowed_classifications(self) -> frozenset[BusinessClassification]:
        """Return the set of :class:`BusinessClassification` values the LLM is allowed to emit."""
        return frozenset(choice.value for choice in self.classifications)

    def allowed_categories(self) -> frozenset[SpendingCategory]:
        """Return the set of category values the LLM is allowed to emit (empty = none).

        Returns:
            Frozenset of :class:`SpendingCategory` values the LLM may emit.
        """
        return frozenset(choice.value for choice in self.categories)

    def allowed_iva_categories(self) -> frozenset[IvaCategory]:
        """Return the set of :class:`cadrumo.domain.iva.IvaCategory` values the LLM may emit (empty = none).

        Returns:
            Frozenset of :class:`cadrumo.domain.iva.IvaCategory` values the LLM may
            select from; empty when the spec does not ask for an IVA category.
        """
        return frozenset(choice.value for choice in self.iva_categories)

    def render(
        self,
        transaction: Transaction,
        *,
        evidence_text: str | None = None,
        evidence_image_present: bool = False,
    ) -> str:
        """Render the prompt for ``transaction`` against this spec.

        Args:
            transaction: The transaction to classify.
            evidence_text: Optional on-host-extracted text of an attached evidence
                document (e.g. a purchase invoice). When present it is injected into
                the prompt for the model to read; the model uses it only to select
                the classification/category/iva_category and must never copy a euro
                figure from it (the regulated numbers stay registry-derived).
            evidence_image_present: Set when the evidence is attached as an image
                (the on-host vision-read path) instead of inlined text; the prompt
                then points the model at the attached image.
        """
        return _render_prompt(
            self,
            transaction,
            evidence_text=evidence_text,
            evidence_image_present=evidence_image_present,
        )


def default_prompt_spec() -> PromptSpec:
    """Return the default :class:`PromptSpec`: classification-only, four decision states."""
    return PromptSpec()


def prompt_spec_with_every_spending_category(
    *,
    classifications: tuple[ClassificationChoice, ...] | None = None,
) -> PromptSpec:
    """Return a prompt spec that also asks the LLM to suggest a SpendingCategory.

    Pulls authoritative Spanish display labels from
    :data:`cadrumo.domain.categories.resolve_category_profiles(2025)` rather than
    inventing ad-hoc hints from the enum value -- the LLM picks
    categories far more accurately against the real AEAT terminology
    than against mangled snake_case. Categories with no registered
    profile (none today; every
    :class:`cadrumo.domain.categories.SpendingCategory` member is covered)
    fall back to the humanised enum value.

    Args:
        classifications: Optional override for the classification
            choices; defaults to :func:`default_classification_choices`.

    Returns:
        A :class:`PromptSpec` whose ``categories`` tuple covers every
        registered :class:`cadrumo.domain.categories.SpendingCategory`.
    """
    category_choices = tuple(CategoryChoice(value=value, hint=_category_hint(value)) for value in SpendingCategory)
    return PromptSpec(
        classifications=classifications or default_classification_choices(),
        categories=category_choices,
    )


# Concise model-facing descriptions for each closed Spanish IVA situation.
# Model-facing only: these reach the prompt body, never a rendered operator
# surface, which is why they are hardcoded English rather than translation
# keys. These hint the model's SELECTION; they do not ground a number —
# the rate is looked up from the registry and the base/amount derived
# downstream. The IVA catalogue's own ``label`` fields are i18n keys that are
# not carried in the locale catalogues, so they cannot serve as hints; these
# curated one-liners are the authoritative prompt descriptions instead.
_IVA_CATEGORY_HINTS: dict[IvaCategory, str] = {
    IvaCategory.DOMESTIC_GENERAL: "domestic supply at the general 21% rate",
    IvaCategory.DOMESTIC_REDUCED: "reduced 10% rate (hospitality, transport, some foods)",
    IvaCategory.DOMESTIC_SUPER_REDUCED: "super-reduced 4% rate (basic foods, books, medicines)",
    IvaCategory.DOMESTIC_ZERO: "domestic supply at a 0% rate",
    IvaCategory.DOMESTIC_EXEMPT: "domestic supply exempt from IVA (education, health, finance — Art. 20)",
    IvaCategory.DOMESTIC_NOT_SUBJECT: "operation not subject to Spanish IVA",
    # No RATE is stated on purpose: the compensación percentages differ by
    # activity and have moved, and a stale figure in a classifier hint would
    # steer a classification the filing then carries. The article is what
    # distinguishes it, and it is the one this codebase already grounds the
    # compensación on (_LIVA_REAGP_COMPENSACION).
    IvaCategory.REAGP_COMPENSATION: (
        "REAGP compensación a tanto alzado — the buyer pays a farmer, forester or fisher under the "
        "special agriculture regime instead of repercutido IVA (LIVA Art. 130); it is NOT IVA the "
        "supplier charged"
    ),
    IvaCategory.DOMESTIC_REVERSE_CHARGE: "domestic reverse charge — the recipient self-assesses IVA (Art. 84)",
    IvaCategory.INTRA_COMMUNITY_SUPPLY: "exempt intra-community supply of goods to an EU business (Art. 25)",
    IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE: "reverse-charge EU goods acquisition",
    IvaCategory.INTRA_COMMUNITY_TRIANGULATION: "intra-community triangular operation",
    # The services pair states what separates it from the goods pair above,
    # because that is the one distinction the auto-derived fallback hint cannot
    # convey: a service and an entrega both show no Spanish cuota, for
    # different legal reasons, and the reason is what a filing cites.
    IvaCategory.INTRA_COMMUNITY_SERVICE_SUPPLY: (
        "service supplied to an EU business — NOT SUBJECT to Spanish IVA because Art. 69.Uno.1 "
        "locates it where the customer is established; this is a SERVICE, not the Art. 25 "
        "exempt supply of goods"
    ),
    IvaCategory.INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE: (
        "service received from an EU supplier — reverse charge, the Spanish recipient "
        "self-assesses IVA under Art. 84.Uno.2; this is a SERVICE, not a goods acquisition"
    ),
    IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED: "export of goods outside the EU, zero-rated (Art. 21)",
    IvaCategory.EXPORT_ASSIMILATED_ZERO_RATED: "operation assimilated to an export, exempt/zero-rated (Art. 22)",
    IvaCategory.IMPORT_THIRD_COUNTRY: "import of goods from outside the EU",
    IvaCategory.RECARGO_EQUIVALENCIA: "purchase subject to the recargo de equivalencia surcharge",
    IvaCategory.REGIMEN_SIMPLIFICADO: "régimen simplificado (modules), not a general-regime invoice",
    IvaCategory.OPERACION_NO_SUJETA: "operation outside the scope of Spanish IVA",
    IvaCategory.ERRONEOUS_INVOICE: "erroneous invoice flagged for correction",
    IvaCategory.UNKNOWN: "IVA situation not yet determined",
}


def default_iva_category_choices() -> tuple[IvaCategoryChoice, ...]:
    """Return the grounded IVA-category choices for the saturation prompt.

    The allow-list is the closed :class:`cadrumo.domain.iva.IvaCategory` enum (the
    registry :class:`cadrumo.domain.iva.IvaCatalogue` is validated to carry a
    regulation for every member, so the enum and the catalogue set are
    identical). Each choice is hinted with a concise description from
    :data:`_IVA_CATEGORY_HINTS`. The model SELECTS a category only; every
    regulated euro figure is derived downstream from the registry rate, never
    emitted by the model.

    Returns:
        One :class:`IvaCategoryChoice` per :class:`cadrumo.domain.iva.IvaCategory`,
        ordered by enum declaration.
    """
    return tuple(
        IvaCategoryChoice(value=category, hint=_IVA_CATEGORY_HINTS.get(category, category.value.replace("_", " ")))
        for category in IvaCategory
    )


def prompt_spec_with_saturation_fields(
    *,
    classifications: tuple[ClassificationChoice, ...] | None = None,
) -> PromptSpec:
    """Return a prompt spec for full saturation: spending + IVA category selection.

    Extends :func:`prompt_spec_with_every_spending_category` with the
    registry-grounded IVA-category allow-list (and invites a proposed MIXED
    ``business_pct``) so one reviewed suggestion can carry the rich tax
    metadata. The model selects categories only; the regulated rate, taxable
    base, and IVA amount are derived downstream from the registry, never
    emitted by the model.

    Args:
        classifications: Optional override for the classification choices;
            defaults to :func:`default_classification_choices`.

    Returns:
        A :class:`PromptSpec` carrying both the spending-category and the
        IVA-category allow-lists.
    """
    category_choices = tuple(CategoryChoice(value=value, hint=_category_hint(value)) for value in SpendingCategory)
    return PromptSpec(
        classifications=classifications or default_classification_choices(),
        categories=category_choices,
        iva_categories=default_iva_category_choices(),
    )


def _category_hint(value: SpendingCategory) -> str:
    """Return the best available hint string for a SpendingCategory.

    Resolves the display label and ``notes`` translation keys to Spanish at
    read time, and pairs them with the proportionality kind from
    :data:`cadrumo.domain.categories.resolve_category_profiles(2025)` -- gives the
    LLM the authoritative AEAT terminology AND the deductibility
    context (e.g. ``full_deductible``, ``usage_ratio_home_area``) that
    disambiguates home-office from premises rent or drives MIXED vs
    BUSINESS decisions. Falls back to the humanised enum value when a
    category has no registered profile.

    Resolution belongs here rather than in the profile registry, whose
    loader is cached: resolving there would bake one operator's locale
    into the shared profile and serve it to the next operator.
    """
    profile = resolve_category_profiles(2025).get(value)
    if profile is None:
        return value.value.replace("_", " ")
    # Pinned to Spanish regardless of operator locale: the classifier reasons
    # over Spanish AEAT invoices, so authoritative AEAT terminology must reach
    # the prompt even when the operator has selected en/ca/hu.
    spanish_label = _tr(profile.display_label, locale="es")
    rule = profile.proportionality
    notes = _tr(rule.notes, locale="es") if rule.notes else ""
    notes_preview = notes.strip().splitlines()[0][:120] if notes else ""
    segments = [spanish_label, f"[{rule.kind.value}]"]
    if notes_preview:
        segments.append(notes_preview)
    return " — ".join(segments)


def _render_choices(lines: Iterable[tuple[str, str]]) -> str:
    """Render ``(value, hint)`` pairs as aligned bullet rows."""
    rows = list(lines)
    if not rows:
        return ""
    width = max(len(value) for value, _hint in rows)
    return "\n".join(f"  {value:<{width}} — {hint}" for value, hint in rows)


def _evidence_section(evidence_text: str) -> list[str]:
    """Render the attached-evidence block (selection-only; never emit its numbers)."""
    return [
        "Attached evidence document for this transaction (read it carefully; it is "
        "authoritative for what was purchased). Use it ONLY to choose the "
        "classification, category, and iva_category. Do NOT copy or output any euro "
        "amount, rate, taxable base, or IVA figure from it -- those are computed "
        "elsewhere from the registry.",
        "--- begin evidence ---",
        evidence_text,
        "--- end evidence ---",
        "",
    ]


def _vision_evidence_section() -> list[str]:
    """Render the attached-image evidence instruction (selection-only; never emit numbers).

    Used when the evidence is a scanned or image invoice read on-host by a local
    vision model: the document is attached as an image rather than inlined as
    text, so the prompt points the model at the attached image instead of
    embedding extracted text.
    """
    return [
        "An invoice or receipt image is attached to this message. Read it carefully; "
        "it is authoritative for what was purchased. Use it ONLY to choose the "
        "classification, category, and iva_category. Do NOT copy or output any euro "
        "amount, rate, taxable base, or IVA figure from it -- those are computed "
        "elsewhere from the registry.",
        "",
    ]


def _evidence_block(evidence_text: str | None, evidence_image_present: bool) -> list[str]:
    """Select the evidence instruction: inlined text, attached image, or none."""
    if evidence_text:
        return _evidence_section(evidence_text)
    if evidence_image_present:
        return _vision_evidence_section()
    return []


def _render_prompt(
    spec: PromptSpec,
    transaction: Transaction,
    *,
    evidence_text: str | None = None,
    evidence_image_present: bool = False,
) -> str:
    """Build the full prompt string for one transaction against a spec.

    When ``evidence_text`` is given it is inlined for the model to read. When
    ``evidence_image_present`` is set (and no text), the prompt instead points the
    model at an attached invoice image (the on-host vision-read path).
    """
    raw = transaction.raw
    effective_date = raw.value_date or raw.booked_date
    classification_block = _render_choices((choice.value.value, choice.hint) for choice in spec.classifications)
    sections = [
        spec.header,
        "",
        "You have all the information you need below. Do NOT ask clarifying questions. "
        "Do NOT offer to help further. Pick the most likely classification from the "
        "closed list and answer in ONE line of JSON, immediately, nothing else.",
        "",
        "Transaction:",
        f"  Date: {effective_date.isoformat()}",
        f"  Amount: {raw.amount} {raw.currency}",
        f"  Counterparty: {raw.counterparty or '(unknown)'}",
        f"  Description: {raw.description}",
        "",
        *_evidence_block(evidence_text, evidence_image_present),
        "Classify it as exactly one of these BusinessClassification values:",
        classification_block,
    ]
    schema_fields = [
        '"classification": "<one value>"',
        '"confidence": <0.0-1.0>',
        '"reason": "<one sentence>"',
    ]
    if spec.categories:
        category_block = _render_choices((choice.value.value, choice.hint) for choice in spec.categories)
        sections.extend(
            [
                "",
                "When classification is BUSINESS or MIXED, also pick exactly one SpendingCategory:",
                category_block,
            ],
        )
        schema_fields.append('"category": "<one SpendingCategory or null>"')
    if spec.iva_categories:
        iva_block = _render_choices((choice.value.value, choice.hint) for choice in spec.iva_categories)
        sections.extend(
            [
                "",
                "Also pick exactly one iva_category — the IVA situation that fits this transaction. "
                "Pick the category only; do NOT compute or output any rate, base, or IVA amount.",
                iva_block,
            ],
        )
        schema_fields.append('"iva_category": "<one IvaCategory or null>"')
        schema_fields.append('"business_pct": <0.0-1.0 when MIXED, else null>')
    evidence_present = bool(evidence_text) or evidence_image_present
    if evidence_present:
        sections.extend(
            [
                "",
                "Also judge whether the attached invoice carries MULTIPLE distinct lines at "
                "different IVA rates or expense categories that should be split into separate "
                "entries (so each line's deductible IVA and base-rate expense file independently). "
                "Set multiple_components true only when two or more distinct rate/category lines are "
                "present; set it false for a single-line, single-rate invoice.",
            ],
        )
        schema_fields.append('"multiple_components": <true|false>')
    schema_line = "{" + ", ".join(schema_fields) + "}"
    example_confidence = "0.85"
    example_reason = "restaurante meal with a named client strongly suggests business meal"
    example = f'{{"classification": "BUSINESS", "confidence": {example_confidence}, "reason": "{example_reason}"'
    if spec.categories:
        example += ', "category": "manutencion_dietas_nacional"'
    if spec.iva_categories:
        example += ', "iva_category": "domestic_general", "business_pct": null'
    example += "}"
    sections.extend(
        [
            "",
            "Respond ONLY with a single JSON object. No prose before or after. No markdown fences.",
            f"Schema: {schema_line}",
            f"Example response format: {example}",
        ],
    )
    return "\n".join(sections)


# ── response parsing ──────────────────────────────────────────────

_JSON_OBJECT_RE = re.compile(r"\{[^{}]*\}")


def parse_response(
    stdout: str,
    *,
    spec: PromptSpec | None = None,
) -> LLMClassificationResponse:
    """Extract a valid JSON object from LLM stdout, validate, enforce spec.

    Iterates every JSON-object candidate in the output and returns the
    first one that validates against the schema AND passes the spec's
    allow-list. Guards against an LLM that echoes a prompt-injected
    JSON block before emitting its real answer: a malformed or
    disallowed first candidate no longer poisons the result.

    Args:
        stdout: Raw stdout captured from the LLM CLI.
        spec: Prompt spec the response should conform to. When provided,
            reject classifications or categories outside the allow-list.

    Returns:
        A validated :class:`LLMClassificationResponse`.

    Raises:
        LLMClassifierError: If no candidate JSON object exists, or if
            none of the candidates passes both schema validation and
            the spec's allow-list.
    """
    resolved_spec = spec or default_prompt_spec()
    allowed_classifications = resolved_spec.allowed_classifications()
    allowed_categories = resolved_spec.allowed_categories()
    allowed_iva_categories = resolved_spec.allowed_iva_categories()
    failures: list[str] = []
    any_candidate_seen = False

    for match in _JSON_OBJECT_RE.finditer(stdout):
        any_candidate_seen = True
        payload = match.group(0)
        try:
            response = LLMClassificationResponse.model_validate_json(payload)
        except ValueError as exc:
            failures.append(f"schema: {str(exc)[:160]} (payload {payload[:100]!r})")
            continue
        if response.classification not in allowed_classifications:
            failures.append(f"disallowed classification {response.classification.value!r} (payload {payload[:100]!r})")
            continue
        if response.category is not None:
            if not allowed_categories:
                failures.append(f"unexpected category {response.category.value!r} (payload {payload[:100]!r})")
                continue
            if response.category not in allowed_categories:
                failures.append(f"disallowed category {response.category.value!r} (payload {payload[:100]!r})")
                continue
        if response.iva_category is not None:
            if not allowed_iva_categories:
                failures.append(f"unexpected iva_category {response.iva_category.value!r} (payload {payload[:100]!r})")
                continue
            if response.iva_category not in allowed_iva_categories:
                failures.append(f"disallowed iva_category {response.iva_category.value!r} (payload {payload[:100]!r})")
                continue
        return response

    if not any_candidate_seen:
        raise LLMClassifierError(f"no JSON object in LLM output: {stdout[:400]!r}")
    raise LLMClassifierError(
        f"no JSON candidate matched schema + spec; tried {len(failures)}: " + "; ".join(failures[:3]),
    )


def build_split_prompt(
    transaction: Transaction,
    *,
    spec: PromptSpec | None = None,
    evidence_text: str | None = None,
    evidence_image_present: bool = False,
) -> str:
    """Build a prompt asking the model to propose an evidence-driven N-way split.

    The model reads the attached invoice and proposes per-child *proportions* plus
    selections; it must never emit a euro amount (the application derives the
    amounts from the parent gross and the tax substrate from the registry). The
    invoice is supplied as inlined text (``evidence_text``) or, on the on-host
    vision-read path, as an attached image (``evidence_image_present``).
    """
    resolved_spec = spec or default_prompt_spec()
    raw = transaction.raw
    effective_date = (raw.value_date or raw.booked_date).isoformat()
    sections = [
        "You are dividing one Spanish autonomo bank transaction into the lines of its attached invoice.",
        "",
        "Transaction:",
        f"  Date: {effective_date}",
        f"  Amount: {raw.amount} {raw.currency}",
        f"  Counterparty: {raw.counterparty or '(unknown)'}",
        f"  Description: {raw.description}",
        "",
        *_evidence_block(evidence_text, evidence_image_present),
        "Propose how to divide this transaction into children, one per distinct line or category on "
        "the invoice. If the invoice is a SINGLE line at a single IVA rate (no split warranted), "
        "return EXACTLY ONE child with proportion 1.0. If it carries two or more distinct lines or "
        "IVA rates, return one child per line. For each child give a proportion (a fraction of the "
        "total; all proportions MUST sum to 1.0), a spending category, an iva_category, and a short "
        "evidence_citation naming the line. Do NOT output any euro amount, rate, base, or IVA figure.",
    ]
    if resolved_spec.categories:
        category_block = _render_choices((choice.value.value, choice.hint) for choice in resolved_spec.categories)
        sections.extend(["", "Pick each child's spending category from:", category_block])
    if resolved_spec.iva_categories:
        iva_block = _render_choices((choice.value.value, choice.hint) for choice in resolved_spec.iva_categories)
        sections.extend(["", "Pick each child's iva_category from:", iva_block])
    sections.extend(
        [
            "",
            "Respond ONLY with a single JSON object. No prose before or after. No markdown fences.",
            'Schema: {"reason": "<one sentence>", "children": [{"proportion": <0..1>, '
            '"category": "<SpendingCategory or null>", "iva_category": "<IvaCategory or null>", '
            '"evidence_citation": "<short>"}, ...]}',
        ]
    )
    return "\n".join(sections)


def _extract_json_object(text: str) -> str | None:
    """Return the first balanced top-level JSON object substring, or ``None``.

    Unlike the flat :data:`_JSON_OBJECT_RE`, this walks brace depth (ignoring
    braces inside strings) so a nested object -- such as a split proposal whose
    ``children`` is an array of objects -- is captured whole.
    """
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def parse_split_response(stdout: str, *, spec: PromptSpec | None = None) -> LLMSplitResponse:
    """Extract and validate an N-way split proposal from LLM stdout.

    Finds the first balanced JSON object, validates it as
    :class:`LLMSplitResponse`, and rejects any child whose ``category`` or
    ``iva_category`` falls outside the spec's allow-list -- the same hallucination
    guard :func:`parse_response` applies to a flat classification.

    Args:
        stdout: Raw stdout captured from the LLM CLI.
        spec: Prompt spec whose allow-lists each child must satisfy.

    Returns:
        A validated :class:`LLMSplitResponse`.

    Raises:
        LLMClassifierError: When no JSON object is present, the schema is
            violated, or a child selection is outside the allow-list.
    """
    resolved_spec = spec or default_prompt_spec()
    allowed_categories = resolved_spec.allowed_categories()
    allowed_iva_categories = resolved_spec.allowed_iva_categories()
    payload = _extract_json_object(stdout)
    if payload is None:
        raise LLMClassifierError(f"no JSON object in LLM split output: {stdout[:400]!r}")
    try:
        response = LLMSplitResponse.model_validate_json(payload)
    except ValueError as exc:
        raise LLMClassifierError(f"split response failed schema validation: {str(exc)[:200]}") from exc
    for child in response.children:
        if child.category is not None and (not allowed_categories or child.category not in allowed_categories):
            raise LLMClassifierError(f"disallowed split child category {child.category.value!r}")
        if child.iva_category is not None and (
            not allowed_iva_categories or child.iva_category not in allowed_iva_categories
        ):
            raise LLMClassifierError(f"disallowed split child iva_category {child.iva_category.value!r}")
    return response


__all__ = [
    "MINIMUM_CLASSIFICATION_TIER",
    "PIPELINE_ONLY_CLASSIFICATIONS",
    "CategoryChoice",
    "ClassificationChoice",
    "IvaCategoryChoice",
    "LLMClassificationResponse",
    "LLMClassifier",
    "LLMClassifierError",
    "ModelProfile",
    "ModelTier",
    "PromptSpec",
    "default_classification_choices",
    "default_iva_category_choices",
    "default_prompt_spec",
    "parse_response",
    "prompt_spec_with_every_spending_category",
    "prompt_spec_with_saturation_fields",
]
