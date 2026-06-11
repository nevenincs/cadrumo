"""LLM-backed transaction classifiers with a parametric prompt builder.

Defines the :class:`LLMClassifier` protocol plus subprocess-based
reference implementations for the three local LLM CLIs
(:func:`build_claude_classifier`, :func:`build_antigravity_classifier`,
:func:`build_codex_classifier`). The prompt is built
PROGRAMMATICALLY from the available enum values so the LLM prompt
stays in sync with :class:`aeat.domain.transactions.BusinessClassification`:
adding a new value automatically requires a developer to decide
whether it belongs in the default LLM choice set.

The prompt spec is parametrized:

- ``classifications``: which :class:`aeat.domain.transactions.BusinessClassification`
  values the LLM may pick. Defaults to the four *decision* states
  (``BUSINESS`` / ``PERSONAL`` / ``MIXED`` / ``PROCESSED_UNCLASSIFIED``).
  Pipeline-state values (``NOT_YET_PROCESSED``, ``SKIPPED_BY_RULE``,
  ``FAILED_VALIDATION``) are excluded because they are not LLM
  decisions -- they are internal pipeline bookkeeping.
- ``categories``: optional :class:`aeat.domain.categories.SpendingCategory`
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
import shutil
import subprocess
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel, Field, field_validator

from ...core._models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.i18n import Translatable as tr
from ...core.logging import get_logger
from ..categories import SpendingCategory, resolve_category_profiles
from ..iva import IvaCategory
from ._enums import BusinessClassification
from ._errors import LLMClassifierError, TransactionValidationError
from ._model_tier import MINIMUM_CLASSIFICATION_TIER, ModelProfile, ModelTier, resolve_profile
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
    """An evidence-driven N-way split proposal: children whose proportions sum to one."""

    model_config = _STRICT_FROZEN

    children: tuple[LLMSplitChild, ...]
    reason: str = Field(min_length=1, max_length=_REASON_MAX_LENGTH)

    @field_validator("children")
    @classmethod
    def _check_children(cls, value: tuple[LLMSplitChild, ...]) -> tuple[LLMSplitChild, ...]:
        """Require at least two children whose proportions sum to ~1.0."""
        if len(value) < 2:
            raise TransactionValidationError("a split must propose at least two children")
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


@dataclass(frozen=True)
class ClassificationChoice:
    """One allowed :class:`BusinessClassification` paired with an LLM-facing hint."""

    value: BusinessClassification
    hint: str


@dataclass(frozen=True)
class CategoryChoice:
    """One allowed :class:`SpendingCategory` paired with an LLM-facing hint."""

    value: SpendingCategory
    hint: str


@dataclass(frozen=True)
class IvaCategoryChoice:
    """One allowed :class:`aeat.domain.iva.IvaCategory` paired with an LLM-facing hint."""

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
        """Return the set of :class:`aeat.domain.iva.IvaCategory` values the LLM may emit (empty = none).

        Returns:
            Frozenset of :class:`aeat.domain.iva.IvaCategory` values the LLM may
            select from; empty when the spec does not ask for an IVA category.
        """
        return frozenset(choice.value for choice in self.iva_categories)

    def render(self, transaction: Transaction, *, evidence_text: str | None = None) -> str:
        """Render the prompt for ``transaction`` against this spec.

        Args:
            transaction: The transaction to classify.
            evidence_text: Optional on-host-extracted text of an attached evidence
                document (e.g. a purchase invoice). When present it is injected into
                the prompt for the model to read; the model uses it only to select
                the classification/category/iva_category and must never copy a euro
                figure from it (the regulated numbers stay registry-derived).
        """
        return _render_prompt(self, transaction, evidence_text=evidence_text)


def default_prompt_spec() -> PromptSpec:
    """Return the default :class:`PromptSpec`: classification-only, four decision states."""
    return PromptSpec()


def prompt_spec_with_every_spending_category(
    *,
    classifications: tuple[ClassificationChoice, ...] | None = None,
) -> PromptSpec:
    """Return a prompt spec that also asks the LLM to suggest a SpendingCategory.

    Pulls authoritative Spanish display labels from
    :data:`aeat.domain.categories.resolve_category_profiles(2025)` rather than
    inventing ad-hoc hints from the enum value -- the LLM picks
    categories far more accurately against the real AEAT terminology
    than against mangled snake_case. Categories with no registered
    profile (none today; every
    :class:`aeat.domain.categories.SpendingCategory` member is covered)
    fall back to the humanised enum value.

    Args:
        classifications: Optional override for the classification
            choices; defaults to :func:`default_classification_choices`.

    Returns:
        A :class:`PromptSpec` whose ``categories`` tuple covers every
        registered :class:`aeat.domain.categories.SpendingCategory`.
    """
    category_choices = tuple(CategoryChoice(value=value, hint=_category_hint(value)) for value in SpendingCategory)
    return PromptSpec(
        classifications=classifications or default_classification_choices(),
        categories=category_choices,
    )


# Concise operator-/LLM-facing descriptions for each closed Spanish IVA
# situation. These hint the model's SELECTION; they do not ground a number —
# the rate is looked up from the registry and the base/amount derived
# downstream. The IVA catalogue's own ``label`` fields are i18n keys that are
# not carried in the locale catalogues, so they cannot serve as hints; these
# curated one-liners are the authoritative prompt descriptions instead.
_IVA_CATEGORY_HINTS: dict[IvaCategory, str] = {
    IvaCategory.DOMESTIC_GENERAL_21: "domestic supply at the general 21% rate",
    IvaCategory.DOMESTIC_REDUCED_10: "reduced 10% rate (hospitality, transport, some foods)",
    IvaCategory.DOMESTIC_SUPER_REDUCED_4: "super-reduced 4% rate (basic foods, books, medicines)",
    IvaCategory.DOMESTIC_ZERO: "domestic supply at a 0% rate",
    IvaCategory.DOMESTIC_EXEMPT: "domestic supply exempt from IVA (education, health, finance — Art. 20)",
    IvaCategory.DOMESTIC_NOT_SUBJECT: "operation not subject to Spanish IVA",
    IvaCategory.DOMESTIC_REVERSE_CHARGE: "domestic reverse charge — the recipient self-assesses IVA (Art. 84)",
    IvaCategory.INTRA_COMMUNITY_SUPPLY: "exempt intra-community supply of goods to an EU business (Art. 25)",
    IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE: "reverse-charge EU goods acquisition",
    IvaCategory.INTRA_COMMUNITY_TRIANGULATION: "intra-community triangular operation",
    IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED: "export of goods outside the EU, zero-rated (Art. 21)",
    IvaCategory.IMPORT_THIRD_COUNTRY: "import of goods from outside the EU",
    IvaCategory.RECARGO_EQUIVALENCIA: "purchase subject to the recargo de equivalencia surcharge",
    IvaCategory.REGIMEN_SIMPLIFICADO: "régimen simplificado (modules), not a general-regime invoice",
    IvaCategory.OPERACION_NO_SUJETA: "operation outside the scope of Spanish IVA",
    IvaCategory.ERRONEOUS_INVOICE: "erroneous invoice flagged for correction",
    IvaCategory.UNKNOWN: "IVA situation not yet determined",
}


def default_iva_category_choices() -> tuple[IvaCategoryChoice, ...]:
    """Return the grounded IVA-category choices for the saturation prompt.

    The allow-list is the closed :class:`aeat.domain.iva.IvaCategory` enum (the
    registry :class:`aeat.domain.iva.IvaCatalogue` is validated to carry a
    regulation for every member, so the enum and the catalogue set are
    identical). Each choice is hinted with a concise description from
    :data:`_IVA_CATEGORY_HINTS`. The model SELECTS a category only; every
    regulated euro figure is derived downstream from the registry rate, never
    emitted by the model (``2026-06-04-llm-ledger-classification-adr``).

    Returns:
        One :class:`IvaCategoryChoice` per :class:`aeat.domain.iva.IvaCategory`,
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
    emitted by the model (``2026-06-04-llm-ledger-classification-adr``).

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

    Pulls the Spanish display label plus the proportionality kind and
    (first 80 chars of) ``notes`` from
    :data:`aeat.domain.categories.resolve_category_profiles(2025)` -- gives the
    LLM the authoritative AEAT terminology AND the deductibility
    context (e.g. ``full_deductible``, ``usage_ratio_home_area``) that
    disambiguates home-office from premises rent or drives MIXED vs
    BUSINESS decisions. Falls back to the humanised enum value when a
    category has no registered profile.
    """
    profile = resolve_category_profiles(2025).get(value)
    if profile is None:
        return value.value.replace("_", " ")
    spanish_label = profile.display_label or value.value.replace("_", " ")
    rule = profile.proportionality
    notes_preview = rule.notes.strip().splitlines()[0][:120] if rule.notes else ""
    segments = [spanish_label, f"[{rule.kind.value}]"]
    if notes_preview:
        segments.append(tr(notes_preview))
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


def _render_prompt(spec: PromptSpec, transaction: Transaction, *, evidence_text: str | None = None) -> str:
    """Build the full prompt string for one transaction against a spec."""
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
        *(_evidence_section(evidence_text) if evidence_text else []),
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
    schema_line = "{" + ", ".join(schema_fields) + "}"
    example_confidence = "0.85"
    example_reason = "restaurante meal with a named client strongly suggests business meal"
    example = f'{{"classification": "BUSINESS", "confidence": {example_confidence}, "reason": "{example_reason}"'
    if spec.categories:
        example += ', "category": "manutencion_dietas_nacional"'
    if spec.iva_categories:
        example += ', "iva_category": "domestic_general_21", "business_pct": null'
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
) -> str:
    """Build a prompt asking the model to propose an evidence-driven N-way split.

    The model reads the attached invoice and proposes per-child *proportions* plus
    selections; it must never emit a euro amount (the application derives the
    amounts from the parent gross and the tax substrate from the registry).
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
        *(_evidence_section(evidence_text) if evidence_text else []),
        "Propose how to divide this transaction into TWO OR MORE children, one per distinct line or "
        "category on the invoice. For each child give a proportion (a fraction of the total; all "
        "proportions MUST sum to 1.0), a spending category, an iva_category, and a short "
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


