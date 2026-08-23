"""Exact-set and import gates for generated CLI registration metadata."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import textwrap
from importlib.resources import files
from pathlib import Path
from typing import cast

import pytest
from dev.quality.generate_command_registration_metadata import _source_sha256, metadata_differences

from .._command_schema import command_registration_projection
from .._verb_input_schema import DECLARED_UNIMPLEMENTED_SURFACES

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_RESOURCE = "command_registration_metadata.v1.json"
_GENERATOR = Path("dev/quality/generate_command_registration_metadata.py")


def _payload() -> dict[str, object]:
    decoded = json.loads(files("cadrumo.entrypoints.cli").joinpath(_RESOURCE).read_text(encoding="utf-8"))
    assert isinstance(decoded, dict)
    return cast("dict[str, object]", decoded)


def test_projection_is_cached_immutable_and_declared_gaps_are_exact() -> None:
    first = command_registration_projection()
    second = command_registration_projection()

    assert first is second
    assert first.commands
    assert first.nodes
    assert tuple(row.command for row in first.commands) == tuple(sorted(row.command for row in first.commands))
    assert tuple(node.path for node in first.nodes) == tuple(sorted(node.path for node in first.nodes))
    assert {row.command for row in first.commands if row.cli_path is None} == set(DECLARED_UNIMPLEMENTED_SURFACES)
    assert all(row.schema_owner and row.schema_source_sha256 for row in first.commands)
    assert all(node.handler_owner == "<none>" or node.source_sha256 for node in first.nodes)


def test_generated_projection_matches_both_localized_materialized_trees() -> None:
    completed = subprocess.run(  # noqa: S603 - fixed interpreter, generator, and check flag
        [sys.executable, "-I", str(_GENERATOR.resolve()), "--check"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_source_fingerprints_are_newline_invariant_and_semantic(tmp_path: Path) -> None:
    lf = tmp_path / "lf.py"
    crlf = tmp_path / "crlf.py"
    changed = tmp_path / "changed.py"
    lf.write_bytes(b"VALUE = 1\n")
    crlf.write_bytes(b"VALUE = 1\r\n")
    changed.write_bytes(b"VALUE = 2\n")

    assert _source_sha256(lf) == _source_sha256(crlf)
    assert _source_sha256(lf) != _source_sha256(changed)


def test_schema_and_operator_inventory_import_no_handler_or_forbidden_authority() -> None:
    expected_commands = len(command_registration_projection().commands) - len(DECLARED_UNIMPLEMENTED_SURFACES)
    script = textwrap.dedent(
        """
        import json
        import sys
        from cadrumo.entrypoints.cli._command_schema import command_registration_projection
        from cadrumo.entrypoints.cli._common import _current_operator_surface_schema_inventory

        projection = command_registration_projection()
        owners = {
            owner.split(":", 1)[0]
            for row in projection.commands
            for owner in (row.handler_owner, row.schema_owner)
            if owner is not None
        }
        before = set(sys.modules)
        inventory = _current_operator_surface_schema_inventory()
        loaded = set(sys.modules) - before
        forbidden_prefixes = (
            "cadrumo.domain.calculations.registry",
            "cadrumo.adapters.persistence.storage",
            "cadrumo.application.user_profile",
            "cryptography",
            "keyring",
        )
        print(json.dumps({
            "commands": len(inventory.command_keys),
            "handler_owners": sorted(owners & loaded),
            "forbidden": sorted(
                name for name in loaded
                if any(name == prefix or name.startswith(prefix + ".") for prefix in forbidden_prefixes)
            ),
        }))
        """
    )
    completed = subprocess.run(  # noqa: S603 - fixed interpreter and in-tree constant probe
        [sys.executable, "-I", "-c", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=True,
    )
    observation = json.loads(completed.stdout)

    assert observation == {"commands": expected_commands, "handler_owners": [], "forbidden": []}


@pytest.mark.parametrize(
    "mutation",
    (
        "missing-node",
        "invented-node",
        "option-default",
        "option-type",
        "localized-help",
        "policy",
        "source-sha",
        "declared-gap-set",
    ),
)
def test_projection_drift_detector_bites_on_every_registration_axis(mutation: str) -> None:
    expected = _payload()
    observed = copy.deepcopy(expected)
    commands = cast("list[dict[str, object]]", observed["commands"])
    nodes = cast("list[dict[str, object]]", observed["nodes"])

    if mutation == "missing-node":
        nodes.pop()
    elif mutation == "invented-node":
        invented = copy.deepcopy(nodes[-1])
        invented["path"] = ["aeat", "planted-future-node"]
        nodes.append(invented)
    elif mutation in {"option-default", "option-type"}:
        row = next(row for row in commands if cast("dict[str, object]", row["parameters_by_language"])["es"])
        parameters = cast("dict[str, list[dict[str, object]]]", row["parameters_by_language"])
        if mutation == "option-default":
            parameters["es"][0]["default"] = "planted-default"
        else:
            parameters["es"][0]["json_type"] = "boolean"
    elif mutation == "localized-help":
        cast("dict[str, str]", commands[0]["help_by_language"])["en"] += " planted"
    elif mutation == "policy":
        row = next(row for row in commands if row["policy"] is not None)
        cast("dict[str, object]", row["policy"])["destructive"] = "planted"
    elif mutation == "source-sha":
        commands[0]["source_sha256"] = "0" * 64
    else:
        row = next(row for row in commands if row["cli_path"] is None)
        row["cli_path"] = ["config", "planted-gap"]

    assert metadata_differences(expected, observed), f"detector accepted planted {mutation} drift"
