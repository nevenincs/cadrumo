"""Completing a partially delta-authored modelo and proving its identity.

A modelo whose editions already name predecessors may still state redundant
or changed complete members. The migration keeps genuine additions, converts
changed predecessor members to precise storage overrides, and lifts shared
defaults. The proof is identity: the staged edition must hold the same members
in the same order and materialise to the same bytes as the edition it was
planned from.

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

import dataclasses
import datetime
import shutil
from pathlib import Path
from typing import Final

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryError
from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from ..compiler.loader import load_modelo_directory
from ..conformance.loader_directory_mode_support import write_standard_manifest
from ..edition_delta_chain_materialisation import chain_materialisation
from ..edition_delta_equivalence import member_difference, prove_chain
from ..edition_delta_planning import edition_delta_planning_plan, plan_migration
from ..edition_delta_source import read_edition
from ..edition_delta_types import PredecessorBasis
from ..edition_delta_writer import (
    edition_changes,
    write_edition,
)
from ..edition_round_trip import RoundTripReport
from .synthetic_delta_edition_support import (
    LEGAL_REF,
    MODELO_ID,
    PREDECESSOR_EDITION,
    SOURCE_REF,
    SUCCESSOR_EDITION,
    delta_casilla,
    delta_formula,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SUCCESSOR_FRAGMENT: Final = "c0005__c0002.toml"
_FORMULA_FRAGMENT: Final = "0001-formulas.toml"
_CLEAN_REPORT: Final = RoundTripReport(findings=(), byte_compared_revisions=())
#: The successor states the new row before the row it supersedes, which is the
#: reverse of the order materialisation gives them. A lift that reordered its
#: members to the merge order would therefore be visible.
_AUTHORED_ORDER: Final = ("0005", "0002")
_MATERIALISED_ORDER: Final = ("0001", "0002", "0003", "0005")


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
        f'legal_refs = ["{LEGAL_REF}"]\n'
        f'source_refs = ["{SOURCE_REF}"]\n'
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
    return delta_formula(SUCCESSOR_EDITION, f"modelo-999-{SUCCESSOR_EDITION}-cuota", target="0002") + delta_formula(
        SUCCESSOR_EDITION, f"modelo-999-{SUCCESSOR_EDITION}-total", target="0003"
    )


def _delta_successor_fragments() -> dict[str, str]:
    """The delta shape: the new row is stated before the row it supersedes, and nothing else."""
    return {
        _SUCCESSOR_FRAGMENT: delta_casilla(SUCCESSOR_EDITION, "0005", number="5", lineage="recargo")
        + delta_casilla(SUCCESSOR_EDITION, "0002", number="22", lineage="cuota"),
    }


def _full_copy_successor_fragments() -> dict[str, str]:
    """The same edition stated in full: the two inheritable rows restated verbatim from the predecessor."""
    return {
        "c0001__c0003.toml": delta_casilla(SUCCESSOR_EDITION, "0001", number="1", lineage="base")
        + delta_casilla(SUCCESSOR_EDITION, "0002", number="22", lineage="cuota")
        + delta_casilla(SUCCESSOR_EDITION, "0003", number="3", lineage="deduccion"),
        "c0005.toml": delta_casilla(SUCCESSOR_EDITION, "0005", number="5", lineage="recargo"),
    }


def _build_modelo(root: Path, *, names_predecessor: bool) -> Path:
    """A two-edition modelo whose rows all restate one shared ``source_refs`` run.

    The successor edition holds one new row, one row superseding its predecessor's,
    and two rows identical to the predecessor's. ``names_predecessor`` chooses
    the shape it is authored in: a delta naming the predecessor and stating only the first
    two, or the full copy of the same four rows naming nothing.
    """
    modelo_dir = root / MODELO_ID
    modelo_dir.mkdir(parents=True)
    write_standard_manifest(modelo_dir, "Test")
    _write_revision(
        modelo_dir,
        PREDECESSOR_EDITION,
        year=int(PREDECESSOR_EDITION),
        casilla_fragments={
            "c0001__c0002.toml": delta_casilla(PREDECESSOR_EDITION, "0001", number="1", lineage="base")
            + delta_casilla(PREDECESSOR_EDITION, "0002", number="2", lineage="cuota"),
            "c0003.toml": delta_casilla(PREDECESSOR_EDITION, "0003", number="3", lineage="deduccion"),
        },
        formulas=delta_formula(PREDECESSOR_EDITION, f"modelo-999-{PREDECESSOR_EDITION}-cuota", target="0002")
        + delta_formula(PREDECESSOR_EDITION, f"modelo-999-{PREDECESSOR_EDITION}-total", target="0003"),
    )
    _write_revision(
        modelo_dir,
        SUCCESSOR_EDITION,
        year=int(SUCCESSOR_EDITION),
        predecessor=PREDECESSOR_EDITION if names_predecessor else None,
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
    _plan_result, works = edition_delta_planning_plan(reference_dir, _definition(reference_dir))
    staged_dir = shutil.copytree(reference_dir, staged_root / MODELO_ID)
    for work in works:
        write_edition(staged_dir / "revisions" / work.plan.revision_id, work)
    return staged_dir


def _prove(reference_dir: Path, staged_dir: Path) -> RoundTripReport:
    return prove_chain(
        reference_modelo_dir=reference_dir,
        staged_modelo_dir=staged_dir,
        revision_ids=(PREDECESSOR_EDITION, SUCCESSOR_EDITION),
        report=_CLEAN_REPORT,
    )


def _copy_of(reference_dir: Path, destination: Path) -> Path:
    return shutil.copytree(reference_dir, destination / MODELO_ID)


def test_an_existing_delta_finishes_changed_members_as_storage_overrides(tmp_path: Path) -> None:
    """A predecessor declaration does not make remaining full member statements final."""
    modelo_dir = _build_modelo(tmp_path / "input", names_predecessor=True)
    assert _materialised_ids(modelo_dir, SUCCESSOR_EDITION) == _MATERIALISED_ORDER

    plan, works = edition_delta_planning_plan(modelo_dir, _definition(modelo_dir))

    assert plan.already_delta_authored
    assert [edition.basis for edition in plan.editions] == [PredecessorBasis.FIRST, PredecessorBasis.LIFT_ONLY]
    predecessor, successor = plan.editions
    # The genuinely new row remains authored. The changed predecessor member
    # becomes one precise storage override instead of remaining a full row.
    assert successor.stated_ids == ("0005",)
    assert successor.inherited_ids == ("0001", "0002", "0003")
    assert successor.casilla_overrides == (
        {
            "selector": {"revision": PREDECESSOR_EDITION, "id": "0002"},
            "fields": {"number": "22"},
            "removed_fields": [],
        },
    )
    assert predecessor.stated_ids == ("0001", "0002", "0003")
    assert predecessor.inherited_ids == ()
    # Inheritance, review stamps and root declarations are left as authored.
    assert (predecessor.predecessor, successor.predecessor) == (None, PREDECESSOR_EDITION)
    assert [edition.reviewed_against for edition in plan.editions] == [None, None]
    assert [edition.blocked for edition in plan.editions] == [(), ()]
    assert predecessor.kept == {}
    assert successor.kept == {"new_lineage": 1}
    assert [work.root_declaration for work in works] == [None, None]
    # The lift itself: every row restates the shared run, so every stated row
    # drops it, and the families whose default derives are declared.
    assert [edition.source_default for edition in plan.editions] == [(SOURCE_REF,), (SOURCE_REF,)]
    assert [edition.source_default_withheld for edition in plan.editions] == [None, None]
    assert (predecessor.lifted.row_source_refs, successor.lifted.row_source_refs) == (3, 1)
    assert [dict(work.source.family_defaults) for work in works] == [
        {"formula_source_refs": (SOURCE_REF,)},
        {"formula_source_refs": (SOURCE_REF,)},
    ]


def test_a_written_lift_proves_identical_and_a_rerun_changes_nothing(tmp_path: Path) -> None:
    """The staged tree materialises to the reference's bytes, and re-planning it is a fixed point."""
    reference_dir = _build_modelo(tmp_path / "input", names_predecessor=True)
    staged_dir = _stage_lift(reference_dir, tmp_path / "staged")

    manifest = (staged_dir / "revisions" / SUCCESSOR_EDITION / "revision.toml").read_text(encoding="utf-8")
    fragment = (staged_dir / "revisions" / SUCCESSOR_EDITION / "casillas" / _SUCCESSOR_FRAGMENT).read_text(
        encoding="utf-8"
    )
    assert f'casilla_source_refs = ["{SOURCE_REF}"]\n' in manifest
    assert f'formula_source_refs = ["{SOURCE_REF}"]\n' in manifest
    assert f'predecessor = "{PREDECESSOR_EDITION}"\n' in manifest
    assert "reviewed_against" not in manifest
    assert "source_refs" not in fragment
    assert 'id = "0005"' in fragment
    assert 'id = "0002"' not in fragment
    assert f'selector = {{ revision = "{PREDECESSOR_EDITION}", id = "0002" }}' in manifest
    assert 'fields = { number = "22" }' in manifest

    assert _prove(reference_dir, staged_dir) == _CLEAN_REPORT
    assert _materialised_ids(staged_dir, SUCCESSOR_EDITION) == _MATERIALISED_ORDER

    plan, works = edition_delta_planning_plan(staged_dir, _definition(staged_dir))

    assert plan.already_delta_authored
    assert [edition.stated_ids for edition in plan.editions] == [("0001", "0002", "0003"), ("0005",)]
    assert [edition.lifted.total() for edition in plan.editions] == [0, 0]
    assert [edition_changes(work) for work in works] == [False, False]


