"""Behaviour of the casilla lineage seeder's predicates, design oracle and writer.

Each refusal is shown against a control that passes, so a predicate that stopped
refusing would turn a test red rather than leave it vacuously green.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.toml import parse_toml
from cadrumo.domain.calculations.registry.casilla_lineage import CasillaLineageOrigin
from cadrumo.domain.calculations.registry.casilla_lineage_totality import (
    lineage_totality,
    unresolved_successor_rows,
)
from cadrumo.domain.calculations.registry.errors import RegistryError
from cadrumo.domain.calculations.registry.revision_order import ordered_revisions, revisions_overlap
from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.tests.authored_editions import (
    authored_revisions,
    filing_year_envelope,
    open_ended_revision,
)
from cadrumo.domain.calculations.registry.tests.lineage_totality import is_total

from ..analysis import casilla_lineage_seed
from ..analysis.casilla_lineage_ledger import load_ledger_refusals
from ..analysis.casilla_lineage_seed_corpus import load_corpus
from ..analysis.casilla_lineage_seed_design import parse_design_inventory
from ..analysis.casilla_lineage_seed_ledger import (
    carried_refusals,
    load_previous_ledger,
    render_ledger,
    run_identifier,
)
from ..analysis.casilla_lineage_seed_planner import plan_corpus, plan_modelo, residual_plan
from ..analysis.casilla_lineage_seed_rules import admit_bare_chain, judged_pairs, load_rulings
from ..analysis.casilla_lineage_seed_types import (
    SCHEMA_EVIDENCE_LIMIT,
    CarriedRefusal,
    LineagePlan,
    LineageRefusalCategory,
    ModeloLoadFailure,
    PartialStamping,
    Ruling,
)
from ..analysis.casilla_lineage_seed_validation import contradictions, gate_regressions
from ..analysis.casilla_lineage_seed_writer import insert_lineage_keys
from ..compiler.loader import load_modelo_directory
from ..compiler.loader_cache import ModeloSource, discover_modelo_sources
from .casilla_lineage_planted_support import (
    ABSENT_ROW,
    HELD_REASON,
    HELD_ROW,
    HELD_STEM,
    PLANTED_MODELO,
    absence_modelo,
    design_oracle,
    held_modelo,
    held_pair_ruling,
    planted_casilla,
    planted_modelo,
    planted_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_YEAR = filing_year_envelope().horizon
# Three consecutive edition labels for the planted modelos, oldest first.
_REV_A, _REV_B, _REV_C = (str(_YEAR - 2), str(_YEAR - 1), str(_YEAR))
# The first three authored editions of Modelo 390, which each carry the one before's chains.
_M390_FIRST, _M390_SECOND, _M390_THIRD = (str(revision.id) for revision in authored_revisions("390")[:3])
_M151_OPEN = str(open_ended_revision("151").id)


def _instant(month: int, day: int, hour: int) -> str:
    return datetime(_YEAR, month, day, hour, tzinfo=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


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
    category, _ = admit_bare_chain(planted_casilla(), planted_casilla())
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
    refused, reason = admit_bare_chain(planted_casilla(**previous), planted_casilla(**successor))
    assert refused == category, reason


def test_the_general_number_field_is_never_read_for_identity() -> None:
    """A one-byte wire campo declares a plain integer in ``number``; it must not refuse a sound chain."""
    category, _ = admit_bare_chain(planted_casilla(number="977"), planted_casilla(number="1016"))
    assert category is None
    refused, _ = admit_bare_chain(
        planted_casilla(number="977", form_number="12"), planted_casilla(number="977", form_number="13")
    )
    assert refused == "contradicted"


# --------------------------------------------------------------------------- writer

_FILE = """\
[[revisions."{older}".casillas]]
id = "01"
number = "01"

[[revisions."{older}".casillas]]
id = "02"
continuidad_id = "base"
number = "02"

