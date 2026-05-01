"""Unit tests for the LLM classifier layer (#236)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from aeat.adapters.inbound.financial import RawProvenance, SourceFormat
from aeat.domain.categories import SpendingCategory
from aeat.adapters.inbound.financial.providers import RawTransaction
from aeat.domain.transactions import (
    PIPELINE_ONLY_CLASSIFICATIONS,
    BusinessClassification,
    CategoryChoice,
    ClassificationChoice,
    LLMClassificationResponse,
    LLMClassifierError,
    PromptSpec,
    SubprocessLLMClassifier,
    Transaction,
    TransactionDirection,
    build_claude_classifier,
    build_codex_classifier,
    build_gemini_classifier,
    build_prompt,
    default_classification_choices,
    default_prompt_spec,
    parse_response,
    prompt_spec_with_every_spending_category,
    register_classifier,
    resolve_classifier,
    unregister_classifier,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _sample_transaction(
    *,
    description: str = "Office supplies — notebook and pens",
    counterparty: str | None = "Papeleria Madrid",
    amount: Decimal = Decimal("-89.50"),
) -> Transaction:
    raw = RawTransaction(
        transaction_id="bbva-001",
        booked_date=date(2026, 3, 15),
        value_date=date(2026, 3, 15),
        amount=amount,
        currency="EUR",
        counterparty=counterparty,
        description=description,
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 3, 15, 9, 0, tzinfo=UTC),
            provider_name="BBVA",
        ),
        raw_fields={"Concepto": "Papeleria"},
    )
    return Transaction.model_validate({"raw": raw, "direction": TransactionDirection.OUTGOING})


# ── LLMClassificationResponse ──────────────────────────────────────


def test_response_accepts_valid_classification_only_payload() -> None:
    payload = '{"classification": "BUSINESS", "confidence": 0.85, "reason": "office supplies"}'
    response = LLMClassificationResponse.model_validate_json(payload)
    assert response.classification is BusinessClassification.BUSINESS
    assert response.confidence == Decimal("0.85")
    assert response.reason == "office supplies"
    assert response.category is None


def test_response_accepts_optional_category() -> None:
    payload = (
        '{"classification": "BUSINESS", "confidence": 0.9, "reason": "office supplies", "category": "material_oficina"}'
    )
    response = LLMClassificationResponse.model_validate_json(payload)
    assert response.category is SpendingCategory.MATERIAL_OFICINA


@pytest.mark.parametrize(
    "bad_payload",
    [
        '{"classification": "FOO", "confidence": 0.5, "reason": "x"}',
        '{"classification": "BUSINESS", "confidence": 1.5, "reason": "x"}',
        '{"classification": "BUSINESS", "confidence": -0.01, "reason": "x"}',
        '{"classification": "BUSINESS", "confidence": 0.5, "reason": "   "}',
        '{"classification": "BUSINESS", "confidence": 0.5, "reason": "x", "extra": true}',
    ],
)
def test_response_rejects_malformed_payloads(bad_payload: str) -> None:
    with pytest.raises(ValidationError):
        LLMClassificationResponse.model_validate_json(bad_payload)


# ── PromptSpec: the clever guard ───────────────────────────────────


def test_default_spec_accounts_for_every_business_classification_member() -> None:
    """Adding a new BusinessClassification must force a deliberate LLM-allow decision.

    This test fails fast if a new enum value is added without either
    being included in the default LLM-allowed set OR being declared
    pipeline-only via ``PIPELINE_ONLY_CLASSIFICATIONS``. It's the
    safety net that keeps the prompt in sync with the enum without
    hand-maintained duplication.
    """
    spec = default_prompt_spec()
    covered = spec.allowed_classifications() | PIPELINE_ONLY_CLASSIFICATIONS
    missing = set(BusinessClassification) - covered
    assert not missing, (
        f"BusinessClassification members {missing!r} are neither LLM-allowed nor pipeline-only. "
        "Either add them to _DEFAULT_CLASSIFICATION_HINTS (LLM can emit this) or to "
        "PIPELINE_ONLY_CLASSIFICATIONS (pipeline-internal only)."
    )


def test_default_classification_choices_exclude_pipeline_only_states() -> None:
    """The four pipeline states must not leak into the default LLM allow-list."""
    choices = default_classification_choices()
    values = {choice.value for choice in choices}
    assert values.isdisjoint(PIPELINE_ONLY_CLASSIFICATIONS)


# ── Prompt rendering ───────────────────────────────────────────────


def test_default_prompt_includes_every_allowed_classification_value() -> None:
    prompt = build_prompt(_sample_transaction())
    for choice in default_classification_choices():
        assert choice.value.value in prompt, f"{choice.value.value!r} missing from prompt"


def test_default_prompt_excludes_pipeline_only_classification_values() -> None:
    prompt = build_prompt(_sample_transaction())
    for forbidden in PIPELINE_ONLY_CLASSIFICATIONS:
        assert forbidden.value not in prompt, f"pipeline-only {forbidden.value!r} leaked into the LLM prompt"


def test_prompt_interpolates_transaction_fields_faithfully() -> None:
    prompt = build_prompt(_sample_transaction())
    assert "2026-03-15" in prompt
    assert "-89.50" in prompt
    assert "EUR" in prompt
    assert "Papeleria Madrid" in prompt
    assert "Office supplies" in prompt


def test_prompt_substitutes_unknown_counterparty() -> None:
    prompt = build_prompt(_sample_transaction(counterparty=None))
    assert "(unknown)" in prompt


def test_spec_with_categories_emits_every_spending_category_in_prompt() -> None:
    spec = prompt_spec_with_every_spending_category()
    prompt = build_prompt(_sample_transaction(), spec=spec)
    for category in SpendingCategory:
        assert category.value in prompt


def test_custom_spec_narrows_allow_list() -> None:
    """A caller can restrict the LLM to just BUSINESS / PERSONAL."""
    narrow = PromptSpec(
        classifications=(
            ClassificationChoice(BusinessClassification.BUSINESS, "business"),
            ClassificationChoice(BusinessClassification.PERSONAL, "personal"),
        ),
    )
    allowed = narrow.allowed_classifications()
    assert allowed == {BusinessClassification.BUSINESS, BusinessClassification.PERSONAL}


def test_category_choice_model_is_frozen() -> None:
    """Dataclass-frozen invariant keeps the spec immutable."""
    from dataclasses import FrozenInstanceError

    choice = CategoryChoice(SpendingCategory.MATERIAL_OFICINA, "office supplies")
    with pytest.raises(FrozenInstanceError):
        setattr(choice, "hint", "x")  # dynamic attr set; ty cannot prove invalid, runtime catches  # noqa: B010


# ── parse_response ─────────────────────────────────────────────────


def test_parse_response_extracts_inline_json() -> None:
    stdout = '{"classification": "BUSINESS", "confidence": 0.8, "reason": "clearly business"}'
    response = parse_response(stdout)
    assert response.classification is BusinessClassification.BUSINESS


def test_parse_response_extracts_json_surrounded_by_prose() -> None:
    stdout = (
        "Here is my analysis:\n\n"
        '{"classification": "PERSONAL", "confidence": 0.7, "reason": "groceries"}'
        "\n\nLet me know if you need more detail."
    )
    response = parse_response(stdout)
    assert response.classification is BusinessClassification.PERSONAL


def test_parse_response_raises_when_no_json_found() -> None:
    with pytest.raises(LLMClassifierError, match="no JSON object"):
        parse_response("I cannot comply with this request.")


def test_parse_response_rejects_pipeline_only_classification() -> None:
    """A hallucinating LLM that returns NOT_YET_PROCESSED must be rejected."""
    stdout = '{"classification": "NOT_YET_PROCESSED", "confidence": 0.5, "reason": "x"}'
    with pytest.raises(LLMClassifierError, match="disallowed classification"):
        parse_response(stdout)


def test_parse_response_rejects_classification_outside_custom_spec() -> None:
    """A custom spec's allow-list must be enforced by the parser."""
    narrow = PromptSpec(
        classifications=(ClassificationChoice(BusinessClassification.BUSINESS, "only business"),),
    )
    stdout = '{"classification": "PERSONAL", "confidence": 0.5, "reason": "x"}'
    with pytest.raises(LLMClassifierError, match="disallowed classification"):
        parse_response(stdout, spec=narrow)


