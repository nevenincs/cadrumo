"""Real-behaviour tests for the edition-delta migration.

Every proof runs the migration over a temporary copy of the bundled registry
holding one real modelo, loads the result through the validated authority, and
judges it with the round-trip gate. Each rule the migration applies is shown
biting: a planted defect changes the plan, or dropping a row the rule kept makes
the gate fail, and the unplanted tree shows the normal path.

Expected blocked editions and inherited rows are derived here from the loaded
pre-migration definition by an independent criterion, never read back from a
migration run.
"""

from __future__ import annotations

import re
import shutil
import tomllib
from itertools import pairwise
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.revision_order import ordered_revisions
from cadrumo.domain.calculations.registry.schema import DeclaredPredecessor, ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.tests.test_revision_edition_round_trip import (
    RoundTripFindingKind,
    copy_registry_tree,
    edition_round_trip_report,
)

from ..analysis.delta_minimality import inheritable_value
from ..edition_delta_migration import (
    BlockedCause,
    KeptReason,
    MigrationOutcome,
    MigrationRefusedError,
    PredecessorBasis,
    migrate_modelo,
    plan_migration,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BUNDLED = bundled_path("registry", "aeat")
_PILOT = "303"
_NO_EXPORT_SURFACE = "194"
_ROW_HEADER = re.compile(r'^\[\[revisions\.(?:"[^"\n]+"|[^".\]\n]+)\.casillas\]\]$', re.MULTILINE)


def _registry(destination: Path, modelo_id: str) -> Path:
    return copy_registry_tree(_BUNDLED, destination / "registry" / "aeat", modelo_id=modelo_id)


def _load(root: Path, modelo_id: str) -> ModeloDefinition:
    return ValidatedRegistryAuthority.load(root, source_root=bundled_path()).modelo(modelo_id)


def _edition_dir(root: Path, modelo_id: str, revision_id: str) -> Path:
    return root / "modelos" / modelo_id / "revisions" / revision_id


def _stated_ids(edition_dir: Path) -> set[str]:
    ids: set[str] = set()
    for fragment in (edition_dir / "casillas").glob("*.toml"):
        for revision in tomllib.loads(fragment.read_text(encoding="utf-8"))["revisions"].values():
            ids.update(str(row["id"]) for row in revision["casillas"])
    return ids


def _blocks(text: str) -> tuple[str, list[str]]:
    starts = [match.start() for match in _ROW_HEADER.finditer(text)]
    bounds = [*starts, len(text)]
    return text[: starts[0]] if starts else text, [text[bounds[i] : bounds[i + 1]] for i in range(len(starts))]


def _row_block(edition_dir: Path, row_id: str) -> tuple[Path, str]:
    for fragment in sorted((edition_dir / "casillas").glob("*.toml")):
        for block in _blocks(fragment.read_text(encoding="utf-8"))[1]:
            if re.search(rf'^id = "{re.escape(row_id)}"$', block, re.MULTILINE):
                return fragment, block
    raise AssertionError(f"no casilla {row_id!r} under {edition_dir}")


def _drop_row(edition_dir: Path, row_id: str) -> None:
    fragment, block = _row_block(edition_dir, row_id)
    text = fragment.read_text(encoding="utf-8").replace(block, "")
    if _ROW_HEADER.search(text):
        fragment.write_text(text, encoding="utf-8", newline="\n")
    else:
        fragment.unlink()


def _order_expressible(predecessor: ModeloRevision, successor: ModeloRevision) -> bool:
    """Whether appending new rows to the predecessor's order yields the successor's order.

    Shared lineages must keep their relative order, and every row whose lineage
    the predecessor lacks must follow every shared row.
    """
    before = [casilla.continuidad_id for casilla in predecessor.casillas]
    after = [casilla.continuidad_id for casilla in successor.casillas]
    shared = set(before) & set(after)
    new_positions = [index for index, lineage in enumerate(after) if lineage not in shared]
    return [lineage for lineage in before if lineage in shared] == [
        lineage for lineage in after if lineage in shared
    ] and all(index >= len(after) - len(new_positions) for index in new_positions)


def _kinds(outcome: MigrationOutcome) -> list[tuple[RoundTripFindingKind, str | None]]:
    assert outcome.report is not None
    return [(finding.kind, finding.revision_id) for finding in outcome.report.findings]


@pytest.fixture(scope="module")
def pilot_input(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _registry(tmp_path_factory.mktemp("pilot-input"), _PILOT)


@pytest.fixture(scope="module")
def pilot(pilot_input: Path, tmp_path_factory: pytest.TempPathFactory) -> MigrationOutcome:
    return migrate_modelo(
        registry_root=pilot_input,
        modelo_id=_PILOT,
        work_dir=tmp_path_factory.mktemp("pilot-work") / "run",
        declare_blocked_roots=True,
        apply=True,
    )


@pytest.fixture(scope="module")
def pilot_before(pilot_input: Path) -> ModeloDefinition:
    return _load(pilot_input, _PILOT)


def _delta_editions(outcome: MigrationOutcome) -> list[str]:
    return [edition.revision_id for edition in outcome.plan.editions if edition.is_delta]


def test_the_pilot_blocks_exactly_the_editions_whose_order_inheritance_cannot_produce(
    pilot: MigrationOutcome, pilot_before: ModeloDefinition, pilot_input: Path
) -> None:
    ordered = ordered_revisions(pilot_before)
    expressible = {
        str(successor.id) for predecessor, successor in pairwise(ordered) if _order_expressible(predecessor, successor)
    }
    blocked = {edition.revision_id for edition in pilot.plan.editions if edition.basis is PredecessorBasis.BLOCKED}
    assert expressible, "the pilot must carry at least one edition inheritance can express, or it proves nothing"
    assert set(_delta_editions(pilot)) == expressible
    assert blocked == {str(revision.id) for revision in ordered[1:]} - expressible
    assert all(
        edition.blocked == (BlockedCause.ROW_ORDER,)
        for edition in pilot.plan.editions
        if edition.revision_id in blocked
    )

    # Typed content, row order and locale identity round-trip for every edition;
    # the only finding is the delta edition whose export bytes no scenario covers,
    # and that finding alone withholds publication.
    assert _kinds(pilot) == [(RoundTripFindingKind.EXPORT_UNCHECKED, revision) for revision in sorted(expressible)]
    assert not pilot.applied
    assert pilot.staged_registry is not None
    assert {str(r.id) for r in _load(pilot_input, _PILOT).revisions.values() if r.predecessor is not None} == set()

    staged = _load(pilot.staged_registry, _PILOT)
    for edition in pilot.plan.editions:
        if not edition.is_delta:
            continue
        assert edition.inherited_ids, edition.revision_id
        edition_dir = _edition_dir(pilot.staged_registry, _PILOT, edition.revision_id)
        assert not set(edition.inherited_ids) & _stated_ids(edition_dir)
        revision = staged.revisions[edition.revision_id]
        assert revision.predecessor == DeclaredPredecessor(revision_id=edition.predecessor)
        assert revision.reviewed_against == edition.predecessor
        assert [casilla.id for casilla in revision.casillas] == [
            casilla.id for casilla in pilot_before.revisions[edition.revision_id].casillas
        ]


def test_a_row_the_screen_calls_identical_but_the_loader_would_not_reproduce_stays_stated(
    pilot: MigrationOutcome, pilot_before: ModeloDefinition, pilot_input: Path, tmp_path: Path
) -> None:
    """The screen ignores lineage evidence; inheriting on its word would carry the predecessor's evidence."""
    assert pilot.staged_registry is not None
    (revision_id,) = _delta_editions(pilot)
    edition = next(item for item in pilot.plan.editions if item.revision_id == revision_id)
    successor = pilot_before.revisions[revision_id]
    predecessor = pilot_before.revisions[str(edition.predecessor)]
    by_lineage = {casilla.continuidad_id: casilla for casilla in predecessor.casillas}
    screen_identical_evidence_differs = sorted(
        str(casilla.id)
        for casilla in successor.casillas
        if (inherited := by_lineage.get(casilla.continuidad_id)) is not None
        and inheritable_value(casilla, successor) == inheritable_value(inherited, predecessor)
        and (casilla.continuidad_evidence, casilla.continuidad_origin)
        != (inherited.continuidad_evidence, inherited.continuidad_origin)
    )
    assert screen_identical_evidence_differs
    row_id = screen_identical_evidence_differs[0]
    assert row_id in edition.stated_ids
    assert edition.kept[KeptReason.NOT_EXACT] >= len(screen_identical_evidence_differs)

    dropped = shutil.copytree(pilot.staged_registry, tmp_path / "dropped" / "registry" / "aeat")
    _drop_row(_edition_dir(dropped, _PILOT, revision_id), row_id)
    report = edition_round_trip_report(
        live_registry_root=dropped, reference_registry_root=pilot_input, modelo_id=_PILOT, export_scenarios={}
    )
    content = [finding for finding in report.findings if finding.kind is RoundTripFindingKind.CONTENT]
    assert [finding.revision_id for finding in content] == [revision_id]
    assert f"casilla {row_id!r} changed [" in content[0].detail
    assert "continuidad_evidence" in content[0].detail or "continuidad_origin" in content[0].detail


def test_a_rerun_is_a_no_op_and_a_restated_default_is_refused(pilot: MigrationOutcome, tmp_path: Path) -> None:
    assert pilot.staged_registry is not None
    again = migrate_modelo(
        registry_root=pilot.staged_registry, modelo_id=_PILOT, work_dir=tmp_path / "again", declare_blocked_roots=True
    )
    assert not again.changed
    assert again.staged_registry is None
    assert not (tmp_path / "again").exists()

    (revision_id,) = _delta_editions(pilot)
    edition = next(item for item in pilot.plan.editions if item.revision_id == revision_id)
    assert edition.source_default is not None
    planted = shutil.copytree(pilot.staged_registry, tmp_path / "planted" / "registry" / "aeat")
    edition_dir = _edition_dir(planted, _PILOT, revision_id)
    lifted_row = next(
        row_id for row_id in edition.stated_ids if "\nsource_refs = " not in _row_block(edition_dir, row_id)[1]
    )
    fragment, block = _row_block(edition_dir, lifted_row)
    restated = block.replace(
        f'id = "{lifted_row}"\n',
        f'id = "{lifted_row}"\nsource_refs = ["{edition.source_default[0]}"]\n',
        1,
    )
    assert restated != block
    fragment.write_text(fragment.read_text(encoding="utf-8").replace(block, restated), encoding="utf-8", newline="\n")
    with pytest.raises(MigrationRefusedError, match="re-planning it would change it"):
        migrate_modelo(
            registry_root=planted, modelo_id=_PILOT, work_dir=tmp_path / "refused", declare_blocked_roots=True
        )


def test_two_runs_over_one_tree_write_the_same_bytes(
    pilot: MigrationOutcome, pilot_input: Path, tmp_path: Path
) -> None:
    second = migrate_modelo(
        registry_root=pilot_input, modelo_id=_PILOT, work_dir=tmp_path / "second", declare_blocked_roots=True
    )
    assert pilot.staged_registry is not None and second.staged_registry is not None
    first_root, second_root = (root / "modelos" / _PILOT for root in (pilot.staged_registry, second.staged_registry))

    def tree(root: Path) -> dict[str, bytes]:
        return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}

    assert tree(first_root) == tree(second_root)
    assert second.plan == pilot.plan


def test_without_the_flag_a_blocked_edition_is_refused_before_anything_is_staged(
    pilot_input: Path, tmp_path: Path
) -> None:
    with pytest.raises(MigrationRefusedError, match="needs an explicit no-predecessor declaration"):
        migrate_modelo(registry_root=pilot_input, modelo_id=_PILOT, work_dir=tmp_path / "work")
    assert not (tmp_path / "work").exists()


def test_a_row_the_successor_changed_is_kept_stated(pilot: MigrationOutcome, pilot_input: Path, tmp_path: Path) -> None:
    (revision_id,) = _delta_editions(pilot)
    edition = next(item for item in pilot.plan.editions if item.revision_id == revision_id)
    planted = shutil.copytree(pilot_input, tmp_path / "registry" / "aeat")
    edition_dir = _edition_dir(planted, _PILOT, revision_id)
    row_id = next(
        row_id for row_id in edition.inherited_ids if _row_block(edition_dir, row_id)[1].count("required = false") == 1
    )
    fragment, block = _row_block(edition_dir, row_id)
    text = fragment.read_text(encoding="utf-8")
    fragment.write_text(
        text.replace(block, block.replace("required = false", "required = true")), encoding="utf-8", newline="\n"
    )

    plan = plan_migration(planted / "modelos" / _PILOT, _load(planted, _PILOT), declare_blocked_roots=True)

    changed = next(item for item in plan.editions if item.revision_id == revision_id)
    assert row_id in changed.stated_ids
    assert changed.kept[KeptReason.DIFFERS] == 1
    assert set(changed.inherited_ids) == set(edition.inherited_ids) - {row_id}


def _withdrawable_row(definition: ModeloDefinition, edition_dir: Path, candidates: tuple[str, ...]) -> str:
    """A casilla no export field, formula, binding or other declaration of the edition names."""
    other = "".join(
        path.read_text(encoding="utf-8") for path in edition_dir.rglob("*.toml") if path.parent.name != "casillas"
    )
    revision = definition.revisions[edition_dir.name]
    exported = {str(casilla.id) for casilla in revision.casillas if casilla.export_refs}
    return next(row_id for row_id in sorted(candidates) if row_id not in exported and f'"{row_id}"' not in other)


def test_a_withdrawn_lineage_blocks_until_a_retirement_declares_it(
    pilot: MigrationOutcome, pilot_before: ModeloDefinition, pilot_input: Path, tmp_path: Path
) -> None:
    (revision_id,) = _delta_editions(pilot)
    edition = next(item for item in pilot.plan.editions if item.revision_id == revision_id)
    planted = shutil.copytree(pilot_input, tmp_path / "registry" / "aeat")
    edition_dir = _edition_dir(planted, _PILOT, revision_id)
    row_id = _withdrawable_row(pilot_before, edition_dir, edition.inherited_ids)
    lineage = next(c.continuidad_id for c in pilot_before.revisions[revision_id].casillas if c.id == row_id)
    _drop_row(edition_dir, row_id)

    unretired = plan_migration(planted / "modelos" / _PILOT, _load(planted, _PILOT), declare_blocked_roots=True)
    assert next(item for item in unretired.editions if item.revision_id == revision_id).blocked == (
        BlockedCause.UNRETIRED_WITHDRAWAL,
    )

    manifest_path = edition_dir / "revision.toml"
    manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))["revisions"][revision_id]
    manifest_path.write_text(
        re.sub(
            rf'(?ms)^\[revisions\.(?:"{re.escape(revision_id)}"|{re.escape(revision_id)})'
            r"\.family_dispositions\.casilla_continuidad_evolutions\]\n.*?(?=^\[|\Z)",
            "",
            manifest_path.read_text(encoding="utf-8"),
        ),
        encoding="utf-8",
        newline="\n",
    )
    evolutions = edition_dir / "casilla_continuidad_evolutions"
    evolutions.mkdir()
    (evolutions / "withdrawn.toml").write_text(
        f'[[revisions."{revision_id}".casilla_continuidad_evolutions]]\n'
        f'id = "{lineage}-{revision_id}-retired"\ncontinuidad_id = "{lineage}"\n'
        f'from_revision = "{edition.predecessor}"\nto_revision = "{revision_id}"\nevolution_kind = "retired"\n'
        f'legal_refs = ["{manifest["orden_aplicabilidad"][0]}"]\nsource_refs = ["{manifest["source_refs"][0]}"]\n',
        encoding="utf-8",
        newline="\n",
    )

    retired = migrate_modelo(
        registry_root=planted, modelo_id=_PILOT, work_dir=tmp_path / "work", declare_blocked_roots=True
    )

    assert next(item for item in retired.plan.editions if item.revision_id == revision_id).is_delta
    assert _kinds(retired) == [(RoundTripFindingKind.EXPORT_UNCHECKED, revision_id)]
    assert retired.staged_registry is not None
    staged = _load(retired.staged_registry, _PILOT)
    # The retirement withdraws the lineage from the successor only; the
    # predecessor it is inherited from still carries the row.
    assert row_id not in {casilla.id for casilla in staged.revisions[revision_id].casillas}
    assert row_id in {casilla.id for casilla in staged.revisions[str(edition.predecessor)].casillas}


