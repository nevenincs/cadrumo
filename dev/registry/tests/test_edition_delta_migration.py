"""Real-behaviour tests for the edition-delta migration.

Every proof runs the migration over a temporary copy of the bundled registry
holding one real modelo and its dependency closure, loads the result through
the validated authority, and judges it with the round-trip gate. Each rule the migration applies is shown
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

import json
import re
import shutil
import tomllib
from collections import Counter
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.toml import render_toml
from cadrumo.domain.calculations.registry.errors import RegistryError
from cadrumo.domain.calculations.registry.revision_contracts import DeclaredPredecessor
from cadrumo.domain.calculations.registry.revision_order import ordered_revisions
from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from dev._paths import REPO_ROOT

from ..analysis.delta_minimality import LINEAGE_CLAIM_FIELDS, definition_findings, restatement_differences
from ..compiler.edition_materialisation import materialise_edition
from ..compiler.loader import load_modelo_directory
from ..compiler.loader_grammar import REVISION_SECTION_FIELDS
from ..conformance.loader_directory_mode_support import write_standard_manifest
from ..edition_delta_migration import (
    BlockedCause,
    EditionPlan,
    MigrationOutcome,
    MigrationPlan,
    PredecessorBasis,
    _validate_staged_modelo,
    main,
    migrate_modelo,
    persist_migration_report,
    plan_migration,
)
from ..edition_export_scenarios import edition_export_scenarios
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
    root = copy_registry_tree(_BUNDLED, destination / "registry" / "aeat", modelo_id=modelo_id)
    modelo = root / "modelos" / modelo_id
    definition = load_modelo_directory(modelo)
    # The corpus can already be enrolled. Build the input before invoking the
    # migration under test, using the canonical materializer, not its output.
    # Keep reference defaults expanded on each row so lifting is exercised too.
    editions = [materialise_edition(modelo, path.name) for path in sorted((modelo / "revisions").iterdir())]
    for edition in editions:
        directory = (modelo / "revisions" / edition.revision_id).resolve()
        assert directory.is_relative_to(root.resolve())
        shutil.rmtree(directory)
        directory.mkdir()
        table = dict(edition.table)
        typed_rows = {str(row.id): row for row in definition.revisions[edition.revision_id].casillas}
        expanded_rows = []
        for raw_row in table.get("casillas", ()):
            row = dict(raw_row)
            typed = typed_rows[str(row["id"])]
            row.pop("additional_source_refs", None)
            row["source_refs"] = tuple(typed.source_refs)
            row["legal_refs"] = tuple(typed.legal_refs)
            if "constraints" in row:
                constraints = dict(row["constraints"])
                constraints.pop("additional_source_refs", None)
                constraints["source_refs"] = tuple(typed.constraints.source_refs)
                constraints["legal_refs"] = tuple(typed.constraints.legal_refs)
                row["constraints"] = constraints
            expanded_rows.append(row)
        table["casillas"] = tuple(expanded_rows)
        for key in ("predecessor", "restated_families", "casilla_source_refs"):
            table.pop(key, None)
        # A deliberate authored ordering, independent of the migration's merge
        # order, preserves the order-detector's non-vacuity after enrollment.
        if modelo_id == _PILOT and edition.inherits_from is not None:
            table["casillas"] = tuple(reversed(table["casillas"]))
        manifest = {key: value for key, value in table.items() if key not in REVISION_SECTION_FIELDS}
        (directory / "revision.toml").write_text(
            render_toml({"revisions": {edition.revision_id: manifest}}), encoding="utf-8"
        )
        for section in REVISION_SECTION_FIELDS:
            if not table.get(section):
                continue
            section_directory = directory / section
            section_directory.mkdir()
            (section_directory / "0001-declarations.toml").write_text(
                render_toml({"revisions": {edition.revision_id: {section: table[section]}}}), encoding="utf-8"
            )
    return root


def _load(root: Path, modelo_id: str) -> ModeloDefinition:
    return load_modelo_directory(root / "modelos" / modelo_id)


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
    isolated = _registry(tmp_path_factory.mktemp("pilot-live"), _PILOT)
    return migrate_modelo(
        registry_root=isolated,
        modelo_id=_PILOT,
        work_dir=tmp_path_factory.mktemp("pilot-work") / "run",
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
    # Delta editions' export bytes are unchecked.  That withholds authority
    # publication, but it does not withhold the proven source replacement.
    assert _unexpected(pilot) == []
    unchecked = [
        revision
        for kind, revision in _kinds(pilot)
        if kind is RoundTripFindingKind.EXPORT_UNCHECKED and revision is not None
    ]
    assert sorted(unchecked) == sorted(successors)
    assert pilot.applied
    assert pilot.source_status == "applied"
    assert pilot.publication_readiness_status == "failed"
    assert pilot.publication_execution_status == "not_performed"
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


def test_a_row_stating_only_a_lineage_claim_moves_to_the_canonical_carrier(
    pilot: MigrationOutcome, pilot_before: ModeloDefinition
) -> None:
    """Continuity-only differences survive without pinning the complete casilla payload."""
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
    assert row_id not in edition.stated_ids
    original_row = next(casilla for casilla in successor.casillas if str(casilla.id) == row_id)
    matching_claims = tuple(
        claim for claim in edition.lineage_attestations if claim.continuidad_id == original_row.continuidad_id
    )
    assert len(matching_claims) == 1
    (claim,) = matching_claims
    assert claim.to_revision == edition.revision_id
    assert claim.from_revision == edition.predecessor
    assert claim.continuidad_id == original_row.continuidad_id

    edition_dir = _edition_dir(pilot.staged_registry, _PILOT, edition.revision_id)
    authored_payload_fields = sum(
        len(row)
        for fragment in (edition_dir / "casillas").glob("*.toml")
        for revision in tomllib.loads(fragment.read_text(encoding="utf-8"))["revisions"].values()
        for row in revision["casillas"]
        if row["id"] == row_id
    )
    assert authored_payload_fields == 0
    hydrated = _load(pilot.staged_registry, _PILOT).revisions[edition.revision_id]
    hydrated_row = next(casilla for casilla in hydrated.casillas if str(casilla.id) == row_id)
    assert hydrated_row.continuidad_origin == original_row.continuidad_origin
    assert hydrated_row.continuidad_evidence == original_row.continuidad_evidence


def test_a_rerun_is_a_no_op_and_a_restated_default_is_lifted_without_changing_the_chain(
    pilot: MigrationOutcome, tmp_path: Path
) -> None:
    assert pilot.staged_registry is not None
    again = migrate_modelo(registry_root=pilot.staged_registry, modelo_id=_PILOT, work_dir=tmp_path / "again")
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
    lifted = migrate_modelo(registry_root=planted, modelo_id=_PILOT, work_dir=tmp_path / "lifted")
    assert lifted.changed
    assert lifted.staged_registry is not None
    assert _unexpected(lifted) == []
    lifted_edition = next(item for item in lifted.plan.editions if item.revision_id == edition.revision_id)
    assert lifted_edition.basis is PredecessorBasis.LIFT_ONLY
    assert lifted_edition.lifted.row_source_refs == 1
    assert _row_block(edition_dir, lifted_row)[1] == restated
    assert (
        "\nsource_refs = "
        not in _row_block(_edition_dir(lifted.staged_registry, _PILOT, edition.revision_id), lifted_row)[1]
    )


def test_two_runs_over_one_tree_write_the_same_bytes(
    pilot: MigrationOutcome, pilot_input: Path, tmp_path: Path
) -> None:
    second = migrate_modelo(registry_root=pilot_input, modelo_id=_PILOT, work_dir=tmp_path / "second")
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


def test_a_lower_grade_successor_reuses_the_adjacent_storage_baseline(
    pilot: MigrationOutcome, pilot_input: Path, tmp_path: Path
) -> None:
    """Capability downgrade does not turn an otherwise exact storage delta into a root."""
    assert plan_migration(pilot_input / "modelos" / _PILOT, _load(pilot_input, _PILOT)).blocked_roots() == ()

    edition = _last_edition(pilot)
    planted = shutil.copytree(pilot_input, tmp_path / "registry" / "aeat")
    _lower_the_grade(_edition_dir(planted, _PILOT, edition.revision_id))

    plan = plan_migration(planted / "modelos" / _PILOT, _load(planted, _PILOT))
    changed = next(item for item in plan.editions if item.revision_id == edition.revision_id)
    assert changed.basis is PredecessorBasis.ADJACENT
    assert changed.predecessor is not None
    assert changed.blocked == ()

    outcome = migrate_modelo(registry_root=planted, modelo_id=_PILOT, work_dir=tmp_path / "work")
    assert outcome.staged_registry is not None
    hydrated = _load(outcome.staged_registry, _PILOT).revisions[edition.revision_id]
    assert str(hydrated.authority_grade) == "applicability"


def test_unannotated_rows_do_not_block_and_a_changed_same_id_uses_a_storage_override(tmp_path: Path) -> None:
    modelo_dir = tmp_path / "modelos" / "999"
    modelo_dir.mkdir(parents=True)
    write_standard_manifest(modelo_dir, "Storage fixture")
    legal_ref = "ley-58-2003:art-29"

    def write_revision(revision_id: str, year: int, *, changed_number: str) -> None:
        revision_dir = modelo_dir / "revisions" / revision_id
        (revision_dir / "casillas").mkdir(parents=True)
        (revision_dir / "revision.toml").write_text(
            f'[revisions."{revision_id}"]\nid = "{revision_id}"\nvalid_from = {year}-01-01\n'
            f'valid_to = {year}-12-31\nperiod_selector = {{ years = [{year}], periods = ["0A"] }}\n'
            f'orden_aplicabilidad = ["{legal_ref}"]\nlegal_refs = ["{legal_ref}"]\nsource_refs = ["aeat-manual"]\n',
            encoding="utf-8",
            newline="\n",
        )
        rows = (
            f'[[revisions."{revision_id}".casillas]]\nid = "0001"\nnumber = "{changed_number}"\n'
            f'section = ["liquidacion"]\nlegal_refs = ["{legal_ref}"]\nsource_refs = ["aeat-manual"]\n\n'
            f'[[revisions."{revision_id}".casillas]]\nid = "0002"\nnumber = "2"\n'
            f'section = ["liquidacion"]\nlegal_refs = ["{legal_ref}"]\nsource_refs = ["aeat-manual"]\n'
        )
        (revision_dir / "casillas" / "c0001__c0002.toml").write_text(rows, encoding="utf-8", newline="\n")

    write_revision("2024", 2024, changed_number="1")
    write_revision("2025", 2025, changed_number="11")
    plan = plan_migration(modelo_dir, load_modelo_directory(modelo_dir))

    successor = next(item for item in plan.editions if item.revision_id == "2025")
    assert successor.blocked == ()
    assert successor.stated_ids == ()
    assert successor.inherited_ids == ("0001", "0002")
    assert successor.casilla_overrides == (
        {
            "selector": {"revision": "2024", "id": "0001"},
            "fields": {"number": "11"},
            "removed_fields": [],
        },
    )


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

    unretired = plan_migration(planted / "modelos" / _PILOT, _load(planted, _PILOT))
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

    retired = migrate_modelo(registry_root=planted, modelo_id=_PILOT, work_dir=tmp_path / "work")

    assert next(item for item in retired.plan.editions if item.revision_id == revision_id).is_delta
    assert _unexpected(retired) == []
    assert retired.staged_registry is not None
    staged = _load(retired.staged_registry, _PILOT)
    # The retirement withdraws the lineage from the successor only; the
    # predecessor it is inherited from still carries the row.
    assert row_id not in {casilla.id for casilla in staged.revisions[revision_id].casillas}
    assert row_id in {casilla.id for casilla in staged.revisions[str(edition.predecessor)].casillas}


def test_a_blocked_full_copy_remains_a_baseline_for_independent_later_work(
    pilot: MigrationOutcome, pilot_before: ModeloDefinition, pilot_input: Path, tmp_path: Path
) -> None:
    """A failed transformation does not make the authored source unreadable."""
    blocked_candidate, later = pilot.plan.editions[-2:]
    assert blocked_candidate.is_delta and later.is_delta
    planted = shutil.copytree(pilot_input, tmp_path / "registry" / "aeat")
    blocked_dir = _edition_dir(planted, _PILOT, blocked_candidate.revision_id)
    row_id = _withdrawable_row(pilot_before, blocked_dir, blocked_candidate.inherited_ids)
    _drop_row(blocked_dir, row_id)
    before = {
        path.relative_to(blocked_dir).as_posix(): path.read_bytes() for path in blocked_dir.rglob("*") if path.is_file()
    }

    outcome = migrate_modelo(registry_root=planted, modelo_id=_PILOT, work_dir=tmp_path / "work")

    assert outcome.staged_registry is not None
    assert not outcome.complete
    assert blocked_candidate.revision_id in outcome.blocked
    assert any("unretired_withdrawal" in detail for detail in outcome.blocked[blocked_candidate.revision_id])
    assert later.revision_id in outcome.completed
    staged_blocked = _edition_dir(outcome.staged_registry, _PILOT, blocked_candidate.revision_id)
    assert before == {
        path.relative_to(staged_blocked).as_posix(): path.read_bytes()
        for path in staged_blocked.rglob("*")
        if path.is_file()
    }
    assert (
        tomllib.loads((staged_blocked / "revision.toml").read_text(encoding="utf-8"))["revisions"][
            blocked_candidate.revision_id
        ].get("predecessor")
        is None
    )


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

    plan = plan_migration(planted / "modelos" / _PILOT, _load(planted, _PILOT))

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


def test_invalid_staged_candidate_leaves_the_live_modelo_byte_identical(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path / "target", _PILOT)
    modelo_dir = registry / "modelos" / _PILOT
    before = {
        path.relative_to(modelo_dir).as_posix(): path.read_bytes() for path in modelo_dir.rglob("*") if path.is_file()
    }

    staged = shutil.copytree(registry, tmp_path / "staged" / "registry" / "aeat")
    revision = sorted((staged / "modelos" / _PILOT / "revisions").iterdir())[1]
    manifest = revision / "revision.toml"
    original_manifest = manifest.read_text(encoding="utf-8")
    invalid_manifest, count = re.subn(
        r'(?m)^(\[revisions\.(?:"[^"\n]+"|[^\]\n]+)\]\s*)$',
        r'\1\npredecessor = "missing-revision"',
        original_manifest,
        count=1,
    )
    assert count == 1
    manifest.write_text(
        invalid_manifest,
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(RegistryError, match="missing-revision"):
        _validate_staged_modelo(staged_root=staged, modelo_id=_PILOT)

    assert before == {
        path.relative_to(modelo_dir).as_posix(): path.read_bytes() for path in modelo_dir.rglob("*") if path.is_file()
    }


def test_the_command_line_renders_every_successors_export_bytes_from_the_canonical_scenarios(
    pilot_before: ModeloDefinition, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A dry run reads the declared scenarios, so every successor's bytes are compared and the proof is clean.

    The successors are read from the unmigrated definition, not from the run:
    every edition after the first is one the migration makes delta-authored,
    and each has an export surface, so each needs a scenario.
    """
    successors = sorted(str(revision.id) for revision in ordered_revisions(pilot_before)[1:])
    assert all(pilot_before.revisions[revision_id].export_layouts for revision_id in successors)
    assert set(edition_export_scenarios(_PILOT)) == set(successors)
    registry = _registry(tmp_path / "input", _PILOT)

    exit_code = main(["--registry-root", str(registry), "--modelo", _PILOT, "--work-dir", str(tmp_path / "work")])

    output = capsys.readouterr().out
    (summary,) = [line for line in output.splitlines() if line.startswith("summary ")]
    (persisted_line,) = [line for line in output.splitlines() if line.startswith("report persisted to ")]
    persisted = Path(persisted_line.removeprefix("report persisted to "))
    assert exit_code == 1, output
    assert " equivalence_status=passed " in summary, output
    assert " minimality_status=failed " in summary, output
    assert " source_status=accepted " in summary, output
    assert " publication_readiness_status=failed " in summary, output
    assert " publication_execution_status=not_performed " in summary, output
    assert " applied=False " in summary, output
    assert persisted.is_relative_to((REPO_ROOT / ".logs" / "audit-runs").resolve())
    assert persisted.is_file()
    assert "summary changed=True" in persisted.read_text(encoding="utf-8")
    assert not persisted.is_relative_to((tmp_path / "work").resolve())
    assert {str(r.id) for r in _load(registry, _PILOT).revisions.values() if r.predecessor is not None} == set()


