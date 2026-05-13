"""Focused unit tests for wizard._runner._condition_satisfied.

`_condition_satisfied` is the visibility-predicate evaluator that
gates per-question display based on the canonical answers collected
so far. Three documented branches:

1. ``visible_when is None`` → True (unconditional visibility).
2. ``visible_when`` set, parent answer absent from canonical → False.
3. ``visible_when`` set, parent answer present → True iff
   ``parent == visible_when.equals`` (exact, case-sensitive match).

Currently exercised only indirectly through ``run_flow`` end-to-end
tests. A regression in any branch — returning True when the parent
is absent, comparing case-insensitively, or treating a missing
parent as satisfied — would silently expose or hide questions to
the operator across every wizard session.

Tests here pin each branch's documented behaviour; assertions are
structural / predicate-contract assertions, not calculation
tautologies.
"""

from __future__ import annotations

import pytest

from ...core.i18n import Translatable
from ._models import WizardCondition, WizardQuestion, WizardWidget
from ._runner import _condition_satisfied

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _question(
    *,
    qid: str = "example",
    visible_when: WizardCondition | None = None,
) -> WizardQuestion:
    return WizardQuestion(
        id=qid,
        widget=WizardWidget.TEXT,
        prompt=Translatable("wizard.test.example.prompt"),
        choices=(),
        default=None,
        visible_when=visible_when,
        answer_type=str,
    )


def test_condition_satisfied_returns_true_when_visible_when_is_none() -> None:
    """Unconditional visibility: the helper returns True regardless of
    canonical contents (including the empty dict)."""
    question = _question(visible_when=None)

    assert _condition_satisfied(question, {}) is True
    assert _condition_satisfied(question, {"unrelated": "value"}) is True


def test_condition_satisfied_returns_false_when_parent_absent_from_canonical() -> None:
    """The gate cannot be evaluated until the parent question has been
    answered; the helper refuses to show the dependent question."""
    question = _question(
        visible_when=WizardCondition(question_id="declaration_type", equals="2"),
    )

    assert _condition_satisfied(question, {}) is False
    assert _condition_satisfied(question, {"other.key": "value"}) is False


def test_condition_satisfied_returns_false_when_parent_value_does_not_match_equals() -> None:
    question = _question(
        visible_when=WizardCondition(question_id="declaration_type", equals="2"),
    )

    assert _condition_satisfied(question, {"declaration_type": "1"}) is False


def test_condition_satisfied_returns_true_when_parent_value_exactly_matches_equals() -> None:
    question = _question(
        visible_when=WizardCondition(question_id="declaration_type", equals="2"),
    )

    assert _condition_satisfied(question, {"declaration_type": "2"}) is True


def test_condition_satisfied_is_case_sensitive_on_equals_comparison() -> None:
    """Parent values differ only by case → False. The wizard runtime
    stores canonical answers in their as-supplied form; a case-
    insensitive predicate would silently match operator-typed
    variants and confuse the visibility logic."""
    question = _question(
        visible_when=WizardCondition(question_id="declaration_type", equals="madrid"),
    )

    assert _condition_satisfied(question, {"declaration_type": "MADRID"}) is False
    assert _condition_satisfied(question, {"declaration_type": "Madrid"}) is False


def test_condition_satisfied_matches_canonical_true_token_for_boolean_gates() -> None:
    """Boolean gate-questions store ``"true"`` / ``"false"`` as the
    canonical token (per `_persistence._canonicalise`). The predicate
    compares against that canonical form, not against a Python
    ``True`` literal."""
    question = _question(
        visible_when=WizardCondition(question_id="pays_iva", equals="true"),
    )

    assert _condition_satisfied(question, {"pays_iva": "true"}) is True
    assert _condition_satisfied(question, {"pays_iva": "false"}) is False
