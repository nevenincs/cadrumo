"""The wizard runtime that walks a flow against a prompter.

``run_flow`` iterates a :class:`WizardFlow`'s sections in order,
evaluates each question's ``visible_when`` predicate against the
canonical-token answers collected so far, asks the prompter for
visible questions, runs the widget-level validator on the raw
answer, accumulates the canonical-token dict, parses each value into
its declared ``answer_type``, and returns the flow's
``answers_model`` instance.

Section / question progress lines:
    Before each section's first visible question, the runner emits a
    translated "Sección N/M: <title>" header via the prompter's
    optional ``emit_progress`` hook. Each question within the section
    prepends "(pregunta n/m) " to its prompt via the same hook. The
    descriptor knows the static section / question counts; visible-
    when conditionals adjust the runtime per-section visible count.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel

from ...core.i18n import tr
from ._models import WizardFlow, WizardQuestion, WizardSection
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


def _emit(prompter: Prompter, text: str) -> None:
    """Emit ``text`` through the prompter if it carries the optional hook."""

    hook = getattr(prompter, "emit_progress", None)
    if callable(hook):
        hook(text)


def _prepare(prompter: Prompter, flow: WizardFlow) -> None:
    """Let interactive prompters validate and introduce the flow before progress."""

    hook = getattr(prompter, "prepare", None)
    if callable(hook):
        hook(flow)


def _section_visible_questions(
    section: WizardSection,
    canonical: Mapping[str, str],
) -> list[WizardQuestion]:
    """Return the section's questions whose ``visible_when`` predicate
    is satisfied by the accumulated canonical answers so far."""

    return [question for question in section.questions if _condition_satisfied(question, canonical)]


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
    section_total = len(flow.sections)
    _prepare(prompter, flow)

    for section_index, section in enumerate(flow.sections, start=1):
        visible_questions = _section_visible_questions(section, canonical)
        if not visible_questions:
            continue
        _emit(
            prompter,
            tr(
                "wizard.progress.section_header",
                section_n=section_index,
                section_total=section_total,
                title=tr(str(section.title)),
            ),
        )
        question_total = len(visible_questions)
        for question_index, question in enumerate(visible_questions, start=1):
            _emit(
                prompter,
                tr(
                    "wizard.progress.question_prefix",
                    q_n=question_index,
                    q_total=question_total,
                ),
            )
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
