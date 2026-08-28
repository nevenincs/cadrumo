"""Revision integrity must content-address immutable filing evidence."""

from __future__ import annotations

import ast
import inspect
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....core import Period, validated_casilla_id
from ....core.directory_scan import scan_directory
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....tests.filing_evidence import general_m303_filing_evidence
from .._action_errors import StoredCalculationDriftError
from .._registry_helpers import assert_revision_content_integrity

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _m303_revision() -> CalculationRevision:
    evidence = general_m303_filing_evidence(
        Period.from_year_and_code(2026, "1T"),
        reference="test:revision-integrity:m303",
    )
    work_unit_id = "a" * 64
    input_id = validated_casilla_id("01", surface="integrity test input")
    inputs = {input_id: "100.00"}
    outputs = {}
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id=inputs,
        binding_overrides={},
        casilla_values=outputs,
        filing_instance_evidence=evidence,
        source_provenance=(),
    )
    instant = datetime(2026, 4, 20, 10, 0, tzinfo=UTC)
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id=inputs,
        binding_overrides={},
        casilla_values=outputs,
        filing_instance_evidence=evidence,
        created_at=instant,
        updated_at=instant,
        source_provenance=(),
    )


def test_evidence_bearing_m303_revision_passes_content_integrity() -> None:
    assert_revision_content_integrity(_m303_revision())


def test_changed_m303_evidence_with_stored_identity_is_rejected() -> None:
    original = _m303_revision()
    assert original.filing_instance_evidence is not None
    assert original.filing_instance_evidence.m303 is not None
    changed = original.model_copy(
        update={
            "filing_instance_evidence": original.filing_instance_evidence.model_copy(
                update={
                    "m303": original.filing_instance_evidence.m303.model_copy(
                        update={"joint_return_elected": True},
                    ),
                },
            ),
        },
    )

    with pytest.raises(StoredCalculationDriftError, match="content-address mismatch"):
        assert_revision_content_integrity(changed)


def test_all_revision_id_calls_explicitly_select_filing_evidence() -> None:
    """Omission syntax is forbidden across production and test identity callers."""
    source_root = Path(__file__).parents[3]
    omissions: list[str] = []
    for path in scan_directory(source_root, pattern="*.py", recursive=True):
        if path.name == "_calculation_revision.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", None)
            if name != "derive_calculation_revision_id":
                continue
            if not any(keyword.arg == "filing_instance_evidence" for keyword in node.keywords):
                omissions.append(f"{path.relative_to(source_root)}:{node.lineno}")

    assert omissions == []


def test_revision_id_filing_evidence_has_no_default_and_cannot_be_omitted() -> None:
    parameter = inspect.signature(derive_calculation_revision_id).parameters["filing_instance_evidence"]
    assert parameter.default is inspect.Parameter.empty

    with pytest.raises(TypeError, match="filing_instance_evidence"):
        inspect.signature(derive_calculation_revision_id).bind(
            work_unit_id="a" * 64,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            source_provenance=(),
        )


def test_all_revision_id_calls_explicitly_select_source_provenance() -> None:
    """Every identity caller records either the canonical trace or explicit emptiness."""
    source_root = Path(__file__).parents[3]
    omissions: list[str] = []
    for path in scan_directory(source_root, pattern="*.py", recursive=True):
        if path.name == "_calculation_revision.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", None)
            if name != "derive_calculation_revision_id":
                continue
            if not any(keyword.arg == "source_provenance" for keyword in node.keywords):
                omissions.append(f"{path.relative_to(source_root)}:{node.lineno}")

    assert omissions == []


def test_revision_id_source_provenance_has_no_default_and_cannot_be_omitted() -> None:
    parameter = inspect.signature(derive_calculation_revision_id).parameters["source_provenance"]
    assert parameter.default is inspect.Parameter.empty

    with pytest.raises(TypeError, match="source_provenance"):
        inspect.signature(derive_calculation_revision_id).bind(
            work_unit_id="a" * 64,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            filing_instance_evidence=None,
        )
