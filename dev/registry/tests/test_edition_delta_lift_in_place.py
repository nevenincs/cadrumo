"""Lifting a delta-authored modelo in place, and the identity proof that guards it.

A modelo whose editions already name predecessors has no full copy left to
prove a rewrite against, so the migration admits exactly one operation on it:
lifting restatement where it stands. Every stated member stays stated, in the
order it was authored, no predecessor or review stamp is written, and the only
changes are a row dropping a reference the manifest default already supplies
and a manifest declaring a default it derives. The proof is identity: the
staged edition must hold the same members in the same order and materialise to
the same bytes as the edition it was planned from.

Every test drives the real planner, writer and chain proof over a synthetic
on-disk modelo built in ``tmp_path``, with nothing mocked and no production
registry corpus read. The tree is deliberately small and its authored order is
deliberately not its materialised order, so a lift that silently adopted the
merge order would fail rather than pass. Each refusal is asserted on its whole
message, and each is paired with the unplanted tree proving clean, so no test
can pass because the proof never ran.

The planner, writer and chain proof are reached directly rather than through
``migrate_modelo``, which copies a whole registry tree and therefore needs the
shared legal catalogues a single synthetic modelo does not carry.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Final

import pytest

from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from ..compiler.loader import load_modelo_directory
from ..conformance.loader_directory_mode_support import write_standard_manifest
from ..edition_delta_migration import (
    MigrationRefusedError,
    PredecessorBasis,
    _edition_changes,
    _plan,
    _prove_chain,
    _write_edition,
    plan_migration,
)
from ..edition_round_trip import RoundTripReport

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO_ID: Final = "999"
_LEGAL_REF: Final = "ley-58-2003:art-29"
_SOURCE_REF: Final = "aeat-manual"
_PREDECESSOR: Final = "2024"
_SUCCESSOR: Final = "2025"
_SUCCESSOR_FRAGMENT: Final = "c0005__c0002.toml"
_FORMULA_FRAGMENT: Final = "0001-formulas.toml"
_CLEAN_REPORT: Final = RoundTripReport(findings=(), byte_compared_revisions=())
#: The successor states the new row before the row it supersedes, which is the
#: reverse of the order materialisation gives them. A lift that reordered its
#: members to the merge order would therefore be visible.
_AUTHORED_ORDER: Final = ("0005", "0002")
_MATERIALISED_ORDER: Final = ("0001", "0002", "0003", "0005")


def _casilla(revision_id: str, casilla_id: str, *, number: str, lineage: str) -> str:
    return (
        f'[[revisions."{revision_id}".casillas]]\n'
        f'id = "{casilla_id}"\n'
        f'number = "{number}"\n'
        'section = ["liquidacion"]\n'
        'data_type = "money"\n'
        f'continuidad_id = "{lineage}"\n'
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        f'source_refs = ["{_SOURCE_REF}"]\n\n'
    )


def _formula(revision_id: str, formula_id: str, *, target: str) -> str:
    return (
        f'[[revisions."{revision_id}".formulas]]\n'
        f'id = "{formula_id}"\n'
        f'target_casilla_id = "{target}"\n'
        'expression = { literal = "0" }\n'
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        f'source_refs = ["{_SOURCE_REF}"]\n\n'
    )


def _write_revision(
    modelo_dir: Path,
    revision_id: str,
    *,
    year: int,
    casilla_fragments: dict[str, str],
    formulas: str,
    predecessor: str | None = None,
) -> None:
    revision_dir = modelo_dir / "revisions" / revision_id
    revision_dir.mkdir(parents=True)
    predecessor_line = f'predecessor = "{predecessor}"\n' if predecessor is not None else ""
    (revision_dir / "revision.toml").write_text(
        f'[revisions."{revision_id}"]\n'
        f"valid_from = {year}-01-01\n"
        f"valid_to = {year}-12-31\n"
        f'period_selector = {{ years = [{year}], periods = ["0A"] }}\n'
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        f'source_refs = ["{_SOURCE_REF}"]\n'
        f"{predecessor_line}",
        encoding="utf-8",
        newline="\n",
    )
    (revision_dir / "casillas").mkdir()
    for name, text in casilla_fragments.items():
        (revision_dir / "casillas" / name).write_text(text, encoding="utf-8", newline="\n")
    (revision_dir / "formulas").mkdir()
    (revision_dir / "formulas" / _FORMULA_FRAGMENT).write_text(formulas, encoding="utf-8", newline="\n")


def _successor_formulas() -> str:
    return _formula(_SUCCESSOR, "modelo-999-2025-cuota", target="0002") + _formula(
        _SUCCESSOR, "modelo-999-2025-total", target="0003"
    )


def _delta_successor_fragments() -> dict[str, str]:
    """The delta shape: the new row is stated before the row it supersedes, and nothing else."""
    return {
        _SUCCESSOR_FRAGMENT: _casilla(_SUCCESSOR, "0005", number="5", lineage="recargo")
        + _casilla(_SUCCESSOR, "0002", number="22", lineage="cuota"),
    }


def _full_copy_successor_fragments() -> dict[str, str]:
    """The same edition stated in full: the two inheritable rows restated verbatim from 2024."""
    return {
        "c0001__c0003.toml": _casilla(_SUCCESSOR, "0001", number="1", lineage="base")
        + _casilla(_SUCCESSOR, "0002", number="22", lineage="cuota")
        + _casilla(_SUCCESSOR, "0003", number="3", lineage="deduccion"),
        "c0005.toml": _casilla(_SUCCESSOR, "0005", number="5", lineage="recargo"),
    }


def _build_modelo(root: Path, *, names_predecessor: bool) -> Path:
    """A two-edition modelo whose rows all restate one shared ``source_refs`` run.

    The 2025 edition holds one new row, one row superseding its predecessor's,
    and two rows identical to the predecessor's. ``names_predecessor`` chooses
    the shape it is authored in: a delta naming 2024 and stating only the first
    two, or the full copy of the same four rows naming nothing.
    """
    modelo_dir = root / _MODELO_ID
    modelo_dir.mkdir(parents=True)
    write_standard_manifest(modelo_dir, "Test")
    _write_revision(
        modelo_dir,
        _PREDECESSOR,
        year=2024,
        casilla_fragments={
            "c0001__c0002.toml": _casilla(_PREDECESSOR, "0001", number="1", lineage="base")
            + _casilla(_PREDECESSOR, "0002", number="2", lineage="cuota"),
            "c0003.toml": _casilla(_PREDECESSOR, "0003", number="3", lineage="deduccion"),
        },
        formulas=_formula(_PREDECESSOR, "modelo-999-2024-cuota", target="0002")
        + _formula(_PREDECESSOR, "modelo-999-2024-total", target="0003"),
    )
    _write_revision(
        modelo_dir,
        _SUCCESSOR,
        year=2025,
        predecessor=_PREDECESSOR if names_predecessor else None,
        casilla_fragments=_delta_successor_fragments() if names_predecessor else _full_copy_successor_fragments(),
        formulas=_successor_formulas(),
    )
    return modelo_dir


def _definition(modelo_dir: Path) -> ModeloDefinition:
    return load_modelo_directory(modelo_dir)


def _materialised_ids(modelo_dir: Path, revision_id: str) -> tuple[str, ...]:
    return tuple(str(casilla.id) for casilla in _definition(modelo_dir).revisions[revision_id].casillas)


def _materialised_formula_ids(modelo_dir: Path, revision_id: str) -> tuple[str, ...]:
    return tuple(str(formula.id) for formula in _definition(modelo_dir).revisions[revision_id].formulas)


def _stage_lift(reference_dir: Path, staged_root: Path) -> Path:
    """Plan the delta-authored modelo and write the lift into a copy of its tree."""
    _plan_result, works = _plan(reference_dir, _definition(reference_dir), declare_blocked_roots=False)
    staged_dir = shutil.copytree(reference_dir, staged_root / _MODELO_ID)
    for work in works:
        _write_edition(staged_dir / "revisions" / work.plan.revision_id, work)
    return staged_dir


def _prove(reference_dir: Path, staged_dir: Path) -> RoundTripReport:
    return _prove_chain(
        reference_modelo_dir=reference_dir,
        staged_modelo_dir=staged_dir,
        revision_ids=(_PREDECESSOR, _SUCCESSOR),
        report=_CLEAN_REPORT,
    )


def _copy_of(reference_dir: Path, destination: Path) -> Path:
    return shutil.copytree(reference_dir, destination / _MODELO_ID)


def test_a_lift_in_place_keeps_every_stated_member_in_its_authored_order(tmp_path: Path) -> None:
    """Nothing is inherited, reordered or newly declared beyond the defaults the lift derives."""
    modelo_dir = _build_modelo(tmp_path / "input", names_predecessor=True)
    assert _materialised_ids(modelo_dir, _SUCCESSOR) == _MATERIALISED_ORDER

    plan, works = _plan(modelo_dir, _definition(modelo_dir), declare_blocked_roots=False)

    assert plan.already_delta_authored
    assert [edition.basis for edition in plan.editions] == [PredecessorBasis.LIFT_ONLY] * 2
    predecessor, successor = plan.editions
    # The successor keeps the members it authored, in the order it authored
    # them, which is not the order its materialisation gives them.
    assert successor.stated_ids == _AUTHORED_ORDER
    assert successor.stated_ids != tuple(row_id for row_id in _MATERIALISED_ORDER if row_id in set(_AUTHORED_ORDER))
    assert successor.inherited_ids == ("0001", "0003")
    assert predecessor.stated_ids == ("0001", "0002", "0003")
    assert predecessor.inherited_ids == ()
    # Inheritance, review stamps and root declarations are left as authored.
    assert (predecessor.predecessor, successor.predecessor) == (None, _PREDECESSOR)
    assert [edition.reviewed_against for edition in plan.editions] == [None, None]
    assert [edition.blocked for edition in plan.editions] == [(), ()]
    assert [edition.kept for edition in plan.editions] == [{}, {}]
    assert [work.root_declaration for work in works] == [None, None]
    # The lift itself: every row restates the shared run, so every stated row
    # drops it, and the families whose default derives are declared.
    assert [edition.source_default for edition in plan.editions] == [(_SOURCE_REF,), (_SOURCE_REF,)]
    assert [edition.source_default_withheld for edition in plan.editions] == [None, None]
    assert (predecessor.lifted.row_source_refs, successor.lifted.row_source_refs) == (3, 2)
    assert [dict(work.source.family_defaults) for work in works] == [
        {"formula_source_refs": (_SOURCE_REF,)},
        {"formula_source_refs": (_SOURCE_REF,)},
    ]


def test_a_written_lift_proves_identical_and_a_rerun_changes_nothing(tmp_path: Path) -> None:
    """The staged tree materialises to the reference's bytes, and re-planning it is a fixed point."""
    reference_dir = _build_modelo(tmp_path / "input", names_predecessor=True)
    staged_dir = _stage_lift(reference_dir, tmp_path / "staged")

    manifest = (staged_dir / "revisions" / _SUCCESSOR / "revision.toml").read_text(encoding="utf-8")
    fragment = (staged_dir / "revisions" / _SUCCESSOR / "casillas" / _SUCCESSOR_FRAGMENT).read_text(encoding="utf-8")
    assert f'casilla_source_refs = ["{_SOURCE_REF}"]\n' in manifest
    assert f'formula_source_refs = ["{_SOURCE_REF}"]\n' in manifest
    assert 'predecessor = "2024"\n' in manifest
    assert "reviewed_against" not in manifest
    assert "source_refs" not in fragment
    assert fragment.index('id = "0005"') < fragment.index('id = "0002"')

    assert _prove(reference_dir, staged_dir) == _CLEAN_REPORT
    assert _materialised_ids(staged_dir, _SUCCESSOR) == _MATERIALISED_ORDER

    plan, works = _plan(staged_dir, _definition(staged_dir), declare_blocked_roots=False)

    assert plan.already_delta_authored
    assert [edition.stated_ids for edition in plan.editions] == [("0001", "0002", "0003"), _AUTHORED_ORDER]
    assert [edition.lifted.total() for edition in plan.editions] == [0, 0]
    assert [_edition_changes(work) for work in works] == [False, False]


