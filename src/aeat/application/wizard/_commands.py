"""Typer command factory for wizard flows.

``build_wizard_command(flow)`` returns a Typer-compatible callable
whose signature is composed at construction time from the flow's
questions plus three fixed mode flags (``--profile-name``,
``--quiet``, ``--accept-defaults``). The closure walks the flow
against a ``Prompter`` and persists the typed answers.

Flag derivation per ADR section D:

* ``TEXT`` / ``SECRET`` / ``PATH`` → ``--<question-id>`` ``str``
  option (``Path`` for ``PATH``);
* ``INTEGER`` → ``--<question-id>`` ``int`` option;
* ``CONFIRM`` → ``--<question-id>/--no-<question-id>`` boolean pair;
* ``SELECT`` → ``--<question-id>`` option with
  ``click.Choice([c.value for c in choices])``;
* ``CHECKBOX`` → repeated ``--<question-id>`` option that accumulates
  a ``list[str]``.

The closure accepts a ``Prompter`` injection through the keyword-only
``_prompter`` parameter (not exposed as a Typer option) so tests can
drive the flow without questionary interaction.
"""

from __future__ import annotations

import inspect
import typing
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

import click
import typer

from ...core.i18n import tr
from ._catalogue import SETUP_FLOW
from ._errors import WizardMissingFlagError
from ._models import WizardFlow, WizardQuestion, WizardWidget
from ._persistence import persist_answers
from ._prompter import Prompter, QuestionaryPrompter, ScriptedPrompter
from ._runner import run_flow


def _flag_name(question: WizardQuestion) -> str:
    """Map a question id to its primary Typer flag name."""

    return f"--{question.id}"


def _no_flag_name(question: WizardQuestion) -> str:
    """Map a CONFIRM question to its negative flag name."""

    return f"--no-{question.id}"


def _help_key(flow: WizardFlow, question: WizardQuestion) -> str:
    """Return the translation key used for the flag's ``--help`` text."""

    return f"wizard.{flow.id}.flags.{question.id}.help"


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
    """Build a ``ScriptedPrompter`` driven by the canonical-token dict."""

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


def _canonical_from_flag_value(question: WizardQuestion, value: Any) -> str | None:
    """Project a Typer-parsed flag value into the canonical-token form."""

    if value is None:
        return None
    if question.widget is WizardWidget.CONFIRM:
        if not isinstance(value, bool):
            return None
        return "true" if value else "false"
    if question.widget is WizardWidget.CHECKBOX:
        if not isinstance(value, list | tuple):
            return None
        tokens = [str(item) for item in value if str(item)]
        return ",".join(tokens) if tokens else None
    if question.widget is WizardWidget.INTEGER:
        return str(int(value))
    if question.widget is WizardWidget.PATH:
        return str(value)
    return str(value)


def _python_parameter(
    flow: WizardFlow,
    question: WizardQuestion,
    *,
    section_title: str | None = None,
) -> inspect.Parameter:
    """Build the ``inspect.Parameter`` Typer reads to register a flag.

    ``section_title`` becomes the ``rich_help_panel`` so Typer renders
    each ``WizardSection`` as its own group in the ``--help`` output;
    this groups the 42-flag surface visually and stops the column
    wrapper from ellipsising long flag names.
    """

    flag = _flag_name(question)
    help_text = tr(_help_key(flow, question))
    match question.widget:
        case WizardWidget.CONFIRM:
            option = typer.Option(
                f"{flag}/{_no_flag_name(question)}",
                help=help_text,
                rich_help_panel=section_title,
            )
            annotation = Annotated[bool | None, option]
            default = None
        case WizardWidget.SELECT:
            option = typer.Option(
                flag,
                click_type=click.Choice([choice.value for choice in question.choices]),
                help=help_text,
                rich_help_panel=section_title,
            )
            annotation = Annotated[str | None, option]
            default = None
        case WizardWidget.CHECKBOX:
            option = typer.Option(
                flag,
                click_type=click.Choice([choice.value for choice in question.choices]),
                help=help_text,
                rich_help_panel=section_title,
            )
            annotation = Annotated[list[str], option]
            default = []
        case WizardWidget.INTEGER:
            option = typer.Option(flag, help=help_text, rich_help_panel=section_title)
            annotation = Annotated[int | None, option]
            default = None
        case WizardWidget.PATH:
            option = typer.Option(flag, help=help_text, rich_help_panel=section_title)
            annotation = Annotated[Path | None, option]
            default = None
        case WizardWidget.SECRET:
            option = typer.Option(
                flag,
                help=help_text,
                hide_input=True,
                rich_help_panel=section_title,
            )
            annotation = Annotated[str | None, option]
            default = None
        case WizardWidget.TEXT:
            option = typer.Option(flag, help=help_text, rich_help_panel=section_title)
            annotation = Annotated[str | None, option]
            default = None
    return inspect.Parameter(
        name=question.id.replace("-", "_"),
        kind=inspect.Parameter.KEYWORD_ONLY,
        default=default,
        annotation=annotation,
    )


