"""Parity tests for global legal-parameter fact projections."""

from __future__ import annotations

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from dev.registry.compiler.legal_parameters import (
    LEGAL_PARAMETER_FACT_IDS,
    LEGAL_PARAMETER_PROVIDER_DIRECTORY,
    LEGAL_PARAMETER_PROVIDER_ID,
    collect_legal_parameter_fact_fingerprints,
    compile_legal_parameter_facts,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_provider_projects_no_retired_legal_parameter_ids() -> None:
    facts = compile_legal_parameter_facts(bundled_path("registry", "aeat"))

    assert frozenset() == LEGAL_PARAMETER_FACT_IDS
    assert facts == ()


def test_legal_parameter_projection_reads_the_existing_legal_catalogue() -> None:
    assert LEGAL_PARAMETER_PROVIDER_DIRECTORY == "legal"
    assert LEGAL_PARAMETER_PROVIDER_ID == "global-legal-parameters"
    assert collect_legal_parameter_fact_fingerprints(bundled_path("registry", "aeat"))
