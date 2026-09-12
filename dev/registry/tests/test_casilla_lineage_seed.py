"""Behaviour of the casilla lineage seeder's predicates, design oracle and writer.

Each refusal is shown against a control that passes, so a predicate that stopped
refusing would turn a test red rather than leave it vacuously green.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.casilla_lineage_totality import (
    lineage_totality,
    unresolved_successor_rows,
)
from cadrumo.domain.calculations.registry.revision_order import ordered_revisions
from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from ..analysis.casilla_lineage_ledger import load_ledger_refusals
from ..analysis.casilla_lineage_seed import (
    CarriedRefusal,
    DesignOracle,
    LineagePlan,
    LineageRefusalCategory,
    ModeloLoadFailure,
    PartialStamping,
    PartialStampingError,
    admit_bare_chain,
    carried_refusals,
    contradictions,
    gate_regressions,
    insert_lineage_keys,
    load_corpus,
    load_previous_ledger,
    load_rulings,
    parse_design_inventory,
    plan_corpus,
    plan_modelo,
    render_ledger,
    residual_plan,
    run_identifier,
)
from ..compiler.loader import load_modelo_directory, load_shared_catalogues
from ..compiler.loader_cache import ModeloSource, discover_modelo_sources

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
def modelos() -> Mapping[str, ModeloDefinition]:
    """One real modelo each, compiled per directory as the seeder compiles them.

    These checks need a real modelo to plant a defect in, not a validated corpus:
    none of them asserts anything about corpus completeness, and compiling the
    whole corpus to read four modelos would make them fail for a defect in any
    of the other fifty-four.
    """
    return {
        modelo_id: load_modelo_directory(_bundled_source(modelo_id).path)
        for modelo_id in ("151", "309", "369", "390")
    }


def test_the_contradiction_check_catches_a_planted_absence_on_a_live_chain(
    modelos: Mapping[str, ModeloDefinition],
) -> None:
    """An absence written onto a row whose chain the predecessor carries is a contradiction."""
    modelo = modelos["390"]
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
    modelos: Mapping[str, ModeloDefinition],
) -> None:
    modelo = modelos["390"]
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
    modelos: Mapping[str, ModeloDefinition],
) -> None:
    """A grounded link lifts the semantic_role requirement; the same link written as seeded does not."""
    modelo = modelos["151"]
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
    modelos: Mapping[str, ModeloDefinition],
) -> None:
    """A ruled row keeps the ruling's category; every other residual row takes the exclusion's."""
    plan = residual_plan("309", modelos["309"], load_rulings()["309"])
    categories = {(refusal.revision, refusal.casilla_id): refusal.category for refusal in plan.refusals}
    assert plan.edits == {}
    assert categories[("2016-2017", "decl.transmitente-apellidos")] == "withheld"
    assert categories[("2016-2017", "decl.transmitente-pais")] == "held"
    assert categories[("2018-2022", "decl.transmitente-pais")] == "absence_unclassified"
    unruled = residual_plan("309", modelos["309"], ())
    assert {refusal.category for refusal in unruled.refusals} == {"absence_unclassified"}


def test_an_excluded_modelo_that_cannot_have_a_residual_row_refuses_to_record_one(
    modelos: Mapping[str, ModeloDefinition],
) -> None:
    """Modelo 369's editions declare no predecessor; losing that declaration is an error, not a refusal."""
    modelo = modelos["369"]
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


# --------------------------------------------------------------------------- per-modelo loading


_LOADABLE = "303"
_PLANTED = "999"


def _bundled_source(modelo_id: str) -> ModeloSource:
    sources = discover_modelo_sources(bundled_path("registry", "aeat", "modelos"))
    return next(source for source in sources if source.modelo_id == modelo_id)


def _planted_failure(root: Path) -> ModeloSource:
    """A modelo directory the registry loader refuses: a manifest with no revisions beside it."""
    directory = root / _PLANTED
    (directory / "revisions").mkdir(parents=True)
    (directory / "manifest.toml").write_text(f'[modelo]\nid = "{_PLANTED}"\n', encoding="utf-8")
    return ModeloSource(modelo_id=_PLANTED, path=directory, manifest_path=directory / "manifest.toml")


