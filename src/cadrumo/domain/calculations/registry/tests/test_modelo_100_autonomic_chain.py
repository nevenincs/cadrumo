"""Structural / graph-wiring tests for the Modelo 100 autonomic chain.

Walks every (CCAA x año) combination across the committed Modelo 100
revisions (2020-2025 x 15 ordinary common-regime CCAA = 90 cells) and
asserts the autonomic-scale dispatch chain's structural invariants
hold for each one:

1. The 0529 (cuota escala autonómica sobre base liquidable general)
   and 0531 (cuota escala autonómica sobre mínimo personal y familiar)
   formulas exist in the revision.
2. Each formula's expression has ``op == "lookup_bracket_by_ccaa"``.
3. Each formula's dispatch_table contains all 15 CCAA keys.
4. Each dispatch_table value resolves to a declared bracket_table
   parameter on the revision.
5. The matching parameter's id follows the
   ``renta-{año}-escala-autonomica-{ccaa}-base-general`` naming pattern.
6. The construct's ``formulas`` member tuple includes both formula ids.

All assertions are structural — they exercise operand refs, formula
targets, relation ids, revision id, casilla counts, and binding
presence. The calculation-arithmetic surface is verified by AEAT-
published oracle data via the replay-parity layer, not by hand-
computed Decimal literals.
"""

from __future__ import annotations

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from ..schema import ModeloDefinition
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_AUTONOMIC_FORMULA_TARGETS: tuple[CasillaId, ...] = (
    validated_casilla_id("0529", surface="test_modelo_100_autonomic_chain.autonomic_formula_target.0529"),
    validated_casilla_id("0531", surface="test_modelo_100_autonomic_chain.autonomic_formula_target.0531"),
)
_EXPECTED_CCAA_KEYS: frozenset[str] = frozenset(
    {
        "andalucia",
        "aragon",
        "asturias",
        "baleares",
        "canarias",
        "cantabria",
        "castilla_la_mancha",
        "castilla_y_leon",
        "cataluna",
        "comunidad_valenciana",
        "extremadura",
        "galicia",
        "la_rioja",
        "madrid",
        "murcia",
    },
)
_SUPPORTED_EJERCICIOS: tuple[str, ...] = ("2020", "2021", "2022", "2023", "2024", "2025")


def _lookup_bracket_by_ccaa_nodes(expression: object) -> list[object]:
    """Collect every ``lookup_bracket_by_ccaa`` node in an expression tree.

    From the 2024/2025 revisions the autonomic escala formulas (0529/0531) wrap
    their ``lookup_bracket_by_ccaa`` operators inside the LIRPF art. 64/75
    anualidades separate-escala ``if_then_else`` régimen predicate, so the
    dispatch table is no longer at the top level. The pre-régimen (flat) years
    yield exactly one node; the modelled years yield several (each escala term of
    the conditional). Every node must satisfy the CCAA-dispatch invariants.
    """
    nodes: list[object] = []
    op = getattr(expression, "op", None)
    if op == "lookup_bracket_by_ccaa":
        nodes.append(expression)
    for arg in getattr(expression, "args", ()) or ():
        nodes.extend(_lookup_bracket_by_ccaa_nodes(arg))
    return nodes


def _dispatch_leaves(expression: object) -> list[object]:
    """Return the dispatch_table leaf (args[2]) of every lookup_bracket_by_ccaa node."""
    leaves: list[object] = []
    for node in _lookup_bracket_by_ccaa_nodes(expression):
        args = getattr(node, "args", None)
        if args is not None and len(args) > 2:
            leaves.append(args[2])
    return leaves


def _get_dispatch_table(dispatch_leaf: object) -> dict[str, str] | None:
    """Safely extract dispatch_table from a dispatch leaf node."""
    raw_table = getattr(dispatch_leaf, "dispatch_table", None)
    if not isinstance(raw_table, dict):
        return None
    table: dict[str, str] = {}
    for key, value in raw_table.items():
        if not isinstance(key, str) or not isinstance(value, str):
            return None
        table[key] = value
    return table


