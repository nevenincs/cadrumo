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


def test_secure_repository_behind_a_typed_store_port_remains_discoverable(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/cadrumo/application/probe.py",
        """class ProbeRepository:
    def __init__(self, objects: ProbeSecureObjectStorePort) -> None:
        self._objects = objects

    def save(self, payload: ProbePayload) -> None:
        self._objects.save(payload)
""",
    )

    rows = discover_secure_repositories(tmp_path)

    assert [(row.repository_name, row.payload_types, row.mechanism) for row in rows] == [
        ("ProbeRepository", ("ProbePayload",), "secure_object"),
    ]


def test_secure_port_name_outside_constructor_does_not_certify_plaintext_repository(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/cadrumo/application/probe.py",
        """class PlainRepository:
    marker: BogusSecureObjectStorePort

    def save(self, payload: PlainPayload) -> None:
        write_plaintext(payload)
""",
    )

    assert discover_secure_repositories(tmp_path) == ()


def test_unused_bogus_secure_port_constructor_marker_does_not_certify_plaintext_repository(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/cadrumo/application/probe.py",
        """class PlainRepository:
    def __init__(self, marker: BogusSecureObjectStorePort) -> None:
        self._marker = marker

    def save(self, payload: PlainPayload) -> None:
        write_plaintext(payload)
""",
    )

    assert discover_secure_repositories(tmp_path) == ()


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


def test_new_command_spec_ingress_is_detected_without_a_typer_decorator(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/cadrumo/entrypoints/cli/_probe_command_specs.py",
        """PROBE_WRITE = ExecutionPolicySpec(
    capabilities=frozenset({"encrypted-facts"}),
    side_effects=frozenset({"local-state"}),
    performance="local-io",
    write_route="profile-bound",
)

PROBE_COMMAND_SPECS = (
    CommandSpec(
        key="probe_add",
        parent_key="probe",
        token="add",
        kind="leaf",
        policy=PROBE_WRITE,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._probe", "probe_add")
        ),
    ),
)
""",
    )
    _write(
        tmp_path,
        "src/cadrumo/entrypoints/cli/_probe.py",
        "def probe_add() -> None:\n    pass\n",
    )

    rows = discover_ingress_surfaces(tmp_path)

    assert [
        (
            row.capability_id,
            row.evidence_locator,
            row.command_name,
            row.execution_policy,
        )
        for row in rows
    ] == [
        (
            "ingress:src/cadrumo/entrypoints/cli/_probe.py:probe_add",
            "src/cadrumo/entrypoints/cli/_probe_command_specs.py:9",
            "add",
            "PROBE_WRITE",
        )
    ]


def test_command_spec_leaf_resolves_declared_and_fallback_handlers_without_execution(tmp_path: Path) -> None:
    """Structural discovery must retain `_leaf`'s exact handler declaration semantics."""
    _write(
        tmp_path,
        "src/cadrumo/entrypoints/cli/_probe_command_specs.py",
        """PROBE_WRITE = ExecutionPolicySpec(
    capabilities=frozenset({"encrypted-facts"}),
    side_effects=frozenset({"local-state"}),
    performance="local-io",
    write_route="profile-bound",
)

def _leaf(token, module, policy, *, handler_name=None):
    name = token.replace("-", "_")
    return CommandSpec(
        key=f"probe_{name}",
        parent_key="probe",
        token=token,
        kind="leaf",
        policy=policy,
        handler=LazyBinding.available(
            DeferredTarget(module, handler_name or f"work_{name}")
        ),
    )

PROBE_COMMAND_SPECS = (
    _leaf("fallback-handler", "cadrumo.entrypoints.cli._probe", PROBE_WRITE),
    _leaf("explicit-handler", "cadrumo.entrypoints.cli._probe", PROBE_WRITE, handler_name="record_probe"),
)
""",
    )
    _write(
        tmp_path,
        "src/cadrumo/entrypoints/cli/_probe.py",
        "def work_fallback_handler() -> None:\n    pass\n\ndef record_probe() -> None:\n    pass\n",
    )

    rows = discover_ingress_surfaces(tmp_path)

    assert [(row.command_name, row.callback_name) for row in rows] == [
        ("fallback-handler", "work_fallback_handler"),
        ("explicit-handler", "record_probe"),
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


def test_public_definition_module_needs_no_package_facade_redeclaration(tmp_path: Path) -> None:
    _write(tmp_path, "src/cadrumo/domain/probe/__init__.py", "__all__: list[str] = []\n")
    _write(
        tmp_path,
        "src/cadrumo/domain/probe/calculations.py",
        """def calculate_probe(left: Decimal, right: Decimal) -> Decimal:
    return left + right
""",
    )

    rows = discover_calculation_helpers(tmp_path)

    assert [(row.module, row.function_name) for row in rows] == [
        ("src/cadrumo/domain/probe/calculations.py", "calculate_probe"),
    ]


def test_colocated_conftest_function_is_not_a_production_capability(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/cadrumo/domain/probe/conftest.py",
        """def calculate_fixture(left: Decimal, right: Decimal) -> Decimal:
    return left + right
""",
    )

    assert discover_calculation_helpers(tmp_path) == ()


def test_public_filename_inside_private_subpackage_is_not_a_public_surface(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/cadrumo/domain/probe/_internal/calculations.py",
        """def calculate_internal(left: Decimal, right: Decimal) -> Decimal:
    return left + right
""",
    )

    assert discover_calculation_helpers(tmp_path) == ()


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
        "src/cadrumo/application/calculations/row_set_assembly.py",
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

    assert [(row.grouping, row.source_kind, row.assembler_name, row.observation_return_type) for row in rows] == [
        (
            "per_probe",
            "RowSetGroupingKind.PROBE",
            "assemble_probe_observations",
            "tuple[ProbeObservation, ...]",
        ),
    ]
