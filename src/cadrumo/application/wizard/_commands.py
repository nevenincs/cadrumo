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
substrate :class:`~cadrumo.application.flows.FlowDefinition`
(via :func:`~cadrumo.application.flows.flow_definition_from_wizard_flow`)
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

import functools
import inspect
import typing
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

if TYPE_CHECKING:
    from ...core.errors import CadrumoError
    from ...domain.user_profile import UserProfileRecord
    from ..workflow import WorkflowState

import contextlib
import re

import click
import click.types
import typer
import typer._click.types
from pydantic import BaseModel, ValidationError
from pydantic_core import ErrorDetails

from ...core.flows import CheckpointAvailability, FlowMode
from ...core.i18n import SUPPORTED_OUTPUT_LANGUAGES, tr
from ..flows import (
    CheckpointStore,
    FlowAnswerError,
    FlowDefinition,
    FlowPage,
    FlowState,
    FlowSubmitError,
    FlowUnsupportedConsoleError,
    LineFlowFrontend,
    flow_definition_from_wizard_flow,
    run_scripted_flow,
    start_flow,
    visible_sequence,
)
from ._catalogue import SETUP_FLOW
from ._checkpoint_store import ProfileFactsCheckpointStore
from ._descendant_group import attach_descendant_group
from ._errors import WizardMissingFlagError
from ._format_hints import attach_format_hints
from ._models import WizardFlow, WizardQuestion, WizardWidget
from ._persistence import WizardPersistMode
from ._registered_values import project_registered_values
from ._setup_legal_validators import attach_setup_legal_validators

#: Which substrate :class:`FlowMode` each wizard verb drives. ``create``
#: registers a fresh profile, ``edit`` modifies an existing one.
_FLOW_MODE_BY_WIZARD_MODE: dict[WizardPersistMode, FlowMode] = {
    "create": FlowMode.CREATE,
    "edit": FlowMode.MODIFY,
}

#: Checkpoint posture for the setup flow (the facts-ARE-the-checkpoint model).
#: CREATE offers save-and-exit and resume: the profile is minted early in
#: ``SETUP_INCOMPLETE`` state and every answer persists as an effective-dated
#: fact through the lifecycle authority, so the encrypted facts themselves are
#: the checkpoint. MODIFY stays the declared no-op — a live profile must never
#: hold a half-applied edit set — so the substrate refuses a save loudly rather
#: than offer one it cannot honour.
_SETUP_CHECKPOINT: dict[FlowMode, CheckpointAvailability] = {
    FlowMode.CREATE: CheckpointAvailability.AVAILABLE,
    FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
}


# KWARGS-RATIONALE-flow-runner: keyword-only frontend seam injected by the caller.
class InteractiveFlowRunner(typing.Protocol):
    """Drive one interactive flow run to a submitted state.

    The application default renders the line-mode frontend (a same-layer
    ``application.flows`` primitive). The CLI entrypoint injects a
    capability-selecting runner that reaches the full-screen Textual
    frontend (an inbound adapter the application layer must not import
    directly), so the paged flow is the operator-facing default while the
    application stays free of an inbound-adapter dependency.
    """

    def __call__(
        self,
        definition: FlowDefinition,
        *,
        mode: FlowMode,
        registered_values: Mapping[str, str] | None,
        on_language_activated: Callable[[str, str], bool] | None = None,
        checkpoint_store: CheckpointStore | None = None,
    ) -> FlowState:
        """Run ``definition`` in ``mode`` and return the final flow state.

        ``on_language_activated`` is the mid-walk output-language activator:
        fired post-commit for each answered page, it re-activates the output
        language when the ``output-language`` page is committed and reports
        whether a switch happened so the frontend can re-render. It is
        ``None`` when the existing language chain (an explicit flag or the
        environment) already pins the language for the whole run.

        ``checkpoint_store`` is the create-mode facts-as-checkpoint port: a
        frontend that declares checkpointing AVAILABLE for ``mode`` honours
        save-and-exit through it. It is ``None`` in a mode whose definition
        declares checkpointing UNAVAILABLE.
        """
        ...


def _activation_only_committed_callback(
    on_language_activated: Callable[[str, str], bool] | None,
) -> Callable[[str, str], None] | None:
    """Adapt a language activator to the frontend's post-commit callback.

    The line frontend re-assembles every page's copy on render, so the next
    page renders under the newly-activated language with no further action;
    the activator's boolean verdict is therefore discarded here. Returns
    ``None`` when no activator is supplied so the frontend fires no hook.
    """
    if on_language_activated is None:
        return None

    def _committed(page_key: str, value: str) -> None:
        on_language_activated(page_key, value)

    return _committed


