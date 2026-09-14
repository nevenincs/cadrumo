"""Packed casilla section ownership, independent of physical fragment count.

This checks source representation, not semantic continuity or filing authority.
Coverage is counted in declared rows and modelos, never fragment files.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

import pytest

from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.resources.bundled_data import bundled_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PACKED_NAME = "0001-declarations.toml"
_MIN_DECLARED_ROWS = 5_000
_MIN_MODELOS = 40


@dataclass(frozen=True)
class _PackingScan:
    violations: tuple[str, ...]
    declared_rows: int
    modelos: frozenset[str]
    directories: int

    @property
    def representative(self) -> bool:
        return self.declared_rows >= _MIN_DECLARED_ROWS and len(self.modelos) >= _MIN_MODELOS


def _naming_violations(root: Path) -> _PackingScan:
    violations: list[str] = []
    rows = 0
    modelos: set[str] = set()
    directories = 0
    for directory in sorted((root / "modelos").glob("*/revisions/*/casillas")):
        directories += 1
        modelos.add(directory.parents[2].name)
        revision_id = directory.parent.name
        files = scan_directory(directory, pattern="*.toml", recursive=True)
        if len(files) != 1 or files[0] != directory / _PACKED_NAME:
            violations.append(
                f"{directory.relative_to(root).as_posix()}: expected one direct {_PACKED_NAME}; "
                f"found {[path.relative_to(directory).as_posix() for path in files]}"
            )
        # Inspect extra and nested fragments too: a bad name cannot hide rows.
        claimed: set[str] = set()
        for path in files:
            relative = path.relative_to(root).as_posix()
            try:
                document = tomllib.loads(path.read_text(encoding="utf-8-sig"))
            except tomllib.TOMLDecodeError as exc:
                violations.append(f"{relative}: invalid TOML: {exc}")
                continue
            if not document:
                continue  # A packed empty section may contain only commentary.
            revisions = document.get("revisions")
            if not isinstance(revisions, dict) or set(document) != {"revisions"}:
                violations.append(f"{relative}: expected only the owning revisions table")
                continue
            if set(revisions) != {revision_id}:
                violations.append(f"{relative}: revision owner must be {revision_id!r}, got {list(revisions)}")
            for owner, body in revisions.items():
                if not isinstance(body, dict) or set(body) != {"casillas"}:
                    violations.append(f"{relative}: revision {owner!r} must contain only casillas")
                    continue
                entries = body["casillas"]
                if not isinstance(entries, list):
                    violations.append(f"{relative}: casillas must be an array of declaration tables")
                    continue
                rows += len(entries)
                for entry in entries:
                    identifier = entry.get("id") if isinstance(entry, dict) else None
                    if not isinstance(identifier, str) or not identifier:
                        violations.append(f"{relative}: casilla declaration has no nonempty string id")
                    elif identifier in claimed:
                        violations.append(f"{relative}: duplicate casilla id {identifier!r}")
                    else:
                        claimed.add(identifier)
    return _PackingScan(tuple(violations), rows, frozenset(modelos), directories)


def test_every_casilla_section_is_packed_and_owned_by_its_edition() -> None:
    scan = _naming_violations(bundled_path("registry", "aeat"))
    assert scan.representative, (
        f"scan saw {scan.declared_rows} declared rows in {len(scan.modelos)} modelos and "
        f"{scan.directories} sections; missing corpus coverage is not clean packing"
    )
    assert not scan.violations, "\n".join(scan.violations)


def _write_fragment(root: Path, name: str, ids: tuple[str, ...], *, owner: str = "2024") -> Path:
    directory = root / "modelos" / "999" / "revisions" / "2024" / "casillas"
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(f'[[revisions."{owner}".casillas]]\nid = "{identifier}"' for identifier in ids),
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(
    "name", ["c0002.toml", "0001-c0002.toml", "0001-casillas.toml", "nested/0001-declarations.toml"]
)
def test_old_or_nested_names_cannot_claim_packed_storage(tmp_path: Path, name: str) -> None:
    _write_fragment(tmp_path, name, ("0002",))
    scan = _naming_violations(tmp_path)
    assert scan.declared_rows == 1
    assert any("expected one direct" in finding for finding in scan.violations)


def test_packed_name_does_not_encode_id_number_or_order(tmp_path: Path) -> None:
    _write_fragment(tmp_path, _PACKED_NAME, ("DP200014B:00592", "0001", "0700"))
    scan = _naming_violations(tmp_path)
    assert not scan.violations
    assert scan.declared_rows == 3
    assert not scan.representative


def test_extra_fragment_is_scanned_and_duplicate_is_reported(tmp_path: Path) -> None:
    _write_fragment(tmp_path, _PACKED_NAME, ("0001",))
    _write_fragment(tmp_path, "0002-declarations.toml", ("0001", "0002"))
    scan = _naming_violations(tmp_path)
    assert scan.declared_rows == 3
    assert any("expected one direct" in finding for finding in scan.violations)
    assert any("duplicate casilla id '0001'" in finding for finding in scan.violations)


def test_packed_fragment_cannot_claim_another_revision(tmp_path: Path) -> None:
    _write_fragment(tmp_path, _PACKED_NAME, ("0001",), owner="2025")
    assert any("revision owner" in finding for finding in _naming_violations(tmp_path).violations)


@pytest.mark.parametrize("body", ['[revisions."2024"]\ncasillas = 1', '[[revisions."2024".casillas]]\nnumber = "1"'])
def test_invalid_declaration_shape_is_not_silently_ignored(tmp_path: Path, body: str) -> None:
    path = _write_fragment(tmp_path, _PACKED_NAME, ())
    path.write_text(body, encoding="utf-8")
    assert _naming_violations(tmp_path).violations


def test_empty_scan_cannot_satisfy_population_guard(tmp_path: Path) -> None:
    assert not _naming_violations(tmp_path).representative
