"""Detector-teeth tests for the edition delta-authoring status screen.

Every test here plants its defect into a temporary registry tree and proves the
screen names it, then proves the clean tree next to it is silent. The live
corpus is read in exactly one test, and only to assert an invariant that holds
whatever the corpus contains -- never a count, which would decay the moment the
campaign this screen serves makes progress.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from ..edition_delta_status import (
    CONDITIONS,
    COVERAGE_CONDITIONS,
    MEASUREMENTS,
    _artifacts_dir,
    _signal_lines,
    _write_detail,
    build_report,
    coverage_gaps,
    edges,
    modelo_signals,
    scan_registry,
    supported_filing_years,
)


def _write_promise(root: Path, years: tuple[int, ...]) -> None:
    """Write the registry-wide supported-filing-years catalogue."""
    legal = root / "legal"
    legal.mkdir(parents=True, exist_ok=True)
    rendered = ", ".join(str(year) for year in years)
    (legal / "supported-filing-years.toml").write_text(
        f"[supported_filing_years]\nyears = [{rendered}]\n",
        encoding="utf-8",
    )


pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _write_edition(
    root: Path,
    modelo: str,
    edition: str,
    *,
    manifest: str,
    casillas: str,
    formulas: str = "",
) -> None:
    """Write one edition directory in the shape the directory loader expects."""
    edition_dir = root / "modelos" / modelo / "revisions" / edition
    (edition_dir / "casillas").mkdir(parents=True)
    (edition_dir / "revision.toml").write_text(f'[revisions."{edition}"]\n{manifest}\n', encoding="utf-8")
    (edition_dir / "casillas" / "0001-casillas.toml").write_text(casillas, encoding="utf-8")
    if formulas:
        (edition_dir / "formulas").mkdir()
        (edition_dir / "formulas" / "0001-formulas.toml").write_text(formulas, encoding="utf-8")


def _kinds(root: Path) -> list[str]:
    return [finding.kind for status in scan_registry(root) for finding in status.findings]


class TestEditionSourceDefault:
    """The screen derives the default through the migration tool's own function.

    The screen once carried a copy of the rule that omitted two clauses and
    disagreed with the tool on eight live editions. These plant each clause the
    copy lacked and prove the screen now reads what the tool would write.
    """

    def test_a_row_stating_no_source_refs_withholds_the_default(self, tmp_path: Path) -> None:
        """The clause the copy lacked: a default would ADD references to a silent row."""
        _write_edition(
            tmp_path,
            "999",
            "2025",
            manifest="valid_from = 2025-01-01",
            casillas=(
                '[[revisions."2025".casillas]]\nid = "01"\ncontinuidad_id = "c1"\nsource_refs = ["src-a"]\n\n'
                '[[revisions."2025".casillas]]\nid = "02"\ncontinuidad_id = "c2"\nsource_refs = ["src-a"]\n\n'
                '[[revisions."2025".casillas]]\nid = "03"\ncontinuidad_id = "c3"\n'
            ),
        )
        (status,) = scan_registry(tmp_path)
        assert status.effective_default == ()
        kinds = _kinds(tmp_path)
        assert "edition_default_underivable" in kinds
        assert "edition_default_undeclared" not in kinds

    def test_a_row_repeating_a_reference_does_not_open_a_run(self, tmp_path: Path) -> None:
        """The other clause: ``["a", "b", "a"]`` cannot be default plus additions."""
        _write_edition(
            tmp_path,
            "999",
            "2025",
            manifest="valid_from = 2025-01-01",
            casillas=(
                '[[revisions."2025".casillas]]\nid = "01"\ncontinuidad_id = "c1"\nsource_refs = ["a", "b", "a"]\n\n'
                '[[revisions."2025".casillas]]\nid = "02"\ncontinuidad_id = "c2"\nsource_refs = ["a", "b", "a"]\n'
            ),
        )
        (status,) = scan_registry(tmp_path)
        assert status.effective_default == ()

    def test_the_longest_run_shared_by_every_row_is_the_default(self, tmp_path: Path) -> None:
        _write_edition(
            tmp_path,
            "999",
            "2025",
            manifest="valid_from = 2025-01-01",
            casillas=(
                '[[revisions."2025".casillas]]\nid = "01"\ncontinuidad_id = "c1"\nsource_refs = ["a", "b", "c"]\n\n'
                '[[revisions."2025".casillas]]\nid = "02"\ncontinuidad_id = "c2"\nsource_refs = ["a", "b", "d"]\n'
            ),
        )
        (status,) = scan_registry(tmp_path)
        assert status.effective_default == ("a", "b")


class TestRestatementConditions:
    """Each restatement rule, planted and detected."""

    def test_a_row_repeating_the_declared_default_is_named(self, tmp_path: Path) -> None:
        _write_edition(
            tmp_path,
            "999",
            "2025",
            manifest='casilla_source_refs = ["src-a"]',
            casillas=(
                '[[revisions."2025".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n'
                'source_refs = ["src-a"]\n\n'
                '[[revisions."2025".casillas]]\nid = "02"\ncontinuidad_id = "c2"\n'
                'source_refs = ["src-a"]\n'
            ),
        )
        assert _kinds(tmp_path).count("row_source_refs_restated") == 2

    def test_a_row_extending_the_default_is_liftable_not_restated(self, tmp_path: Path) -> None:
        _write_edition(
            tmp_path,
            "999",
            "2025",
            manifest='casilla_source_refs = ["src-a"]',
            casillas=(
                '[[revisions."2025".casillas]]\nid = "01"\ncontinuidad_id = "c1"\nsource_refs = ["src-a", "src-b"]\n'
            ),
        )
        kinds = _kinds(tmp_path)
        assert "row_source_refs_liftable" in kinds
        assert "row_source_refs_restated" not in kinds

    def test_a_row_the_default_cannot_reproduce_is_measured_not_a_finding(self, tmp_path: Path) -> None:
        """An irreducible value is kept whole by design and must not read as a defect."""
        _write_edition(
            tmp_path,
            "999",
            "2025",
            manifest='casilla_source_refs = ["src-a"]',
            casillas=('[[revisions."2025".casillas]]\nid = "01"\ncontinuidad_id = "c1"\nsource_refs = ["src-z"]\n'),
        )
        kinds = _kinds(tmp_path)
        assert "row_source_refs_irreducible" in kinds
        assert "row_source_refs_irreducible" in MEASUREMENTS
        assert "row_source_refs_irreducible" not in CONDITIONS

    def test_a_constraints_table_is_counted_apart_from_its_row(self, tmp_path: Path) -> None:
        """A sweep reading only rows understates the surface; prove both are seen."""
        _write_edition(
            tmp_path,
            "999",
            "2025",
            manifest='casilla_source_refs = ["src-a"]',
            casillas=(
                '[[revisions."2025".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n'
                'source_refs = ["src-a"]\n\n'
                '[revisions."2025".casillas.constraints]\nsource_refs = ["src-a"]\n'
            ),
        )
        kinds = _kinds(tmp_path)
        assert "row_source_refs_restated" in kinds
        assert "constraints_source_refs_restated" in kinds

    def test_legal_refs_equal_to_the_orden_are_named(self, tmp_path: Path) -> None:
        _write_edition(
            tmp_path,
            "999",
            "2025",
            manifest='orden_aplicabilidad = ["orden-x:art-1"]\ncasilla_source_refs = ["src-a"]',
            casillas=(
                '[[revisions."2025".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n'
                'legal_refs = ["orden-x:art-1"]\nsource_refs = ["src-a"]\n'
            ),
        )
        assert "row_legal_refs_equal_orden" in _kinds(tmp_path)

    def test_a_derivable_but_undeclared_default_is_named(self, tmp_path: Path) -> None:
        _write_edition(
            tmp_path,
            "999",
            "2025",
            manifest="valid_from = 2025-01-01",
            casillas=(
                '[[revisions."2025".casillas]]\nid = "01"\ncontinuidad_id = "c1"\nsource_refs = ["src-a"]\n\n'
                '[[revisions."2025".casillas]]\nid = "02"\ncontinuidad_id = "c2"\nsource_refs = ["src-a"]\n'
            ),
        )
        assert "edition_default_undeclared" in _kinds(tmp_path)


class TestCanaries:
    """Classes that read clean on the live corpus, proven still able to fire."""

    def test_an_authored_export_refs_is_refused_as_a_derived_field(self, tmp_path: Path) -> None:
        _write_edition(
            tmp_path,
            "999",
            "2025",
            manifest='casilla_source_refs = ["src-a"]',
            casillas=('[[revisions."2025".casillas]]\nid = "01"\ncontinuidad_id = "c1"\nexport_refs = ["rec.field"]\n'),
        )
        assert "derived_field_authored" in _kinds(tmp_path)

    def test_a_key_in_neither_vocabulary_is_named(self, tmp_path: Path) -> None:
        _write_edition(
            tmp_path,
            "999",
            "2025",
            manifest='casilla_source_refs = ["src-a"]',
            casillas='[[revisions."2025".casillas]]\nid = "01"\ncontinuidad_id = "c1"\ninvented_key = "x"\n',
        )
        assert "unknown_authoring_key" in _kinds(tmp_path)

    def test_the_authoring_only_key_is_not_reported_as_unknown(self, tmp_path: Path) -> None:
        """`additional_source_refs` is legal in a fragment though absent from the typed model."""
        _write_edition(
            tmp_path,
            "999",
            "2025",
            manifest='casilla_source_refs = ["src-a"]',
            casillas=(
                '[[revisions."2025".casillas]]\nid = "01"\ncontinuidad_id = "c1"\nadditional_source_refs = ["src-b"]\n'
            ),
        )
        assert "unknown_authoring_key" not in _kinds(tmp_path)


class TestEditionKeyedIdentifiers:
    """Whole-token matching, which is the whole difference from a substring sweep."""

    def test_an_identifier_carrying_the_edition_year_is_named(self, tmp_path: Path) -> None:
        _write_edition(
            tmp_path,
            "999",
            "2025",
            manifest='casilla_source_refs = ["src-a"]',
            casillas='[[revisions."2025".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n',
            formulas='[[revisions."2025".formulas]]\nid = "modelo-999-2025-total"\n',
        )
        assert "edition_keyed_identifier" in _kinds(tmp_path)

    def test_a_two_digit_period_token_is_not_an_edition_key(self, tmp_path: Path) -> None:
        """``09`` in ``2024-desde-09-y-3t`` is a period; an identifier naming box 09 is not keyed."""
        _write_edition(
            tmp_path,
            "999",
            "2024-desde-09-y-3t",
            manifest='casilla_source_refs = ["src-a"]',
            casillas='[[revisions."2024-desde-09-y-3t".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n',
            formulas='[[revisions."2024-desde-09-y-3t".formulas]]\nid = "modelo-999-dr999-09-projection"\n',
        )
        assert "edition_keyed_identifier" not in _kinds(tmp_path)

    def test_a_year_inside_an_offset_range_is_not_an_edition_key(self, tmp_path: Path) -> None:
        """``2001-2017`` in edition ``2016-2017`` is a range the box carries, not the edition."""
        _write_edition(
            tmp_path,
            "999",
            "2016-2017",
            manifest='casilla_source_refs = ["src-a"]',
            casillas='[[revisions."2016-2017".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n',
            formulas=(
                '[[revisions."2016-2017".formulas]]\nid = "modelo-999.page_02.2001-2017.valor"\n\n'
                '[[revisions."2016-2017".formulas]]\nid = "modelo-999-2017-total"\n'
            ),
        )
        assert _kinds(tmp_path).count("edition_keyed_identifier") == 1

    def test_a_legal_reference_year_inside_an_identifier_is_not_named(self, tmp_path: Path) -> None:
        """The defect a substring sweep produces: 1992 is a norm's year, not this edition."""
        _write_edition(
            tmp_path,
            "999",
            "2025",
            manifest='casilla_source_refs = ["src-a"]',
            casillas='[[revisions."2025".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n',
            formulas='[[revisions."2025".formulas]]\nid = "rd-1624-1992-art-71-total"\n',
        )
        assert "edition_keyed_identifier" not in _kinds(tmp_path)