def test_a_lift_that_dropped_a_casilla_member_is_refused(tmp_path: Path) -> None:
    """Losing the successor's last member is reported by position, on the side that still holds it."""
    reference_dir = _build_modelo(tmp_path / "input", names_predecessor=True)
    staged_dir = _copy_of(reference_dir, tmp_path / "staged")
    assert _prove(reference_dir, staged_dir) == _CLEAN_REPORT

    fragment = staged_dir / "revisions" / SUCCESSOR_EDITION / "casillas" / _SUCCESSOR_FRAGMENT
    dropped = delta_casilla(SUCCESSOR_EDITION, "0005", number="5", lineage="recargo")
    text = fragment.read_text(encoding="utf-8")
    assert dropped in text
    fragment.write_text(text.replace(dropped, ""), encoding="utf-8", newline="\n")

    with pytest.raises(RegistryError) as refusal:
        _prove(reference_dir, staged_dir)

    assert str(refusal.value) == (
        f"edition '{SUCCESSOR_EDITION}': lifting changed the casillas members, which a lift may never do: "
        "4 before, 3 after, first difference at position 3: ['0005|recargo'] on the reference side only"
    )


def test_a_lift_that_reordered_a_reference_family_is_refused(tmp_path: Path) -> None:
    """Member identity is compared for every reference family, not for casillas alone."""
    reference_dir = _build_modelo(tmp_path / "input", names_predecessor=True)
    staged_dir = _copy_of(reference_dir, tmp_path / "staged")

    assert _prove(reference_dir, staged_dir) == _CLEAN_REPORT

    formulas = staged_dir / "revisions" / SUCCESSOR_EDITION / "formulas" / _FORMULA_FRAGMENT
    cuota = delta_formula(SUCCESSOR_EDITION, f"modelo-999-{SUCCESSOR_EDITION}-cuota", target="0002")
    total = delta_formula(SUCCESSOR_EDITION, f"modelo-999-{SUCCESSOR_EDITION}-total", target="0003")
    assert formulas.read_text(encoding="utf-8") == cuota + total
    # The successor's chain carries its predecessor's two formulas ahead of its
    # own two, so the swap first shows at position two.
    assert _materialised_formula_ids(reference_dir, SUCCESSOR_EDITION) == (
        f"modelo-999-{PREDECESSOR_EDITION}-cuota",
        f"modelo-999-{PREDECESSOR_EDITION}-total",
        f"modelo-999-{SUCCESSOR_EDITION}-cuota",
        f"modelo-999-{SUCCESSOR_EDITION}-total",
    )
    formulas.write_text(total + cuota, encoding="utf-8", newline="\n")

    with pytest.raises(RegistryError) as refusal:
        _prove(reference_dir, staged_dir)

    assert str(refusal.value) == (
        f"edition '{SUCCESSOR_EDITION}': lifting changed the formulas members, which a lift may never do: "
        f"4 before, 4 after, first difference at position 2: 'modelo-999-{SUCCESSOR_EDITION}-cuota' became "
        f"'modelo-999-{SUCCESSOR_EDITION}-total'"
    )


