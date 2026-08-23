"""CI boundary gates for the production-owned command authority."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from cadrumo.entrypoints.cli.command_api import command_spec_nodes

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_RUNTIME_ARTIFACTS = frozenset(
    {
        "app_lazy_manifest.v1.json",
        "command_registration_metadata.v1.json",
    }
)


def _assert_no_runtime_artifact_edge(source: str) -> None:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value in _RUNTIME_ARTIFACTS:
            raise AssertionError(f"forbidden generated command artifact: {node.value}")
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            assert not node.module.startswith("dev")


def test_ci_observes_every_production_node_through_the_public_api() -> None:
    nodes = command_spec_nodes()
    assert nodes
    assert len(nodes) == len({node.spec.key for node in nodes})
    assert len(nodes) == len({node.path for node in nodes})
    assert all(node.path[-1] == node.spec.token for node in nodes)


def test_production_has_no_dev_or_generated_runtime_artifact_edge() -> None:
    root = Path(__file__).parents[3]
    for path in (root / "src/cadrumo").rglob("*.py"):
        if "tests" not in path.parts:
            _assert_no_runtime_artifact_edge(path.read_text(encoding="utf-8"))


def test_forbidden_import_and_artifact_detectors_bite_independently() -> None:
    with pytest.raises(AssertionError, match="forbidden generated command artifact"):
        _assert_no_runtime_artifact_edge("RESOURCE = 'app_lazy_manifest.v1.json'")
    with pytest.raises(AssertionError):
        _assert_no_runtime_artifact_edge("from dev.quality import command_manifest")
