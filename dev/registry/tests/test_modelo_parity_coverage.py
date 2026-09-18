"""Coverage guards for registry-backed modelo calculation parity."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.directory_scan import scan_directory

from ..conformance.registry_schema_support import committed_registry_tree as _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_TEST_ROOT = Path(__file__).parent


def _modelo_registry_test_ids() -> set[str]:
    """Return every modelo id token named by a ``test_modelo_*.py`` file.

    A model-specific test file may cover a single modelo
    (``test_modelo_303_registry.py``) or a batch of modelos consolidated into
    one file (``test_modelo_490_604_763_registry.py``). The modelo's own tests
    are also routinely split by subject rather than kept in one
    ``_registry``-suffixed file -- Modelo 100 alone carries a couple of dozen
    ``test_modelo_100_*.py`` modules -- so the census reads the whole
    ``test_modelo_`` family rather than the suffix, which would report a
    thoroughly covered modelo as covered by nothing.

    Every ``_``-separated segment of the name contributes a token. A
    non-numeric one (``informativas``, ``batch2``, ``tarifa``) is harmless
    because no real modelo id collides with it.
    """
    scanned = scan_directory(_TEST_ROOT, pattern="test_modelo_*.py", require_root=True)
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
        ids.update(path.stem.removeprefix("test_modelo_").split("_"))
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