def test_a_modelo_that_cannot_be_compiled_is_recorded_and_stops_only_itself(tmp_path: Path) -> None:
    """The control loads clean; adding a modelo the loader refuses records it and seeds the rest anyway."""
    real = _bundled_source(_LOADABLE)
    control, no_failures = load_corpus((real,))
    assert sorted(control) == [_LOADABLE]
    assert no_failures == ()

    loaded, failures = load_corpus((real, _planted_failure(tmp_path)))
    assert sorted(loaded) == [_LOADABLE], "a modelo that fails to load must not take another one down"
    assert len(loaded[_LOADABLE].revisions) > 1
    assert [failure.modelo for failure in failures] == [_PLANTED]
    assert "no revisions found" in failures[0].reason


def test_a_recorded_load_failure_never_names_a_machine_specific_path(tmp_path: Path) -> None:
    """The ledger is committed, so a reason must read the same in every checkout."""
    _, failures = load_corpus((_planted_failure(tmp_path),))
    assert "\\" not in failures[0].reason
    assert str(Path(__file__).resolve().parents[3]) not in failures[0].reason


def test_a_load_failure_with_nothing_to_carry_names_no_row(tmp_path: Path) -> None:
    """The [[load_failed]] record itself names no row; what keeps the ledger whole is the carry below."""
    loaded, _ = load_corpus((_bundled_source(_LOADABLE),))
    modelo = loaded[_LOADABLE]
    unresolved = unresolved_successor_rows(modelo)
    assert unresolved, f"modelo {_LOADABLE} has no unresolved row left; this gate would be vacuous"

    plan = LineagePlan(_LOADABLE)
    for key in unresolved:
        plan.refuse(key.revision, key.casilla, LineageRefusalCategory.NOT_EXAMINED, "planted for this gate")
    failure = ModeloLoadFailure(_PLANTED, f"registry/aeat/modelos/{_PLANTED}: no revisions found in revisions/")
    path = tmp_path / "ledger.toml"
    path.write_text(render_ledger([plan], {_LOADABLE: []}, (failure,), ()) + "\n", encoding="utf-8")

    document = tomllib.loads(path.read_text(encoding="utf-8"))
    assert document["load_failed"] == [{"modelo": failure.modelo, "reason": failure.reason}]
    assert all(entry["modelo"] != _PLANTED for entry in document["refusal"])

    keys = set(load_ledger_refusals(path))
    assert {key.modelo for key in keys} == {_LOADABLE}
    assert lineage_totality((modelo,), keys).is_total
    # The same ledger one row short is not total, so the assertion above is earned rather than vacuous.
    assert not lineage_totality((modelo,), keys - {min(keys)}).is_total


# --------------------------------------------------------------------------- partly stamped identifiers


_PLANTED_ROW = "23"
_PLANTED_ROLE = "planted_role_no_successor_shares"


def _oracle() -> DesignOracle:
    return DesignOracle(load_shared_catalogues(bundled_path("registry", "aeat")).sources)


def _half_stamped(modelo: ModeloDefinition) -> ModeloDefinition:
    """The same modelo with one identifier's first-edition occurrence left unstamped and unexcused.

    Mirrors the shape a half-finished stamping pass leaves behind: the later
    editions carry the chain, and the first carries neither it nor an absence.
    The first edition has no predecessor to seed from, and the divergent
    ``semantic_role`` keeps the bare-chain admission from healing it forward, so
    the identifier stays partly stamped exactly as the corpus would leave it.
    """
    first = ordered_revisions(modelo)[0]
    casillas = tuple(
        casilla.model_copy(
            update={
                "continuidad_id": None,
                "continuidad_origin": None,
                "continuidad_evidence": None,
                "semantic_role": _PLANTED_ROLE,
            }
        )
        if casilla.id == _PLANTED_ROW
        else casilla
        for casilla in first.casillas
    )
    return modelo.model_copy(
        update={"revisions": {**modelo.revisions, first.id: first.model_copy(update={"casillas": casillas})}}
    )


