"""The wizard runtime that walks a flow against a prompter.

``run_flow`` iterates a :class:`WizardFlow`'s sections in order,
evaluates each question's ``visible_when`` predicate against the
canonical-token answers collected so far, asks the prompter for
visible questions, runs the widget-level validator on the raw
answer, accumulates the canonical-token dict, parses each value into
its declared ``answer_type``, and returns the flow's
``answers_model`` instance.

Visibility is evaluated *incrementally*, one question at a time, so a
question whose ``visible_when`` predicate names an earlier question
*in the same section* sees that earlier answer. Evaluating a whole
section's visibility upfront — before any question in the section is
answered — would treat such an intra-section gate's parent as absent
and wrongly hide the dependent question.

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
from ._models import WizardCondition, WizardFlow, WizardQuestion, WizardSection, iter_conditions
from ._persistence import _parse_canonical
from ._prompter import Prompter
from ._widgets import validate_widget_answer


def _clause_satisfied(clause: WizardCondition, canonical: Mapping[str, str]) -> bool:
    """Return True when a single ``visible_when`` clause holds.

    The clause cannot be evaluated until its named parent question has
    been answered; an absent parent yields False. ``equals`` is an
    exact, case-sensitive token match; ``contains`` splits the parent's
    comma-joined CHECKBOX answer into a token set and tests membership.
    """
    parent = canonical.get(clause.question_id)
    if parent is None:
        return False
    if clause.contains is not None:
        tokens = {token.strip() for token in parent.split(",") if token.strip()}
        return clause.contains in tokens
    return parent == clause.equals


def _condition_satisfied(
    question: WizardQuestion,
    canonical: Mapping[str, str],
    *,
    force_visible: frozenset[str] = frozenset(),
) -> bool:
    """Return True when the question is visible given the canonical answer set.

    An unconditional question is always visible. A gated question is
    visible when *any* of its ``visible_when`` clauses is satisfied
    (a bare :class:`WizardCondition` is the one-clause case).

    ``force_visible`` names questions whose flag the operator supplied
    explicitly on a non-interactive command line. An explicit flag is
    an unambiguous declaration of intent, so the question is collected
    even when its ``visible_when`` gate would otherwise hide it — the
    gate governs interactive prompting and the demand for a value, not
    whether an explicitly-given value is honoured.
    """
    if question.visible_when is None:
        return True
    if question.id in force_visible:
        return True
    return any(_clause_satisfied(clause, canonical) for clause in iter_conditions(question.visible_when))


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


def _section_progress_total(
    section: WizardSection,
    canonical: Mapping[str, str],
    asked_so_far: int,
    *,
    force_visible: frozenset[str] = frozenset(),
) -> int:
    """Estimate the visible-question count for the section's progress line.

    The total is ``asked_so_far`` (questions already shown this section)
    plus the remaining questions whose ``visible_when`` predicate is
    already satisfiable from ``canonical``. A question that only becomes
    visible after a later answer in the same section is conservatively
    excluded; the running total then ticks up as it is revealed.
    """
    remaining = sum(
        1 for question in section.questions if _condition_satisfied(question, canonical, force_visible=force_visible)
    )
    # `canonical` already carries every answer up to and including the
    # question currently being asked, so `remaining` counts that
    # question and any later siblings whose gate is already satisfied;
    # the questions asked *before* it are not in `remaining`.
    return asked_so_far - 1 + remaining


def run_flow(
    flow: WizardFlow,
    prompter: Prompter,
    *,
    defaults: Mapping[str, str] | None = None,
    force_visible: frozenset[str] = frozenset(),
) -> BaseModel:
    """Walk ``flow`` against ``prompter`` and return the typed answers model.

    Args:
        flow: The descriptor to drive.
        prompter: The interaction source.
        defaults: Optional canonical-token defaults keyed by question id;
            override descriptor-declared defaults when present.
        force_visible: Question ids the operator named explicitly on a
            non-interactive command line. An explicitly-supplied flag
            is collected even when its ``visible_when`` gate would
            otherwise hide the question.

    Returns:
        A validated instance of ``flow.answers_model``.
    """
    defaults_map: Mapping[str, str] = defaults or {}
    canonical: dict[str, str] = {}
    typed: dict[str, object] = {}
    section_total = len(flow.sections)
    _prepare(prompter, flow)

    for section_index, section in enumerate(flow.sections, start=1):
        section_header_emitted = False
        question_index = 0
        for question in section.questions:
            # Evaluate visibility against the answers collected so far,
            # including answers given to *earlier questions in this same
            # section*. A section-wide upfront evaluation would miss an
            # intra-section gate whose parent has not yet been walked.
            if not _condition_satisfied(question, canonical, force_visible=force_visible):
                continue
            if not section_header_emitted:
                _emit(
                    prompter,
                    tr(
                        "wizard.progress.section_header",
                        section_n=section_index,
                        section_total=section_total,
                        title=tr(str(section.title)),
                    ),
                )
                section_header_emitted = True
            question_index += 1
            _emit(
                prompter,
                tr(
                    "wizard.progress.question_prefix",
                    q_n=question_index,
                    q_total=_section_progress_total(section, canonical, question_index, force_visible=force_visible),
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
