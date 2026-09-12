"""Detector teeth for the source-window citation screen.

A `[sources.*]` window is overlap-checked against a revision's span, but nothing
checks it at load time, so a source whose window excludes the revision citing it
is silent. Modelo 345 carried two: its base order declared a window opening
2023-01-01 while the 2022 revision cited it in five files, because the window
recorded the January of PRESENTATION rather than the ejercicio governed.

The screen's value is not the count but the CLASSIFICATION. Two citing roles sit
outside their own span correctly -- a continuity evolution names the design a
concept came FROM, and a deadline window names the calendar of the year the
return is PRESENTED -- and reporting those as defects would bury the population
that matters under a pile of correct declarations. So there is one tooth per
role: each test plants a citation of one role and asserts it lands in that role
and not another.

The registry trees here are constructed. A screen only reachable through the
live corpus cannot be handed a planted defect, and the live corpus changes under
a test that asserts counts against it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dev.registry.analysis.source_window_citations import (
    ROLES,
    classify,
    scan,
    screen_line,
    tally,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def build_catalogue(legal: Path, entries: dict[str, tuple[str | None, str | None]]) -> None:
    """Write one legal catalogue declaring each source's window."""
    legal.mkdir(parents=True, exist_ok=True)
    blocks = []
    for source_id, (applies_from, applies_to) in entries.items():
        lines = [f'[sources."{source_id}"]', 'evidence_tier = "layout_authority"']
        if applies_from:
            lines.append(f"applies_from = {applies_from}")
        if applies_to:
            lines.append(f"applies_to = {applies_to}")
        blocks.append("\n".join(lines))
    (legal / "planted.toml").write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def build_revision(
    modelos: Path,
    *,
    modelo: str,
    revision: str,
    valid_from: str,
    valid_to: str | None,
    citations: dict[str, str],
) -> None:
    """Write one revision citing each source from the file path given."""
    root = modelos / modelo / "revisions" / revision
    root.mkdir(parents=True, exist_ok=True)
    body = [f'[revisions."{revision}"]', f"valid_from = {valid_from}"]
    if valid_to:
        body.append(f"valid_to = {valid_to}")
    (root / "revision.toml").write_text("\n".join(body) + "\n", encoding="utf-8")
    for source_id, relative in citations.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        existing = target.read_text(encoding="utf-8") if target.exists() else ""
        target.write_text(existing + f'source_refs = ["{source_id}"]\n', encoding="utf-8")