def test_a_staged_tree_whose_content_changed_fails_the_byte_identity_proof(tmp_path: Path) -> None:
    """Every member keeps its identity, so only the materialised bytes can catch the change."""
    reference_dir = _build_modelo(tmp_path / "input", names_predecessor=True)
    staged_dir = _copy_of(reference_dir, tmp_path / "staged")

    assert _prove(reference_dir, staged_dir) == _CLEAN_REPORT

    fragment = staged_dir / "revisions" / SUCCESSOR_EDITION / "casillas" / _SUCCESSOR_FRAGMENT
    text = fragment.read_text(encoding="utf-8")
    assert 'number = "22"' in text
    fragment.write_text(text.replace('number = "22"', 'number = "222"'), encoding="utf-8", newline="\n")
    assert _materialised_ids(staged_dir, SUCCESSOR_EDITION) == _MATERIALISED_ORDER

    with pytest.raises(RegistryError) as refusal:
        _prove(reference_dir, staged_dir)

    assert str(refusal.value) == (
        f"edition '{SUCCESSOR_EDITION}': the staged tree materialises to different bytes than the tree it was "
        "planned from, so the lift is not an identity and cannot be proven"
    )


def test_a_modelo_naming_no_predecessor_still_plans_through_the_full_copy_path(tmp_path: Path) -> None:
    """The same declarations without the predecessor key take the original branch and its bases."""
    modelo_dir = _build_modelo(tmp_path / "input", names_predecessor=False)

    plan = plan_migration(modelo_dir, _definition(modelo_dir))

    assert not plan.already_delta_authored
    predecessor, successor = plan.editions
    assert (predecessor.basis, predecessor.predecessor) == (PredecessorBasis.FIRST, None)
    assert (successor.basis, successor.predecessor) == (PredecessorBasis.STORAGE, PREDECESSOR_EDITION)
    assert successor.is_delta
    # The full-copy path drops the rows the successor may inherit and states the
    # rest in materialised order, where the lift path states what was authored.
    assert successor.inherited_ids == ("0001", "0003")
    assert successor.stated_ids == ("0005",)
    assert successor.casilla_overrides == (
        {
            "selector": {"revision": PREDECESSOR_EDITION, "id": "0002"},
            "fields": {"number": "22"},
            "removed_fields": [],
        },
    )