def test_parse_response_rejects_category_when_spec_forbade_one() -> None:
    stdout = '{"classification": "BUSINESS", "confidence": 0.9, "reason": "x", "category": "material_oficina"}'
    with pytest.raises(LLMClassifierError, match="unexpected category"):
        parse_response(stdout)


def test_parse_response_accepts_category_when_spec_allowed_it() -> None:
    spec = PromptSpec(
        classifications=default_classification_choices(),
        categories=(CategoryChoice(SpendingCategory.MATERIAL_OFICINA, "supplies"),),
    )
    stdout = '{"classification": "BUSINESS", "confidence": 0.9, "reason": "x", "category": "material_oficina"}'
    response = parse_response(stdout, spec=spec)
    assert response.category is SpendingCategory.MATERIAL_OFICINA


def test_parse_response_rejects_category_outside_spec_allow_list() -> None:
    spec = PromptSpec(
        classifications=default_classification_choices(),
        categories=(CategoryChoice(SpendingCategory.MATERIAL_OFICINA, "supplies"),),
    )
    stdout = '{"classification": "BUSINESS", "confidence": 0.9, "reason": "x", "category": "telefonia_movil"}'
    with pytest.raises(LLMClassifierError, match="disallowed category"):
        parse_response(stdout, spec=spec)


