"""Typer command factory for wizard flows.

``build_wizard_command(flow)`` returns a Typer-compatible callable
whose signature is composed at construction time from the flow's
questions plus three fixed mode flags (``--profile``,
``--quiet``, ``--accept-defaults``). The closure walks the flow
against a ``Prompter`` and persists the typed answers.

Flag derivation per question kind:

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
from typing import Annotated

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


_SETUP_OPTION_INFOS: dict[str, object] = {
    "tax-id": typer.Option("--tax-id", help=tr("wizard.setup.flags.tax-id.help")),
    "name": typer.Option("--name", help=tr("wizard.setup.flags.name.help")),
    "surnames": typer.Option("--surnames", help=tr("wizard.setup.flags.surnames.help")),
    "activity": typer.Option("--activity", help=tr("wizard.setup.flags.activity.help")),
    "address-postcode": typer.Option("--address-postcode", help=tr("wizard.setup.flags.address-postcode.help")),
    "taxation-type": typer.Option(
        "--taxation-type",
        click_type=click.Choice(["1", "2"]),
        help=tr("wizard.setup.flags.taxation-type.help"),
    ),
    "output-language": typer.Option(
        "--output-language",
        click_type=click.Choice(["es", "en", "ca", "hu"]),
        help=tr("wizard.setup.flags.output-language.help"),
    ),
    "taxpayer-sex": typer.Option(
        "--taxpayer-sex",
        click_type=click.Choice(["H", "M"]),
        help=tr("wizard.setup.flags.taxpayer-sex.help"),
    ),
    "taxpayer-marital-status": typer.Option(
        "--taxpayer-marital-status",
        click_type=click.Choice(["1", "2", "3", "4"]),
        help=tr("wizard.setup.flags.taxpayer-marital-status.help"),
    ),
    "taxpayer-birth-date": typer.Option(
        "--taxpayer-birth-date",
        help=tr("wizard.setup.flags.taxpayer-birth-date.help"),
    ),
    "taxpayer-disability-grade": typer.Option(
        "--taxpayer-disability-grade",
        click_type=click.Choice(["1", "2", "3", "4"]),
        help=tr("wizard.setup.flags.taxpayer-disability-grade.help"),
    ),
    "taxpayer-death-date": typer.Option(
        "--taxpayer-death-date",
        help=tr("wizard.setup.flags.taxpayer-death-date.help"),
    ),
    "spouse-tax-id": typer.Option("--spouse-tax-id", help=tr("wizard.setup.flags.spouse-tax-id.help")),
    "spouse-name": typer.Option("--spouse-name", help=tr("wizard.setup.flags.spouse-name.help")),
    "spouse-surnames": typer.Option("--spouse-surnames", help=tr("wizard.setup.flags.spouse-surnames.help")),
    "spouse-birth-date": typer.Option(
        "--spouse-birth-date",
        help=tr("wizard.setup.flags.spouse-birth-date.help"),
    ),
    "spouse-sex": typer.Option(
        "--spouse-sex",
        click_type=click.Choice(["H", "M"]),
        help=tr("wizard.setup.flags.spouse-sex.help"),
    ),
    "spouse-disability-grade": typer.Option(
        "--spouse-disability-grade",
        click_type=click.Choice(["1", "2", "3", "4"]),
        help=tr("wizard.setup.flags.spouse-disability-grade.help"),
    ),
    "spouse-non-resident-irpf": typer.Option(
        "--spouse-non-resident-irpf/--no-spouse-non-resident-irpf",
        help=tr("wizard.setup.flags.spouse-non-resident-irpf.help"),
    ),
    "spouse-eu-eea-resident": typer.Option(
        "--spouse-eu-eea-resident/--no-spouse-eu-eea-resident",
        help=tr("wizard.setup.flags.spouse-eu-eea-resident.help"),
    ),
    "spouse-eu-eea-country": typer.Option(
        "--spouse-eu-eea-country",
        help=tr("wizard.setup.flags.spouse-eu-eea-country.help"),
    ),
    "family-descendants-eu-eea-deduction": typer.Option(
        "--family-descendants-eu-eea-deduction/--no-family-descendants-eu-eea-deduction",
        help=tr("wizard.setup.flags.family-descendants-eu-eea-deduction.help"),
    ),
    "family-minor-children-in-unit": typer.Option(
        "--family-minor-children-in-unit/--no-family-minor-children-in-unit",
        help=tr("wizard.setup.flags.family-minor-children-in-unit.help"),
    ),
    "iva-regime": typer.Option(
        "--iva-regime",
        click_type=click.Choice(["GENERAL", "SIMPLIFICADO", "RECARGO_EQUIVALENCIA", "EXENTO"]),
        help=tr("wizard.setup.flags.iva-regime.help"),
    ),
    "iva-roi-enrolled": typer.Option(
        "--iva-roi-enrolled/--no-iva-roi-enrolled",
        help=tr("wizard.setup.flags.iva-roi-enrolled.help"),
    ),
    "iva-oss-enrolled": typer.Option(
        "--iva-oss-enrolled/--no-iva-oss-enrolled",
        help=tr("wizard.setup.flags.iva-oss-enrolled.help"),
    ),
    "iva-intracommunity-operations-exceed-50000-eur": typer.Option(
        "--iva-intracommunity-operations-exceed-50000-eur/--no-iva-intracommunity-operations-exceed-50000-eur",
        help=tr("wizard.setup.flags.iva-intracommunity-operations-exceed-50000-eur.help"),
    ),
    "enrollment-large-company": typer.Option(
        "--enrollment-large-company/--no-enrollment-large-company",
        help=tr("wizard.setup.flags.enrollment-large-company.help"),
    ),
    "enrollment-public-administration-budget-gt-6000000": typer.Option(
        "--enrollment-public-administration-budget-gt-6000000/--no-enrollment-public-administration-budget-gt-6000000",
        help=tr("wizard.setup.flags.enrollment-public-administration-budget-gt-6000000.help"),
    ),
    "has-employees": typer.Option(
        "--has-employees/--no-has-employees",
        help=tr("wizard.setup.flags.has-employees.help"),
    ),
    "pays-professionals-with-retencion": typer.Option(
        "--pays-professionals-with-retencion/--no-pays-professionals-with-retencion",
        help=tr("wizard.setup.flags.pays-professionals-with-retencion.help"),
    ),
    "professional-income-withholding-ge-70pct": typer.Option(
        "--professional-income-withholding-ge-70pct/--no-professional-income-withholding-ge-70pct",
        help=tr("wizard.setup.flags.professional-income-withholding-ge-70pct.help"),
    ),
    "pays-rent-with-retencion": typer.Option(
        "--pays-rent-with-retencion/--no-pays-rent-with-retencion",
        help=tr("wizard.setup.flags.pays-rent-with-retencion.help"),
    ),
    "pays-capital-income-with-retencion": typer.Option(
        "--pays-capital-income-with-retencion/--no-pays-capital-income-with-retencion",
        help=tr("wizard.setup.flags.pays-capital-income-with-retencion.help"),
    ),
    "uses-objective-estimation-irpf": typer.Option(
        "--uses-objective-estimation-irpf/--no-uses-objective-estimation-irpf",
        help=tr("wizard.setup.flags.uses-objective-estimation-irpf.help"),
    ),
    "does-intracomunitario": typer.Option(
        "--does-intracomunitario/--no-does-intracomunitario",
        help=tr("wizard.setup.flags.does-intracomunitario.help"),
    ),
    "third-party-transactions-above-347-threshold": typer.Option(
        "--third-party-transactions-above-347-threshold/--no-third-party-transactions-above-347-threshold",
        help=tr("wizard.setup.flags.third-party-transactions-above-347-threshold.help"),
    ),
    "bienes-extranjero-above-threshold": typer.Option(
        "--bienes-extranjero-above-threshold/--no-bienes-extranjero-above-threshold",
        help=tr("wizard.setup.flags.bienes-extranjero-above-threshold.help"),
    ),
    "tax-residence-ccaa": typer.Option(
        "--tax-residence-ccaa",
        click_type=click.Choice(
            [
                "andalucia",
                "aragon",
                "asturias",
                "baleares",
                "canarias",
                "cantabria",
                "castilla_la_mancha",
                "castilla_y_leon",
                "cataluna",
                "comunidad_valenciana",
                "extremadura",
                "galicia",
                "la_rioja",
                "madrid",
                "murcia",
            ]
        ),
        help=tr("wizard.setup.flags.tax-residence-ccaa.help"),
    ),
    "notes": typer.Option("--notes", help=tr("wizard.setup.flags.notes.help")),
}


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


def _canonical_from_flag_value(question: WizardQuestion, value: object) -> str | None:
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
        if isinstance(value, int):
            return str(value)
        return str(int(str(value)))
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

    _flag_name(question)
    del section_title
    try:
        option = _SETUP_OPTION_INFOS[question.id]
    except KeyError as exc:
        raise KeyError(_help_key(flow, question)) from exc
    annotation: object
    default: object
    match question.widget:
        case WizardWidget.CONFIRM:
            annotation = Annotated[bool | None, option]
            default = None
        case WizardWidget.SELECT:
            annotation = Annotated[str | None, option]
            default = None
        case WizardWidget.CHECKBOX:
            annotation = Annotated[list[str], option]
            default = []
        case WizardWidget.INTEGER:
            annotation = Annotated[int | None, option]
            default = None
        case WizardWidget.PATH:
            annotation = Annotated[Path | None, option]
            default = None
        case WizardWidget.SECRET:
            annotation = Annotated[str | None, option]
            default = None
        case WizardWidget.TEXT:
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
        default=...,
        annotation=Annotated[
            str,
            typer.Argument(
                ...,
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
    title so ``aeat config profile create NAME --help`` renders one help panel per
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
    kwargs: dict[str, object],
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

    def _command(*, _prompter: Prompter | None = None, **kwargs: object) -> None:
        from ..workflow._persistence import workflow_state_repository

        raw_profile_name = kwargs.pop("profile_name")
        if not isinstance(raw_profile_name, str) or not raw_profile_name.strip():
            raise WizardMissingFlagError(
                tr("application.wizard.errors.profile_flag_required"),
                context={"flow_id": flow.id, "missing": ("profile_name",)},
            )
        profile_name = raw_profile_name.strip()
        quiet = bool(kwargs.pop("quiet", False))
        accept_defaults = bool(kwargs.pop("accept_defaults", False))
        canonical = _collect_flag_values(flow, kwargs)

        if accept_defaults:
            seeded: dict[str, str] = {
                question.id: question.default or ""
                for section in flow.sections
                for question in section.questions
                if question.default is not None
            }
            seeded.update(canonical)
            canonical = seeded

        if quiet:
            missing = _missing_required_flags(flow, canonical)
            if missing:
                raise WizardMissingFlagError(
                    tr("application.wizard.errors.quiet_missing_flags"),
                    context={"flow_id": flow.id, "missing": missing},
                )
            scripted = _scripted_from_canonical(flow, canonical)
            answers = run_flow(flow, scripted)
        elif accept_defaults:
            scripted = _scripted_from_canonical(flow, canonical)
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
