"""Regression coverage for the canonical converter on the live Modelo 100 shape."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ..edition_delta_migration import migrate_modelo
from ..edition_round_trip import copy_registry_tree

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]

_LIVE = REPO_ROOT / "src/cadrumo/_data/registry/aeat/modelos/100"


def _isolated_registry(root: Path) -> Path:
    registry_root = root / "registry" / "aeat"
    return copy_registry_tree(
        REPO_ROOT / "src/cadrumo/_data/registry/aeat",
        registry_root,
        modelo_id="100",
    )


def test_live_modelo_100_is_a_verified_no_op(tmp_path: Path) -> None:
    registry_root = _isolated_registry(tmp_path)

    outcome = migrate_modelo(
        registry_root=registry_root,
        modelo_id="100",
        work_dir=tmp_path / "work",
    )

    assert not outcome.changed
    assert outcome.staged_registry is None
    assert outcome.complete
    assert outcome.after_assessment is not None
    assert outcome.after_assessment.minimal


def test_partial_family_enrolment_continues_instead_of_skipping_revision(tmp_path: Path) -> None:
    registry_root = _isolated_registry(tmp_path)
    source = registry_root / "modelos" / "100"
    restated = source / "revisions" / "2021" / "applicability"
    shutil.copytree(_LIVE / "revisions" / "2020" / "applicability", restated)
    for fragment in restated.glob("*.toml"):
        fragment.write_text(
            fragment.read_text(encoding="utf-8").replace('revisions."2020"', 'revisions."2021"'),
            encoding="utf-8",
        )

    outcome = migrate_modelo(
        registry_root=registry_root,
        modelo_id="100",
        work_dir=tmp_path / "work",
    )

    assert outcome.changed
    assert outcome.staged_registry is not None
    assert outcome.after_assessment is not None
    assert outcome.after_assessment.minimal
    assert not (outcome.staged_registry / "modelos/100/revisions/2021/applicability").exists()
