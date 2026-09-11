"""Real-behaviour tests for the edition-delta migration.

Every proof runs the migration over a temporary copy of the bundled registry
holding one real modelo, loads the result through the validated authority, and
judges it with the round-trip gate. Each rule the migration applies is shown
biting: a planted defect changes the plan, or dropping a row the rule kept makes
the gate fail, and the unplanted tree shows the normal path.

Expected editions, defaults and inherited rows are derived here from the loaded
pre-migration definition by an independent criterion, never read back from a
migration run.

Locale identity is asserted only for the official Spanish label. The pilot's
lineage-wide label entries in the other output languages repeat the Spanish
text while the first edition's own entries carry translations, so an inherited
row can resolve a better translation than its full copy did; that is a
catalogue coverage gap, reported by the gate, and not something the migration
may change.
"""

from __future__ import annotations

import re
import shutil
import tomllib
from collections import Counter
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.revision_order import ordered_revisions
from cadrumo.domain.calculations.registry.schema import DeclaredPredecessor, ModeloDefinition

from ..analysis.delta_minimality import LINEAGE_CLAIM_FIELDS, definition_findings, restatement_differences
from ..compiler.authority import compile_validated_authority
from ..edition_delta_migration import (
    BlockedCause,
    EditionPlan,
    KeptReason,
    MigrationOutcome,
    MigrationRefusedError,
    PredecessorBasis,
    migrate_modelo,
    plan_migration,
)
from ..edition_round_trip import RoundTripFindingKind, copy_registry_tree, edition_round_trip_report

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BUNDLED = bundled_path("registry", "aeat")
_PILOT = "303"
_NO_EXPORT_SURFACE = "194"
_ROW_HEADER = re.compile(r'^\[\[revisions\.(?:"[^"\n]+"|[^".\]\n]+)\.casillas\]\]$', re.MULTILINE)
_ROW_SOURCE_LINE = re.compile(r"^source_refs = \[[^\]]*\]\n", re.MULTILINE)
#: Findings the pilot is expected to carry: bytes no scenario covers, and labels
#: in a non-Spanish language (see the module docstring).
_EXPECTED_KINDS = frozenset({RoundTripFindingKind.EXPORT_UNCHECKED, RoundTripFindingKind.LOCALIZATION})


def _registry(destination: Path, modelo_id: str) -> Path:
    return copy_registry_tree(_BUNDLED, destination / "registry" / "aeat", modelo_id=modelo_id)


def _load(root: Path, modelo_id: str) -> ModeloDefinition:
    return compile_validated_authority(root, bundled_path()).modelo(modelo_id)


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


def _kinds(outcome: MigrationOutcome) -> list[tuple[RoundTripFindingKind, str | None]]:
    assert outcome.report is not None
    return [(finding.kind, finding.revision_id) for finding in outcome.report.findings]


def _unexpected(outcome: MigrationOutcome) -> list[tuple[RoundTripFindingKind, str | None]]:
    """Every gate finding except those the module docstring accounts for; a Spanish label change is never one."""
    assert outcome.report is not None
    for finding in outcome.report.findings:
        if finding.kind is RoundTripFindingKind.LOCALIZATION:
            assert "in 'es'" not in finding.detail, finding.detail
            assert "key chain" not in finding.detail, finding.detail
    return [(kind, revision) for kind, revision in _kinds(outcome) if kind not in _EXPECTED_KINDS]


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


def _delta_editions(outcome: MigrationOutcome) -> list[EditionPlan]:
    return [edition for edition in outcome.plan.editions if edition.is_delta]


def _last_edition(outcome: MigrationOutcome) -> EditionPlan:
    """The latest edition, which no other edition inherits from, so a plant in it touches nothing downstream."""
    edition = outcome.plan.editions[-1]
    assert edition.is_delta, edition
    return edition