def test_a_value_the_chain_proof_cannot_render_is_refused_by_key_path_and_type(tmp_path: Path) -> None:
    """The proof is byte identity, so a value it has no exact rendering for fails closed rather than stringifies.

    A ``default=`` fallback would render this value as text and let the proof
    pass on it, which is unsound in both directions: two values whose fallback
    reads alike would compare equal, and a fallback reaching ``repr`` embeds an
    address that differs between the reference and staged reads the proof
    compares, making the proof fail at random.
    """
    modelo_dir = _build_modelo(tmp_path / "input", names_predecessor=True)
    source = read_edition(modelo_dir, SUCCESSOR_EDITION)
    # The unplanted edition renders, so the refusal below cannot pass vacuously.
    assert chain_materialisation(source)

    planted = dataclasses.replace(source, table={**source.table, "audit_stamp": {"taken_at": datetime.time(9, 0)}})

    with pytest.raises(RegistryError) as refusal:
        chain_materialisation(planted)

    assert str(refusal.value) == (
        f"edition '{SUCCESSOR_EDITION}': the value at table.audit_stamp.taken_at is a time, "
        "which the chain proof cannot compare; the proof is byte identity and refuses a type it has no exact "
        "rendering for"
    )


def test_a_date_and_the_text_that_reads_like_it_do_not_materialise_alike(tmp_path: Path) -> None:
    """Dates are what the corpus holds, so they render -- but never to the bare text a string would give."""
    modelo_dir = _build_modelo(tmp_path / "input", names_predecessor=True)
    source = read_edition(modelo_dir, SUCCESSOR_EDITION)

    dated = dataclasses.replace(source, table={**source.table, "stamp": datetime.date(int(SUCCESSOR_EDITION), 1, 1)})
    as_text = dataclasses.replace(source, table={**source.table, "stamp": f"{SUCCESSOR_EDITION}-01-01"})

    # A date is permitted: the corpus declares `valid_from` and its kin as bare
    # TOML dates, so refusing them would refuse every edition.
    assert chain_materialisation(dated)
    assert chain_materialisation(dated) != chain_materialisation(as_text)
    # And two editions holding the same date still prove identical.
    assert chain_materialisation(dated) == chain_materialisation(
        dataclasses.replace(source, table={**source.table, "stamp": datetime.date(int(SUCCESSOR_EDITION), 1, 1)}),
    )