class TestEdges:
    """Edge state, where the four outcomes must not be pooled."""

    def _two_editions(self, root: Path, *, successor_manifest: str, predecessor_lineage: bool) -> None:
        lineage = 'continuidad_id = "c1"\n' if predecessor_lineage else ""
        _write_edition(
            root,
            "999",
            "2024",
            manifest='valid_from = 2024-01-01\nauthority_grade = "filing"\ncasilla_source_refs = ["src-a"]',
            casillas=f'[[revisions."2024".casillas]]\nid = "01"\n{lineage}',
        )
        _write_edition(
            root,
            "999",
            "2025",
            manifest=successor_manifest,
            casillas='[[revisions."2025".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n',
        )

    def test_a_successor_declaring_a_predecessor_is_migrated(self, tmp_path: Path) -> None:
        self._two_editions(
            tmp_path,
            successor_manifest=(
                'valid_from = 2025-01-01\nauthority_grade = "filing"\n'
                'predecessor = "2024"\ncasilla_source_refs = ["src-a"]'
            ),
            predecessor_lineage=True,
        )
        assert [edge.state for edge in edges(scan_registry(tmp_path))] == ["migrated"]

    def test_a_predecessor_row_without_lineage_blocks_the_edge(self, tmp_path: Path) -> None:
        self._two_editions(
            tmp_path,
            successor_manifest='valid_from = 2025-01-01\nauthority_grade = "filing"\ncasilla_source_refs = ["src-a"]',
            predecessor_lineage=False,
        )
        found = edges(scan_registry(tmp_path))
        assert [edge.state for edge in found] == ["blocked"]
        assert found[0].blockers == ("predecessor_lineage_missing=1",)

    def test_a_complete_predecessor_leaves_the_edge_ready(self, tmp_path: Path) -> None:
        self._two_editions(
            tmp_path,
            successor_manifest='valid_from = 2025-01-01\nauthority_grade = "filing"\ncasilla_source_refs = ["src-a"]',
            predecessor_lineage=True,
        )
        assert [edge.state for edge in edges(scan_registry(tmp_path))] == ["ready"]

    def test_an_explicit_no_predecessor_is_dispositioned_not_blocked(self, tmp_path: Path) -> None:
        """A `[...predecessor.none]` table is a recorded outcome, never outstanding work.

        Reading it as enrollment would report a parallel scheme variant as
        migrated; reading it as absent would report it as work that remains.
        """
        self._two_editions(
            tmp_path,
            successor_manifest=(
                'valid_from = 2025-01-01\nauthority_grade = "filing"\ncasilla_source_refs = ["src-a"]\n'
                '[revisions."2025".predecessor.none]\nreason = "parallel scheme variant"'
            ),
            predecessor_lineage=False,
        )
        assert [edge.state for edge in edges(scan_registry(tmp_path))] == ["dispositioned"]

    def test_a_successor_withholding_by_design_blocks_the_edge(self, tmp_path: Path) -> None:
        self._two_editions(
            tmp_path,
            successor_manifest=(
                'valid_from = 2025-01-01\nauthority_grade = "advisory"\ncasilla_source_refs = ["src-a"]'
            ),
            predecessor_lineage=True,
        )
        found = edges(scan_registry(tmp_path))
        assert found[0].blockers == ("successor_withholds_by_design",)

    _READY_SUCCESSOR = 'valid_from = 2025-01-01\nauthority_grade = "filing"\ncasilla_source_refs = ["src-a"]'
    _READY_PREDECESSOR = 'valid_from = 2024-01-01\nauthority_grade = "filing"\ncasilla_source_refs = ["src-a"]'

    def test_a_predecessor_lineage_the_successor_drops_without_retiring_blocks(self, tmp_path: Path) -> None:
        """The tool refuses an absence that is not an authored retirement."""
        _write_edition(
            tmp_path,
            "999",
            "2024",
            manifest=self._READY_PREDECESSOR,
            casillas=(
                '[[revisions."2024".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n\n'
                '[[revisions."2024".casillas]]\nid = "02"\ncontinuidad_id = "c2"\n'
            ),
        )
        _write_edition(
            tmp_path,
            "999",
            "2025",
            manifest=self._READY_SUCCESSOR,
            casillas='[[revisions."2025".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n',
        )
        (edge,) = edges(scan_registry(tmp_path))
        assert edge.state == "blocked"
        assert edge.blockers == ("unretired_withdrawal=1",)

    def test_a_retired_lineage_is_not_a_withdrawal(self, tmp_path: Path) -> None:
        _write_edition(
            tmp_path,
            "999",
            "2024",
            manifest=self._READY_PREDECESSOR,
            casillas=(
                '[[revisions."2024".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n\n'
                '[[revisions."2024".casillas]]\nid = "02"\ncontinuidad_id = "c2"\n'
            ),
        )
        _write_edition(
            tmp_path,
            "999",
            "2025",
            manifest=(
                self._READY_SUCCESSOR + '\n[[revisions."2025".casilla_continuidad_evolutions]]\n'
                'continuidad_id = "c2"\nevolution_kind = "retired"\nto_revision = "2025"'
            ),
            casillas='[[revisions."2025".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n',
        )
        (edge,) = edges(scan_registry(tmp_path))
        assert edge.state == "ready"

    def test_a_row_reusing_an_id_under_another_lineage_blocks(self, tmp_path: Path) -> None:
        _write_edition(
            tmp_path,
            "999",
            "2024",
            manifest=self._READY_PREDECESSOR,
            casillas='[[revisions."2024".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n',
        )
        _write_edition(
            tmp_path,
            "999",
            "2025",
            manifest=(
                self._READY_SUCCESSOR + '\n[[revisions."2025".casilla_continuidad_evolutions]]\n'
                'continuidad_id = "c1"\nevolution_kind = "retired"\nto_revision = "2025"'
            ),
            casillas='[[revisions."2025".casillas]]\nid = "01"\ncontinuidad_id = "c9"\n',
        )
        (edge,) = edges(scan_registry(tmp_path))
        assert edge.blockers == ("undeclared_repurpose=1",)

    def test_a_lineage_carried_twice_blocks(self, tmp_path: Path) -> None:
        _write_edition(
            tmp_path,
            "999",
            "2024",
            manifest=self._READY_PREDECESSOR,
            casillas='[[revisions."2024".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n',
        )
        _write_edition(
            tmp_path,
            "999",
            "2025",
            manifest=self._READY_SUCCESSOR,
            casillas=(
                '[[revisions."2025".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n\n'
                '[[revisions."2025".casillas]]\nid = "02"\ncontinuidad_id = "c1"\n'
            ),
        )
        (edge,) = edges(scan_registry(tmp_path))
        assert edge.blockers == ("ambiguous_lineage",)

    def test_an_export_surface_without_a_scenario_blocks_apply(self, tmp_path: Path) -> None:
        """The tool refuses to publish bytes it cannot compare."""
        _write_edition(
            tmp_path,
            "999",
            "2024",
            manifest=self._READY_PREDECESSOR,
            casillas='[[revisions."2024".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n',
        )
        _write_edition(
            tmp_path,
            "999",
            "2025",
            manifest=self._READY_SUCCESSOR,
            casillas='[[revisions."2025".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n',
        )
        export = tmp_path / "modelos" / "999" / "revisions" / "2025" / "export"
        export.mkdir()
        (export / "0001-layout.toml").write_text('[[revisions."2025".export_layouts]]\nid = "x"\n', encoding="utf-8")
        (edge,) = edges(scan_registry(tmp_path))
        assert edge.blockers == ("export_scenario_missing",)

    def test_a_migrated_predecessor_is_walked_to_its_inherited_rows(self, tmp_path: Path) -> None:
        """A delta edition states only its delta; as a predecessor it holds the whole chain.

        Without the walk, the rows it inherits read as missing from it, and the
        edge after it reads as a withdrawal of every inherited lineage.
        """
        _write_edition(
            tmp_path,
            "999",
            "2023",
            manifest='valid_from = 2023-01-01\nauthority_grade = "filing"\ncasilla_source_refs = ["src-a"]',
            casillas=(
                '[[revisions."2023".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n\n'
                '[[revisions."2023".casillas]]\nid = "02"\ncontinuidad_id = "c2"\n'
            ),
        )
        _write_edition(
            tmp_path,
            "999",
            "2024",
            manifest=self._READY_PREDECESSOR + '\npredecessor = "2023"',
            casillas='[[revisions."2024".casillas]]\nid = "02"\ncontinuidad_id = "c2"\nrequired = true\n',
        )
        _write_edition(
            tmp_path,
            "999",
            "2025",
            manifest=self._READY_SUCCESSOR,
            casillas=(
                '[[revisions."2025".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n\n'
                '[[revisions."2025".casillas]]\nid = "02"\ncontinuidad_id = "c2"\n'
            ),
        )
        first, second = edges(scan_registry(tmp_path))
        assert first.state == "migrated"
        assert second.state == "ready"
        assert second.predecessor_rows == 2


