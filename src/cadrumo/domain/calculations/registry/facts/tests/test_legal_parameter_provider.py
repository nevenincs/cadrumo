"""Parity tests for global legal-parameter fact projections."""

from __future__ import annotations

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.facts.legal_parameters import (
    LEGAL_PARAMETER_FACT_IDS,
    LEGAL_PARAMETER_PROVIDER_DIRECTORY,
    LEGAL_PARAMETER_PROVIDER_ID,
    compile_legal_parameter_facts,
)
from cadrumo.domain.calculations.registry.facts.providers import FACT_PROVIDER_REGISTRATIONS

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]
def test_provider_projects_no_retired_legal_parameter_ids() -> None:
    facts = compile_legal_parameter_facts(bundled_path("registry", "aeat"))

    assert frozenset() == LEGAL_PARAMETER_FACT_IDS
    assert facts == ()


def test_legal_parameter_provider_owns_the_existing_legal_catalogue() -> None:
    registration = next(item for item in FACT_PROVIDER_REGISTRATIONS if item.provider_id == LEGAL_PARAMETER_PROVIDER_ID)

    assert registration.owned_directories == (LEGAL_PARAMETER_PROVIDER_DIRECTORY,)
    assert registration.collect_fingerprints(bundled_path("registry", "aeat"))