def test_a_family_only_the_staged_tree_holds_is_reported_as_a_member_change() -> None:
    """Member identity is compared over both sides' families, not the reference's alone.

    Reading the reference's families only would leave a family the staged tree
    holds and the reference does not uncompared here, so the difference would
    fall through to the byte comparison and be reported as an unspecific change
    of bytes rather than as the members it is.
    """
    shared: dict[str, tuple[str, ...]] = {"casillas": ("0001|base",)}

    assert member_difference(shared, shared) is None
    assert member_difference(shared, {**shared, "bindings": (f"modelo-999-{SUCCESSOR_EDITION}-iva",)}) == (
        "lifting changed the bindings members, which a lift may never do: 0 before, 1 after, first difference at "
        f"position 0: ['modelo-999-{SUCCESSOR_EDITION}-iva'] on the staged side only"
    )
    # The reference-only direction, which the asymmetric read already caught,
    # keeps reporting on the side that still holds the member.
    assert member_difference({**shared, "bindings": (f"modelo-999-{SUCCESSOR_EDITION}-iva",)}, shared) == (
        "lifting changed the bindings members, which a lift may never do: 1 before, 0 after, first difference at "
        f"position 0: ['modelo-999-{SUCCESSOR_EDITION}-iva'] on the reference side only"
    )


