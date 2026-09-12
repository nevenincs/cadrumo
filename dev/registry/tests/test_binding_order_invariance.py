"""Binding declaration order decides nothing a filing depends on.

A revision's ``bindings`` tuple is a merge artefact: the loader concatenates the
binding fragments in ``sorted(rglob("*.toml"))`` order, so a fragment's
*filename* is its position. Renaming a fragment, splitting one, or authoring a
new family therefore permutes the tuple without changing a single declaration.
Four consumers read that tuple in ways that could survive such a permutation
only by accident, and this gate holds each of them to it:

* the prorrata regularisation source roles, which are read POSITIONALLY out of
  the concatenated ``source_casilla_ids`` of every prorrata binding;
* export field derivation, which keeps the FIRST binding to claim a record's
  ``row_field`` and silently drops every later claimant;
* the Modelo 303/4T simplified-regime annual summary, whose endpoints are held
  to official Modelo 390 box numbers 74-83;
* the Modelo 720 foreign-asset valuation binding, discovered by FIRST MATCH on
  the money data type.

Three of the four are order-free because the declaration they read is unique:
one prorrata binding, one claimant per ``row_field`` slot, one money-typed
foreign-asset binding. That uniqueness is not a coincidence of the current
corpus -- the first two are refused at load by
:func:`~dev.registry.compiler.validate_bindings.validate_binding_registration_section`
for the first two -- so the assertions below pin both the permutation invariance
and the singularity that produces it. The fourth, the annual summary, is keyed
by each endpoint's own official box number rather than by its position.

Every test carries its own anti-tautology control: a defect constructed in
memory with ``model_copy`` that MUST become visible to the same comparison. A
permutation that stopped moving anything, or a comparison too coarse to see a
swapped claimant, would make the invariance half pass vacuously. The bundled
corpus is only ever read; nothing is written.

Modelo 193 is covered for the export site even though it declares none of the
three other families: it is a large row-binding corpus member and its export
records are derived through the same first-wins path.
"""

from __future__ import annotations

from functools import cache
from hashlib import blake2b
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from cadrumo.application.calculations.prorrata_regularizacion import (
    # The four positional role reads in prorrata_regularizacion all index this
    # one derived tuple, so it is the exact surface an order dependency would
    # move. There is no public projection of it: the public resolver needs live
    # ledger and observation repositories, which a corpus gate has no business
    # standing up.
    _prorrata_source_casilla_ids,
)
from cadrumo.core.aggregation import BindingAggregationOp
from cadrumo.domain.calculations.registry.binding_aggregation import binding_aggregation_op
from cadrumo.domain.calculations.registry.binding_selector_utils import selector_as_dict
from cadrumo.domain.calculations.registry.detail_record_bindings import ForeignAssetProvider
from cadrumo.domain.calculations.registry.export import derive_export_layouts_from_bindings
from cadrumo.domain.calculations.registry.m303_regimen_simplificado_annual_summary_bindings import (
    m303_regimen_simplificado_annual_summary_requirement,
    validate_m303_regimen_simplificado_annual_summary_revision,
)
from cadrumo.domain.calculations.registry.prorrata_regularizacion_bindings import ProrrataRegularizacionProvider
from cadrumo.domain.calculations.registry.schema_base import CasillaDataType

from ..compiler.loader import load_modelo_directory

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.schema import BindingDefinition, ModeloRevision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELOS_ROOT = Path(__file__).resolve().parents[3] / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos"

#: Modelo 303 and 390 carry the prorrata binding, 390 the annual summary, 720
#: the foreign-asset family; 193 contributes a large row-binding export corpus.
_COVERED_MODELOS = ("303", "193", "390", "720")

#: Several independent permutations. One seed could leave a two-member pair in
#: its original relative order and prove nothing about that pair. Seed 0 is the
#: reversal, the maximal permutation, which moves every member that can move.
_SEEDS = (0, 1, 2, 3, 7, 11, 13)