def test_the_pilot_migrates_every_successor_edition_in_merge_order(
    pilot: MigrationOutcome, pilot_before: ModeloDefinition, pilot_input: Path
) -> None:
    successors = {str(revision.id) for revision in ordered_revisions(pilot_before)[1:]}
    assert successors
    assert {edition.revision_id for edition in _delta_editions(pilot)} == successors
    assert not [edition for edition in pilot.plan.editions if edition.basis is PredecessorBasis.BLOCKED]

    # Typed content and merge-order row order round-trip for every edition; the
    # delta editions' export bytes are unchecked, which withholds publication.
    assert _unexpected(pilot) == []
    unchecked = [
        revision
        for kind, revision in _kinds(pilot)
        if kind is RoundTripFindingKind.EXPORT_UNCHECKED and revision is not None
    ]
    assert sorted(unchecked) == sorted(successors)
    assert not pilot.applied
    assert pilot.staged_registry is not None
    assert {str(r.id) for r in _load(pilot_input, _PILOT).revisions.values() if r.predecessor is not None} == set()

    staged = _load(pilot.staged_registry, _PILOT)
    reordered = []
    for edition in _delta_editions(pilot):
        assert edition.inherited_ids, edition.revision_id
        edition_dir = _edition_dir(pilot.staged_registry, _PILOT, edition.revision_id)
        assert not set(edition.inherited_ids) & _stated_ids(edition_dir)
        revision = staged.revisions[edition.revision_id]
        assert revision.predecessor == DeclaredPredecessor(revision_id=str(edition.predecessor))
        assert revision.reviewed_against == edition.reviewed_against
        # The loader marks exactly the rows the plan inherits, so the screen and
        # every other consumer see the same split the migration wrote.
        assert {casilla.id for casilla in revision.casillas if casilla.inherited_from is not None} == set(
            edition.inherited_ids
        )
        before = [casilla.id for casilla in pilot_before.revisions[edition.revision_id].casillas]
        after = [casilla.id for casilla in revision.casillas]
        assert sorted(before) == sorted(after)
        if before != after:
            reordered.append(edition.revision_id)
    assert reordered, "no edition was reordered, so the merge-order rule was never exercised"


def test_the_migrated_pilot_is_minimal_where_the_unmigrated_one_is_not(
    pilot: MigrationOutcome, pilot_before: ModeloDefinition
) -> None:
    """The screen judges only what each edition states, through the loader's inheritance markers."""
    assert pilot.staged_registry is not None
    assert any(item.kind == "restated_unchanged" for item in definition_findings(pilot_before, modelo_id=_PILOT))
    assert definition_findings(_load(pilot.staged_registry, _PILOT), modelo_id=_PILOT) == ()


def test_references_beyond_the_default_are_stated_as_additions(
    pilot: MigrationOutcome, pilot_before: ModeloDefinition
) -> None:
    """A row citing the edition default and more states only the rest, and still loads as it did."""
    assert pilot.staged_registry is not None
    staged = _load(pilot.staged_registry, _PILOT)
    checked = 0
    for edition in pilot.plan.editions:
        edition_dir = _edition_dir(pilot.staged_registry, _PILOT, edition.revision_id)
        before = {casilla.id: casilla for casilla in pilot_before.revisions[edition.revision_id].casillas}
        after = {casilla.id: casilla for casilla in staged.revisions[edition.revision_id].casillas}
        for fragment in sorted((edition_dir / "casillas").glob("*.toml")):
            for revision in tomllib.loads(fragment.read_text(encoding="utf-8"))["revisions"].values():
                for row in revision["casillas"]:
                    if "additional_source_refs" not in row:
                        continue
                    assert "source_refs" not in row
                    assert edition.source_default is not None
                    expected = tuple(dict.fromkeys((*edition.source_default, *row["additional_source_refs"])))
                    assert tuple(after[row["id"]].source_refs) == expected == tuple(before[row["id"]].source_refs)
                    checked += 1
    assert checked, "no row was lifted to additions, so the additions path was never exercised"


