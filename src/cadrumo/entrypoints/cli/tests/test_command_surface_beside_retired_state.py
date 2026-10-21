"""Metadata stays storage-free while selected-root retired databases are refused.

The command manifest reads the pinned registry without touching taxpayer
storage. Commands that read the selected storage root still refuse a retired
``aeat.db`` there and leave its bytes untouched. Each case uses a fresh
interpreter so settings resolve against the child's process environment.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cadrumo.tests.cli_fixture_ports import FreshCliInvocation

from ....domain.calculations.registry.authority import bundled_indexed_authority

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_RETIRED_MARKER = b"retired-aeat-state-must-remain"
#: Keep the isolated selected root and the session's published authority only.
_STRIPPED_PREFIXES = ("AEAT_", "PYTEST_", "CADRUMO_")


def _selected_root_with_retired_database(tmp_path: Path) -> tuple[dict[str, str], Path]:
    """Select isolated storage containing the recognizable retired database."""
    storage = tmp_path / "storage"
    storage.mkdir()
    retired = storage / "aeat.db"
    retired.write_bytes(_RETIRED_MARKER)
    return {"CADRUMO_LOCAL_STORAGE_ROOT": str(storage)}, retired


def _assert_retired_state_untouched(retired: Path) -> None:
    assert sorted(entry.name for entry in retired.parent.iterdir()) == ["aeat.db"]
    assert retired.read_bytes() == _RETIRED_MARKER


def test_the_command_surface_manifest_carries_the_published_modelos_beside_a_retired_database(
    tmp_path: Path, fresh_cli: FreshCliInvocation
) -> None:
    environment, retired = _selected_root_with_retired_database(tmp_path)
    with bundled_indexed_authority().operation() as operation:
        published_modelos = sorted(operation.modelo_ids())

    completed = fresh_cli(
        ["--cadrumo-command-surface"],
        env_strip_prefixes=_STRIPPED_PREFIXES,
        extra_env=environment,
        cwd=tmp_path,
        program_name="aeat",
    ).completed

    assert completed.returncode == 0, completed.stderr[-4000:]
    manifest = json.loads(completed.stdout)
    modelo = next(
        parameter
        for parameter in manifest["input_schemas"]["modelo.history"]["parameters"]
        if parameter["name"] == "modelo"
    )
    assert modelo["choices"] == published_modelos
    # The command-to-operation join is recorded beside the graph, so describing
    # it asks neither the storage root nor an operation registry for anything.
    join = manifest["command_operations"]
    submitted = {tuple(row["cli_path"]): row["operation_ids"] for row in join["commands"]}
    submitters = {row["operation_id"]: row["cli_paths"] for row in join["operations"]}
    assert submitted["app", "ledger", "add"] == ["ledger.add"]
    assert submitters["ledger.add"] == [["app", "ledger", "add"]]
    _assert_retired_state_untouched(retired)


def test_a_storage_command_refuses_a_retired_database_in_the_selected_root(
    tmp_path: Path, fresh_cli: FreshCliInvocation
) -> None:
    environment, retired = _selected_root_with_retired_database(tmp_path)

    completed = fresh_cli(
        ["config", "profile", "list"],
        env_strip_prefixes=_STRIPPED_PREFIXES,
        extra_env={**environment, "CADRUMO_OUTPUT_LANGUAGE": "en"},
        cwd=tmp_path,
        program_name="aeat",
    ).completed

    combined = f"{completed.stdout}\n{completed.stderr}"
    assert completed.returncode != 0, combined
    assert "Traceback" not in combined
    assert "incompatible retired `aeat` database" in combined
    assert "storage.former_product_state.absent" in combined
    _assert_retired_state_untouched(retired)