# ── subprocess-based classifier ───────────────────────────────────


@dataclass(frozen=True)
class SubprocessLLMClassifier:
    """LLM classifier that shells out to a local CLI binary.

    Pipes the prompt via stdin by default (more reliable than a
    positional argument for long multi-line prompts, especially on
    Windows where CreateProcess quoting can corrupt arguments).

    Reads output from stdout. Transaction prompts and classifier
    responses are sensitive financial data, so this adapter deliberately
    avoids file-backed subprocess handoff.

    Set ``prompt_via_argument=True`` for CLIs that reject stdin and
    require the prompt as the final positional argument.
    """

    name: str
    command: tuple[str, ...]
    model: str | None = None
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS
    spec: PromptSpec = field(default_factory=default_prompt_spec)
    prompt_via_argument: bool = False

    @property
    def decided_by(self) -> str:
        """Return the ``classified_by`` identifier including the model when set."""
        if self.model:
            return f"llm:{self.name}:{self.model}"
        return f"llm:{self.name}"

    def classify(self, transaction: Transaction, *, evidence_text: str | None = None) -> LLMClassificationResponse:
        """Shell out to the LLM CLI, parse, validate, return.

        Args:
            transaction: The transaction to classify.
            evidence_text: Optional on-host-extracted attached-evidence text injected
                into the prompt (sent via stdin, never a file).

        Returns:
            A :class:`LLMClassificationResponse` with the parsed classification result.
        """
        stdout = self._run_cli(
            self.spec.render(transaction, evidence_text=evidence_text),
            transaction_id=transaction.transaction_id,
        )
        response = parse_response(stdout, spec=self.spec)
        _logger.debug(
            "llm classify: %s returned classification=%s confidence=%s for transaction %s",
            self.name,
            response.classification.value,
            response.confidence,
            transaction.transaction_id,
        )
        return response

    def propose_split(self, transaction: Transaction, *, evidence_text: str | None = None) -> LLMSplitResponse:
        """Shell out with a split-proposal prompt, parse and validate the split.

        Args:
            transaction: The transaction to split.
            evidence_text: Optional on-host-extracted attached-evidence text injected
                into the prompt (sent via stdin, never a file).

        Returns:
            A validated :class:`LLMSplitResponse`.
        """
        stdout = self._run_cli(
            build_split_prompt(transaction, spec=self.spec, evidence_text=evidence_text),
            transaction_id=transaction.transaction_id,
        )
        return parse_split_response(stdout, spec=self.spec)

    def _run_cli(self, prompt: str, *, transaction_id: str) -> str:
        """Shell out to the CLI with ``prompt`` via stdin (never a file) and return stdout."""
        resolved_binary = shutil.which(self.command[0])
        if resolved_binary is None:
            _logger.warning("llm classifier %s not found on PATH: %s", self.name, self.command[0])
            raise LLMClassifierError(f"{self.name} CLI not found on PATH: {self.command[0]}")

        argv: list[str] = [resolved_binary, *self.command[1:]]
        stdin_input: str | None = None
        if self.prompt_via_argument:
            argv.append(prompt)
        else:
            stdin_input = prompt

        _logger.debug("llm classify: spawning %s argv=%s transaction_id=%s", self.name, argv[0], transaction_id)
        try:
            completed = subprocess.run(
                argv,
                input=stdin_input,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            _logger.warning(
                "llm classify: %s timed out after %ss for transaction %s",
                self.name,
                self.timeout_seconds,
                transaction_id,
                exc_info=True,
            )
            raise LLMClassifierError(f"{self.name} CLI timed out after {self.timeout_seconds}s") from exc
        except OSError as exc:
            # Spawn-time failures (PermissionError, ENOEXEC, ENOMEM, Windows
            # CreateProcess errors). Translate so the --all CLI loop can
            # skip this one transaction and continue on the next.
            _logger.error("llm classify: %s spawn failed", self.name, exc_info=True)
            raise LLMClassifierError(f"{self.name} CLI spawn failed: {exc}") from exc
        if completed.returncode != 0:
            _logger.warning(
                "llm classify: %s exited with returncode=%d for transaction %s",
                self.name,
                completed.returncode,
                transaction_id,
            )
            raise LLMClassifierError(
                f"{self.name} CLI exited with {completed.returncode}: {(completed.stderr or completed.stdout)[:400]!r}",
            )
        return completed.stdout


# ── builders + registry ───────────────────────────────────────────


def build_claude_classifier(
    *,
    alias: str | None = None,
    model: str | None = None,
    spec: PromptSpec | None = None,
    minimum_tier: ModelTier = MINIMUM_CLASSIFICATION_TIER,
) -> SubprocessLLMClassifier:
    """Build a classifier that shells out to ``claude --bare -p``.

    Args:
        alias: Capability-tier alias (``claude-sonnet`` / ``claude-opus``
            / ``claude-haiku``). Resolves to the current model ID via
            :func:`aeat.domain.transactions._model_tier.resolve_profile`
            and enforces ``minimum_tier``.
        model: Explicit provider-specific model override. When set,
            takes precedence over ``alias`` AND skips the tier check;
            reserved for advanced operators pinning a specific model.
        spec: Prompt spec override.
        minimum_tier: Refuses aliases below this tier (default:
            :data:`MINIMUM_CLASSIFICATION_TIER`).

    Returns:
        A :class:`SubprocessLLMClassifier` configured for the
        ``claude`` CLI.
    """
    resolved_model = _resolve_model_id(provider="claude", alias=alias, explicit_model=model, minimum_tier=minimum_tier)
    command: tuple[str, ...] = ("claude", "--bare", "-p")
    if resolved_model:
        command = ("claude", "--bare", "-p", "--model", resolved_model)
    return SubprocessLLMClassifier(
        name="claude",
        command=command,
        model=resolved_model or None,
        spec=spec or default_prompt_spec(),
    )


def build_antigravity_classifier(
    *,
    alias: str | None = None,
    model: str | None = None,
    spec: PromptSpec | None = None,
    minimum_tier: ModelTier = MINIMUM_CLASSIFICATION_TIER,
) -> SubprocessLLMClassifier:
    """Build a classifier that shells out to ``agy --prompt <prompt>``.

    Antigravity (Google's agentic CLI ``agy``) is the supported successor to
    the retired standalone ``gemini`` CLI. Its ``--print`` / ``-p`` /
    ``--prompt`` mode runs a single prompt non-interactively; the prompt is the
    VALUE of that flag, so it is passed as the final positional argument
    (``prompt_via_argument=True``). Unlike the old ``gemini`` CLI (a Node
    wrapper whose command line overflowed a ~8 KB limit on the larger
    saturation prompt), ``agy`` is a native binary invoked through the
    subprocess argument list, so it carries the full platform command-line
    budget. ``--model`` selects a model when one is pinned; otherwise ``agy``
    uses its own current default. Its stdout may carry start-up noise; the JSON
    iterator in :func:`parse_response` tolerates it.

    Args:
        alias: Capability-tier alias (``antigravity-default``). Enforces
            ``minimum_tier``.
        model: Explicit provider-specific model override.
        spec: Prompt spec override.
        minimum_tier: Refuses aliases below this tier.

    Returns:
        A :class:`SubprocessLLMClassifier` configured for the ``agy`` CLI with
        ``prompt_via_argument=True``.
    """
    resolved_model = _resolve_model_id(
        provider="antigravity", alias=alias, explicit_model=model, minimum_tier=minimum_tier,
    )
    command = ("agy", "--prompt") if not resolved_model else ("agy", "--model", resolved_model, "--prompt")
    return SubprocessLLMClassifier(
        name="antigravity",
        command=command,
        model=resolved_model or None,
        spec=spec or default_prompt_spec(),
        prompt_via_argument=True,
    )


def build_codex_classifier(
    *,
    alias: str | None = None,
    model: str | None = None,
    spec: PromptSpec | None = None,
    minimum_tier: ModelTier = MINIMUM_CLASSIFICATION_TIER,
) -> SubprocessLLMClassifier:
    """Build a classifier that shells out to ``codex exec``.

    Uses ``--ephemeral`` + ``--skip-git-repo-check`` so the invocation
    does not require a git repo and does not persist sessions. The
    The subprocess adapter parses JSON candidates from stdout so no
    transaction data is written to a temporary file.

    Args:
        alias: Capability-tier alias (``codex-default`` / ``codex-o3``).
            Enforces ``minimum_tier``.
        model: Explicit provider-specific model override.
        spec: Prompt spec override.
        minimum_tier: Refuses aliases below this tier.

    Returns:
        A :class:`SubprocessLLMClassifier` configured for the
        ``codex`` CLI.
    """
    resolved_model = _resolve_model_id(provider="codex", alias=alias, explicit_model=model, minimum_tier=minimum_tier)
    command: tuple[str, ...] = ("codex", "exec", "--ephemeral", "--skip-git-repo-check")
    if resolved_model:
        command = (*command, "-m", resolved_model)
    return SubprocessLLMClassifier(
        name="codex",
        command=command,
        model=resolved_model or None,
        spec=spec or default_prompt_spec(),
    )


def _resolve_model_id(
    *,
    provider: str,
    alias: str | None,
    explicit_model: str | None,
    minimum_tier: ModelTier,
) -> str:
    """Resolve an alias or explicit model override to a provider-specific model ID.

    Precedence:
    1. ``explicit_model`` wins (advanced operator pinning a raw ID);
       no tier check.
    2. Otherwise ``alias`` resolves via the tier catalogue with
       minimum-tier enforcement.
    3. When both are None the catalogue's default for ``provider``
       (the lowest-tier profile at or above ``minimum_tier``) wins.
    """
    if explicit_model is not None:
        return explicit_model
    profile: ModelProfile = resolve_profile(provider, alias=alias, minimum_tier=minimum_tier)
    return profile.model_id


_BUILDERS: dict[str, Callable[..., LLMClassifier]] = {
    "claude": build_claude_classifier,
    "antigravity": build_antigravity_classifier,
    "codex": build_codex_classifier,
}


def resolve_classifier(
    provider: str,
    *,
    alias: str | None = None,
    model: str | None = None,
    spec: PromptSpec | None = None,
    minimum_tier: ModelTier = MINIMUM_CLASSIFICATION_TIER,
) -> LLMClassifier:
    """Return a classifier for the given provider name.

    Args:
        provider: One of ``"claude"``, ``"antigravity"``, ``"codex"``, or a
            name registered via :func:`register_classifier`.
        alias: Optional capability-tier alias (see
            :class:`aeat.domain.transactions._model_tier.ModelProfile`).
            Resolves to a current model ID via the tier catalogue.
        model: Optional raw model-ID override. Takes precedence over
            alias and skips the tier check. Reserved for advanced
            operators pinning a specific provider model.
        spec: Optional prompt spec override.
        minimum_tier: Refuses aliases below this tier (default
            :data:`MINIMUM_CLASSIFICATION_TIER`).

    Returns:
        A concrete implementation of :class:`LLMClassifier`.

    Raises:
        LLMClassifierError: If ``provider`` is not a registered builder,
            or if tier resolution fails.
    """
    try:
        builder = _BUILDERS[provider.lower()]
    except KeyError as exc:
        valid = ", ".join(sorted(_BUILDERS))
        raise LLMClassifierError(f"unknown LLM provider: {provider!r}; valid: {valid}") from exc
    try:
        return builder(alias=alias, model=model, spec=spec, minimum_tier=minimum_tier)
    except ValueError as exc:
        raise LLMClassifierError(str(exc)) from exc
    except TypeError:
        # Test-only builders registered via register_classifier may not take
        # the alias/minimum_tier kwargs. Fall back to the simple form so the
        # dependency-injected concrete classifiers keep working.
        _logger.debug(
            "resolve_classifier: builder for provider %r does not accept alias/minimum_tier kwargs; "
            "falling back to simple form",
            provider,
        )
        return builder(model=model, spec=spec)


def resolve_split_proposer(provider: str, *, spec: PromptSpec | None = None) -> LLMSplitProposer:
    """Resolve the production split proposer for ``provider``.

    Resolves the provider's classifier (via :func:`resolve_classifier`) and
    narrows it to an :class:`LLMSplitProposer`. The subprocess classifiers are
    the only production proposers; a registered classifier that does not also
    propose splits is refused instructively.

    Args:
        provider: One of ``"claude"``, ``"antigravity"``, ``"codex"``.
        spec: Optional prompt spec override (the category + IVA-category
            saturation spec is the natural choice so split children carry the
            same allow-list-guarded selections).

    Returns:
        An :class:`LLMSplitProposer` for ``provider``.

    Raises:
        LLMClassifierError: If ``provider`` resolves to a classifier that does
            not support evidence-driven splitting.
    """
    classifier = resolve_classifier(provider, spec=spec)
    if not isinstance(classifier, SubprocessLLMClassifier):
        raise LLMClassifierError(f"provider {provider!r} does not support evidence-driven splitting")
    return classifier


def register_classifier(name: str, builder: Callable[..., LLMClassifier]) -> None:
    """Register a classifier builder under ``name``.

    Intended for tests that want to inject a concrete in-process
    classifier (no mocks) and for third-party extensions that want to
    add a new provider without monkey-patching the module.
    """
    _BUILDERS[name.lower()] = builder


def unregister_classifier(name: str) -> None:
    """Remove a builder previously added via :func:`register_classifier`."""
    _BUILDERS.pop(name.lower(), None)


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
    "SubprocessLLMClassifier",
    "build_antigravity_classifier",
    "build_claude_classifier",
    "build_codex_classifier",
    "default_classification_choices",
    "default_iva_category_choices",
    "default_prompt_spec",
    "parse_response",
    "prompt_spec_with_every_spending_category",
    "prompt_spec_with_saturation_fields",
    "register_classifier",
    "resolve_classifier",
    "resolve_split_proposer",
    "unregister_classifier",
]