def _committed_modelo_100() -> ModeloDefinition:
    modelo, _catalogues = _committed_modelo("100")
    return modelo


@pytest.fixture(scope="module")
def modelo_100() -> ModeloDefinition:
    return _committed_modelo_100()


def test_autonomic_formula_exists_for_every_ejercicio(modelo_100: ModeloDefinition) -> None:
    """Every supported ejercicio carries both 0529 and 0531 formulas."""
    for ejercicio in _SUPPORTED_EJERCICIOS:
        revision = modelo_100.revisions[ejercicio]

        for target_casilla_id in _AUTONOMIC_FORMULA_TARGETS:
            matching = [formula for formula in revision.formulas if formula.target_casilla_id == target_casilla_id]

            assert len(matching) == 1, (
                f"ejercicio {ejercicio}: expected exactly one formula targeting {target_casilla_id}, "
                f"found {len(matching)}"
            )


def test_autonomic_formula_uses_lookup_bracket_by_ccaa_op(modelo_100: ModeloDefinition) -> None:
    """The autonomic-scale formula must use the ``lookup_bracket_by_ccaa``
    op. A regression to ``lookup_bracket`` (state-scale) or any other op
    would silently revert the CCAA-dispatch behaviour."""
    for ejercicio in _SUPPORTED_EJERCICIOS:
        revision = modelo_100.revisions[ejercicio]

        for target_casilla_id in _AUTONOMIC_FORMULA_TARGETS:
            formula = next(item for item in revision.formulas if item.target_casilla_id == target_casilla_id)

            nodes = _lookup_bracket_by_ccaa_nodes(formula.expression)
            assert nodes, (
                f"ejercicio {ejercicio} casilla {target_casilla_id}: no 'lookup_bracket_by_ccaa' node found "
                f"(top-level op is {formula.expression.op!r}). A regression to 'lookup_bracket' (state-scale) "
                f"or any other op would silently revert the CCAA-dispatch behaviour."
            )


def test_autonomic_formula_dispatch_table_covers_every_ccaa(modelo_100: ModeloDefinition) -> None:
    """Every formula's dispatch_table covers all 15 ordinary common-
    regime CCAA. A regression dropping a CCAA from the dispatch_table
    would surface as a runtime error at evaluation time, but only for
    profiles whose tax-residence happens to be that CCAA — pinning
    every key here surfaces the gap at registry-load time."""
    for ejercicio in _SUPPORTED_EJERCICIOS:
        revision = modelo_100.revisions[ejercicio]

        for target_casilla_id in _AUTONOMIC_FORMULA_TARGETS:
            formula = next(item for item in revision.formulas if item.target_casilla_id == target_casilla_id)

            dispatch_leaves = _dispatch_leaves(formula.expression)
            assert dispatch_leaves, f"ejercicio {ejercicio} casilla {target_casilla_id}: no dispatch_table leaf found"
            for dispatch_leaf in dispatch_leaves:
                dispatch_table = _get_dispatch_table(dispatch_leaf)
                assert dispatch_table is not None, (
                    f"ejercicio {ejercicio} casilla {target_casilla_id}: args[2] is not a dispatch_table leaf"
                )
                observed_keys = frozenset(dispatch_table)
                missing = _EXPECTED_CCAA_KEYS - observed_keys
                extra = observed_keys - _EXPECTED_CCAA_KEYS
                assert not missing, (
                    f"ejercicio {ejercicio} casilla {target_casilla_id}: "
                    f"dispatch_table missing CCAA keys {sorted(missing)}"
                )
                assert not extra, (
                    f"ejercicio {ejercicio} casilla {target_casilla_id}: "
                    f"dispatch_table has unexpected keys {sorted(extra)}"
                )