@pytest.fixture
def tree(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / "legal", tmp_path / "modelos"


class TestOneToothPerRole:
    """Each role is planted on its own and must classify as itself."""

    def test_a_governing_citation_outside_its_window_is_flagged(
        self, tree: tuple[Path, Path]
    ) -> None:
        legal, modelos = tree
        build_catalogue(legal, {"planted-base-order": ("2023-01-01", None)})
        build_revision(
            modelos,
            modelo="999",
            revision="2022",
            valid_from="2022-01-01",
            valid_to="2022-12-31",
            citations={"planted-base-order": "revision.toml"},
        )
        findings, revisions, citations = scan(legal, modelos)
        assert revisions == 1
        assert citations == 1
        assert [f["role"] for f in findings] == ["governing_non_overlap"]
        assert findings[0]["source"] == "planted-base-order"

    def test_an_evolution_record_citing_the_prior_design_is_not_a_defect(
        self, tree: tuple[Path, Path]
    ) -> None:
        legal, modelos = tree
        build_catalogue(legal, {"planted-dr-2022": ("2022-01-01", "2022-12-31")})
        build_revision(
            modelos,
            modelo="999",
            revision="2023",
            valid_from="2023-01-01",
            valid_to="2023-12-31",
            citations={"planted-dr-2022": "casilla_continuidad_evolutions/0001-carried.toml"},
        )
        findings, _, _ = scan(legal, modelos)
        assert [f["role"] for f in findings] == ["evolution_origin"]

    def test_a_deadline_window_citing_the_filing_year_calendar_is_not_a_defect(
        self, tree: tuple[Path, Path]
    ) -> None:
        legal, modelos = tree
        build_catalogue(legal, {"planted-calendario-2023": ("2023-01-01", "2023-12-31")})
        build_revision(
            modelos,
            modelo="999",
            revision="2022",
            valid_from="2022-01-01",
            valid_to="2022-12-31",
            citations={"planted-calendario-2023": "deadline_windows/0001-windows.toml"},
        )
        findings, _, _ = scan(legal, modelos)
        assert [f["role"] for f in findings] == ["presentation_calendar"]


class TestGoverningWins:
    """A source cited in several roles is judged by the strictest one."""

    def test_a_source_cited_both_in_an_evolution_and_in_a_casilla_is_governing(
        self, tree: tuple[Path, Path]
    ) -> None:
        legal, modelos = tree
        build_catalogue(legal, {"planted-dr": ("2024-01-01", "2024-12-31")})
        root = modelos / "999" / "revisions" / "2023"
        build_revision(
            modelos,
            modelo="999",
            revision="2023",
            valid_from="2023-01-01",
            valid_to="2023-12-31",
            citations={"planted-dr": "casilla_continuidad_evolutions/0001-carried.toml"},
        )
        (root / "casillas").mkdir(parents=True, exist_ok=True)
        (root / "casillas" / "c01.toml").write_text(
            'source_refs = ["planted-dr"]\n', encoding="utf-8"
        )
        findings, _, _ = scan(legal, modelos)
        assert [f["role"] for f in findings] == ["governing_non_overlap"]

    def test_classify_prefers_governing_over_either_by_design_role(self) -> None:
        assert classify(["casilla_continuidad_evolutions/x.toml", "casillas/c01.toml"]) == (
            "governing_non_overlap"
        )
        assert classify(["deadline_windows/x.toml", "revision.toml"]) == "governing_non_overlap"


class TestNoFalsePositives:
    """A window that covers its citing revision produces nothing."""

    def test_an_overlapping_window_is_silent(self, tree: tuple[Path, Path]) -> None:
        legal, modelos = tree
        build_catalogue(legal, {"planted-ok": ("2022-01-01", None)})
        build_revision(
            modelos,
            modelo="999",
            revision="2022",
            valid_from="2022-01-01",
            valid_to="2022-12-31",
            citations={"planted-ok": "revision.toml"},
        )
        findings, _, citations = scan(legal, modelos)
        assert citations == 1
        assert findings == []

    def test_an_undeclared_window_makes_no_claim_to_contradict(
        self, tree: tuple[Path, Path]
    ) -> None:
        legal, modelos = tree
        build_catalogue(legal, {"planted-unwindowed": (None, None)})
        build_revision(
            modelos,
            modelo="999",
            revision="2022",
            valid_from="2022-01-01",
            valid_to="2022-12-31",
            citations={"planted-unwindowed": "revision.toml"},
        )
        findings, _, citations = scan(legal, modelos)
        assert citations == 0, "a source with no window must not be counted as checked"
        assert findings == []

    def test_an_open_ended_revision_is_covered_by_an_open_ended_source(
        self, tree: tuple[Path, Path]
    ) -> None:
        legal, modelos = tree
        build_catalogue(legal, {"planted-open": ("2020-01-01", None)})
        build_revision(
            modelos,
            modelo="999",
            revision="2025-y-siguientes",
            valid_from="2025-01-01",
            valid_to=None,
            citations={"planted-open": "revision.toml"},
        )
        findings, _, _ = scan(legal, modelos)
        assert findings == []


class TestScreenLine:
    """The grammar other registry screens are read with."""

    def test_every_role_is_named_even_at_zero(self) -> None:
        line = screen_line([], revisions=7, citations=9)
        for role in ROLES:
            assert f"{role}=0" in line, "a role absent from the line reads as not measured"
        assert line.startswith("source_windows ")
        assert "revisions=7" in line
        assert "citations=9" in line

    def test_counts_are_per_role(self, tree: tuple[Path, Path]) -> None:
        legal, modelos = tree
        build_catalogue(
            legal,
            {
                "planted-governing": ("2024-01-01", None),
                "planted-evolution": ("2021-01-01", "2021-12-31"),
                "planted-calendar": ("2023-01-01", "2023-12-31"),
            },
        )
        build_revision(
            modelos,
            modelo="999",
            revision="2022",
            valid_from="2022-01-01",
            valid_to="2022-12-31",
            citations={
                "planted-governing": "revision.toml",
                "planted-evolution": "identifier_evolutions/0001-x.toml",
                "planted-calendar": "filing_schedules/0001-x.toml",
            },
        )
        findings, revisions, citations = scan(legal, modelos)
        assert tally(findings) == {
            "governing_non_overlap": 1,
            "evolution_origin": 1,
            "presentation_calendar": 1,
        }
        assert screen_line(findings, revisions, citations) == (
            "source_windows governing_non_overlap=1 evolution_origin=1 "
            "presentation_calendar=1 revisions=1 citations=3"
        )
