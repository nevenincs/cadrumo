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

from ..coverage_dispositions import CLASSIFICATIONS, CoverageDisposition, load_coverage_dispositions
from ..edition_delta_status import (
    _LIMITATIONS,
    CONDITIONS,
    COVERAGE_CONDITIONS,
    LINEAGE_SCOPES,
    MEASUREMENTS,
    Edge,
    _artifacts_dir,
    _signal_lines,
    _write_detail,
    build_report,
    coverage_gaps,
    edges,
    ledger_scope,
    modelo_signals,
    projected_sources,
    render_report,
    scan_registry,
    supported_filing_years,
)


def _write_promise(root: Path, years: tuple[int, ...]) -> None:
    """Write the registry-wide supported-filing-years catalogue."""
    legal = root / "legal"
    legal.mkdir(parents=True, exist_ok=True)
    (legal / "supported-filing-years.toml").write_text(
        f"[supported_filing_years]\nfloor = {min(years)}\nhorizon = {max(years)}\n",
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


class TestUnionFamilies:
    """The union rule measured per family, planted and detected."""

    _FIRST = 'valid_from = 2024-01-01\nauthority_grade = "filing"\ncasilla_source_refs = ["src-a"]'
    _NEXT = 'valid_from = 2025-01-01\nauthority_grade = "filing"\ncasilla_source_refs = ["src-a"]'

    def _bindings_edition(self, root: Path, edition: str, manifest: str, binding_rows: str) -> None:
        _write_edition(
            root,
            "999",
            edition,
            manifest=manifest,
            casillas=f'[[revisions."{edition}".casillas]]\nid = "{edition}"\ncontinuidad_id = "c{edition}"\n',
        )
        bindings = root / "modelos" / "999" / "revisions" / edition / "bindings"
        bindings.mkdir()
        (bindings / "0001-bindings.toml").write_text(binding_rows, encoding="utf-8")

    def test_an_identical_binding_restated_by_a_successor_is_named(self, tmp_path: Path) -> None:
        row = 'id = "b1"\nprovider = { kind = "manual" }\nvalue = { data_type = "money", channel = "decimal" }\n'
        self._bindings_edition(tmp_path, "2024", self._FIRST, f'[[revisions."2024".bindings]]\n{row}')
        self._bindings_edition(tmp_path, "2025", self._NEXT, f'[[revisions."2025".bindings]]\n{row}')
        report = build_report(tmp_path)
        (edge,) = report.edges
        assert dict(edge.restated_members) == {"bindings": 1}
        assert any(
            f.kind == "member_restated" and f.locus == "bindings/b1" for s in report.statuses for f in s.findings
        )
        assert any(line.startswith("family bindings members=2 restated=1") for line in _signal_lines(report))

    def test_a_binding_that_differs_is_not_restated(self, tmp_path: Path) -> None:
        self._bindings_edition(
            tmp_path, "2024", self._FIRST, '[[revisions."2024".bindings]]\nid = "b1"\nprovider = { kind = "manual" }\n'
        )
        self._bindings_edition(
            tmp_path, "2025", self._NEXT, '[[revisions."2025".bindings]]\nid = "b1"\nprovider = { kind = "profile" }\n'
        )
        (edge,) = build_report(tmp_path).edges
        assert edge.restated_members == ()

    def test_a_binding_differing_only_in_refs_is_restated(self, tmp_path: Path) -> None:
        """References are lifted before comparison: they are what restatement is made of."""
        self._bindings_edition(
            tmp_path,
            "2024",
            self._FIRST,
            '[[revisions."2024".bindings]]\nid = "b1"\nprovider = { kind = "manual" }\nsource_refs = ["dr-2024"]\n',
        )
        self._bindings_edition(
            tmp_path,
            "2025",
            self._NEXT,
            '[[revisions."2025".bindings]]\nid = "b1"\nprovider = { kind = "manual" }\nsource_refs = ["dr-2025"]\n',
        )
        (edge,) = build_report(tmp_path).edges
        assert dict(edge.restated_members) == {"bindings": 1}

    def test_a_derivable_binding_default_the_manifest_lacks_is_named(self, tmp_path: Path) -> None:
        rows = (
            '[[revisions."2024".bindings]]\nid = "b1"\nsource_refs = ["dr-2024"]\n\n'
            '[[revisions."2024".bindings]]\nid = "b2"\nsource_refs = ["dr-2024"]\n'
        )
        self._bindings_edition(tmp_path, "2024", self._FIRST, rows)
        kinds = [(f.kind, f.locus) for s in scan_registry(tmp_path) for f in s.findings]
        assert ("family_default_undeclared", "bindings") in kinds

    def test_a_declared_binding_default_is_not_named(self, tmp_path: Path) -> None:
        rows = (
            '[[revisions."2024".bindings]]\nid = "b1"\nsource_refs = ["dr-2024"]\n\n'
            '[[revisions."2024".bindings]]\nid = "b2"\nsource_refs = ["dr-2024"]\n'
        )
        self._bindings_edition(tmp_path, "2024", self._FIRST + '\nbinding_source_refs = ["dr-2024"]', rows)
        assert "family_default_undeclared" not in _kinds(tmp_path)

    def test_a_family_without_an_identity_field_is_named_once(self, tmp_path: Path) -> None:
        _write_edition(
            tmp_path,
            "999",
            "2024",
            manifest=self._FIRST,
            casillas='[[revisions."2024".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n',
        )
        section = tmp_path / "modelos" / "999" / "revisions" / "2024" / "projection_endpoints"
        section.mkdir()
        (section / "0001.toml").write_text(
            '[[revisions."2024".projection_endpoints]]\ncasilla_id = "01"\n\n'
            '[[revisions."2024".projection_endpoints]]\ncasilla_id = "02"\n',
            encoding="utf-8",
        )
        findings = [f for s in scan_registry(tmp_path) for f in s.findings if f.kind == "family_without_identity"]
        assert [(f.locus, f.detail.split(" ")[0]) for f in findings] == [("projection_endpoints", "2")]

    def test_casillas_under_a_root_are_measured_and_under_a_predecessor_are_not(self, tmp_path: Path) -> None:
        """Inheritance is what removes restatement; a root inherits nothing, so its copies count."""
        row = 'id = "01"\ncontinuidad_id = "c1"\ndata_type = "money"\n'
        _write_edition(tmp_path, "999", "2024", manifest=self._FIRST, casillas=f'[[revisions."2024".casillas]]\n{row}')
        _write_edition(
            tmp_path,
            "999",
            "2025",
            manifest=(
                self._NEXT + '\n[revisions."2025".predecessor.none]\nreason = "Stated in full: this edition cannot be '
                'materialised exactly from the edition before it (predecessor row without lineage)."'
            ),
            casillas=f'[[revisions."2025".casillas]]\n{row}',
        )
        report = build_report(tmp_path)
        (edge,) = report.edges
        assert edge.state == "dispositioned"
        assert edge.root_kind == "root_pending_lineage"
        assert dict(edge.restated_members) == {"casillas": 1}
        (signal,) = modelo_signals(report)
        assert signal.state == "rooted"
        assert signal.outstanding == 2

    def test_a_root_by_law_is_terminal(self, tmp_path: Path) -> None:
        _write_edition(
            tmp_path,
            "999",
            "2024",
            manifest=self._FIRST,
            casillas='[[revisions."2024".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n',
        )
        _write_edition(
            tmp_path,
            "999",
            "2025",
            manifest=self._NEXT + '\n[revisions."2025".predecessor.none]\nreason = "parallel scheme variant"',
            casillas='[[revisions."2025".casillas]]\nid = "02"\ncontinuidad_id = "c2"\n',
        )
        report = build_report(tmp_path)
        (edge,) = report.edges
        assert edge.root_kind == "root_by_law"
        (signal,) = modelo_signals(report)
        assert signal.state == "done"
        assert signal.outstanding == 0


class TestRenderedReport:
    """The human-readable form carries the same facts as the record lines, grouped and aligned."""

    def test_the_report_is_grouped_and_deterministic(self, tmp_path: Path) -> None:
        _write_edition(
            tmp_path,
            "999",
            "2025",
            manifest='valid_from = 2025-01-01\nauthority_grade = "filing"',
            casillas=(
                '[[revisions."2025".casillas]]\nid = "01"\ncontinuidad_id = "c1"\nsource_refs = ["src-a"]\n\n'
                '[[revisions."2025".casillas]]\nid = "02"\ncontinuidad_id = "c2"\nsource_refs = ["src-a"]\n'
            ),
        )
        report = build_report(tmp_path)
        text = render_report(report)
        assert text == render_report(report)
        for heading in (
            "EDITION DELTA STATUS",
            "EDGES",
            "ACTIONS",
            "SHAPE CONDITIONS",
            "FAMILIES",
            "MODELOS",
            "WORKLIST",
        ):
            assert f"\n{heading}" in text or text.startswith(heading)
        assert "edition_default_undeclared" in text
        assert "999" in text

    def test_totals_only_omits_the_per_modelo_blocks(self, tmp_path: Path) -> None:
        _write_edition(
            tmp_path,
            "999",
            "2025",
            manifest='valid_from = 2025-01-01\nauthority_grade = "filing"\ncasilla_source_refs = ["src-a"]',
            casillas='[[revisions."2025".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n',
        )
        text = render_report(build_report(tmp_path), totals_only=True)
        assert "FAMILIES" in text
        assert "MODELOS" not in text
        assert "WORKLIST" not in text


class TestYearAsMemberData:
    """A year the member declares as its own field is data, not an edition key."""

    def test_a_deadline_window_named_by_its_own_filing_year_is_not_keyed(self, tmp_path: Path) -> None:
        _write_edition(
            tmp_path,
            "999",
            "2013-2014",
            manifest='casilla_source_refs = ["src-a"]\nvalid_from = 2013-01-01',
            casillas='[[revisions."2013-2014".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n',
        )
        windows = tmp_path / "modelos" / "999" / "revisions" / "2013-2014" / "deadline_windows"
        windows.mkdir()
        (windows / "0001.toml").write_text(
            '[[revisions."2013-2014".deadline_windows]]\nid = "modelo-999-2013-1t"\nfiling_year = 2013\n\n'
            '[[revisions."2013-2014".deadline_windows]]\nid = "modelo-999-2014-1t"\nfiling_year = 2014\n\n'
            '[[revisions."2013-2014".deadline_windows]]\nid = "modelo-999-2013-legacy"\nfiling_year = 2014\n',
            encoding="utf-8",
        )
        keyed = [f.locus for s in scan_registry(tmp_path) for f in s.findings if f.kind == "edition_keyed_identifier"]
        assert keyed == ["modelo-999-2013-legacy"]


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
            "rooted",
            "rooted_recoverable",
            "ledger",
            "family",
            "limitation",
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


def _kinds_of(report) -> list[str]:
    """Finding kinds from a built report, which is where lineage scoping happens.

    _kinds reads scan_registry alone and cannot see the scopes: an
    edition knows its own rows but not what succeeds it, so the scope is
    assigned once the edges are derived.
    """
    return [finding.kind for status in report.statuses for finding in status.findings]


class TestLineageScope:
    """A missing chain is scoped by whether an edge is waiting on it.

    The flat ``row_missing_lineage`` count answers a corpus question and was
    excluded from the verdict for that reason, which left the campaign's own
    share of it -- the rows a successor cannot inherit today -- invisible in
    every number a reader would act on.
    """

    def _sequence(self, root: Path, *, successor_manifest: str) -> None:
        """Two editions of one modelo, each carrying one unchained row."""
        _write_edition(
            root,
            "999",
            "2024",
            manifest='valid_from = 2024-01-01\nauthority_grade = "filing"',
            casillas='[[revisions."2024".casillas]]\nid = "01"\n',
        )
        _write_edition(
            root,
            "999",
            "2025",
            manifest=successor_manifest,
            casillas='[[revisions."2025".casillas]]\nid = "01"\n',
        )

    def test_a_row_in_a_predecessor_edition_is_scoped_to_the_edge(self, tmp_path: Path) -> None:
        self._sequence(tmp_path, successor_manifest='valid_from = 2025-01-01\nauthority_grade = "filing"')
        kinds = _kinds_of(build_report(tmp_path))
        assert kinds.count("row_missing_lineage_on_edge") == 1
        assert kinds.count("row_missing_lineage_terminal") == 1

    def test_a_row_in_a_modelo_with_one_edition_is_scoped_apart(self, tmp_path: Path) -> None:
        """Nothing inherits from a modelo with no edge, so its gap is not this campaign's."""
        _write_edition(
            tmp_path,
            "999",
            "2024",
            manifest='valid_from = 2024-01-01\nauthority_grade = "filing"',
            casillas='[[revisions."2024".casillas]]\nid = "01"\n',
        )
        kinds = _kinds_of(build_report(tmp_path))
        assert kinds.count("row_missing_lineage_unedged") == 1
        assert "row_missing_lineage_on_edge" not in kinds

    def test_the_three_scopes_account_for_every_missing_chain(self, tmp_path: Path) -> None:
        """The decomposition is checkable: a scope that drifts leaves rows unaccounted for."""
        self._sequence(tmp_path, successor_manifest='valid_from = 2025-01-01\nauthority_grade = "filing"')
        _write_edition(
            tmp_path,
            "888",
            "2024",
            manifest='valid_from = 2024-01-01\nauthority_grade = "filing"',
            casillas='[[revisions."2024".casillas]]\nid = "01"\n',
        )
        kinds = _kinds_of(build_report(tmp_path))
        assert sum(kinds.count(scope) for scope in LINEAGE_SCOPES) == kinds.count("row_missing_lineage")

    def test_a_chained_row_is_in_no_scope(self, tmp_path: Path) -> None:
        _write_edition(
            tmp_path,
            "999",
            "2024",
            manifest='valid_from = 2024-01-01\nauthority_grade = "filing"',
            casillas='[[revisions."2024".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n',
        )
        kinds = _kinds_of(build_report(tmp_path))
        assert not [kind for kind in kinds if kind.startswith("row_missing_lineage")]

    def test_the_scoped_gap_reaches_the_outstanding_count(self, tmp_path: Path) -> None:
        """A modelo whose only remaining work is unchained rows must not read as converged."""
        self._sequence(tmp_path, successor_manifest='valid_from = 2025-01-01\nauthority_grade = "filing"')
        (signal,) = modelo_signals(build_report(tmp_path))
        assert signal.lineage_gap_on_edge == 1
        assert signal.outstanding >= signal.lineage_gap_on_edge


class TestRootsDoNotSuppressCauses:
    """A root declared for want of lineage must not hide what stops the edge.

    ``edges`` once computed blockers only for states it called outstanding, so
    an edition that rooted away from its predecessor reported no cause at all
    -- and the corpus printed no blocker while such roots held thousands of
    rows no successor could inherit.
    """

    _PENDING_ROOT = 'predecessor = { none = { reason = "Stated in full: predecessor row without lineage." } }'
    _BY_LAW_ROOT = 'predecessor = { none = { reason = "Parallel scheme variants sharing one window." } }'

    def _rooted(self, root: Path, *, reason: str) -> None:
        _write_edition(
            root,
            "999",
            "2024",
            manifest='valid_from = 2024-01-01\nauthority_grade = "filing"',
            casillas='[[revisions."2024".casillas]]\nid = "01"\n',
        )
        _write_edition(
            root,
            "999",
            "2025",
            manifest=f'valid_from = 2025-01-01\nauthority_grade = "filing"\n{reason}',
            casillas='[[revisions."2025".casillas]]\nid = "01"\n',
        )

    def test_a_root_pending_lineage_still_names_its_cause(self, tmp_path: Path) -> None:
        self._rooted(tmp_path, reason=self._PENDING_ROOT)
        (edge,) = edges(scan_registry(tmp_path))
        assert edge.state == "dispositioned"
        assert edge.rooted_pending_lineage
        assert any(blocker.startswith("predecessor_lineage_missing") for blocker in edge.blockers)

    def test_a_root_by_law_names_none(self, tmp_path: Path) -> None:
        """No cause of ours is what stops a parallel variant, so none is computed."""
        self._rooted(tmp_path, reason=self._BY_LAW_ROOT)
        (edge,) = edges(scan_registry(tmp_path))
        assert edge.state == "dispositioned"
        assert not edge.rooted_pending_lineage
        assert edge.blockers == ()

    def test_the_blocker_tally_counts_a_rooted_edge(self, tmp_path: Path) -> None:
        self._rooted(tmp_path, reason=self._PENDING_ROOT)
        lines = _signal_lines(build_report(tmp_path))
        (blocker_line,) = [line for line in lines if line.startswith("blocker ")]
        assert "predecessor_lineage_missing=1" in blocker_line

    def test_an_edge_awaiting_lineage_is_counted_once(self, tmp_path: Path) -> None:
        """The rooted count and the blocker tally name the same edge; the action must not add them."""
        self._rooted(tmp_path, reason=self._PENDING_ROOT)
        lines = _signal_lines(build_report(tmp_path))
        (action_line,) = [line for line in lines if line.startswith("action ")]
        assert "seed_lineage=1" in action_line

    def test_the_rooted_edge_has_a_record_of_its_own(self, tmp_path: Path) -> None:
        """Seeding a chain behind a root once moved no line in the diffable signal."""
        self._rooted(tmp_path, reason=self._PENDING_ROOT)
        lines = _signal_lines(build_report(tmp_path))
        (rooted_line,) = [line for line in lines if line.startswith("rooted ")]
        assert "predecessor_rows=1" in rooted_line
        assert "unchained=1" in rooted_line
        assert "shared_chains=0" in rooted_line


def _write_dispositions(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


class TestCoverageDispositionLoader:
    """The declaration refuses what would quietly widen the exempt set."""

    def test_an_absent_file_disposes_of_nothing(self, tmp_path: Path) -> None:
        """A corpus whose coverage nobody has adjudicated has disposed of nothing."""
        assert load_coverage_dispositions(tmp_path / "absent.toml") == {}

    def test_a_signed_entry_is_keyed_by_its_coordinate(self, tmp_path: Path) -> None:
        path = _write_dispositions(
            tmp_path / "d.toml",
            '[[disposition]]\nmodelo = "303"\nfiling_year = 2026\nperiod = "*"\n'
            'kind = "promised_year_unserved"\nclassification = "inception"\n'
            'reason = "no design published"\nauthority = "orden-x:art-1"\n',
        )
        loaded = load_coverage_dispositions(path)
        assert set(loaded) == {("303", 2026, "*")}
        assert loaded[("303", 2026, "*")].authority == "orden-x:art-1"

    @pytest.mark.parametrize(
        "body",
        [
            pytest.param(
                '[[disposition]]\nmodelo = "303"\nfiling_year = 2026\nperiod = "*"\n'
                'kind = "promised_year_unserved"\nclassification = "inception"\nreason = "r"\n',
                id="no authority",
            ),
            pytest.param(
                '[[disposition]]\nmodelo = "303"\nperiod = "*"\n'
                'kind = "promised_year_unserved"\nclassification = "inception"\n'
                'reason = "r"\nauthority = "a"\n',
                id="no filing year",
            ),
            pytest.param(
                '[[disposition]]\nmodelo = "303"\nfiling_year = 2026\nperiod = "*"\n'
                'kind = "looks_fine_to_me"\nclassification = "inception"\nreason = "r"\nauthority = "a"\n',
                id="unknown kind",
            ),
        ],
    )
    def test_a_malformed_entry_is_refused(self, tmp_path: Path, body: str) -> None:
        with pytest.raises(ValueError):
            load_coverage_dispositions(_write_dispositions(tmp_path / "d.toml", body))

    def test_a_coordinate_named_twice_is_refused(self, tmp_path: Path) -> None:
        """Two entries for one coordinate is how a later, weaker reason silently wins."""
        entry = (
            '[[disposition]]\nmodelo = "303"\nfiling_year = 2026\nperiod = "*"\n'
            'kind = "promised_year_unserved"\nclassification = "inception"\n'
            'reason = "r"\nauthority = "a"\n'
        )
        with pytest.raises(ValueError, match="a second time"):
            load_coverage_dispositions(_write_dispositions(tmp_path / "d.toml", entry * 2))


class TestCoverageDispositions:
    """An unclassified gap stays outstanding; only a signed one leaves the count."""

    def _one_gap(self, root: Path) -> None:
        """A modelo serving 2024 only, against a promise of 2024 and 2025."""
        _write_promise(root, (2024, 2025))
        _write_edition(
            root,
            "999",
            "2024",
            manifest=(
                'valid_from = 2024-01-01\nauthority_grade = "filing"\n'
                'period_selector = { year_from = 2024, year_to = 2024, periods = ["0A"] }'
            ),
            casillas='[[revisions."2024".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n',
        )

    def test_an_unclassified_gap_is_outstanding(self, tmp_path: Path) -> None:
        self._one_gap(tmp_path)
        (gap,) = coverage_gaps(scan_registry(tmp_path), supported_filing_years(tmp_path))
        assert gap.kind == "promised_year_unserved"
        assert not gap.disposed

    def test_a_signed_disposition_classifies_its_own_coordinate(self, tmp_path: Path) -> None:
        self._one_gap(tmp_path)
        signed = {
            ("999", 2025, "*"): CoverageDisposition(
                coordinate=("999", 2025, "*"),
                kind="promised_year_unserved",
                classification="inception",
                reason="AEAT approved no design for this ejercicio",
                authority="orden-x:art-1",
            )
        }
        (gap,) = coverage_gaps(scan_registry(tmp_path), supported_filing_years(tmp_path), signed)
        assert gap.disposed
        assert gap.disposition.startswith("AEAT approved no design")

    def test_a_disposition_written_for_another_kind_does_not_absorb_this_one(self, tmp_path: Path) -> None:
        """An entry written for an unserved year must not cover the opposite failure."""
        self._one_gap(tmp_path)
        signed = {
            ("999", 2025, "*"): CoverageDisposition(
                coordinate=("999", 2025, "*"),
                kind="coordinate_served_twice",
                classification="inception",
                reason="two editions overlap here",
                authority="orden-x:art-1",
            )
        }
        (gap,) = coverage_gaps(scan_registry(tmp_path), supported_filing_years(tmp_path), signed)
        assert not gap.disposed

    def test_a_disposition_for_another_coordinate_does_not_reach_this_one(self, tmp_path: Path) -> None:
        self._one_gap(tmp_path)
        signed = {
            ("999", 2026, "*"): CoverageDisposition(
                coordinate=("999", 2026, "*"),
                kind="promised_year_unserved",
                classification="inception",
                reason="a different year entirely",
                authority="orden-x:art-1",
            )
        }
        (gap,) = coverage_gaps(scan_registry(tmp_path), supported_filing_years(tmp_path), signed)
        assert not gap.disposed

    def test_coverage_never_enters_the_shape_verdict(self, tmp_path: Path) -> None:
        """Migration cannot move a coverage gap, so it must not hold the shape signal hostage."""
        self._one_gap(tmp_path)
        (signal,) = modelo_signals(build_report(tmp_path))
        assert signal.coverage_gaps_undisposed == 1
        assert signal.outstanding == 0


class TestUnreadablePromise:
    """A promise the screen cannot read must not render as a promise of nothing.

    With no promised years `coverage_gaps` returns early and every coverage
    condition prints zero -- a clean bill of health emitted precisely when the
    screen went blind. The promise file changed shape once already this week;
    the next change must announce itself rather than closing 71 gaps silently.
    """

    def _blind(self, root: Path, body: str) -> list[str]:
        legal = root / "legal"
        legal.mkdir(parents=True, exist_ok=True)
        (legal / "supported-filing-years.toml").write_text(body, encoding="utf-8")
        _write_edition(
            root,
            "999",
            "2024",
            manifest=(
                'valid_from = 2024-01-01\nauthority_grade = "filing"\n'
                'period_selector = { year_from = 2024, year_to = 2024, periods = ["0A"] }'
            ),
            casillas='[[revisions."2024".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n',
        )
        _LIMITATIONS.clear()
        try:
            return _signal_lines(build_report(root))
        finally:
            _LIMITATIONS.clear()

    @pytest.mark.parametrize(
        ("body", "reason"),
        [
            pytest.param(
                "[supported_filing_years]\nyears = [2024, 2025]\n",
                "promise_bounds_unparsable",
                id="the retired list shape",
            ),
            pytest.param(
                '[supported_filing_years]\nfloor = "2022"\nhorizon = 2026\n',
                "promise_bounds_unparsable",
                id="a bound that is not an integer",
            ),
            pytest.param(
                "[supported_filing_years]\nfloor = 2026\nhorizon = 2022\n",
                "promise_bounds_inverted",
                id="horizon before floor",
            ),
        ],
    )
    def test_an_unreadable_promise_says_so(self, tmp_path: Path, body: str, reason: str) -> None:
        lines = self._blind(tmp_path, body)
        assert any(line.startswith(f"limitation {reason}") for line in lines), f"expected a {reason} limitation record"

    def test_an_absent_promise_says_so(self, tmp_path: Path) -> None:
        _write_edition(
            tmp_path,
            "999",
            "2024",
            manifest='valid_from = 2024-01-01\nauthority_grade = "filing"',
            casillas='[[revisions."2024".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n',
        )
        _LIMITATIONS.clear()
        try:
            lines = _signal_lines(build_report(tmp_path))
        finally:
            _LIMITATIONS.clear()
        assert any(line.startswith("limitation promise_absent") for line in lines)

    def test_a_zero_coverage_line_never_stands_alone_when_the_promise_failed(self, tmp_path: Path) -> None:
        """The coverage line still reads zero -- what must not happen is it reading zero UNANNOUNCED."""
        lines = self._blind(tmp_path, "[supported_filing_years]\nyears = [2024, 2025]\n")
        (coverage,) = [line for line in lines if line.startswith("coverage ")]
        assert "promised_year_unserved=0" in coverage
        assert [line for line in lines if line.startswith("limitation ")], (
            "a zero coverage line with no limitation beside it is the silent collapse"
        )

    def test_a_readable_promise_emits_no_limitation(self, tmp_path: Path) -> None:
        lines = self._blind(tmp_path, "[supported_filing_years]\nfloor = 2024\nhorizon = 2025\n")
        assert not [line for line in lines if line.startswith("limitation promise_")]
        (coverage,) = [line for line in lines if line.startswith("coverage ")]
        assert "promised_year_unserved=1" in coverage


class TestDispositionClassification:
    """`did not exist` and `not yet authored` refuse identically and mean opposite things."""

    def _entry(self, classification: str) -> str:
        return (
            '[[disposition]]\nmodelo = "303"\nfiling_year = 2026\nperiod = "*"\n'
            f'kind = "promised_year_unserved"\nclassification = "{classification}"\n'
            'reason = "r"\nauthority = "orden-x:art-1"\n'
        )

    def test_an_entry_without_a_classification_is_refused(self, tmp_path: Path) -> None:
        body = (
            '[[disposition]]\nmodelo = "303"\nfiling_year = 2026\nperiod = "*"\n'
            'kind = "promised_year_unserved"\nreason = "r"\nauthority = "a"\n'
        )
        with pytest.raises(ValueError, match="classification"):
            load_coverage_dispositions(_write_dispositions(tmp_path / "d.toml", body))

    def test_an_unknown_classification_is_refused(self, tmp_path: Path) -> None:
        """There is deliberately no value for `unsure`: that case writes no entry at all."""
        with pytest.raises(ValueError, match="unknown classification"):
            load_coverage_dispositions(_write_dispositions(tmp_path / "d.toml", self._entry("uncertain")))

    def test_inception_closes_the_coordinate(self, tmp_path: Path) -> None:
        """A modelo that did not exist has a gap no authoring will ever serve."""
        loaded = load_coverage_dispositions(_write_dispositions(tmp_path / "d.toml", self._entry("inception")))
        assert loaded[("303", 2026, "*")].closes

    def test_unauthored_names_the_gap_without_closing_it(self, tmp_path: Path) -> None:
        """Saying what a gap is does not serve the year; the debt is still owed."""
        loaded = load_coverage_dispositions(_write_dispositions(tmp_path / "d.toml", self._entry("unauthored")))
        assert not loaded[("303", 2026, "*")].closes

    def test_every_declared_classification_loads(self, tmp_path: Path) -> None:
        for classification in CLASSIFICATIONS:
            loaded = load_coverage_dispositions(
                _write_dispositions(tmp_path / f"{classification}.toml", self._entry(classification))
            )
            assert loaded[("303", 2026, "*")].classification == classification


class TestRootKindReadsTheCause:
    """A root is terminal only for the causes that are facts about the forms.

    `_root_kind` split on one string and filed everything else as law, so an
    unretired withdrawal and a row order -- both work -- were counted terminal.
    Two instruments found it: the tool's own reason text, and 355 of 357
    root-crossing continuity chains sitting on exactly those two edges.
    """

    def _rooted(self, root: Path, cause: str) -> Edge:
        _write_edition(
            root,
            "999",
            "2024",
            manifest='valid_from = 2024-01-01\nauthority_grade = "filing"',
            casillas='[[revisions."2024".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n',
        )
        reason = f"Stated in full: this edition cannot be materialised exactly from the edition before it ({cause})."
        _write_edition(
            root,
            "999",
            "2025",
            manifest=(
                'valid_from = 2025-01-01\nauthority_grade = "filing"\n'
                f'predecessor = {{ none = {{ reason = "{reason}" }} }}'
            ),
            casillas='[[revisions."2025".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n',
        )
        (edge,) = edges(scan_registry(root))
        return edge

    @pytest.mark.parametrize(
        "cause", ["parallel scheme variants", "Parallel Scheme Variant", "lower grade", "overlapping predecessor"]
    )
    def test_a_cause_that_is_a_fact_about_the_forms_is_terminal(self, tmp_path: Path, cause: str) -> None:
        edge = self._rooted(tmp_path, cause)
        assert edge.root_kind == "root_by_law"
        assert not edge.root_is_open
        assert edge.blockers == (), "no cause of ours stops a root the law gives"

    @pytest.mark.parametrize("cause", ["unretired withdrawal", "row order"])
    def test_a_cause_that_is_work_is_recoverable(self, tmp_path: Path, cause: str) -> None:
        edge = self._rooted(tmp_path, cause)
        assert edge.root_kind == "root_recoverable"
        assert edge.rooted_recoverable
        assert edge.root_is_open

    def test_an_unrecognised_cause_falls_to_recoverable(self, tmp_path: Path) -> None:
        """A wording the screen has not seen is a new tool cause far more often than a new law."""
        assert self._rooted(tmp_path, "some cause nobody has written yet").root_kind == "root_recoverable"

    def test_the_lineage_mark_still_wins(self, tmp_path: Path) -> None:
        edge = self._rooted(tmp_path, "predecessor row without lineage")
        assert edge.root_kind == "root_pending_lineage"
        assert edge.rooted_pending_lineage
        assert not edge.rooted_recoverable

    def test_a_recoverable_root_is_outstanding_work(self, tmp_path: Path) -> None:
        self._rooted(tmp_path, "row order")
        (signal,) = modelo_signals(build_report(tmp_path))
        assert signal.edges_rooted_recoverable == 1
        assert signal.outstanding >= 1

    def test_a_recoverable_root_has_its_own_record(self, tmp_path: Path) -> None:
        """`rooted` keeps its pinned population; the new kind gets a record of its own."""
        self._rooted(tmp_path, "row order")
        lines = _signal_lines(build_report(tmp_path))
        assert [line for line in lines if line.startswith("rooted_recoverable ")]
        assert not [line for line in lines if line.startswith("rooted 999 ")]


def _year_edition(root: Path, modelo: str, edition: str, *, valid: str, years: str, chained: bool = True) -> None:
    """One edition admitting exactly the named years."""
    lineage = f'continuidad_id = "c-{edition}"\n' if chained else ""
    _write_edition(
        root,
        modelo,
        edition,
        manifest=(
            f'valid_from = {valid}\nauthority_grade = "filing"\n'
            f'period_selector = {{ years = [{years}], periods = ["0A"] }}'
        ),
        casillas=f'[[revisions."{edition}".casillas]]\nid = "01"\n{lineage}',
    )


class TestProjection:
    """A year with coverage BELOW it is answerable, not a hole.

    Pooling a projected year with an unserved one overstates the worklist by
    every trailing-edge cell, and understates it by hiding the chains a
    projection would have to carry forward.
    """

    def test_a_year_with_coverage_below_it_projects(self, tmp_path: Path) -> None:
        _write_promise(tmp_path, (2024, 2025))
        _year_edition(tmp_path, "999", "2024", valid="2024-01-01", years="2024")
        (gap,) = coverage_gaps(scan_registry(tmp_path), supported_filing_years(tmp_path))
        assert gap.kind == "promised_year_projected"
        assert gap.filing_year == 2025

    def test_a_year_with_no_coverage_below_it_is_unserved(self, tmp_path: Path) -> None:
        """Leading edge: applying a later design to an earlier period is wrong as law."""
        _write_promise(tmp_path, (2024, 2025))
        _year_edition(tmp_path, "999", "2025", valid="2025-01-01", years="2025")
        (gap,) = coverage_gaps(scan_registry(tmp_path), supported_filing_years(tmp_path))
        assert gap.kind == "promised_year_unserved"
        assert gap.filing_year == 2024

    def test_a_fully_covered_modelo_reports_neither(self, tmp_path: Path) -> None:
        _write_promise(tmp_path, (2024, 2025))
        _year_edition(tmp_path, "999", "2024", valid="2024-01-01", years="2024")
        _year_edition(tmp_path, "999", "2025", valid="2025-01-01", years="2025")
        assert coverage_gaps(scan_registry(tmp_path), supported_filing_years(tmp_path)) == ()

    def test_the_source_is_the_newest_edition_strictly_below(self, tmp_path: Path) -> None:
        _write_promise(tmp_path, (2023, 2024, 2025))
        _year_edition(tmp_path, "999", "2023", valid="2023-01-01", years="2023")
        _year_edition(tmp_path, "999", "2024", valid="2024-01-01", years="2024")
        statuses = scan_registry(tmp_path)
        assert projected_sources(statuses, supported_filing_years(tmp_path)) == frozenset({("999", "2024")})

    def test_an_unchained_row_at_a_projected_source_is_measured(self, tmp_path: Path) -> None:
        """Today it asserts nothing; the moment projection ships it is a predecessor row."""
        _write_promise(tmp_path, (2024, 2025))
        _year_edition(tmp_path, "999", "2024", valid="2024-01-01", years="2024", chained=False)
        kinds = _kinds_of(build_report(tmp_path))
        assert kinds.count("row_missing_lineage_on_projected_edge") == 1
        assert kinds.count("row_missing_lineage_unedged") == 1, "the original scope is unchanged"

    def test_an_unchained_row_that_projects_nowhere_is_not_measured(self, tmp_path: Path) -> None:
        _write_promise(tmp_path, (2024, 2025))
        _year_edition(tmp_path, "999", "2025", valid="2025-01-01", years="2025", chained=False)
        assert "row_missing_lineage_on_projected_edge" not in _kinds_of(build_report(tmp_path))


class TestLedgerScope:
    """The ledger's contract is successor rows, so its two unnamed populations differ."""

    def _pair(self, root: Path, *, chained_successor: bool) -> None:
        _write_promise(root, (2024, 2025))
        _write_edition(
            root,
            "999",
            "2024",
            manifest='valid_from = 2024-01-01\nauthority_grade = "filing"',
            casillas='[[revisions."2024".casillas]]\nid = "01"\n',
        )
        lineage = 'continuidad_id = "c1"\n' if chained_successor else ""
        _write_edition(
            root,
            "999",
            "2025",
            manifest='valid_from = 2025-01-01\nauthority_grade = "filing"',
            casillas=f'[[revisions."2025".casillas]]\nid = "01"\n{lineage}[[revisions."2025".casillas]]\nid = "02"\n',
        )
        _write_edition(
            root,
            "999",
            "2026",
            manifest='valid_from = 2026-01-01\nauthority_grade = "filing"',
            casillas='[[revisions."2026".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n',
        )

    def _scope(self, root: Path, ledger: str) -> object:
        path = root / "ledger.toml"
        path.write_text(ledger, encoding="utf-8")
        statuses = scan_registry(root)
        return ledger_scope(statuses, edges(statuses), path)

    def test_a_first_edition_row_is_an_unclaimed_predecessor_not_a_miss(self, tmp_path: Path) -> None:
        """2024 is never anyone's successor, so the ledger cannot name its rows."""
        self._pair(tmp_path, chained_successor=True)
        scope = self._scope(tmp_path, "")
        assert scope.unclaimed_predecessor == 1
        assert scope.unnamed_successor == 1, "2025's unchained row 02 is a genuine miss"

    def test_naming_the_successor_row_moves_only_that_count(self, tmp_path: Path) -> None:
        self._pair(tmp_path, chained_successor=True)
        named = '[[refusal]]\nmodelo = "999"\nrevision = "2025"\ncasilla = "02"\n'
        named += 'category = "held"\nreason = "r"\n'
        scope = self._scope(tmp_path, named)
        assert scope.unnamed_successor == 0
        assert scope.unclaimed_predecessor == 1, "naming a successor row cannot claim a predecessor one"
        assert scope.named == 1

    def test_the_counts_account_for_every_unchained_row_on_an_edge(self, tmp_path: Path) -> None:
        self._pair(tmp_path, chained_successor=True)
        scope = self._scope(tmp_path, "")
        assert scope.named + scope.unclaimed_predecessor + scope.unnamed_successor == scope.unchained_on_edge

    def test_an_unreadable_ledger_says_so_rather_than_reporting_nothing(self, tmp_path: Path) -> None:
        self._pair(tmp_path, chained_successor=True)
        _LIMITATIONS.clear()
        try:
            statuses = scan_registry(tmp_path)
            assert ledger_scope(statuses, edges(statuses), tmp_path / "absent.toml") is None
            assert any(text.startswith("lineage_ledger_unreadable") for text in _LIMITATIONS)
        finally:
            _LIMITATIONS.clear()
