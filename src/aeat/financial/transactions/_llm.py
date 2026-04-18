"""LLM-backed transaction classifiers with parametric prompt builder (#236).

Defines the :class:`LLMClassifier` protocol plus subprocess-based
reference implementations for the three local LLM CLIs (claude,
gemini, codex). The prompt is built PROGRAMMATICALLY from the
available enum values so the LLM prompt stays in sync with the
Python enum — adding a new :class:`BusinessClassification` value
automatically requires a developer to decide whether it belongs in
the default LLM choice set (via the
``test_default_spec_accounts_for_every_classification_member`` guard
in ``test_llm.py``).

The prompt spec is parametrized:

- ``classifications``: which :class:`BusinessClassification` values
  the LLM may pick. Defaults to the four *decision* states
  (``BUSINESS`` / ``PERSONAL`` / ``MIXED`` / ``PROCESSED_UNCLASSIFIED``).
  Pipeline-state values (``NOT_YET_PROCESSED``, ``SKIPPED_BY_RULE``,
  ``FAILED_VALIDATION``) are excluded because they are not LLM
  decisions — they are internal pipeline bookkeeping.
- ``categories``: optional :class:`SpendingCategory` values the LLM
  may additionally attach. Empty by default (classification-only).
  When populated, the response includes a ``category`` field.

Every decision the LLM emits is validated against the spec's
allow-list: a response that picks a value outside the allowed set
raises :class:`LLMClassifierError`, so a hallucinating model cannot
corrupt the catalogue.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..categories import SpendingCategory
from ._enums import BusinessClassification
from ._models import Transaction

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
_CONFIDENCE_MIN = Decimal("0")
_CONFIDENCE_MAX = Decimal("1")
_DEFAULT_TIMEOUT_SECONDS = 120.0
_REASON_MAX_LENGTH = 2048


class LLMClassifierError(Exception):
    """Raised when an LLM classification attempt fails."""


# ── response model ────────────────────────────────────────────────


class LLMClassificationResponse(BaseModel):
    """One LLM-emitted classification result for a transaction."""

    model_config = _STRICT_FROZEN

    classification: BusinessClassification
    confidence: Decimal
    reason: str = Field(min_length=1, max_length=_REASON_MAX_LENGTH)
    category: SpendingCategory | None = None

    @field_validator("confidence")
    @classmethod
    def _check_confidence_range(cls, value: Decimal) -> Decimal:
        """Restrict confidence to the inclusive 0..1 range."""
        if not _CONFIDENCE_MIN <= value <= _CONFIDENCE_MAX:
            raise ValueError("confidence must be within the inclusive 0..1 range")
        return value

    @field_validator("reason")
    @classmethod
    def _strip_reason(cls, value: str) -> str:
        """Trim whitespace and reject empty reasons."""
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("reason must not be empty")
        return trimmed


# ── protocol ──────────────────────────────────────────────────────


class LLMClassifier(Protocol):
    """Classify one transaction with an LLM-generated decision."""

    @property
    def decided_by(self) -> str:
        """Return the ``classified_by`` identifier this classifier emits."""

    def classify(self, transaction: Transaction) -> LLMClassificationResponse:
        """Return one classification decision for ``transaction``."""


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
    }
)


def default_classification_choices() -> tuple[ClassificationChoice, ...]:
    """Return the default allowed-classifications tuple used by the prompt."""
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
    header: str = "You are classifying a Spanish autónomo's bank transaction for tax purposes."

    def allowed_classifications(self) -> frozenset[BusinessClassification]:
        """Return the set of classification values the LLM is allowed to emit."""
        return frozenset(choice.value for choice in self.classifications)

    def allowed_categories(self) -> frozenset[SpendingCategory]:
        """Return the set of category values the LLM is allowed to emit (empty = none)."""
        return frozenset(choice.value for choice in self.categories)

    def render(self, transaction: Transaction) -> str:
        """Render the prompt for ``transaction`` against this spec."""
        return _render_prompt(self, transaction)


def default_prompt_spec() -> PromptSpec:
    """Return the default prompt spec: classification-only, four decision states."""
    return PromptSpec()


def prompt_spec_with_every_spending_category(
    *,
    classifications: tuple[ClassificationChoice, ...] | None = None,
) -> PromptSpec:
    """Return a prompt spec that also asks the LLM to suggest a SpendingCategory.

    Attaches every member of :class:`SpendingCategory` as an allowed
    category. Callers that want a smaller subset should build their
    own :class:`PromptSpec` instance.
    """
    category_choices = tuple(
        CategoryChoice(value=value, hint=value.value.replace("_", " ")) for value in SpendingCategory
    )
    return PromptSpec(
        classifications=classifications or default_classification_choices(),
        categories=category_choices,
    )


def _render_choices(lines: Iterable[tuple[str, str]]) -> str:
    """Render ``(value, hint)`` pairs as aligned bullet rows."""
    rows = list(lines)
    if not rows:
        return ""
    width = max(len(value) for value, _hint in rows)
    return "\n".join(f"  {value:<{width}} — {hint}" for value, hint in rows)


def _render_prompt(spec: PromptSpec, transaction: Transaction) -> str:
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
            ]
        )
        schema_fields.append('"category": "<one SpendingCategory or null>"')
    schema_line = "{" + ", ".join(schema_fields) + "}"
    example_confidence = "0.85"
    example_reason = "restaurante meal with a named client strongly suggests business meal"
    example = f'{{"classification": "BUSINESS", "confidence": {example_confidence}, "reason": "{example_reason}"'
    if spec.categories:
        example += ', "category": "manutencion_dietas_nacional"'
    example += "}"
    sections.extend(
        [
            "",
            "Respond ONLY with a single JSON object. No prose before or after. No markdown fences.",
            f"Schema: {schema_line}",
            f"Example response format: {example}",
        ]
    )
    return "\n".join(sections)


# Kept for backward-compatible imports from earlier drafts/tests.
def build_prompt(transaction: Transaction, *, spec: PromptSpec | None = None) -> str:
    """Render the classification prompt for one transaction against ``spec``."""
    return (spec or default_prompt_spec()).render(transaction)


# ── response parsing ──────────────────────────────────────────────


_JSON_OBJECT_RE = re.compile(r"\{[^{}]*\}")


def parse_response(
    stdout: str,
    *,
    spec: PromptSpec | None = None,
) -> LLMClassificationResponse:
    """Extract the first JSON object from LLM stdout, validate, enforce spec.

    Args:
        stdout: Raw stdout captured from the LLM CLI.
        spec: Prompt spec the response should conform to. When provided,
            reject classifications or categories outside the allow-list.

    Returns:
        A validated :class:`LLMClassificationResponse`.

    Raises:
        LLMClassifierError: If no JSON object is found, if the payload
            fails schema validation, or if the classification/category
            escape the spec's allow-list.
    """
    match = _JSON_OBJECT_RE.search(stdout)
    if not match:
        raise LLMClassifierError(f"no JSON object in LLM output: {stdout[:400]!r}")
    payload = match.group(0)
    try:
        response = LLMClassificationResponse.model_validate_json(payload)
    except ValueError as exc:
        raise LLMClassifierError(f"invalid LLM response: {exc}; payload was {payload!r}") from exc

    resolved_spec = spec or default_prompt_spec()
    allowed_classifications = resolved_spec.allowed_classifications()
    if response.classification not in allowed_classifications:
        raise LLMClassifierError(
            f"LLM picked a disallowed classification {response.classification.value!r}; "
            f"spec allows: {sorted(v.value for v in allowed_classifications)}"
        )
    if response.category is not None:
        allowed_categories = resolved_spec.allowed_categories()
        if not allowed_categories:
            raise LLMClassifierError("LLM returned a category but the prompt spec forbade one")
        if response.category not in allowed_categories:
            raise LLMClassifierError(f"LLM picked a disallowed category {response.category.value!r}")
    return response


# ── subprocess-based classifier ───────────────────────────────────


@dataclass(frozen=True)
class SubprocessLLMClassifier:
    """LLM classifier that shells out to a local CLI binary.

    Pipes the prompt via stdin by default (more reliable than a
    positional argument for long multi-line prompts, especially on
    Windows where CreateProcess quoting can corrupt arguments).

    Reads output from stdout by default. Some CLIs (notably ``codex``)
    emit event-stream noise on stdout but write the final agent
    message to a separate file; set ``output_from_file_flag`` to the
    CLI's flag name for that file (e.g. ``"--output-last-message"``)
    and the classifier will append a tempfile path, read it back, and
    parse that instead of stdout.

    Set ``prompt_via_argument=True`` for CLIs that reject stdin and
    require the prompt as the final positional argument.
    """

    name: str
    command: tuple[str, ...]
    model: str | None = None
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS
    spec: PromptSpec = field(default_factory=default_prompt_spec)
    output_from_file_flag: str | None = None
    prompt_via_argument: bool = False

    @property
    def decided_by(self) -> str:
        """Return the ``classified_by`` identifier including the model when set."""
        if self.model:
            return f"llm:{self.name}:{self.model}"
        return f"llm:{self.name}"

    def classify(self, transaction: Transaction) -> LLMClassificationResponse:
        """Shell out to the LLM CLI, parse, validate, return."""
        prompt = self.spec.render(transaction)
        resolved_binary = shutil.which(self.command[0])
        if resolved_binary is None:
            raise LLMClassifierError(f"{self.name} CLI not found on PATH: {self.command[0]}")

        output_file: Path | None = None
        extra_flags: tuple[str, ...] = ()
        if self.output_from_file_flag is not None:
            # Create an empty tempfile and close it immediately; the LLM CLI
            # will write into it, we read it back after the subprocess exits.
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                suffix=f".{self.name}.out",
                delete=False,
            ) as handle:
                output_file = Path(handle.name)
            extra_flags = (self.output_from_file_flag, str(output_file))

        argv: list[str] = [resolved_binary, *self.command[1:], *extra_flags]
        stdin_input: str | None = None
        if self.prompt_via_argument:
            argv.append(prompt)
        else:
            stdin_input = prompt

        try:
            try:
                completed = subprocess.run(  # noqa: S603 — explicit command list, trusted binary.
                    argv,
                    input=stdin_input,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=self.timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise LLMClassifierError(f"{self.name} CLI timed out after {self.timeout_seconds}s") from exc
            if completed.returncode != 0:
                raise LLMClassifierError(
                    f"{self.name} CLI exited with {completed.returncode}: "
                    f"{(completed.stderr or completed.stdout)[:400]!r}"
                )
            output = output_file.read_text(encoding="utf-8") if output_file else completed.stdout
            return parse_response(output, spec=self.spec)
        finally:
            if output_file is not None:
                output_file.unlink(missing_ok=True)


# ── builders + registry ───────────────────────────────────────────


def build_claude_classifier(
    *,
    model: str | None = None,
    spec: PromptSpec | None = None,
) -> SubprocessLLMClassifier:
    """Build a classifier that shells out to ``claude -p``."""
    return SubprocessLLMClassifier(
        name="claude",
        command=("claude", "--bare", "-p"),
        model=model,
        spec=spec or default_prompt_spec(),
    )


def build_gemini_classifier(
    *,
    model: str | None = None,
    spec: PromptSpec | None = None,
) -> SubprocessLLMClassifier:
    """Build a classifier that shells out to ``gemini -p``."""
    command = ("gemini", "-p") if model is None else ("gemini", "-m", model, "-p")
    return SubprocessLLMClassifier(
        name="gemini",
        command=command,
        model=model,
        spec=spec or default_prompt_spec(),
    )


def build_codex_classifier(
    *,
    model: str | None = None,
    spec: PromptSpec | None = None,
) -> SubprocessLLMClassifier:
    """Build a classifier that shells out to ``codex exec``.

    Uses ``--ephemeral`` + ``--skip-git-repo-check`` so the invocation
    does not require a git repo and does not persist sessions. The
    final agent message is written via ``--output-last-message`` so
    stdout chatter (reasoning events, warnings) is ignored.
    """
    command: tuple[str, ...] = ("codex", "exec", "--ephemeral", "--skip-git-repo-check")
    if model is not None:
        command = (*command, "-m", model)
    return SubprocessLLMClassifier(
        name="codex",
        command=command,
        model=model,
        spec=spec or default_prompt_spec(),
        output_from_file_flag="--output-last-message",
    )


_BUILDERS: dict[str, Callable[..., LLMClassifier]] = {
    "claude": build_claude_classifier,
    "gemini": build_gemini_classifier,
    "codex": build_codex_classifier,
}


def resolve_classifier(
    provider: str,
    *,
    model: str | None = None,
    spec: PromptSpec | None = None,
) -> LLMClassifier:
    """Return a classifier for the given provider name.

    Args:
        provider: One of ``"claude"``, ``"gemini"``, ``"codex"``, or a
            name registered via :func:`register_classifier`.
        model: Optional model override passed through to the builder.
        spec: Optional prompt spec override.

    Returns:
        A concrete implementation of :class:`LLMClassifier`.

    Raises:
        LLMClassifierError: If ``provider`` is not a registered builder.
    """
    try:
        builder = _BUILDERS[provider.lower()]
    except KeyError as exc:
        valid = ", ".join(sorted(_BUILDERS))
        raise LLMClassifierError(f"unknown LLM provider: {provider!r}; valid: {valid}") from exc
    return builder(model=model, spec=spec)


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
    "PIPELINE_ONLY_CLASSIFICATIONS",
    "CategoryChoice",
    "ClassificationChoice",
    "LLMClassificationResponse",
    "LLMClassifier",
    "LLMClassifierError",
    "PromptSpec",
    "SubprocessLLMClassifier",
    "build_claude_classifier",
    "build_codex_classifier",
    "build_gemini_classifier",
    "build_prompt",
    "default_classification_choices",
    "default_prompt_spec",
    "parse_response",
    "prompt_spec_with_every_spending_category",
    "register_classifier",
    "resolve_classifier",
    "unregister_classifier",
]
