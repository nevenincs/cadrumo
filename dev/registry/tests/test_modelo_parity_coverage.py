"""Coverage guards for registry-backed modelo calculation parity."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.directory_scan import scan_directory
from dev.registry.tests._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_TEST_ROOT = Path(__file__).parent


def _modelo_registry_test_ids() -> set[str]:
    """Return every modelo id token named by a ``test_modelo_*_registry.py`` file.

    A model-specific registry test file may cover a single modelo
    (``test_modelo_100_registry.py``) or a batch of modelos consolidated
    into one file (``test_modelo_117_126_128_136_registry.py``,
    ``test_modelo_187_188_194_registry.py``). The ``_``-separated segments
    between the ``test_modelo_`` prefix and the ``_registry`` suffix are
    each a modelo id when the file follows the consolidated-batch
    convention; a non-numeric batch name (``test_modelo_informativas_
    batch2_registry.py``) contributes no id token and is harmless to
    include here since no real modelo id ever collides with one.
    """
    scanned = scan_directory(_TEST_ROOT, pattern="test_modelo_*_registry.py", require_root=True)
    # Measured: with `_TEST_ROOT` pointed at a directory that does not exist this
    # returned 0 ids silently, against 51 healthy, so the parity comparison held
    # over an empty set -- a modelo with no registry test would look covered.
    if not scanned:
        message = (
            f"the parity census reached no modelo registry test under {_TEST_ROOT}; "
            "an empty id set makes every modelo look covered"
        )
        raise AssertionError(message)
    ids: set[str] = set()
    for path in scanned:
        stem = path.stem.removeprefix("test_modelo_").removesuffix("_registry")
        ids.update(stem.split("_"))
    return ids


def test_formula_bearing_modelos_have_constructs_and_model_specific_tests() -> None:
    modelos, _ = _committed_registry_tree()
    covered_ids = _modelo_registry_test_ids()

    violations: list[str] = []
    for modelo in sorted(modelos, key=lambda item: item.id):
        formula_count = sum(len(revision.formulas) for revision in modelo.revisions.values())
        if formula_count == 0:
            continue
        construct_count = sum(len(revision.constructs) for revision in modelo.revisions.values())
        if construct_count == 0:
            violations.append(f"modelo {modelo.id}: has formulas but no registry constructs")
        if modelo.id not in covered_ids:
            violations.append(f"modelo {modelo.id}: has formulas but no model-specific registry test")

    assert violations == []
