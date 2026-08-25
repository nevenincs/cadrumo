"""Both sides of a reconciliation pair must aggregate the same IVA categories.

A modelo that reconciles its totals against another modelo's is only consistent
if the two sides aggregate the same ledger categories into the concepts they
BOTH model. Adding a category to one side and not the other leaves the pair
arithmetically divergent, which surfaces either as a blocked filing or as a
silently under-declared return.

That is not hypothetical. Routing a new intra-community SERVICES category onto
the Modelo 303 quarterly line without the Modelo 390 annual line produced
exactly this: 63.00 goods + 21.00 services gave 84.00 on the quarters and 63.00
on the annual return, and nothing in the suite objected. The annual surface had
tests; none of them compared the two sides' category sets.

What this gate does NOT cover, stated so nobody reads more into a green run:

* Selecting the same categories is not producing the same VALUE. Two sides can
  agree on every category and still disagree arithmetically through a different
  fact, rate-kind filter, flow direction, or aggregation op. Value agreement is
  the reconciliation blocking rules' job, not this gate's.
* Only concepts BOTH sides model are compared. Modelo 390 models 22 casillas and
  simply has no counterpart for several Modelo 303 boxes; a concept absent from
  one side is out of scope here rather than a divergence, because "should this
  modelo model that box at all" is a registry-completeness question with its own
  grounding.
* Only ``ledger_iva_aggregation`` bindings are compared. A concept fed by a
  relation or a previous-filing carry on one side and by ledger aggregation on
  the other is not a category-parity question.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

import pytest

from .....core import BindingSourceKind
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.binding_selector_utils import selector_as_dict
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


# The reconciliation pairs this gate expects to find, as (target, counterpart).
# Pinned so that a NEW pair cannot enter the registry without an author reading
# this file: a pair added in a shape the derivation understands changes the
# derived set and reds here, and one added in a shape it does not understand is
# caught by the reconciliation-casilla coverage test below.
_EXPECTED_PAIRS = frozenset(
    {
        ("180", "115"),
        ("190", "111"),
        ("193", "123"),
        # IRNR's annual/periodic pair, the same shape 190/111 carries for IRPF:
        # the registry titles them "IRNR resumen anual de retenciones e ingresos
        # a cuenta" and "IRNR retenciones e ingresos a cuenta", so the summary
        # reconciles against the periodic declarations it sums.
        ("296", "216"),
        ("353", "322"),
        ("390", "303"),
    },
)

# Modelo id suffix on a reconciliation casilla, e.g.
# ``iva.anual.reconciliacion.devengada-303`` -> ``303``.
_RECONCILIATION_CASILLA_SUFFIX = re.compile(r"reconciliacion\.[a-z0-9-]*?-(\d{3})$")


def _cross_modelo_source(revision: ModeloRevision, owning_modelo: str) -> set[str]:
    """Return counterpart modelo ids this revision reconciles against.

    Reads BOTH declaration sites, because the registry expresses the same
    relationship two ways and either alone undercounts. Querying only the
    relation site returns four pairs where five exist: the grupo pair
    (M353 against M322) is declared as a ``previous_filing`` binding carrying a
    cross-modelo ``source_modelo``, never as a relation. A gate built on the
    relation list alone would pass over that pair permanently -- which is the
    same blind spot that let the M390 divergence ship.

    Narrowed to the two RECONCILIATION shapes by their declared semantics, not
    by an id list. A cross-modelo dependency is not automatically a
    reconciliation: ``cross_model_output`` carries one value into another
    modelo's calculation (M100 folding in an M130 pago fraccionado), and the two
    sides are never asserted equal. Only a periodic-to-annual summary and a
    grupo member-to-aggregate rollup claim that the sides agree, which is what
    makes category parity meaningful for them.
    """
    counterparts: set[str] = set()
    for relation in getattr(revision, "relations", ()):
        if str(getattr(relation, "kind", "")) != "annual_summary":
            continue
        source = getattr(relation, "source_modelo", None)
        if source is not None and str(source) != owning_modelo:
            counterparts.add(str(source))
    for binding in revision.bindings:
        if binding.source != BindingSourceKind.PREVIOUS_FILING:
            continue
        selector = selector_as_dict(binding)
        if str(selector.get("grouping") or "") != "per_grupo_member":
            continue
        source = selector.get("source_modelo")
        if source is not None and str(source) != owning_modelo:
            counterparts.add(str(source))
    return counterparts


def _ledger_categories_by_semantic_role(revision: ModeloRevision) -> Mapping[str, frozenset[str]]:
    """Map each ledger-IVA-bound casilla's ``semantic_role`` to its category set.

    ``semantic_role`` is the join key rather than the casilla id, because the two
    sides of a pair deliberately number the same concept differently -- the
    annual ``iva.anual.autorepercutido.intracomunitaria`` and the quarterly
    ``iva.autorepercutido.intracomunitaria`` share the role
    ``iva_cuota_autorepercutida_intracomunitaria`` and nothing else.
    """
    bindings_by_id = {str(binding.id): binding for binding in revision.bindings}
    roles: dict[str, frozenset[str]] = {}
    for casilla in revision.casillas:
        role = getattr(casilla, "semantic_role", None)
        binding_id = getattr(casilla, "binding", None)
        if role is None or binding_id is None:
            continue
        binding = bindings_by_id.get(str(binding_id))
        if binding is None or binding.source != BindingSourceKind.LEDGER_IVA_AGGREGATION:
            continue
        raw_categories = selector_as_dict(binding).get("categories")
        # ``or ()`` alone leaves the element type unknown, so the
        # comprehension below reads as iterating something that may not be
        # iterable. Declaring the fallback keeps the same behaviour and
        # states what a missing selector key yields.
        categories: tuple[object, ...] = tuple(raw_categories) if isinstance(raw_categories, list | tuple) else ()
        roles[str(role)] = frozenset(str(category) for category in categories)
    return roles


def _derive_pairs() -> dict[tuple[str, str], tuple[ModeloRevision, ModeloRevision]]:
    """Return every reconciliation pair with the two revisions to compare."""
    modelos, _catalogues = _committed_registry_tree()
    by_id = {modelo.id: modelo for modelo in modelos}
    pairs: dict[tuple[str, str], tuple[ModeloRevision, ModeloRevision]] = {}
    for modelo in modelos:
        for revision in modelo.revisions.values():
            for counterpart_id in _cross_modelo_source(revision, modelo.id):
                counterpart = by_id.get(counterpart_id)
                if counterpart is None:
                    continue
                counterpart_revision = max(counterpart.revisions.values(), key=lambda item: item.id)
                pairs.setdefault((modelo.id, counterpart_id), (revision, counterpart_revision))
    return pairs


def test_reconciliation_pair_derivation_is_not_vacuous() -> None:
    """The derived pair set matches the pinned inventory, and is non-empty.

    A gate that enumerates zero pairs passes cleanly and protects nothing, so the
    count is asserted rather than assumed. The pinned set also makes a NEW pair
    a deliberate decision: adding one reds this test until its author confirms
    the parity assertion below is right for it.
    """
    derived = frozenset(_derive_pairs())
    assert derived, "no reconciliation pairs derived; the gate would protect nothing"
    assert derived == _EXPECTED_PAIRS, (
        f"reconciliation pair inventory changed; derived-only={sorted(derived - _EXPECTED_PAIRS)}, "
        f"expected-only={sorted(_EXPECTED_PAIRS - derived)}"
    )


def test_every_reconciliation_casilla_belongs_to_a_derived_pair() -> None:
    """A reconciliation casilla naming a modelo the derivation missed fails loudly.

    This is the third-shape detector. The two derivation sites read relations and
    previous-filing bindings; a pair declared some future third way would be
    silently skipped by them, and silence is the failure mode that let the M390
    divergence ship. Reconciliation casillas name their counterpart modelo in the
    id suffix, so every such suffix must resolve to a pair the derivation already
    found -- otherwise there is a reconciliation the gate above cannot see.
    """
    modelos, _catalogues = _committed_registry_tree()
    derived = _derive_pairs()
    orphans: list[str] = []
    checked = 0
    for modelo in modelos:
        for revision in modelo.revisions.values():
            for casilla in revision.casillas:
                match = _RECONCILIATION_CASILLA_SUFFIX.search(str(casilla.id))
                if match is None:
                    continue
                checked += 1
                if (modelo.id, match.group(1)) not in derived:
                    orphans.append(f"{modelo.id}:{casilla.id} -> counterpart {match.group(1)}")
    assert checked > 0, "no reconciliation casillas found; the third-shape detector is vacuous"
    assert not orphans, f"reconciliation casillas whose pair the derivation missed: {sorted(orphans)}"


def test_reconciliation_pairs_aggregate_the_same_categories() -> None:
    """Both sides of every pair select the same categories for shared concepts.

    Compared per ``semantic_role``, so only concepts both sides model are in
    scope. A divergence here means one side booked a category the other dropped,
    which is the M390 defect: quarterly 84.00 against annual 63.00.
    """
    divergences: list[str] = []
    compared = 0
    for (target_id, counterpart_id), (target_revision, counterpart_revision) in sorted(_derive_pairs().items()):
        target_roles = _ledger_categories_by_semantic_role(target_revision)
        counterpart_roles = _ledger_categories_by_semantic_role(counterpart_revision)
        for role in sorted(set(target_roles) & set(counterpart_roles)):
            compared += 1
            if target_roles[role] == counterpart_roles[role]:
                continue
            only_target = sorted(target_roles[role] - counterpart_roles[role])
            only_counterpart = sorted(counterpart_roles[role] - target_roles[role])
            divergences.append(
                f"M{target_id}<->M{counterpart_id} role {role!r}: "
                f"only on M{target_id}={only_target}, only on M{counterpart_id}={only_counterpart}",
            )
    assert compared > 0, "no shared ledger-bound roles compared; the parity assertion is vacuous"
    assert not divergences, "reconciliation pairs disagree on aggregated categories: " + "; ".join(divergences)


#: The role whose disappearance from the shared set would be silent.
#:
#: The intra-community autorepercutido concept is the one this whole gate was
#: built from: routing a services category onto the quarterly line without the
#: annual line gave 84.00 against 63.00 and nothing objected.
_INTRACOM_AUTOREPERCUTIDO_ROLE = "iva_cuota_autorepercutida_intracomunitaria"


def test_the_intracom_concept_is_still_inside_the_compared_set() -> None:
    """The originating concept stays covered, named rather than counted.

    ``test_reconciliation_pairs_aggregate_the_same_categories`` guards against
    vacuity with ``compared > 0``, which is the right global check and the wrong
    one for this. The comparison runs over the INTERSECTION of the two sides'
    semantic roles, and an intersection shrinks silently: if one side stops
    carrying a role, that role simply stops being compared while every other
    role keeps the count positive. The gate goes on passing and quietly covers
    less.

    That is not hypothetical for this role. Splitting an annual casilla per leg
    — the M390 under-modelling work — gives the annual side two per-leg roles
    where the quarterly side carries one combined role. Neither new role
    intersects the old one, so the concept drops out of the comparison on the
    day the split lands, with no test reddening anywhere.

    Naming the role is what makes that loud. If a split retires this role, this
    test fails and forces a deliberate choice: carry the combined role on both
    sides, or teach the gate the per-leg mapping. Both are fine; losing the
    coverage without noticing is not.
    """
    covered: list[str] = []
    for (target_id, counterpart_id), (target_revision, counterpart_revision) in sorted(_derive_pairs().items()):
        shared = set(_ledger_categories_by_semantic_role(target_revision)) & set(
            _ledger_categories_by_semantic_role(counterpart_revision),
        )
        if _INTRACOM_AUTOREPERCUTIDO_ROLE in shared:
            covered.append(f"M{target_id}<->M{counterpart_id}")

    assert covered, (
        f"role {_INTRACOM_AUTOREPERCUTIDO_ROLE!r} is compared by no reconciliation pair. "
        "It is the concept this gate was built from, so its absence from every shared set "
        "means the gate no longer covers the divergence it exists to catch. If an annual "
        "casilla was split per leg, the annual side now carries per-leg roles that do not "
        "intersect the quarterly side's combined role -- decide whether both sides carry the "
        "combined role or the gate learns the per-leg mapping, rather than letting the "
        "intersection shrink silently"
    )
