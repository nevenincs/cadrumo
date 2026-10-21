"""Real-supervisor conformance matrix for every production executor."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

from ...core.operations import OperationEffect, OperationTerminalCondition
from .conformance_family_contract import ConformanceFamily, RegisteredExecutorConformanceCase
from .conformance_variants import CONFORMANCE_VARIANT_FAMILIES
from .registered_executor_conformance_expectations import (
    _EXPECTATIONS,
    _expectations_owned_once,
    _registered_definition_ids,
)
from .registered_executor_conformance_runner import _run_registered_executor_conformance_case

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_every_registered_definition_has_a_conformance_scenario() -> None:
    """The matrix's subjects are the registry's, in both directions.

    This is the census the hardcoded item list used to stand in for. It
    asserts membership, never a count: a tally would have to be edited
    every time an operation is composed, which trains everyone to update
    the constant and then detects nothing.
    """
    registered = set(_registered_definition_ids())
    declared = set(_EXPECTATIONS)

    assert not registered - declared, (
        "registered operations run through the supervisor with no conformance scenario, so this "
        f"matrix does not cover what its name claims: {sorted(registered - declared)}"
    )
    assert not declared - registered, (
        f"conformance scenarios name operations the production registry does not compose: {sorted(declared - registered)}"
    )


def test_a_second_scenario_for_one_operation_is_refused() -> None:
    """A family module cannot silently replace a scenario the matrix or another family owns."""
    owned = RegisteredExecutorConformanceCase(
        "diagnostics.read", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
    )
    rival = replace(owned, expected_effect=OperationEffect.UPDATED)

    with pytest.raises(AssertionError, match=r"diagnostics\.read declares more than one conformance scenario"):
        _expectations_owned_once((owned, rival))


@pytest.mark.parametrize("definition_id", _registered_definition_ids())
def test_every_production_registered_executor_runs_through_the_shared_supervisor_matrix(
    tmp_path: Path, definition_id: str, *, operation: PinnedAuthorityOperation
) -> None:
    """Every registered operation has exactly one primary composed-runtime witness."""
    case = _EXPECTATIONS.get(definition_id)
    assert case is not None, f"{definition_id} has no registered conformance scenario"
    _run_registered_executor_conformance_case(tmp_path, case, operation=operation)


@pytest.mark.parametrize(
    ("family", "case"),
    [(family, case) for family in CONFORMANCE_VARIANT_FAMILIES for case in family.cases],
    ids=[
        f"variant-{index}-{case.definition_id}"
        for index, family in enumerate(CONFORMANCE_VARIANT_FAMILIES)
        for case in family.cases
    ],
)
def test_registered_executor_material_and_refusal_variants(
    tmp_path: Path,
    family: ConformanceFamily,
    case: RegisteredExecutorConformanceCase,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Distinct local premises retain both source snapshots' material and negative oracles."""
    _run_registered_executor_conformance_case(tmp_path, case, operation=operation, family=family)