def test_a_lower_grade_successor_is_blocked(pilot: MigrationOutcome, pilot_input: Path, tmp_path: Path) -> None:
    (revision_id,) = _delta_editions(pilot)
    planted = shutil.copytree(pilot_input, tmp_path / "registry" / "aeat")
    manifest = _edition_dir(planted, _PILOT, revision_id) / "revision.toml"
    text = manifest.read_text(encoding="utf-8")
    assert text.count('authority_grade = "filing"') == 1
    manifest.write_text(
        text.replace('authority_grade = "filing"', 'authority_grade = "applicability"'), encoding="utf-8", newline="\n"
    )

    plan = plan_migration(planted / "modelos" / _PILOT, _load(planted, _PILOT), declare_blocked_roots=True)

    assert BlockedCause.LOWER_GRADE in next(item for item in plan.editions if item.revision_id == revision_id).blocked


def test_a_tied_source_default_is_withheld_and_a_clear_one_is_lifted(
    pilot: MigrationOutcome, pilot_before: ModeloDefinition, pilot_input: Path, tmp_path: Path
) -> None:
    first = pilot.plan.editions[0]
    counts: dict[tuple[str, ...], int] = {}
    for casilla in pilot_before.revisions[first.revision_id].casillas:
        counts[tuple(casilla.source_refs)] = counts.get(tuple(casilla.source_refs), 0) + 1
    top, runner_up = sorted(counts.items(), key=lambda item: -item[1])[:2]
    assert top[1] == runner_up[1], "the first edition's two most common source_refs values must tie for this proof"
    assert first.source_default is None
    assert first.source_default_withheld is not None and "tie" in first.source_default_withheld

    planted = shutil.copytree(pilot_input, tmp_path / "registry" / "aeat")
    edition_dir = _edition_dir(planted, _PILOT, first.revision_id)
    longer, shorter = sorted((top[0], runner_up[0]), key=len, reverse=True)
    row_id = next(
        str(casilla.id)
        for casilla in pilot_before.revisions[first.revision_id].casillas
        if tuple(casilla.source_refs) == longer
    )
    fragment, block = _row_block(edition_dir, row_id)
    rendered_longer = "source_refs = [" + ", ".join(f'"{ref}"' for ref in longer) + "]"
    rendered_shorter = "source_refs = [" + ", ".join(f'"{ref}"' for ref in shorter) + "]"
    assert block.count(rendered_longer) == 1
    fragment.write_text(
        fragment.read_text(encoding="utf-8").replace(block, block.replace(rendered_longer, rendered_shorter)),
        encoding="utf-8",
        newline="\n",
    )

    plan = plan_migration(planted / "modelos" / _PILOT, _load(planted, _PILOT), declare_blocked_roots=True)

    lifted = plan.editions[0]
    assert lifted.source_default == shorter
    assert lifted.source_default_withheld is None
    assert lifted.lifted.row_source_refs == counts[shorter] + 1


def test_apply_publishes_a_modelo_whose_proof_is_clean(tmp_path: Path) -> None:
    registry = _registry(tmp_path / "target", _NO_EXPORT_SURFACE)
    before = _load(registry, _NO_EXPORT_SURFACE)
    assert not any(revision.export_layouts for revision in before.revisions.values())
    pristine = shutil.copytree(registry, tmp_path / "pristine" / "registry" / "aeat")

    outcome = migrate_modelo(
        registry_root=registry, modelo_id=_NO_EXPORT_SURFACE, work_dir=tmp_path / "work", apply=True
    )

    assert outcome.report is not None and outcome.report.findings == ()
    assert outcome.applied
    published = _load(registry, _NO_EXPORT_SURFACE)
    assert {str(r.id): r.predecessor for r in published.revisions.values()} == {
        str(edition.revision_id): (
            DeclaredPredecessor(revision_id=edition.predecessor) if edition.predecessor else None
        )
        for edition in outcome.plan.editions
    }
    report = edition_round_trip_report(
        live_registry_root=registry, reference_registry_root=pristine, modelo_id=_NO_EXPORT_SURFACE, export_scenarios={}
    )
    assert report.findings == ()
