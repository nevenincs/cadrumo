"""Typer command factory for wizard flows.

``build_wizard_command(flow)`` returns a Typer-compatible callable
whose signature is composed at construction time from the flow's
questions plus three fixed mode flags (``--profile``,
``--quiet``, ``--accept-defaults``). The closure runs the flow and
persists the typed answers.

Flag derivation per question kind:

* ``TEXT`` / ``SECRET`` / ``PATH`` → ``--<question-id>`` ``str``
  option (``Path`` for ``PATH``);
* ``INTEGER`` → ``--<question-id>`` ``int`` option;
* ``CONFIRM`` → ``--<question-id>/--no-<question-id>`` boolean pair;
* ``SELECT`` → ``--<question-id>`` option with
  ``click.Choice([c.value for c in choices])``;
* ``CHECKBOX`` → repeated ``--<question-id>`` option that accumulates
  a ``list[str]``.

An interactive walk projects the one-shot wizard catalogue into a
substrate :class:`~cadrumo.application.flows.definition.FlowDefinition`
(via :func:`~cadrumo.application.flows.wizard_projection.flow_definition_from_wizard_flow`)
and drives it through an injected frontend runner: the full-screen
Textual frontend where the host supports it, degrading to the line-mode
frontend otherwise, and refusing instructively on a non-interactive
host. The application default renders the line frontend (a same-layer
``application.flows`` primitive); the CLI entrypoint injects the
capability-selecting runner that reaches the full-screen inbound adapter.
The committed answers are then replayed through the same scripted
projection the ``--quiet`` / ``--accept-defaults`` paths use, so the
persisted typed model is produced identically regardless of frontend.
"""

from __future__ import annotations

import inspect
import typing
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

if TYPE_CHECKING:
    from ...core.errors.hierarchy import CadrumoError
    from ...core.json_contract import Notice, ResolvedNoticeAction
    from ...domain.user_profile.values import UserProfileFact
    from .results import ConfigProfileCreateResult, ConfigProfileEditResult

import contextlib

import click
import typer
import typer._click.types
from pydantic import BaseModel, ValidationError
from pydantic_core import ErrorDetails

from ...core.flows import CheckpointAvailability, FlowMode
from ...core.i18n import SUPPORTED_OUTPUT_LANGUAGES, tr
from ...core.modelo import Modelo
from ...core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ...core.type_adapters import OBJECT_TUPLE_ADAPTER, STR_KEYED_MAPPING_ADAPTER
from ..flows.definition import FlowDefinition, FlowPage, FlowSection
from ..flows.engine import start_flow, visible_sequence
from ..flows.errors import FlowAnswerError, FlowSubmitError
from ..flows.scripted import run_scripted_flow
from ..flows.wizard_projection import flow_definition_from_wizard_flow
from ._format_hints import attach_format_hints
from .catalogue import SETUP_FLOW
from .descendant_group import attach_descendant_group
from .errors import (
    WizardEditUnsupportedConsoleError,
    WizardMissingFlagError,
    WizardPreconditionCondition,
    WizardUnsupportedConsoleError,
    WizardValidationError,
    wizard_no_action_verdict,
)
from .models import WizardFlow, WizardQuestion, WizardWidget
from .persistence import WizardPersistMode
from .setup_legal_validators import attach_setup_legal_validators


