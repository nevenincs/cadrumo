"""Real-behaviour tests for ApiStubManager scaffold, check, and audit."""

from __future__ import annotations

import pytest

from ..manager import ApiStubManager, DriftResult, ScaffoldResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_scaffold_produces_conformant_tree(tmp_path: pytest.TempPathFactory) -> None:
    """scaffold() followed by check() returns an empty DriftResult.

    A freshly scaffolded tree must be immediately conformant: every
    source module has a stub and no stubs are orphaned.
    """
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[4]
    src_aeat = repo_root / "src" / "aeat"
    docs_api = tmp_path / "api"

    manager = ApiStubManager(src_aeat=src_aeat, docs_api=docs_api)
    result = manager.scaffold()

    assert isinstance(result, ScaffoldResult)
    assert result.written > 0

    drift = manager.check()
    assert isinstance(drift, DriftResult)
    assert drift.is_conformant, (
        f"Drift after scaffold — missing: {drift.missing_stubs!r}, orphans: {drift.orphan_stubs!r}"
    )


def test_check_detects_missing_stub(tmp_path: pytest.TempPathFactory) -> None:
    """check() reports a module as missing when its stub file is absent.

    After scaffolding, deleting one stub file causes check() to report
    that module in missing_stubs.
    """
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[4]
    src_aeat = repo_root / "src" / "aeat"
    docs_api = tmp_path / "api"

    manager = ApiStubManager(src_aeat=src_aeat, docs_api=docs_api)
    manager.scaffold()

    # Remove one known stub and verify check() surfaces it.
    target = docs_api / "aeat.core.errors.rst"
    assert target.exists(), f"Expected stub not found: {target}"
    target.unlink()

    drift = manager.check()
    assert "aeat.core.errors" in drift.missing_stubs
    assert not drift.is_conformant


def test_check_detects_orphan_stub(tmp_path: pytest.TempPathFactory) -> None:
    """check() reports an RST file as orphaned when no module backs it.

    Injecting a stub for a non-existent module causes check() to list it
    in orphan_stubs.
    """
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[4]
    src_aeat = repo_root / "src" / "aeat"
    docs_api = tmp_path / "api"

    manager = ApiStubManager(src_aeat=src_aeat, docs_api=docs_api)
    manager.scaffold()

    ghost = docs_api / "aeat.does_not_exist.rst"
    ghost.write_text(".. automodule:: aeat.does_not_exist\n", encoding="utf-8")

    drift = manager.check()
    assert "aeat.does_not_exist" in drift.orphan_stubs
    assert not drift.is_conformant


def test_check_detects_stale_stub_content(tmp_path: pytest.TempPathFactory) -> None:
    """check() reports a generated stub whose content was hand-edited."""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[4]
    src_aeat = repo_root / "src" / "aeat"
    docs_api = tmp_path / "api"

    manager = ApiStubManager(src_aeat=src_aeat, docs_api=docs_api)
    manager.scaffold()

    target = docs_api / "aeat.core.errors.rst"
    target.write_text("aeat.core.errors module\n=======================\n\nmanual drift\n", encoding="utf-8")

    drift = manager.check()
    assert "aeat.core.errors" in drift.stale_stubs
    assert not drift.is_conformant


def test_scaffold_removes_stale_stub(tmp_path: pytest.TempPathFactory) -> None:
    """scaffold() removes stubs whose backing module no longer exists.

    A pre-existing stub for a phantom module is deleted on the next scaffold
    run and the removal is reported in ScaffoldResult.removed_names.
    """
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[4]
    src_aeat = repo_root / "src" / "aeat"
    docs_api = tmp_path / "api"
    docs_api.mkdir(parents=True)

    phantom = docs_api / "aeat.phantom_module.rst"
    phantom.write_text(".. automodule:: aeat.phantom_module\n", encoding="utf-8")

    manager = ApiStubManager(src_aeat=src_aeat, docs_api=docs_api)
    result = manager.scaffold()

    assert "aeat.phantom_module.rst" in result.removed_names
    assert not phantom.exists()


def test_scaffold_leaves_unchanged_stubs_untouched(tmp_path: pytest.TempPathFactory) -> None:
    """A second scaffold run writes no files when the tree is already current."""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[4]
    src_aeat = repo_root / "src" / "aeat"
    docs_api = tmp_path / "api"

    manager = ApiStubManager(src_aeat=src_aeat, docs_api=docs_api)
    first = manager.scaffold()
    second = manager.scaffold()

    assert first.written > 0
    assert second.written == 0
    assert second.unchanged == first.written


def test_audit_returns_conformant_message_after_scaffold(tmp_path: pytest.TempPathFactory) -> None:
    """audit() includes a conformant message after a successful scaffold."""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[4]
    src_aeat = repo_root / "src" / "aeat"
    docs_api = tmp_path / "api"

    manager = ApiStubManager(src_aeat=src_aeat, docs_api=docs_api)
    manager.scaffold()

    report = manager.audit()
    assert "conformant" in report.lower()
