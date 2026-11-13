"""The leaves served for a descendant row cover every fact the row can store."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from ....core.flows import FlowWidgetKind
from ....core.i18n.render import tr
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.descendant_disability_catalogue import accepted_descendant_disability_grades
from ....domain.calculations.registry.descendant_relacion_catalogue import (
    descendant_relacion_adoption_token,
    descendant_relacion_entitling_tokens,
    descendant_relacion_tokens,
)
from ....domain.calculations.registry.tests.modelo_100_profile_binding_tables import FAMILY_ROW_BINDINGS
from ....domain.contribuyente.descendant import DescendantInfo
from ....domain.contribuyente.descendant_facts import descendant_facts_from_list
from ....domain.contribuyente.family_types import GuarderiaMonthSpend
from ....domain.user_profile.schema import ProfileFieldType
from ...flows.definition import FlowCondition, FlowPage, locale_copy_ref
from ..family_rows import (
    ProfileFamilyGroupState,
    ProfileFamilyLeaf,
    ProfileFamilyLeafAsk,
    ProfileViewFamilyGroupItem,
    ProfileViewFamilyRowItem,
    family_row_items,
    resolve_leaf_asks,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# Stored by the descendant record but asked by no wizard page, so no wording exists for it.
_STORED_WITHOUT_WORDING = frozenset({"segundo_ciclo_infantil_inicio_mes"})


def test_every_stored_descendant_leaf_but_one_has_served_wording() -> None:
    with bundled_indexed_authority().operation() as authority:
        full = DescendantInfo(
            birth_date=date(2021, 5, 17),
            relacion=descendant_relacion_adoption_token(authority=authority),
            inscripcion_registro_civil_date=date(2021, 9, 1),
            death_date=date(2025, 2, 3),
            discapacidad_grado=65,
            convive_con_contribuyente=False,
            dependencia_economica=True,
            custodia_compartida=True,
            rentas_anuales_euros=Decimal("10.25"),
            presenta_declaracion_propia=True,
            prorrata_minimo=False,
            meses_madre_trabajo=(3, 4),
            alta_posterior_nacimiento_mes=3,
            segundo_ciclo_infantil_inicio_mes=9,
            gastos_guarderia_mensuales=(GuarderiaMonthSpend(month=1, amount_euros=50),),
            cotizaciones_ss_madre_euros=Decimal("2332.80"),
            nif="12345678Z",
            apellidos_nombre="Ortega Navarro Pablo",
        )
        stored = {
            path.removeprefix("renta_family.descendiente.0."): value
            for path, value in descendant_facts_from_list((full,), authority=authority)
            if path.startswith("renta_family.descendiente.0.")
        }
        values = {f"renta_family.descendiente.0.{leaf}": value for leaf, value in stored.items()}
        items = family_row_items(values, schema=authority.profile_schema(), operation=authority)
    group, row = items[0], items[1]
    assert isinstance(group, ProfileViewFamilyGroupItem) and isinstance(row, ProfileViewFamilyRowItem)
    served = {leaf.leaf for leaf in group.leaves}
    assert "cotizaciones_ss_madre" in stored
    assert set(stored) - served == _STORED_WITHOUT_WORDING
    assert {fact.leaf for fact in row.facts} == set(stored) - _STORED_WITHOUT_WORDING


_ASCENDANT_OBJECT = "renta_family.ascendiente"
_ASCENDANT_COUNT = "renta_family.ascendientes_count"
# Read by the mínimo por ascendientes aggregate and the derived disability key rather than by a form binding.
_MINIMO_ASCENDIENTES_LEAVES = frozenset(
    {
        "rentas_anuales",
        "declaracion_propia",
        "discapacidad",
        "convivencia_mitad_periodo",
        "discapacidad_asistencia",
        "incapacidad_judicial",
    }
)
# The Modelo 100 bindings read this leaf from the object; the calculation derives it and nothing stores it.
_BOUND_WITHOUT_STORED_LEAF = frozenset({"minimo_discapacidad_clave"})


def _ascendant_group(
    values: dict[str, str],
) -> tuple[ProfileViewFamilyGroupItem, tuple[ProfileViewFamilyRowItem, ...]]:
    with bundled_indexed_authority().operation() as authority:
        items = family_row_items(values, schema=authority.profile_schema(), operation=authority)
    group = next(
        item for item in items if isinstance(item, ProfileViewFamilyGroupItem) and item.group_key == _ASCENDANT_OBJECT
    )
    rows = tuple(
        item for item in items if isinstance(item, ProfileViewFamilyRowItem) and item.group_key == _ASCENDANT_OBJECT
    )
    return group, rows


_ASCENDANT_YES_NO_LEAVES = (
    "declaracion_propia",
    "convivencia_mitad_periodo",
    "discapacidad_asistencia",
    "incapacidad_judicial",
)


def _assert_yes_no_leaf(leaf: ProfileFamilyLeaf) -> None:
    assert leaf.field_type is ProfileFieldType.BOOLEAN
    assert [choice.value for choice in leaf.choices] == ["true", "false"]
    assert leaf.help is not None and leaf.help != ""


def test_ascendant_leaves_are_those_the_form_reads_from_the_object_that_a_row_can_store() -> None:
    group, _ = _ascendant_group({})
    bound = {leaf for obj, leaf, _count in FAMILY_ROW_BINDINGS.values() if obj == _ASCENDANT_OBJECT}
    counts = {count for obj, _leaf, count in FAMILY_ROW_BINDINGS.values() if obj == _ASCENDANT_OBJECT}
    served = {leaf.leaf for leaf in group.leaves}
    assert bound - served == _BOUND_WITHOUT_STORED_LEAF
    assert served - bound == _MINIMO_ASCENDIENTES_LEAVES
    assert counts == {_ASCENDANT_COUNT}
    by_leaf = {leaf.leaf: leaf for leaf in group.leaves}
    assert by_leaf["birth_date"].field_type is ProfileFieldType.DATE and by_leaf["birth_date"].required
    assert by_leaf["fallecimiento"].field_type is ProfileFieldType.DATE and not by_leaf["fallecimiento"].required
    assert by_leaf["convivientes"].field_type is ProfileFieldType.INTEGER
    assert by_leaf["nif"].field_type is ProfileFieldType.STRING
    assert by_leaf["apellidos_nombre"].field_type is ProfileFieldType.STRING
    assert not by_leaf["apellidos_nombre"].required
    assert by_leaf["rentas_anuales"].field_type is ProfileFieldType.DECIMAL
    for answer in _ASCENDANT_YES_NO_LEAVES:
        _assert_yes_no_leaf(by_leaf[answer])
    with bundled_indexed_authority().operation() as authority:
        grades = sorted(accepted_descendant_disability_grades(authority=authority))
    assert [choice.value for choice in by_leaf["discapacidad"].choices] == [str(grade) for grade in grades]
    assert all(leaf.label for leaf in group.leaves)
    assert not [leaf.leaf for leaf in group.leaves if leaf.choices and leaf.leaf not in _MINIMO_ASCENDIENTES_LEAVES]


def test_an_unstated_ascendant_household_is_unknown_and_a_stated_zero_is_declared_none() -> None:
    unknown, no_rows = _ascendant_group({})
    assert unknown.state is ProfileFamilyGroupState.UNKNOWN
    assert unknown.stated_count is None and unknown.row_count == 0 and not no_rows
    # A descendant count says nothing about ascendants.
    other, _ = _ascendant_group({"renta_family.descendientes_count": "0"})
    assert other.state is ProfileFamilyGroupState.UNKNOWN
    none_declared, rows = _ascendant_group({_ASCENDANT_COUNT: "0"})
    assert none_declared.state is ProfileFamilyGroupState.NONE_DECLARED
    assert none_declared.stated_count == "0" and not rows


def test_stored_ascendants_are_rows_holding_only_the_leaves_they_state() -> None:
    group, rows = _ascendant_group(
        {
            _ASCENDANT_COUNT: "2",
            f"{_ASCENDANT_OBJECT}.0.nif": "12345678Z",
            f"{_ASCENDANT_OBJECT}.0.apellidos_nombre": "Ibáñez Roca Carmen",
            f"{_ASCENDANT_OBJECT}.0.birth_date": "1950-02-03",
            f"{_ASCENDANT_OBJECT}.0.convivientes": "2",
            f"{_ASCENDANT_OBJECT}.0.rentas_anuales": "7200.00",
            f"{_ASCENDANT_OBJECT}.0.declaracion_propia": "false",
            f"{_ASCENDANT_OBJECT}.0.discapacidad": "33",
            f"{_ASCENDANT_OBJECT}.1.birth_date": "1948-07-09",
            f"{_ASCENDANT_OBJECT}.1.fallecimiento": "  ",
            # A leaf nothing stores, and a descendant row, are not ascendant facts.
            f"{_ASCENDANT_OBJECT}.1.discapacidad_clave": "1",
            "renta_family.descendiente.0.birth_date": "2020-01-01",
        }
    )
    assert group.state is ProfileFamilyGroupState.ROWS
    assert group.row_count == 2 and group.stated_count == "2"
    first, second = rows
    assert (first.row_index, second.row_index) == ("0", "1")
    assert [(fact.leaf, fact.value) for fact in first.facts] == [
        ("nif", "12345678Z"),
        ("apellidos_nombre", "Ibáñez Roca Carmen"),
        ("birth_date", "1950-02-03"),
        ("convivientes", "2"),
        ("rentas_anuales", "7200.00"),
        ("declaracion_propia", "false"),
        ("discapacidad", "33"),
    ]
    assert all(fact.path == f"{_ASCENDANT_OBJECT}.0.{fact.leaf}" and not fact.masked for fact in first.facts)
    assert [(fact.leaf, fact.value) for fact in second.facts] == [("birth_date", "1948-07-09")]


def test_stored_ascendants_beat_a_stated_zero_count() -> None:
    group, rows = _ascendant_group({_ASCENDANT_COUNT: "0", f"{_ASCENDANT_OBJECT}.0.birth_date": "1950-02-03"})
    assert group.state is ProfileFamilyGroupState.ROWS and len(rows) == 1


_DESCENDANT_OBJECT = "renta_family.descendiente"
_DESCENDANT_COUNT = "renta_family.descendientes_count"


def _incomplete_words(*, stated: str, recorded: int) -> str:
    words = tr("application.user_profile.family_rows.incomplete", stated=stated, recorded=recorded)
    assert stated in words and str(recorded) in words
    return words


def _descendant_group(
    values: dict[str, str],
) -> tuple[ProfileViewFamilyGroupItem, tuple[ProfileViewFamilyRowItem, ...]]:
    with bundled_indexed_authority().operation() as authority:
        items = family_row_items(values, schema=authority.profile_schema(), operation=authority)
    group = next(
        item for item in items if isinstance(item, ProfileViewFamilyGroupItem) and item.group_key == _DESCENDANT_OBJECT
    )
    rows = tuple(
        item for item in items if isinstance(item, ProfileViewFamilyRowItem) and item.group_key == _DESCENDANT_OBJECT
    )
    return group, rows


def test_a_stated_count_larger_than_the_stored_rows_is_incomplete_and_still_serves_the_rows() -> None:
    group, rows = _descendant_group({_DESCENDANT_COUNT: "3", f"{_DESCENDANT_OBJECT}.0.birth_date": "2019-03-14"})

    assert group.state is ProfileFamilyGroupState.INCOMPLETE
    assert (group.stated_count, group.row_count) == ("3", 1)
    assert group.incomplete_words == _incomplete_words(stated="3", recorded=1)
    assert [row.row_index for row in rows] == ["0"]


def test_a_stated_count_with_no_stored_row_is_incomplete_not_unknown() -> None:
    group, rows = _descendant_group({_DESCENDANT_COUNT: "2"})

    assert group.state is ProfileFamilyGroupState.INCOMPLETE
    assert (group.stated_count, group.row_count, group.incomplete_words) == (
        "2",
        0,
        _incomplete_words(stated="2", recorded=0),
    )
    assert not rows


def test_a_count_equal_to_the_stored_rows_is_rows_and_says_nothing_more() -> None:
    group, rows = _descendant_group({_DESCENDANT_COUNT: "1", f"{_DESCENDANT_OBJECT}.0.birth_date": "2019-03-14"})

    assert group.state is ProfileFamilyGroupState.ROWS
    assert (group.stated_count, group.row_count, group.incomplete_words) == ("1", 1, None)
    assert len(rows) == 1


def test_stored_rows_with_no_stated_count_are_rows_and_not_incomplete() -> None:
    group, rows = _descendant_group({f"{_DESCENDANT_OBJECT}.0.birth_date": "2019-03-14"})

    assert group.state is ProfileFamilyGroupState.ROWS
    assert (group.stated_count, group.row_count, group.incomplete_words) == (None, 1, None)
    assert len(rows) == 1


def test_a_count_below_the_stored_rows_or_not_a_number_is_not_incomplete() -> None:
    below, _ = _descendant_group(
        {
            _DESCENDANT_COUNT: "1",
            f"{_DESCENDANT_OBJECT}.0.birth_date": "2019-03-14",
            f"{_DESCENDANT_OBJECT}.1.birth_date": "2021-05-17",
        }
    )
    garbled, _ = _descendant_group({_DESCENDANT_COUNT: "several", f"{_DESCENDANT_OBJECT}.0.birth_date": "2019-03-14"})

    assert below.state is ProfileFamilyGroupState.ROWS
    assert garbled.state is ProfileFamilyGroupState.ROWS
    assert below.incomplete_words is None and garbled.incomplete_words is None


def test_a_stated_ascendant_count_larger_than_its_rows_is_incomplete_like_descendants() -> None:
    group, rows = _ascendant_group({_ASCENDANT_COUNT: "3", f"{_ASCENDANT_OBJECT}.0.birth_date": "1950-02-03"})

    assert group.state is ProfileFamilyGroupState.INCOMPLETE
    assert (group.stated_count, group.row_count, group.incomplete_words) == (
        "3",
        1,
        _incomplete_words(stated="3", recorded=1),
    )
    assert len(rows) == 1


def test_each_group_serves_the_most_rows_the_design_holds() -> None:
    # The 2025 Modelo 100 design repeats Hijo 15 times and Ascendiente 4 times, whatever the household holds.
    for values in ({}, {_ASCENDANT_COUNT: "0", _DESCENDANT_COUNT: "0"}):
        descendants, _ = _descendant_group(values)
        ascendants, _ = _ascendant_group(values)
        assert (descendants.max_rows, ascendants.max_rows) == (15, 4)


_BORN = (date.today() - timedelta(days=1500)).isoformat()
_DESCENDANT_PREFIX = "renta_family.descendiente.0."


def _descendant_row_asks(stated: dict[str, str]) -> dict[str, ProfileFamilyLeafAsk]:
    values = {f"{_DESCENDANT_PREFIX}{leaf}": value for leaf, value in stated.items()}
    with bundled_indexed_authority().operation() as authority:
        items = family_row_items(values, schema=authority.profile_schema(), operation=authority)
    row = next(item for item in items if isinstance(item, ProfileViewFamilyRowItem))
    return {entry.leaf: entry.ask for entry in row.leaf_asks}


def _relacion_tokens() -> tuple[str, frozenset[str], str]:
    """The adoption token, the entitling tokens and one token that entitles to nothing."""
    with bundled_indexed_authority().operation() as authority:
        adoption = descendant_relacion_adoption_token(authority=authority).value
        entitling = frozenset(token.value for token in descendant_relacion_entitling_tokens(authority=authority))
        plain = next(
            token.value for token in descendant_relacion_tokens(authority=authority) if token.value not in entitling
        )
    return adoption, entitling, plain


def test_an_adoption_asks_for_its_registry_date_and_every_entitling_relation_for_its_resolution() -> None:
    adoption, entitling, _plain = _relacion_tokens()
    asks = _descendant_row_asks({"birth_date": _BORN, "relacion": adoption})
    assert asks["inscripcion_registro_civil"] is ProfileFamilyLeafAsk.ASKED
    assert adoption in entitling and asks["acogimiento_resolucion"] is ProfileFamilyLeafAsk.ASKED
    assert asks["birth_date"] is ProfileFamilyLeafAsk.ASKED and asks["relacion"] is ProfileFamilyLeafAsk.ASKED


def test_an_answered_relation_that_is_not_adoption_does_not_ask_for_the_registry_date() -> None:
    adoption, entitling, plain = _relacion_tokens()
    assert plain != adoption
    asks = _descendant_row_asks({"birth_date": _BORN, "relacion": plain})
    assert asks["inscripcion_registro_civil"] is ProfileFamilyLeafAsk.NOT_ASKED
    assert asks["acogimiento_resolucion"] is ProfileFamilyLeafAsk.NOT_ASKED
    assert plain not in entitling


def test_a_row_with_no_relation_waits_for_it_before_asking_what_depends_on_it() -> None:
    asks = _descendant_row_asks({"birth_date": _BORN})
    assert asks["inscripcion_registro_civil"] is ProfileFamilyLeafAsk.AWAITS_ANSWER
    assert asks["acogimiento_resolucion"] is ProfileFamilyLeafAsk.AWAITS_ANSWER
    assert asks["relacion"] is ProfileFamilyLeafAsk.ASKED


def test_economic_dependence_is_asked_only_of_a_descendant_who_does_not_live_with_the_taxpayer() -> None:
    base = {"birth_date": _BORN}
    assert _descendant_row_asks(base)["dependencia_economica"] is ProfileFamilyLeafAsk.AWAITS_ANSWER
    away = _descendant_row_asks({**base, "convivencia": "false"})
    assert away["dependencia_economica"] is ProfileFamilyLeafAsk.ASKED
    home = _descendant_row_asks({**base, "convivencia": "true"})
    assert home["dependencia_economica"] is ProfileFamilyLeafAsk.NOT_ASKED


def test_a_fact_stored_on_a_leaf_that_is_not_asked_stays_in_the_served_row() -> None:
    values = {
        f"{_DESCENDANT_PREFIX}birth_date": _BORN,
        f"{_DESCENDANT_PREFIX}convivencia": "true",
        f"{_DESCENDANT_PREFIX}dependencia_economica": "true",
    }
    with bundled_indexed_authority().operation() as authority:
        items = family_row_items(values, schema=authority.profile_schema(), operation=authority)
    row = next(item for item in items if isinstance(item, ProfileViewFamilyRowItem))
    assert {entry.leaf: entry.ask for entry in row.leaf_asks}["dependencia_economica"] is ProfileFamilyLeafAsk.NOT_ASKED
    assert {fact.leaf: fact.value for fact in row.facts}["dependencia_economica"] == "true"


def test_a_blank_new_row_asks_what_is_unconditional_and_waits_on_what_is_gated() -> None:
    with bundled_indexed_authority().operation() as authority:
        items = family_row_items({}, schema=authority.profile_schema(), operation=authority)
    descendants, ascendants = (item for item in items if isinstance(item, ProfileViewFamilyGroupItem))
    assert [entry.leaf for entry in descendants.new_row_leaves] == [leaf.leaf for leaf in descendants.leaves]
    asks = {entry.leaf: entry.ask for entry in descendants.new_row_leaves}
    gated = {leaf.leaf for leaf in descendants.leaves if leaf.shown_when}
    assert gated == {"inscripcion_registro_civil", "acogimiento_resolucion", "dependencia_economica"}
    assert {leaf for leaf, ask in asks.items() if ask is ProfileFamilyLeafAsk.AWAITS_ANSWER} == gated
    assert all(ask is ProfileFamilyLeafAsk.ASKED for leaf, ask in asks.items() if leaf not in gated)
    assert all(entry.ask is ProfileFamilyLeafAsk.ASKED for entry in ascendants.new_row_leaves)


def _gated_page(page_id: str, gate: FlowCondition | None = None) -> FlowPage:
    return FlowPage(
        id=page_id,
        widget=FlowWidgetKind.TEXT,
        prompt=locale_copy_ref("wizard.setup.title"),
        visible_when=gate,
        required=False,
        answer_type=str,
    )


def test_a_leaf_gated_on_a_leaf_that_is_not_asked_is_not_asked_whatever_is_stored() -> None:
    pages = (
        _gated_page("first"),
        _gated_page("second", FlowCondition(page_id="first", equals="x")),
        _gated_page("third", FlowCondition(page_id="second", equals="y")),
    )
    keys = ("first", "second", "third", "free")

    def asks(row: dict[str, str]) -> dict[str, ProfileFamilyLeafAsk]:
        return {entry.leaf: entry.ask for entry in resolve_leaf_asks(pages, keys, row)}

    hidden_parent = asks({"first": "z", "second": "y", "third": "w"})
    assert hidden_parent["second"] is ProfileFamilyLeafAsk.NOT_ASKED
    assert hidden_parent["third"] is ProfileFamilyLeafAsk.NOT_ASKED
    assert hidden_parent["free"] is ProfileFamilyLeafAsk.ASKED
    assert asks({"first": "x"})["third"] is ProfileFamilyLeafAsk.AWAITS_ANSWER
    assert asks({"first": "x", "second": "y"})["third"] is ProfileFamilyLeafAsk.ASKED
    assert asks({"first": "x", "second": "n"})["third"] is ProfileFamilyLeafAsk.NOT_ASKED
    assert asks({})["second"] is ProfileFamilyLeafAsk.AWAITS_ANSWER
    assert asks({"first": "  "})["second"] is ProfileFamilyLeafAsk.AWAITS_ANSWER


def test_a_gate_on_a_page_the_group_does_not_ask_can_never_be_met() -> None:
    orphan = _gated_page("orphan", FlowCondition(page_id="elsewhere", equals="x"))
    (entry,) = resolve_leaf_asks((orphan,), ("orphan",), {"orphan": "kept", "elsewhere": "x"})
    assert entry.ask is ProfileFamilyLeafAsk.NOT_ASKED