@cache
def _revisions(modelo_id: str) -> tuple[tuple[str, ModeloRevision], ...]:
    """Compile one bundled modelo directory once per session."""
    modelo = load_modelo_directory(_MODELOS_ROOT / modelo_id)
    return tuple(sorted(modelo.revisions.items()))


def _shuffled(revision: ModeloRevision, seed: int) -> ModeloRevision:
    """Return ``revision`` with its binding tuple permuted and nothing else changed.

    The permutation is a keyed digest sort rather than a PRNG shuffle so that a
    failure is reproducible from the seed alone on any interpreter, and seed 0
    is the reversal so at least one run moves every member that can move.
    """
    bindings = list(revision.bindings)
    if seed == 0:
        bindings.reverse()
    else:
        bindings.sort(key=lambda binding: blake2b(f"{seed}:{binding.id}".encode()).digest())
    return revision.model_copy(update={"bindings": tuple(bindings)})


def _with_bindings(revision: ModeloRevision, bindings: tuple[BindingDefinition, ...]) -> ModeloRevision:
    return revision.model_copy(update={"bindings": bindings})


def _covered_revisions() -> list[tuple[str, str, ModeloRevision]]:
    return [(modelo_id, rid, rev) for modelo_id in _COVERED_MODELOS for rid, rev in _revisions(modelo_id)]


def _revision_params() -> list[Any]:
    return [
        pytest.param(modelo_id, revision, id=f"{modelo_id}-{revision_id}")
        for modelo_id, revision_id, revision in _covered_revisions()
    ]


# --------------------------------------------------------------------------
# Site 1: the positional prorrata source roles.
# --------------------------------------------------------------------------


def _prorrata_bindings(revision: ModeloRevision) -> tuple[BindingDefinition, ...]:
    return tuple(b for b in revision.bindings if isinstance(b.provider, ProrrataRegularizacionProvider))


@pytest.mark.parametrize(("modelo_id", "revision"), _revision_params())
def test_prorrata_source_roles_do_not_move_with_binding_order(modelo_id: str, revision: ModeloRevision) -> None:
    """The ordered source tuple the four role reads index is permutation-stable."""
    baseline = _prorrata_source_casilla_ids(revision)
    for seed in _SEEDS:
        assert _prorrata_source_casilla_ids(_shuffled(revision, seed)) == baseline, (
            f"modelo {modelo_id}: permuting the binding fragments reordered the prorrata source casillas, "
            f"so the cuota/volumen/porcentaje roles read at positions 0-3 now name different casillas"
        )
    assert len(_prorrata_bindings(revision)) <= 1, (
        f"modelo {modelo_id}: more than one prorrata_regularizacion binding is declared, so the positional "
        f"role order comes from fragment merge order rather than from one reviewed declaration"
    )


@pytest.mark.parametrize(("modelo_id", "revision"), _revision_params())
def test_a_second_prorrata_binding_would_make_the_roles_order_dependent(
    modelo_id: str, revision: ModeloRevision
) -> None:
    """Anti-tautology: a duplicate prorrata declaration IS visible to the comparison above.

    The source roles concatenate across prorrata bindings, so a second binding
    contributing different casillas puts the role order at the mercy of merge
    order. Planting one must break the invariance the first test asserts;
    otherwise that test passes only because nothing it looks at can move.
    """
    declared = _prorrata_bindings(revision)
    if not declared:
        pytest.skip(f"modelo {modelo_id} declares no prorrata_regularizacion binding to duplicate")

    original = declared[0]
    provider = original.provider
    assert isinstance(provider, ProrrataRegularizacionProvider)
    planted = original.model_copy(
        update={
            "id": f"{original.id}-planted-duplicate",
            "provider": provider.model_copy(
                update={"source_casilla_ids": tuple(reversed(provider.source_casilla_ids))},
            ),
        },
    )
    defective = _with_bindings(revision, (*revision.bindings, planted))

    permuted = {_prorrata_source_casilla_ids(_shuffled(defective, seed)) for seed in _SEEDS}
    assert len(permuted) > 1, (
        f"modelo {modelo_id}: a second prorrata binding declaring a different source order left the derived "
        f"role tuple identical under every permutation, so the invariance gate cannot see a duplicate at all"
    )


