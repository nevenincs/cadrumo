"""CLI parameter definitions for wizard commands."""

from __future__ import annotations

import inspect
import typing
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


import click
import typer
import typer._click.types

from ...core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from ...core.i18n.render import tr
from ...core.type_adapters import OBJECT_TUPLE_ADAPTER
from .models import WizardFlow, WizardQuestion, WizardWidget
from .persistence import WizardPersistMode


def _choice(values: list[str], *, case_sensitive: bool = True) -> typer._click.types.ParamType:
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
    return typing.cast("typer._click.types.ParamType", click.Choice(values, case_sensitive=case_sensitive))


def _choice_metavar(values: list[str]) -> str:
    """Render accepted choice tokens for Typer's dynamic-signature help."""
    return "|".join(values)


# Choice values are materialized from the operation-scoped WizardFlow by
# _python_parameter.  Keeping these placeholders empty makes importing the
# command factory safe before any authority operation is leased.
_CCAA_CHOICE_VALUES: list[str] = []
_FISCAL_RESIDENCY_CHOICE_VALUES: list[str] = []
_ENTITY_TYPE_CHOICE_VALUES: list[str] = []
_LEGAL_ENTITY_FORM_CHOICE_VALUES: list[str] = []
_IRPF_INCOME_CATEGORY_CHOICE_VALUES: list[str] = []
_IRPF_ESTIMATION_REGIME_CHOICE_VALUES: list[str] = []
_THIRD_PARTY_DECLARATION_ROLE_CHOICE_VALUES: list[str] = []
_IRPF_SPECIAL_REGIME_CHOICE_VALUES: list[str] = []
_SITUACION_FAMILIAR_CHOICE_VALUES: list[str] = []
IVA_REGIME_CHOICE_VALUES: list[str] = []
_M303_REGIME_COMPOSITION_CHOICE_VALUES: list[str] = []
_M303_TAX_TERRITORY_CHOICE_VALUES: list[str] = []


def flag_name(question: WizardQuestion) -> str:
    """Map a question id to its primary Typer flag name."""
    return f"--{question.id}"


def _help_key(flow: WizardFlow, question: WizardQuestion) -> str:
    """Return the translation key used for the flag's ``--help`` text."""
    return f"wizard.{flow.id}.flags.{question.id}.help"


