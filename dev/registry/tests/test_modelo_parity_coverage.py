"""Coverage guards for registry-backed modelo calculation parity."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.directory_scan import scan_directory

from ..conformance.registry_schema_support import committed_registry_tree as _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Both homes a model-specific registry test lives in. The development tests
#: sit beside this module; the package's own registry tests sit under
#: ``src/cadrumo/domain/calculations/registry/tests`` and carry fifty more
#: modelo files, including the 117/126/128/136 arithmetic batch and modelo 714.
#: A census reading one root reported every one of those modelos as untested.
_TEST_ROOTS = (
    Path(__file__).parent,
    Path(__file__).resolve().parents[3] / "src" / "cadrumo" / "domain" / "calculations" / "registry" / "tests",
)


#: The two spellings a model-specific test file uses for the modelo it covers.
#: Both are live in this directory, and a census reading only one reports a
#: covered modelo as covered by nothing -- which is how Modelo 353 came to be
#: listed as untested beside ``test_m353_2024_grupo_entidades_manual_worked_example.py``.
_MODELO_TEST_PREFIXES = ("test_modelo_", "test_m")


def _modelo_registry_test_ids() -> set[str]:
    """Return every modelo id token named by a model-specific test file.

    A model-specific test file may cover a single modelo
    (``test_modelo_303_registry.py``) or a batch of modelos consolidated into
    one file (``test_modelo_490_604_763_registry.py``). The modelo's own tests
    are also routinely split by subject rather than kept in one
    ``_registry``-suffixed file -- Modelo 100 alone carries a couple of dozen
    ``test_modelo_100_*.py`` modules -- so the census reads the whole family
    rather than the suffix.

    Every ``_``-separated segment of the name contributes a token. A
    non-numeric one (``informativas``, ``batch2``, ``tarifa``) is harmless
    because no real modelo id collides with it.
    """
    scanned: set[Path] = set()
    for root in _TEST_ROOTS:
        # Measured: with a root pointed at a directory that does not exist the
        # walk returned 0 ids silently, against 51 healthy, so the parity
        # comparison held over an empty set -- a modelo with no registry test
        # would look covered. Each root is required to contribute.
        found = {
            path
            for prefix in _MODELO_TEST_PREFIXES
            for path in scan_directory(root, pattern=f"{prefix}*.py", require_root=True)
        }
        if not found:
            message = (
                f"the parity census reached no modelo registry test under {root}; "
                "an empty id set makes every modelo look covered"
            )
            raise AssertionError(message)
        scanned |= found
    ids: set[str] = set()
    for path in sorted(scanned):
        stem = path.stem
        for prefix in _MODELO_TEST_PREFIXES:
            if stem.startswith(prefix):
                stem = stem[len(prefix) :]
                break
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