def test_autonomic_formula_dispatch_values_resolve_to_declared_parameters(modelo_100: ModeloDefinition) -> None:
    """Every dispatch_table value resolves to a declared parameter on
    the revision (a bracket_table parameter — the runtime requires
    this data_type for the lookup_bracket_by_ccaa op)."""
    for ejercicio in _SUPPORTED_EJERCICIOS:
        revision = modelo_100.revisions[ejercicio]
        parameters_by_id = {parameter.id: parameter for parameter in revision.parameters}

        for target_casilla_id in _AUTONOMIC_FORMULA_TARGETS:
            formula = next(item for item in revision.formulas if item.target_casilla_id == target_casilla_id)
            dispatch_leaves = _dispatch_leaves(formula.expression)
            assert dispatch_leaves, f"ejercicio {ejercicio} casilla {target_casilla_id}: no dispatch_table leaf found"

            for dispatch_leaf in dispatch_leaves:
                dispatch_table = _get_dispatch_table(dispatch_leaf)
                assert dispatch_table is not None
                for ccaa, parameter_id in dispatch_table.items():
                    assert parameter_id in parameters_by_id, (
                        f"ejercicio {ejercicio} casilla {target_casilla_id} ccaa {ccaa}: "
                        "dispatch_table references unknown parameter "
                        f"{parameter_id!r}"
                    )
                    parameter = parameters_by_id[parameter_id]
                    assert parameter.data_type == "bracket_table", (
                        f"ejercicio {ejercicio} casilla {target_casilla_id} ccaa {ccaa}: "
                        f"parameter {parameter_id!r} has data_type "
                        f"{parameter.data_type!r}, expected 'bracket_table'"
                    )


def test_autonomic_dispatch_parameters_follow_canonical_naming_pattern(modelo_100: ModeloDefinition) -> None:
    """Every dispatched parameter id follows the canonical
    ``renta-{año}-escala-autonomica-{ccaa}-base-general`` pattern.
    A regression that names a parameter differently would still
    resolve at the registry-validator level but break operator-
    facing introspection and audit reports that key off the
    canonical id shape."""
    for ejercicio in _SUPPORTED_EJERCICIOS:
        revision = modelo_100.revisions[ejercicio]

        for target_casilla_id in _AUTONOMIC_FORMULA_TARGETS:
            formula = next(item for item in revision.formulas if item.target_casilla_id == target_casilla_id)
            dispatch_leaves = _dispatch_leaves(formula.expression)
            assert dispatch_leaves, f"ejercicio {ejercicio} casilla {target_casilla_id}: no dispatch_table leaf found"

            for dispatch_leaf in dispatch_leaves:
                dispatch_table = _get_dispatch_table(dispatch_leaf)
                assert dispatch_table is not None
                for ccaa, parameter_id in dispatch_table.items():
                    ccaa_slug = ccaa.replace("_", "-")
                    expected_id = f"renta-{ejercicio}-escala-autonomica-{ccaa_slug}-base-general"
                    assert parameter_id == expected_id, (
                        f"ejercicio {ejercicio} casilla {target_casilla_id} ccaa {ccaa}: "
                        f"parameter id is {parameter_id!r}, "
                        f"expected {expected_id!r}"
                    )


def test_autonomic_construct_lists_both_autonomic_formulas(modelo_100: ModeloDefinition) -> None:
    """The construct that owns the autonomic-scale formulas must
    declare both 0529 and 0531 ids in its formulas tuple — owners-
    of-record for the formula provenance trail."""
    for ejercicio in _SUPPORTED_EJERCICIOS:
        revision = modelo_100.revisions[ejercicio]
        formula_id_by_target = {formula.target_casilla_id: formula.id for formula in revision.formulas}
        expected_formula_ids = {formula_id_by_target[target] for target in _AUTONOMIC_FORMULA_TARGETS}

        declared_ids: set[str] = set()
        for construct in revision.constructs:
            declared_ids.update(construct.formulas)

        missing = expected_formula_ids - declared_ids
        assert not missing, (
            f"ejercicio {ejercicio}: autonomic-scale formulas not declared by any construct: {sorted(missing)}"
        )
