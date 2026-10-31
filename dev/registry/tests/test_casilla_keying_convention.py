"""Behavioral gate for canonical casilla lookup."""

from __future__ import annotations

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot
from cadrumo.domain.calculations.registry.tests import casilla_keying_convention_scenarios as scenarios
from dev.registry.compiler.authority import compiled_bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def _m303_2025_1t_snapshot() -> RegistrySnapshot:
    return compiled_bundled_authority().snapshot("303", filing_year=2025, period="1T")


@pytest.fixture(scope="module")
def _m200_2024_snapshot() -> RegistrySnapshot:
    return compiled_bundled_authority().snapshot(
        "200", filing_year=2025, period="0A", grade=RegistryAuthorityGrade.CALCULATION
    )


def test_runtime_accepts_canonical_casilla_id_for_semantic_input(_m303_2025_1t_snapshot: RegistrySnapshot) -> None:
    scenarios.check_runtime_accepts_canonical_casilla_id_for_semantic_input(_m303_2025_1t_snapshot)


def test_runtime_rejects_casilla_number_for_semantic_input(_m303_2025_1t_snapshot: RegistrySnapshot) -> None:
    scenarios.check_runtime_rejects_casilla_number_for_semantic_input(_m303_2025_1t_snapshot)


def test_noncanonical_reference_targets_include_export_refs_without_accepting_them_as_ids(
    _m303_2025_1t_snapshot: RegistrySnapshot,
) -> None:
    scenarios.check_noncanonical_reference_targets_include_export_refs_without_accepting_them_as_ids(
        _m303_2025_1t_snapshot
    )


def test_noncanonical_reference_targets_expose_ambiguous_reused_printed_number(
    _m200_2024_snapshot: RegistrySnapshot,
) -> None:
    scenarios.check_noncanonical_reference_targets_expose_ambiguous_reused_printed_number(_m200_2024_snapshot)
