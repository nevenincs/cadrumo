"""Detector teeth for verifier interpreting-input stability."""

from __future__ import annotations

from pathlib import Path

import pytest

from dev._paths import REPO_ROOT
from dev.registry.registry_collapse_inputs import _tool_input_paths
from dev.registry.registry_collapse_run import _tool_fingerprints

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _write(root: Path, relative: str, content: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _tool_tree(root: Path) -> Path:
    _write(root, "dev/registry/registry_collapse_verification.py", "from dev.registry import active\n")
    _write(root, "dev/registry/active.py", "VALUE = 1\n")
    _write(root, "src/cadrumo/domain/calculations/registry/schema_exports.py", "VALUE = 1\n")
    _write(root, "dev/registry/tests/not_a_tool.py", "VALUE = 1\n")
    _write(root, "src/cadrumo/application/unrelated.py", "VALUE = 1\n")
    return root


def _dynamic_provider_tree(root: Path) -> Path:
    _tool_tree(root)
    _write(
        root,
        "src/cadrumo/domain/calculations/registry/snapshot.py",
        "_CROSS_DOMAIN_CHECK_MODULES: tuple[str, ...] = (\n"
        '    "...renta.first_slice_routing_integrity",\n'
        '    "...renta.retenciones_routing_integrity",\n'
        '    "...modelos.perceptor_clave_scope",\n'
        ")\n",
    )
    _write(
        root,
        "src/cadrumo/domain/renta/first_slice_routing_integrity.py",
        "from cadrumo.core import scalar\nVALUE = 1\n",
    )
    _write(root, "src/cadrumo/domain/renta/__init__.py", "PACKAGE = 1\n")
    _write(root, "src/cadrumo/domain/renta/retenciones_routing_integrity.py", "VALUE = 1\n")
    _write(root, "src/cadrumo/domain/modelos/__init__.py", "PACKAGE = 1\n")
    _write(root, "src/cadrumo/domain/modelos/perceptor_clave_scope.py", "VALUE = 1\n")
    _write(root, "src/cadrumo/core/scalar.py", "VALUE = 1\n")
    return root


def test_unchanged_interpreting_inputs_remain_stable(tmp_path: Path) -> None:
    root = _tool_tree(tmp_path)

    before = _tool_fingerprints(root)

    assert before == _tool_fingerprints(root)
    assert {entry.path for entry in before} == {
        "dev/registry/active.py",
        "dev/registry/registry_collapse_verification.py",
        "src/cadrumo/domain/calculations/registry/schema_exports.py",
    }


def test_same_size_active_helper_edit_changes_fingerprint(tmp_path: Path) -> None:
    root = _tool_tree(tmp_path)
    before = _tool_fingerprints(root)
    _write(root, "dev/registry/active.py", "VALUE = 2\n")

    after = _tool_fingerprints(root)

    assert before != after
    assert before[0].path == after[0].path == "dev/registry/active.py"
    assert before[0].bytes == after[0].bytes
    assert before[0].sha256 != after[0].sha256


def test_active_helper_size_change_changes_fingerprint(tmp_path: Path) -> None:
    root = _tool_tree(tmp_path)
    before = _tool_fingerprints(root)
    _write(root, "dev/registry/active.py", "VALUE = 12345\n")

    after = _tool_fingerprints(root)

    assert before != after
    assert before[0].bytes != after[0].bytes


def test_new_and_removed_registry_helpers_change_discovered_manifest(tmp_path: Path) -> None:
    root = _tool_tree(tmp_path)
    before = _tool_fingerprints(root)
    added = _write(root, "dev/registry/edition_delta_drop_planning.py", "VALUE = 1\n")

    with_added = _tool_fingerprints(root)
    added.unlink()
    restored = _tool_fingerprints(root)

    assert with_added != before
    assert "dev/registry/edition_delta_drop_planning.py" in {item.path for item in with_added}
    assert restored == before


def test_removed_active_helper_changes_discovered_manifest(tmp_path: Path) -> None:
    root = _tool_tree(tmp_path)
    before = _tool_fingerprints(root)
    (root / "dev/registry/active.py").unlink()

    after = _tool_fingerprints(root)

    assert before != after
    assert "dev/registry/active.py" not in {item.path for item in after}


def test_recursive_local_imports_cover_external_defining_helpers(tmp_path: Path) -> None:
    root = _tool_tree(tmp_path)
    _write(root, "dev/registry/active.py", "from cadrumo.core.authority_grade import VALUE\n")
    _write(root, "src/cadrumo/core/authority_grade.py", "from cadrumo.core import scalar\n")
    scalar = _write(root, "src/cadrumo/core/scalar.py", "VALUE = 1\n")
    before = _tool_fingerprints(root)

    scalar.write_text("VALUE = 2\n", encoding="utf-8")
    after = _tool_fingerprints(root)

    assert "src/cadrumo/core/scalar.py" in {item.path for item in before}
    assert before != after
    assert "src/cadrumo/application/unrelated.py" not in {item.path for item in after}


def test_same_size_dynamic_snapshot_provider_edit_changes_fingerprint(tmp_path: Path) -> None:
    root = _dynamic_provider_tree(tmp_path)
    provider = "src/cadrumo/domain/renta/first_slice_routing_integrity.py"
    before = {entry.path: entry for entry in _tool_fingerprints(root)}
    _write(root, provider, "from cadrumo.core import scalar\nVALUE = 2\n")

    after = {entry.path: entry for entry in _tool_fingerprints(root)}

    assert before[provider].bytes == after[provider].bytes
    assert before[provider].sha256 != after[provider].sha256
    assert "src/cadrumo/core/scalar.py" in after
    assert "src/cadrumo/domain/renta/__init__.py" in after
    assert "src/cadrumo/domain/modelos/__init__.py" in after


def test_missing_declared_snapshot_provider_refuses(tmp_path: Path) -> None:
    root = _dynamic_provider_tree(tmp_path)
    (root / "src/cadrumo/domain/modelos/perceptor_clave_scope.py").unlink()

    with pytest.raises(
        FileNotFoundError, match=r"snapshot declared dynamic provider is missing: .*perceptor_clave_scope"
    ):
        _tool_fingerprints(root)


def test_current_census_includes_split_verifier_dependencies() -> None:
    paths = {path.relative_to(REPO_ROOT).as_posix() for path in _tool_input_paths(REPO_ROOT)}

    assert {
        "dev/registry/edition_delta_drop_planning.py",
        "dev/registry/edition_delta_assessment_revision.py",
        "dev/registry/edition_family_delta_collapse_revision.py",
        "dev/registry/compiler/revision_materialisation.py",
        "dev/registry/edition_round_trip.py",
        "src/cadrumo/domain/calculations/registry/schema_exports.py",
        "src/cadrumo/domain/calculations/registry/schema_revision_members.py",
        "dev/registry/source_default_rule.py",
        "dev/packaging/authority_staging.py",
        "src/cadrumo/domain/renta/first_slice_routing_integrity.py",
        "src/cadrumo/domain/renta/retenciones_routing_integrity.py",
        "src/cadrumo/domain/modelos/perceptor_clave_scope.py",
    } <= paths