def _line_mode_interactive_runner(
    definition: FlowDefinition,
    *,
    mode: FlowMode,
    registered_values: Mapping[str, str] | None = None,
    on_language_activated: Callable[[str, str], bool] | None = None,
    checkpoint_store: CheckpointStore | None = None,
) -> FlowState:
    """Default runner: the line-mode frontend over the one flow engine.

    The line frontend carries no registered-value column, so on-record
    values are surfaced only through the full-screen review table when the
    entrypoint injects the capability-selecting runner; the degradation
    tier walks the same engine, validation, and submit gate. When the
    definition declares checkpointing AVAILABLE for ``mode`` the injected
    ``checkpoint_store`` backs the save-and-exit affordance.
    """
    del registered_values
    state, _projection = LineFlowFrontend(
        definition,
        checkpoint_store=checkpoint_store,
        on_answer_committed=_activation_only_committed_callback(on_language_activated),
    ).run(mode=mode)
    return state


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
    from ...domain.contribuyente import CCAA

    common = [member.value for member in CCAA]
    foral = ["pais_vasco", "navarra"]
    return common + foral


_CCAA_CHOICE_VALUES: list[str] = _ccaa_choice_values()


def _fiscal_residency_choice_values() -> list[str]:
    """Return the FiscalResidency choice tokens accepted by ``--fiscal-residency``."""
    from ...domain.deadlines import FiscalResidency

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
    from ...domain.deadlines import (
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
    from ...domain.deadlines import IrpfSpecialRegime

    return (
        [member.value for member in IrpfSpecialRegime],
        [member.value for member in SituacionFamiliar],
    )


(
    _IRPF_SPECIAL_REGIME_CHOICE_VALUES,
    _SITUACION_FAMILIAR_CHOICE_VALUES,
) = _irpf_personal_choice_values()


def _iva_regime_choice_values() -> list[str]:
    """Return the wizard choice tokens accepted by ``--iva-regime``."""
    for section in SETUP_FLOW.sections:
        for question in section.questions:
            if question.id == "iva-regime":
                return [choice.value for choice in question.choices]
    raise RuntimeError("SETUP_FLOW is missing the iva-regime question")


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
        click_type=_choice(_IVA_REGIME_CHOICE_VALUES, case_sensitive=False),
        metavar=_choice_metavar(_IVA_REGIME_CHOICE_VALUES),
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


def _missing_filing_baseline_flags(flow: WizardFlow, answers: BaseModel) -> tuple[str, ...]:
    """Return filing identity facts that must exist before persistence.

    Wizard answer models can carry partial values while prompts are being
    collected or projected. Persisted create and edit operations are stricter:
    they must leave a taxpayer-type axis and a filing identity, otherwise
    modelo work would fail later against an already-committed profile.
    """
    from ..user_profile import missing_filing_baseline_flags as _missing_profile_filing_baseline_flags
    from ._persistence import serialise_answers

    return _missing_profile_filing_baseline_flags(serialise_answers(flow, answers))


def _setup_flow_definition(flow: WizardFlow, *, attach_descendants: bool = True) -> FlowDefinition:
    """Bridge and decorate the wizard flow into the shared substrate definition.

    The single projected :class:`FlowDefinition` every frontend drives:
    the substrate bridge, format hints, setup legal validators, and -- for
    CREATE -- the descendant repeating group, applied in one place so the
    interactive and the non-interactive walks can never diverge on the
    definition they run.

    ``attach_descendants`` gates the descendant group. It is spliced for
    CREATE (where the facts-as-checkpoint store seeds and re-seeds the group)
    and withheld for MODIFY. Modify-mode seeding cannot instantiate the
    repeating group: the modify frontend seeds render-time page defaults over
    a fresh :func:`~cadrumo.application.flows.start_flow` state, and instance
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
    new_sections = []
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

    :func:`~cadrumo.application.flows.run_scripted_flow` consumes an ordered
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
    from ._persistence import _parse_canonical
    from ._widgets import validate_widget_answer

    typed: dict[str, object] = {}
    for section in flow.sections:
        for question in section.questions:
            if question.id not in committed:
                continue
            validated = validate_widget_answer(question, committed[question.id])
            typed[question.id.replace("-", "_")] = _parse_canonical(question, validated)
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
        _setup_flow_definition(flow, attach_descendants=mode == "create"),
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


def _run_patch_edit(flow: WizardFlow, explicit_flags: dict[str, str], *, profile_id: str) -> dict[str, str]:
    """Persist a non-interactive ``edit`` as a true patch.

    Only the flags the operator named on the command line are written;
    every other stored field is left untouched. No full-flow walk, no
    ``SetupAnswers`` model construction, no descriptor-default seeding.
    """
    from ..user_profile import profile_storage_session, record_to_path_values
    from ..workflow import workflow_state_repository
    from ._persistence import persist_patch, profile_values_from_patch, project_answers

    patched_values = profile_values_from_patch(flow, explicit_flags)
    merged_values: dict[str, str] | None = None

    with profile_storage_session(profile_id):
        repository = workflow_state_repository()

        def _persist_if_filing_baseline_survives(state: WorkflowState) -> WorkflowState:
            nonlocal merged_values
            values = record_to_path_values(state.active_profile_record())
            values.update(patched_values)
            merged_values = values
            missing_baseline = _missing_filing_baseline_flags(flow, project_answers(flow, values))
            if missing_baseline:
                raise WizardMissingFlagError(
                    translated_message="application.wizard.errors.edit_missing_filing_baseline",
                    context={
                        "flow_id": flow.id,
                        "missing": missing_baseline,
                        "missing_flags": _format_missing_flags(missing_baseline),
                    },
                )
            return persist_patch(flow, explicit_flags, state=state)

        repository.update(_persist_if_filing_baseline_survives)
    return merged_values or patched_values


def _all_question_ids(flow: WizardFlow) -> frozenset[str]:
    """Return every question id declared by the flow."""
    return frozenset(question.id for section in flow.sections for question in section.questions)


def _seed_flow_definition(definition: FlowDefinition, seed_by_page_id: Mapping[str, str]) -> FlowDefinition:
    """Return a copy of ``definition`` with page defaults seeded from a value map.

    The seeded value becomes each page's render-time prefill (the
    descriptor default the frontend shows before the operator types),
    never a committed answer — the engine's answer map still records only
    what the operator actually confirms, which is what the patch-scope
    (``supplied_question_ids``) derivation relies on.
    """
    if not seed_by_page_id:
        return definition
    new_sections = []
    for section in definition.sections:
        new_items = tuple(
            item.model_copy(update={"default": seed_by_page_id[item.id]})
            if isinstance(item, FlowPage) and item.id in seed_by_page_id
            else item
            for item in section.items
        )
        new_sections.append(section.model_copy(update={"items": new_items}))
    return definition.model_copy(update={"sections": tuple(new_sections)})


def _load_on_record(profile_id: str) -> UserProfileRecord | None:
    """Load the active profile record for the on-record seed and projection."""
    from ..user_profile import profile_storage_session
    from ..workflow import workflow_state_repository

    with profile_storage_session(profile_id):
        return workflow_state_repository().load().active_profile_record()


def _prepare_interactive_flow(
    flow: WizardFlow,
    canonical: Mapping[str, str],
    *,
    mode: WizardPersistMode,
    profile_id: str,
) -> tuple[FlowDefinition, Mapping[str, str] | None]:
    """Bridge the wizard flow to a seeded flow definition for interactive rendering.

    ``create`` seeds page prefills from the collected canonical values
    (the environment / explicit output-language, chiefly) and surfaces no
    registered column. ``edit`` seeds render-time prefills from the
    profile's on-record TOKEN values (the raw token the operator edits)
    and, separately, feeds the review table's ``registered_values`` column
    from the display-ready projection
    (:func:`~cadrumo.application.wizard._registered_values.project_registered_values`):
    closed-set tokens render as their choice label, booleans as the
    localized yes/no pair, and an artefact-sourced fact carries the
    non-official-evidence suffix. The projection resolves copy at call
    time — post output-language activation — so the review renders in the
    operator's chosen language.
    """
    definition = _setup_flow_definition(flow, attach_descendants=mode == "create")
    if mode == "create":
        return _seed_flow_definition(definition, dict(canonical)), None

    from ..user_profile import record_to_path_values

    record = _load_on_record(profile_id)
    record_values = record_to_path_values(record)
    registered_values = project_registered_values(flow, record)
    seed_by_page_id: dict[str, str] = {}
    for section in flow.sections:
        for question in section.questions:
            if question.profile_key is not None and question.profile_key in record_values:
                seed_by_page_id[question.id] = record_values[question.profile_key]
    seed_by_page_id.update(canonical)
    return _seed_flow_definition(definition, seed_by_page_id), registered_values


def _run_interactive_flow(
    flow: WizardFlow,
    canonical: Mapping[str, str],
    *,
    mode: WizardPersistMode,
    profile_id: str,
    profile_name: str,
    interactive_flow_runner: InteractiveFlowRunner,
    checkpoint_store: CheckpointStore | None = None,
) -> tuple[BaseModel, frozenset[str], dict[str, str]]:
    """Render the paged flow, then project its answers into the typed model.

    Drives the injected frontend runner (full-screen TUI where the host
    supports it, line mode otherwise) to a submitted flow state, then
    replays the engine's committed answers through the same scripted
    projection the non-interactive paths use, so the persisted typed
    model is produced identically regardless of frontend. ``edit`` scopes
    the write to the pages the operator actually answered; ``create``
    writes the full set.

    ``checkpoint_store`` backs create-mode save-and-exit; it is threaded
    into the runner so the frontend can persist through it. The returned
    tuple carries the typed answers model, the supplied-question-id scope,
    and the engine's committed page-keyed answer map (the create-mode
    completion path persists that map through the same store).
    """
    if mode == "create" and checkpoint_store is not None:
        # Resume seed: an in-progress SETUP_INCOMPLETE profile re-projects
        # its on-record facts to page prefills so the walk continues from
        # the prior answers. Explicit flags still override a resumed value.
        resumed = checkpoint_store.load(flow.id)
        if resumed:
            canonical = {**dict(resumed), **dict(canonical)}
    # The wizard console-refusal taxonomy is registry-pinned to the retired
    # line-mode surface and relocated by the substrate-retirement stream; reach
    # it through this package's own public facade so this module carries no
    # dependency on that surface's private module.
    from . import WizardEditUnsupportedConsoleError, WizardUnsupportedConsoleError

    definition, registered_values = _prepare_interactive_flow(flow, canonical, mode=mode, profile_id=profile_id)
    try:
        final_state = interactive_flow_runner(
            definition,
            mode=_FLOW_MODE_BY_WIZARD_MODE[mode],
            registered_values=registered_values,
            checkpoint_store=checkpoint_store,
        )
    except (FlowUnsupportedConsoleError, WizardUnsupportedConsoleError) as exc:
        # The shared no-console message points at `profile create`, which
        # reads as a destructive replacement when an operator hit it via
        # `profile edit`; re-raise an edit-specific hint that names the
        # non-interactive `profile edit` patch form instead.
        if mode == "edit":
            raise WizardEditUnsupportedConsoleError(
                translated_message="wizard.errors.unsupported_console_edit",
                context={"profile_name": profile_name},
            ) from exc
        raise WizardUnsupportedConsoleError(
            translated_message="wizard.errors.unsupported_console",
        ) from exc

    committed = dict(final_state.answers)
    # An interactive edit patches exactly the pages the operator answered; a
    # create writes the full set.
    supplied_question_ids = frozenset(committed) if mode == "edit" else _all_question_ids(flow)
    # Coerce the engine's committed answers into the typed model through the
    # one projection every frontend shares — no second walk, no prompter.
    answers = _answers_model_from_canonical(flow, committed)
    return answers, supplied_question_ids, committed


def _finish_interactive_create(
    flow: WizardFlow,
    answers: BaseModel,
    committed: Mapping[str, str],
    *,
    profile_id: str,
    checkpoint_store: CheckpointStore,
) -> dict[str, str]:
    """Complete or leave-incomplete an interactive create after the walk returns.

    The profile is minted early and its facts persist through the store, so
    this decides only the terminal transition. A frontend save-and-exit
    (``save_exit_persisted``) leaves the profile ``SETUP_INCOMPLETE`` — the
    facts are already saved and the operator resumes later. A submit runs
    the filing-baseline gate, ensures the answer set is persisted, then
    flips the profile ``ACTIVE`` through
    :func:`~cadrumo.application.user_profile.complete_setup_with_lifecycle_span`
    (emitting ``PROFILE_SETUP_COMPLETED``) — the completion discard: the
    status flip is what ends resume-eligibility.
    """
    from ..user_profile import complete_setup_with_lifecycle_span
    from ._persistence import serialise_answers

    profile_values = serialise_answers(flow, answers)
    if checkpoint_store.save_exit_persisted:
        return profile_values

    missing_baseline = _missing_filing_baseline_flags(flow, answers)
    if missing_baseline:
        raise WizardMissingFlagError(
            translated_message="application.wizard.errors.create_missing_filing_baseline",
            context={
                "flow_id": flow.id,
                "missing": missing_baseline,
                "missing_flags": _format_missing_flags(missing_baseline),
            },
        )
    checkpoint_store.persist(committed)
    complete_setup_with_lifecycle_span(profile_id)
    return profile_values


def _run_full_flow(
    flow: WizardFlow,
    canonical: dict[str, str],
    *,
    quiet: bool,
    accept_defaults: bool,
    profile_name: str,
    profile_id: str,
    mode: WizardPersistMode,
    interactive_flow_runner: InteractiveFlowRunner = _line_mode_interactive_runner,
    explicit_question_ids: frozenset[str] = frozenset(),
    checkpoint_store: CheckpointStore | None = None,
) -> dict[str, str]:
    """Walk the full wizard flow and persist the resulting answer set.

    Used for ``create`` (every path) and for an interactive ``edit``,
    where the operator re-walks and confirms every visible question.

    ``explicit_question_ids`` names the questions whose flag the
    operator supplied on a non-interactive command line. Such a
    question is collected even when its ``visible_when`` gate would
    hide it, so an explicitly-given flag value is always honoured.

    ``checkpoint_store`` is supplied only for an interactive ``create``:
    the facts persist incrementally through it (mint-early, save-and-exit)
    and completion flips the profile ``ACTIVE``, so that path bypasses the
    end-of-flow ``register_active_profile`` used by every other persistence
    route.
    """
    from ..user_profile import (
        profile_create_storage_span,
        profile_storage_session,
        record_to_path_values,
    )
    from ..workflow import workflow_state_repository
    from ._persistence import persist_answers, project_answers, serialise_answers

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
        answers = _run_scripted_walk(
            flow,
            canonical,
            mode=mode,
            explicit_question_ids=explicit_question_ids,
        )
        supplied_question_ids = _all_question_ids(flow)
    elif accept_defaults:
        answers = _run_scripted_walk(
            flow,
            canonical,
            mode=mode,
            explicit_question_ids=explicit_question_ids,
        )
        supplied_question_ids = _all_question_ids(flow)
    else:
        answers, supplied_question_ids, committed = _run_interactive_flow(
            flow,
            canonical,
            mode=mode,
            profile_id=profile_id,
            profile_name=profile_name,
            interactive_flow_runner=interactive_flow_runner,
            checkpoint_store=checkpoint_store,
        )
        # Interactive create is the facts-as-checkpoint path: the profile
        # was minted early and its facts persisted through the store, so a
        # save-and-exit needs no further write and a submit completes the
        # setup. Every other route falls through to the shared span below.
        if mode == "create" and checkpoint_store is not None:
            return _finish_interactive_create(
                flow,
                answers,
                committed,
                profile_id=profile_id,
                checkpoint_store=checkpoint_store,
            )

    # `create` writes the full answer set. An interactive `edit` writes a
    # patch scoped to the pages the operator actually answered
    # (``supplied_question_ids``); the full serialisation here feeds the
    # filing-baseline survival check and the success payload.
    profile_values = serialise_answers(flow, answers)
    if mode == "create":
        missing_baseline = _missing_filing_baseline_flags(flow, answers)
        if missing_baseline:
            raise WizardMissingFlagError(
                translated_message="application.wizard.errors.create_missing_filing_baseline",
                context={
                    "flow_id": flow.id,
                    "missing": missing_baseline,
                    "missing_flags": _format_missing_flags(missing_baseline),
                },
            )

    span = profile_create_storage_span(profile_id) if mode == "create" else profile_storage_session(profile_id)
    with span as routing_profile_id:

        def _persist_if_filing_baseline_survives(state: WorkflowState) -> WorkflowState:
            if mode == "edit":
                values = record_to_path_values(state.active_profile_record())
                values.update({path: value for path, value in profile_values.items() if value})
                missing_baseline = _missing_filing_baseline_flags(flow, project_answers(flow, values))
                if missing_baseline:
                    raise WizardMissingFlagError(
                        translated_message="application.wizard.errors.edit_missing_filing_baseline",
                        context={
                            "flow_id": flow.id,
                            "missing": missing_baseline,
                            "missing_flags": _format_missing_flags(missing_baseline),
                        },
                    )
            return persist_answers(
                flow,
                answers,
                state=state,
                profile_name=profile_name,
                profile_id=profile_id,
                mode=mode,
                supplied_question_ids=supplied_question_ids,
                routing_profile_id=routing_profile_id if mode == "create" else None,
            )

        workflow_state_repository().update(_persist_if_filing_baseline_survives)
    return profile_values


def _enter_requested_output_language(kwargs: dict[str, object], language_stack: contextlib.ExitStack) -> None:
    """Apply a command-line output-language override for the command body."""
    from ...core.config import override_settings

    requested_language = kwargs.get("output_language")
    if isinstance(requested_language, str) and requested_language in SUPPORTED_OUTPUT_LANGUAGES:
        language_stack.enter_context(override_settings(cadrumo_output_language=requested_language))


def _build_mid_walk_language_activation(
    kwargs: dict[str, object],
    language_stack: contextlib.ExitStack,
) -> Callable[[str, str], bool] | None:
    """Return a mid-walk output-language activator, or ``None`` when precedence forbids it.

    The interactive setup flow asks for the output language on its first
    page, so committing that answer should re-render the remaining pages in
    the chosen language. Precedence guards that: an explicit
    ``--output-language`` flag or a ``CADRUMO_OUTPUT_LANGUAGE`` environment /
    settings value already pins the language for the whole run, so the
    mid-walk answer must not override the existing chain — this returns
    ``None`` and no hook is wired.

    Otherwise the returned callback, fired post-commit for the
    ``output-language`` page only, enters a settings override scoped to the
    remainder of the run (tearing down with ``language_stack``) and reports
    ``True`` so the caller can re-render the next page under the new language.
    It reacts to no other page — the hook also fires per staged checkbox
    toggle, so a handler that re-activated on anything else would rebuild on
    every tick. The committed value may be a secret page's raw answer, so the
    callback never logs, echoes, or records it; it inspects the value only for
    the non-secret ``output-language`` page.
    """
    requested = kwargs.get("output_language")
    if isinstance(requested, str) and requested in SUPPORTED_OUTPUT_LANGUAGES:
        return None
    from ...core.config import load_settings

    if "cadrumo_output_language" in load_settings().model_fields_set:
        return None

    def _activate(page_key: str, value: str) -> bool:
        if page_key != "output-language":
            return False
        if not isinstance(value, str) or value not in SUPPORTED_OUTPUT_LANGUAGES:
            return False
        from ...core.config import override_settings
        from ...core.i18n import clear_output_language_cache

        language_stack.enter_context(override_settings(cadrumo_output_language=value))
        clear_output_language_cache()
        return True

    return _activate


def _render_error_inside_language_override(exc: CadrumoError) -> None:
    """Freeze a translated Cadrumo error message before locale overrides unwind."""
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
    """Resolve or mint the immutable profile id for the requested wizard mode.

    A ``create`` for a label whose profile is ``SETUP_INCOMPLETE`` resolves
    to that in-progress bucket so the walk RESUMES it rather than refusing
    as a duplicate — the facts-as-checkpoint re-entry. A label carried by an
    ``ACTIVE`` profile still refuses (finish then edit), and a genuinely new
    label mints a fresh id.
    """
    from ...domain.user_profile import UserProfileStatus, new_profile_id
    from ..user_profile import refuse_duplicate_label, require_registered_label
    from ..workflow import read_profile_bucket

    if mode == "create":
        pointer = read_profile_bucket(profile_name)
        if pointer is not None and pointer.status is UserProfileStatus.SETUP_INCOMPLETE:
            return pointer.bucket_id
        refuse_duplicate_label(profile_name)
        return new_profile_id()

    require_registered_label(profile_name)
    pointer = read_profile_bucket(profile_name)
    if pointer is not None:
        return pointer.bucket_id
    raise WizardMissingFlagError(
        translated_message="application.wizard.errors.profile_flag_required",
        context={"flow_id": flow.id, "missing": ("profile_name",)},
    )


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

    from ...domain.contribuyente import ForalRegimeError, parse_tax_region

    try:
        parse_tax_region(ccaa_token)
    except ForalRegimeError as foral_exc:
        # Re-raise the domain refusal so the whole line renders through the
        # localized CadrumoError boundary (translated_message + suggestion),
        # instead of English Click ``Usage`` chrome around a localized body.
        foral_exc.suggestion = _FORAL_REFUSAL_SUGGESTION
        raise foral_exc


_FORAL_REFUSAL_SUGGESTION = "aeat config profile create NAME --tax-residence-ccaa <ccaa>"


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


def _replace_validation_field_names(message: str, field_flags: dict[str, str]) -> str:
    """Replace model field identifiers in ``message`` with operator-facing flags."""
    rendered = message
    for field_name, flag_name in sorted(field_flags.items(), key=lambda item: len(item[0]), reverse=True):
        rendered = re.sub(rf"\b{re.escape(field_name)}\b", flag_name, rendered)
    return rendered


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
    interactive_flow_runner: InteractiveFlowRunner,
    checkpoint_store: CheckpointStore | None = None,
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
        interactive_flow_runner=interactive_flow_runner,
        explicit_question_ids=frozenset(explicit_flags),
        checkpoint_store=checkpoint_store,
    )


_DEFAULT_PROFILE_NEXT_COMMAND = "aeat app modelo work create"
_NON_RESIDENT_IRNR_NEXT_COMMAND = "aeat app modelo describe 210"


def _next_step_command_for_profile_values(profile_values: dict[str, str]) -> str:
    fiscal_residency = profile_values.get("taxpayer_type.fiscal_residency", "").strip().lower()
    if fiscal_residency == "non_resident_irnr":
        return _NON_RESIDENT_IRNR_NEXT_COMMAND
    return _DEFAULT_PROFILE_NEXT_COMMAND


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
    from ...domain.contribuyente import CCAA

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
    next_command: str = _DEFAULT_PROFILE_NEXT_COMMAND,
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
    import typer as _typer

    from ...core.click_context import json_output_requested
    from ...core.json_contract import Notice, NoticeSeverity, emit_json_success
    from ...core.output_rendering import render_command_output
    from ...domain.contribuyente import CCAA

    verb = tr("wizard.commands.status.created" if mode == "create" else "wizard.commands.status.updated")
    notices: list[Notice] = [
        Notice(
            severity=NoticeSeverity.INFO,
            code=f"config.profile.{'create' if mode == 'create' else 'edit'}.next_step",
            message=tr("application.wizard.output_labels.next"),
            suggestion=next_command,
        )
    ]
    resolved_modify_no_resume_message = (
        modify_no_resume_message
        if modify_no_resume_message is not None
        else tr("application.wizard.notices.modify_no_resume")
    )
    if modify_no_resume:
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code=_MODIFY_NO_RESUME_CODE,
                message=resolved_modify_no_resume_message,
            )
        )
    resolved_modify_descendants_message = (
        modify_descendants_message
        if modify_descendants_message is not None
        else tr(
            "application.wizard.notices.modify_descendants_via_door",
            default="Descendants are not part of profile edit. Manage them with '{command}'.",
            command=_DESCENDIENTE_DOOR_COMMAND,
        )
    )
    if modify_descendants_via_door:
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code=_MODIFY_DESCENDANTS_DOOR_CODE,
                message=resolved_modify_descendants_message,
                suggestion=_DESCENDIENTE_DOOR_COMMAND,
            )
        )
    ccaa_message = tr("application.wizard.notices.ccaa_defaulted", ccaa=CCAA.MADRID.value)
    if ccaa_defaulted:
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code=f"config.profile.{'create' if mode == 'create' else 'edit'}.ccaa_defaulted",
                message=ccaa_message,
                context={"assumed_ccaa": CCAA.MADRID.value},
            )
        )
    payload: dict[str, object] = {
        "profile_name": profile_name,
        "status": verb,
    }
    if mode == "create":
        payload["active_profile"] = profile_name
    if json_output_requested():
        command_path = "config.profile.create" if mode == "create" else "config.profile.edit"
        # Populate the envelope-spine active_profile identity anchor. The
        # wizard emits through emit_json_success directly rather than the
        # CLI _emit_envelope funnel that resolves the active label, so it
        # must supply the label itself. On create the newly-created
        # profile IS the active one, so its name is the label; on edit
        # the active profile is not necessarily the edited one, so the
        # spine stays null (the label is not the wizard's to assert there).
        active_profile = profile_name if mode == "create" else None
        emit_json_success(command_path, payload, notices=notices, active_profile=active_profile)
        return

    lines = [
        f"{tr('application.wizard.output_labels.profile')}\t{profile_name}",
        f"{tr('application.wizard.output_labels.status')}\t{verb}",
    ]
    if mode == "create":
        lines.append(f"{tr('application.wizard.output_labels.active_profile')}\t{profile_name}")
    lines.append(f"{tr('application.wizard.output_labels.next')}\t{next_command}")
    if modify_no_resume:
        lines.append(resolved_modify_no_resume_message)
    if modify_descendants_via_door:
        lines.append(resolved_modify_descendants_message)
    if ccaa_defaulted:
        lines.append(ccaa_message)
    rendered = render_command_output(format_name="text", payload=payload, lines=lines)
    _typer.echo(rendered.text)


_SAVE_EXIT_RESUME_CODE = "config.profile.create.saved_resume_later"


def _emit_save_exit_notice(profile_name: str, *, message: str | None = None) -> None:
    """Emit the create-mode save-and-exit disclosure ('saved — resume later').

    A save-and-exit leaves the profile ``SETUP_INCOMPLETE``, so no
    created/active success is emitted. Instead an ``info``-severity
    :class:`Notice` states the setup was saved and its ``suggestion`` is the
    resume command (``config profile create`` re-enters the in-progress
    profile), so the operator is told how to continue rather than left with
    a silent exit.

    ``message`` carries the disclosure pre-rendered in the command-level
    output language (see :func:`_emit_wizard_success`); ``None`` resolves it
    now for the direct, walk-less callers.
    """
    import typer as _typer

    from ...core.click_context import json_output_requested
    from ...core.json_contract import Notice, NoticeSeverity, emit_json_success

    resume_command = f"aeat config profile create {profile_name}"
    if message is None:
        message = tr("application.wizard.notices.setup_saved_resume_later")
    notice = Notice(
        severity=NoticeSeverity.INFO,
        code=_SAVE_EXIT_RESUME_CODE,
        message=message,
        suggestion=resume_command,
    )
    if json_output_requested():
        emit_json_success(
            "config.profile.create",
            {"profile_name": profile_name},
            notices=[notice],
            active_profile=None,
        )
        return
    _typer.echo(f"{message}\t{resume_command}")


def _execute_wizard_command(
    flow: WizardFlow,
    mode: WizardPersistMode,
    *,
    kwargs: dict[str, object],
    interactive_flow_runner: InteractiveFlowRunner,
) -> None:
    """Run the wizard command body after Typer has parsed dynamic flags."""
    profile_name = _require_profile_name(flow, kwargs.pop("profile_name"))
    profile_id = _resolve_profile_id_for_mode(flow, mode, profile_name)
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
    modify_descendants_message = tr(
        "application.wizard.notices.modify_descendants_via_door",
        default="Descendants are not part of profile edit. Manage them with '{command}'.",
        command=_DESCENDIENTE_DOOR_COMMAND,
    )
    save_exit_message = tr("application.wizard.notices.setup_saved_resume_later")
    _refuse_foral_ccaa(canonical, explicit_flags)
    # Interactive create is the facts-as-checkpoint path: the store mints
    # the profile early in ``SETUP_INCOMPLETE`` state and persists each
    # answered fact through the lifecycle authority, backing save-and-exit.
    checkpoint_store = (
        ProfileFactsCheckpointStore(flow, profile_id=profile_id, profile_name=profile_name)
        if mode == "create" and not (quiet or accept_defaults)
        else None
    )
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
            interactive_flow_runner=interactive_flow_runner,
            checkpoint_store=checkpoint_store,
        )
    except ValidationError as exc:
        raise _wizard_validation_bad(flow, exc) from exc
    if checkpoint_store is not None and checkpoint_store.save_exit_persisted:
        # Save-and-exit: the frontend already surfaced the saved state and
        # the profile stays SETUP_INCOMPLETE for a later resume. Emitting a
        # created/active success here would be a lie, so the command surfaces
        # only the "saved — resume later" info notice.
        _emit_save_exit_notice(profile_name, message=save_exit_message)
        return
    # Every interactive modify run carries the LOUD staged-only disclosure on
    # its final envelope: mid-flow save/resume is unavailable and an
    # interrupted modify discards its staged edits. Non-interactive patch
    # edits (`--quiet` / `--accept-defaults`) stage nothing, so the notice is
    # scoped to the interactive walk.
    interactive_modify = mode == "edit" and not (quiet or accept_defaults)
    _emit_wizard_success(
        mode,
        profile_name,
        next_command=_next_step_command_for_profile_values(profile_values),
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
    interactive_flow_runner: InteractiveFlowRunner | None = None,
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

    ``interactive_flow_runner`` is the frontend seam an interactive walk
    renders through; it defaults to the line-mode frontend so the
    application layer stays self-sufficient, and the CLI entrypoint
    injects the capability-selecting runner that reaches the full-screen
    Textual frontend.
    """
    question_params = _question_parameters(flow)
    mode_params = _mode_parameters(flow)
    parameters = (*mode_params, *question_params)
    runner = interactive_flow_runner or _line_mode_interactive_runner

    def _command(**kwargs: object) -> None:
        import contextlib

        from ...core.errors import CadrumoError

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
            # When neither an explicit flag nor the environment pins the
            # language, bind a mid-walk activator so answering the first
            # (output-language) page re-renders the rest of the walk in the
            # chosen language; the override tears down with this stack.
            _activate_language = _build_mid_walk_language_activation(kwargs, _language_stack)
            active_runner = (
                functools.partial(runner, on_language_activated=_activate_language)
                if _activate_language is not None
                else runner
            )
            try:
                _execute_wizard_command(flow, mode, kwargs=kwargs, interactive_flow_runner=active_runner)
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
    typed.__signature__ = inspect.Signature(parameters=list(parameters))
    typed.__annotations__ = {param.name: param.annotation for param in parameters}
    typed.__name__ = flow.id
    typed.__doc__ = tr(f"wizard.{flow.id}.description")
    typed.__wizard_flow__ = flow
    return _command


__all__ = [
    "SETUP_FLOW",
    "InteractiveFlowRunner",
    "build_wizard_command",
]
