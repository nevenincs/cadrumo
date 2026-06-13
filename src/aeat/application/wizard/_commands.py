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
from typing import TYPE_CHECKING, Annotated

if TYPE_CHECKING:
    from ...core.errors import AeatError

import contextlib

import click
import click.types
import typer
import typer._click.types

from ...core.i18n import SUPPORTED_OUTPUT_LANGUAGES, tr
from ._catalogue import SETUP_FLOW
from ._errors import WizardMissingFlagError
from ._models import WizardFlow, WizardQuestion, WizardWidget
from ._persistence import WizardPersistMode
from ._prompter import (
    Prompter,
    QuestionaryPrompter,
    ScriptedPrompter,
    WizardEditUnsupportedConsoleError,
    WizardUnsupportedConsoleError,
)
from ._runner import run_flow


def _choice(values: list[str]) -> typer._click.types.ParamType:
    """Wrap ``click.Choice`` and present it as ``typer._click.types.ParamType``.

    ``click.Choice`` is generic (``Choice[T]``), but the ``typer.Option``
    overload that accepts ``click_type`` declares it as
    ``typer._click.types.ParamType | None``.  Typer vendors its own copy of
    click; the static type hierarchies are unrelated even though at runtime
    ``click.Choice`` is exactly the object typer passes through to click.

    CAST-RATIONALE-CHOICE-PARAM-TYPE: ``typing.cast`` is used here for the
    same reason as in ``build_wizard_command`` — the runtime object is always a
    real ``click.Choice`` instance.  Only the static view is narrowed to the
    typer-internal ``ParamType`` so the ``typer.Option`` overload resolver
    accepts it without an ``Any`` escape.
    """
    # CAST-RATIONALE-CHOICE-PARAM-TYPE: runtime object is a real click.Choice;
    # only the static view is narrowed to typer's vendored ParamType (see docstring).
    return typing.cast("typer._click.types.ParamType", click.Choice(values))


def _ccaa_choice_values() -> list[str]:
    """Return the CCAA choice tokens accepted by ``--tax-residence-ccaa``.

    The list includes all 15 common-regime values from the ``CCAA`` enum
    plus the two foral-regime tokens (``pais_vasco``, ``navarra``).  The
    foral tokens are accepted by Click so the operator receives a
    localised redirect rather than a generic "not one of" error, but they
    are refused by the wizard persistence layer via ``ForalRegimeError``.
    """
    from ...domain.contribuyente._ccaa import CCAA

    common = [member.value for member in CCAA]
    foral = ["pais_vasco", "navarra"]
    return common + foral


_CCAA_CHOICE_VALUES: list[str] = _ccaa_choice_values()


def _fiscal_residency_choice_values() -> list[str]:
    """Return the FiscalResidency choice tokens accepted by ``--fiscal-residency``."""
    from ...domain.deadlines._models import FiscalResidency

    return [member.value for member in FiscalResidency]


_FISCAL_RESIDENCY_CHOICE_VALUES: list[str] = _fiscal_residency_choice_values()


def _taxpayer_type_choice_values() -> tuple[list[str], list[str], list[str], list[str]]:
    """Return choice tokens for the taxpayer-type and IRPF-regime enums.

    Derived from the canonical domain enums (``EntityType``,
    ``LegalEntityForm``, ``IrpfIncomeCategory``, ``IrpfEstimationRegime``)
    so the ``--entity-type``, ``--legal-entity-form``,
    ``--irpf-income-categories``, and ``--irpf-estimation-regime``
    flag choices never drift from the values the wizard catalogue and
    the profile schema validate against.
    """
    from ...domain.deadlines._models import (
        EntityType,
        IrpfEstimationRegime,
        IrpfIncomeCategory,
        LegalEntityForm,
    )

    return (
        [member.value for member in EntityType],
        [member.value for member in LegalEntityForm],
        [member.value for member in IrpfIncomeCategory],
        [member.value for member in IrpfEstimationRegime],
    )