def test_a_partly_stamped_modelo_is_recorded_and_stops_only_itself() -> None:
    """The control plans clean; a planted half-stamped chain is recorded and the run keeps going."""
    loaded, _ = load_corpus((_bundled_source(_LOADABLE),))
    modelo = loaded[_LOADABLE]
    oracle = _oracle()

    # Negative control: unplanted, the same modelo plans without a record, so a plant that
    # stopped taking would leave the positive assertion below failing rather than vacuously green.
    control_plans, control_records = plan_corpus((_LOADABLE,), {_LOADABLE: modelo}, oracle, {})
    assert [plan.modelo for plan in control_plans] == [_LOADABLE]
    assert control_records == ()

    planted = _half_stamped(modelo)
    # The refusal to seed into a partly stamped chain is unchanged: planning it alone still raises.
    with pytest.raises(PartialStampingError, match="stay partly stamped"):
        plan_modelo(_PLANTED, planted, oracle, {})

    plans, records = plan_corpus((_LOADABLE, _PLANTED), {_LOADABLE: modelo, _PLANTED: planted}, oracle, {})
    assert [plan.modelo for plan in plans] == [_LOADABLE], "a partly stamped modelo must not take another one down"
    assert [(record.modelo, record.casilla) for record in records] == [(_PLANTED, _PLANTED_ROW)]
    record = records[0]
    assert record.chain, "the record must name the chain the stamped editions carry"
    assert record.unstamped == (ordered_revisions(modelo)[0].id,)
    assert set(record.stamped) == set(modelo.revisions) - set(record.unstamped)
    assert record.chain in record.describe()
    assert record.unstamped[0] in record.describe()


def test_a_partly_stamped_modelo_with_nothing_to_carry_names_no_row(tmp_path: Path) -> None:
    """The [[stamping_in_progress]] record itself names no row; its previous refusals are carried below."""
    loaded, _ = load_corpus((_bundled_source(_LOADABLE),))
    modelo = loaded[_LOADABLE]
    unresolved = unresolved_successor_rows(modelo)
    assert unresolved, f"modelo {_LOADABLE} has no unresolved row left; this gate would be vacuous"

    plan = LineagePlan(_LOADABLE)
    for key in unresolved:
        plan.refuse(key.revision, key.casilla, LineageRefusalCategory.NOT_EXAMINED, "planted for this gate")
    record = PartialStamping(
        modelo=_PLANTED,
        casilla=_PLANTED_ROW,
        chain="dr999-23",
        stamped=("2023", "2024"),
        unstamped=("2022",),
    )
    path = tmp_path / "ledger.toml"
    path.write_text(render_ledger([plan], {_LOADABLE: []}, (), (record,)) + "\n", encoding="utf-8")

    document = tomllib.loads(path.read_text(encoding="utf-8"))
    assert document["stamping_in_progress"] == [
        {
            "modelo": _PLANTED,
            "casilla": _PLANTED_ROW,
            "chain": "dr999-23",
            "stamped": ["2023", "2024"],
            "unstamped": ["2022"],
        }
    ]
    assert all(entry["modelo"] != _PLANTED for entry in document["refusal"])

    keys = set(load_ledger_refusals(path))
    assert {key.modelo for key in keys} == {_LOADABLE}
    assert lineage_totality((modelo,), keys).is_total
    # The same ledger one row short is not total, so the assertion above is earned rather than vacuous.
    assert not lineage_totality((modelo,), keys - {min(keys)}).is_total


# --------------------------------------------------------------------------- carrying forward


_PREVIOUS_RUN = "2026-09-01T08:00:00Z"
_SKIPPED = {_PLANTED: "modelo could not be compiled this run: no revisions found in revisions/"}


