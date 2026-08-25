"""Real-behaviour tests for ApiStubManager scaffold, check, and audit."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core import scan_directory

from ...._paths import REPO_ROOT
from ..manager import ApiStubManager, DriftResult, ScaffoldResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_public_type_aliases_have_one_canonical_facade_target(tmp_path: Path) -> None:
    """Public PEP 695 aliases are indexed once at their intended facades."""
    manager = ApiStubManager(src_cadrumo=REPO_ROOT / "src" / "cadrumo", docs_api=tmp_path / "api")

    manager.scaffold()

    core_api_text = (tmp_path / "api" / "cadrumo.core.rst").read_text(encoding="utf-8")
    identity_api_text = (tmp_path / "api" / "cadrumo.core.identity.rst").read_text(encoding="utf-8")
    registry_api_text = (tmp_path / "api" / "cadrumo.domain.calculations.registry.rst").read_text(encoding="utf-8")
    all_stub_text = "\n".join(path.read_text(encoding="utf-8") for path in (tmp_path / "api").glob("*.rst"))
    assert ".. py:data:: CasillaId\n   :module: cadrumo.core" in core_api_text
    assert ".. py:data:: TaxIdIdentityToken\n   :module: cadrumo.core.identity" in identity_api_text
    assert ".. py:data:: SubjectTaxId\n   :module: cadrumo.core.identity" in identity_api_text
    assert ".. py:data:: ContentDigest\n   :module: cadrumo.core.identity" in identity_api_text
    assert all_stub_text.count(".. py:data:: CasillaId\n") == 1
    assert all_stub_text.count(".. py:data:: TaxIdIdentityToken\n") == 1
    assert all_stub_text.count(".. py:data:: SubjectTaxId\n") == 1
    assert all_stub_text.count(".. py:data:: ContentDigest\n") == 1
    assert ".. py:function:: collect_registry_tree_fingerprints" in registry_api_text
    assert all_stub_text.count(".. py:function:: collect_registry_tree_fingerprints\n") == 1


def test_imported_generic_models_are_excluded_only_at_consumers(tmp_path: Path) -> None:
    """Pydantic generic consumers must not re-index their defining objects."""
    manager = ApiStubManager(src_cadrumo=REPO_ROOT / "src" / "cadrumo", docs_api=tmp_path / "api")
    manager.scaffold()

    owner = (tmp_path / "api" / "cadrumo.application.aggregation._models.rst").read_text(encoding="utf-8")
    consumer = (tmp_path / "api" / "cadrumo.application.aggregation._renta_ledger.rst").read_text(
        encoding="utf-8",
    )
    assert "LedgerAggregationResultBase" not in owner
    assert ":exclude-members: LedgerAggregationResultBase" in consumer


def test_imported_journal_repository_base_is_excluded_only_at_consumers(tmp_path: Path) -> None:
    """Journal repositories keep their shared generic base at its defining stub."""
    manager = ApiStubManager(src_cadrumo=REPO_ROOT / "src" / "cadrumo", docs_api=tmp_path / "api")
    manager.scaffold()

    config_reset = (tmp_path / "api" / "cadrumo.application._config_reset_repository.rst").read_text(
        encoding="utf-8",
    )
    bundle_export = (tmp_path / "api" / "cadrumo.application.user_profile.bundle_export_operation.rst").read_text(
        encoding="utf-8"
    )
    assert ":exclude-members: JournalRepositoryBase" in config_reset
    assert ":exclude-members: JournalRepositoryBase" in bundle_export


def test_scaffold_produces_conformant_tree(tmp_path: Path) -> None:
    """scaffold() followed by check() returns an empty DriftResult.

    A freshly scaffolded tree must be immediately conformant: every
    source module has a stub and no stubs are orphaned.
    """

    repo_root = REPO_ROOT
    src_cadrumo = repo_root / "src" / "cadrumo"
    docs_api = tmp_path / "api"

    manager = ApiStubManager(src_cadrumo=src_cadrumo, docs_api=docs_api)
    result = manager.scaffold()

    assert isinstance(result, ScaffoldResult)
    assert result.written > 0

    drift = manager.check()
    assert isinstance(drift, DriftResult)
    assert drift.is_conformant, (
        f"Drift after scaffold — missing: {drift.missing_stubs!r}, orphans: {drift.orphan_stubs!r}"
    )


def test_check_detects_missing_stub(tmp_path: Path) -> None:
    """check() reports a module as missing when its stub file is absent.

    After scaffolding, deleting one stub file causes check() to report
    that module in missing_stubs.
    """

    repo_root = REPO_ROOT
    src_cadrumo = repo_root / "src" / "cadrumo"
    docs_api = tmp_path / "api"

    manager = ApiStubManager(src_cadrumo=src_cadrumo, docs_api=docs_api)
    manager.scaffold()

    # Remove one known stub and verify check() surfaces it.
    target = docs_api / "cadrumo.core.errors.rst"
    assert target.exists(), f"Expected stub not found: {target}"
    target.unlink()

    drift = manager.check()
    assert "cadrumo.core.errors" in drift.missing_stubs
    assert not drift.is_conformant


def test_check_detects_orphan_stub(tmp_path: Path) -> None:
    """check() reports an RST file as orphaned when no module backs it.

    Injecting a stub for a non-existent module causes check() to list it
    in orphan_stubs.
    """

    repo_root = REPO_ROOT
    src_cadrumo = repo_root / "src" / "cadrumo"
    docs_api = tmp_path / "api"

    manager = ApiStubManager(src_cadrumo=src_cadrumo, docs_api=docs_api)
    manager.scaffold()

    ghost = docs_api / "cadrumo.does_not_exist.rst"
    ghost.write_text(".. automodule:: cadrumo.does_not_exist\n", encoding="utf-8")

    drift = manager.check()
    assert "cadrumo.does_not_exist" in drift.orphan_stubs
    assert not drift.is_conformant


def test_check_detects_stale_stub_content(tmp_path: Path) -> None:
    """check() reports a generated stub whose content was hand-edited."""

    repo_root = REPO_ROOT
    src_cadrumo = repo_root / "src" / "cadrumo"
    docs_api = tmp_path / "api"

    manager = ApiStubManager(src_cadrumo=src_cadrumo, docs_api=docs_api)
    manager.scaffold()

    target = docs_api / "cadrumo.core.errors.rst"
    target.write_text("cadrumo.core.errors module\n=======================\n\nmanual drift\n", encoding="utf-8")

    drift = manager.check()
    assert "cadrumo.core.errors" in drift.stale_stubs
    assert not drift.is_conformant


def test_check_detects_a_terminator_translated_stub(tmp_path: Path) -> None:
    """check() reports a stub whose terminators were translated after it was written.

    This is the case a decoded-text comparison structurally cannot reach.
    ``Path.read_text`` is universal-newline, so the planted CRLF bytes decode
    to exactly the canonical string — the middle assertion below asserts that
    equality outright, which is the comparison the check used to perform and
    pass. Git is equally blind: the repository normalises to LF on the index
    side, so the same file shows no diff. The stale verdict at the end is
    therefore the only reader in the system that can see this drift at all.
    """

    repo_root = REPO_ROOT
    src_cadrumo = repo_root / "src" / "cadrumo"
    docs_api = tmp_path / "api"

    manager = ApiStubManager(src_cadrumo=src_cadrumo, docs_api=docs_api)
    manager.scaffold()
    assert manager.check().is_conformant, "the tree must be clean before the drift is planted"

    target = docs_api / "cadrumo.core.errors.rst"
    canonical = target.read_bytes()
    assert b"\r\n" not in canonical, "the generator must emit line feeds for the plant to mean anything"

    target.write_bytes(canonical.replace(b"\n", b"\r\n"))

    assert target.read_text(encoding="utf-8") == canonical.decode("utf-8"), (
        "the planted file must still decode to the canonical text, or this proves nothing "
        "about the comparison that normalised terminators away"
    )

    drift = manager.check()
    assert "cadrumo.core.errors" in drift.stale_stubs
    assert not drift.is_conformant


def test_scaffold_writes_line_feed_terminators(tmp_path: Path) -> None:
    """Every stub the generator writes carries line feeds, on every platform.

    Without the explicit newline the writer translates on write, which is how
    a check that reads through the same translation came to be blind to its
    own output.
    """

    repo_root = REPO_ROOT
    src_cadrumo = repo_root / "src" / "cadrumo"
    docs_api = tmp_path / "api"

    manager = ApiStubManager(src_cadrumo=src_cadrumo, docs_api=docs_api)
    result = manager.scaffold()

    rst_paths = scan_directory(docs_api, pattern="*.rst")
    assert len(rst_paths) == result.written, "the scan must cover every stub the run reported writing"

    translated = [rst_path.name for rst_path in rst_paths if b"\r\n" in rst_path.read_bytes()]
    assert not translated, f"the generator translated terminators in {len(translated)} stubs: {translated[:5]}"


def test_scaffold_rewrites_a_terminator_translated_stub(tmp_path: Path) -> None:
    """scaffold() restores a translated stub instead of counting it unchanged.

    The skip-if-current branch shares the comparison with check(), so a text
    comparison would have skipped this file forever and left the drift on disk
    permanently.
    """

    repo_root = REPO_ROOT
    src_cadrumo = repo_root / "src" / "cadrumo"
    docs_api = tmp_path / "api"

    manager = ApiStubManager(src_cadrumo=src_cadrumo, docs_api=docs_api)
    manager.scaffold()

    target = docs_api / "cadrumo.core.errors.rst"
    canonical = target.read_bytes()
    target.write_bytes(canonical.replace(b"\n", b"\r\n"))

    second = manager.scaffold()

    assert second.written == 1, f"expected the one translated stub to be rewritten, got {second.written}"
    assert target.read_bytes() == canonical


def test_scaffold_removes_stale_stub(tmp_path: Path) -> None:
    """scaffold() removes stubs whose backing module no longer exists.

    A pre-existing stub for a phantom module is deleted on the next scaffold
    run and the removal is reported in ScaffoldResult.removed_names.
    """

    repo_root = REPO_ROOT
    src_cadrumo = repo_root / "src" / "cadrumo"
    docs_api = tmp_path / "api"
    docs_api.mkdir(parents=True)

    phantom = docs_api / "cadrumo.phantom_module.rst"
    phantom.write_text(".. automodule:: cadrumo.phantom_module\n", encoding="utf-8")

    manager = ApiStubManager(src_cadrumo=src_cadrumo, docs_api=docs_api)
    result = manager.scaffold()

    assert "cadrumo.phantom_module.rst" in result.removed_names
    assert not phantom.exists()


def test_scaffold_leaves_unchanged_stubs_untouched(tmp_path: Path) -> None:
    """A second scaffold run writes no files when the tree is already current."""

    repo_root = REPO_ROOT
    src_cadrumo = repo_root / "src" / "cadrumo"
    docs_api = tmp_path / "api"

    manager = ApiStubManager(src_cadrumo=src_cadrumo, docs_api=docs_api)
    first = manager.scaffold()
    second = manager.scaffold()

    assert first.written > 0
    assert second.written == 0
    assert second.unchanged == first.written


def test_audit_returns_conformant_message_after_scaffold(tmp_path: Path) -> None:
    """audit() includes a conformant message after a successful scaffold."""

    repo_root = REPO_ROOT
    src_cadrumo = repo_root / "src" / "cadrumo"
    docs_api = tmp_path / "api"

    manager = ApiStubManager(src_cadrumo=src_cadrumo, docs_api=docs_api)
    manager.scaffold()

    report = manager.audit()
    assert "conformant" in report.lower()