(
    _ENTITY_TYPE_CHOICE_VALUES,
    _LEGAL_ENTITY_FORM_CHOICE_VALUES,
    _IRPF_INCOME_CATEGORY_CHOICE_VALUES,
    _IRPF_ESTIMATION_REGIME_CHOICE_VALUES,
) = _taxpayer_type_choice_values()


def _irpf_personal_choice_values() -> tuple[list[str], list[str]]:
    """Return choice tokens for IRPF-personal enums.

    Derived from the canonical domain enums (``IrpfSpecialRegime``,
    ``SituacionFamiliar``) so the ``--irpf-special-regime`` and
    ``--situacion-familiar`` flag choices never drift from the values
    the wizard catalogue and the profile schema validate against.
    """
    from ...domain.contribuyente import SituacionFamiliar
    from ...domain.deadlines._models import IrpfSpecialRegime

    return (
        [member.value for member in IrpfSpecialRegime],
        [member.value for member in SituacionFamiliar],
    )


(
    _IRPF_SPECIAL_REGIME_CHOICE_VALUES,
    _SITUACION_FAMILIAR_CHOICE_VALUES,
) = _irpf_personal_choice_values()


def _iva_regime_choice_values() -> list[str]:
    """Return the IVARegime choice tokens accepted by ``--iva-regime``."""
    from ...domain.deadlines._models import IVARegime

    return [member.value for member in IVARegime]


_IVA_REGIME_CHOICE_VALUES: list[str] = _iva_regime_choice_values()


def _flag_name(question: WizardQuestion) -> str:
    """Map a question id to its primary Typer flag name."""
    return f"--{question.id}"


def _no_flag_name(question: WizardQuestion) -> str:
    """Map a CONFIRM question to its negative flag name."""
    return f"--no-{question.id}"


def _help_key(flow: WizardFlow, question: WizardQuestion) -> str:
    """Return the translation key used for the flag's ``--help`` text."""
    return f"wizard.{flow.id}.flags.{question.id}.help"


