"""Structural gate: the ``*Observation`` family carries no cross-module homonyms.

The bindings vocabulary requires every observation carrier to be
name-distinguishable by domain: a single ``*Observation`` class name must not be
defined in two unrelated modules. Existing carriers are domain-qualified
(``WithholdingObservation``, ``IvaLedgerObservation``, ``InvoiceObservation``,
``RentaDeductibleExpenseObservation``, ``CounterpartAggregationObservation``).

This gate walks the production source tree (tests excluded) and refuses any
``*Observation`` class name that is defined in more than one module. A future
homonym fails here loudly instead of silently overloading the vocabulary a
semantic search relies on.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC_ROOT = Path(__file__).resolve().parents[1]


def _production_python_files() -> list[Path]:
    """Every ``.py`` under ``src/aeat`` except test modules and test packages."""
    files: list[Path] = []
    for path in _SRC_ROOT.rglob("*.py"):
        parts = path.parts
        if "tests" in parts or path.name.startswith("test_"):
            continue
        files.append(path)
    return files


def _observation_class_definitions() -> dict[str, set[str]]:
    """Map each ``*Observation`` class name to the set of modules defining it."""
    definitions: dict[str, set[str]] = defaultdict(set)
    for path in _production_python_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            # A peer's in-flight syntax error in the shared worktree must not
            # mask this gate; skip unparseable files rather than fail spuriously.
            continue
        module = str(path.relative_to(_SRC_ROOT.parent).with_suffix("")).replace("\\", "/").replace("/", ".")
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name.endswith("Observation"):
                definitions[node.name].add(module)
    return definitions


def test_observation_names_have_no_cross_module_homonyms() -> None:
    """No ``*Observation`` class name is defined in two unrelated modules.

    The observation vocabulary is domain-distinguishable by name. A homonym
    (same class name, two modules) is the fragmentation this gate refuses.
    """
    definitions = _observation_class_definitions()
    homonyms = {name: sorted(modules) for name, modules in definitions.items() if len(modules) > 1}
    assert not homonyms, (
        "cross-module *Observation homonyms detected — the observation naming "
        "cohesion is broken; give each carrier a domain-distinct name:\n"
        + "\n".join(f"  {name}: {mods}" for name, mods in sorted(homonyms.items()))
    )


def test_observation_family_is_populated() -> None:
    """Anti-tautology guard: the scan actually finds the observation family.

    If a refactor relocated or renamed the whole family, the homonym gate above
    would pass vacuously; this asserts the scan still sees the carriers it is
    meant to police, so the cohesion gate cannot silently become a no-op.
    """
    definitions = _observation_class_definitions()
    assert len(definitions) >= 20, (
        f"expected the production *Observation family (>=20 carriers); found "
        f"{len(definitions)} — the scan may be mis-rooted or the family relocated"
    )