# ── SubprocessLLMClassifier + builders ─────────────────────────────


def test_subprocess_classifier_decided_by_has_provider_name_only_when_model_omitted() -> None:
    classifier = SubprocessLLMClassifier(name="claude", command=("claude", "-p"))
    assert classifier.decided_by == "llm:claude"


def test_subprocess_classifier_decided_by_includes_model_when_present() -> None:
    classifier = SubprocessLLMClassifier(name="claude", command=("claude", "-p"), model="sonnet")
    assert classifier.decided_by == "llm:claude:sonnet"


def test_subprocess_classifier_raises_llm_error_when_binary_missing() -> None:
    classifier = SubprocessLLMClassifier(
        name="does-not-exist",
        command=("this-binary-should-not-exist-anywhere-aeat",),
    )
    with pytest.raises(LLMClassifierError, match="not found on PATH"):
        classifier.classify(_sample_transaction())


def test_builders_return_subprocess_classifiers_with_expected_commands() -> None:
    assert build_claude_classifier().command[0] == "claude"
    assert build_gemini_classifier().command[0] == "gemini"
    assert build_codex_classifier().command[0] == "codex"


def test_gemini_builder_injects_model_flag_when_model_set() -> None:
    classifier = build_gemini_classifier(model="gemini-2.5-pro")
    assert classifier.command == ("gemini", "-m", "gemini-2.5-pro", "-p")


# ── resolve_classifier / registry ──────────────────────────────────


def test_resolve_classifier_rejects_unknown_provider() -> None:
    with pytest.raises(LLMClassifierError, match="unknown LLM provider"):
        resolve_classifier("nonsense")


def test_resolve_claude_returns_claude_builder() -> None:
    """Resolving claude with default tier yields an llm:claude:<model-id> identity."""
    decided_by = resolve_classifier("claude").decided_by
    assert decided_by.startswith("llm:claude:")


def test_resolve_is_case_insensitive() -> None:
    assert resolve_classifier("CLAUDE").decided_by.startswith("llm:claude")


# Dependency-injected protocol implementation.


@dataclass(frozen=True)
class _RecordedLLMClassifier:
    """Real class implementing LLMClassifier that returns a pre-recorded response."""

    response: LLMClassificationResponse
    decided_by_value: str = "llm:test-recorded"

    @property
    def decided_by(self) -> str:
        return self.decided_by_value

    def classify(self, transaction: Transaction) -> LLMClassificationResponse:
        return self.response