def test_a_lift_that_dropped_a_casilla_member_is_refused(tmp_path: Path) -> None:
    """Losing the successor's last member is reported by position, on the side that still holds it."""
    reference_dir = _build_modelo(tmp_path / "input", names_predecessor=True)
    staged_dir = _copy_of(reference_dir, tmp_path / "staged")
    assert _prove(reference_dir, staged_dir) == _CLEAN_REPORT

    fragment = staged_dir / "revisions" / _SUCCESSOR / "casillas" / _SUCCESSOR_FRAGMENT
    dropped = _casilla(_SUCCESSOR, "0005", number="5", lineage="recargo")
    text = fragment.read_text(encoding="utf-8")
    assert dropped in text
    fragment.write_text(text.replace(dropped, ""), encoding="utf-8", newline="\n")

    with pytest.raises(MigrationRefusedError) as refusal:
        _prove(reference_dir, staged_dir)

    assert str(refusal.value) == (
        f"edition '{_SUCCESSOR}': lifting changed the casillas members, which a lift may never do: "
        "4 before, 3 after, first difference at position 3: ['0005|recargo'] on the reference side only"
    )


def test_a_lift_that_reordered_a_reference_family_is_refused(tmp_path: Path) -> None:
    """Member identity is compared for every reference family, not for casillas alone."""
    reference_dir = _build_modelo(tmp_path / "input", names_predecessor=True)
    staged_dir = _copy_of(reference_dir, tmp_path / "staged")

    assert _prove(reference_dir, staged_dir) == _CLEAN_REPORT

    formulas = staged_dir / "revisions" / _SUCCESSOR / "formulas" / _FORMULA_FRAGMENT
    cuota = _formula(_SUCCESSOR, "modelo-999-2025-cuota", target="0002")
    total = _formula(_SUCCESSOR, "modelo-999-2025-total", target="0003")
    assert formulas.read_text(encoding="utf-8") == cuota + total
    # The successor's chain carries its predecessor's two formulas ahead of its
    # own two, so the swap first shows at position two.
    assert _materialised_formula_ids(reference_dir, _SUCCESSOR) == (
        "modelo-999-2024-cuota",
        "modelo-999-2024-total",
        "modelo-999-2025-cuota",
        "modelo-999-2025-total",
    )
    formulas.write_text(total + cuota, encoding="utf-8", newline="\n")

    with pytest.raises(MigrationRefusedError) as refusal:
        _prove(reference_dir, staged_dir)

    assert str(refusal.value) == (
        f"edition '{_SUCCESSOR}': lifting changed the formulas members, which a lift may never do: "
        "4 before, 4 after, first difference at position 2: 'modelo-999-2025-cuota' became "
        "'modelo-999-2025-total'"
    )