def _previous_ledger(tmp_path: Path, plan: LineagePlan, skipped_rows: tuple[tuple[str, str], ...]) -> Path:
    """A ledger as a healthy previous run left it: ``plan``'s refusals plus the skipped modelo's own."""
    skipped = LineagePlan(_PLANTED)
    for revision, casilla in skipped_rows:
        skipped.refuse(revision, casilla, LineageRefusalCategory.NOT_EXAMINED, "judged by the previous run")
    path = tmp_path / "previous.toml"
    path.write_text(
        render_ledger(
            [plan, skipped],
            {_LOADABLE: [], _PLANTED: []},
            (),
            (),
            carried=(),
            judged_at=_PREVIOUS_RUN,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def test_a_skipped_modelos_previous_refusals_are_carried_forward_rather_than_dropped(tmp_path: Path) -> None:
    """Carrying keeps the ledger whole; the same run without it drops the modelo's rows outright."""
    loaded, _ = load_corpus((_bundled_source(_LOADABLE),))
    modelo = loaded[_LOADABLE]
    unresolved = unresolved_successor_rows(modelo)
    assert unresolved, f"modelo {_LOADABLE} has no unresolved row left; this gate would be vacuous"
    plan = LineagePlan(_LOADABLE)
    for key in unresolved:
        plan.refuse(key.revision, key.casilla, LineageRefusalCategory.NOT_EXAMINED, "planted for this gate")

    rows = (("2023", "01"), ("2024", "02"))
    previous = load_previous_ledger(_previous_ledger(tmp_path, plan, rows))
    assert previous.judged_at == _PREVIOUS_RUN
    assert {(entry["revision"], entry["casilla"]) for entry in previous.refusals[_PLANTED]} == set(rows)

    carried = carried_refusals(previous, _SKIPPED)
    assert [(entry.revision, entry.casilla) for entry in carried] == sorted(rows)
    failure = ModeloLoadFailure(_PLANTED, "registry/aeat/modelos/999: no revisions found in revisions/")

    path = tmp_path / "carried.toml"
    now = run_identifier()
    path.write_text(
        render_ledger([plan], {_LOADABLE: []}, (failure,), (), carried=carried, judged_at=now) + "\n",
        encoding="utf-8",
    )
    entries = load_ledger_refusals(path)
    assert {key.modelo for key in entries} == {_LOADABLE, _PLANTED}, "the skipped modelo must keep its rows"
    assert {(key.revision, key.casilla) for key in entries if key.modelo == _PLANTED} == set(rows)
    for key, entry in entries.items():
        if key.modelo != _PLANTED:
            continue
        assert entry.carried_from_previous_run
        assert entry.reason == "judged by the previous run", "a carried entry is carried verbatim"
        assert entry.last_judged == _PREVIOUS_RUN
        assert entry.carried_runs == 1
        assert "could not be compiled" in (entry.carried_reason or "")

    # Negative control: the same run that drops instead of carrying loses the modelo from the ledger,
    # so the assertions above are earned rather than vacuous.
    dropped = tmp_path / "dropped.toml"
    dropped.write_text(
        render_ledger([plan], {_LOADABLE: []}, (failure,), (), carried=(), judged_at=now) + "\n", encoding="utf-8"
    )
    assert {key.modelo for key in load_ledger_refusals(dropped)} == {_LOADABLE}


def test_a_carried_refusal_records_when_it_was_last_actually_judged(tmp_path: Path) -> None:
    """Carrying twice keeps the original judgement and counts the carries, so staleness stays visible."""
    plan = LineagePlan(_LOADABLE)
    plan.refuse("2024", "01", LineageRefusalCategory.NOT_EXAMINED, "judged by the previous run")
    rows = (("2023", "01"),)
    first = carried_refusals(load_previous_ledger(_previous_ledger(tmp_path, plan, rows)), _SKIPPED)
    assert [(entry.last_judged, entry.carried_runs) for entry in first] == [(_PREVIOUS_RUN, 1)]

    second_run = tmp_path / "second.toml"
    second_run.write_text(
        render_ledger([plan], {_LOADABLE: []}, (), (), carried=first, judged_at="2026-09-05T09:00:00Z") + "\n",
        encoding="utf-8",
    )
    second = carried_refusals(load_previous_ledger(second_run), _SKIPPED)
    assert [(entry.last_judged, entry.carried_runs) for entry in second] == [(_PREVIOUS_RUN, 2)], (
        "a re-carried entry keeps the run that judged it and counts one more carry"
    )

    third_run = tmp_path / "third.toml"
    third_run.write_text(
        render_ledger([plan], {_LOADABLE: []}, (), (), carried=second, judged_at="2026-09-09T09:00:00Z") + "\n",
        encoding="utf-8",
    )
    third = carried_refusals(load_previous_ledger(third_run), _SKIPPED)
    assert [(entry.last_judged, entry.carried_runs) for entry in third] == [(_PREVIOUS_RUN, 3)]


def test_a_carried_refusal_never_collides_with_one_this_run_judged(tmp_path: Path) -> None:
    """Judging and carrying the same row would name it twice; that is this tooling contradicting itself."""
    plan = LineagePlan(_LOADABLE)
    plan.refuse("2024", "01", LineageRefusalCategory.NOT_EXAMINED, "judged this run")
    collision = CarriedRefusal(
        modelo=_LOADABLE,
        revision="2024",
        casilla="01",
        category="not_examined",
        reason="judged by the previous run",
        predecessor=None,
        carried_reason="planted collision",
        last_judged=_PREVIOUS_RUN,
        carried_runs=1,
    )
    with pytest.raises(ValueError, match="is also judged in this run"):
        render_ledger([plan], {_LOADABLE: []}, (), (), carried=(collision,), judged_at=run_identifier())
    # The same render without the collision is fine, so the refusal is the collision's doing.
    text = render_ledger([plan], {_LOADABLE: []}, (), (), carried=(), judged_at=run_identifier())
    assert '[run]' in text
