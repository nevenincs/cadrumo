"""Explainer and format-hint content contract for the setup flow."""

from __future__ import annotations

import pytest

from ....core.config import override_settings
from ....core.flows import CheckpointAvailability, FlowMode
from ....core.i18n import tr
from ...flows import assemble_page_copy, flow_definition_from_wizard_flow
from .._catalogue import SETUP_FLOW
from .._format_hints import PAGE_FORMAT_HINTS, attach_format_hints

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
    hinted = {
        item.id: item.format_hint.ref
        for section in definition.sections
        for item in section.items
        if getattr(item, "format_hint", None) is not None
    }
    assert hinted == dict(PAGE_FORMAT_HINTS)


def test_tax_id_page_copy_carries_the_identity_hint_in_spanish() -> None:
    definition = _definition()
    page = next(
        item for section in definition.sections for item in section.items if getattr(item, "id", "") == "tax-id"
    )
    with override_settings(cadrumo_output_language="es"):
        copy = assemble_page_copy(page)
    assert copy.format_hint, "tax-id page must carry a resolved format hint"
    assert "12345678Z" in copy.format_hint