def _build_forward_storage_modelo(root: Path, *, names_predecessor: bool = True) -> Path:
    """Reuse the later edition's payload in an earlier, independently dated branch."""
    modelo_dir = _build_modelo(root, names_predecessor=names_predecessor)
    successor_manifest = modelo_dir / "revisions" / SUCCESSOR_EDITION / "revision.toml"
    text = successor_manifest.read_text(encoding="utf-8")
    assert text.count(f"valid_from = {SUCCESSOR_EDITION}-01-01") == 1
    successor_manifest.write_text(
        text.replace(f"valid_from = {SUCCESSOR_EDITION}-01-01", f"valid_from = {SUCCESSOR_EDITION}-02-01"),
        encoding="utf-8",
        newline="\n",
    )
    branch_dir = modelo_dir / "revisions" / f"{SUCCESSOR_EDITION}-early"
    branch_dir.mkdir()
    (branch_dir / "revision.toml").write_text(
        f'[revisions."{SUCCESSOR_EDITION}-early"]\n'
        f"valid_from = {SUCCESSOR_EDITION}-01-01\n"
        f"valid_to = {SUCCESSOR_EDITION}-01-31\n"
        f'period_selector = {{ years = [{SUCCESSOR_EDITION}], periods = ["0A"] }}\n'
        f'legal_refs = ["{LEGAL_REF}"]\n'
        f'source_refs = ["{SOURCE_REF}"]\n'
        f'casilla_storage_baseline = "{SUCCESSOR_EDITION}"\n'
        f'family_storage_baseline = "{SUCCESSOR_EDITION}"\n',
        encoding="utf-8",
        newline="\n",
    )
    return modelo_dir


def _source_bytes(modelo_dir: Path) -> dict[Path, bytes]:
    return {path.relative_to(modelo_dir): path.read_bytes() for path in modelo_dir.rglob("*") if path.is_file()}


def test_forward_storage_dependencies_preserve_chronological_reports_and_existing_plans(tmp_path: Path) -> None:
    """A later storage baseline is ready before its early branch, with no legal edge inferred."""
    control_dir = _build_modelo(tmp_path / "control", names_predecessor=True)
    control = plan_migration(control_dir, _definition(control_dir))
    modelo_dir = _build_forward_storage_modelo(tmp_path / "input")
    definition = _definition(modelo_dir)
    before = _source_bytes(modelo_dir)

    plan, works = edition_delta_planning_plan(modelo_dir, definition)

    assert [edition.revision_id for edition in plan.editions] == [
        PREDECESSOR_EDITION,
        f"{SUCCESSOR_EDITION}-early",
        SUCCESSOR_EDITION,
    ]
    assert [work.plan for work in works] == list(plan.editions)
    assert (
        tuple(edition for edition in plan.editions if edition.revision_id != f"{SUCCESSOR_EDITION}-early")
        == control.editions
    )
    early = plan.editions[1]
    assert early.predecessor == SUCCESSOR_EDITION
    assert early.dependencies == (SUCCESSOR_EDITION,)
    assert early.blocked == ()
    assert early.stated_ids == ()
    assert early.inherited_ids == _MATERIALISED_ORDER
    assert definition.revisions[f"{SUCCESSOR_EDITION}-early"].predecessor is None
    assert str(definition.revisions[f"{SUCCESSOR_EDITION}-early"].casilla_storage_baseline) == SUCCESSOR_EDITION
    assert _source_bytes(modelo_dir) == before


def test_forward_storage_lift_proves_all_members_and_bytes_and_is_a_fixed_point(tmp_path: Path) -> None:
    """Dependency scheduling changes neither materialisation nor the second conversion."""
    reference_dir = _build_forward_storage_modelo(tmp_path / "input")
    staged_dir = _stage_lift(reference_dir, tmp_path / "staged")
    revision_ids = (PREDECESSOR_EDITION, f"{SUCCESSOR_EDITION}-early", SUCCESSOR_EDITION)

    assert (
        prove_chain(
            reference_modelo_dir=reference_dir,
            staged_modelo_dir=staged_dir,
            revision_ids=revision_ids,
            report=_CLEAN_REPORT,
        )
        == _CLEAN_REPORT
    )
    for revision_id in revision_ids:
        assert chain_materialisation(read_edition(staged_dir, revision_id)) == chain_materialisation(
            read_edition(reference_dir, revision_id)
        )
    assert _materialised_ids(staged_dir, f"{SUCCESSOR_EDITION}-early") == _MATERIALISED_ORDER
    assert _materialised_formula_ids(staged_dir, f"{SUCCESSOR_EDITION}-early") == _materialised_formula_ids(
        reference_dir, SUCCESSOR_EDITION
    )
    before = _source_bytes(staged_dir)

    plan, works = edition_delta_planning_plan(staged_dir, _definition(staged_dir))

    assert [edition.revision_id for edition in plan.editions] == list(revision_ids)
    assert [edition_changes(work) for work in works] == [False, False, False]
    assert _source_bytes(staged_dir) == before


