"""Behaviour of the casilla lineage seeder's predicates, design oracle and writer.

Each refusal is shown against a control that passes, so a predicate that stopped
refusing would turn a test red rather than leave it vacuously green.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition
from dev.registry.compiler.authority import compiled_bundled_authority

from ..analysis.casilla_lineage_seed import (
    LineagePlan,
    admit_bare_chain,
    contradictions,
    gate_regressions,
    insert_lineage_keys,
    load_rulings,
    parse_design_inventory,
    residual_plan,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _casilla(**updates: object) -> CasillaDefinition:
    payload: dict[str, object] = {
        "id": "01",
        "number": "01",
        "localization_keys": ("modelo.schema.test.casilla.01.label",),
        "section": ("liquidacion",),
        "semantic_role": "base_imponible",
        "legal_refs": ("ley-35-2006:art-25",),
        "source_refs": ("aeat-dr-123-2024-v20",),
    }
    payload.update(updates)
    return CasillaDefinition.model_validate(payload)


# --------------------------------------------------------------------------- design oracle


@pytest.mark.parametrize(
    ("line", "box"),
    [
        ("33 | 882 | 17 | Num | Liquidación. Cuota íntegra ([13] x [15])  [16] | | 15 ent", 16),
        ("34 | 899 | 17 | Num | Cuota íntegra atribuible ([16] x [24] [17] | | 15 ent", 17),
        ("43 | 992 | 17 | N | Resultado de la liquidación ([17] + [19] - [25]) [26] |", 26),
        ("25 | 300 | 17 | Num | Cantidad a ingresar (mayor de claves [32] y [33] )  [34] |", 34),
        ("42 | 565 | 17 | N | Operaciones en régimen especial del recargo de equivalencia [102]. |", 102),
        ("45 | 496 | 17 | Num | B) Resultado previo (clave ([16] x [17]) + [47]-[40]) [18] |", 18),
    ],
)
def test_a_campo_prints_the_box_its_description_ends_with(line: str, box: int) -> None:
    inventory = parse_design_inventory(line, relative_path="design.md", sha256="0" * 64)
    assert inventory.boxes == {box}
    assert inventory.defining_line(box) == 1


@pytest.mark.parametrize(
    "line",
    [
        # A formula ending with an operand prints no box of its own.
        "17 | 192 | 17 | Num | Total liquidación. Suma de retenciones y regularización. [03] + [05] |",
        # A note enumerating boxes is about boxes, not a campo.
        "Nota 2: | | se cumplimentará en caso de no cumplimentar las casillas [20], [21], [22] y [23]",
        # Text after the bracket means the bracket is not the campo's box.
        "Ver la casilla [12] del modelo anterior para el importe",
    ],
)
def test_a_cell_that_prints_no_box_defines_none(line: str) -> None:
    assert parse_design_inventory(line, relative_path="design.md", sha256="0" * 64).boxes == frozenset()


def test_a_box_printed_on_two_lines_has_no_single_locus() -> None:
    text = "1 | Base imponible [07] |\n2 | Base imponible, página 2 [07] |"
    inventory = parse_design_inventory(text, relative_path="design.md", sha256="0" * 64)
    assert inventory.boxes == {7}
    assert inventory.defining_line(7) is None


# --------------------------------------------------------------------------- bare predicate


def test_agreeing_rows_are_admitted() -> None:
    category, _ = admit_bare_chain(_casilla(), _casilla())
    assert category is None


@pytest.mark.parametrize(
    ("previous", "successor", "category"),
    [
        ({"semantic_role": None}, {}, "role_absent"),
        ({}, {"semantic_role": None}, "role_absent"),
        ({}, {"semantic_role": "cuota_integra"}, "contradicted"),
        ({}, {"data_type": "text"}, "contradicted"),
        ({"form_number": "01"}, {"form_number": "07"}, "contradicted"),
    ],
)
def test_a_disagreeing_row_is_refused(previous: dict[str, object], successor: dict[str, object], category: str) -> None:
    refused, reason = admit_bare_chain(_casilla(**previous), _casilla(**successor))
    assert refused == category, reason


def test_the_general_number_field_is_never_read_for_identity() -> None:
    """A one-byte wire campo declares a plain integer in ``number``; it must not refuse a sound chain."""
    category, _ = admit_bare_chain(_casilla(number="977"), _casilla(number="1016"))
    assert category is None
    refused, _ = admit_bare_chain(_casilla(number="977", form_number="12"), _casilla(number="977", form_number="13"))
    assert refused == "contradicted"


# --------------------------------------------------------------------------- writer

_FILE = """\
[[revisions."2024".casillas]]
id = "01"
number = "01"

[[revisions."2024".casillas]]
id = "02"
continuidad_id = "base"
number = "02"

