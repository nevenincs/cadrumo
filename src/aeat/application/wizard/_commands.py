"""Typer command factory for wizard flows.

``build_wizard_command(flow)`` returns a closure whose signature is
composed from the flow's questions plus a fixed set of mode flags
(``--quiet``, ``--profile-name``, ``--accept-defaults``). Each question
contributes one optional flag whose type maps to the canonical
serialisation: ``TEXT`` / ``SECRET`` / ``PATH`` → ``str``, ``INTEGER``
→ ``int``, ``CONFIRM`` → ``bool``, ``SELECT`` → ``str``, ``CHECKBOX``
→ ``list[str]``. When ``--quiet`` is set, every required-and-not-
conditional question must supply a flag value or descriptor default;
the closure raises :class:`WizardMissingFlagError` otherwise.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable

from ._catalogue import SETUP_FLOW
from ._errors import WizardMissingFlagError
from ._models import WizardFlow, WizardQuestion, WizardWidget
from ._persistence import persist_answers
from ._prompter import Prompter, QuestionaryPrompter, ScriptedPrompter
from ._runner import run_flow


def _flag_name(question: WizardQuestion) -> str:
    """Map a question id to its Typer flag name."""

    return f"--{question.id}"


def _no_flag_name(question: WizardQuestion) -> str:
    """Map a ``CONFIRM`` question to its negative flag."""

    return f"--no-{question.id}"


def _required_flag_questions(flow: WizardFlow) -> tuple[WizardQuestion, ...]:
    """Return the questions whose value must be supplied in ``--quiet`` mode."""

    return tuple(
        question
        for section in flow.sections
        for question in section.questions
        if question.required and question.visible_when is None
    )


def _missing_required_flags(
    flow: WizardFlow,
    canonical: dict[str, str],
) -> tuple[str, ...]:
    """Return the question ids whose canonical-token value is missing."""

    missing: list[str] = []
    for question in _required_flag_questions(flow):
        if question.id not in canonical or not canonical[question.id]:
            if question.default:
                canonical[question.id] = question.default
            else:
                missing.append(question.id)
    return tuple(missing)


def _scripted_from_canonical(flow: WizardFlow, canonical: dict[str, str]) -> ScriptedPrompter:
    """Build a ``ScriptedPrompter`` from the canonical-token dict.

    The runtime asks questions in flow order; for visible questions
    without a canonical answer, we feed the descriptor default (or an
    empty string for optional / conditional questions).
    """

    answers: deque[str] = deque()
    pending: dict[str, str] = dict(canonical)
    visible_ids: set[str] = set()
    for section in flow.sections:
        for question in section.questions:
            if question.visible_when is not None:
                target = question.visible_when.question_id
                if target not in visible_ids or pending.get(target) != question.visible_when.equals:
                    continue
            visible_ids.add(question.id)
            value = pending.get(question.id, question.default or "")
            answers.append(value)
    return ScriptedPrompter(answers)


def build_wizard_command(flow: WizardFlow) -> Callable[..., None]:
    """Return a Typer-compatible callable that runs ``flow``.

    The returned closure walks ``flow`` against either a
    ``QuestionaryPrompter`` (interactive default) or a
    ``ScriptedPrompter`` driven by the closure's per-question flag
    arguments (``--quiet`` mode). On success, the closure persists the
    typed answers via ``persist_answers``.
    """

    def _command(
        *,
        prompter: Prompter | None = None,
        profile_name: str = "default",
        quiet: bool = False,
        accept_defaults: bool = False,
        flag_values: dict[str, str] | None = None,
    ) -> None:
        from ..workflow._persistence import workflow_state_repository

        flag_values = flag_values or {}
        if quiet:
            canonical: dict[str, str] = dict(flag_values)
            missing = _missing_required_flags(flow, canonical)
            if missing:
                raise WizardMissingFlagError(
                    "missing required flags for --quiet wizard run",
                    context={"flow_id": flow.id, "missing": missing},
                )
            scripted = _scripted_from_canonical(flow, canonical)
            answers = run_flow(flow, scripted)
        elif accept_defaults:
            canonical = {
                question.id: question.default or ""
                for section in flow.sections
                for question in section.questions
                if question.default is not None
            }
            canonical.update(flag_values)
            scripted = _scripted_from_canonical(flow, canonical)
            answers = run_flow(flow, scripted)
        else:
            active = prompter if prompter is not None else QuestionaryPrompter()
            answers = run_flow(flow, active, defaults=flag_values)

        repository = workflow_state_repository()
        repository.update(lambda state: persist_answers(flow, answers, state=state, profile_name=profile_name))

    setattr(_command, "__wizard_flow__", flow)  # noqa: B010
    return _command


def widget_supports_flag(question: WizardQuestion) -> bool:
    """Return True when the question can accept a CLI flag value."""

    return question.widget in {
        WizardWidget.TEXT,
        WizardWidget.SECRET,
        WizardWidget.PATH,
        WizardWidget.INTEGER,
        WizardWidget.CONFIRM,
        WizardWidget.SELECT,
        WizardWidget.CHECKBOX,
    }


def flag_signature(flow: WizardFlow) -> tuple[tuple[str, str, str], ...]:
    """Return the (flag, no_flag, widget) triple for every question.

    Used by tests and the CLI registrar to introspect the descriptor's
    flag surface without actually constructing the Typer command.
    """

    rows: list[tuple[str, str, str]] = []
    for section in flow.sections:
        for question in section.questions:
            rows.append(
                (
                    _flag_name(question),
                    _no_flag_name(question) if question.widget is WizardWidget.CONFIRM else "",
                    question.widget.value,
                )
            )
    return tuple(rows)


__all__ = [
    "SETUP_FLOW",
    "build_wizard_command",
    "flag_signature",
    "widget_supports_flag",
]