# --------------------------------------------------------------------------
# Site 2: first-wins row_field dedup in export field derivation.
#
# On the present corpus every derived export field comes from a FIXED
# projection: no revision reaches the row_field dedup, because the records
# the row bindings name are either not claimed by an export layout (Modelo
# 720's "bien") or already hand-author the binding field (Modelo 193's
# "perceptor" and "gastos"). The dedup is therefore pinned through the
# declaration it keys on -- one claimant per (record, row_field) slot --
# rather than through a derived field it does not currently produce.
# --------------------------------------------------------------------------


def _export_signature(revision: ModeloRevision) -> frozenset[tuple[str, frozenset[tuple[object, ...]]]]:
    """Project derived export layouts into an order-free canonical comparison.

    Records are keyed by id and fields collected into a set, so only a genuine
    change of the derived coordinates -- which binding fills a slot, at what
    offset, width and type -- can make two signatures differ. The whole
    projection is hashable so that several permutations can be compared as a
    set rather than pairwise.
    """
    return frozenset(
        (
            f"{index}:{record.id}",
            frozenset(
                (field.id, str(field.kind), field.offset, field.length, field.binding, field.casilla_id)
                for field in record.fields
            ),
        )
        for index, layout in enumerate(derive_export_layouts_from_bindings(revision))
        for record in layout.records
    )


def _row_slot_claimants(revision: ModeloRevision) -> dict[tuple[str, str], tuple[str, ...]]:
    """Return the row bindings claiming each ``(record, row_field)`` slot.

    Read from the binding's own selector rather than from the export projection,
    because a record no export layout claims today is held to the same
    uniqueness as one that does: the slot is what the first-wins dedup keys on
    the moment a layout starts claiming it.
    """
    claimants: dict[tuple[str, str], list[str]] = {}
    for binding in revision.bindings:
        if binding_aggregation_op(binding) is not BindingAggregationOp.ROWS:
            continue
        selector = selector_as_dict(binding)
        record = selector.get("record")
        row_field = selector.get("row_field")
        if not isinstance(record, str) or not isinstance(row_field, str):
            continue
        claimants.setdefault((record, row_field), []).append(binding.id)
    return {slot: tuple(sorted(ids)) for slot, ids in claimants.items()}


def _binding_derived_export_fields(revision: ModeloRevision) -> frozenset[tuple[str, str]]:
    """Return the ``(record id, binding id)`` pairs derivation adds to the layouts."""
    authored = {
        (record.id, field.binding)
        for layout in revision.export_layouts
        for record in layout.records
        for field in record.fields
        if field.binding is not None
    }
    derived = {
        (record.id, field.binding)
        for layout in derive_export_layouts_from_bindings(revision)
        for record in layout.records
        for field in record.fields
        if field.binding is not None
    }
    return frozenset(derived - authored)


@pytest.mark.parametrize(("modelo_id", "revision"), _revision_params())
def test_derived_export_fields_do_not_move_with_binding_order(modelo_id: str, revision: ModeloRevision) -> None:
    """Permuting the bindings cannot change which binding fills an export slot."""
    baseline = _export_signature(revision)
    for seed in _SEEDS:
        assert _export_signature(_shuffled(revision, seed)) == baseline, (
            f"modelo {modelo_id}: permuting the binding fragments changed the derived export record fields, "
            f"so the emitted filing record depends on fragment filenames"
        )