[[revisions."{newer}".casillas]]
id = "01"
number = "01"
""".replace("{older}", _REV_B).replace("{newer}", _REV_C)


def test_keys_are_inserted_into_the_named_revision_table_only() -> None:
    text, done = insert_lineage_keys(
        _FILE, _REV_B, {"01": {"continuidad_origin": "new_on_form", "continuidad_evidence": "design.md:3 [01]"}}
    )
    assert done == {"01"}
    assert text.splitlines()[:5] == [
        f'[[revisions."{_REV_B}".casillas]]',
        'id = "01"',
        'continuidad_origin = "new_on_form"',
        'continuidad_evidence = "design.md:3 [01]"',
        'number = "01"',
    ]
    assert text.endswith(f'[[revisions."{_REV_C}".casillas]]\nid = "01"\nnumber = "01"\n')


def test_keys_follow_an_existing_chain_and_an_identical_value_is_left_alone() -> None:
    text, done = insert_lineage_keys(_FILE, _REV_B, {"02": {"continuidad_id": "base", "continuidad_origin": "seeded"}})
    assert done == {"02"}
    assert 'continuidad_id = "base"\ncontinuidad_origin = "seeded"\nnumber = "02"' in text
    assert text.count('continuidad_id = "base"') == 1
    again, _ = insert_lineage_keys(text, _REV_B, {"02": {"continuidad_id": "base", "continuidad_origin": "seeded"}})
    assert again == text


def test_a_differing_value_already_present_is_never_overwritten() -> None:
    with pytest.raises(ValueError, match="already declares a different continuidad_id"):
        insert_lineage_keys(_FILE, _REV_B, {"02": {"continuidad_id": "other"}})


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
        modelo_id: load_modelo_directory(_bundled_source(modelo_id).path) for modelo_id in ("151", "309", "369", "390")
    }


def test_the_contradiction_check_catches_a_planted_absence_on_a_live_chain(
    modelos: Mapping[str, ModeloDefinition],
) -> None:
    """An absence written onto a row whose chain the predecessor carries is a contradiction."""
    modelo = modelos["390"]
    predecessor, successor = modelo.revisions[_M390_SECOND], modelo.revisions[_M390_THIRD]
    prior = {casilla.continuidad_id for casilla in predecessor.casillas} - {None}
    target = next(casilla for casilla in successor.casillas if casilla.continuidad_id in prior)
    assert contradictions(modelo, LineagePlan("390")) == []
    planted = LineagePlan("390")
    planted.set_keys(_M390_THIRD, target.id, continuidad_origin="new_on_form", continuidad_evidence="design.md:1 [1]")
    assert contradictions(modelo, planted) == [
        f"{_M390_THIRD}/{target.id}: new_on_form but chain {target.continuidad_id!r} present in {_M390_SECOND}"
    ]


def test_the_contradiction_check_catches_a_continuation_with_no_chain_behind_it(
    modelos: Mapping[str, ModeloDefinition],
) -> None:
    modelo = modelos["390"]
    first, second = modelo.revisions[_M390_FIRST], modelo.revisions[_M390_SECOND]
    prior = {casilla.continuidad_id for casilla in first.casillas} - {None}
    target = next(
        casilla
        for casilla in second.casillas
        if casilla.continuidad_id is not None and casilla.continuidad_id not in prior
    )
    planted = LineagePlan("390")
    planted.set_keys(_M390_SECOND, target.id, continuidad_origin="seeded")
    assert contradictions(modelo, planted) == [
        f"{_M390_SECOND}/{target.id}: seeded but chain {target.continuidad_id!r} absent from {_M390_FIRST}"
    ]


def test_the_registry_gate_refuses_a_roleless_chain_unless_every_link_is_grounded(
    modelos: Mapping[str, ModeloDefinition],
) -> None:
    """A grounded link lifts the semantic_role requirement; the same link written as seeded does not."""
    modelo = modelos["151"]
    successor = next(
        casilla
        for casilla in modelo.revisions[_M151_OPEN].casillas
        if casilla.continuidad_origin is not None
        and casilla.continuidad_origin.value == "grounded"
        and casilla.semantic_role is None
    )
    assert gate_regressions(modelo, LineagePlan("151")) == []
    demoted = LineagePlan("151")
    demoted.set_keys(_M151_OPEN, successor.id, continuidad_origin="seeded")
    regressions = gate_regressions(modelo, demoted)
    assert any(f"casilla {successor.id!r} has no semantic_role" in failure for failure in regressions), regressions


def _unstamped(modelo: ModeloDefinition, rows: set[tuple[str, str]]) -> ModeloDefinition:
    """Return ``modelo`` with each ``(revision, casilla)`` row left without its lineage stamp."""
    revisions = dict(modelo.revisions)
    for revision_id in {revision for revision, _ in rows}:
        revision = revisions[revision_id]
        casillas = tuple(
            casilla.model_copy(
                update={"continuidad_id": None, "continuidad_origin": None, "continuidad_evidence": None}
            )
            if (revision_id, casilla.id) in rows
            else casilla
            for casilla in revision.casillas
        )
        revisions[revision_id] = revision.model_copy(update={"casillas": casillas})
    return modelo.model_copy(update={"revisions": revisions})


def test_an_excluded_modelo_is_refused_row_by_row_and_never_written(
    modelos: Mapping[str, ModeloDefinition],
) -> None:
    """A ruled row keeps the ruling's category; every other residual row takes the exclusion's.

    The exemplars come from the rulings rather than from three hard-coded rows.
    They were hard-coded, and one of them -- ``2018-2022 decl.transmitente-pais``
    -- stopped being a residual the moment it was grounded, which failed this
    test for the corpus getting BETTER. A fixture that has to be edited every
    time the adjudication campaign lands a row cannot tell a regression from
    progress, so the invariant is stated against whatever the rulings currently
    say. Once the corpus grounds every ruled row the live modelo has no residual
    left, so each ruled row is planted back unstamped to keep the gate earned.
    """
    rulings = load_rulings()["309"]
    ruled_rows = {
        (ruling.successor, successor_casilla)
        for ruling in rulings
        for pairs in (ruling.held, ruling.withheld)
        for _, successor_casilla in pairs
    }
    modelo = _unstamped(modelos["309"], ruled_rows)
    plan = residual_plan("309", modelo, rulings)
    categories = {(refusal.revision, refusal.casilla_id): refusal.category for refusal in plan.refusals}
    assert plan.edits == {}, "an excluded modelo is refused row by row and never written"

    ruled: dict[tuple[str, str], str] = {}
    for ruling in rulings:
        for category, pairs in (("held", ruling.held), ("withheld", ruling.withheld)):
            for _, successor_casilla in pairs:
                ruled[(ruling.successor, successor_casilla)] = category
    assert ruled, "309's rulings must name at least one held or withheld row for this to test anything"

    for key, category in ruled.items():
        assert categories[key] == category, f"{key} should keep the ruling's {category}"
    for key, category in categories.items():
        if key not in ruled:
            assert category == "absence_unclassified", f"{key} is unruled and takes the exclusion's category"

    # A ruling recategorises a residual; it never adds or removes one. Without
    # that, a ruling that silently dropped rows from the plan would leave those
    # rows unrefused and unwritten, which is the one outcome an excluded modelo
    # must never produce.
    unruled = residual_plan("309", modelo, ())
    assert {(refusal.revision, refusal.casilla_id) for refusal in unruled.refusals} == set(categories)
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
#: A modelo whose successor editions still carry unresolved rows.
_UNRESOLVED = "100"


def _bundled_source(modelo_id: str) -> ModeloSource:
    sources = discover_modelo_sources(bundled_path("registry", "aeat", "modelos"))
    return next(source for source in sources if source.modelo_id == modelo_id)


def _planted_failure(root: Path) -> ModeloSource:
    """A modelo directory the registry loader refuses: a manifest with no revisions beside it."""
    directory = root / PLANTED_MODELO
    (directory / "revisions").mkdir(parents=True)
    (directory / "manifest.toml").write_text(f'[modelo]\nid = "{PLANTED_MODELO}"\n', encoding="utf-8")
    return ModeloSource(modelo_id=PLANTED_MODELO, path=directory, manifest_path=directory / "manifest.toml")


def test_a_modelo_that_cannot_be_compiled_is_recorded_and_stops_only_itself(tmp_path: Path) -> None:
    """The control loads clean; adding a modelo the loader refuses records it and seeds the rest anyway."""
    real = _bundled_source(_LOADABLE)
    control, no_failures = load_corpus((real,))
    assert sorted(control) == [_LOADABLE]
    assert no_failures == ()

    loaded, failures = load_corpus((real, _planted_failure(tmp_path)))
    assert sorted(loaded) == [_LOADABLE], "a modelo that fails to load must not take another one down"
    assert len(loaded[_LOADABLE].revisions) > 1
    assert [failure.modelo for failure in failures] == [PLANTED_MODELO]
    assert "no revisions found" in failures[0].reason


def test_a_recorded_load_failure_never_names_a_machine_specific_path(tmp_path: Path) -> None:
    """The ledger is committed, so a reason must read the same in every checkout."""
    _, failures = load_corpus((_planted_failure(tmp_path),))
    assert "\\" not in failures[0].reason
    assert str(Path(__file__).resolve().parents[3]) not in failures[0].reason


def test_a_load_failure_with_nothing_to_carry_names_no_row(tmp_path: Path) -> None:
    """The [[load_failed]] record itself names no row; what keeps the ledger whole is the carry below."""
    loaded, _ = load_corpus((_bundled_source(_UNRESOLVED),))
    modelo = loaded[_UNRESOLVED]
    unresolved = unresolved_successor_rows(modelo)
    assert unresolved, f"modelo {_UNRESOLVED} has no unresolved row left; this gate would be vacuous"

    plan = LineagePlan(_UNRESOLVED)
    for key in unresolved:
        plan.refuse(key.revision, key.casilla, LineageRefusalCategory.NOT_EXAMINED, "planted for this gate")
    failure = ModeloLoadFailure(
        PLANTED_MODELO, f"registry/aeat/modelos/{PLANTED_MODELO}: no revisions found in revisions/"
    )
    path = tmp_path / "ledger.toml"
    path.write_text(render_ledger([plan], {_UNRESOLVED: []}, (failure,), ()) + "\n", encoding="utf-8")

    document = parse_toml(path.read_text(encoding="utf-8"))
    assert document["load_failed"] == [{"modelo": failure.modelo, "reason": failure.reason}]
    assert all(entry["modelo"] != PLANTED_MODELO for entry in document["refusal"])

    keys = set(load_ledger_refusals(path))
    assert {key.modelo for key in keys} == {_UNRESOLVED}
    assert is_total(lineage_totality((modelo,), keys))
    # The same ledger one row short is not total, so the assertion above is earned rather than vacuous.
    assert not is_total(lineage_totality((modelo,), keys - {min(keys)}))


# --------------------------------------------------------------------------- partly stamped identifiers


_PLANTED_ROW = "23"
_PLANTED_ROLE = "planted_role_no_successor_shares"


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
    oracle = design_oracle()

    # Negative control: unplanted, the same modelo plans without a record, so a plant that
    # stopped taking would leave the positive assertion below failing rather than vacuously green.
    control_plans, control_records = plan_corpus((_LOADABLE,), {_LOADABLE: modelo}, oracle, {})
    assert [plan.modelo for plan in control_plans] == [_LOADABLE]
    assert control_records == ()

    planted = _half_stamped(modelo)
    # The refusal to seed into a partly stamped chain is unchanged: planning it alone still raises.
    with pytest.raises(RegistryError, match="stay partly stamped"):
        plan_modelo(PLANTED_MODELO, planted, oracle, {})

    plans, records = plan_corpus((_LOADABLE, PLANTED_MODELO), {_LOADABLE: modelo, PLANTED_MODELO: planted}, oracle, {})
    assert [plan.modelo for plan in plans] == [_LOADABLE], "a partly stamped modelo must not take another one down"
    assert [(record.modelo, record.casilla) for record in records] == [(PLANTED_MODELO, _PLANTED_ROW)]
    record = records[0]
    assert record.chain, "the record must name the chain the stamped editions carry"
    assert record.unstamped == (ordered_revisions(modelo)[0].id,)
    assert set(record.stamped) == set(modelo.revisions) - set(record.unstamped)
    assert record.chain in record.describe()
    assert record.unstamped[0] in record.describe()


def test_a_partly_stamped_modelo_with_nothing_to_carry_names_no_row(tmp_path: Path) -> None:
    """The [[stamping_in_progress]] record itself names no row; its previous refusals are carried below."""
    loaded, _ = load_corpus((_bundled_source(_UNRESOLVED),))
    modelo = loaded[_UNRESOLVED]
    unresolved = unresolved_successor_rows(modelo)
    assert unresolved, f"modelo {_UNRESOLVED} has no unresolved row left; this gate would be vacuous"

    plan = LineagePlan(_UNRESOLVED)
    for key in unresolved:
        plan.refuse(key.revision, key.casilla, LineageRefusalCategory.NOT_EXAMINED, "planted for this gate")
    record = PartialStamping(
        modelo=PLANTED_MODELO,
        casilla=_PLANTED_ROW,
        chain="dr999-23",
        stamped=(_REV_B, _REV_C),
        unstamped=(_REV_A,),
    )
    path = tmp_path / "ledger.toml"
    path.write_text(render_ledger([plan], {_UNRESOLVED: []}, (), (record,)) + "\n", encoding="utf-8")

    document = parse_toml(path.read_text(encoding="utf-8"))
    assert document["stamping_in_progress"] == [
        {
            "modelo": PLANTED_MODELO,
            "casilla": _PLANTED_ROW,
            "chain": "dr999-23",
            "stamped": [_REV_B, _REV_C],
            "unstamped": [_REV_A],
        }
    ]
    assert all(entry["modelo"] != PLANTED_MODELO for entry in document["refusal"])

    keys = set(load_ledger_refusals(path))
    assert {key.modelo for key in keys} == {_UNRESOLVED}
    assert is_total(lineage_totality((modelo,), keys))
    # The same ledger one row short is not total, so the assertion above is earned rather than vacuous.
    assert not is_total(lineage_totality((modelo,), keys - {min(keys)}))


# --------------------------------------------------------------------------- carrying forward


_PREVIOUS_RUN = _instant(9, 1, 8)
_SKIPPED = {PLANTED_MODELO: "modelo could not be compiled this run: no revisions found in revisions/"}


def _previous_ledger(tmp_path: Path, plan: LineagePlan, skipped_rows: tuple[tuple[str, str], ...]) -> Path:
    """A ledger as a healthy previous run left it: ``plan``'s refusals plus the skipped modelo's own."""
    skipped = LineagePlan(PLANTED_MODELO)
    for revision, casilla in skipped_rows:
        skipped.refuse(revision, casilla, LineageRefusalCategory.NOT_EXAMINED, "judged by the previous run")
    path = tmp_path / "previous.toml"
    path.write_text(
        render_ledger(
            [plan, skipped],
            {plan.modelo: [], PLANTED_MODELO: []},
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
    loaded, _ = load_corpus((_bundled_source(_UNRESOLVED),))
    modelo = loaded[_UNRESOLVED]
    unresolved = unresolved_successor_rows(modelo)
    assert unresolved, f"modelo {_UNRESOLVED} has no unresolved row left; this gate would be vacuous"
    plan = LineagePlan(_UNRESOLVED)
    for key in unresolved:
        plan.refuse(key.revision, key.casilla, LineageRefusalCategory.NOT_EXAMINED, "planted for this gate")

    rows = ((_REV_B, "01"), (_REV_C, "02"))
    previous = load_previous_ledger(_previous_ledger(tmp_path, plan, rows))
    assert previous.judged_at == _PREVIOUS_RUN
    assert {(entry["revision"], entry["casilla"]) for entry in previous.refusals[PLANTED_MODELO]} == set(rows)

    carried = carried_refusals(previous, _SKIPPED)
    assert [(entry.revision, entry.casilla) for entry in carried] == sorted(rows)
    failure = ModeloLoadFailure(PLANTED_MODELO, "registry/aeat/modelos/999: no revisions found in revisions/")

    path = tmp_path / "carried.toml"
    now = run_identifier()
    path.write_text(
        render_ledger([plan], {_UNRESOLVED: []}, (failure,), (), carried=carried, judged_at=now) + "\n",
        encoding="utf-8",
    )
    entries = load_ledger_refusals(path)
    assert {key.modelo for key in entries} == {_UNRESOLVED, PLANTED_MODELO}, "the skipped modelo must keep its rows"
    assert {(key.revision, key.casilla) for key in entries if key.modelo == PLANTED_MODELO} == set(rows)
    for key, entry in entries.items():
        if key.modelo != PLANTED_MODELO:
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
        render_ledger([plan], {_UNRESOLVED: []}, (failure,), (), carried=(), judged_at=now) + "\n", encoding="utf-8"
    )
    assert {key.modelo for key in load_ledger_refusals(dropped)} == {_UNRESOLVED}


def test_a_carried_refusal_records_when_it_was_last_actually_judged(tmp_path: Path) -> None:
    """Carrying twice keeps the original judgement and counts the carries, so staleness stays visible."""
    plan = LineagePlan(_LOADABLE)
    plan.refuse(_REV_C, "01", LineageRefusalCategory.NOT_EXAMINED, "judged by the previous run")
    rows = ((_REV_B, "01"),)
    first = carried_refusals(load_previous_ledger(_previous_ledger(tmp_path, plan, rows)), _SKIPPED)
    assert [(entry.last_judged, entry.carried_runs) for entry in first] == [(_PREVIOUS_RUN, 1)]

    second_run = tmp_path / "second.toml"
    second_run.write_text(
        render_ledger([plan], {_LOADABLE: []}, (), (), carried=first, judged_at=_instant(9, 5, 9)) + "\n",
        encoding="utf-8",
    )
    second = carried_refusals(load_previous_ledger(second_run), _SKIPPED)
    assert [(entry.last_judged, entry.carried_runs) for entry in second] == [(_PREVIOUS_RUN, 2)], (
        "a re-carried entry keeps the run that judged it and counts one more carry"
    )

    third_run = tmp_path / "third.toml"
    third_run.write_text(
        render_ledger([plan], {_LOADABLE: []}, (), (), carried=second, judged_at=_instant(9, 9, 9)) + "\n",
        encoding="utf-8",
    )
    third = carried_refusals(load_previous_ledger(third_run), _SKIPPED)
    assert [(entry.last_judged, entry.carried_runs) for entry in third] == [(_PREVIOUS_RUN, 3)]


def test_a_carried_refusal_never_collides_with_one_this_run_judged(tmp_path: Path) -> None:
    """Judging and carrying the same row would name it twice; that is this tooling contradicting itself."""
    plan = LineagePlan(_LOADABLE)
    plan.refuse(_REV_C, "01", LineageRefusalCategory.NOT_EXAMINED, "judged this run")
    collision = CarriedRefusal(
        modelo=_LOADABLE,
        revision=_REV_C,
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
    assert "[run]" in text


# --------------------------------------------------------------------------- edition pairing


_PAIR_ROW = "01"


def test_lineage_command_rejects_unknown_arguments_before_loading_or_writing(capsys) -> None:
    with pytest.raises(SystemExit) as failure:
        casilla_lineage_seed.main(["--unrecognized-option"])
    assert failure.value.code == 2
    assert "unrecognized arguments" in capsys.readouterr().err


def test_editions_whose_selectors_overlap_but_whose_validity_succeeds_are_paired() -> None:
    """The live 308 shape: one edition closes before the next opens, and both name the same year."""
    closed = planted_revision(
        f"{_YEAR - 2}-{_YEAR}-junio", date(_YEAR - 2, 1, 1), date(_YEAR, 6, 30), (_YEAR,), (planted_casilla(),)
    )
    successor = planted_revision(
        f"{_YEAR}-julio-{_YEAR + 4}",
        date(_YEAR, 7, 1),
        date(_YEAR + 4, 12, 31),
        (_YEAR,),
        (planted_casilla(),),
        no_predecessor=True,
    )
    modelo = planted_modelo(closed, successor)

    # The shape is only interesting while the period selectors DO overlap: that is the reading
    # the seeder used to pair by, and pairing by dates has to disagree with it here.
    assert revisions_overlap(closed, successor), "the planted selectors no longer overlap; this gate is vacuous"
    assert [(previous.id, current.id) for previous, current in judged_pairs(modelo, ordered_revisions(modelo))] == [
        (str(closed.id), str(successor.id))
    ]


def test_concurrent_scheme_variants_sharing_a_validity_window_are_not_paired() -> None:
    """The live 369 shape: siblings that take effect together and never close continue nothing."""
    start = date(_YEAR, 7, 1)
    first = planted_revision("esquema-union", start, None, (_YEAR,), (planted_casilla(),), no_predecessor=True)
    second = planted_revision(
        "esquema-importacion", start, None, (_YEAR + 1,), (planted_casilla(),), no_predecessor=True
    )
    modelo = planted_modelo(first, second)

    # Their selectors do NOT overlap, so selector-reading would have paired them; the dates must not.
    assert not revisions_overlap(first, second), "the planted selectors now overlap; this gate is vacuous"
    assert judged_pairs(modelo, ordered_revisions(modelo)) == ()


# --------------------------------------------------------------------------- held stems


def _held_boundary() -> tuple[str, str]:
    """Return the two editions of the planted held modelo, which its rulings name as their boundary."""
    predecessor, successor = (str(revision.id) for revision in ordered_revisions(held_modelo(origin=None)))
    return predecessor, successor


def _held_ruling(predecessor: str, successor: str) -> Ruling:
    return Ruling(
        predecessor=predecessor,
        successor=successor,
        refuse_bare=False,
        rationale="planted for this gate",
        grounded=(),
        new_on_form=frozenset(),
        new_on_form_stems=frozenset(),
        not_on_form=frozenset(),
        held=(),
        held_stems=frozenset({HELD_STEM}),
        held_reason=HELD_REASON,
        withheld=(),
        withheld_reason="",
        merged=(),
        merged_reason="",
        discontinued=frozenset(),
    )


def _assert_held_row_with_declared_absence_is_dispositioned(rulings: dict[str, list[Ruling]]) -> None:
    plan = plan_modelo(PLANTED_MODELO, held_modelo(origin=CasillaLineageOrigin.NEW_ON_FORM), design_oracle(), rulings)

    assert [refusal.casilla_id for refusal in plan.refusals] == []
    assert plan.counts[CasillaLineageOrigin.NEW_ON_FORM.value] == 1

    # The same row without an origin is still held, so the skip above is the origin's doing.
    bare = plan_modelo(PLANTED_MODELO, held_modelo(origin=None), design_oracle(), rulings)
    assert [(refusal.casilla_id, refusal.category) for refusal in bare.refusals] == [
        (HELD_ROW, LineageRefusalCategory.HELD)
    ]
    assert bare.refusals[0].reason == HELD_REASON


def test_a_held_stem_row_that_already_declares_its_absence_is_not_refused_again() -> None:
    """A row whose kind of none is already written is dispositioned; re-refusing it makes the ledger stale."""
    rulings = {PLANTED_MODELO: [_held_ruling(*_held_boundary())]}
    _assert_held_row_with_declared_absence_is_dispositioned(rulings)


def test_a_held_pair_row_that_already_declares_its_absence_is_not_refused_again() -> None:
    """A row an adjudicated pair holds is dispositioned by its own declared origin, like a held stem."""
    rulings = {PLANTED_MODELO: [held_pair_ruling(*_held_boundary())]}
    _assert_held_row_with_declared_absence_is_dispositioned(rulings)


# --------------------------------------------------------------------------- unclassified absence


def test_an_unclassifiable_absence_that_already_declares_its_origin_is_not_refused() -> None:
    """A row whose kind of none is already written is dispositioned, whatever the record design can say."""
    origin = CasillaLineageOrigin.PREDECESSOR_EDITION_SILENT
    plan = plan_modelo(PLANTED_MODELO, absence_modelo(origin=origin), design_oracle(), {})

    assert [refusal.casilla_id for refusal in plan.refusals] == []
    assert plan.counts[origin.value] == 1


def test_an_unclassifiable_absence_with_no_origin_is_still_refused() -> None:
    """The negative control: with nothing declared, the row has no disposition and is refused."""
    bare = plan_modelo(PLANTED_MODELO, absence_modelo(origin=None), design_oracle(), {})

    assert [(refusal.casilla_id, refusal.category) for refusal in bare.refusals] == [
        (ABSENT_ROW, LineageRefusalCategory.ABSENCE_UNCLASSIFIED)
    ]


# --------------------------------------------------------------------------- evidence length


def test_evidence_within_the_schema_cap_is_written_and_reported_rather_than_refused() -> None:
    """The schema's cap is the bound; a long citation is kept and named, not cut to a house style."""
    plan = LineagePlan(PLANTED_MODELO)
    long_evidence = "x" * 700
    assert len(long_evidence) < SCHEMA_EVIDENCE_LIMIT, "the planted evidence no longer fits; this gate is vacuous"

    assert plan.record_evidence(_REV_C, "01", long_evidence) == long_evidence
    assert [(entry.revision, entry.casilla, entry.length) for entry in plan.long_evidence] == [(_REV_C, "01", 700)]

    # A routine-length citation is written without a report, so the report above is the length's doing.
    assert plan.record_evidence(_REV_C, "02", "short citation") == "short citation"
    assert [entry.casilla for entry in plan.long_evidence] == ["01"]


def test_evidence_over_the_schema_cap_refuses() -> None:
    plan = LineagePlan(PLANTED_MODELO)
    with pytest.raises(ValueError, match="exceeds the schema"):
        plan.record_evidence(_REV_C, "01", "x" * (SCHEMA_EVIDENCE_LIMIT + 1))
    assert plan.long_evidence == []
