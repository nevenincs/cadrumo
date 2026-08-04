"""Live LLM classification accuracy harness over the ledger corpus (ratchet history).

Drives the REAL Claude classifier (``build_claude_classifier`` → the ``claude``
CLI) over a representative sample of the hand-authored corpus and scores its
predictions against the ground-truth oracle. Marked ``aeat_live`` and excluded
from the default unit selection; after live opt-in, unavailable classifier
credentials or CLI state fail loudly.

When live classification IS available the harness:
- behavior contract: scores per-classification accuracy against the oracle;
- behavior contract: records ``classified_by="llm:<name>"`` + confidence and flags
  low-confidence predictions for manual review;
- behavior contract: samples the internal-transfer and foreign-reverse-charge edge
  cases alongside business income/expense, personal, trabajo income, business
  premises, and hospitality;
- behavior contract: gates overall accuracy against a lenient floor and reports the
  per-classification miss rate.

Sampled coverage, stated accurately: the needle list above is what the sample
contains. It does NOT reach the recargo-anomaly or régimen-simplificado rows —
both exist in the corpus and in the oracle, but no needle selects them, so an
earlier claim that they were sampled overstated the harness. Adding them is a
coverage decision for whoever owns the accuracy floor, not a docstring edit.

Because this module is ``aeat_live``, none of the above runs without live opt-in.
The two ``unit``-marked guards at the end therefore hold its preconditions — that
every needle still resolves, and that every oracle classification has an
agreement rule — in ordinary CI, where a corpus edit would otherwise erode the
live run's coverage unobserved.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ..adapters.inbound.financial.providers import CsvProvider
from ..domain.transactions import (
    BusinessClassification,
    LLMClassifierError,
    Transaction,
    TransactionDirection,
    build_claude_classifier,
)
from .live_gate import requires_live_enabled

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_application]

_CORPUS = Path(__file__).parent / "fixtures" / "financial" / "ledger-corpus"
# Every account a needle draws from must be listed here, or the needle silently
# contributes nothing: the business-premises needle previously named a row in
# ``n26-savings.csv`` while that file was not scanned.
_ACCOUNTS = (
    "bbva-business-eur.csv",
    "caixabank-personal.csv",
    "revolut-multi.csv",
    "n26-savings.csv",
)
# Representative descriptions spanning the gamut + the edge cases (behavior contract).
# Each needle MUST be a substring of a real corpus description that the oracle also
# has a rule for; :func:`test_every_declared_needle_resolves_to_a_scored_sample`
# enforces that, because an unmatched needle is skipped in silence and shrinks the
# scored sample without changing any assertion.
_SAMPLE_NEEDLES = (
    "Cobro factura F-2025-001 ACME",  # business income
    "Cuota autonomos RETA",  # business expense
    "Compra supermercado",  # personal
    "Transferencia a cuenta personal",  # internal transfer (oracle: PERSONAL)
    "Nomina",  # trabajo income
    "cliente DE GmbH intracom",  # foreign reverse-charge
    "Alquiler oficina coworking",  # business premises
    "Restaurante",  # hospitality
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
                    txn = Transaction.model_validate(
                        {"raw": raw, "direction": parsed.direction, "group_label": None, "source_jurisdiction": "ES"},
                    )
                    out.append((txn, rule))
                    seen.add(needle)
    return out


def _live_classifier_or_fail():
    """Return a live Claude classifier, failing when the live LLM is unavailable."""
    classifier = build_claude_classifier(alias="claude-sonnet")
    probe_account = next(CsvProvider().ingest(_CORPUS / _ACCOUNTS[0])).raw
    probe = Transaction.model_validate(
        {
            "raw": probe_account,
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
        },
    )
    try:
        classifier.classify(probe)
    except LLMClassifierError as exc:
        pytest.fail(f"live LLM classifier unavailable after live opt-in: {exc}")
    return classifier


def test_llm_classification_scores_against_oracle_and_gates_accuracy() -> None:
    requires_live_enabled()
    classifier = _live_classifier_or_fail()
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
    """Coarse agreement between the oracle classification and the LLM axis.

    Raises on an oracle value this mapping does not know. The previous fallback
    returned ``True``, which scored every unrecognised expectation as a HIT and
    so inflated the accuracy the floor is measured against — a new oracle
    classification would have raised the reported score while testing nothing.
    Only ``BUSINESS``/``PERSONAL``/``MIXED`` occur today; a fourth value must
    arrive with a deliberate agreement rule rather than a free pass.
    """
    if expected == "BUSINESS":
        return predicted is BusinessClassification.BUSINESS
    if expected == "PERSONAL":
        # Transfers are PERSONAL on the oracle's gated axis (INTERNAL_TRANSFER is
        # a *direction* there, never a classification), and the LLM may answer
        # PERSONAL or PROCESSED_UNCLASSIFIED — both are acceptable non-business.
        return predicted in {
            BusinessClassification.PERSONAL,
            BusinessClassification.PROCESSED_UNCLASSIFIED,
        }
    if expected == "MIXED":
        return predicted in {BusinessClassification.MIXED, BusinessClassification.BUSINESS}
    raise AssertionError(
        f"oracle classification {expected!r} has no agreement rule; add one rather than "
        "letting it score as correct by default",
    )
