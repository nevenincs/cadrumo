"""A delta edition's review stamp states the predecessor it was reviewed against.

An edition naming a predecessor inherits the predecessor's casilla rows at load,
so a reviewer reading its file signs a delta. The stamp writer records that
scope as ``reviewed_against``, filled from the compiled predecessor and never
from the caller, and the schema refuses a reviewed delta edition whose scope is
missing or names another edition. Every case runs against a copy of modelo 232
driven through the real loader and the real writer.
"""

from __future__ import annotations

import inspect
import re
import shutil
import tomllib
from datetime import date
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryError
from dev.registry.compiler.loader import load_modelo_directory

from .._stamp import GOVERNANCE_KEYS, StampError, stamp_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_MODELO = "232"
_BASE = "2016-2017"
_DELTA = "2018-y-siguientes"
_REVIEW_DATE = date(2026, 9, 10)
_REVIEW_LINE = re.compile(r"^(review_status|reviewed_by|reviewed_at) = .*\n", re.MULTILINE)


def _copy(tmp_path: Path) -> Path:
    registry_root = tmp_path / "registry" / "aeat"
    shutil.copytree(bundled_path("registry", "aeat", "modelos", _MODELO), registry_root / "modelos" / _MODELO)
    return registry_root


def _manifest(registry_root: Path, revision: str) -> Path:
    return registry_root / "modelos" / _MODELO / "revisions" / revision / "revision.toml"


def _edit_manifest(registry_root: Path, revision: str, *, add: str = "", drop_review: bool = False) -> None:
    manifest = _manifest(registry_root, revision)
    header = f'[revisions."{revision}"]\n'
    text = manifest.read_bytes().decode("utf-8")
    assert header in text, "sanity: the edit needs the canonical header"
    if drop_review:
        text, dropped = _REVIEW_LINE.subn("", text)
        assert dropped == 3, "sanity: the shipped review claim is three single-line scalars"
    manifest.write_bytes(text.replace(header, header + add, 1).encode("utf-8"))


def _migrated(tmp_path: Path) -> Path:
    """Modelo 232 with its later edition declared a delta and its pre-migration review cleared."""
    registry_root = _copy(tmp_path)
    _edit_manifest(registry_root, _DELTA, add=f'predecessor = "{_BASE}"\n', drop_review=True)
    return registry_root


def _load(registry_root: Path):
    return load_modelo_directory(registry_root / "modelos" / _MODELO)


def _declared_stamp(registry_root: Path, revision: str) -> dict[str, object]:
    table = tomllib.loads(_manifest(registry_root, revision).read_text("utf-8"))["revisions"][revision]
    return {key: table[key] for key in GOVERNANCE_KEYS if key in table}


def _review(registry_root: Path, revision: str):
    return stamp_revision(
        _MODELO,
        revision,
        review_status="agent_reviewed",
        reviewed_by="agent:scope-probe",
        reviewed_at=_REVIEW_DATE,
        registry_root=registry_root,
    )


def test_a_reviewed_delta_edition_stamp_names_the_predecessor_it_covers(tmp_path: Path) -> None:
    """The stamp alone tells a reviewed delta from an unreviewed one, and says what it covers."""
    registry_root = _migrated(tmp_path)
    unreviewed = _declared_stamp(registry_root, _DELTA)

    result = _review(registry_root, _DELTA)
    reviewed = _declared_stamp(registry_root, _DELTA)

    assert "reviewed_against" not in unreviewed
    assert unreviewed.get("review_status", "pending_review") == "pending_review"
    assert reviewed["review_status"] == "agent_reviewed"
    assert reviewed["reviewed_against"] == _BASE
    assert result.written["reviewed_against"] == f'"{_BASE}"'
    assert _load(registry_root).revisions[_DELTA].reviewed_against == _BASE


def test_an_edition_stating_every_row_is_reviewed_without_a_scope(tmp_path: Path) -> None:
    """The control: the writer adds a scope only where the compiled edition inherits."""
    registry_root = _migrated(tmp_path)

    _review(registry_root, _BASE)

    assert "reviewed_against" not in _declared_stamp(registry_root, _BASE)
    assert _load(registry_root).revisions[_BASE].reviewed_against is None


def test_returning_a_delta_edition_to_pending_drops_its_scope(tmp_path: Path) -> None:
    registry_root = _migrated(tmp_path)
    _review(registry_root, _DELTA)

    result = stamp_revision(_MODELO, _DELTA, review_status="pending_review", registry_root=registry_root)

    assert "reviewed_against" in result.removed
    assert "reviewed_against" not in _declared_stamp(registry_root, _DELTA)


def test_the_scope_is_never_caller_input() -> None:
    """The writer takes no scope argument, so a caller cannot name an edition the reviewer did not read against."""
    assert "reviewed_against" not in inspect.signature(stamp_revision).parameters


def test_the_shipped_pre_migration_stamp_is_refused_once_the_edition_inherits(tmp_path: Path) -> None:
    """Migrating 232 without re-review leaves an unscoped claim, which no longer loads or stamps."""
    registry_root = _copy(tmp_path)
    assert _declared_stamp(registry_root, _DELTA)["review_status"] == "agent_reviewed", "sanity: shipped claim"
    assert _load(registry_root).revisions[_DELTA].reviewed_against is None

    _edit_manifest(registry_root, _DELTA, add=f'predecessor = "{_BASE}"\n')

    with pytest.raises(RegistryError, match="omits reviewed_against"):
        _load(registry_root)
    with pytest.raises(StampError, match="omits reviewed_against"):
        stamp_revision(_MODELO, _DELTA, engineered_by="agent:author", registry_root=registry_root)


def test_a_scope_naming_another_edition_is_refused(tmp_path: Path) -> None:
    registry_root = _migrated(tmp_path)
    _review(registry_root, _DELTA)
    manifest = _manifest(registry_root, _DELTA)
    text = manifest.read_bytes().decode("utf-8")
    manifest.write_bytes(text.replace(f'reviewed_against = "{_BASE}"', 'reviewed_against = "2015"').encode("utf-8"))

    with pytest.raises(RegistryError, match="reviewed_against='2015'"):
        _load(registry_root)


def test_a_scope_on_an_edition_that_names_no_predecessor_is_refused(tmp_path: Path) -> None:
    registry_root = _copy(tmp_path)
    _edit_manifest(registry_root, _BASE, add=f'reviewed_against = "{_BASE}"\n')

    with pytest.raises(RegistryError, match="names no predecessor"):
        _load(registry_root)