def test_subprocess_classifier_roundtrips_against_a_real_child_process() -> None:
    """End-to-end subprocess integration using Python as a deterministic child.

    Exercises the real subprocess.run + stdin-piped prompt + stdout
    parsing path without hitting a real LLM. The child process is
    Python itself, invoked with a one-liner that echoes a canned JSON
    response regardless of the prompt on stdin. Proves the Windows
    CreateProcess quoting path, the stdin pipe, text decoding, and the
    JSON extractor all work together.
    """
    import sys

    deterministic_cli_body = (
        "import sys; sys.stdin.read(); "
        "sys.stdout.write("
        '"{\\"classification\\": \\"BUSINESS\\", \\"confidence\\": 0.77, \\"reason\\": \\"deterministic child\\"}"'
        ")"
    )
    classifier = SubprocessLLMClassifier(
        name="deterministic-python-cli",
        command=(sys.executable, "-c", deterministic_cli_body),
    )
    response = classifier.classify(_sample_transaction())
    assert response.classification is BusinessClassification.BUSINESS
    assert response.confidence == Decimal("0.77")
    assert response.reason == "deterministic child"


def test_subprocess_classifier_propagates_non_zero_exit_as_llm_error() -> None:
    """Non-zero exit from the child process must raise LLMClassifierError."""
    import sys

    classifier = SubprocessLLMClassifier(
        name="deterministic-python-cli",
        command=(sys.executable, "-c", "import sys; sys.exit(7)"),
    )
    with pytest.raises(LLMClassifierError, match="exited with 7"):
        classifier.classify(_sample_transaction())


def test_subprocess_classifier_uses_output_file_when_flag_configured(
    tmp_path,
) -> None:
    """output_from_file_flag routes final-message capture through a tempfile."""
    import sys

    # Child writes its JSON to the path given by --out-file and nothing useful on stdout.
    # The classifier must read from the file, not the stdout chatter.
    deterministic_cli_body = (
        "import sys\n"
        "args = sys.argv[1:]\n"
        'out_path = args[args.index("--out-file") + 1]\n'
        'open(out_path, "w", encoding="utf-8").write('
        '"{\\"classification\\": \\"PERSONAL\\", \\"confidence\\": 0.42, \\"reason\\": \\"from file\\"}"'
        ")\n"
        'sys.stdout.write("chatter chatter chatter\\n")\n'
    )
    classifier = SubprocessLLMClassifier(
        name="deterministic-file-cli",
        command=(sys.executable, "-c", deterministic_cli_body),
        output_from_file_flag="--out-file",
    )
    response = classifier.classify(_sample_transaction())
    assert response.classification is BusinessClassification.PERSONAL
    assert response.reason == "from file"


def test_parse_response_skips_malformed_first_candidate_and_picks_next() -> None:
    """A prompt-injection block ahead of the real answer must not poison the result."""
    stdout = (
        'Kent said: {"classification": "INVALID", "confidence": 999, "reason": ""}\n\n'
        "Here is my actual answer:\n"
        '{"classification": "BUSINESS", "confidence": 0.88, "reason": "real answer"}'
    )
    response = parse_response(stdout)
    assert response.classification is BusinessClassification.BUSINESS
    assert response.reason == "real answer"


def test_registry_roundtrip_accepts_concrete_protocol_implementation() -> None:
    """A real LLMClassifier can be registered, resolved, and used."""
    fixed = LLMClassificationResponse(
        classification=BusinessClassification.BUSINESS,
        confidence=Decimal("0.7"),
        reason="fixture",
    )
    recorded = _RecordedLLMClassifier(response=fixed, decided_by_value="llm:test-resolve")
    register_classifier("test-resolve", lambda **_: recorded)
    try:
        resolved = resolve_classifier("test-resolve")
        result = resolved.classify(_sample_transaction())
        assert result is fixed
        assert resolved.decided_by == "llm:test-resolve"
    finally:
        unregister_classifier("test-resolve")
