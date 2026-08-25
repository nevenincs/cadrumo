"""Independent fixed-point proof for the legacy-TUI migration manifest."""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

import pytest

from cadrumo.core import scan_directory

from ..quality.import_hygiene_scan import (
    LEGACY_TUI_PACKAGE,
    LEGACY_TUI_ROOT,
    REPO_ROOT,
    SRC_ROOT,
    TuiMigrationManifestError,
    TuiMigrationRow,
    TuiMigrationRowKind,
    _tui_migration_identity_sha256,
    generate_tui_migration_manifest,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _module_name(path: Path, root: Path) -> str:
    relative = path.relative_to(root)
    parts = list(relative.parts)
    parts[-1] = "" if parts[-1] == "__init__.py" else parts[-1].removesuffix(".py")
    return ".".join(part for part in parts if part)


def _literal_exports(path: Path) -> Counter[tuple[str, str, int]]:
    module = _module_name(path, SRC_ROOT)
    found: Counter[tuple[str, str, int]] = Counter()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for statement in tree.body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
        if not any(isinstance(target, ast.Name) and target.id == "__all__" for target in targets):
            continue
        value = statement.value
        if not isinstance(value, (ast.List, ast.Tuple, ast.Set)):
            continue
        for element in value.elts:
            if isinstance(element, ast.Constant) and isinstance(element.value, str):
                found[(module, element.value, element.lineno)] += 1
    return found


def _manifest_counter(
    rows: tuple[TuiMigrationRow, ...], kind: TuiMigrationRowKind
) -> Counter[tuple[str, str | None, str]]:
    return Counter((row.legacy_module, row.symbol, row.locator) for row in rows if row.kind is kind)


def _synthetic_tree(tmp_path: Path) -> tuple[Path, Path, Path]:
    src_root = tmp_path / "src"
    package_root = src_root / "cadrumo"
    legacy_root = package_root / "adapters/inbound/tui"
    legacy_root.mkdir(parents=True)
    (legacy_root / "__init__.py").write_text(
        'class Existing: pass\n__all__ = ["Existing"]\n',
        encoding="utf-8",
    )
    return src_root, package_root, legacy_root


def test_generated_manifest_matches_real_module_and_export_multiplicity() -> None:
    """Direct filesystem and AST facts must exactly equal generated declarations."""
    rows = generate_tui_migration_manifest()
    production_modules = [
        path
        for path in scan_directory(LEGACY_TUI_ROOT, pattern="*.py", recursive=True)
        if "tests" not in path.relative_to(LEGACY_TUI_ROOT).parts
    ]
    direct_modules = Counter(
        (_module_name(path, SRC_ROOT), None, f"{path.relative_to(REPO_ROOT).as_posix()}:1")
        for path in production_modules
    )
    direct_exports: Counter[tuple[str, str | None, str]] = Counter()
    for path in production_modules:
        for (module, symbol, line), count in _literal_exports(path).items():
            direct_exports[(module, symbol, f"{path.relative_to(REPO_ROOT).as_posix()}:{line}")] += count

    assert _manifest_counter(rows, TuiMigrationRowKind.MODULE) == direct_modules
    assert _manifest_counter(rows, TuiMigrationRowKind.EXPORT) == direct_exports
    assert len(rows) == 515


def test_same_line_import_and_qualified_reference_are_both_manifested(tmp_path: Path) -> None:
    """A string reference sharing an import line remains a distinct occurrence."""
    src_root, package_root, legacy_root = _synthetic_tree(tmp_path)
    consumer = package_root / "consumer.py"
    consumer.write_text(
        f'from {LEGACY_TUI_PACKAGE} import Existing; marker = "{LEGACY_TUI_PACKAGE}.Existing"\n',
        encoding="utf-8",
    )

    rows = generate_tui_migration_manifest(
        repo_root=tmp_path,
        src_root=src_root,
        package_root=package_root,
        legacy_root=legacy_root,
        accepted_identity_sha256=None,
    )

    consumer_rows = Counter(row.kind for row in rows if row.consumer == "cadrumo.consumer")
    assert consumer_rows == Counter({TuiMigrationRowKind.IMPORT: 1, TuiMigrationRowKind.REFERENCE: 1})


def test_nested_legacy_module_fails_closed(tmp_path: Path) -> None:
    """A production module below a nested package cannot evade disposition."""
    src_root, package_root, legacy_root = _synthetic_tree(tmp_path)
    nested = legacy_root / "nested"
    nested.mkdir()
    (nested / "_unowned.py").write_text("class Hidden: pass\n", encoding="utf-8")

    with pytest.raises(TuiMigrationManifestError, match=r"has no accepted disposition.*nested\._unowned"):
        generate_tui_migration_manifest(
            repo_root=tmp_path,
            src_root=src_root,
            package_root=package_root,
            legacy_root=legacy_root,
            accepted_identity_sha256=None,
        )


def test_duplicate_semantic_row_changes_the_accepted_digest(tmp_path: Path) -> None:
    """Repeating an otherwise identical edge is a new census occurrence."""
    src_root, package_root, legacy_root = _synthetic_tree(tmp_path)
    consumer = package_root / "consumer.py"
    consumer.write_text(f"from {LEGACY_TUI_PACKAGE} import Existing\n", encoding="utf-8")
    baseline = generate_tui_migration_manifest(
        repo_root=tmp_path,
        src_root=src_root,
        package_root=package_root,
        legacy_root=legacy_root,
        accepted_identity_sha256=None,
    )
    accepted = _tui_migration_identity_sha256(baseline)
    consumer.write_text(
        f"from {LEGACY_TUI_PACKAGE} import Existing; from {LEGACY_TUI_PACKAGE} import Existing\n",
        encoding="utf-8",
    )

    with pytest.raises(TuiMigrationManifestError, match="identities differ from the accepted exact census"):
        generate_tui_migration_manifest(
            repo_root=tmp_path,
            src_root=src_root,
            package_root=package_root,
            legacy_root=legacy_root,
            accepted_identity_sha256=accepted,
        )