def test_work_directory_must_not_be_inside_the_registry_root(tmp_path: Path) -> None:
    registry = _registry(tmp_path / "target", _NO_EXPORT_SURFACE)
    work_dir = registry / "migration-work"

    with pytest.raises(RegistryError, match="inside registry root"):
        migrate_modelo(registry_root=registry, modelo_id=_NO_EXPORT_SURFACE, work_dir=work_dir)

    assert not work_dir.exists()


def test_work_directory_must_not_be_inside_the_production_source_tree(tmp_path: Path) -> None:
    registry = _registry(tmp_path / "target", _NO_EXPORT_SURFACE)
    work_dir = REPO_ROOT / "src" / f".edition-delta-migration-test-work-{tmp_path.name}"

    assert not work_dir.exists()
    with pytest.raises(RegistryError, match="inside production source tree"):
        migrate_modelo(registry_root=registry, modelo_id=_NO_EXPORT_SURFACE, work_dir=work_dir)

    assert not work_dir.exists()


def test_work_directory_must_not_exist_before_migration(tmp_path: Path) -> None:
    registry = _registry(tmp_path / "target", _NO_EXPORT_SURFACE)
    work_dir = tmp_path / "existing-work"
    work_dir.mkdir()

    with pytest.raises(RegistryError, match="already exists"):
        migrate_modelo(registry_root=registry, modelo_id=_NO_EXPORT_SURFACE, work_dir=work_dir)


