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

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _wizard_descriptor_translation_keys() -> set[str]:
    from ..application.wizard.catalogue import WIZARD_FLOWS

    keys: set[str] = set()
    for flow in WIZARD_FLOWS:
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


def test_wizard_catalogue_materializes_bounded_dynamic_choice_keys() -> None:
    """Enum- and language-derived choice labels must be concrete descriptor keys."""
    from ..core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
    from ..domain.contribuyente.entity_type import EntityType
    from ..domain.contribuyente.renta_codes import FiscalResidency
    from ..domain.deadlines.models import IrpfIncomeCategory

    keys = _wizard_descriptor_translation_keys()

    expected = {
        *{
            f"wizard.setup.taxpayer-type.entity-type.choices.{member.value.replace('_', '-')}.label"
            for member in EntityType
        },
        *{
            f"wizard.setup.taxpayer-type.irpf-income-categories.choices.{member.value.replace('_', '-')}.label"
            for member in IrpfIncomeCategory
        },
        *{
            f"wizard.setup.residence.fiscal-residency.choices.{member.value.replace('_', '-')}.label"
            for member in FiscalResidency
        },
        *{f"wizard.setup.profile.output-language.choices.{language}.label" for language in SUPPORTED_OUTPUT_LANGUAGES},
    }

    assert expected <= keys
