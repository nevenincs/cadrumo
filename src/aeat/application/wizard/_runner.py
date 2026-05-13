"""The wizard runtime that walks a flow against a prompter.

``run_flow`` iterates a :class:`WizardFlow`'s sections in order,
evaluates each question's ``visible_when`` predicate against the
canonical-token answers collected so far, asks the prompter for
visible questions, runs the widget-level validator on the raw
answer, accumulates the canonical-token dict, parses each value into
its declared ``answer_type``, and returns the flow's
``answers_model`` instance.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel

from ._models import WizardFlow, WizardQuestion
from ._persistence import _parse_canonical
from ._prompter import Prompter
from ._widgets import validate_widget_answer


def _condition_satisfied(question: WizardQuestion, canonical: Mapping[str, str]) -> bool:
    """Return True when the question is visible given the canonical answer set."""

    if question.visible_when is None:
        return True
    parent = canonical.get(question.visible_when.question_id)
    if parent is None:
        return False
    return parent == question.visible_when.equals


def run_flow(
    flow: WizardFlow,
    prompter: Prompter,
    *,
    defaults: Mapping[str, str] | None = None,
) -> BaseModel:
    """Walk ``flow`` against ``prompter`` and return the typed answers model.

    Args:
        flow: The descriptor to drive.
        prompter: The interaction source.
        defaults: Optional canonical-token defaults keyed by question id;
            override descriptor-declared defaults when present.

    Returns:
        A validated instance of ``flow.answers_model``.
    """

    defaults_map: Mapping[str, str] = defaults or {}
    canonical: dict[str, str] = {}
    typed: dict[str, object] = {}

    for section in flow.sections:
        for question in section.questions:
            if not _condition_satisfied(question, canonical):
                continue
            default = defaults_map.get(question.id, question.default)
            raw = prompter.ask(question, default=default)
            validated = validate_widget_answer(question, raw)
            canonical[question.id] = validated
            field_name = question.id.replace("-", "_")
            typed[field_name] = _parse_canonical(question, validated)

    close = getattr(prompter, "close", None)
    if callable(close):
        close()

    return flow.answers_model.model_validate(typed)


__all__ = ["run_flow"]
