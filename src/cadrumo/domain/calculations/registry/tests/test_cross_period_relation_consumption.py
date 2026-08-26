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
withholdings already folded via the periodic quarters). It may remain unconsumed;
some annual-resumen relations are declared as alternate binding channels, and the
canonical index must still report that real declaration rather than hiding it.

This gate is the registry-wide consumption invariant: a new value-feeding relation
added without wiring its slot fails immediately, while the supplementary evidence
set is allowed to stand unconsumed by its declared role.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.handoffs import relation_consumption_index, relation_is_consumed
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from .....core import Modelo
from ..authority import bundled_authority
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

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


def test_relation_consumption_includes_real_alternate_binding_channel() -> None:
    snapshot = bundled_authority().snapshot(Modelo.M390.value, filing_year=2025, period="0A")
    relation = next(
        item for item in snapshot.revision.relations if item.id == "modelo-390-rel-303-cuota-devengada-total"
    )
    target = next(item for item in snapshot.revision.casillas if item.binding == relation.target_binding)
    revised_target = CasillaDefinition.model_validate(
        {
            **target.model_dump(),
            "localization_keys": target.localization_keys,
            "binding": "modelo-390-prev-303-cuota-deducible-total",
            "alternate_bindings": (relation.target_binding,),
        },
    )
    revision = snapshot.revision.model_copy(
        update={
            "casillas": tuple(revised_target if item.id == target.id else item for item in snapshot.revision.casillas),
        },
    )

    assert relation.target_binding not in {item.binding for item in revision.casillas}
    assert relation_is_consumed(relation, relation_consumption_index(revision))


def test_no_inert_value_feeding_cross_period_relations() -> None:
    """No value-feeding relation is left with an unconsumed target slot.

    A failure here means a cross-period relation carries a prior-period value into a
    slot nothing reads — the value silently never reaches its dependent casilla.
    Wire the slot (bind the target casilla or reference the relation in a formula),
    or, if the relation is a supplementary cross-check, declare it
    ``dependency_role = "factual_evidence"``.
    """
    modelos, _catalogues = _committed_registry_tree()
    gaps: list[str] = []
    for modelo in modelos:
        for revision_id, revision in modelo.revisions.items():
            relations = revision.relations
            if not relations:
                continue
            index = relation_consumption_index(revision)
            for relation in relations:
                role = getattr(relation, "dependency_role", None)
                if role not in _VALUE_FEEDING_ROLES:
                    continue
                if not relation_is_consumed(relation, index):
                    gaps.append(
                        f"{modelo.id}/{revision_id}: relation {relation.id!r} "
                        f"(role={role!r}, target_binding="
                        f"{getattr(relation, 'target_binding', None)!r}) is unconsumed"
                    )

    assert not gaps, (
        "Inert value-feeding cross-period relation(s) found — each carries a "
        "prior-period value into a slot nothing consumes:\n" + "\n".join(f"  * {gap}" for gap in gaps)
    )


def test_evidence_relations_are_the_only_unconsumed_relations() -> None:
    """Every unconsumed relation is a declared ``factual_evidence`` cross-check.

    Pins the converse: the supplementary set is the sole reason a relation may be
    unconsumed. If a non-evidence relation becomes unconsumed it is caught above.
    Evidence relations that are alternate binding channels remain honestly
    classified as consumed by the production index.
    """
    modelos, _catalogues = _committed_registry_tree()
    unconsumed_roles: set[str] = set()
    for modelo in modelos:
        for _revision_id, revision in modelo.revisions.items():
            relations = revision.relations
            if not relations:
                continue
            index = relation_consumption_index(revision)
            for relation in relations:
                if not relation_is_consumed(relation, index):
                    unconsumed_roles.add(relation.dependency_role)

    assert unconsumed_roles <= {_EVIDENCE_ROLE}, (
        f"Unconsumed relations carry unexpected roles {unconsumed_roles - {_EVIDENCE_ROLE}!r}; "
        f"only {_EVIDENCE_ROLE!r} cross-checks may stand unconsumed."
    )
