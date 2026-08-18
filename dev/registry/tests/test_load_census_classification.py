"""Load-census gate: every module a sanctioned registry load reaches carries one classification.

Wires :mod:`dev.registry.load_census` into the test surface. The property this
pins is exhaustiveness BY CONSTRUCTION: the universe is derived from the import
graph and the package directory, never from the reviewed table, so a module
added tomorrow appears in the universe the moment it is reachable and fails this
gate until somebody decides what runs it. A census that quantified over the
table instead could not see an unenrolled module at all -- absence from the
declaration is exactly what is being asked about.

No count is asserted anywhere here. The universe grows whenever the package
does, and a pinned tally would train everyone to update a constant and then
detect nothing.

The anti-tautology proof is
:func:`test_a_planted_module_is_reported_unclassified`. If the resolver ever
answers for a module no rule covers -- a too-greedy prefix, a silent default --
the clean result above becomes a false all-clear, and every other assertion in
this file becomes decorative.
"""

from __future__ import annotations

import pytest
from dev.registry.load_census import (
    REGISTRY_PACKAGE,
    build_reference_map,
    build_runtime_graph,
    census_universe,
    registry_package_modules,
    run_census,
    static_load_closure,
    unreferenced_modules,
)
from dev.registry.load_census_classification import RULES, classify_universe

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PLANTED = "cadrumo.domain.calculations.registry._module_that_does_not_exist"


def test_every_reachable_module_carries_exactly_one_classification() -> None:
    """No module in the derived universe is left for someone else to decide."""
    report = run_census()

    assert report.unclassified == ()
    assert report.stale_rules == ()
    assert report.clean


def test_a_planted_module_is_reported_unclassified() -> None:
    """The resolver refuses to answer for a module no rule covers.

    Planted from OUTSIDE the tree -- no file is written, so a peer's sweep
    cannot commit the mutation and a crashed run leaves no residue.
    """
    planted_universe = frozenset({_PLANTED})

    assert _PLANTED not in classify_universe(planted_universe)


def test_a_real_module_resolves_so_the_planted_proof_is_not_vacuous() -> None:
    """The same resolver answers for a module that IS covered."""
    resolved = classify_universe(frozenset({f"{REGISTRY_PACKAGE}._loader"}))

    assert resolved[f"{REGISTRY_PACKAGE}._loader"].classification == "live"


def test_every_conditionally_reachable_rule_names_its_trigger() -> None:
    """A classification whose trigger names no surface is an unanswered question."""
    conditional = [rule for rule in RULES if rule.classification == "conditionally_reachable"]

    assert conditional, "the table has lost its conditional rules; the gate would pass vacuously"
    assert all(len(rule.trigger.split()) >= 3 and rule.reason.strip() for rule in conditional)


def test_the_registry_package_is_covered_whether_or_not_the_load_imports_it() -> None:
    """A registry module outside the load closure is still in the universe.

    This is the case the census exists to catch. Deriving the universe from the
    closure alone would silently exempt exactly the modules a load never
    reaches, which is the population under investigation.
    """
    graph = build_runtime_graph()

    assert registry_package_modules() <= census_universe(graph)
    assert registry_package_modules() - static_load_closure(graph)


def test_dead_candidates_are_adjudicated_rather_than_assumed() -> None:
    """Every module nothing reaches carries an explicit ``dead`` decision.

    The candidate set is empty at present, and that emptiness is a finding in
    its own right: two modules reached it on the first run and both survived
    review, because their consumers import them through the package facade.
    """
    graph = build_runtime_graph()
    candidates = unreferenced_modules(graph, build_reference_map())
    classified = classify_universe(census_universe(graph))

    assert all(classified[module].classification == "dead" for module in candidates)


def test_the_static_closure_matches_what_a_real_load_imports(
    registry_authority: object,
) -> None:
    """The closure is checked against reality, not trusted as a graph artefact.

    A closure computed from an import graph is a claim about the running
    program. Here it is confronted with ``sys.modules`` after the session
    authority has loaded: every registry module the graph says a load imports
    must actually be there.
    """
    import sys

    assert registry_authority is not None
    imported = {name for name in sys.modules if name == REGISTRY_PACKAGE or name.startswith(REGISTRY_PACKAGE + ".")}
    closure = {m for m in static_load_closure(build_runtime_graph()) if m.startswith(REGISTRY_PACKAGE)}

    assert closure <= imported
