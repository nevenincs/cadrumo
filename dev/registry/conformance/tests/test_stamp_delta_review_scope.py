"""A review claim is never written onto an edition whose compiled rows its file does not state.

An edition naming a predecessor inherits the predecessor's casilla rows at load,
so a reviewer reading its file signs a delta. The governance stamp names a
reviewer and a date and nothing about what was reviewed, so the writer refuses a
review claim there instead of writing one that reads as covering the whole
compiled edition. Every case runs against a copy of a real modelo driven through
the real loader, with the predecessor declaration as the only planted change.
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.loader import load_modelo_directory
from cadrumo.domain.calculations.registry.schema import DeclaredPredecessor

from .._stamp import StampError, stamp_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_MODELO = "232"
_BASE = "2016-2017"
_DELTA = "2018-y-siguientes"
_REVIEW_DATE = date(2026, 9, 10)


def _registry(tmp_path: Path, *, delta: bool) -> Path:
    """Copy modelo 232 into an isolated tree, optionally declaring the later edition a delta."""
    registry_root = tmp_path / "registry" / "aeat"
    modelo_dir = registry_root / "modelos" / _MODELO
    shutil.copytree(bundled_path("registry", "aeat", "modelos", _MODELO), modelo_dir)
    if delta:
        manifest = modelo_dir / "revisions" / _DELTA / "revision.toml"
        header = f'[revisions."{_DELTA}"]\n'
        text = manifest.read_bytes().decode("utf-8")
        assert header in text, "sanity: the planted declaration needs the canonical header"
        manifest.write_bytes(text.replace(header, f'{header}predecessor = "{_BASE}"\n', 1).encode("utf-8"))
        compiled = load_modelo_directory(modelo_dir).revisions[_DELTA]
        assert isinstance(compiled.predecessor, DeclaredPredecessor), "sanity: the plant must compile as a delta"
    return registry_root


def _manifest(registry_root: Path, revision: str) -> Path:
    return registry_root / "modelos" / _MODELO / "revisions" / revision / "revision.toml"


def _review(registry_root: Path, revision: str) -> None:
    stamp_revision(
        _MODELO,
        revision,
        review_status="agent_reviewed",
        reviewed_by="agent:scope-probe",
        reviewed_at=_REVIEW_DATE,
        registry_root=registry_root,
    )


def test_a_review_claim_on_a_delta_edition_is_refused_and_nothing_is_written(tmp_path: Path) -> None:
    registry_root = _registry(tmp_path, delta=True)
    manifest = _manifest(registry_root, _DELTA)
    before = manifest.read_bytes()

    with pytest.raises(StampError) as refusal:
        _review(registry_root, _DELTA)

    message = str(refusal.value)
    assert f"predecessor {_BASE!r}" in message
    assert "inherited" in message
    assert manifest.read_bytes() == before


def test_the_same_review_is_written_when_the_edition_states_every_row(tmp_path: Path) -> None:
    """The control, and the teeth: without the predecessor declaration the identical call succeeds."""
    registry_root = _registry(tmp_path, delta=False)

    _review(registry_root, _DELTA)

    compiled = load_modelo_directory(registry_root / "modelos" / _MODELO).revisions[_DELTA]
    assert compiled.reviewed_by == "agent:scope-probe"
    assert compiled.reviewed_at == _REVIEW_DATE


def test_the_predecessor_itself_stays_reviewable(tmp_path: Path) -> None:
    """The refusal is about inheriting, not about being named as a predecessor."""
    registry_root = _registry(tmp_path, delta=True)

    _review(registry_root, _BASE)

    assert load_modelo_directory(registry_root / "modelos" / _MODELO).revisions[_BASE].reviewed_by == (
        "agent:scope-probe"
    )


def test_a_delta_edition_can_be_returned_to_pending_and_have_its_author_recorded(tmp_path: Path) -> None:
    """Clearing a claim asserts less, and authorship claims no coverage, so both stay writable."""
    registry_root = _registry(tmp_path, delta=True)

    stamp_revision(_MODELO, _DELTA, engineered_by="agent:author", registry_root=registry_root)
    result = stamp_revision(_MODELO, _DELTA, review_status="pending_review", registry_root=registry_root)

    compiled = load_modelo_directory(registry_root / "modelos" / _MODELO).revisions[_DELTA]
    assert compiled.engineered_by == "agent:author"
    assert compiled.review_status.value == "pending_review"
    assert compiled.reviewed_by is None
    assert set(result.removed) == {"reviewed_by", "reviewed_at"}