def _translation_context(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    return STR_KEYED_MAPPING_ADAPTER.validate_python(value)


#: Which substrate :class:`FlowMode` each wizard verb drives. ``create``
#: registers a fresh profile, ``edit`` modifies an existing one.
_FLOW_MODE_BY_WIZARD_MODE: dict[WizardPersistMode, FlowMode] = {
    "create": FlowMode.CREATE,
    "edit": FlowMode.MODIFY,
}

#: Neither setup mode offers a checkpoint.  Credential registration owns
#: profile creation, and profile edits must never leave a half-applied fact
#: set behind.
_SETUP_CHECKPOINT: dict[FlowMode, CheckpointAvailability] = {
    FlowMode.CREATE: CheckpointAvailability.UNAVAILABLE,
    FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
}


# KWARGS-RATIONALE-flow-runner: keyword-only frontend seam injected by the caller.


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


def _ccaa_choice_values() -> list[str]:
    """Return the CCAA choice tokens accepted by ``--tax-residence-ccaa``.

    The list includes all 15 common-regime values from the ``CCAA`` enum
    plus the two foral-regime tokens (``pais_vasco``, ``navarra``).  The
    foral tokens are accepted by Click so the operator receives a
    localised redirect rather than a generic "not one of" error, but they
    are refused by the wizard persistence layer via ``ForalRegimeError``.
    """
    from ...domain.contribuyente.ccaa import CCAA

    common = [member.value for member in CCAA]
    foral = ["pais_vasco", "navarra"]
    return common + foral


_CCAA_CHOICE_VALUES: list[str] = _ccaa_choice_values()


def _fiscal_residency_choice_values() -> list[str]:
    """Return the FiscalResidency choice tokens accepted by ``--fiscal-residency``."""
    from ...domain.deadlines.models import FiscalResidency

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
    from ...domain.deadlines.models import EntityType, IrpfEstimationRegime, IrpfIncomeCategory, LegalEntityForm

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


def _third_party_declaration_role_choice_values() -> list[str]:
    """Return choice tokens for the Modelo 347 declaring-role enum.

    Derived from :class:`ThirdPartyDeclarationRole` so the
    ``--declaration-roles`` flag choices never drift from the
    values the wizard catalogue and the profile schema validate against.
    """
    from ...core.aggregation import ThirdPartyDeclarationRole

    return [member.value for member in ThirdPartyDeclarationRole]


_THIRD_PARTY_DECLARATION_ROLE_CHOICE_VALUES: list[str] = _third_party_declaration_role_choice_values()


def _irpf_personal_choice_values() -> tuple[list[str], list[str]]:
    """Return choice tokens for IRPF-personal enums.

    Derived from the canonical domain enums (``IrpfSpecialRegime``,
    ``SituacionFamiliar``) so the ``--irpf-special-regime`` and
    ``--situacion-familiar`` flag choices never drift from the values
    the wizard catalogue and the profile schema validate against.
    """
    from ...domain.contribuyente.renta_codes import SituacionFamiliar
    from ...domain.deadlines.models import IrpfSpecialRegime

    return (
        [member.value for member in IrpfSpecialRegime],
        [member.value for member in SituacionFamiliar],
    )


(
    _IRPF_SPECIAL_REGIME_CHOICE_VALUES,
    _SITUACION_FAMILIAR_CHOICE_VALUES,
) = _irpf_personal_choice_values()


def _setup_choice_values(question_id: str) -> list[str]:
    """Return the canonical choice tokens declared for one setup question."""
    for section in SETUP_FLOW.sections:
        for question in section.questions:
            if question.id == question_id:
                return [choice.value for choice in question.choices]
    raise RuntimeError(f"SETUP_FLOW is missing the {question_id} question")


_IVA_REGIME_CHOICE_VALUES: list[str] = _setup_choice_values("iva-regime")
_M303_REGIME_COMPOSITION_CHOICE_VALUES: list[str] = _setup_choice_values("iva-m303-regime-composition")
_M303_TAX_TERRITORY_CHOICE_VALUES: list[str] = _setup_choice_values("tax-residence-jurisdiction-scope")


def _flag_name(question: WizardQuestion) -> str:
    """Map a question id to its primary Typer flag name."""
    return f"--{question.id}"


def _help_key(flow: WizardFlow, question: WizardQuestion) -> str:
    """Return the translation key used for the flag's ``--help`` text."""
    return f"wizard.{flow.id}.flags.{question.id}.help"


_SETUP_OPTION_INFOS: dict[str, typer.models.OptionInfo] = {
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
    "charge-iban": typer.Option(
        "--charge-iban",
        help=tr("wizard.setup.flags.charge-iban.help"),
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
        click_type=_choice(_IVA_REGIME_CHOICE_VALUES, case_sensitive=False),
        metavar=_choice_metavar(_IVA_REGIME_CHOICE_VALUES),
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
    "professional-income-withholding-ge-70pct": typer.Option(
        "--professional-income-withholding-ge-70pct/--no-professional-income-withholding-ge-70pct",
        help=tr("wizard.setup.flags.professional-income-withholding-ge-70pct.help"),
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
        # column tidy; the choice values are listed in the help text,
        # where they wrap on commas / word boundaries.
        metavar="CCAA",
        show_choices=False,
        help=tr(
            "wizard.setup.flags.tax-residence-ccaa.help",
            choices=", ".join(_CCAA_CHOICE_VALUES),
        ),
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
    "notes": typer.Option("--notes", help=tr("wizard.setup.flags.notes.help")),
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
    "ley-49-2002-option-declared": typer.Option(
        "--ley-49-2002-option-declared/--no-ley-49-2002-option-declared",
        help=tr("wizard.setup.flags.ley-49-2002-option-declared.help"),
    ),
    "ley-49-2002-option-date": typer.Option(
        "--ley-49-2002-option-date",
        help=tr("wizard.setup.flags.ley-49-2002-option-date.help"),
    ),
    "ley-49-2002-renunciation-declared": typer.Option(
        "--ley-49-2002-renunciation-declared/--no-ley-49-2002-renunciation-declared",
        help=tr("wizard.setup.flags.ley-49-2002-renunciation-declared.help"),
    ),
    "ley-49-2002-renunciation-date": typer.Option(
        "--ley-49-2002-renunciation-date",
        help=tr("wizard.setup.flags.ley-49-2002-renunciation-date.help"),
    ),
    "irpf-estimation-regime": typer.Option(
        "--irpf-estimation-regime",
        click_type=_choice(_IRPF_ESTIMATION_REGIME_CHOICE_VALUES),
        metavar=_choice_metavar(_IRPF_ESTIMATION_REGIME_CHOICE_VALUES),
        help=tr("wizard.setup.flags.irpf-estimation-regime.help"),
    ),
    "objective-estimation-modulos-iae-epigraph": typer.Option(
        "--objective-estimation-modulos-iae-epigraph",
        help=tr("wizard.setup.flags.objective-estimation-modulos-iae-epigraph.help"),
    ),
    "objective-estimation-modulos-module-1-units": typer.Option(
        "--objective-estimation-modulos-module-1-units",
        help=tr("wizard.setup.flags.objective-estimation-modulos-module-1-units.help"),
    ),
    "objective-estimation-modulos-module-2-units": typer.Option(
        "--objective-estimation-modulos-module-2-units",
        help=tr("wizard.setup.flags.objective-estimation-modulos-module-2-units.help"),
    ),
    "objective-estimation-modulos-module-3-units": typer.Option(
        "--objective-estimation-modulos-module-3-units",
        help=tr("wizard.setup.flags.objective-estimation-modulos-module-3-units.help"),
    ),
    "objective-estimation-modulos-module-4-units": typer.Option(
        "--objective-estimation-modulos-module-4-units",
        help=tr("wizard.setup.flags.objective-estimation-modulos-module-4-units.help"),
    ),
    "objective-estimation-modulos-module-5-units": typer.Option(
        "--objective-estimation-modulos-module-5-units",
        help=tr("wizard.setup.flags.objective-estimation-modulos-module-5-units.help"),
    ),
    "objective-estimation-modulos-module-6-units": typer.Option(
        "--objective-estimation-modulos-module-6-units",
        help=tr("wizard.setup.flags.objective-estimation-modulos-module-6-units.help"),
    ),
    "objective-estimation-modulos-module-7-units": typer.Option(
        "--objective-estimation-modulos-module-7-units",
        help=tr("wizard.setup.flags.objective-estimation-modulos-module-7-units.help"),
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
SETUP_OPTION_INFOS = _SETUP_OPTION_INFOS

# Guard against future catalogue / dict drift: every question id that
# the SETUP_FLOW catalogue exposes must have a matching OptionInfo entry.
# This assert fires at import time so a missing entry is discovered
# immediately rather than as a runtime KeyError buried inside a Typer
# command factory call.
_SETUP_CATALOGUE_IDS: frozenset[str] = frozenset(
    question.id for section in SETUP_FLOW.sections for question in section.questions
)
_missing_option_infos = _SETUP_CATALOGUE_IDS - frozenset(_SETUP_OPTION_INFOS)
if _missing_option_infos:  # pragma: no cover - option-coverage invariant
    raise ValueError(
        f"_SETUP_OPTION_INFOS is missing entries for catalogue question ids: "
        f"{sorted(_missing_option_infos)!r}. "
        "Add a typer.Option entry for each missing id.",
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


def _missing_filing_baseline_flags(flow: WizardFlow, answers: BaseModel) -> tuple[str, ...]:
    """Return filing identity facts that must exist before persistence.

    Wizard answer models can carry partial values while prompts are being
    collected or projected. Persisted create and edit operations are stricter:
    they must leave a taxpayer-type axis and a filing identity, otherwise
    modelo work would fail later against an already-committed profile.
    """
    from ..user_profile.filing_baseline import missing_filing_baseline_flags as _missing_profile_filing_baseline_flags
    from .persistence import serialise_answers

    return _missing_profile_filing_baseline_flags(serialise_answers(flow, answers))


def _require_filing_baseline(flow: WizardFlow, answers: BaseModel) -> None:
    """Refuse a wizard write whose projected answers lack the filing baseline.

    Both the non-interactive patch and full-flow persistence paths reach this
    single terminal-precondition owner after composing their candidate answer
    set and before publishing any profile facts.
    """
    missing = _missing_filing_baseline_flags(flow, answers)
    if not missing:
        return
    raise WizardMissingFlagError(
        translated_message="application.wizard.errors.edit_missing_filing_baseline",
        context={
            "flow_id": flow.id,
            "missing": missing,
            "missing_flags": _format_missing_flags(missing),
        },
        precondition_verdict=wizard_no_action_verdict(
            condition=WizardPreconditionCondition.FILING_BASELINE_COMPLETE,
            facts={
                "filing_baseline_complete": False,
                "missing_flag_count": len(missing),
            },
            provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        ),
    )


def setup_flow_definition(
    flow: WizardFlow,
    *,
    attach_descendants: bool = True,
) -> FlowDefinition:
    """Bridge and decorate the wizard flow into the shared substrate definition.

    The single projected :class:`FlowDefinition` every frontend drives:
    the substrate bridge, format hints, setup legal validators, and -- for
    CREATE -- the descendant repeating group, applied in one place so no
    caller can diverge on the definition it runs.

    ``attach_descendants`` gates the descendant group. It is spliced for
    CREATE (where the facts-as-checkpoint store seeds and re-seeds the group)
    and withheld for MODIFY. Modify-mode seeding cannot instantiate the
    repeating group: the modify frontend seeds render-time page defaults over
    a fresh :func:`~cadrumo.application.flows.engine.start_flow` state, and instance
    pages are generated dynamically from the group's count rather than being
    static items the default-seed mechanism can reach. Rendering the group
    unseeded would show an operator's existing descendants as an empty group
    whose commit -- via the namespace-replacing clearing guard -- would then
    silently erase them. So MODIFY withholds the group and the command
    surfaces the descendant door instead of a silently-lossy surface.

    """
    definition = attach_setup_legal_validators(
        attach_format_hints(flow_definition_from_wizard_flow(flow, checkpoint=_SETUP_CHECKPOINT)),
    )
    if attach_descendants:
        definition = attach_descendant_group(definition)
    return definition


def _force_pages_visible(definition: FlowDefinition, page_ids: frozenset[str]) -> FlowDefinition:
    """Project the named pages as unconditionally visible for one scripted walk.

    An explicitly-supplied flag is an unambiguous declaration of intent, so
    its gated question must be collected even when its ``visible_when`` gate
    would otherwise hide it. Stripping the gate on exactly the named pages
    reproduces the retired runner's ``force_visible`` law: the scripted
    driver then walks and demands the page like any other visible one, while
    every other gate keeps governing prompting normally.
    """
    if not page_ids:
        return definition
    new_sections: list[FlowSection] = []
    for section in definition.sections:
        new_items = tuple(
            item.model_copy(update={"visible_when": None})
            if isinstance(item, FlowPage) and item.id in page_ids and item.visible_when is not None
            else item
            for item in section.items
        )
        new_sections.append(section.model_copy(update={"items": new_items}))
    return definition.model_copy(update={"sections": tuple(new_sections)})


def _project_scripted_answers(
    definition: FlowDefinition,
    canonical: Mapping[str, str],
    *,
    mode: FlowMode,
) -> tuple[list[str], dict[str, str]]:
    """Project the canonical dict into the driver's visible-sequence order.

    :func:`~cadrumo.application.flows.scripted.run_scripted_flow` consumes an ordered
    queue, one token per visible page, re-evaluating visibility after each
    commit. This mirrors that walk over the DEFINITION (so a substrate-only
    page keeps its true walk position) and emits each page's canonical token,
    or its descriptor default / blank when the operator supplied none, so the
    positional queue stays aligned with every gate the driver will observe.

    Returns the ordered token queue plus the same tokens keyed by page id —
    the intended answer set, used to re-derive the wizard's localized
    refusal when the substrate rejects an answer or blocks submission.
    """
    base = start_flow(definition, mode=mode)
    answers: dict[str, str] = {}
    tokens: list[str] = []
    while True:
        target = next(
            (
                entry
                for entry in visible_sequence(definition, base.model_copy(update={"answers": dict(answers)}))
                if entry.key not in answers
            ),
            None,
        )
        if target is None:
            return tokens, answers
        raw = canonical.get(target.key, target.page.default or "")
        tokens.append(raw)
        answers[target.key] = raw


def _answers_model_from_canonical(flow: WizardFlow, committed: Mapping[str, str]) -> BaseModel:
    """Coerce a page-keyed committed-answer map into the typed answers model.

    Every visible page commits during a walk (even blank), so a question the
    walk visited carries a key in ``committed`` and a gate-hidden question is
    absent. Each present answer is re-validated through its widget validator
    and parsed into the declared answer type — the exact projection the
    retired runner applied post-walk — so the persisted typed model is
    produced identically regardless of the frontend (scripted, line, or
    full-screen) that produced ``committed``.
    """
    from .persistence import parse_canonical
    from .widgets import validate_widget_answer

    typed: dict[str, object] = {}
    for section in flow.sections:
        for question in section.questions:
            if question.id not in committed:
                continue
            validated = validate_widget_answer(question, committed[question.id])
            typed[question.id.replace("-", "_")] = parse_canonical(question, validated)
    return flow.answers_model.model_validate(typed)


def _run_scripted_walk(
    flow: WizardFlow,
    canonical: dict[str, str],
    *,
    mode: WizardPersistMode,
    explicit_question_ids: frozenset[str],
) -> BaseModel:
    """Drive a non-interactive walk through the shared flow substrate.

    Builds the same projected definition the interactive frontends drive,
    forces every explicitly-supplied gated question visible for this walk,
    projects the canonical dict into the driver's visible-sequence token
    order, and runs the scripted intent driver. The committed answers are
    then coerced through the one projection every frontend shares, so a
    non-interactive create is answer-for-answer identical to an interactive
    one.

    The substrate is the sole authority for the persisted answers (parity
    with the interactive frontends). A substrate refusal — a rejected answer
    or a blocked submission — is re-surfaced through the wizard's own
    localized answer-model validation so the operator still reads the precise
    flag-named date / decimal / cross-field message, not the substrate's
    generic verdict. That fallback only ever raises; if the model unexpectedly
    validates, the substrate refusal stands.
    """
    flow_mode = _FLOW_MODE_BY_WIZARD_MODE[mode]
    definition = _force_pages_visible(
        setup_flow_definition(flow, attach_descendants=mode == "create"),
        explicit_question_ids,
    )
    tokens, intended = _project_scripted_answers(definition, canonical, mode=flow_mode)
    defaults = {
        question.id: question.default or ""
        for section in flow.sections
        for question in section.questions
        if question.default is not None
    }
    try:
        state, _projection = run_scripted_flow(definition, tokens, mode=flow_mode, defaults=defaults)
    except (FlowAnswerError, FlowSubmitError):
        _answers_model_from_canonical(flow, intended)
        raise
    return _answers_model_from_canonical(flow, dict(state.answers))


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
        tokens = [str(item) for item in OBJECT_TUPLE_ADAPTER.validate_python(value) if str(item)]
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


def _mode_parameters(flow: WizardFlow, *, mode: WizardPersistMode) -> tuple[inspect.Parameter, ...]:
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


def _question_parameters(flow: WizardFlow) -> tuple[inspect.Parameter, ...]:
    """Build one ``inspect.Parameter`` per descriptor question.

    Each question's ``rich_help_panel`` is the section's translated
    title so the profile-create command's help renders one panel per
    :class:`WizardSection`.
    """
    parameters: list[inspect.Parameter] = []
    for section in flow.sections:
        section_title = tr(str(section.title))
        for question in section.questions:
            parameters.append(_python_parameter(flow, question, section_title=section_title))
    return tuple(parameters)


def _wizard_command_metadata(
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
    annotations = {
        parameter.name: parameter.annotation
        for parameter in signature.parameters.values()
        if parameter.annotation is not inspect.Parameter.empty
    }
    return signature, annotations


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


def scripted_profile_facts(
    flow: WizardFlow,
    kwargs: Mapping[str, object],
) -> tuple[UserProfileFact, ...]:
    """Project a scripted ``create``'s field flags into initial profile facts.

    Creation is the credential door's authority, not this flow's: a profile
    exists only once a passphrase has wrapped its DEK. That leaves the field
    flags of a scripted ``config profile create`` with nowhere to land, because
    the flow's own create arm is retired and its patch arm is bound to ``edit``
    and to an already-authenticated session. This is the seam between the two.
    The projection is deliberately PURE -- it writes nothing and opens no
    session, so the caller hands the result to the registration door and the
    facts are published inside the create transaction that already holds the
    record session, rather than through a second unlock afterwards.

    A refused value refuses HERE, before the caller registers anything, so a
    foral CCAA token costs the operator no profile to correct afterwards.

    The foral check is not redundant with the question validators. Dropping it
    does still refuse -- the widget validator behind the CCAA question raises
    too -- but it refuses as a generic wizard-validation failure instead of the
    domain refusal that names the Concierto Económico and the foral tax office
    the operator actually has to file with. The flow's own command body calls
    it for the same reason. It runs first so the good message wins.

    No filing-baseline check applies. A profile created this way is born
    ``INCOMPLETE`` on purpose, so demanding the full filing baseline would
    refuse the very state the create door exists to produce.

    Args:
        flow: The setup flow whose questions name the accepted flags.
        kwargs: The verb's parsed keyword arguments, keyed by parameter name.

    Returns:
        The supplied flags as facts, empty when the caller named none.
    """
    from ...domain.user_profile.values import UserProfileFact
    from .persistence import profile_values_from_patch

    canonical = _collect_flag_values(flow, dict(kwargs))
    _refuse_foral_ccaa(canonical, canonical)
    if not canonical:
        return ()
    return tuple(
        UserProfileFact(path=path, value=value) for path, value in profile_values_from_patch(flow, canonical).items()
    )


def _run_patch_edit(flow: WizardFlow, explicit_flags: dict[str, str], *, profile_id: str) -> dict[str, str]:
    """Persist a non-interactive ``edit`` as a true patch.

    Only the flags the operator named on the command line are written;
    every other stored field is left untouched. No full-flow walk, no
    ``SetupAnswers`` model construction, no descriptor-default seeding.
    """
    from ...domain.user_profile.values import UserProfileFact
    from ..user_profile.fact_write import ProfileFactWriteDoor, apply_profile_fact_changes
    from ..user_profile.profile_record_repository import ProfileRecordRepository
    from ..user_profile.projections import record_to_path_values
    from .persistence import (
        profile_values_from_patch,
        project_answers,
    )

    patched_values = profile_values_from_patch(flow, explicit_flags)
    record = ProfileRecordRepository.for_current_session(profile_id).load(profile_id)
    merged_values = record_to_path_values(record)
    merged_values.update(patched_values)
    _require_filing_baseline(flow, project_answers(flow, merged_values))
    apply_profile_fact_changes(
        profile_id=profile_id,
        changes=tuple(UserProfileFact(path=path, value=value) for path, value in patched_values.items()),
        door=ProfileFactWriteDoor.PATCH,
    )
    return merged_values


def _run_full_flow(
    flow: WizardFlow,
    canonical: dict[str, str],
    *,
    quiet: bool,
    accept_defaults: bool,
    profile_name: str,
    profile_id: str,
    mode: WizardPersistMode,
    explicit_question_ids: frozenset[str] = frozenset(),
) -> dict[str, str]:
    """Walk the full wizard flow and persist the resulting answer set.

    This is the full-flow path for an edit. Create is refused before any
    console or checkpoint can be opened because credential registration owns
    profile creation.

    ``explicit_question_ids`` names the questions whose flag the
    operator supplied on a non-interactive command line. Such a
    question is collected even when its ``visible_when`` gate would
    hide it, so an explicitly-given flag value is always honoured.

    """
    from ...domain.user_profile.values import UserProfileFact
    from ..user_profile.fact_write import ProfileFactWriteDoor, apply_profile_fact_changes
    from ..user_profile.profile_record_repository import ProfileRecordRepository
    from ..user_profile.projections import record_to_path_values
    from ..user_profile.registration import ProfileRegistrationError
    from .persistence import (
        project_answers,
        serialise_answers,
    )

    if mode == "create":
        raise ProfileRegistrationError(
            "wizard profile creation is unavailable; register with credentials before setup",
        )

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
                precondition_verdict=wizard_no_action_verdict(
                    condition=WizardPreconditionCondition.REQUIRED_FLAGS_SUPPLIED,
                    facts={
                        "required_flags_supplied": False,
                        "missing_flag_count": len(missing),
                    },
                    provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                    outcome=NoRecoveryOutcome.OPERATOR_DECISION,
                ),
            )
        answers = _run_scripted_walk(
            flow,
            canonical,
            mode=mode,
            explicit_question_ids=explicit_question_ids,
        )
    elif accept_defaults:
        answers = _run_scripted_walk(
            flow,
            canonical,
            mode=mode,
            explicit_question_ids=explicit_question_ids,
        )
    else:
        # There is no interactive walk here any more. An operator at a
        # capable terminal was already diverted to the profile manager
        # before this command ran, so reaching this branch means the host
        # cannot present a screen at all.  The terminal verdict records that
        # factual capability refusal without prescribing a replacement flow.
        if mode == "edit":
            raise WizardEditUnsupportedConsoleError(
                translated_message="wizard.errors.unsupported_console_edit",
                context={"profile_name": profile_name},
                precondition_verdict=wizard_no_action_verdict(
                    condition=WizardPreconditionCondition.INTERACTIVE_CONSOLE_AVAILABLE,
                    facts={"interactive_console_available": False},
                    provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                    outcome=NoRecoveryOutcome.SAFETY,
                ),
            )
        raise WizardUnsupportedConsoleError(
            translated_message="wizard.errors.unsupported_console",
            precondition_verdict=wizard_no_action_verdict(
                condition=WizardPreconditionCondition.INTERACTIVE_CONSOLE_AVAILABLE,
                facts={"interactive_console_available": False},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        )

    # `create` writes the full answer set. An interactive `edit` writes a
    # patch scoped to the pages the operator actually answered
    # (``supplied_question_ids``); the full serialisation here feeds the
    # filing-baseline survival check and the success payload.
    profile_values = serialise_answers(flow, answers)
    record = ProfileRecordRepository.for_current_session(profile_id).load(profile_id)
    values = record_to_path_values(record)
    values.update({path: value for path, value in profile_values.items() if value})
    _require_filing_baseline(flow, project_answers(flow, values))
    from ...domain.deadlines.profiles import taxpayer_profile_from_mapping

    taxpayer_profile_from_mapping(values, tax_id_default=values.get("identity.tax_id", ""))
    apply_profile_fact_changes(
        profile_id=profile_id,
        changes=tuple(UserProfileFact(path=path, value=value) for path, value in profile_values.items() if value),
        door=ProfileFactWriteDoor.ANSWERS,
    )
    return values


def _enter_requested_output_language(kwargs: dict[str, object], language_stack: contextlib.ExitStack) -> None:
    """Apply a command-line output-language override for the command body."""
    from ...core.config import override_settings

    requested_language = kwargs.get("output_language")
    if isinstance(requested_language, str) and requested_language in SUPPORTED_OUTPUT_LANGUAGES:
        language_stack.enter_context(override_settings(cadrumo_output_language=requested_language))


def _render_error_inside_language_override(exc: CadrumoError) -> None:
    """Freeze a translated Cadrumo error message before locale overrides unwind."""
    translated_key = exc.translated_message
    if not isinstance(translated_key, str) or not translated_key:
        return

    context = _translation_context(getattr(exc, "context", None))
    rendered = tr(translated_key, **context)
    exc.args = (rendered, *exc.args[1:])
    exc.translated_message = None


def _require_profile_name(flow: WizardFlow, raw_profile_name: object) -> str:
    """Return a stripped profile name or raise the wizard missing-flag error."""
    if isinstance(raw_profile_name, str) and raw_profile_name.strip():
        return raw_profile_name.strip()
    raise WizardMissingFlagError(
        translated_message="application.wizard.errors.profile_flag_required",
        context={"flow_id": flow.id, "missing": ("profile_name",)},
        precondition_verdict=wizard_no_action_verdict(
            condition=WizardPreconditionCondition.PROFILE_NAME_SUPPLIED,
            facts={"profile_name_supplied": False},
            provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        ),
    )


def _resolve_profile_id_for_mode(flow: WizardFlow, mode: WizardPersistMode, profile_name: str) -> str:
    """Resolve or mint the immutable profile id for the requested wizard mode.

    A ``create`` always addresses a fresh capsule, so a label already bound to
    a committed capsule is refused here rather than minting an id that could
    never be published. The refusal is an early, operator-facing one over the
    same committed-label projection the resolver below reads; the race-free
    authority remains the custody service's check under the custody-root lock,
    which still backstops this one. A genuinely new label mints a fresh id.

    Any other mode addresses an existing capsule, and the resolution below is
    itself the registration check: an unresolvable label falls through to the
    missing-flag refusal.
    """
    from ...domain.user_profile.values import new_profile_id
    from ..workflow.profile_bucket_scan import read_profile_bucket

    if mode == "create":
        _require_profile_label_available(
            flow,
            profile_name,
            label_is_registered=read_profile_bucket(profile_name) is not None,
        )
        return new_profile_id()

    pointer = read_profile_bucket(profile_name)
    if pointer is not None:
        return pointer.bucket_id
    raise WizardMissingFlagError(
        translated_message="application.wizard.errors.profile_flag_required",
        context={"flow_id": flow.id, "missing": ("profile_name",)},
        precondition_verdict=wizard_no_action_verdict(
            condition=WizardPreconditionCondition.PROFILE_NAME_SUPPLIED,
            facts={"profile_name_supplied": False},
            provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        ),
    )


def _require_profile_label_available(
    flow: WizardFlow,
    profile_name: str,
    *,
    label_is_registered: bool,
) -> None:
    """Refuse create when the committed-label projection already owns a label.

    The caller resolves the persistence fact; this deterministic policy owns
    the operator-facing precondition and remains independent of bucket access.
    """
    if not label_is_registered:
        return
    raise WizardValidationError(
        translated_message="application.wizard.errors.profile_label_taken",
        context={"flow_id": flow.id, "label": profile_name},
        precondition_verdict=wizard_no_action_verdict(
            condition=WizardPreconditionCondition.PROFILE_LABEL_AVAILABLE,
            facts={"profile_registration_available": False},
            provenance=ActionEvidenceProvenance.APPLICATION_STATE,
            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        ),
    )


def _resolve_profile_target_for_mode(
    flow: WizardFlow,
    mode: WizardPersistMode,
    raw_profile_name: object,
) -> tuple[str, str]:
    """Resolve the display label and immutable id addressed by a wizard verb.

    An explicit name keeps the existing create/edit resolver contract. An
    omitted edit addresses the active profile, matching the profile manager and
    the root authentication gate that precedes this command. Create has no
    existing subject to inherit and therefore retains its missing-name refusal.
    """
    if isinstance(raw_profile_name, str) and raw_profile_name.strip():
        profile_name = raw_profile_name.strip()
        return profile_name, _resolve_profile_id_for_mode(flow, mode, profile_name)
    if mode == "create":
        profile_name = _require_profile_name(flow, raw_profile_name)
        return profile_name, _resolve_profile_id_for_mode(flow, mode, profile_name)

    from ...core.bucket_pointer import require_active_bucket_id
    from ..user_profile.login_session import resolve_login_target

    target = resolve_login_target(require_active_bucket_id())
    return target.label, target.bucket_id


def _seed_output_language_from_environment(canonical: dict[str, str]) -> None:
    """Use CADRUMO_OUTPUT_LANGUAGE when the operator omitted the explicit flag."""
    from ...core.config import load_settings

    if "output-language" in canonical:
        return

    env_lang = load_settings().cadrumo_output_language
    if isinstance(env_lang, str) and env_lang in SUPPORTED_OUTPUT_LANGUAGES:
        canonical["output-language"] = env_lang


def _refuse_foral_ccaa(canonical: dict[str, str], explicit_flags: dict[str, str]) -> None:
    """Reject foral CCAA tokens before any persistence or prompt."""
    ccaa_token = canonical.get("tax-residence-ccaa") or explicit_flags.get("tax-residence-ccaa")
    if ccaa_token is None:
        return

    from ...domain.contribuyente.errors import ForalRegimeError
    from ...domain.contribuyente.tax_residence import parse_tax_region

    try:
        parse_tax_region(ccaa_token)
    except ForalRegimeError as foral_exc:
        # Re-raise the domain refusal so the whole line renders through the
        # localized CadrumoError boundary (translated_message), instead of
        # English Click ``Usage`` chrome around a localized body.
        raise foral_exc


# ``SetupAnswers`` field names whose free-text value fails an ISO-8601 date or
# a decimal validator. Keyed on the pydantic error ``loc`` leaf so the raw
# English validator ``msg`` never reaches operator output.
_WIZARD_INVALID_DATE_FIELDS: frozenset[str] = frozenset(
    {
        "taxpayer_marriage_date",
        "activity_start_date",
        "ley_49_2002_option_date",
        "ley_49_2002_renunciation_date",
        "irpf_special_regime_start_date",
    }
)
_WIZARD_INVALID_DECIMAL_FIELDS: frozenset[str] = frozenset(
    {
        "incn_prior_12_months",
        "objective_estimation_modulos_module_1_units",
        "objective_estimation_modulos_module_2_units",
        "objective_estimation_modulos_module_3_units",
        "objective_estimation_modulos_module_4_units",
        "objective_estimation_modulos_module_5_units",
        "objective_estimation_modulos_module_6_units",
        "objective_estimation_modulos_module_7_units",
    }
)
_WIZARD_ERROR_FIELD_KEYS: dict[str, str] = {
    **{field: "wizard.errors.invalid_date" for field in _WIZARD_INVALID_DATE_FIELDS},
    **{field: "wizard.errors.invalid_decimal" for field in _WIZARD_INVALID_DECIMAL_FIELDS},
}

# Cross-field model-validator refusals report an empty ``loc``, so they are
# routed on the stable pydantic error ``type`` (a ``PydanticCustomError`` token
# raised by ``SetupAnswers``). Each maps to its localized detail key plus the
# primary and condition fields whose flags fill the message.
_WIZARD_ERROR_TYPE_KEYS: dict[str, tuple[str, str, str]] = {
    "spouse_tax_id_required_joint": (
        "wizard.errors.spouse_tax_id_required_joint",
        "spouse_tax_id",
        "taxation_type",
    ),
    "eu_eea_country_required": (
        "wizard.errors.eu_eea_country_required",
        "spouse_eu_eea_country",
        "spouse_eu_eea_resident",
    ),
}


def _wizard_field_flags(flow: WizardFlow) -> dict[str, str]:
    """Return answers-model field names mapped to their CLI flag names."""
    return {
        question.id.replace("-", "_"): _flag_name(question)
        for section in flow.sections
        for question in section.questions
    }


def _validation_location_flag(location: tuple[object, ...], field_flags: dict[str, str]) -> str:
    """Render a pydantic location tuple as a flag-oriented field path."""
    path: list[str] = []
    for part in location:
        if part == "__root__":
            continue
        if isinstance(part, str):
            path.append(field_flags.get(part, part))
        else:
            path.append(str(part))
    return ".".join(path)


def _validation_leaf_field(location: tuple[object, ...]) -> str:
    """Return the trailing model field name from a pydantic location tuple."""
    for part in reversed(location):
        if isinstance(part, str) and part != "__root__":
            return part
    return ""


def _stringify_wizard_error_input(value: object) -> str:
    """Render the rejected input value for the ``got`` message context."""
    if value is None:
        return ""
    return str(value)


def _format_wizard_validation_error(flow: WizardFlow, item: ErrorDetails) -> tuple[str | None, str | None]:
    """Render one pydantic validation entry as a localized detail plus its flag.

    The detail is built entirely from a translation-key mapping: cross-field
    model-validator refusals route on the stable pydantic error ``type``, and
    free-text date/decimal value errors route on the failing field's ``loc``
    leaf. The raw pydantic ``msg`` (library English) is never spliced into
    operator output. An entry with no mapped key returns a ``None`` detail so
    the caller falls back to the localized generic message; the failing flag is
    still returned for the ``param_hint``.
    """
    field_flags = _wizard_field_flags(flow)
    error_type = str(item.get("type", ""))
    cross_field = _WIZARD_ERROR_TYPE_KEYS.get(error_type)
    if cross_field is not None:
        key, primary_field, condition_field = cross_field
        primary_flag = field_flags.get(primary_field, primary_field)
        condition_flag = field_flags.get(condition_field, condition_field)
        return tr(key, flag=primary_flag, condition_flag=condition_flag), primary_flag

    location = tuple(item.get("loc", ()))
    field_flag = _validation_location_flag(location, field_flags) or None
    if error_type == "value_error":
        field_key = _WIZARD_ERROR_FIELD_KEYS.get(_validation_leaf_field(location))
        if field_key is not None:
            got = _stringify_wizard_error_input(item.get("input"))
            return tr(field_key, flag=field_flag or _validation_leaf_field(location), got=got), field_flag
    return None, field_flag


def _wizard_validation_bad(flow: WizardFlow, error: ValidationError) -> typer.BadParameter:
    """Convert leaked wizard answer validation into a specific CLI refusal."""
    rendered = [_format_wizard_validation_error(flow, item) for item in error.errors()]
    mapped_details = [detail for detail, _flag in rendered if detail is not None]
    details = (
        "; ".join(mapped_details) if mapped_details else tr("application.wizard.errors.command_input_invalid_fallback")
    )
    message = tr("application.wizard.errors.command_input_invalid", details=details)
    first_flag = next((flag for _detail, flag in rendered if flag), None)
    if first_flag is not None:
        return typer.BadParameter(message, param_hint=f"'{first_flag}'")
    return typer.BadParameter(message)


def _run_wizard_persistence_path(
    flow: WizardFlow,
    mode: WizardPersistMode,
    canonical: dict[str, str],
    explicit_flags: dict[str, str],
    *,
    quiet: bool,
    accept_defaults: bool,
    profile_name: str,
    profile_id: str,
) -> dict[str, str]:
    """Dispatch to patch-edit or full-flow persistence."""
    non_interactive = quiet or accept_defaults
    if mode == "edit" and non_interactive:
        return _run_patch_edit(flow, explicit_flags, profile_id=profile_id)

    return _run_full_flow(
        flow,
        canonical,
        quiet=quiet,
        accept_defaults=accept_defaults,
        profile_name=profile_name,
        profile_id=profile_id,
        mode=mode,
        explicit_question_ids=frozenset(explicit_flags),
    )


#: The routing projection's default suggestion: a profile carrying no
#: fiscal-residency classification that redirects it elsewhere. Public
#: because a consumer projecting this same guidance onto another surface
#: (the profile manager) needs to tell "the ordinary default applies" from
#: "this profile earned a specific next step" without re-deriving the
#: comparison.
DEFAULT_PROFILE_NEXT_COMMAND = "aeat app modelo work create"


def profile_next_step_modelo(profile_values: dict[str, str]) -> str | None:
    """The modelo id the routing projection singles out, or ``None`` for the default.

    The one canonical classification a taxpayer's declared facts route
    through — currently a single rule (IRNR non-residents route to Modelo
    210, TRLIRNR RDLeg 5/2004 Art. 2) — ``None`` for every profile the
    projection does not single out. This is the PRIMARY authority;
    :func:`next_step_command_for_profile_values` derives its CLI command
    text from it rather than repeating the classification, so a consumer
    whose channel cannot carry command prose (the shared
    :class:`~cadrumo.core.json_contract.Notice` structurally forbids an
    embedded executable ``aeat ...`` invocation outside its typed action
    projection) can still word its own sentence around the routed modelo.

    Args:
        profile_values: Dotted-path fact values as the wizard's canonical
            question-id keys, or the equivalent
            :func:`~cadrumo.application.user_profile.record_to_path_values`
            projection of a :class:`~cadrumo.domain.user_profile.values.UserProfileRecord`
            — the two share the same ``taxpayer_type.fiscal_residency`` key.
    """
    fiscal_residency = profile_values.get("taxpayer_type.fiscal_residency", "").strip().lower()
    if fiscal_residency == "non_resident_irnr":
        return Modelo.M210.value
    return None


def next_step_command_for_profile_values(profile_values: dict[str, str]) -> str:
    """Resolve the CLI command a profile's declared facts point at next.

    Derived from :func:`profile_next_step_modelo`, the canonical
    classification, falling back to :data:`DEFAULT_PROFILE_NEXT_COMMAND` when
    it singles out no modelo. Consumed by the scripted wizard's own success
    line, which renders the command as text.
    """
    modelo = profile_next_step_modelo(profile_values)
    if modelo is None:
        return DEFAULT_PROFILE_NEXT_COMMAND
    return f"aeat app modelo describe {modelo}"


def _ccaa_was_defaulted(
    mode: WizardPersistMode,
    explicit_flags: dict[str, str],
    profile_values: dict[str, str],
    *,
    non_interactive: bool,
) -> bool:
    """Return True when the comunidad autónoma was assumed, not chosen.

    The wizard descriptor defaults ``tax-residence-ccaa`` to Madrid for a
    resident-IRPF profile. That default is applied silently on the
    non-interactive create paths (``--quiet`` / ``--accept-defaults``)
    when the operator omits ``--tax-residence-ccaa`` — precisely the case
    that lands a Madrid-based autonomic calculation without the operator
    knowing. The signal is therefore: a non-interactive ``create`` where
    the operator supplied no CCAA flag yet the persisted profile carries
    the Madrid default. An explicitly-supplied CCAA (including an explicit
    ``madrid``) sits in ``explicit_flags`` and is excluded; the interactive
    path prompts for the value and is likewise excluded, as is ``edit``
    (whose CCAA already exists on the profile).
    """
    from ...domain.contribuyente.ccaa import CCAA

    return (
        mode == "create"
        and non_interactive
        and "tax-residence-ccaa" not in explicit_flags
        and profile_values.get("tax_residence.ccaa") == CCAA.MADRID.value
    )


_MODIFY_NO_RESUME_CODE = "config.profile.edit.modify_no_resume"
_MODIFY_DESCENDANTS_DOOR_CODE = "config.profile.edit.descendants_via_door"
_DESCENDIENTE_DOOR_COMMAND = "aeat config profile descendiente"


def _emit_wizard_success(
    mode: WizardPersistMode,
    profile_name: str,
    *,
    next_command: str = DEFAULT_PROFILE_NEXT_COMMAND,
    ccaa_defaulted: bool = False,
    modify_no_resume: bool = False,
    modify_no_resume_message: str | None = None,
    modify_descendants_via_door: bool = False,
    modify_descendants_message: str | None = None,
) -> None:
    """Emit the success payload in JSON or tabular CLI form.

    The post-create / post-edit next-step hint rides on the envelope
    ``notices`` channel (an ``info``-severity :class:`Notice` whose
    ``suggestion`` is the follow-on command) rather than as a bespoke
    ``next`` payload field, so next-step guidance is uniform with every
    other command's notices.

    ``ccaa_defaulted`` requests an additional ``warning``-severity
    :class:`Notice` disclosing that no comunidad autónoma was chosen and
    that Madrid was assumed for the profile — so the operator learns the
    autonomic deductions and autonomic tax scale are being computed for
    Madrid rather than the value being applied silently.

    ``modify_no_resume`` requests an ``info``-severity :class:`Notice`
    stating that mid-flow save/resume is unavailable in modify mode and an
    interrupted modify discards its staged edits. It rides the final
    envelope of every interactive modify run regardless of whether the
    operator attempted a save — the LOUD, never-silent honesty disclosure
    the persistence model binds modify to.

    ``modify_no_resume_message`` carries the message pre-rendered in the
    command-level output language. The final envelope is a command-level
    disclosure, so it must render in the language the command entered with,
    not a mid-walk output-language switch that shadows it by the time this
    emit runs; the caller freezes the string before the walk and passes it
    here. ``None`` falls back to resolving it now (the direct, walk-less
    callers).
    """
    from ...core.click_context import json_output_requested
    from ...domain.contribuyente.ccaa import CCAA
    from ..operator_output.emit import emit_operator_json_success
    from .results import ConfigProfileCreateResult, ConfigProfileEditResult, ProfileWizardStatus

    # Two distinct values, deliberately: ``status_token`` is the closed
    # machine-readable vocabulary the JSON envelope carries, and ``verb`` is
    # the localized word the operator reads on the text line. Collapsing them
    # is what let the wizard publish ``creado`` as a contract token while the
    # profile manager published ``created`` for the same command.
    status_token = ProfileWizardStatus.CREATED if mode == "create" else ProfileWizardStatus.UPDATED
    verb = tr("wizard.commands.status.created" if mode == "create" else "wizard.commands.status.updated")
    resolved_modify_no_resume_message = (
        modify_no_resume_message
        if modify_no_resume_message is not None
        else tr("application.wizard.notices.modify_no_resume")
    )
    resolved_modify_descendants_message = (
        modify_descendants_message
        if modify_descendants_message is not None
        else tr("application.wizard.notices.modify_descendants_via_door")
    )
    ccaa_message = tr("application.wizard.notices.ccaa_defaulted", ccaa=CCAA.MADRID.value)
    notices = _wizard_success_notices(
        mode,
        next_command=next_command,
        modify_no_resume=modify_no_resume,
        modify_no_resume_message=resolved_modify_no_resume_message,
        modify_descendants_via_door=modify_descendants_via_door,
        modify_descendants_message=resolved_modify_descendants_message,
        modify_descendants_action=_resolved_descendientes_action(),
        ccaa_defaulted=ccaa_defaulted,
        ccaa_message=ccaa_message,
    )
    # Populate the envelope-spine active_profile identity anchor. The wizard
    # sits below the CLI transport's emit_envelope funnel (it cannot import
    # it — layering), so it must resolve the label itself. On create the
    # newly-created profile IS the active one, so its name is the label; on
    # edit the active profile is not necessarily the edited one, so the
    # spine stays null (the label is not the wizard's to assert there).
    active_profile = profile_name if mode == "create" else None
    result: ConfigProfileCreateResult | ConfigProfileEditResult = (
        ConfigProfileCreateResult(
            profile_name=profile_name,
            status=status_token,
            active_profile=active_profile,
        )
        if mode == "create"
        else ConfigProfileEditResult(profile_name=profile_name, status=status_token)
    )
    if json_output_requested():
        command_path = "config.profile.create" if mode == "create" else "config.profile.edit"
        # emit_operator_json_success is the one sanctioned direct route to
        # the envelope: it resolves and prepends the sandbox-active notice
        # itself, so this call site cannot forget it (there is no other way
        # to reach SchemaEnvelope for this result from here).
        emit_operator_json_success(command_path, result, notices=notices, active_profile=active_profile)
        return

    _echo_wizard_success_text(
        mode,
        profile_name,
        verb=verb,
        next_command=next_command,
        result=result,
        disclosures=(
            (modify_no_resume, resolved_modify_no_resume_message),
            (modify_descendants_via_door, resolved_modify_descendants_message),
            (ccaa_defaulted, ccaa_message),
        ),
    )


def _echo_wizard_text(lines: list[str], *, payload: object) -> None:
    """Render wizard text lines through the output boundary and emit them.

    The single place this module's operator-facing text crosses into stdout.
    Every identifier-bearing success disclosure funnels through here, so the
    sandbox banner, the redaction pass and the reveal-identifiers resolution
    are applied once rather than once per emitter. Two emitters each holding a
    private copy of the render-and-echo pair is how one of them came to bypass
    the boundary while its sibling did not.
    """
    import typer as _typer

    from ...core.output_rendering import render_command_output
    from ..operator_output.sandbox_notice import sandbox_banner_line, sandbox_notice_for_active_bucket

    sandbox_notice = sandbox_notice_for_active_bucket()
    if sandbox_notice is not None:
        lines.insert(0, sandbox_banner_line(sandbox_notice))
    rendered = render_command_output(format_name="text", payload=payload, lines=lines)
    _typer.echo(rendered.text)


def _echo_wizard_success_text(
    mode: WizardPersistMode,
    profile_name: str,
    *,
    verb: str,
    next_command: str,
    result: ConfigProfileCreateResult | ConfigProfileEditResult,
    disclosures: tuple[tuple[bool, str], ...],
) -> None:
    """Render the success payload as tab-separated operator text.

    Every disclosure that rides the notices channel is repeated here: the
    envelope renders ``notices`` only in JSON mode, so one left off these
    lines would be visible to automation and invisible to the operator
    running the verb plainly.
    """
    lines = [
        f"{tr('application.wizard.output_labels.profile')}\t{profile_name}",
        f"{tr('application.wizard.output_labels.status')}\t{verb}",
    ]
    if mode == "create":
        lines.append(f"{tr('application.wizard.output_labels.active_profile')}\t{profile_name}")
    lines.append(f"{tr('application.wizard.output_labels.next')}\t{next_command}")
    lines.extend(message for enabled, message in disclosures if enabled)
    _echo_wizard_text(lines, payload=result)


def _resolved_descendientes_action() -> ResolvedNoticeAction | None:
    """Resolve the typed descendiente door for the success notice.

    The catalogue entry fails closed on an unknown id, so the notice's
    executable action always names a live verb or the emission refuses —
    the failure mode the old literal-command message could not have.
    """
    from ..operator_actions.catalogue import next_action

    return next_action("operator.profile.descendiente")


def _wizard_success_notices(
    mode: WizardPersistMode,
    *,
    next_command: str,
    modify_no_resume: bool,
    modify_no_resume_message: str,
    modify_descendants_via_door: bool,
    modify_descendants_message: str,
    modify_descendants_action: ResolvedNoticeAction | None = None,
    ccaa_defaulted: bool,
    ccaa_message: str,
) -> list[Notice]:
    """Build the success envelope's notices: the next step plus each disclosure.

    Every message arrives pre-rendered because the final envelope is a
    command-level disclosure and must render in the language the command
    entered with, not one a mid-walk output-language switch left behind.
    """
    from ...core.json_contract import Notice, NoticeSeverity
    from ...domain.contribuyente.ccaa import CCAA

    verb_key = "create" if mode == "create" else "edit"
    # The next-step hint is text-surface only. ``Notice`` reserves executable
    # command identity for its typed action projection, which models a
    # PRECONDITION-FAILURE recovery - a failed condition, its evidence, its
    # conditionality - and has no member that means "this succeeded, here is a
    # reasonable next verb". Carrying the bare label without its command would
    # emit a notice reading "Next:" and nothing else, which is worse than
    # emitting none, so the JSON channel omits it entirely rather than shipping
    # an empty gesture. ``next_command`` still renders on the text surface.
    _ = next_command
    notices: list[Notice] = []
    if modify_no_resume:
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code=_MODIFY_NO_RESUME_CODE,
                message=modify_no_resume_message,
            ),
        )
    if modify_descendants_via_door:
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code=_MODIFY_DESCENDANTS_DOOR_CODE,
                message=modify_descendants_message,
                action=modify_descendants_action,
            ),
        )
    if ccaa_defaulted:
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code=f"config.profile.{verb_key}.ccaa_defaulted",
                message=ccaa_message,
                context={"assumed_ccaa": CCAA.MADRID.value},
            ),
        )
    return notices


def _execute_wizard_command(
    flow: WizardFlow,
    mode: WizardPersistMode,
    *,
    kwargs: dict[str, object],
) -> None:
    """Run the wizard command body after Typer has parsed dynamic flags."""
    profile_name, profile_id = _resolve_profile_target_for_mode(
        flow,
        mode,
        kwargs.pop("profile_name"),
    )
    quiet = bool(kwargs.pop("quiet", False))
    accept_defaults = bool(kwargs.pop("accept_defaults", False))
    canonical = _collect_flag_values(flow, kwargs)
    explicit_flags: dict[str, str] = dict(canonical)

    _seed_output_language_from_environment(canonical)
    # Freeze the final-envelope disclosure notices in the command-level output
    # language now, BEFORE the interactive walk can activate a mid-walk
    # override that shadows this language by the time the envelope is emitted.
    # The envelope is a command-level disclosure, not walk content, so it must
    # render in the language the command entered with — the same pre-render
    # discipline the error path uses for a translated refusal.
    modify_no_resume_message = tr("application.wizard.notices.modify_no_resume")
    modify_descendants_message = tr("application.wizard.notices.modify_descendants_via_door")
    _refuse_foral_ccaa(canonical, explicit_flags)
    try:
        profile_values = _run_wizard_persistence_path(
            flow,
            mode,
            canonical,
            explicit_flags,
            quiet=quiet,
            accept_defaults=accept_defaults,
            profile_name=profile_name,
            profile_id=profile_id,
        )
    except ValidationError as exc:
        raise _wizard_validation_bad(flow, exc) from exc
    # Every interactive modify run carries the LOUD staged-only disclosure on
    # its final envelope: mid-flow save/resume is unavailable and an
    # interrupted modify discards its staged edits. Non-interactive patch
    # edits (`--quiet` / `--accept-defaults`) stage nothing, so the notice is
    # scoped to the interactive walk.
    interactive_modify = mode == "edit" and not (quiet or accept_defaults)
    _emit_wizard_success(
        mode,
        profile_name,
        next_command=next_step_command_for_profile_values(profile_values),
        ccaa_defaulted=_ccaa_was_defaulted(
            mode,
            explicit_flags,
            profile_values,
            non_interactive=quiet or accept_defaults,
        ),
        modify_no_resume=interactive_modify,
        modify_no_resume_message=modify_no_resume_message,
        modify_descendants_via_door=interactive_modify,
        modify_descendants_message=modify_descendants_message,
    )


def build_wizard_command(
    flow: WizardFlow,
    *,
    mode: WizardPersistMode,
) -> Callable[..., None]:
    """Return a Typer-compatible callable that runs ``flow``.

    The returned closure carries one parameter per question in the
    flow (typed and annotated for Typer to derive a CLI flag) plus the
    three mode flags.

    ``mode`` binds the closure to a single wizard verb. ``"create"``
    refuses a name that already has a manifest; ``"edit"`` refuses a
    name that has none. Both refusals fire before the wizard prompts,
    so an operator is never walked through 40-odd questions only to
    have the persistence step reject the work.

    There is no interactive walk: an operator at a capable terminal is
    diverted to the profile manager before this command runs, so what is
    left here is the programmatic contract — flags in, JSON envelope out.
    An invocation that supplies neither ``--quiet``/``--accept-defaults``
    nor the values it needs is refused with the flag form named.
    """
    question_params = _question_parameters(flow)
    mode_params = _mode_parameters(flow, mode=mode)
    parameters = (*mode_params, *question_params)
    signature, annotations = _wizard_command_metadata(parameters)

    def _command(**kwargs: object) -> None:
        import contextlib

        from ...core.errors.hierarchy import CadrumoError

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
                _execute_wizard_command(flow, mode, kwargs=kwargs)
            except CadrumoError as exc:
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
    typed.__signature__ = signature
    typed.__annotations__ = annotations
    typed.__name__ = flow.id
    typed.__doc__ = tr(f"wizard.{flow.id}.description")
    typed.__wizard_flow__ = flow
    return _command


__all__ = [
    "DEFAULT_PROFILE_NEXT_COMMAND",
    "SETUP_OPTION_INFOS",
    "build_wizard_command",
    "next_step_command_for_profile_values",
    "profile_next_step_modelo",
    "scripted_profile_facts",
]