class TestLiveCorpus:
    """One invariant over the shipped tree, stated so it cannot decay into a count."""

    def test_every_reported_kind_is_a_declared_condition_or_measurement(self) -> None:
        from ..edition_delta_status import _bundled_registry_root

        statuses = scan_registry(_bundled_registry_root())
        assert statuses, "the bundled registry declares at least one edition"
        declared = frozenset((*CONDITIONS, *MEASUREMENTS))
        reported = {finding.kind for status in statuses for finding in status.findings}
        assert reported <= declared, f"undeclared kinds emitted: {sorted(reported - declared)}"


class TestSignal:
    """The signal's contract: deterministic, and a real change moves it."""

    def _corpus(self, root: Path, *, lifted: bool) -> None:
        manifest = 'valid_from = 2025-01-01\nauthority_grade = "filing"'
        if lifted:
            manifest += '\ncasilla_source_refs = ["src-a"]'
        row_refs = "" if lifted else 'source_refs = ["src-a"]\n'
        _write_edition(
            root,
            "999",
            "2025",
            manifest=manifest,
            casillas=(
                f'[[revisions."2025".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n{row_refs}\n'
                f'[[revisions."2025".casillas]]\nid = "02"\ncontinuidad_id = "c2"\n{row_refs}'
            ),
        )

    def test_the_signal_is_byte_identical_across_runs(self, tmp_path: Path) -> None:
        """A signal that churns between runs cannot be read as a delta."""
        self._corpus(tmp_path, lifted=False)
        first = _signal_lines(build_report(tmp_path))
        second = _signal_lines(build_report(tmp_path))
        assert first == second

    def test_lifting_an_edition_moves_the_signal_and_nothing_else(self, tmp_path: Path) -> None:
        before = tmp_path / "before"
        after = tmp_path / "after"
        self._corpus(before, lifted=False)
        self._corpus(after, lifted=True)
        moved = set(_signal_lines(build_report(before))) ^ set(_signal_lines(build_report(after)))
        assert any(line.startswith("action ") for line in moved)
        assert any(line.startswith("modelo 999 ") for line in moved)
        assert not any(line.startswith("corpus ") for line in moved), "row and edition counts must not move"

    def test_every_signal_line_is_a_declared_record_type(self, tmp_path: Path) -> None:
        """Each line must parse as `<record> ...` from a closed vocabulary."""
        self._corpus(tmp_path, lifted=False)
        declared = {
            "#",
            "corpus",
            "promise",
            "coverage",
            "edge",
            "action",
            "blocker",
            "clean",
            "condition",
            "measurement",
            "modelo",
            "uncovered",
            "ready",
            "blocked",
        }
        emitted = {line.split(" ", 1)[0] for line in _signal_lines(build_report(tmp_path))}
        assert emitted <= declared, f"undeclared record types: {sorted(emitted - declared)}"

    def test_a_fully_migrated_and_lifted_modelo_reports_done(self, tmp_path: Path) -> None:
        """`done` requires both halves: no unmigrated edge AND no unlifted edition."""
        _write_edition(
            tmp_path,
            "999",
            "2024",
            manifest='valid_from = 2024-01-01\nauthority_grade = "filing"\ncasilla_source_refs = ["src-a"]',
            casillas='[[revisions."2024".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n',
        )
        _write_edition(
            tmp_path,
            "999",
            "2025",
            manifest=(
                'valid_from = 2025-01-01\nauthority_grade = "filing"\n'
                'predecessor = "2024"\ncasilla_source_refs = ["src-a"]'
            ),
            casillas='[[revisions."2025".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n',
        )
        (signal,) = modelo_signals(build_report(tmp_path))
        assert signal.state == "done"
        assert signal.outstanding == 0

    def test_a_migrated_but_restating_modelo_is_not_done(self, tmp_path: Path) -> None:
        """Migration alone must not retire the restatement work that remains."""
        _write_edition(
            tmp_path,
            "999",
            "2024",
            manifest='valid_from = 2024-01-01\nauthority_grade = "filing"',
            casillas=(
                '[[revisions."2024".casillas]]\nid = "01"\ncontinuidad_id = "c1"\nsource_refs = ["src-a"]\n\n'
                '[[revisions."2024".casillas]]\nid = "02"\ncontinuidad_id = "c2"\nsource_refs = ["src-a"]\n'
            ),
        )
        _write_edition(
            tmp_path,
            "999",
            "2025",
            manifest='valid_from = 2025-01-01\nauthority_grade = "filing"\npredecessor = "2024"',
            casillas='[[revisions."2025".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n',
        )
        (signal,) = modelo_signals(build_report(tmp_path))
        assert signal.state == "migrated_unlifted"
        assert signal.outstanding > 0