def test_a_row_stating_only_a_lineage_claim_stays_stated_and_dropping_it_loses_the_claim(
    pilot: MigrationOutcome, pilot_before: ModeloDefinition, pilot_input: Path, tmp_path: Path
) -> None:
    """An inherited row carries no lineage claim, so a row differing only by one can never be inherited."""
    assert pilot.staged_registry is not None
    found: tuple[EditionPlan, str] | None = None
    for edition in reversed(_delta_editions(pilot)):
        successor = pilot_before.revisions[edition.revision_id]
        predecessor = pilot_before.revisions[str(edition.predecessor)]
        by_lineage = {casilla.continuidad_id: casilla for casilla in predecessor.casillas if casilla.continuidad_id}
        for casilla in successor.casillas:
            inherited = by_lineage.get(casilla.continuidad_id)
            if inherited is None:
                continue
            differences = restatement_differences(casilla, successor, inherited, predecessor)
            if differences and set(differences) <= LINEAGE_CLAIM_FIELDS:
                found = (edition, str(casilla.id))
                break
        if found is not None:
            break
    assert found is not None, "no row differs from its inherited row by a lineage claim alone"
    edition, row_id = found
    assert row_id in edition.stated_ids

    dropped = shutil.copytree(pilot.staged_registry, tmp_path / "dropped" / "registry" / "aeat")
    _drop_row(_edition_dir(dropped, _PILOT, edition.revision_id), row_id)
    report = edition_round_trip_report(
        live_registry_root=dropped, reference_registry_root=pilot_input, modelo_id=_PILOT, export_scenarios={}
    )
    content = {
        finding.revision_id: finding.detail
        for finding in report.findings
        if finding.kind is RoundTripFindingKind.CONTENT
    }
    assert edition.revision_id in content
    detail = content[edition.revision_id]
    assert f"casilla {row_id!r} changed [" in detail
    assert "continuidad_evidence" in detail or "continuidad_origin" in detail


