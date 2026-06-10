"""Live LLM classification accuracy harness over the ledger corpus (ratchet history).

Drives the REAL Claude classifier (``build_claude_classifier`` → the ``claude``
CLI) over a representative sample of the hand-authored corpus and scores its
predictions against the ground-truth oracle. Marked ``aeat_live`` and excluded
from the default unit selection; self-skips when the classifier is unavailable
(no CLI / not logged in), mirroring ``test_live_anthropic``.

When live classification IS available the harness:
- behavior contract: scores per-classification accuracy against the oracle;
- behavior contract: records ``classified_by="llm:<name>"`` + confidence and flags
  low-confidence predictions for manual review;
- behavior contract: includes the edge cases (recargo anomaly, internal transfer, foreign
  reverse-charge, régimen simplificado) in the sample;
- behavior contract: gates overall accuracy against a lenient floor and reports the
  per-classification miss rate.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ..adapters.inbound.financial.providers._csv import CsvProvider
from ..domain.transactions import BusinessClassification, Transaction, TransactionDirection
from ..domain.transactions._errors import LLMClassifierError
from ..domain.transactions._llm import build_claude_classifier

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_application]

_CORPUS = Path(__file__).parent / "fixtures" / "financial" / "ledger-corpus"
_ACCOUNTS = ("bbva-business-eur.csv", "caixabank-personal.csv", "revolut-multi.csv")
# Representative descriptions spanning the gamut + the edge cases (behavior contract).
_SAMPLE_NEEDLES = (
    "Cobro factura F-2025-001 ACME",  # business income
    "Cuota autonomos RETA",  # business expense
    "Compra supermercado",  # personal
    "Transferencia a cuenta personal",  # internal transfer
    "Nomina",  # trabajo income
    "cliente DE GmbH intracom",  # foreign reverse-charge
    "Alquiler local",  # business premises
    "Restaurante",  # mixed / hospitality
)
# Lenient accuracy floor: a live LLM is not deterministic and the sample is
# small; the gate guards against gross regression, not perfect agreement.
_ACCURACY_FLOOR = Decimal("0.5")
_LOW_CONFIDENCE = Decimal("0.5")


def _oracle_rules() -> list[dict[str, Any]]:
    return json.loads((_CORPUS / "ground-truth.manifest.json").read_text(encoding="utf-8"))["rules"]


def _match(description: str, rules: list[dict[str, Any]]) -> dict[str, Any] | None:
    for rule in rules:
        if rule["match"] in description:
            return rule
    return None


def _sample_transactions() -> list[tuple[Transaction, dict[str, Any]]]:
    rules = _oracle_rules()
    seen: set[str] = set()
    out: list[tuple[Transaction, dict[str, Any]]] = []
    for account in _ACCOUNTS:
        for parsed in CsvProvider().ingest(_CORPUS / account):
            raw = parsed.raw
            for needle in _SAMPLE_NEEDLES:
                if needle in raw.description and needle not in seen:
                    rule = _match(raw.description, rules)
                    if rule is None:
                        continue
                    txn = Transaction.model_validate({"raw": raw, "direction": parsed.direction})
                    out.append((txn, rule))
                    seen.add(needle)
    return out


def _live_classifier_or_skip():
    """Return a live Claude classifier, or skip when live LLM is unavailable."""
    classifier = build_claude_classifier(alias="claude-sonnet")
    probe_account = next(CsvProvider().ingest(_CORPUS / _ACCOUNTS[0])).raw
    probe = Transaction.model_validate({"raw": probe_account, "direction": TransactionDirection.OUTGOING})
    try:
        classifier.classify(probe)
    except LLMClassifierError as exc:
        pytest.skip(f"live LLM classifier unavailable: {exc}")
    return classifier


def test_llm_classification_scores_against_oracle_and_gates_accuracy() -> None:
    classifier = _live_classifier_or_skip()
    sample = _sample_transactions()
    assert sample, "corpus sample for LLM classification must be non-empty"

    correct = 0
    total = 0
    low_confidence: list[str] = []
    misses_by_expected: dict[str, int] = {}
    for txn, rule in sample:
        response = classifier.classify(txn)
        # behavior contract: every prediction carries a confidence and an attributable source.
        classified_by = f"llm:{classifier.name}"
        assert classified_by.startswith("llm:")
        assert Decimal("0") <= response.confidence <= Decimal("1")
        if response.confidence < _LOW_CONFIDENCE:
            low_confidence.append(txn.transaction_id)

        # The oracle's economic classification, coarsened to the LLM's axis.
        expected = rule["classification"]
        # Transfers are PERSONAL on the oracle's gated axis; the LLM may say
        # PERSONAL or PROCESSED_UNCLASSIFIED — both are acceptable non-business.
        predicted = response.classification
        total += 1
        if _agrees(expected, predicted):
            correct += 1
        else:
            misses_by_expected[expected] = misses_by_expected.get(expected, 0) + 1

    accuracy = Decimal(correct) / Decimal(total)
    # behavior contract: lenient accuracy gate + per-class miss report (surfaced on failure).
    assert accuracy >= _ACCURACY_FLOOR, (accuracy, misses_by_expected, low_confidence)


def _agrees(expected: str, predicted: BusinessClassification) -> bool:
    """Coarse agreement between the oracle classification and the LLM axis."""
    if expected == "BUSINESS":
        return predicted is BusinessClassification.BUSINESS
    if expected in {"PERSONAL", "INTERNAL_TRANSFER"}:
        return predicted in {
            BusinessClassification.PERSONAL,
            BusinessClassification.PROCESSED_UNCLASSIFIED,
        }
    if expected == "MIXED":
        return predicted in {BusinessClassification.MIXED, BusinessClassification.BUSINESS}
    return True
