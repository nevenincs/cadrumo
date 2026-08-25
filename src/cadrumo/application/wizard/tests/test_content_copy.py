"""Explainer and format-hint content contract for the setup flow."""

from __future__ import annotations

import pytest

from ....core.config import override_settings
from ....core.flows import CheckpointAvailability, FlowMode, FlowWidgetKind
from ....core.i18n import tr
from ...flows.copy import assemble_page_copy
from ...flows.definition import FlowPage
from ...flows.engine import answer, start_flow
from ...flows.wizard_projection import flow_definition_from_wizard_flow
from ..catalogue import SETUP_FLOW
from .._format_hints import PAGE_FORMAT_HINTS, PAGE_WIDGET_KINDS, attach_format_hints

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LOCALES = ("en", "es", "ca", "hu")


def _definition():
    return attach_format_hints(
        flow_definition_from_wizard_flow(
            SETUP_FLOW,
            checkpoint={
                FlowMode.CREATE: CheckpointAvailability.UNAVAILABLE,
                FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
            },
        ),
    )


def test_every_declared_choice_description_resolves_in_all_locales() -> None:
    """A description ref that does not resolve would refuse loudly at render."""
    checked = 0
    for section in SETUP_FLOW.sections:
        for question in section.questions:
            for choice in question.choices:
                if choice.description is None:
                    continue
                for locale in _LOCALES:
                    with override_settings(cadrumo_output_language=locale):
                        rendered = tr(str(choice.description))
                    assert rendered != str(choice.description), (choice.value, locale)
                    checked += 1
    assert checked >= 25 * len(_LOCALES)


def test_decision_pages_carry_choice_explainers() -> None:
    """The pick-consequence pages each explain every offered option."""
    fully_described = {
        "entity-type",
        "irpf-income-categories",
        "iva-regime",
        "irpf-estimation-regime",
        "fiscal-residency",
        "situacion-familiar",
        "taxpayer-disability-grade",
        "taxation-type",
    }
    for section in SETUP_FLOW.sections:
        for question in section.questions:
            if question.id in fully_described:
                assert question.choices, question.id
                missing = [c.value for c in question.choices if c.description is None]
                assert not missing, (question.id, missing)


def test_format_hints_attach_to_exactly_the_mapped_pages() -> None:
    definition = _definition()
    hinted: dict[str, str] = {}
    for section in definition.sections:
        for item in section.items:
            if isinstance(item, FlowPage) and item.format_hint is not None:
                hinted[item.id] = item.format_hint.ref
    assert hinted == dict(PAGE_FORMAT_HINTS)


def test_widget_kinds_assigned_to_exactly_the_mapped_pages() -> None:
    """DATE / DECIMAL land on exactly the mapped pages and nowhere else.

    The bridge never emits DATE or DECIMAL (the wizard widget set has no
    such members), so every shape-validated page in the decorated
    definition originates from :data:`PAGE_WIDGET_KINDS`.
    """
    definition = _definition()
    shape_widgets = {FlowWidgetKind.DATE, FlowWidgetKind.DECIMAL}
    assigned: dict[str, FlowWidgetKind] = {}
    for section in definition.sections:
        for item in section.items:
            if isinstance(item, FlowPage) and item.widget in shape_widgets:
                assigned[item.id] = item.widget
    assert assigned == dict(PAGE_WIDGET_KINDS)


def test_shape_widget_pages_stay_valid_non_choice_pages() -> None:
    """Every overridden page keeps ``answer_type = str`` and no choices."""
    definition = _definition()
    overridden = {
        item.id: item
        for section in definition.sections
        for item in section.items
        if getattr(item, "id", "") in PAGE_WIDGET_KINDS
    }
    assert set(overridden) == set(PAGE_WIDGET_KINDS)
    for page_id, page in overridden.items():
        assert isinstance(page, FlowPage), page_id
        assert page.answer_type is str, page_id
        assert page.choices == (), page_id


def test_date_page_shape_validation_refuses_then_commits_through_the_engine() -> None:
    """Drive a real DATE page: malformed refuses as a verdict, ISO commits."""
    definition = _definition()
    state = start_flow(definition, mode=FlowMode.CREATE)

    rejected = answer(definition, state, "activity-start-date", "not-a-date")
    assert "activity-start-date" not in rejected.answers
    verdicts = rejected.verdicts["activity-start-date"]
    assert len(verdicts) == 1
    assert verdicts[0].ok is False
    assert verdicts[0].message_key == "flows.errors.invalid_date"

    committed = answer(definition, state, "activity-start-date", "2020-12-31")
    assert committed.answers["activity-start-date"] == "2020-12-31"
    assert "activity-start-date" not in committed.verdicts


def test_decimal_page_shape_validation_refuses_then_commits_through_the_engine() -> None:
    """Drive a real DECIMAL page: non-numeric refuses as a verdict, Decimal commits."""
    definition = _definition()
    state = start_flow(definition, mode=FlowMode.CREATE)

    rejected = answer(definition, state, "incn-prior-12-months", "not-a-number")
    assert "incn-prior-12-months" not in rejected.answers
    verdicts = rejected.verdicts["incn-prior-12-months"]
    assert len(verdicts) == 1
    assert verdicts[0].ok is False
    assert verdicts[0].message_key == "flows.errors.invalid_decimal"

    committed = answer(definition, state, "incn-prior-12-months", "1234.56")
    assert committed.answers["incn-prior-12-months"] == "1234.56"
    assert "incn-prior-12-months" not in committed.verdicts


def test_tax_id_page_copy_carries_the_identity_hint_in_spanish() -> None:
    definition = _definition()
    page = next(
        item for section in definition.sections for item in section.items if getattr(item, "id", "") == "tax-id"
    )
    assert isinstance(page, FlowPage)
    with override_settings(cadrumo_output_language="es"):
        copy = assemble_page_copy(page)
    assert copy.format_hint, "tax-id page must carry a resolved format hint"
    assert "12345678Z" in copy.format_hint