def test_a_missing_forward_storage_baseline_is_still_refused_without_writing(tmp_path: Path) -> None:
    """Canonical source resolution still refuses a missing authored baseline."""
    modelo_dir = _build_forward_storage_modelo(tmp_path / "input")
    definition = _definition(modelo_dir)
    assert plan_migration(modelo_dir, definition).blocked_roots() == ()
    manifest = modelo_dir / "revisions" / f"{SUCCESSOR_EDITION}-early" / "revision.toml"
    text = manifest.read_text(encoding="utf-8")
    manifest.write_text(
        text.replace(f'casilla_storage_baseline = "{SUCCESSOR_EDITION}"', 'casilla_storage_baseline = "missing"'),
        encoding="utf-8",
        newline="\n",
    )
    before = _source_bytes(modelo_dir)

    with pytest.raises(RegistryError) as refusal:
        edition_delta_planning_plan(modelo_dir, definition)

    assert str(refusal.value).endswith(
        f"revision '{SUCCESSOR_EDITION}-early' has invalid casilla storage baseline 'missing'"
    )
    assert _source_bytes(modelo_dir) == before


def test_an_authored_predecessor_cycle_is_still_refused_before_planning(tmp_path: Path) -> None:
    """Dependency scheduling retains the canonical forest's existing cycle refusal."""
    modelo_dir = _build_modelo(tmp_path / "input", names_predecessor=True)
    definition = _definition(modelo_dir)
    assert plan_migration(modelo_dir, definition).blocked_roots() == ()
    manifest = modelo_dir / "revisions" / PREDECESSOR_EDITION / "revision.toml"
    with manifest.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(f'predecessor = "{SUCCESSOR_EDITION}"\n')
    before = _source_bytes(modelo_dir)

    with pytest.raises(RegistryError) as refusal:
        edition_delta_planning_plan(modelo_dir, definition)

    assert str(refusal.value).endswith(
        f"modelo '999' predecessor declarations form a cycle '{PREDECESSOR_EDITION}' -> '{SUCCESSOR_EDITION}' "
        f"-> '{PREDECESSOR_EDITION}'; "
        "no edition on it is reachable from a root"
    )
    assert _source_bytes(modelo_dir) == before


def test_a_cyclic_inferred_planning_baseline_is_refused_without_guessing(tmp_path: Path) -> None:
    """A valid authored DAG cannot justify changing an inferred chronological baseline."""
    modelo_dir = _build_forward_storage_modelo(tmp_path / "input", names_predecessor=False)
    definition = _definition(modelo_dir)
    assert _materialised_ids(modelo_dir, f"{SUCCESSOR_EDITION}-early") == _MATERIALISED_ORDER
    assert definition.revisions[SUCCESSOR_EDITION].predecessor is None
    before = _source_bytes(modelo_dir)

    with pytest.raises(RegistryError) as refusal:
        edition_delta_planning_plan(modelo_dir, definition)

    early = f"{SUCCESSOR_EDITION}-early"
    assert str(refusal.value) == f"cyclic edition planning dependency: '{early}' -> '{SUCCESSOR_EDITION}' -> '{early}'"
    assert _source_bytes(modelo_dir) == before
