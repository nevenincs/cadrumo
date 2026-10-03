"""The edition-delta migration keeps the member order an edition's declarations give.

An edition that states every member of a family it also inherits is a full copy
of that family, and its stated order is its meaning. A storage baseline added
beneath such a statement makes the merge move each member the baseline lacks to
the end, so a migration proven against that merge would carry the move into the
delta and still call it equivalent. These tests drive the real planner, writer,
family collapse and chain proof over a synthetic on-disk modelo: the order the
declarations give is restored with positions and proven to move members only,
the migration then keeps it, and a staged tree that lets a stated row land out
of order fails the proof. Every expectation is derived from the fixture's own
statement, never read back from a migration run.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Final

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryError
from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from ..compiler.loader import load_modelo_directory
from ..conformance.loader_directory_mode_support import write_standard_manifest
from ..edition_delta_equivalence import (
    _prove_chain,
)
from ..edition_delta_order_restoration import (
    OrderRestoration,
    _prove_order_restoration,
    _write_order_restorations,
    declared_order_restorations,
)
from ..edition_delta_migration import main, migrate_modelo
from ..edition_delta_planning import _plan
from ..edition_delta_writer import _write_edition
from ..edition_family_delta_collapse import collapse_keyed_families
from ..edition_round_trip import RoundTripReport, copy_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO_ID: Final = "999"
_LEGAL_REF: Final = "ley-58-2003:art-29"
_SOURCE_REF: Final = "aeat-manual"
_BASELINE: Final = "2024"
_EDITION: Final = "2025"
_CLEAN_REPORT: Final = RoundTripReport(findings=(), byte_compared_revisions=())
#: The baseline's rows and their lineages, in its record order.
_BASELINE_ROWS: Final = (("0001", "base"), ("0002", "cuota"), ("0003", "deduccion"))
#: The edition's record order: its one new box, 0004, sits between 0001 and 0002.
_EDITION_ROWS: Final = (("0001", "base"), ("0004", "recargo"), ("0002", "cuota"), ("0003", "deduccion"))
#: Formulas keep their ids across editions; the edition adds one between the two it shares.
_BASELINE_FORMULAS: Final = (("modelo-999-cuota", "0002"), ("modelo-999-total", "0003"))
_EDITION_FORMULAS: Final = (
    ("modelo-999-cuota", "0002"),
    ("modelo-999-recargo", "0004"),
    ("modelo-999-total", "0003"),
)


def _casillas(revision_id: str, rows: tuple[tuple[str, str], ...]) -> str:
    return "".join(
        f'[[revisions."{revision_id}".casillas]]\n'
        f'id = "{casilla_id}"\n'
        f'number = "{int(casilla_id)}"\n'
        'section = ["liquidacion"]\n'
        'data_type = "money"\n'
        f'continuidad_id = "{lineage}"\n'
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        f'source_refs = ["{_SOURCE_REF}"]\n\n'
        for casilla_id, lineage in rows
    )


def _formulas(revision_id: str, formulas: tuple[tuple[str, str], ...]) -> str:
    return "".join(
        f'[[revisions."{revision_id}".formulas]]\n'
        f'id = "{formula_id}"\n'
        f'target_casilla_id = "{target}"\n'
        'expression = { literal = "0" }\n'
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        f'source_refs = ["{_SOURCE_REF}"]\n\n'
        for formula_id, target in formulas
    )


def _write_revision(
    modelo_dir: Path,
    revision_id: str,
    *,
    year: int,
    casillas: str,
    formulas: str,
    manifest_extra: str = "",
) -> None:
    revision_dir = modelo_dir / "revisions" / revision_id
    (revision_dir / "casillas").mkdir(parents=True)
    (revision_dir / "formulas").mkdir()
    (revision_dir / "revision.toml").write_text(
        f'[revisions."{revision_id}"]\n'
        f"valid_from = {year}-01-01\n"
        f"valid_to = {year}-12-31\n"
        f'period_selector = {{ years = [{year}], periods = ["0A"] }}\n'
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        f'source_refs = ["{_SOURCE_REF}"]\n'
        f"{manifest_extra}",
        encoding="utf-8",
        newline="\n",
    )
    (revision_dir / "casillas" / "0001-declarations.toml").write_text(casillas, encoding="utf-8", newline="\n")
    (revision_dir / "formulas" / "0001-declarations.toml").write_text(formulas, encoding="utf-8", newline="\n")


def _build_modelo(
    modelos_dir: Path,
    *,
    edition_rows: tuple[tuple[str, str], ...] = _EDITION_ROWS,
    edition_formulas: tuple[tuple[str, str], ...] = _EDITION_FORMULAS,
    manifest_extra: str = "",
) -> Path:
    """A baseline edition and a later one storing its casillas and formulas against it.

    By default the later edition states every casilla and formula it holds, in
    its own record order, with the baseline's members restated verbatim: the
    shape an author leaves after adding a storage baseline beneath a full copy.
    """
    modelo_dir = modelos_dir / _MODELO_ID
    modelo_dir.mkdir(parents=True)
    write_standard_manifest(modelo_dir, "Declared order")
    _write_revision(
        modelo_dir,
        _BASELINE,
        year=2024,
        casillas=_casillas(_BASELINE, _BASELINE_ROWS),
        formulas=_formulas(_BASELINE, _BASELINE_FORMULAS),
    )
    _write_revision(
        modelo_dir,
        _EDITION,
        year=2025,
        casillas=_casillas(_EDITION, edition_rows),
        formulas=_formulas(_EDITION, edition_formulas),
        manifest_extra=(
            f'casilla_storage_baseline = "{_BASELINE}"\nfamily_storage_baseline = "{_BASELINE}"\n{manifest_extra}'
        ),
    )
    return modelo_dir


def _definition(modelo_dir: Path) -> ModeloDefinition:
    return load_modelo_directory(modelo_dir)


def _casilla_order(modelo_dir: Path, revision_id: str = _EDITION) -> list[str]:
    return [str(casilla.id) for casilla in _definition(modelo_dir).revisions[revision_id].casillas]


def _formula_order(modelo_dir: Path, revision_id: str = _EDITION) -> list[str]:
    return [str(formula.id) for formula in _definition(modelo_dir).revisions[revision_id].formulas]


def _stated_casilla_order() -> list[str]:
    return [casilla_id for casilla_id, _lineage in _EDITION_ROWS]


def _stated_formula_order() -> list[str]:
    return [formula_id for formula_id, _target in _EDITION_FORMULAS]


def _declared_copy(modelo_dir: Path, destination: Path) -> tuple[Path, tuple[OrderRestoration, ...]]:
    restorations = declared_order_restorations(modelo_dir)
    declared_dir = shutil.copytree(modelo_dir, destination / _MODELO_ID)
    _write_order_restorations(declared_dir, restorations)
    return declared_dir, restorations


def _stage_migration(planned_from: Path, staged_root: Path) -> Path:
    """Plan the modelo and write the casilla delta and the family collapse into a copy of its tree."""
    _plan_result, works = _plan(planned_from, _definition(planned_from))
    staged_dir = shutil.copytree(planned_from, staged_root / _MODELO_ID)
    for work in works:
        _write_edition(staged_dir / "revisions" / work.plan.revision_id, work)
    collapse_keyed_families(planned_from, staged_dir)
    return staged_dir


def _prove(reference_dir: Path, staged_dir: Path) -> RoundTripReport:
    return _prove_chain(
        reference_modelo_dir=reference_dir,
        staged_modelo_dir=staged_dir,
        revision_ids=(_BASELINE, _EDITION),
        report=_CLEAN_REPORT,
    )


def test_the_merge_moves_a_complete_statements_new_members_to_the_end(tmp_path: Path) -> None:
    """The precondition the restoration answers: the merge, not the statement, decides the live order."""
    modelo_dir = _build_modelo(tmp_path)
    stated_new = {casilla_id for casilla_id, _ in _EDITION_ROWS} - {casilla_id for casilla_id, _ in _BASELINE_ROWS}

    live = _casilla_order(modelo_dir)

    assert live != _stated_casilla_order()
    assert set(live[-len(stated_new) :]) == stated_new
    assert _formula_order(modelo_dir) != _stated_formula_order()


def test_accepted_source_order_drift_refuses_apply_before_staging(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    reference = _build_modelo(tmp_path / "accepted")
    root = tmp_path / "candidate" / "registry" / "aeat"
    candidate = shutil.copytree(reference, root / "modelos" / _MODELO_ID)
    fragment = candidate / "revisions" / _BASELINE / "casillas" / "0001-declarations.toml"
    fragment.write_text(_casillas(_BASELINE, tuple(reversed(_BASELINE_ROWS))), encoding="utf-8")
    before = fragment.read_bytes()
    work = tmp_path / "migration-work"

    result = main(
        [
            "--registry-root",
            str(root),
            "--modelo",
            _MODELO_ID,
            "--work-dir",
            str(work),
            "--accepted-modelo-dir",
            str(reference),
            "--apply",
        ]
    )

    assert result == 1
    assert "accepted-source order review refused: drift" in capsys.readouterr().err
    assert not work.exists()
    assert fragment.read_bytes() == before


def test_casilla_rename_requires_an_accepted_source_snapshot(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as refusal:
        main(
            [
                "--registry-root",
                str(tmp_path),
                "--modelo",
                _MODELO_ID,
                "--work-dir",
                str(tmp_path / "work"),
                "--rename-casilla",
                "0001=DP:0001",
            ]
        )

    assert refusal.value.code == 2
    assert "--rename-casilla requires --accepted-modelo-dir" in capsys.readouterr().err
    assert not (tmp_path / "work").exists()


def test_a_complete_statement_over_a_baseline_is_restored_to_its_stated_order(tmp_path: Path) -> None:
    modelo_dir = _build_modelo(tmp_path / "input")

    declared_dir, restorations = _declared_copy(modelo_dir, tmp_path / "declared")

    assert {(item.revision_id, item.family) for item in restorations} == {
        (_EDITION, "casillas"),
        (_EDITION, "formulas"),
    }
    # One new member each, so one move each is the fewest that restore the order.
    assert all(len(item.moves) == 1 for item in restorations)
    assert _casilla_order(declared_dir) == _stated_casilla_order()
    assert _formula_order(declared_dir) == _stated_formula_order()
    assert set(
        _prove_order_restoration(
            reference_modelo_dir=modelo_dir, declared_modelo_dir=declared_dir, restorations=restorations
        )
    ) == {(_EDITION, "casillas"), (_EDITION, "formulas")}
    assert declared_order_restorations(declared_dir) == ()


def test_the_migration_keeps_the_declared_order_and_proves_it(tmp_path: Path) -> None:
    """The normal path: planned from the declared order, the delta states only the new member and keeps its place."""
    modelo_dir = _build_modelo(tmp_path / "input")
    declared_dir, _restorations = _declared_copy(modelo_dir, tmp_path / "declared")

    staged_dir = _stage_migration(declared_dir, tmp_path / "staged")

    assert _prove(declared_dir, staged_dir) == _CLEAN_REPORT
    revisions = load_modelo_directory(staged_dir).revisions
    assert [str(casilla.id) for casilla in revisions[_EDITION].casillas] == _stated_casilla_order()
    assert [str(formula.id) for formula in revisions[_EDITION].formulas] == _stated_formula_order()
    stated = (staged_dir / "revisions" / _EDITION / "casillas" / "0001-declarations.toml").read_text(encoding="utf-8")
    assert stated.count("[[revisions.") == 1
    assert 'id = "0004"' in stated


def test_a_stated_row_landing_out_of_order_over_its_baseline_fails_the_proof(tmp_path: Path) -> None:
    """Detector: a delta planned from the merge order drops the new row's place, and the order-aware proof refuses."""
    modelo_dir = _build_modelo(tmp_path / "input")
    declared_dir, _restorations = _declared_copy(modelo_dir, tmp_path / "declared")

    staged_dir = _stage_migration(modelo_dir, tmp_path / "staged")

    assert _casilla_order(staged_dir) != _stated_casilla_order()
    with pytest.raises(RegistryError, match=r"lifting changed the casillas members.*first difference at position 1"):
        _prove(declared_dir, staged_dir)