[[revisions."2025".casillas]]
id = "01"
number = "01"
"""


def test_keys_are_inserted_into_the_named_revision_table_only() -> None:
    text, done = insert_lineage_keys(
        _FILE, "2024", {"01": {"continuidad_origin": "new_on_form", "continuidad_evidence": "design.md:3 [01]"}}
    )
    assert done == {"01"}
    assert text.splitlines()[:5] == [
        '[[revisions."2024".casillas]]',
        'id = "01"',
        'continuidad_origin = "new_on_form"',
        'continuidad_evidence = "design.md:3 [01]"',
        'number = "01"',
    ]
    assert text.endswith('[[revisions."2025".casillas]]\nid = "01"\nnumber = "01"\n')


def test_keys_follow_an_existing_chain_and_an_identical_value_is_left_alone() -> None:
    text, done = insert_lineage_keys(_FILE, "2024", {"02": {"continuidad_id": "base", "continuidad_origin": "seeded"}})
    assert done == {"02"}
    assert 'continuidad_id = "base"\ncontinuidad_origin = "seeded"\nnumber = "02"' in text
    assert text.count('continuidad_id = "base"') == 1
    again, _ = insert_lineage_keys(text, "2024", {"02": {"continuidad_id": "base", "continuidad_origin": "seeded"}})
    assert again == text


def test_a_differing_value_already_present_is_never_overwritten() -> None:
    with pytest.raises(ValueError, match="already declares a different continuidad_id"):
        insert_lineage_keys(_FILE, "2024", {"02": {"continuidad_id": "other"}})


# --------------------------------------------------------------------------- self-check


@pytest.fixture(scope="module")
def authority() -> ValidatedRegistryAuthority:
    return compiled_bundled_authority()


def test_the_contradiction_check_catches_a_planted_absence_on_a_live_chain(
    authority: ValidatedRegistryAuthority,
) -> None:
    """An absence written onto a row whose chain the predecessor carries is a contradiction."""
    modelo = authority.modelo("390")
    predecessor, successor = modelo.revisions["2022"], modelo.revisions["2023"]
    prior = {casilla.continuidad_id for casilla in predecessor.casillas} - {None}
    target = next(casilla for casilla in successor.casillas if casilla.continuidad_id in prior)
    assert contradictions(modelo, LineagePlan("390")) == []
    planted = LineagePlan("390")
    planted.set_keys("2023", target.id, continuidad_origin="new_on_form", continuidad_evidence="design.md:1 [1]")
    assert contradictions(modelo, planted) == [
        f"2023/{target.id}: new_on_form but chain {target.continuidad_id!r} present in 2022"
    ]


def test_the_contradiction_check_catches_a_continuation_with_no_chain_behind_it(
    authority: ValidatedRegistryAuthority,
) -> None:
    modelo = authority.modelo("390")
    first, second = modelo.revisions["2021"], modelo.revisions["2022"]
    prior = {casilla.continuidad_id for casilla in first.casillas} - {None}
    target = next(
        casilla
        for casilla in second.casillas
        if casilla.continuidad_id is not None and casilla.continuidad_id not in prior
    )
    planted = LineagePlan("390")
    planted.set_keys("2022", target.id, continuidad_origin="seeded")
    assert contradictions(modelo, planted) == [
        f"2022/{target.id}: seeded but chain {target.continuidad_id!r} absent from 2021"
    ]


def test_the_registry_gate_refuses_a_roleless_chain_unless_every_link_is_grounded(
    authority: ValidatedRegistryAuthority,
) -> None:
    """A grounded link lifts the semantic_role requirement; the same link written as seeded does not."""
    modelo = authority.modelo("151")
    successor = next(
        casilla
        for casilla in modelo.revisions["2025-y-siguientes"].casillas
        if casilla.continuidad_origin is not None
        and casilla.continuidad_origin.value == "grounded"
        and casilla.semantic_role is None
    )
    assert gate_regressions(modelo, LineagePlan("151")) == []
    demoted = LineagePlan("151")
    demoted.set_keys("2025-y-siguientes", successor.id, continuidad_origin="seeded")
    regressions = gate_regressions(modelo, demoted)
    assert any(f"casilla {successor.id!r} has no semantic_role" in failure for failure in regressions), regressions


def test_an_excluded_modelo_is_refused_row_by_row_and_never_written(
    authority: ValidatedRegistryAuthority,
) -> None:
    """A ruled row keeps the ruling's category; every other residual row takes the exclusion's."""
    plan = residual_plan("309", authority.modelo("309"), load_rulings()["309"])
    categories = {(refusal.revision, refusal.casilla_id): refusal.category for refusal in plan.refusals}
    assert plan.edits == {}
    assert categories[("2016-2017", "decl.transmitente-apellidos")] == "withheld"
    assert categories[("2016-2017", "decl.transmitente-pais")] == "held"
    assert categories[("2018-2022", "decl.transmitente-pais")] == "absence_unclassified"
    unruled = residual_plan("309", authority.modelo("309"), ())
    assert {refusal.category for refusal in unruled.refusals} == {"absence_unclassified"}


def test_an_excluded_modelo_that_cannot_have_a_residual_row_refuses_to_record_one(
    authority: ValidatedRegistryAuthority,
) -> None:
    """Modelo 369's editions declare no predecessor; losing that declaration is an error, not a refusal."""
    modelo = authority.modelo("369")
    assert residual_plan("369", modelo, ()).refusals == []
    revision_id = max(modelo.revisions)
    stripped = modelo.model_copy(
        update={
            "revisions": {
                **modelo.revisions,
                revision_id: modelo.revisions[revision_id].model_copy(update={"predecessor": None}),
            }
        }
    )
    with pytest.raises(ValueError, match="cannot have one"):
        residual_plan("369", stripped, ())
