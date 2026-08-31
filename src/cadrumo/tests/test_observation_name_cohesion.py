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

See Also:
    :mod:`~tests._inventory`
        Provides the production AST inventory used by this cohesion gate.
    :class:`~domain.calculations.registry.RegistryModeloObservation`
        Canonical registry observation carrier protected from generic
        ``Observation`` homonyms by the binding vocabulary pass.

Every binding and observation name must stay domain-qualified so a reader (or
a semantic search) can trust the name without cross-checking the module.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path

import pytest

from .inventory import module_name, production_ast_items

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _observation_class_definitions(source_tree_ast: Mapping[Path, ast.AST] | None = None) -> dict[str, set[str]]:
    """Map each ``*Observation`` class name to the set of modules defining it."""
    definitions: dict[str, set[str]] = defaultdict(set)
    for path, tree in production_ast_items(source_tree_ast):
        module = module_name(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name.endswith("Observation"):
                definitions[node.name].add(module)
    return definitions


@pytest.fixture(scope="module")
def observation_class_definitions(source_tree_ast: Mapping[Path, ast.AST]) -> dict[str, set[str]]:
    """Return the production ``*Observation`` class inventory once for this module."""
    return _observation_class_definitions(source_tree_ast)


def test_observation_names_have_no_cross_module_homonyms(
    observation_class_definitions: dict[str, set[str]],
) -> None:
    """No ``*Observation`` class name is defined in two unrelated modules.

    The observation vocabulary is domain-distinguishable by name. A homonym
    (same class name, two modules) is the fragmentation this gate refuses.
    """
    homonyms = {name: sorted(modules) for name, modules in observation_class_definitions.items() if len(modules) > 1}
    assert not homonyms, (
        "cross-module *Observation homonyms detected — the observation naming "
        "cohesion is broken; give each carrier a domain-distinct name:\n"
        + "\n".join(f"  {name}: {mods}" for name, mods in sorted(homonyms.items()))
    )


def test_observation_family_is_populated(observation_class_definitions: dict[str, set[str]]) -> None:
    """Anti-tautology guard: the scan actually finds the observation family.

    If a refactor relocated or renamed the whole family, the homonym gate above
    would pass vacuously; this asserts the scan still sees the carriers it is
    meant to police, so the cohesion gate cannot silently become a no-op.
    """
    assert len(observation_class_definitions) >= 20, (
        f"expected the production *Observation family (>=20 carriers); found "
        f"{len(observation_class_definitions)} — the scan may be mis-rooted or the family relocated"
    )