def test_a_partial_statement_keeps_the_order_the_merge_gives(tmp_path: Path) -> None:
    """A delta stating only its new row means the merge's order; nothing is restored."""
    modelo_dir = _build_modelo(
        tmp_path,
        edition_rows=(("0004", "recargo"),),
        edition_formulas=(("modelo-999-recargo", "0004"),),
    )

    assert declared_order_restorations(modelo_dir) == ()


def test_a_complete_statement_that_also_declares_positions_is_refused(tmp_path: Path) -> None:
    """The statement and its positions disagree about the order, so neither is taken."""
    modelo_dir = _build_modelo(
        tmp_path,
        manifest_extra=f'\n[[revisions."{_EDITION}".casilla_positions]]\nid = "0003"\nposition = 0\n',
    )

    with pytest.raises(RegistryError, match="statement and the positions disagree"):
        declared_order_restorations(modelo_dir)


def test_a_restoration_that_changes_a_member_is_refused(tmp_path: Path) -> None:
    """Restoring order may move members only; a changed field fails the restoration proof."""
    modelo_dir = _build_modelo(tmp_path / "input")
    declared_dir, restorations = _declared_copy(modelo_dir, tmp_path / "declared")
    fragment = declared_dir / "revisions" / _EDITION / "casillas" / "0001-declarations.toml"
    text = fragment.read_text(encoding="utf-8")
    fragment.write_text(text.replace('number = "4"', 'number = "44"'), encoding="utf-8", newline="\n")

    with pytest.raises(RegistryError, match="changed more than the order of its members"):
        _prove_order_restoration(
            reference_modelo_dir=modelo_dir, declared_modelo_dir=declared_dir, restorations=restorations
        )


def test_an_applied_migration_restores_the_order_and_a_rerun_changes_nothing(tmp_path: Path) -> None:
    """End to end through the command's entry point, over a registry root carrying the shared catalogues."""
    registry_root = copy_registry_tree(
        Path(bundled_path("registry", "aeat")), tmp_path / "registry" / "aeat", modelo_id="194"
    )
    modelo_dir = _build_modelo(registry_root / "modelos")

    outcome = migrate_modelo(registry_root=registry_root, modelo_id=_MODELO_ID, work_dir=tmp_path / "work", apply=True)

    assert outcome.applied
    assert outcome.equivalence_status == "passed"
    assert {(item.revision_id, item.family) for item in outcome.order_restorations} == {
        (_EDITION, "casillas"),
        (_EDITION, "formulas"),
    }
    assert _casilla_order(modelo_dir) == _stated_casilla_order()
    assert _formula_order(modelo_dir) == _stated_formula_order()

    rerun = migrate_modelo(registry_root=registry_root, modelo_id=_MODELO_ID, work_dir=tmp_path / "rerun")

    assert rerun.order_restorations == ()
    assert not rerun.changed
