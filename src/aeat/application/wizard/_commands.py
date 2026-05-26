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
from ._persistence import WizardPersistMode
from ._prompter import (
    Prompter,
    QuestionaryPrompter,
    ScriptedPrompter,
    WizardEditUnsupportedConsoleError,
    WizardUnsupportedConsoleError,
)
from ._runner import run_flow


def _ccaa_choice_values() -> list[str]:
    """Return the CCAA choice tokens from the canonical ``CCAA`` enum.

    Derived from the domain enum rather than a hand-kept literal list
    so the ``--tax-residence-ccaa`` choices never drift from the
    autonomous-community catalogue the rest of the domain validates
    against.
    """

    from ...domain.profile._ccaa import CCAA

    return [member.value for member in CCAA]


_CCAA_CHOICE_VALUES: list[str] = _ccaa_choice_values()


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
        click_type=click.Choice(_CCAA_CHOICE_VALUES),
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
        click_type=click.Choice(_ENTITY_TYPE_CHOICE_VALUES),
        help=tr("wizard.setup.flags.entity-type.help"),
    ),
    "legal-entity-form": typer.Option(
        "--legal-entity-form",
        click_type=click.Choice(_LEGAL_ENTITY_FORM_CHOICE_VALUES),
        help=tr("wizard.setup.flags.legal-entity-form.help"),
    ),
    "irpf-income-categories": typer.Option(
        "--irpf-income-categories",
        click_type=click.Choice(_IRPF_INCOME_CATEGORY_CHOICE_VALUES),
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
        click_type=click.Choice(_IRPF_ESTIMATION_REGIME_CHOICE_VALUES),
        help=tr("wizard.setup.flags.irpf-estimation-regime.help"),
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

    from ...adapters.persistence.storage import activate_master_key_provider, get_master_key_provider
    from ..user_profile._orchestration import _write_active_profile_pointer
    from ..workflow._persistence import workflow_state_repository
    from ._persistence import persist_patch

    _write_active_profile_pointer(profile_id)
    provider = get_master_key_provider()
    with activate_master_key_provider(provider, fallback_bucket_id=profile_id):
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

    from ...adapters.persistence.storage import activate_master_key_provider, get_master_key_provider
    from ..user_profile._orchestration import (
        _write_active_profile_pointer,
        capture_active_profile_pointer,
        restore_active_profile_pointer,
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
                tr(
                    "application.wizard.errors.quiet_missing_flags",
                    missing_flags=missing_flags,
                ),
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
                    tr(
                        "wizard.errors.unsupported_console_edit",
                        default=(
                            "The guided setup could not open an interactive "
                            "prompt in this run.\nNothing has been saved yet.\n\n"
                            "Edit this profile non-interactively by naming the "
                            "field to change:\n"
                            f"  aeat config profile edit {profile_name} "
                            "--quiet --<field> VALUE\n\n"
                            "Or re-run the guided edit from an interactive "
                            "terminal session:\n"
                            f"  aeat config profile edit {profile_name}"
                        ),
                        profile_name=profile_name,
                    )
                ) from exc
            raise

    # `create` writes the full answer set. An interactive `edit`
    # re-walks every visible question, so the full answer set is the
    # operator's confirmed intent.
    supplied_question_ids = frozenset(
        question.id for section in flow.sections for question in section.questions
    )

    # Cold-start: the active-profile pointer must aim at the target
    # profile before `workflow_state_repository()` opens its per-bucket
    # engine. For `create`, `ProfileRepository.create` (inside
    # `persist_answers`) owns the cross-store unit of work — bucket
    # directory, manifest, encrypted record, AND the pointer — and
    # rolls every store back on a failure inside the create. The
    # genuine prior pointer is captured here and restored if the
    # surrounding span fails before or around `create` (engine open,
    # master-key activation), the window the repository's own rollback
    # cannot see. For `edit` the profile already has a record, so the
    # pointer write only sets the active profile.
    prior_pointer = capture_active_profile_pointer() if mode == "create" else None
    _write_active_profile_pointer(profile_id)
    try:
        provider = get_master_key_provider()
        with activate_master_key_provider(provider, fallback_bucket_id=profile_id):
            workflow_state_repository().update(
                lambda state: persist_answers(
                    flow,
                    answers,
                    state=state,
                    profile_name=profile_name,
                    profile_id=profile_id,
                    mode=mode,
                    supplied_question_ids=supplied_question_ids,
                )
            )
    except Exception:
        if mode == "create":
            restore_active_profile_pointer(prior_pointer)
        raise


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

        from ...core.config import override_settings
        from ...core.i18n import SUPPORTED_OUTPUT_LANGUAGES

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
            requested_language = kwargs.get("output_language")
            if isinstance(requested_language, str) and requested_language in SUPPORTED_OUTPUT_LANGUAGES:
                _language_stack.enter_context(
                    override_settings(aeat_output_language=requested_language)
                )
            _command_body(_prompter=_prompter, **kwargs)

    def _command_body(*, _prompter: Prompter | None = None, **kwargs: object) -> None:
        from ...domain.user_profile import new_profile_id
        from ..user_profile._orchestration import _refuse_duplicate_label, _require_registered_label
        from ..workflow._profile_bucket_scan import read_profile_bucket

        raw_profile_name = kwargs.pop("profile_name")
        if not isinstance(raw_profile_name, str) or not raw_profile_name.strip():
            raise WizardMissingFlagError(
                tr("application.wizard.errors.profile_flag_required"),
                context={"flow_id": flow.id, "missing": ("profile_name",)},
            )
        profile_name = raw_profile_name.strip()

        # Refuse BEFORE prompting and BEFORE any pointer/engine write.
        # A `create` that targets an existing label, or an `edit` that
        # targets an unknown one, must neither walk the operator
        # through the flow nor switch the active-profile pointer as a
        # side effect. The profile identity is the immutable UUID:
        # `create` mints a fresh one, `edit` resolves the existing
        # profile's UUID from its operator-facing label.
        if mode == "create":
            _refuse_duplicate_label(profile_name)
            profile_id = new_profile_id()
        else:
            _require_registered_label(profile_name)
            pointer = read_profile_bucket(profile_name)
            if pointer is None:
                raise WizardMissingFlagError(
                    tr("application.wizard.errors.profile_flag_required"),
                    context={"flow_id": flow.id, "missing": ("profile_name",)},
                )
            profile_id = pointer.bucket_id

        quiet = bool(kwargs.pop("quiet", False))
        accept_defaults = bool(kwargs.pop("accept_defaults", False))
        canonical = _collect_flag_values(flow, kwargs)

        # The keys present in `canonical` BEFORE any default seeding are
        # exactly the question ids the operator named on the command
        # line. A non-interactive `edit` (`--quiet` / `--accept-
        # defaults`) is a patch: it writes only these explicit flags
        # and leaves every other stored field untouched. It must never
        # be routed through `run_flow`, which constructs the full
        # `SetupAnswers` model and seeds descriptor defaults for the
        # unsupplied questions — the silent full-rewrite that flipped
        # `output_language` while editing an unrelated field.
        explicit_flags: dict[str, str] = dict(canonical)
        non_interactive = quiet or accept_defaults
        patch_edit = mode == "edit" and non_interactive

        if patch_edit:
            _run_patch_edit(flow, explicit_flags, profile_id=profile_id)
        else:
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

        import json as _json

        import typer as _typer

        from ...core.click_context import json_output_requested

        verb = "created" if mode == "create" else "updated"
        payload: dict[str, object] = {
            "profile_name": profile_name,
            "status": verb,
            "next": "aeat app modelo work create",
        }
        # `create` writes the active-profile pointer above, so the new
        # profile is now the active one. Surface that explicitly — the
        # operator otherwise cannot see the silent promotion (the same
        # `active_profile` line `switch` emits).
        if mode == "create":
            payload["active_profile"] = profile_name
        if json_output_requested():
            _typer.echo(_json.dumps(payload, ensure_ascii=False))
        else:
            _typer.echo(f"profile\t{profile_name}")
            _typer.echo(f"status\t{verb}")
            if mode == "create":
                _typer.echo(f"active_profile\t{profile_name}")
            _typer.echo("next\taeat app modelo work create")

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