SETUP_OPTION_INFOS: dict[str, typer.models.OptionInfo | None] = {
    "tax-id": typer.Option("--tax-id", help=tr("wizard.setup.flags.tax-id.help")),
    "name": typer.Option("--name", help=tr("wizard.setup.flags.name.help")),
    "surnames": typer.Option("--surnames", help=tr("wizard.setup.flags.surnames.help")),
    "legal-name": typer.Option("--legal-name", help=tr("wizard.setup.flags.legal-name.help")),
    "activity": typer.Option("--activity", help=tr("wizard.setup.flags.activity.help")),
    "address-postcode": typer.Option("--address-postcode", help=tr("wizard.setup.flags.address-postcode.help")),
    "activity-start-date": typer.Option(
        "--activity-start-date",
        help=tr("wizard.setup.flags.activity-start-date.help"),
    ),
    "taxation-type": typer.Option(
        "--taxation-type",
        click_type=_choice(["1", "2"]),
        metavar=_choice_metavar(["1", "2"]),
        help=tr("wizard.setup.flags.taxation-type.help"),
    ),
    "output-language": typer.Option(
        "--output-language",
        click_type=_choice(list(SUPPORTED_OUTPUT_LANGUAGES)),
        metavar=_choice_metavar(list(SUPPORTED_OUTPUT_LANGUAGES)),
        help=tr("wizard.setup.flags.output-language.help"),
    ),
    "taxpayer-sex": typer.Option(
        "--taxpayer-sex",
        click_type=_choice(["H", "M"]),
        metavar=_choice_metavar(["H", "M"]),
        help=tr("wizard.setup.flags.taxpayer-sex.help"),
    ),
    "taxpayer-marital-status": typer.Option(
        "--taxpayer-marital-status",
        click_type=_choice(["1", "2", "3", "4", "5"]),
        metavar=_choice_metavar(["1", "2", "3", "4", "5"]),
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
        metavar=_choice_metavar(["1", "2", "3", "4"]),
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
        metavar=_choice_metavar(["H", "M"]),
        help=tr("wizard.setup.flags.spouse-sex.help"),
    ),
    "spouse-disability-grade": typer.Option(
        "--spouse-disability-grade",
        click_type=_choice(["1", "2", "3", "4"]),
        metavar=_choice_metavar(["1", "2", "3", "4"]),
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
        click_type=_choice(IVA_REGIME_CHOICE_VALUES, case_sensitive=False),
        metavar=_choice_metavar(IVA_REGIME_CHOICE_VALUES),
        help=tr("wizard.setup.flags.iva-regime.help"),
    ),
    "iva-m303-regime-composition": typer.Option(
        "--iva-m303-regime-composition",
        click_type=_choice(_M303_REGIME_COMPOSITION_CHOICE_VALUES),
        metavar=_choice_metavar(_M303_REGIME_COMPOSITION_CHOICE_VALUES),
        help=tr("wizard.setup.flags.iva-m303-regime-composition.help"),
    ),
    "iva-roi-enrolled": typer.Option(
        "--iva-roi-enrolled/--no-iva-roi-enrolled",
        help=tr("wizard.setup.flags.iva-roi-enrolled.help"),
    ),
    "iva-oss-enrolled": typer.Option(
        "--iva-oss-enrolled/--no-iva-oss-enrolled",
        help=tr("wizard.setup.flags.iva-oss-enrolled.help"),
    ),
    "iva-group-member-enrolled": typer.Option(
        "--iva-group-member-enrolled/--no-iva-group-member-enrolled",
        help=tr("wizard.setup.flags.iva-group-member-enrolled.help"),
    ),
    "iva-group-dominant-entity-enrolled": typer.Option(
        "--iva-group-dominant-entity-enrolled/--no-iva-group-dominant-entity-enrolled",
        help=tr("wizard.setup.flags.iva-group-dominant-entity-enrolled.help"),
    ),
    "iva-intracommunity-operations-exceed-50000-eur": typer.Option(
        "--iva-intracommunity-operations-exceed-50000-eur/--no-iva-intracommunity-operations-exceed-50000-eur",
        help=tr("wizard.setup.flags.iva-intracommunity-operations-exceed-50000-eur.help"),
    ),
    "iva-cash-accounting-regime-enrolled": typer.Option(
        "--iva-cash-accounting-regime-enrolled/--no-iva-cash-accounting-regime-enrolled",
        help=tr("wizard.setup.flags.iva-cash-accounting-regime-enrolled.help"),
    ),
    "iva-voluntary-sii-enrolled": typer.Option(
        "--iva-voluntary-sii-enrolled/--no-iva-voluntary-sii-enrolled",
        help=tr("wizard.setup.flags.iva-voluntary-sii-enrolled.help"),
    ),
    "iva-hydrocarbon-deposit-advance-payment-deduction-entitled": typer.Option(
        "--iva-hydrocarbon-deposit-advance-payment-deduction-entitled/"
        "--no-iva-hydrocarbon-deposit-advance-payment-deduction-entitled",
        help=tr("wizard.setup.flags.iva-hydrocarbon-deposit-advance-payment-deduction-entitled.help"),
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
    "art109-activity-income-withholding-ge-70pct": typer.Option(
        "--art109-activity-income-withholding-ge-70pct/--no-art109-activity-income-withholding-ge-70pct",
        help=tr("wizard.setup.flags.art109-activity-income-withholding-ge-70pct.help"),
    ),
    "pays-rent-with-retencion": typer.Option(
        "--pays-rent-with-retencion/--no-pays-rent-with-retencion",
        help=tr("wizard.setup.flags.pays-rent-with-retencion.help"),
    ),
    "pays-capital-income-with-retencion": typer.Option(
        "--pays-capital-income-with-retencion/--no-pays-capital-income-with-retencion",
        help=tr("wizard.setup.flags.pays-capital-income-with-retencion.help"),
    ),
    "modelo-111-no-retenciones-periods": typer.Option(
        "--modelo-111-no-retenciones-periods",
        help=tr("wizard.setup.flags.modelo-111-no-retenciones-periods.help"),
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
    "monedas-virtuales-extranjero-above-threshold": typer.Option(
        "--monedas-virtuales-extranjero-above-threshold/--no-monedas-virtuales-extranjero-above-threshold",
        help=tr("wizard.setup.flags.monedas-virtuales-extranjero-above-threshold.help"),
    ),
    "premio-loteria-gravamen-especial-sin-retencion": typer.Option(
        "--premio-loteria-gravamen-especial-sin-retencion/--no-premio-loteria-gravamen-especial-sin-retencion",
        help=tr("wizard.setup.flags.premio-loteria-gravamen-especial-sin-retencion.help"),
    ),
    "premio-loteria-gravamen-especial-trimestres": typer.Option(
        "--premio-loteria-gravamen-especial-trimestres",
        help=tr("wizard.setup.flags.premio-loteria-gravamen-especial-trimestres.help"),
    ),
    "fiscal-residency": typer.Option(
        "--fiscal-residency",
        click_type=_choice(_FISCAL_RESIDENCY_CHOICE_VALUES),
        metavar=_choice_metavar(_FISCAL_RESIDENCY_CHOICE_VALUES),
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
        # column tidy; the refusal for an unrecognised value lists the
        # accepted communities instead.
        metavar="CCAA",
        show_choices=False,
        help=tr("wizard.setup.flags.tax-residence-ccaa.help"),
    ),
    "tax-residence-jurisdiction-scope": typer.Option(
        "--tax-residence-jurisdiction-scope",
        click_type=_choice(_M303_TAX_TERRITORY_CHOICE_VALUES),
        metavar=_choice_metavar(_M303_TAX_TERRITORY_CHOICE_VALUES),
        help=tr("wizard.setup.flags.tax-residence-jurisdiction-scope.help"),
    ),
    "cloud-evidence-upload": typer.Option(
        "--cloud-evidence-upload/--no-cloud-evidence-upload",
        help=tr("wizard.setup.flags.cloud-evidence-upload.help"),
    ),
    "llm-vision": typer.Option(
        "--llm-vision/--no-llm-vision",
        help=tr("wizard.setup.flags.llm-vision.help"),
    ),
    "google-export": typer.Option(
        "--google-export/--no-google-export",
        help=tr("wizard.setup.flags.google-export.help"),
    ),
    "entity-type": typer.Option(
        "--entity-type",
        click_type=_choice(_ENTITY_TYPE_CHOICE_VALUES),
        metavar=_choice_metavar(_ENTITY_TYPE_CHOICE_VALUES),
        help=tr("wizard.setup.flags.entity-type.help"),
    ),
    "legal-entity-form": typer.Option(
        "--legal-entity-form",
        click_type=_choice(_LEGAL_ENTITY_FORM_CHOICE_VALUES),
        metavar=_choice_metavar(_LEGAL_ENTITY_FORM_CHOICE_VALUES),
        help=tr("wizard.setup.flags.legal-entity-form.help"),
    ),
    "irpf-income-categories": typer.Option(
        "--irpf-income-categories",
        click_type=_choice(_IRPF_INCOME_CATEGORY_CHOICE_VALUES),
        metavar=_choice_metavar(_IRPF_INCOME_CATEGORY_CHOICE_VALUES),
        help=tr("wizard.setup.flags.irpf-income-categories.help"),
    ),
    "declaration-roles": typer.Option(
        "--declaration-roles",
        click_type=_choice(_THIRD_PARTY_DECLARATION_ROLE_CHOICE_VALUES),
        metavar=_choice_metavar(_THIRD_PARTY_DECLARATION_ROLE_CHOICE_VALUES),
        help=tr("wizard.setup.flags.declaration-roles.help"),
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
        metavar=_choice_metavar(_IRPF_ESTIMATION_REGIME_CHOICE_VALUES),
        help=tr("wizard.setup.flags.irpf-estimation-regime.help"),
    ),
    "irpf-special-regime": typer.Option(
        "--irpf-special-regime",
        click_type=_choice(_IRPF_SPECIAL_REGIME_CHOICE_VALUES),
        metavar=_choice_metavar(_IRPF_SPECIAL_REGIME_CHOICE_VALUES),
        help=tr("wizard.setup.flags.irpf-special-regime.help"),
    ),
    "irpf-special-regime-start-date": typer.Option(
        "--irpf-special-regime-start-date",
        help=tr("wizard.setup.flags.irpf-special-regime-start-date.help"),
    ),
    "situacion-familiar": typer.Option(
        "--situacion-familiar",
        click_type=_choice(_SITUACION_FAMILIAR_CHOICE_VALUES),
        metavar=_choice_metavar(_SITUACION_FAMILIAR_CHOICE_VALUES),
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

# This mapping is the operator-facing wizard vocabulary used by application
# refusals to name flags the CLI can actually parse.


def required_flag_questions(flow: WizardFlow) -> tuple[WizardQuestion, ...]:
    """Return the questions whose value must be supplied in ``--quiet`` mode."""
    return tuple(
        question
        for section in flow.sections
        for question in section.questions
        if question.required and question.visible_when is None
    )


def canonical_from_flag_value(question: WizardQuestion, value: object) -> str | None:
    """Project a Typer-parsed flag value into the canonical-token form."""
    if value is None:
        return None
    if question.widget is WizardWidget.CONFIRM:
        return _canonical_confirm_value(value)
    if question.widget is WizardWidget.CHECKBOX:
        return _canonical_checkbox_value(value)
    if question.widget is WizardWidget.INTEGER:
        return _canonical_integer_value(value)
    if question.widget is WizardWidget.PATH:
        return str(value)
    return str(value)


def _canonical_confirm_value(value: object) -> str | None:
    """Project a boolean flag into the flow's lowercase canonical token."""
    if not isinstance(value, bool):
        return None
    return "true" if value else "false"


def _canonical_checkbox_value(value: object) -> str | None:
    """Project repeated checkbox values into one comma-separated token."""
    if not isinstance(value, list | tuple):
        return None
    tokens = [str(item) for item in OBJECT_TUPLE_ADAPTER.validate_python(value) if str(item)]
    return ",".join(tokens) if tokens else None


def _canonical_integer_value(value: object) -> str:
    """Project an integer flag while retaining Typer's accepted coercions."""
    if isinstance(value, int):
        return str(value)
    return str(int(str(value)))


def _configure_select_option(
    question: WizardQuestion,
    operation: PinnedAuthorityOperation,
    option: typer.models.OptionInfo,
) -> None:
    """Apply registry choices and reviewed help overrides for selects."""
    if question.widget is not WizardWidget.SELECT:
        return
    values = [choice.value for choice in question.choices]
    if question.id == "tax-residence-ccaa":
        # Foral tokens stay selectable so the refusal can redirect the
        # operator to the foral Hacienda instead of a generic choice error.
        from ...domain.calculations.registry.ccaa_catalogue import resolve_ccaa_catalogue

        values.extend(resolve_ccaa_catalogue(authority=operation).foral_cli_aliases)
    option.click_type = _choice(values, case_sensitive=question.id != "iva-regime")
    option.metavar = _choice_metavar(values)
    if question.id == "situacion-familiar":
        # Keep the closed input protocol visible at the boundary while using
        # the direct catalogue translation for operator-facing help.
        option.help = tr("wizard.setup.flags.situacion-familiar.help")
    if question.id == "tax-residence-ccaa":
        option.metavar = "CCAA"
        option.show_choices = False
        option.help = tr("wizard.setup.flags.tax-residence-ccaa.help")


def _parameter_annotation_default(
    question: WizardQuestion,
    option: typer.models.OptionInfo,
) -> tuple[object, object]:
    """Derive the exact Typer annotation and default for one wizard widget."""
    match question.widget:
        case WizardWidget.CONFIRM:
            return Annotated[bool | None, option], None
        case WizardWidget.SELECT:
            return Annotated[str | None, option], None
        case WizardWidget.CHECKBOX:
            return Annotated[list[str], option], []
        case WizardWidget.INTEGER:
            return Annotated[int | None, option], None
        case WizardWidget.PATH:
            return Annotated[Path | None, option], None
        case WizardWidget.SECRET:
            return Annotated[str | None, option], None
        case WizardWidget.TEXT:
            return Annotated[str | None, option], None


def _python_parameter(
    flow: WizardFlow,
    question: WizardQuestion,
    *,
    operation: PinnedAuthorityOperation,
    section_title: str | None = None,
) -> inspect.Parameter:
    """Build the ``inspect.Parameter`` Typer reads to register a flag.

    ``section_title`` becomes the ``rich_help_panel`` so Typer renders
    each ``WizardSection`` as its own group in the ``--help`` output;
    this groups the ~40-flag surface into operator-meaningful panels
    (basic identity vs. advanced regime questions) instead of one
    undifferentiated wall of flags.
    """
    flag_name(question)
    option = SETUP_OPTION_INFOS.get(question.id)
    if option is None:
        option = typer.Option(flag_name(question), help=tr(_help_key(flow, question)))
        SETUP_OPTION_INFOS[question.id] = option
    _configure_select_option(question, operation, option)
    if section_title is not None:
        # `OptionInfo` carries `rich_help_panel`; setting it groups the
        # flag under the section's panel in Typer's `--help` output.
        option.rich_help_panel = section_title
    annotation, default = _parameter_annotation_default(question, option)
    return inspect.Parameter(
        name=question.id.replace("-", "_"),
        kind=inspect.Parameter.KEYWORD_ONLY,
        default=default,
        annotation=annotation,
    )


def mode_parameters(flow: WizardFlow, *, mode: WizardPersistMode) -> tuple[inspect.Parameter, ...]:
    """Build the callback context, profile-name, and fixed mode-flag parameters.

    The name is optional at parse time for both verbs. The interactive create
    screen can collect it, while an unnamed edit addresses the authenticated
    active profile. The programmatic create path still applies
    ``_require_profile_name`` after dispatch, so headless create retains its
    typed missing-name refusal. The injected ``ctx`` is part of the callback
    contract rather than a profile field: the CLI frontend seam needs it to
    emit the manager's closing envelope after the screen returns.
    """
    del flow
    ctx = inspect.Parameter(
        name="ctx",
        kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
        annotation=typer.Context,
    )
    profile_name_default: object = None
    profile_name_argument = typer.Argument(
        ...,
        help=tr("cli.config.setup.profile_name_help"),
    )
    profile_name_annotation = Annotated[str | None, profile_name_argument]
    profile_name = inspect.Parameter(
        name="profile_name",
        kind=inspect.Parameter.KEYWORD_ONLY,
        default=profile_name_default,
        annotation=profile_name_annotation,
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
    return (ctx, profile_name, quiet, accept_defaults)


def question_parameters(flow: WizardFlow, *, operation: PinnedAuthorityOperation) -> tuple[inspect.Parameter, ...]:
    """Build one ``inspect.Parameter`` per descriptor question.

    Each question's ``rich_help_panel`` is the section's translated
    title so the profile-create command's help renders one panel per
    :class:`WizardSection`.
    """
    parameters: list[inspect.Parameter] = []
    for section in flow.sections:
        section_title = tr(str(section.title))
        for question in section.questions:
            parameters.append(_python_parameter(flow, question, operation=operation, section_title=section_title))
    return tuple(parameters)


def wizard_command_metadata(
    parameters: tuple[inspect.Parameter, ...],
) -> tuple[inspect.Signature, dict[str, object]]:
    """Build the public signature and annotation map for a wizard callback.

    The callback is assembled at runtime because each flow contributes a
    different set of flags.  Keep the ``inspect.Signature`` and the function's
    annotation mapping derived from the same canonical parameter objects: a
    future change in how Python stores annotations must not make Typer inspect
    one representation while ``typing.get_type_hints`` sees another.  The
    public ``inspect.Parameter.annotation`` sentinel is deliberately retained
    for an unannotated parameter rather than importing any private ``inspect``
    or ``typing`` implementation detail.
    """
    signature = inspect.Signature(parameters=parameters)
    annotations: dict[str, object] = {
        parameter.name: parameter.annotation
        for parameter in signature.parameters.values()
        if parameter.annotation is not inspect.Parameter.empty
    }
    return signature, annotations