@pytest.mark.parametrize(("modelo_id", "revision"), _revision_params())
def test_no_two_row_bindings_claim_one_row_field_of_one_record(modelo_id: str, revision: ModeloRevision) -> None:
    """The first-wins dedup is order-free because every row slot has one claimant.

    This is the structural reason the invariance above holds rather than a
    second observation of it: with one claimant per slot there is no "first" to
    choose. It is also refused at load, so a future revision cannot quietly
    reintroduce the ambiguity.
    """
    contested = {slot: ids for slot, ids in _row_slot_claimants(revision).items() if len(ids) > 1}
    assert not contested, (
        f"modelo {modelo_id}: these row slots are claimed by more than one binding, so which one reaches the "
        f"export record is decided by fragment merge order: {contested}"
    )


@pytest.mark.parametrize(("modelo_id", "revision"), _revision_params())
def test_a_duplicate_row_field_claimant_is_visible_to_the_slot_check(modelo_id: str, revision: ModeloRevision) -> None:
    """Anti-tautology: the slot check detects a planted second claimant.

    A clone of a live row binding under a new id must make the slot contested.
    Without this the assertion above would be satisfied by a projection that
    silently collapsed the two claimants, or found none at all.
    """
    claimants = _row_slot_claimants(revision)
    if not claimants:
        pytest.skip(f"modelo {modelo_id} declares no row binding claiming a record row field")

    slot, ids = sorted(claimants.items())[0]
    original = next(binding for binding in revision.bindings if binding.id == ids[0])
    planted = original.model_copy(update={"id": f"{original.id}-planted-duplicate"})
    defective = _with_bindings(revision, (*revision.bindings, planted))

    assert len(_row_slot_claimants(defective)[slot]) == 2, (
        f"modelo {modelo_id}: a cloned row binding did not show up as a second claimant of slot {slot}, "
        f"so the slot check cannot see a duplicate at all"
    )


@pytest.mark.parametrize(("modelo_id", "revision"), _revision_params())
def test_the_export_signature_can_see_a_binding_leave_a_record(modelo_id: str, revision: ModeloRevision) -> None:
    """Anti-tautology: the export signature has the resolution the invariance needs.

    A comparison too coarse to notice a binding losing its export field would
    hold under every permutation for the wrong reason. Removing one binding that
    derivation genuinely contributes must therefore change the signature.
    """
    contributed = _binding_derived_export_fields(revision)
    if not contributed:
        pytest.skip(f"modelo {modelo_id} derives no export field from a binding")

    _record_id, binding_id = sorted(contributed)[0]
    reduced = _with_bindings(revision, tuple(b for b in revision.bindings if b.id != binding_id))
    assert _export_signature(reduced) != _export_signature(revision), (
        f"modelo {modelo_id}: dropping binding {binding_id!r}, which derivation contributes an export field "
        f"for, left the export signature unchanged, so the invariance gate compares nothing"
    )


# --------------------------------------------------------------------------
# Site 3: the Modelo 390 annual-summary box assignment.
# --------------------------------------------------------------------------


def _annual_summary_fingerprint(revision: ModeloRevision) -> dict[str, Any]:
    """Project the annual-summary endpoint map and its validation verdict."""
    requirement = m303_regimen_simplificado_annual_summary_requirement(revision)
    numbers_by_casilla = {casilla.id: casilla.number for casilla in revision.casillas}
    endpoints = {} if requirement is None else dict(requirement.binding_ids_by_summary_casilla_id)
    return {
        "bindings_by_endpoint": endpoints,
        "official_number_by_endpoint": {casilla_id: numbers_by_casilla.get(casilla_id) for casilla_id in endpoints},
        "failures": frozenset(validate_m303_regimen_simplificado_annual_summary_revision(revision)),
    }


@pytest.mark.parametrize(("modelo_id", "revision"), _revision_params())
def test_annual_summary_box_numbers_do_not_move_with_binding_order(modelo_id: str, revision: ModeloRevision) -> None:
    """Each summary endpoint keeps its own official box number under permutation."""
    baseline = _annual_summary_fingerprint(revision)
    for seed in _SEEDS:
        assert _annual_summary_fingerprint(_shuffled(revision, seed)) == baseline, (
            f"modelo {modelo_id}: permuting the binding fragments reassigned the official Modelo 390 "
            f"annual-summary box numbers across endpoints"
        )


