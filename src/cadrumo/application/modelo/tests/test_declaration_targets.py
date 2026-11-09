"""The new-declaration dialog offers each modelo the years the registry envelope admits, and names it once.

The envelope is the registry's one declaration of supported filing years. Inside
it, a year with no edition of its own is projected from the nearest authored
edition, so a modelo whose newest edition is older than the horizon is still
offered every later year up to it. Modelos 100, 189 and 714 were filed in every
envelope year, so each is offered all of them.
"""

from __future__ import annotations

import pytest

from ....core.external_constants import OutputLanguage
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ..declaration_targets import declaration_targets
from ..work_form_wording import modelo_name

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FILED_IN_EVERY_SUPPORTED_YEAR = ("100", "189", "714")


def _offered_years(operation: PinnedAuthorityOperation) -> dict[str, set[int]]:
    offered: dict[str, set[int]] = {}
    for target in declaration_targets(operation, profile=None):
        offered.setdefault(target.modelo, set()).add(target.period.filing_year)
    return offered


def test_modelos_filed_in_every_supported_year_are_offered_every_one(operation: PinnedAuthorityOperation) -> None:
    envelope = set(operation.supported_filing_years().years)
    offered = _offered_years(operation)

    assert {modelo: offered.get(modelo) for modelo in _FILED_IN_EVERY_SUPPORTED_YEAR} == {
        modelo: envelope for modelo in _FILED_IN_EVERY_SUPPORTED_YEAR
    }


def test_every_modelo_is_offered_an_unbroken_run_of_years_up_to_the_horizon(
    operation: PinnedAuthorityOperation,
) -> None:
    horizon = operation.supported_filing_years().horizon
    broken = {
        modelo: sorted(years)
        for modelo, years in _offered_years(operation).items()
        if set(range(min(years), horizon + 1)) != years
    }

    assert broken == {}


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_every_modelo_has_a_name_apart_from_its_number(
    operation: PinnedAuthorityOperation, language: OutputLanguage
) -> None:
    unnamed = {
        modelo: name
        for modelo in operation.modelo_ids()
        if (name := modelo_name(modelo, language)) is None or modelo in name
    }

    assert unnamed == {}
