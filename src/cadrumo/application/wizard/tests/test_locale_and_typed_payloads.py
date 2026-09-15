"""Wizard locale routing contracts.

The wizard catalogue materializes bounded dynamic choice translation keys in
its runtime descriptors.

See Also:
    :mod:`~application.wizard`
        Wizard descriptor package whose bounded dynamic locale keys are
        materialized at runtime.
"""

from __future__ import annotations

import pytest

from cadrumo.application.wizard.models import WizardFlow
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.entity_type import entity_type_tokens
from cadrumo.domain.calculations.registry.irpf_income_categories import irpf_income_category_choices
from cadrumo.domain.calculations.registry.renta_codes_catalogue import fiscal_residency_choices

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _wizard_descriptor_translation_keys(*, registry_setup_flow: WizardFlow) -> set[str]:
    keys: set[str] = set()
    flow = registry_setup_flow
    keys.add(str(flow.title))
    keys.add(str(flow.description))
    for section in flow.sections:
        keys.add(str(section.title))
        for question in section.questions:
            keys.add(str(question.prompt))
            if question.help is not None:
                keys.add(str(question.help))
            for choice in question.choices:
                keys.add(str(choice.label))
                if choice.description is not None:
                    keys.add(str(choice.description))
    return keys


# ---------------------------------------------------------------------------
# Wizard bounded dynamic keys materialize in descriptors
# ---------------------------------------------------------------------------


def test_wizard_catalogue_materializes_bounded_dynamic_choice_keys(*, registry_setup_flow: WizardFlow) -> None:
    """Enum- and language-derived choice labels must be concrete descriptor keys."""
    from ....core.external_constants import SUPPORTED_OUTPUT_LANGUAGES

    keys = _wizard_descriptor_translation_keys(registry_setup_flow=registry_setup_flow)

    with bundled_indexed_authority().operation() as operation:
        expected = {
            *{
                f"wizard.setup.taxpayer-type.entity-type.choices.{member.value.replace('_', '-')}.label"
                for member in entity_type_tokens(authority=operation)
            },
            *{
                f"wizard.setup.taxpayer-type.irpf-income-categories.choices.{member.value.replace('_', '-')}.label"
                for member in irpf_income_category_choices(authority=operation)
            },
            *{
                f"wizard.setup.residence.fiscal-residency.choices.{member.value.replace('_', '-')}.label"
                for member in fiscal_residency_choices(authority=operation)
            },
            *{
                f"wizard.setup.profile.output-language.choices.{language}.label"
                for language in SUPPORTED_OUTPUT_LANGUAGES
            },
        }

    assert expected <= keys
