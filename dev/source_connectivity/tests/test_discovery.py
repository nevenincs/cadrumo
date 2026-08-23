"""Mutation-shaped proofs that each capability detector expands independently."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..discovery import (
    discover_calculation_helpers,
    discover_ingress_surfaces,
    discover_row_assemblers,
    discover_secure_repositories,
    discover_source_readiness,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _write(root: Path, relative: str, source: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def test_new_secure_repository_is_detected_without_an_inventory_entry(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/cadrumo/domain/probe.py",
        """class ProbeRepository(SecureBoundRepository[ProbePayload]):
    payload_type = ProbePayload

    def extract_identifier(self, payload: ProbePayload) -> str:
        return payload.identifier
""",
    )

    rows = discover_secure_repositories(tmp_path)

    assert [(row.repository_name, row.payload_types) for row in rows] == [
        ("ProbeRepository", ("ProbePayload",)),
    ]


def test_new_cli_ingress_is_detected_from_command_and_write_policy(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/cadrumo/entrypoints/cli/probe.py",
        """@probe_app.command("ingest")
@command_execution_policy(PROBE_WRITE)
def ingest_probe() -> None:
    persist_probe()
""",
    )

    rows = discover_ingress_surfaces(tmp_path)

    assert [(row.command_name, row.execution_policy, row.channel) for row in rows] == [
        ("ingest", "PROBE_WRITE", "cli"),
    ]


def test_new_exported_calculation_helper_is_detected_independently(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/cadrumo/domain/probe/__init__.py",
        """__all__ = ["calculate_probe"]

def calculate_probe(left: Decimal, right: Decimal) -> Decimal:
    return left + right
""",
    )

    rows = discover_calculation_helpers(tmp_path)

    assert [(row.function_name, row.return_type, row.operation_kinds) for row in rows] == [
        ("calculate_probe", "Decimal", ("Add",)),
    ]


def test_new_source_readiness_declaration_is_detected_independently(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/cadrumo/domain/probe.py",
        """def probe_source_readiness() -> ProbeSourceReadiness:
    return ProbeSourceReadiness(ready=False, source_kind=PROBE_SOURCE_KIND, reason="not connected")
""",
    )

    rows = discover_source_readiness(tmp_path)

    assert [(row.function_name, row.readiness_type, row.source_kind_expression) for row in rows] == [
        ("probe_source_readiness", "ProbeSourceReadiness", "PROBE_SOURCE_KIND"),
    ]


def test_new_row_grouping_and_typed_assembler_are_detected_together(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/cadrumo/application/calculations/_row_set_assembly.py",
        """_GROUPING_DISPATCH: Mapping[str, RowSetGroupingKind] = {
    "per_probe": RowSetGroupingKind.PROBE,
}

def assemble_observations_for_grouping(grouping: str) -> AssembledObservations:
    source_kind = _GROUPING_DISPATCH.get(grouping)
    if source_kind == RowSetGroupingKind.PROBE:
        return (source_kind, assemble_probe_observations())
    raise ValueError(grouping)

def assemble_probe_observations() -> tuple[ProbeObservation, ...]:
    return ()
""",
    )

    rows = discover_row_assemblers(tmp_path)

    assert [
        (row.grouping, row.source_kind, row.assembler_name, row.observation_return_type)
        for row in rows
    ] == [
        (
            "per_probe",
            "RowSetGroupingKind.PROBE",
            "assemble_probe_observations",
            "tuple[ProbeObservation, ...]",
        ),
    ]