class TestCoverageProjection:
    """The registry's promise, projected against what the corpus can select."""

    def _edition(self, root: Path, edition: str, selector: str, periods: str = '"0A"') -> None:
        _write_edition(
            root,
            "999",
            edition,
            manifest=(
                f"valid_from = {edition[:4]}-01-01\n"
                f'authority_grade = "filing"\ncasilla_source_refs = ["src-a"]\n'
                f"period_selector = {{ {selector}, periods = [{periods}] }}"
            ),
            casillas=f'[[revisions."{edition}".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n',
        )

    def test_the_promise_is_read_from_the_registry_not_assumed(self, tmp_path: Path) -> None:
        _write_promise(tmp_path, (2022, 2023))
        assert supported_filing_years(tmp_path) == (2022, 2023)

    def test_no_promise_file_yields_no_coverage_findings(self, tmp_path: Path) -> None:
        """Absent a declared promise there is nothing to measure against, and
        inventing one would manufacture gaps the registry never claimed."""
        self._edition(tmp_path, "2025", "year_from = 2025, year_to = 2025")
        report = build_report(tmp_path)
        assert report.promised_years == ()
        assert report.gaps == ()

    def test_a_promised_year_no_edition_admits_is_named(self, tmp_path: Path) -> None:
        _write_promise(tmp_path, (2024, 2025))
        self._edition(tmp_path, "2025", "year_from = 2025, year_to = 2025")
        gaps = build_report(tmp_path).gaps
        assert [(gap.filing_year, gap.kind) for gap in gaps] == [(2024, "promised_year_unserved")]

    def test_an_open_ended_selector_serves_every_later_promised_year(self, tmp_path: Path) -> None:
        """`year_to` absent means open-ended; `valid_to` absent alone does not."""
        _write_promise(tmp_path, (2024, 2025, 2026))
        self._edition(tmp_path, "2024", "year_from = 2024")
        assert build_report(tmp_path).gaps == ()

    def test_a_selector_with_no_year_bound_admits_nothing(self, tmp_path: Path) -> None:
        """The trap this must not approximate away: no bound is not 'all years'."""
        _write_promise(tmp_path, (2025,))
        self._edition(tmp_path, "2025", 'periods_placeholder = "x"')
        gaps = build_report(tmp_path).gaps
        assert [gap.kind for gap in gaps] == ["promised_year_unserved"]

    def test_a_period_served_in_one_year_but_not_another_is_a_coordinate_gap(self, tmp_path: Path) -> None:
        _write_promise(tmp_path, (2024, 2025))
        self._edition(tmp_path, "2024", "year_from = 2024, year_to = 2024", periods='"0A"')
        self._edition(tmp_path, "2025", "year_from = 2025, year_to = 2025", periods='"0A", "1T"')
        gaps = build_report(tmp_path).gaps
        assert [(gap.filing_year, gap.period, gap.kind) for gap in gaps] == [
            (2024, "1T", "promised_coordinate_unserved")
        ]

    def test_two_editions_admitting_one_cell_is_named_as_ambiguous(self, tmp_path: Path) -> None:
        """`select_revision` refuses such a cell when no date narrows it."""
        _write_promise(tmp_path, (2025,))
        self._edition(tmp_path, "2025", "year_from = 2025, year_to = 2025")
        self._edition(tmp_path, "2025-bis", "year_from = 2025, year_to = 2025")
        gaps = build_report(tmp_path).gaps
        assert [gap.kind for gap in gaps] == ["coordinate_served_twice"]
        assert set(gaps[0].editions) == {"2025", "2025-bis"}

    def test_a_coverage_gap_is_reported_beside_the_shape_verdict_not_inside_it(self, tmp_path: Path) -> None:
        """Migration cannot move a coverage gap, so it must not hold the shape signal open."""
        _write_promise(tmp_path, (2024, 2025))
        _write_edition(
            tmp_path,
            "999",
            "2025",
            manifest=(
                'valid_from = 2025-01-01\nauthority_grade = "filing"\ncasilla_source_refs = ["src-a"]\n'
                'period_selector = { year_from = 2025, year_to = 2025, periods = ["0A"] }'
            ),
            casillas='[[revisions."2025".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n',
        )
        (signal,) = modelo_signals(build_report(tmp_path))
        assert signal.state == "single_edition"
        assert signal.coverage_gaps == 1
        assert signal.outstanding == 0

    def test_coverage_conditions_are_declared_conditions(self) -> None:
        assert set(COVERAGE_CONDITIONS) <= set(CONDITIONS)

    def test_coverage_gaps_need_a_promise_to_measure_against(self, tmp_path: Path) -> None:
        self._edition(tmp_path, "2025", "year_from = 2025, year_to = 2025")
        assert coverage_gaps(scan_registry(tmp_path), ()) == ()