@pytest.mark.parametrize(("modelo_id", "revision"), _revision_params())
def test_an_endpoint_off_its_official_box_is_refused_regardless_of_order(
    modelo_id: str, revision: ModeloRevision
) -> None:
    """Anti-tautology: the summary check still has teeth after losing its positional read.

    Moving an endpoint casilla off its official box must be refused under every
    permutation. A check that only compared a permutation-stable map, without
    proving the map is still held to the official numbers, would be satisfied by
    a validator that checked nothing.
    """
    requirement = m303_regimen_simplificado_annual_summary_requirement(revision)
    if requirement is None:
        pytest.skip(f"modelo {modelo_id} declares no annual-summary bindings")

    endpoint_id = next(iter(requirement.binding_ids_by_summary_casilla_id))
    casillas = tuple(
        casilla.model_copy(update={"number": "9999"}) if casilla.id == endpoint_id else casilla
        for casilla in revision.casillas
    )
    defective = revision.model_copy(update={"casillas": casillas})

    assert not validate_m303_regimen_simplificado_annual_summary_revision(revision)
    for seed in _SEEDS:
        failures = validate_m303_regimen_simplificado_annual_summary_revision(_shuffled(defective, seed))
        assert [f for f in failures if endpoint_id in f and "9999" in f], (
            f"modelo {modelo_id}: moving endpoint {endpoint_id!r} off its official Modelo 390 box was not "
            f"refused under permutation seed {seed}"
        )


# --------------------------------------------------------------------------
# Site 4: first-match discovery of the foreign-asset valuation binding.
# --------------------------------------------------------------------------


def _foreign_asset_money_binding_ids(revision: ModeloRevision) -> frozenset[str]:
    return frozenset(
        binding.id
        for binding in revision.bindings
        if isinstance(binding.provider, ForeignAssetProvider) and binding.provider.data_type is CasillaDataType.MONEY
    )


@pytest.mark.parametrize(("modelo_id", "revision"), _revision_params())
def test_the_foreign_asset_valuation_first_match_has_no_choice_to_make(
    modelo_id: str, revision: ModeloRevision
) -> None:
    """The money-typed foreign-asset candidate set is singular and permutation-stable.

    The valuation binding is discovered by first match on the money data type.
    A first match is order-free exactly when at most one candidate exists, so
    the singularity is the load-bearing assertion and the permutation stability
    confirms nothing else selects the candidate.
    """
    baseline = _foreign_asset_money_binding_ids(revision)
    for seed in _SEEDS:
        assert _foreign_asset_money_binding_ids(_shuffled(revision, seed)) == baseline

    assert len(baseline) <= 1, (
        f"modelo {modelo_id}: {len(baseline)} money-typed foreign-asset bindings are declared "
        f"({sorted(baseline)}), so the valuation binding is whichever fragment merged first"
    )


@pytest.mark.parametrize(("modelo_id", "revision"), _revision_params())
def test_a_second_money_foreign_asset_binding_is_visible_to_the_singularity_check(
    modelo_id: str, revision: ModeloRevision
) -> None:
    """Anti-tautology: the singularity assertion detects a planted second candidate."""
    baseline = _foreign_asset_money_binding_ids(revision)
    if not baseline:
        pytest.skip(f"modelo {modelo_id} declares no money-typed foreign-asset binding")

    original = next(binding for binding in revision.bindings if binding.id in baseline)
    planted = original.model_copy(update={"id": f"{original.id}-planted-duplicate"})
    defective = _with_bindings(revision, (*revision.bindings, planted))

    assert len(_foreign_asset_money_binding_ids(defective)) > 1, (
        f"modelo {modelo_id}: a second money-typed foreign-asset binding did not enlarge the candidate set, "
        f"so the singularity assertion cannot see a duplicate at all"
    )
