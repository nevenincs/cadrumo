"""Every value-feeding cross-period relation is consumed; evidence relations may not be.

A registry relation materialises a ``target_binding`` slot. A relation that feeds a
casilla value (``dependency_role`` of ``direct_calculation``,
``instalment_to_final_settlement``, or ``periodic_to_annual_summary``) is only
live if something consumes that slot — a ``casilla.binding`` or a formula operand
referencing the binding or the relation directly. A value-feeding relation whose
slot nothing consumes is an inert cross-period wiring gap: the prior-period value
it carries never reaches the dependent casilla, and the dependent casilla silently
holds no contribution.

A ``factual_evidence`` relation is the deliberate exception: it is a supplementary
cross-check (e.g. the M115 arrendamientos relation, whose casilla stays a manual
form-native entry, or the M180/M190/M193 annual-resumen relations that restate
withholdings already folded via the periodic quarters). Consuming it as a value
would double-count, so it is expected to remain unconsumed and is excluded here.

This gate is the registry-wide consumption invariant: a new value-feeding relation
added without wiring its slot fails immediately, while the supplementary evidence
set is allowed to stand unconsumed by its declared role.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from .....core.resources import bundled_path
from .._loader import load_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")

# Roles whose relation must feed a consumed value slot to be live.
_VALUE_FEEDING_ROLES = frozenset(
    {
        "direct_calculation",
        "instalment_to_final_settlement",
        "periodic_to_annual_summary",
    }
)
# The deliberate exception: supplementary cross-check evidence, expected unconsumed.
_EVIDENCE_ROLE = "factual_evidence"


def _walk(expression) -> Iterator[object]:
    yield expression
    for arg in getattr(expression, "args", ()) or ():
        yield from _walk(arg)


def _consumption_index(revision) -> tuple[set[str], set[str], set[str]]:
    """Return (casilla-bound bindings, formula-referenced relations, formula-referenced bindings)."""
    casilla_bindings = {c.binding for c in revision.casillas if getattr(c, "binding", None)}
    formula_relations: set[str] = set()
    formula_bindings: set[str] = set()
    for formula in revision.formulas:
        for node in _walk(formula.expression):
            relation_ref = getattr(node, "relation", None)
            if relation_ref:
                formula_relations.add(relation_ref)
            binding_ref = getattr(node, "binding", None)
            if binding_ref:
                formula_bindings.add(binding_ref)
    return casilla_bindings, formula_relations, formula_bindings


def _relation_is_consumed(relation, index: tuple[set[str], set[str], set[str]]) -> bool:
    casilla_bindings, formula_relations, formula_bindings = index
    if relation.id in formula_relations:
        return True
    target = getattr(relation, "target_binding", None)
    return bool(target) and (target in casilla_bindings or target in formula_bindings)


def test_no_inert_value_feeding_cross_period_relations() -> None:
    """No value-feeding relation is left with an unconsumed target slot.

    A failure here means a cross-period relation carries a prior-period value into a
    slot nothing reads — the value silently never reaches its dependent casilla.
    Wire the slot (bind the target casilla or reference the relation in a formula),
    or, if the relation is a supplementary cross-check, declare it
    ``dependency_role = "factual_evidence"``.
    """
    modelos, _catalogues = load_registry_tree(_REGISTRY_ROOT)
    gaps: list[str] = []
    for modelo in modelos:
        for revision_id, revision in modelo.revisions.items():
            relations = getattr(revision, "relations", ()) or ()
            if not relations:
                continue
            index = _consumption_index(revision)
            for relation in relations:
                role = getattr(relation, "dependency_role", None)
                if role not in _VALUE_FEEDING_ROLES:
                    continue
                if not _relation_is_consumed(relation, index):
                    gaps.append(
                        f"{modelo.id}/{revision_id}: relation {relation.id!r} "
                        f"(role={role!r}, target_binding="
                        f"{getattr(relation, 'target_binding', None)!r}) is unconsumed"
                    )

    assert not gaps, (
        "Inert value-feeding cross-period relation(s) found — each carries a "
        "prior-period value into a slot nothing consumes:\n"
        + "\n".join(f"  * {gap}" for gap in gaps)
    )


def test_evidence_relations_are_the_only_unconsumed_relations() -> None:
    """Every unconsumed relation is a declared ``factual_evidence`` cross-check.

    Pins the converse: the supplementary set is the sole reason a relation may be
    unconsumed. If a non-evidence relation becomes unconsumed it is caught above;
    if an evidence relation becomes consumed (wired into a value) it should be
    reclassified to a value-feeding role and is surfaced here.
    """
    modelos, _catalogues = load_registry_tree(_REGISTRY_ROOT)
    unconsumed_roles: set[str] = set()
    for modelo in modelos:
        for _revision_id, revision in modelo.revisions.items():
            relations = getattr(revision, "relations", ()) or ()
            if not relations:
                continue
            index = _consumption_index(revision)
            for relation in relations:
                if not _relation_is_consumed(relation, index):
                    unconsumed_roles.add(getattr(relation, "dependency_role", None))

    assert unconsumed_roles <= {_EVIDENCE_ROLE}, (
        f"Unconsumed relations carry unexpected roles {unconsumed_roles - {_EVIDENCE_ROLE}!r}; "
        f"only {_EVIDENCE_ROLE!r} cross-checks may stand unconsumed."
    )