class TestPersistedDetail:
    """The artifacts path, which only fires when a run directory is set."""

    def _corpus(self, root: Path) -> None:
        _write_promise(root, (2024, 2025))
        _write_edition(
            root,
            "999",
            "2025",
            manifest=(
                'valid_from = 2025-01-01\nauthority_grade = "filing"\n'
                'period_selector = { year_from = 2025, year_to = 2025, periods = ["0A"] }'
            ),
            casillas=(
                '[[revisions."2025".casillas]]\nid = "01"\ncontinuidad_id = "c1"\nsource_refs = ["src-a"]\n\n'
                '[[revisions."2025".casillas]]\nid = "02"\ncontinuidad_id = "c2"\nsource_refs = ["src-a"]\n'
            ),
        )

    def test_the_detail_files_are_written_and_parse(self, tmp_path: Path) -> None:
        """Regression: this path takes the report, not the raw statuses, and is
        reached only with an artifacts directory set -- so a direct run cannot
        exercise it and the type error it once carried escaped every other test.
        """
        root = tmp_path / "registry"
        out = tmp_path / "artifacts"
        self._corpus(root)
        report = build_report(root)
        signal_path, findings_path = _write_detail(out, report)

        payload = json.loads(signal_path.read_text(encoding="utf-8"))
        assert payload["promised_filing_years"] == [2024, 2025]
        assert payload["census"]["row_source_refs_restated"] == 2

        rows = [json.loads(line) for line in findings_path.read_text(encoding="utf-8").splitlines()]
        assert rows, "the findings file carries the population"
        assert {"modelo", "edition", "kind", "locus", "detail"} == set(rows[0])

    def test_coverage_gaps_reach_the_findings_file(self, tmp_path: Path) -> None:
        """A gap is modelo-scoped, so it must not be dropped by an edition-scoped writer."""
        root = tmp_path / "registry"
        out = tmp_path / "artifacts"
        self._corpus(root)
        _, findings_path = _write_detail(out, build_report(root))
        rows = [json.loads(line) for line in findings_path.read_text(encoding="utf-8").splitlines()]
        gaps = [row for row in rows if row["kind"] in COVERAGE_CONDITIONS]
        assert [(row["locus"], row["edition"]) for row in gaps] == [("2024/*", "<modelo>")]

    def test_nothing_is_written_without_a_directory(self, tmp_path: Path) -> None:
        """A screen invoked by hand prints its signal and leaves no files behind."""
        assert _artifacts_dir(None) is None or os.environ.get("CADRUMO_DEV_ARTIFACTS_DIR")