def _mode_parameters(flow: WizardFlow) -> tuple[inspect.Parameter, ...]:
    """Build the three fixed mode-flag parameters."""

    del flow
    profile_name = inspect.Parameter(
        name="profile_name",
        kind=inspect.Parameter.KEYWORD_ONLY,
        default="default",
        annotation=Annotated[
            str,
            typer.Option(
                "--profile",
                "--profile-name",
                help=tr("cli.config.setup.profile_name_help"),
            ),
        ],
    )
    quiet = inspect.Parameter(
        name="quiet",
        kind=inspect.Parameter.KEYWORD_ONLY,
        default=False,
        annotation=Annotated[
            bool,
            typer.Option("--quiet", help=tr("cli.config.setup.quiet_help")),
        ],
    )
    accept_defaults = inspect.Parameter(
        name="accept_defaults",
        kind=inspect.Parameter.KEYWORD_ONLY,
        default=False,
        annotation=Annotated[
            bool,
            typer.Option("--accept-defaults", help=tr("cli.config.setup.accept_defaults_help")),
        ],
    )
    return (profile_name, quiet, accept_defaults)


def _question_parameters(flow: WizardFlow) -> tuple[inspect.Parameter, ...]:
    """Build one ``inspect.Parameter`` per descriptor question.

    Each question's ``rich_help_panel`` is the section's translated
    title so ``aeat config init --help`` renders one help panel per
    :class:`WizardSection`.
    """

    parameters: list[inspect.Parameter] = []
    for section in flow.sections:
        section_title = tr(str(section.title))
        for question in section.questions:
            parameters.append(_python_parameter(flow, question, section_title=section_title))
    return tuple(parameters)


def _collect_flag_values(
    flow: WizardFlow,
    kwargs: dict[str, Any],
) -> dict[str, str]:
    """Project the closure's keyword arguments into the canonical-token dict."""

    canonical: dict[str, str] = {}
    for section in flow.sections:
        for question in section.questions:
            field_name = question.id.replace("-", "_")
            raw = kwargs.get(field_name)
            canonical_value = _canonical_from_flag_value(question, raw)
            if canonical_value is not None:
                canonical[question.id] = canonical_value
    return canonical


def build_wizard_command(flow: WizardFlow) -> Callable[..., None]:
    """Return a Typer-compatible callable that runs ``flow``.

    The returned closure carries one parameter per question in the
    flow (typed and annotated for Typer to derive a CLI flag) plus the
    three mode flags. Tests can pass a custom prompter through the
    keyword-only ``_prompter`` slot (not surfaced as a Typer option).
    """

    question_params = _question_parameters(flow)
    mode_params = _mode_parameters(flow)
    parameters = (*mode_params, *question_params)

    def _command(*, _prompter: Prompter | None = None, **kwargs: Any) -> None:
        from ..workflow._persistence import workflow_state_repository

        profile_name = kwargs.pop("profile_name", "default")
        quiet = kwargs.pop("quiet", False)
        accept_defaults = kwargs.pop("accept_defaults", False)
        canonical = _collect_flag_values(flow, kwargs)

        if quiet:
            missing = _missing_required_flags(flow, canonical)
            if missing:
                raise WizardMissingFlagError(
                    "missing required flags for --quiet wizard run",
                    context={"flow_id": flow.id, "missing": missing},
                )
            scripted = _scripted_from_canonical(flow, canonical)
            answers = run_flow(flow, scripted)
        elif accept_defaults:
            seeded: dict[str, str] = {
                question.id: question.default or ""
                for section in flow.sections
                for question in section.questions
                if question.default is not None
            }
            seeded.update(canonical)
            scripted = _scripted_from_canonical(flow, seeded)
            answers = run_flow(flow, scripted)
        else:
            active = _prompter if _prompter is not None else QuestionaryPrompter()
            answers = run_flow(flow, active, defaults=canonical)

        repository = workflow_state_repository()
        repository.update(lambda state: persist_answers(flow, answers, state=state, profile_name=profile_name))

    typed = typing.cast(typing.Any, _command)
    typed.__signature__ = inspect.Signature(parameters=list(parameters))
    typed.__annotations__ = {param.name: param.annotation for param in parameters}
    typed.__name__ = flow.id
    typed.__doc__ = tr(f"wizard.{flow.id}.description")
    typed.__wizard_flow__ = flow
    return _command


__all__ = [
    "SETUP_FLOW",
    "build_wizard_command",
]
