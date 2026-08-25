"""One-way projection of the wizard catalogue into flow definitions.

The one-shot wizard catalogue (:mod:`cadrumo.application.wizard`)
remains the authoring source of the setup questions: it keeps feeding
the ``compile_profile_keys`` projection and the
``register_wizard_catalogue`` / ``register_project_answers`` core slots
exactly as before. This module
adds the one-way projection from that vocabulary into the substrate's
:class:`FlowDefinition` so the engine and its frontends can drive the
same questions without a second authored catalogue — one source, two
descriptor views, zero drift by construction.

The mapping is mechanical: question ids become page keys unchanged,
``profile_key`` becomes ``domain_key``, the translation-key prompt and
help become locale-key :class:`CopyRef` references, and the
``visible_when`` clause shapes carry over one-to-one. Nothing here
re-derives requirement or visibility semantics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.flows import CheckpointAvailability, CopyRefKind, FlowMode, FlowWidgetKind
from .definition import (
    CopyRef,
    FlowChoice,
    FlowCondition,
    FlowDefinition,
    FlowPage,
    FlowSection,
    FlowVisibility,
)

if TYPE_CHECKING:
    from ..wizard import (
        WizardChoice,
        WizardCondition,
        WizardFlow,
        WizardQuestion,
        WizardSection,
        WizardVisibility,
    )


def flow_definition_from_wizard_flow(
    flow: WizardFlow,
    *,
    checkpoint: dict[FlowMode, CheckpointAvailability],
) -> FlowDefinition:
    """Project a wizard descriptor into a substrate flow definition.

    ``checkpoint`` is supplied by the caller because the per-mode
    declaration is a flow-surface decision the one-shot descriptor
    never carried.
    """
    return FlowDefinition(
        id=flow.id,
        title=_locale_ref(str(flow.title)),
        description=_locale_ref(str(flow.description)),
        sections=tuple(_section(section) for section in flow.sections),
        answers_model=flow.answers_model,
        checkpoint=checkpoint,
    )


def _section(section: WizardSection) -> FlowSection:
    return FlowSection(
        id=section.id,
        title=_locale_ref(str(section.title)),
        items=tuple(_page(question) for question in section.questions),
    )


def _page(question: WizardQuestion) -> FlowPage:
    # The one-shot catalogue declares several closed sets as TEXT
    # questions carrying choices (free text validated against the set).
    # The substrate's page model renders a closed set as a selectable
    # list, never free text, so the projection upgrades those to SELECT —
    # same accepted values, same blank-optional semantics.
    widget = FlowWidgetKind(question.widget.value)
    if widget is FlowWidgetKind.TEXT and question.choices:
        widget = FlowWidgetKind.SELECT
    return FlowPage(
        id=question.id,
        widget=widget,
        prompt=_locale_ref(str(question.prompt)),
        help=_locale_ref(str(question.help)) if question.help is not None else None,
        choices=tuple(_choice(choice) for choice in question.choices),
        default=question.default,
        required=question.required,
        visible_when=_visibility(question.visible_when),
        answer_type=question.answer_type,
        domain_key=question.profile_key,
    )


def _choice(choice: WizardChoice) -> FlowChoice:
    return FlowChoice(
        value=choice.value,
        label=_locale_ref(str(choice.label)),
        description=_locale_ref(str(choice.description)) if choice.description is not None else None,
    )


def _visibility(
    visible_when: WizardCondition | WizardVisibility | None,
) -> FlowCondition | FlowVisibility | None:
    if visible_when is None:
        return None
    from ..wizard import WizardCondition as _WizardCondition

    if isinstance(visible_when, _WizardCondition):
        return _condition(visible_when)
    return FlowVisibility(any_of=tuple(_condition(clause) for clause in visible_when.any_of))


def _condition(condition: WizardCondition) -> FlowCondition:
    return FlowCondition(
        page_id=condition.question_id,
        equals=condition.equals,
        contains=condition.contains,
    )


def _locale_ref(key: str) -> CopyRef:
    return CopyRef(kind=CopyRefKind.LOCALE_KEY, ref=key)


__all__ = ["flow_definition_from_wizard_flow"]
