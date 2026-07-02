"""Compiled-schema equality gate for the inline-to-fragmented revision migration.

Each committed baseline under ``_inline_fragment_baselines/`` is the
``model_dump(mode="json")`` of one revision's compiled :class:`ModeloRevision`
captured at its pre-migration (inline ``revision.toml``) shape. The gate reloads
the same revision from the live registry tree at its post-migration (fragmented)
shape and asserts the compiled output is byte-for-byte identical, proving the
authoring-surface move carried zero semantic drift.

This is a transient migration gate authored for the registry-format convergence
campaign; it is deleted once every inline revision has migrated and the loader
inline-parsing tolerance is removed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .....core.resources import bundled_path
from .._loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BASELINE_DIR = Path(__file__).parent / "_inline_fragment_baselines"


def _baseline_paths() -> list[Path]:
    return sorted(_BASELINE_DIR.glob("*.json"))


@pytest.mark.parametrize("baseline_path", _baseline_paths(), ids=lambda path: path.stem)
def test_migrated_revision_matches_pre_migration_compiled_schema(baseline_path: Path) -> None:
    payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    modelo_id = payload["modelo_id"]
    revision_id = payload["revision_id"]
    expected = payload["revision"]

    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", modelo_id))
    revision = modelo.revisions[revision_id]
    actual = revision.model_dump(mode="json")

    assert actual == expected, (
        f"fragmented {modelo_id}/{revision_id} compiled to a different ModeloRevision "
        f"than its pre-migration inline shape"
    )


def test_baseline_fixtures_present() -> None:
    """Guard against an empty parametrisation silently passing."""
    assert _baseline_paths(), "no inline-fragment migration baselines are present"