def test_a_rerun_is_a_no_op_and_a_restated_default_is_refused(pilot: MigrationOutcome, tmp_path: Path) -> None:
    assert pilot.staged_registry is not None
    again = migrate_modelo(
        registry_root=pilot.staged_registry, modelo_id=_PILOT, work_dir=tmp_path / "again", declare_blocked_roots=True
    )
    assert not again.changed
    assert again.staged_registry is None
    assert not (tmp_path / "again").exists()

    edition = _last_edition(pilot)
    assert edition.source_default is not None and len(edition.source_default) == 1
    planted = shutil.copytree(pilot.staged_registry, tmp_path / "planted" / "registry" / "aeat")
    edition_dir = _edition_dir(planted, _PILOT, edition.revision_id)
    lifted_row = next(
        row_id
        for row_id in edition.stated_ids
        if "\nsource_refs = " not in (block := _row_block(edition_dir, row_id)[1])
        and "additional_source_refs" not in block
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


def _lower_the_grade(edition_dir: Path) -> None:
    manifest = edition_dir / "revision.toml"
    text = manifest.read_text(encoding="utf-8")
    assert text.count('authority_grade = "filing"') == 1
    manifest.write_text(
        text.replace('authority_grade = "filing"', 'authority_grade = "applicability"'), encoding="utf-8", newline="\n"
    )


def test_a_lower_grade_successor_is_blocked_and_refused_without_the_flag(
    pilot: MigrationOutcome, pilot_input: Path, tmp_path: Path
) -> None:
    """A blocked edition needs a no-predecessor claim, which is written only on request and never staged otherwise."""
    assert plan_migration(pilot_input / "modelos" / _PILOT, _load(pilot_input, _PILOT)).blocked_roots() == ()

    edition = _last_edition(pilot)
    planted = shutil.copytree(pilot_input, tmp_path / "registry" / "aeat")
    _lower_the_grade(_edition_dir(planted, _PILOT, edition.revision_id))

    plan = plan_migration(planted / "modelos" / _PILOT, _load(planted, _PILOT), declare_blocked_roots=True)
    assert (
        BlockedCause.LOWER_GRADE
        in next(item for item in plan.editions if item.revision_id == edition.revision_id).blocked
    )
    with pytest.raises(MigrationRefusedError, match="needs an explicit no-predecessor declaration"):
        migrate_modelo(registry_root=planted, modelo_id=_PILOT, work_dir=tmp_path / "work")
    assert not (tmp_path / "work").exists()


def test_a_row_the_successor_changed_is_kept_stated(pilot: MigrationOutcome, pilot_input: Path, tmp_path: Path) -> None:
    edition = _last_edition(pilot)
    planted = shutil.copytree(pilot_input, tmp_path / "registry" / "aeat")
    edition_dir = _edition_dir(planted, _PILOT, edition.revision_id)
    row_id = next(
        row_id for row_id in edition.inherited_ids if _row_block(edition_dir, row_id)[1].count("required = false") == 1
    )
    fragment, block = _row_block(edition_dir, row_id)
    text = fragment.read_text(encoding="utf-8")
    fragment.write_text(
        text.replace(block, block.replace("required = false", "required = true")), encoding="utf-8", newline="\n"
    )

    plan = plan_migration(planted / "modelos" / _PILOT, _load(planted, _PILOT), declare_blocked_roots=True)

    changed = next(item for item in plan.editions if item.revision_id == edition.revision_id)
    assert row_id in changed.stated_ids
    assert changed.kept[KeptReason.DIFFERS] == edition.kept.get(KeptReason.DIFFERS, 0) + 1
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
    edition = _last_edition(pilot)
    revision_id = edition.revision_id
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
    evolutions.mkdir(exist_ok=True)
    assert not (evolutions / "withdrawn.toml").exists()
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
    assert _unexpected(retired) == []
    assert retired.staged_registry is not None
    staged = _load(retired.staged_registry, _PILOT)
    # The retirement withdraws the lineage from the successor only; the
    # predecessor it is inherited from still carries the row.
    assert row_id not in {casilla.id for casilla in staged.revisions[revision_id].casillas}
    assert row_id in {casilla.id for casilla in staged.revisions[str(edition.predecessor)].casillas}


def _rewrite_row_sources(edition_dir: Path, sources: list[list[str]]) -> None:
    """Give the edition's rows, in fragment order, the given row-level ``source_refs``; constraints are untouched."""
    remaining = iter(sources)
    for fragment in sorted((edition_dir / "casillas").glob("*.toml")):
        preamble, blocks = _blocks(fragment.read_text(encoding="utf-8"))
        rewritten = []
        for block in blocks:
            header_end = block.index("\n") + 1
            row_end = block.find("\n[", header_end)
            row_part = block[: row_end + 1] if row_end >= 0 else block
            refs = ", ".join(f'"{ref}"' for ref in next(remaining))
            replaced, count = _ROW_SOURCE_LINE.subn(f"source_refs = [{refs}]\n", row_part, count=1)
            assert count == 1, block
            rewritten.append(replaced + block[len(row_part) :])
        fragment.write_text(preamble + "".join(rewritten), encoding="utf-8", newline="\n")
    assert next(remaining, None) is None


def test_the_default_is_the_leading_run_most_rows_open_with_and_a_tie_withholds_it(
    pilot: MigrationOutcome, pilot_before: ModeloDefinition, pilot_input: Path, tmp_path: Path
) -> None:
    first = pilot.plan.editions[0]
    rows = [tuple(casilla.source_refs) for casilla in pilot_before.revisions[first.revision_id].casillas]
    openers = Counter(refs[0] for refs in rows)
    ((top, top_count), (runner_up, runner_count)) = openers.most_common(2)
    assert top_count > runner_count
    longer = Counter(refs[:2] for refs in rows if len(refs) > 1 and refs[0] == top)
    assert not longer or longer.most_common(1)[0][1] < top_count
    assert first.source_default == (top,)
    assert first.lifted.row_source_refs > 0

    # Half the rows opening with one reference and half with another is a tie:
    # no run opens more rows than the other, so no default is declared at all.
    assert len(rows) % 2 == 0
    planted = shutil.copytree(pilot_input, tmp_path / "registry" / "aeat")
    _rewrite_row_sources(
        _edition_dir(planted, _PILOT, first.revision_id),
        [[top] if index % 2 == 0 else [runner_up] for index in range(len(rows))],
    )

    plan = plan_migration(planted / "modelos" / _PILOT, _load(planted, _PILOT), declare_blocked_roots=True)

    tied = plan.editions[0]
    assert tied.source_default is None
    assert tied.source_default_withheld is not None and "tie" in tied.source_default_withheld
    assert tied.lifted.row_source_refs == 0


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