def test_migration_reports_use_unique_logs_runs_and_not_the_scratch_directory(tmp_path: Path) -> None:
    outcome = MigrationOutcome(
        plan=MigrationPlan(
            modelo_id="303",
            editions=(),
            already_delta_authored=False,
        ),
        staged_registry=None,
        report=None,
        applied=False,
        changed=False,
    )

    first = persist_migration_report(tmp_path, outcome, ("migration", "first"))
    second = persist_migration_report(tmp_path, outcome, ("migration", "second"))

    logs_root = (tmp_path / ".logs" / "audit-runs").resolve()
    assert first.is_relative_to(logs_root)
    assert second.is_relative_to(logs_root)
    assert first != second
    assert first.name == "report.md"
    assert second.name == "report.md"
    assert first.read_text(encoding="utf-8").startswith("command: migration first")
    assert second.read_text(encoding="utf-8").startswith("command: migration second")
    machine = json.loads((first.parent / "report.json").read_text(encoding="utf-8"))
    assert machine["outcomes"]["completed"] == []
    assert machine["outcomes"]["unchanged"] == []
    assert machine["outcomes"]["blocked"] == {}
    assert not machine["outcomes"]["complete"]
    assert machine["outcomes"]["equivalence"] == "passed"
    assert machine["outcomes"]["minimality"] == "incomplete"
    assert machine["outcomes"]["application"] == "not_applied"
    assert machine["measurements"] == {"before": None, "after": None}
    assert first.parent != second.parent