def test_a_staged_tree_whose_content_changed_fails_the_byte_identity_proof(tmp_path: Path) -> None:
    """Every member keeps its identity, so only the materialised bytes can catch the change."""
    reference_dir = _build_modelo(tmp_path / "input", names_predecessor=True)
    staged_dir = _copy_of(reference_dir, tmp_path / "staged")

    assert _prove(reference_dir, staged_dir) == _CLEAN_REPORT

    fragment = staged_dir / "revisions" / _SUCCESSOR / "casillas" / _SUCCESSOR_FRAGMENT
    text = fragment.read_text(encoding="utf-8")
    assert 'number = "22"' in text
    fragment.write_text(text.replace('number = "22"', 'number = "222"'), encoding="utf-8", newline="\n")
    assert _materialised_ids(staged_dir, _SUCCESSOR) == _MATERIALISED_ORDER

    with pytest.raises(MigrationRefusedError) as refusal:
        _prove(reference_dir, staged_dir)

    assert str(refusal.value) == (
        f"edition '{_SUCCESSOR}': the staged tree materialises to different bytes than the tree it was "
        "planned from, so the lift is not an identity and cannot be proven"
    )


def test_a_modelo_naming_no_predecessor_still_plans_through_the_full_copy_path(tmp_path: Path) -> None:
    """The same declarations without the predecessor key take the original branch and its bases."""
    modelo_dir = _build_modelo(tmp_path / "input", names_predecessor=False)

    plan = plan_migration(modelo_dir, _definition(modelo_dir))

    assert not plan.already_delta_authored
    predecessor, successor = plan.editions
    assert (predecessor.basis, predecessor.predecessor) == (PredecessorBasis.FIRST, None)
    assert (successor.basis, successor.predecessor) == (PredecessorBasis.ADJACENT, _PREDECESSOR)
    assert successor.is_delta
    # The full-copy path drops the rows the successor may inherit and states the
    # rest in materialised order, where the lift path states what was authored.
    assert successor.inherited_ids == ("0001", "0003")
    assert successor.stated_ids == ("0002", "0005")
    assert successor.stated_ids != _AUTHORED_ORDER