_SETUP_OPTION_INFOS: dict[str, typer.models.OptionInfo] = {
    "tax-id": typer.Option("--tax-id", help=tr("wizard.setup.flags.tax-id.help")),
    "name": typer.Option("--name", help=tr("wizard.setup.flags.name.help")),
    "surnames": typer.Option("--surnames", help=tr("wizard.setup.flags.surnames.help")),
    "activity": typer.Option("--activity", help=tr("wizard.setup.flags.activity.help")),
    "address-postcode": typer.Option("--address-postcode", help=tr("wizard.setup.flags.address-postcode.help")),
    "activity-start-date": typer.Option(
        "--activity-start-date",
        help=tr("wizard.setup.flags.activity-start-date.help"),
    ),
    "taxation-type": typer.Option(
        "--taxation-type",
        click_type=_choice(["1", "2"]),
        help=tr("wizard.setup.flags.taxation-type.help"),
    ),
    "output-language": typer.Option(
        "--output-language",
        help=tr("wizard.setup.flags.output-language.help"),
    ),
    "taxpayer-sex": typer.Option(
        "--taxpayer-sex",
        click_type=_choice(["H", "M"]),
        help=tr("wizard.setup.flags.taxpayer-sex.help"),
    ),
    "taxpayer-marital-status": typer.Option(
        "--taxpayer-marital-status",
        click_type=_choice(["1", "2", "3", "4"]),
        help=tr("wizard.setup.flags.taxpayer-marital-status.help"),
    ),
    "taxpayer-marriage-date": typer.Option(
        "--taxpayer-marriage-date",
        help=tr("wizard.setup.flags.taxpayer-marriage-date.help"),
    ),
    "taxpayer-birth-date": typer.Option(
        "--taxpayer-birth-date",
        help=tr("wizard.setup.flags.taxpayer-birth-date.help"),
    ),
    "taxpayer-disability-grade": typer.Option(
        "--taxpayer-disability-grade",
        click_type=_choice(["1", "2", "3", "4"]),
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
        click_type=_choice(["H", "M"]),
        help=tr("wizard.setup.flags.spouse-sex.help"),
    ),
    "spouse-disability-grade": typer.Option(
        "--spouse-disability-grade",
        click_type=_choice(["1", "2", "3", "4"]),
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
        click_type=_choice(_IVA_REGIME_CHOICE_VALUES),
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
    "fiscal-residency": typer.Option(
        "--fiscal-residency",
        click_type=_choice(_FISCAL_RESIDENCY_CHOICE_VALUES),
        help=tr("wizard.setup.flags.fiscal-residency.help"),
    ),
    "country-of-fiscal-residence": typer.Option(
        "--country-of-fiscal-residence",
        help=tr("wizard.setup.flags.country-of-fiscal-residence.help"),
    ),
    "representante-fiscal-nif": typer.Option(
        "--representante-fiscal-nif",
        help=tr("wizard.setup.flags.representante-fiscal-nif.help"),
    ),
    "representante-fiscal-nombre": typer.Option(
        "--representante-fiscal-nombre",
        help=tr("wizard.setup.flags.representante-fiscal-nombre.help"),
    ),
    "tax-residence-ccaa": typer.Option(
        "--tax-residence-ccaa",
        click_type=_choice(_CCAA_CHOICE_VALUES),
        # The 15 CCAA choices form one ~150-char metavar that Rich
        # wraps mid-token (`com` / `unidad_valenciana`). A short
        # explicit metavar plus `show_choices=False` keeps the metavar
        # column tidy; the choice values are listed in the help text,
        # where they wrap on commas / word boundaries.
        metavar="CCAA",
        show_choices=False,
        help=tr(
            "wizard.setup.flags.tax-residence-ccaa.help",
            choices=", ".join(_CCAA_CHOICE_VALUES),
        ),
    ),
    "notes": typer.Option("--notes", help=tr("wizard.setup.flags.notes.help")),
    "entity-type": typer.Option(
        "--entity-type",
        click_type=_choice(_ENTITY_TYPE_CHOICE_VALUES),
        help=tr("wizard.setup.flags.entity-type.help"),
    ),
    "legal-entity-form": typer.Option(
        "--legal-entity-form",
        click_type=_choice(_LEGAL_ENTITY_FORM_CHOICE_VALUES),
        help=tr("wizard.setup.flags.legal-entity-form.help"),
    ),
    "irpf-income-categories": typer.Option(
        "--irpf-income-categories",
        click_type=_choice(_IRPF_INCOME_CATEGORY_CHOICE_VALUES),
        help=tr("wizard.setup.flags.irpf-income-categories.help"),
    ),
    "incn-prior-12-months": typer.Option(
        "--incn-prior-12-months",
        help=tr("wizard.setup.flags.incn-prior-12-months.help"),
    ),
    "new-entity-first-two-profit-periods": typer.Option(
        "--new-entity-first-two-profit-periods/--no-new-entity-first-two-profit-periods",
        help=tr("wizard.setup.flags.new-entity-first-two-profit-periods.help"),
    ),
    "irpf-estimation-regime": typer.Option(
        "--irpf-estimation-regime",
        click_type=_choice(_IRPF_ESTIMATION_REGIME_CHOICE_VALUES),
        help=tr("wizard.setup.flags.irpf-estimation-regime.help"),
    ),
    "irpf-special-regime": typer.Option(
        "--irpf-special-regime",
        click_type=_choice(_IRPF_SPECIAL_REGIME_CHOICE_VALUES),
        help=tr("wizard.setup.flags.irpf-special-regime.help"),
    ),
    "irpf-special-regime-start-date": typer.Option(
        "--irpf-special-regime-start-date",
        help=tr("wizard.setup.flags.irpf-special-regime-start-date.help"),
    ),
    "situacion-familiar": typer.Option(
        "--situacion-familiar",
        click_type=_choice(_SITUACION_FAMILIAR_CHOICE_VALUES),
        help=tr("wizard.setup.flags.situacion-familiar.help"),
    ),
    "iva-sii-enrolled": typer.Option(
        "--iva-sii-enrolled/--no-iva-sii-enrolled",
        help=tr("wizard.setup.flags.iva-sii-enrolled.help"),
    ),
    "iva-redeme-enrolled": typer.Option(
        "--iva-redeme-enrolled/--no-iva-redeme-enrolled",
        help=tr("wizard.setup.flags.iva-redeme-enrolled.help"),
    ),
}

# Guard against future catalogue / dict drift: every question id that
# the SETUP_FLOW catalogue exposes must have a matching OptionInfo entry.
# This assert fires at import time so a missing entry is discovered
# immediately rather than as a runtime KeyError buried inside a Typer
# command factory call.
_SETUP_CATALOGUE_IDS: frozenset[str] = frozenset(
    question.id for section in SETUP_FLOW.sections for question in section.questions
)
_missing_option_infos = _SETUP_CATALOGUE_IDS - frozenset(_SETUP_OPTION_INFOS)
assert not _missing_option_infos, (
    f"_SETUP_OPTION_INFOS is missing entries for catalogue question ids: "
    f"{sorted(_missing_option_infos)!r}. "
    "Add a typer.Option entry for each missing id."
)


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


def _format_missing_flags(missing: tuple[str, ...]) -> str:
    """Render missing question ids as the ``--flag`` form an operator types.

    A wizard question id (``tax-id``, ``activity``) is the long-option
    spelling minus the leading ``--``. The refusal an operator reads
    must name the actual flags to add, never a raw Python identifier
    tuple.
    """
    return " ".join(f"--{question_id}" for question_id in missing)


def _scripted_from_canonical(
    flow: WizardFlow,
    canonical: dict[str, str],
    *,
    force_visible: frozenset[str] = frozenset(),
) -> ScriptedPrompter:
    """Build a ``ScriptedPrompter`` driven by the canonical-token dict.

    The scripted answer queue must match ``run_flow``'s question
    sequence exactly. Visibility is therefore evaluated with the same
    :func:`_condition_satisfied` predicate the runner uses — including
    the same ``force_visible`` set — walking answer-by-answer so an
    intra-section gate sees the earlier answer. A drift between this
    projection and the runner desyncs the queue and feeds a question
    the wrong token.
    """
    from ._runner import _condition_satisfied

    answers: deque[str] = deque()
    running: dict[str, str] = {}
    for section in flow.sections:
        for question in section.questions:
            if not _condition_satisfied(question, running, force_visible=force_visible):
                continue
            value = canonical.get(question.id, question.default or "")
            answers.append(value)
            running[question.id] = value
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
    this groups the ~40-flag surface into operator-meaningful panels
    (basic identity vs. advanced regime questions) instead of one
    undifferentiated wall of flags.
    """
    _flag_name(question)
    try:
        option = _SETUP_OPTION_INFOS[question.id]
    except KeyError as exc:
        raise KeyError(_help_key(flow, question)) from exc
    if section_title is not None:
        # `OptionInfo` carries `rich_help_panel`; setting it groups the
        # flag under the section's panel in Typer's `--help` output.
        option.rich_help_panel = section_title
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


def _run_patch_edit(flow: WizardFlow, explicit_flags: dict[str, str], *, profile_id: str) -> None:
    """Persist a non-interactive ``edit`` as a true patch.

    Only the flags the operator named on the command line are written;
    every other stored field is left untouched. No full-flow walk, no
    ``SetupAnswers`` model construction, no descriptor-default seeding.
    """
    from ..user_profile._orchestration import profile_storage_session
    from ..workflow._persistence import workflow_state_repository
    from ._persistence import persist_patch

    with profile_storage_session(profile_id):
        repository = workflow_state_repository()
        repository.update(lambda state: persist_patch(flow, explicit_flags, state=state))


def _run_full_flow(
    flow: WizardFlow,
    canonical: dict[str, str],
    *,
    _prompter: Prompter | None,
    quiet: bool,
    accept_defaults: bool,
    profile_name: str,
    profile_id: str,
    mode: WizardPersistMode,
    explicit_question_ids: frozenset[str] = frozenset(),
) -> None:
    """Walk the full wizard flow and persist the resulting answer set.

    Used for ``create`` (every path) and for an interactive ``edit``,
    where the operator re-walks and confirms every visible question.

    ``explicit_question_ids`` names the questions whose flag the
    operator supplied on a non-interactive command line. Such a
    question is collected even when its ``visible_when`` gate would
    hide it, so an explicitly-given flag value is always honoured.
    """
    from ..user_profile._orchestration import (
        profile_create_storage_span,
        profile_storage_session,
    )
    from ..workflow._persistence import workflow_state_repository
    from ._persistence import persist_answers

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
            missing_flags = _format_missing_flags(missing)
            raise WizardMissingFlagError(
                translated_message="application.wizard.errors.quiet_missing_flags",
                context={
                    "flow_id": flow.id,
                    "missing": missing,
                    "missing_flags": missing_flags,
                },
            )
        answers = run_flow(
            flow,
            _scripted_from_canonical(flow, canonical, force_visible=explicit_question_ids),
            force_visible=explicit_question_ids,
        )
    elif accept_defaults:
        answers = run_flow(
            flow,
            _scripted_from_canonical(flow, canonical, force_visible=explicit_question_ids),
            force_visible=explicit_question_ids,
        )
    else:
        active = _prompter if _prompter is not None else QuestionaryPrompter()
        try:
            answers = run_flow(flow, active, defaults=canonical)
        except WizardUnsupportedConsoleError as exc:
            # The shared no-console message points at `profile create`,
            # which is correct for `create` but reads as a destructive
            # replacement when an operator hit it via `profile edit`.
            # Re-raise an edit-specific hint that names the
            # non-interactive `profile edit` patch form instead.
            if mode == "edit":
                raise WizardEditUnsupportedConsoleError(
                    translated_message="wizard.errors.unsupported_console_edit",
                    context={"profile_name": profile_name},
                ) from exc
            raise

    # `create` writes the full answer set. An interactive `edit`
    # re-walks every visible question, so the full answer set is the
    # operator's confirmed intent.
    supplied_question_ids = frozenset(question.id for section in flow.sections for question in section.questions)

    span = profile_create_storage_span(profile_id) if mode == "create" else profile_storage_session(profile_id)
    with span as routing_profile_id:
        workflow_state_repository().update(
            lambda state: persist_answers(
                flow,
                answers,
                state=state,
                profile_name=profile_name,
                profile_id=profile_id,
                mode=mode,
                supplied_question_ids=supplied_question_ids,
                routing_profile_id=routing_profile_id if mode == "create" else None,
            ),
        )


def _enter_requested_output_language(kwargs: dict[str, object], language_stack: contextlib.ExitStack) -> None:
    """Apply a command-line output-language override for the command body."""
    from ...core.config import override_settings

    requested_language = kwargs.get("output_language")
    if isinstance(requested_language, str) and requested_language in SUPPORTED_OUTPUT_LANGUAGES:
        language_stack.enter_context(override_settings(aeat_output_language=requested_language))


def _render_error_inside_language_override(exc: AeatError) -> None:
    """Freeze a translated AEAT error message before locale overrides unwind."""
    translated_key = exc.translated_message
    if not isinstance(translated_key, str) or not translated_key:
        return

    context = getattr(exc, "context", None) or {}
    rendered = tr(translated_key, **{key: value for key, value in context.items()})
    exc.args = (rendered, *exc.args[1:])
    exc.translated_message = None


def _require_profile_name(flow: WizardFlow, raw_profile_name: object) -> str:
    """Return a stripped profile name or raise the wizard missing-flag error."""
    if isinstance(raw_profile_name, str) and raw_profile_name.strip():
        return raw_profile_name.strip()
    raise WizardMissingFlagError(
        translated_message="application.wizard.errors.profile_flag_required",
        context={"flow_id": flow.id, "missing": ("profile_name",)},
    )


def _resolve_profile_id_for_mode(flow: WizardFlow, mode: WizardPersistMode, profile_name: str) -> str:
    """Resolve or mint the immutable profile id for the requested wizard mode."""
    from ...domain.user_profile import new_profile_id
    from ..user_profile._orchestration import _refuse_duplicate_label, _require_registered_label
    from ..workflow._profile_bucket_scan import read_profile_bucket

    if mode == "create":
        _refuse_duplicate_label(profile_name)
        return new_profile_id()

    _require_registered_label(profile_name)
    pointer = read_profile_bucket(profile_name)
    if pointer is not None:
        return pointer.bucket_id
    raise WizardMissingFlagError(
        translated_message="application.wizard.errors.profile_flag_required",
        context={"flow_id": flow.id, "missing": ("profile_name",)},
    )


def _seed_output_language_from_environment(canonical: dict[str, str]) -> None:
    """Use AEAT_OUTPUT_LANGUAGE when the operator omitted the explicit flag."""
    from ...core.config import load_settings

    if "output-language" in canonical:
        return

    env_lang = load_settings().aeat_output_language
    if isinstance(env_lang, str) and env_lang in SUPPORTED_OUTPUT_LANGUAGES:
        canonical["output-language"] = env_lang


def _refuse_foral_ccaa(canonical: dict[str, str], explicit_flags: dict[str, str]) -> None:
    """Reject foral CCAA tokens before any persistence or prompt."""
    ccaa_token = canonical.get("tax-residence-ccaa") or explicit_flags.get("tax-residence-ccaa")
    if ccaa_token is None:
        return

    from ...domain.contribuyente import ForalRegimeError, parse_tax_region

    try:
        parse_tax_region(ccaa_token)
    except ForalRegimeError as foral_exc:
        raise typer.BadParameter(
            tr("profile.errors.foral_regime", tax_region=foral_exc.value),
            param_hint="'--tax-residence-ccaa'",
        ) from foral_exc


def _run_wizard_persistence_path(
    flow: WizardFlow,
    mode: WizardPersistMode,
    canonical: dict[str, str],
    explicit_flags: dict[str, str],
    *,
    _prompter: Prompter | None,
    quiet: bool,
    accept_defaults: bool,
    profile_name: str,
    profile_id: str,
) -> None:
    """Dispatch to patch-edit or full-flow persistence."""
    non_interactive = quiet or accept_defaults
    if mode == "edit" and non_interactive:
        _run_patch_edit(flow, explicit_flags, profile_id=profile_id)
        return

    _run_full_flow(
        flow,
        canonical,
        _prompter=_prompter,
        quiet=quiet,
        accept_defaults=accept_defaults,
        profile_name=profile_name,
        profile_id=profile_id,
        mode=mode,
        explicit_question_ids=frozenset(explicit_flags),
    )


def _emit_wizard_success(mode: WizardPersistMode, profile_name: str) -> None:
    """Emit the success payload in JSON or tabular CLI form.

    The post-create / post-edit next-step hint rides on the envelope
    ``notices`` channel (an ``info``-severity :class:`Notice` whose
    ``suggestion`` is the follow-on command) rather than as a bespoke
    ``next`` payload field, so next-step guidance is uniform with every
    other command's notices.
    """
    import typer as _typer

    from ...core.click_context import json_output_requested
    from ...core.json_contract import Notice, NoticeSeverity, emit_json_success
    from ...core.output_rendering import render_command_output

    verb = tr("wizard.commands.status.created" if mode == "create" else "wizard.commands.status.updated")
    next_command = "aeat app modelo work create"
    next_notice = Notice(
        severity=NoticeSeverity.INFO,
        code=f"config.profile.{'create' if mode == 'create' else 'edit'}.next_step",
        message=tr("application.wizard.output_labels.next"),
        suggestion=next_command,
    )
    payload: dict[str, object] = {
        "profile_name": profile_name,
        "status": verb,
    }
    if mode == "create":
        payload["active_profile"] = profile_name
    if json_output_requested():
        command_path = "config.profile.create" if mode == "create" else "config.profile.edit"
        emit_json_success(command_path, payload, notices=[next_notice])
        return

    lines = [
        f"profile\t{profile_name}",
        f"{tr('application.wizard.output_labels.status')}\t{verb}",
    ]
    if mode == "create":
        lines.append(f"active_profile\t{profile_name}")
    lines.append(f"next\t{next_command}")
    rendered = render_command_output(format_name="text", payload=payload, lines=lines)
    _typer.echo(rendered.text)


def _execute_wizard_command(
    flow: WizardFlow,
    mode: WizardPersistMode,
    *,
    _prompter: Prompter | None,
    kwargs: dict[str, object],
) -> None:
    """Run the wizard command body after Typer has parsed dynamic flags."""
    profile_name = _require_profile_name(flow, kwargs.pop("profile_name"))
    profile_id = _resolve_profile_id_for_mode(flow, mode, profile_name)
    quiet = bool(kwargs.pop("quiet", False))
    accept_defaults = bool(kwargs.pop("accept_defaults", False))
    canonical = _collect_flag_values(flow, kwargs)
    explicit_flags: dict[str, str] = dict(canonical)

    _seed_output_language_from_environment(canonical)
    _refuse_foral_ccaa(canonical, explicit_flags)
    _run_wizard_persistence_path(
        flow,
        mode,
        canonical,
        explicit_flags,
        _prompter=_prompter,
        quiet=quiet,
        accept_defaults=accept_defaults,
        profile_name=profile_name,
        profile_id=profile_id,
    )
    _emit_wizard_success(mode, profile_name)


def build_wizard_command(flow: WizardFlow, *, mode: WizardPersistMode) -> Callable[..., None]:
    """Return a Typer-compatible callable that runs ``flow``.

    The returned closure carries one parameter per question in the
    flow (typed and annotated for Typer to derive a CLI flag) plus the
    three mode flags. Tests can pass a custom prompter through the
    keyword-only ``_prompter`` slot (not surfaced as a Typer option).

    ``mode`` binds the closure to a single wizard verb. ``"create"``
    refuses a name that already has a manifest; ``"edit"`` refuses a
    name that has none. Both refusals fire before the wizard prompts,
    so an operator is never walked through 40-odd questions only to
    have the persistence step reject the work.
    """
    question_params = _question_parameters(flow)
    mode_params = _mode_parameters(flow)
    parameters = (*mode_params, *question_params)

    def _command(*, _prompter: Prompter | None = None, **kwargs: object) -> None:
        import contextlib

        from ...core.errors import AeatError

        with contextlib.ExitStack() as _language_stack:
            # When the operator supplies `--output-language` on the
            # command line, that language must drive every operator-
            # facing string this command renders — including a
            # creation-time refusal raised before the profile exists
            # (e.g. a missing `--activity` under `--quiet`). The flag
            # value is already parsed; apply it as a settings override
            # for the whole command body so the error boundary renders
            # in the requested language rather than falling back to the
            # default. The override unwinds when the command returns.
            _enter_requested_output_language(kwargs, _language_stack)
            try:
                _execute_wizard_command(flow, mode, _prompter=_prompter, kwargs=kwargs)
            except AeatError as exc:
                # Pre-render translated_message INSIDE the override so the
                # error boundary's renderer (which runs after the ExitStack
                # unwinds) sees the already-localised string. Without this
                # the override is gone by the time render_error_text fires,
                # and the refusal falls back to the default language.
                _render_error_inside_language_override(exc)
                raise

    # CAST-RATIONALE-WIZARD-COMMAND-INJECT: Typer resolves CLI parameters
    # from ``__signature__`` at decoration time; the cast to ``Any`` is the
    # only way to assign a dynamically-built ``inspect.Signature`` without
    # mypy complaining about the ``Callable`` type being immutable.  The
    # runtime object is always the real ``_command`` function — the cast
    # only widens the static view so the attribute assignments below are
    # accepted by the type checker.
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
