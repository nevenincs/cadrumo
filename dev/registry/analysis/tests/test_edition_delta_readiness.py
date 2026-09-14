"""Readiness is a claim about whether work can actually be applied.

Three times the screen called an edge ready that the modelo could not load. The
last was 189: the declaration was applied and reverted at net zero, because
declaring one edge left the other two editions keyless and the forest rule
refused the whole modelo. And separately, eight export scenarios were declared
in a single pass while the authority would not compile, so not one could be
rendered -- and every one of them stopped reporting as blocked, because
declaring a scenario was enough to clear the blocker.

Both are the same defect wearing different clothes: a signal that went quiet
because the instrument stopped asking, not because the work was done. These
plant each shape.
"""

from __future__ import annotations

import inspect
import re
import subprocess
import sys
from pathlib import Path

import pytest

import dev.registry.analysis.chain_contiguity as chain_contiguity
import dev.registry.analysis.edition_delta_status as module
from dev.registry.analysis.edition_delta_status import Edge, build_report, edges, scan_registry

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _write_edition(
    root: Path,
    edition: str,
    *,
    modelo: str = "999",
    predecessor: str = "",
    review: str = "",
    reviewed_against: str = "",
    restated_families: str = "",
    families: dict[str, str] | None = None,
) -> None:
    """Write one edition directory in the shape the directory loader expects."""
    manifest = [
        f"valid_from = {edition[:4]}-01-01",
        'authority_grade = "filing"',
        'casilla_source_refs = ["src-a"]',
    ]
    if predecessor:
        manifest.append(f"predecessor = {predecessor}")
    if review:
        manifest.append(f'review_status = "{review}"')
    if reviewed_against:
        manifest.append(f'reviewed_against = "{reviewed_against}"')
    if restated_families:
        manifest.append(f"restated_families = {restated_families}")
    edition_dir = root / "modelos" / modelo / "revisions" / edition
    (edition_dir / "casillas").mkdir(parents=True)
    body = "\n".join(manifest)
    (edition_dir / "revision.toml").write_text(f'[revisions."{edition}"]\n{body}\n', encoding="utf-8")
    (edition_dir / "casillas" / "0001-casillas.toml").write_text(
        f'[[revisions."{edition}".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n',
        encoding="utf-8",
    )
    for family, rows in (families or {}).items():
        (edition_dir / family).mkdir()
        (edition_dir / family / f"0001-{family}.toml").write_text(rows, encoding="utf-8")


def _write_promise(root: Path, years: tuple[int, int]) -> None:
    """Write the registry-wide supported-filing-years catalogue as a floor and horizon."""
    legal = root / "legal"
    legal.mkdir(parents=True, exist_ok=True)
    (legal / "supported-filing-years.toml").write_text(
        f"[supported_filing_years]\nfloor = {years[0]}\nhorizon = {years[1]}\n",
        encoding="utf-8",
    )


def _finding_loci(root: Path, kind: str) -> set[str]:
    """Loci of one finding kind, after the edge pass that emits restatement findings."""
    statuses = scan_registry(root)
    edges(statuses)
    return {finding.locus for status in statuses for finding in status.findings if finding.kind == kind}


def _finding_kinds(root: Path) -> set[str]:
    """Every kind the full report emits, so conditions raised outside the edge pass are visible."""
    return {finding.kind for status in build_report(root).statuses for finding in status.findings}


def _edge(root: Path, predecessor: str, successor: str) -> Edge:
    found = [
        edge for edge in edges(scan_registry(root)) if (edge.predecessor, edge.successor) == (predecessor, successor)
    ]
    assert len(found) == 1, f"expected one {predecessor}->{successor} edge, got {len(found)}"
    return found[0]


class TestLimitationsAreDeclaredAndReachable:
    """Limitations were the third category and the only one with no inventory.

    `CONDITIONS` and `MEASUREMENTS` are tuples, so declared-equals-emitted is
    checkable both ways. A limitation's name existed solely as an f-string literal
    at its emit site, so one that silently STOPPED being emitted -- a guard moved,
    a code path restructured -- was caught by nothing. That is the most expensive
    absence to lose: a limitation is the screen saying what it could NOT measure,
    and losing it turns an unmeasured axis into an apparently clean one.
    """

    def test_every_declared_limitation_has_an_emit_site(self) -> None:
        """The absence-catching direction: a declared name whose emit site vanished."""
        source = inspect.getsource(module)
        assert module.LIMITATIONS, "nothing declared, so this proves nothing"
        orphans = [name for name in module.LIMITATIONS if f'"{name}:' not in source]
        assert not orphans, f"declared with no emit site, so it can never fire: {sorted(orphans)}"

    def test_every_emitted_limitation_is_declared(self, tmp_path: Path) -> None:
        """The other direction, over whatever a real run records."""
        module._LIMITATIONS.clear()
        module._family_default_keys.cache_clear()
        _write_edition(tmp_path, "2024")
        _write_promise(tmp_path, (2024, 2024))
        build_report(tmp_path)
        recorded = list(module._LIMITATIONS)
        assert recorded, "the run recorded none, so this proves nothing"
        undeclared = [text for text in recorded if not text.split(":", 1)[0] in module.LIMITATIONS]
        assert not undeclared, f"emitted but not declared: {undeclared}"

    def test_the_emit_site_check_can_fail(self) -> None:
        """The control: a name with no emit site must be detected as having none."""
        source = inspect.getsource(module)
        assert '"a_limitation_this_screen_never_records:' not in source


class TestWholeModeloReadiness:
    """An edge is not a unit of work on a modelo that has declared nothing."""

    def test_three_silent_editions_block_every_edge_and_name_the_pass_size(self, tmp_path: Path) -> None:
        """The 189 shape.

        Two of the three editions must be declared in one pass; exactly one may
        stay keyless as the chain's root, so the count is two, not three.
        """
        for edition in ("2023", "2024", "2025"):
            _write_edition(tmp_path, edition)
        first = _edge(tmp_path, "2023", "2024")
        assert first.state == "blocked"
        assert "whole_modelo_declaration_required=2" in first.blockers
        assert "whole_modelo_declaration_required=2" in _edge(tmp_path, "2024", "2025").blockers

    def test_a_modelo_that_has_declared_something_is_not_whole_modelo_blocked(self, tmp_path: Path) -> None:
        """The constraint binds only once the modelo has claimed a chain.

        A modelo already carrying a declaration is back to per-edge work, which
        is what keeps this cause from blocking the entire corpus.
        """
        _write_edition(tmp_path, "2023")
        _write_edition(tmp_path, "2024", predecessor='{ none = { reason = "first edition of the form" } }')
        _write_edition(tmp_path, "2025")
        for edge in edges(scan_registry(tmp_path)):
            assert not any(blocker.startswith("whole_modelo_declaration_required") for blocker in edge.blockers)

    def test_two_silent_editions_need_one_declaration_not_two(self, tmp_path: Path) -> None:
        _write_edition(tmp_path, "2024")
        _write_edition(tmp_path, "2025")
        assert "whole_modelo_declaration_required=1" in _edge(tmp_path, "2024", "2025").blockers


class TestReviewScopeReadiness:
    """`reviewed_against` is required on a reviewed delta edition and refused elsewhere."""

    def test_a_reviewed_successor_without_a_review_scope_is_blocked(self, tmp_path: Path) -> None:
        """It is a reviewer's claim about what was examined, so nobody migrating
        the edge may invent it."""
        _write_edition(tmp_path, "2024", review="agent_reviewed")
        _write_edition(tmp_path, "2025", review="agent_reviewed")
        assert "reviewed_against_required=2025" in _edge(tmp_path, "2024", "2025").blockers

    def test_a_root_successor_is_never_asked_for_a_review_scope(self, tmp_path: Path) -> None:
        """The refused half of the same rule.

        The schema REFUSES `reviewed_against` on an edition declaring an explicit
        no-predecessor, so demanding it there asks for a declaration that cannot
        be written. This was tested the wide way first, and 23 of the 29 live
        findings were exactly that error.
        """
        _write_edition(tmp_path, "2024", review="agent_reviewed")
        _write_edition(
            tmp_path,
            "2025",
            review="agent_reviewed",
            predecessor='{ none = { reason = "parallel scheme variant" } }',
        )
        edge = _edge(tmp_path, "2024", "2025")
        assert not any(blocker.startswith("reviewed_against_required") for blocker in edge.blockers)

    def test_a_reviewed_successor_that_states_its_scope_is_not_blocked(self, tmp_path: Path) -> None:
        _write_edition(tmp_path, "2024", review="agent_reviewed")
        _write_edition(tmp_path, "2025", review="agent_reviewed", reviewed_against="2024")
        edge = _edge(tmp_path, "2024", "2025")
        assert not any(blocker.startswith("reviewed_against_required") for blocker in edge.blockers)


class TestRenderEvidence:
    """Declaring an export scenario must not clear the blocker by itself."""

    def _evidence(self, root: Path, body: str) -> Path:
        path = root / "renders.toml"
        path.write_text(body, encoding="utf-8")
        return path

    def _rendered(self, path: Path) -> frozenset[tuple[str, str]] | None:
        original = module._RENDER_EVIDENCE_FILE
        module._rendered_editions.cache_clear()
        try:
            module._RENDER_EVIDENCE_FILE = path
            return module._rendered_editions()
        finally:
            module._RENDER_EVIDENCE_FILE = original
            module._rendered_editions.cache_clear()

    def test_an_unreadable_evidence_file_is_unknowable_not_empty(self, tmp_path: Path) -> None:
        """An empty answer would convict every declared scenario of being
        unrendered; the limitation says the question could not be asked."""
        assert self._rendered(self._evidence(tmp_path, "this is not = = toml")) is None

    def test_an_entry_that_rendered_a_different_edition_does_not_count(self, tmp_path: Path) -> None:
        """A scenario that selected the wrong revision is a withdrawal, not a proof."""
        body = (
            "[[render]]\n"
            'modelo = "189"\n'
            'edition = "2025"\n'
            'selected_revision = "2024"\n'
            "rendered_bytes = 120\n"
            'observed = "2026-09-12"\n'
        )
        assert self._rendered(self._evidence(tmp_path, body)) == frozenset()

    def test_an_entry_with_no_bytes_behind_it_does_not_count(self, tmp_path: Path) -> None:
        body = (
            "[[render]]\n"
            'modelo = "189"\n'
            'edition = "2025"\n'
            'selected_revision = "2025"\n'
            "rendered_bytes = 0\n"
            'observed = "2026-09-12"\n'
        )
        assert self._rendered(self._evidence(tmp_path, body)) == frozenset()

    def test_a_real_render_counts(self, tmp_path: Path) -> None:
        body = (
            "[[render]]\n"
            'modelo = "189"\n'
            'edition = "2025"\n'
            'selected_revision = "2025"\n'
            "rendered_bytes = 4096\n"
            'observed = "2026-09-12"\n'
        )
        assert self._rendered(self._evidence(tmp_path, body)) == frozenset({("189", "2025")})


class TestRestatedFamilyExclusion:
    """A declared restatement excludes its family, and only its family.

    `family_dispositions` and `restated_families` are different claims and
    neither can express the other: a disposition means the family is empty by
    construction, and a none-root would root the whole edition rather than one
    family. So the exclusion is narrow by construction -- an undeclared sibling
    family on the same edge must still be counted, or the declaration becomes a
    way to silence restatement debt wholesale.
    """

    def _pair(self, root: Path, *, restated: str = "") -> None:
        rows = {
            "formulas": '[[revisions."{e}".formulas]]\nid = "f1"\nexpression = "1"\n',
            "constructs": '[[revisions."{e}".constructs]]\nid = "k1"\nkind = "literal"\n',
        }
        _write_edition(root, "2024", families={f: body.format(e="2024") for f, body in rows.items()})
        _write_edition(
            root,
            "2025",
            predecessor='"2024"',
            restated_families=restated,
            families={f: body.format(e="2025") for f, body in rows.items()},
        )

    def test_a_declared_family_is_excluded_and_its_sibling_is_not(self, tmp_path: Path) -> None:
        self._pair(
            tmp_path,
            restated='[{ family = "formulas", cause = "official_structure_differs", reason = "restated" }]',
        )
        declared = _finding_loci(tmp_path, "member_restated_family_declared")
        counted = _finding_loci(tmp_path, "member_restated")
        assert any(locus.startswith("formulas/") for locus in declared), declared
        assert not any(locus.startswith("formulas/") for locus in counted), counted
        assert any(locus.startswith("constructs/") for locus in counted), counted

    def test_with_no_declaration_neither_family_is_excluded(self, tmp_path: Path) -> None:
        self._pair(tmp_path)
        assert _finding_loci(tmp_path, "member_restated_family_declared") == set()
        counted = _finding_loci(tmp_path, "member_restated")
        assert any(locus.startswith("formulas/") for locus in counted), counted
        assert any(locus.startswith("constructs/") for locus in counted), counted


class TestInlineMemberRefs:
    """The member lift's own convergence, which no other measure could see.

    Lifting a family's shared references onto the edition default and removing
    them from each member is real work that restatement cannot detect: that
    measure compares editions to each other, so refs coming off thousands of
    members left it unmoved. A zero here has to be a proven zero, which is what
    the planted member below is for -- without it, an instrument that never
    fires and a corpus with nothing left to lift read identically.
    """

    def _edition_with_formula_refs(self, root: Path, member_refs: str) -> None:
        edition_dir = root / "modelos" / "999" / "revisions" / "2025"
        (edition_dir / "casillas").mkdir(parents=True)
        (edition_dir / "revision.toml").write_text(
            '[revisions."2025"]\n'
            "valid_from = 2025-01-01\n"
            'authority_grade = "filing"\n'
            'casilla_source_refs = ["src-a"]\n'
            'formula_source_refs = ["src-f"]\n',
            encoding="utf-8",
        )
        (edition_dir / "casillas" / "0001-casillas.toml").write_text(
            '[[revisions."2025".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n', encoding="utf-8"
        )
        (edition_dir / "formulas").mkdir()
        (edition_dir / "formulas" / "0001-formulas.toml").write_text(
            f'[[revisions."2025".formulas]]\nid = "f1"\nexpression = "1"\n{member_refs}',
            encoding="utf-8",
        )

    def test_a_member_restating_its_family_default_is_counted(self, tmp_path: Path) -> None:
        self._edition_with_formula_refs(tmp_path, 'source_refs = ["src-f"]\n')
        (finding,) = [
            finding
            for status in build_report(tmp_path).statuses
            for finding in status.findings
            if finding.kind == "member_refs_inline"
        ]
        assert finding.locus == "formulas"
        assert finding.detail.startswith("1 members")

    def test_a_lifted_member_is_not_counted(self, tmp_path: Path) -> None:
        """The burn-down's zero end. This is the state the lift produces."""
        self._edition_with_formula_refs(tmp_path, "")
        assert not [
            finding
            for status in build_report(tmp_path).statuses
            for finding in status.findings
            if finding.kind == "member_refs_inline"
        ]

    def test_refs_that_differ_from_the_default_are_not_counted(self, tmp_path: Path) -> None:
        """A member with its OWN references states something the default does not,
        so removing them would lose a fact rather than a repetition."""
        self._edition_with_formula_refs(tmp_path, 'source_refs = ["src-other"]\n')
        assert not [
            finding
            for status in build_report(tmp_path).statuses
            for finding in status.findings
            if finding.kind == "member_refs_inline"
        ]


class TestDisjointValidityIsNotDoubleService:
    """A mid-year cutover admits one filing year from both sides and serves it once.

    036 closes on 2025-02-02 and its successor opens on 2025-02-03, so both
    selectors span filing year 2025 and the screen called all three censal
    coordinates double-served. Selection resolves it on a reference date and is
    correct; narrowing the predecessor's `year_to` to quiet the screen would
    silently misroute the 33 days of events before the cutover. So the rule
    changed, not the registry.
    """

    def _censal_pair(self, root: Path, *, predecessor_valid_to: str) -> None:
        for edition, valid_from, valid_to in (
            ("2023-hasta-cutover", "2023-01-01", predecessor_valid_to),
            ("2025-desde-cutover", "2025-02-03", ""),
        ):
            edition_dir = root / "modelos" / "036" / "revisions" / edition
            (edition_dir / "casillas").mkdir(parents=True)
            end = f"valid_to = {valid_to}\n" if valid_to else ""
            year_to = ", year_to = 2025" if valid_to else ""
            (edition_dir / "revision.toml").write_text(
                f'[revisions."{edition}"]\n'
                f"valid_from = {valid_from}\n{end}"
                'authority_grade = "filing"\n'
                'casilla_source_refs = ["src-a"]\n'
                f'period_selector = {{ year_from = {valid_from[:4]}{year_to}, periods = ["alta"] }}\n',
                encoding="utf-8",
            )
            (edition_dir / "casillas" / "0001-casillas.toml").write_text(
                f'[[revisions."{edition}".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n', encoding="utf-8"
            )

    def _kinds(self, root: Path, year: int) -> set[str]:
        # The promise is what coverage is measured against. Without it
        # build_report finds no promised years and reports no gaps at all, so
        # the negative case passes while measuring nothing -- which is exactly
        # what it did until this assert was added.
        _write_promise(root, (2023, 2025))
        report = build_report(root)
        assert report.promised_years, "the promise must load or this class tests nothing"
        return {gap.kind for gap in report.gaps if gap.filing_year == year}

    def test_a_mid_year_cutover_is_not_double_service(self, tmp_path: Path) -> None:
        self._censal_pair(tmp_path, predecessor_valid_to="2025-02-02")
        assert "coordinate_served_twice" not in self._kinds(tmp_path, 2025)

    def test_genuinely_overlapping_editions_are_still_double_service(self, tmp_path: Path) -> None:
        """The rule must stay narrow: two editions valid at the same time really
        do leave selection without a single right answer."""
        self._censal_pair(tmp_path, predecessor_valid_to="2025-06-30")
        assert "coordinate_served_twice" in self._kinds(tmp_path, 2025)


class TestServedDispositionIsNamed:
    """A signed disposition whose coordinate an edition now serves is stale.

    036/2023 and 036/2024 sat signed `unauthored` beside the edition serving
    them, and nothing linked the two until somebody read both files by hand. A
    stale disposition is worse than an unclassified gap: it asserts a gap the
    corpus has closed, with a reviewer's name on it.
    """

    def _tree(self, root: Path, *, serve_2024: bool) -> Path:
        editions = ["2023"] + (["2024"] if serve_2024 else [])
        for edition in editions:
            edition_dir = root / "modelos" / "999" / "revisions" / edition
            (edition_dir / "casillas").mkdir(parents=True)
            (edition_dir / "revision.toml").write_text(
                f'[revisions."{edition}"]\n'
                f"valid_from = {edition}-01-01\nvalid_to = {edition}-12-31\n"
                'authority_grade = "filing"\n'
                'casilla_source_refs = ["src-a"]\n'
                f'period_selector = {{ year_from = {edition}, year_to = {edition}, periods = ["0A"] }}\n',
                encoding="utf-8",
            )
            (edition_dir / "casillas" / "0001-casillas.toml").write_text(
                f'[[revisions."{edition}".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n', encoding="utf-8"
            )
        _write_promise(root, (2022, 2024))
        return root

    def _dispositions(self, root: Path) -> Path:
        path = root / "dispositions.toml"
        path.write_text(
            "[[disposition]]\n"
            'modelo = "999"\nfiling_year = 2024\nperiod = "*"\n'
            'kind = "promised_year_unserved"\nclassification = "unauthored"\n'
            'reason = "nobody authored it"\nauthority = "orden-test-1:art-1"\n',
            encoding="utf-8",
        )
        return path

    def _kinds(self, root: Path) -> set[str]:
        from dev.registry.analysis.coverage_dispositions import load_coverage_dispositions

        statuses = scan_registry(root)
        gaps = module.coverage_gaps(
            statuses,
            (2023, 2024),
            load_coverage_dispositions(self._dispositions(root)),
        )
        return {(gap.modelo, gap.filing_year, gap.kind) for gap in gaps}

    def test_a_disposition_whose_coordinate_is_served_is_named(self, tmp_path: Path) -> None:
        self._tree(tmp_path, serve_2024=True)
        assert ("999", 2024, "disposition_coordinate_served") in self._kinds(tmp_path)

    def test_a_disposition_for_a_still_unserved_coordinate_is_silent(self, tmp_path: Path) -> None:
        """The signature is only stale once the gap closes; while it stands it is
        doing its job and must not be reported as debt.

        The assertion is that the coordinate is still an OUTSTANDING gap, not
        that it carries one particular kind. With 2023 covered beneath it, an
        unserved 2024 reads `promised_year_projected` rather than
        `promised_year_unserved` -- a different condition, and naming either one
        here would tie this test to a classification it is not about.
        """
        self._tree(tmp_path, serve_2024=False)
        kinds = self._kinds(tmp_path)
        assert ("999", 2024, "disposition_coordinate_served") not in kinds
        assert any(
            modelo == "999" and year == 2024 and kind != "disposition_coordinate_served" for modelo, year, kind in kinds
        ), f"2024 must still be reported as an outstanding gap; got {kinds}"


class TestServednessIsAskedOfTheEditions:
    """A period nothing declares is not served, however few gaps mention it.

    The first implementation derived servedness by subtracting the gaps a run
    found, and a period absent from every edition never enters the period
    denominator -- so no gap is emitted for it, and "no gap" read as "served".
    That convicted four true 303 dispositions: 0A signed for 2022, 2023, 2024
    and 2026, where no 303 edition admits 0A in any year at all.
    """

    def _quarterly_edition(self, root: Path) -> None:
        edition_dir = root / "modelos" / "999" / "revisions" / "2022"
        (edition_dir / "casillas").mkdir(parents=True)
        (edition_dir / "revision.toml").write_text(
            '[revisions."2022"]\n'
            "valid_from = 2022-01-01\nvalid_to = 2022-12-31\n"
            'authority_grade = "filing"\n'
            'casilla_source_refs = ["src-a"]\n'
            'period_selector = { year_from = 2022, year_to = 2022, periods = ["1T", "2T", "3T", "4T"] }\n',
            encoding="utf-8",
        )
        (edition_dir / "casillas" / "0001-casillas.toml").write_text(
            '[[revisions."2022".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n', encoding="utf-8"
        )
        _write_promise(root, (2022, 2022))

    def _served_kinds(self, root: Path, period: str) -> set[str]:
        from dev.registry.analysis.coverage_dispositions import load_coverage_dispositions

        path = root / "dispositions.toml"
        path.write_text(
            "[[disposition]]\n"
            f'modelo = "999"\nfiling_year = 2022\nperiod = "{period}"\n'
            'kind = "promised_coordinate_unserved"\nclassification = "inception"\n'
            'reason = "the annual period does not exist for this modelo"\n'
            'authority = "orden-test-1:art-1"\n',
            encoding="utf-8",
        )
        gaps = module.coverage_gaps(scan_registry(root), (2022,), load_coverage_dispositions(path))
        return {gap.kind for gap in gaps if gap.period == period}

    def test_an_annual_disposition_beside_quarterly_editions_is_not_served(self, tmp_path: Path) -> None:
        """The 303 shape: 0A signed, editions serve 1T-4T only, 0A stays unserved."""
        self._quarterly_edition(tmp_path)
        assert "disposition_coordinate_served" not in self._served_kinds(tmp_path, "0A")

    def test_a_disposition_naming_a_period_an_edition_does_serve_is_named(self, tmp_path: Path) -> None:
        """The positive half, so the negative above is not passing vacuously."""
        self._quarterly_edition(tmp_path)
        assert "disposition_coordinate_served" in self._served_kinds(tmp_path, "1T")


class TestUnreachableDisposition:
    """A signature nothing can reach is reported, not skipped.

    The served pass drops two cases before it can judge them: a disposition
    naming a modelo with no manifest, and one naming a filing year outside the
    promise. Both load, both are accepted, and before this guard no pass ever
    reached either -- so a mistyped modelo id governed nothing, silently, for as
    long as it sat in the file.
    """

    def _corpus(self, root: Path) -> None:
        edition_dir = root / "modelos" / "999" / "revisions" / "2022"
        (edition_dir / "casillas").mkdir(parents=True)
        (edition_dir / "revision.toml").write_text(
            '[revisions."2022"]\n'
            "valid_from = 2022-01-01\nvalid_to = 2022-12-31\n"
            'authority_grade = "filing"\n'
            'casilla_source_refs = ["src-a"]\n'
            'period_selector = { year_from = 2022, year_to = 2022, periods = ["1T"] }\n',
            encoding="utf-8",
        )
        (edition_dir / "casillas" / "0001-casillas.toml").write_text(
            '[[revisions."2022".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n', encoding="utf-8"
        )
        _write_promise(root, (2022, 2022))

    def _kinds(self, root: Path, modelo: str, year: int, period: str) -> set[str]:
        from dev.registry.analysis.coverage_dispositions import load_coverage_dispositions

        path = root / "dispositions.toml"
        path.write_text(
            "[[disposition]]\n"
            f'modelo = "{modelo}"\nfiling_year = {year}\nperiod = "{period}"\n'
            'kind = "promised_coordinate_unserved"\nclassification = "unauthored"\n'
            'reason = "a signature whose subject may or may not exist"\n'
            'authority = "orden-test-1:art-1"\n',
            encoding="utf-8",
        )
        # `whole_corpus=True` because the fixture tree IS the whole corpus for this
        # dispositions file. The production caller passes it only for an unscoped
        # scan of the bundled tree, since a scoped scan cannot judge an entry
        # naming a modelo it never read.
        gaps = module.coverage_gaps(scan_registry(root), (2022,), load_coverage_dispositions(path), whole_corpus=True)
        return {gap.kind for gap in gaps}

    def test_a_disposition_naming_a_modelo_no_manifest_declares_is_reported(self, tmp_path: Path) -> None:
        self._corpus(tmp_path)
        assert "disposition_coordinate_unreachable" in self._kinds(tmp_path, "998", 2022, "1T")

    def test_a_disposition_naming_a_year_outside_the_promise_is_reported(self, tmp_path: Path) -> None:
        self._corpus(tmp_path)
        assert "disposition_coordinate_unreachable" in self._kinds(tmp_path, "999", 2019, "1T")

    def test_a_disposition_on_a_real_modelo_and_promised_year_is_not_reported(self, tmp_path: Path) -> None:
        """The control: the guard must be able to stay silent, or the two above prove nothing."""
        self._corpus(tmp_path)
        assert "disposition_coordinate_unreachable" not in self._kinds(tmp_path, "999", 2022, "1T")

    def test_a_period_absent_from_the_denominator_is_not_unreachable(self, tmp_path: Path) -> None:
        """The 303/0A precedent: reachability is modelo and year, never period."""
        self._corpus(tmp_path)
        assert "disposition_coordinate_unreachable" not in self._kinds(tmp_path, "999", 2022, "0A")

    def test_a_scoped_scan_does_not_judge_reachability_at_all(self, tmp_path: Path) -> None:
        """The gate: an unanswerable question must not be asked.

        The dispositions file is global. Scoped to one modelo, "no modelo of that
        id carries a manifest" is true of every other entry in the file and says
        nothing about it -- an ungated check reported all 41 other signatures as
        unreachable when the screen was pointed at modelo 100 alone.
        """
        from dev.registry.analysis.coverage_dispositions import load_coverage_dispositions

        self._corpus(tmp_path)
        path = tmp_path / "dispositions.toml"
        path.write_text(
            "[[disposition]]\n"
            'modelo = "998"\nfiling_year = 2022\nperiod = "1T"\n'
            'kind = "promised_coordinate_unserved"\nclassification = "unauthored"\n'
            'reason = "an entry a scoped scan has no standing to judge"\n'
            'authority = "orden-test-1:art-1"\n',
            encoding="utf-8",
        )
        signed = load_coverage_dispositions(path)
        scoped = {gap.kind for gap in module.coverage_gaps(scan_registry(tmp_path), (2022,), signed)}
        whole = {gap.kind for gap in module.coverage_gaps(scan_registry(tmp_path), (2022,), signed, whole_corpus=True)}
        assert "disposition_coordinate_unreachable" not in scoped
        assert "disposition_coordinate_unreachable" in whole, "the control: the same input DOES fire when asked"


class TestRootReasonResolved:
    """A root declared for want of lineage that now has lineage is a candidate, not an action.

    The reason being false says the root is no longer JUSTIFIED. It does not say
    the edition can be materialised from its predecessor, which is a separate
    fact and the one that decides -- of the first eight candidates, a per-family
    harness found zero free, six drifting or refusing, and two behind a human
    attestation. So this is measured and never presented as work.
    """

    def _rooted(self, root: Path, *, reason: str, cause: str = "", chained: bool = True) -> None:
        lineage = 'continuidad_id = "c1"\n' if chained else ""
        for edition, none in (("2024", ""), ("2025", f'predecessor = {{ none = {{ reason = "{reason}"{cause} }} }}')):
            edition_dir = root / "modelos" / "999" / "revisions" / edition
            (edition_dir / "casillas").mkdir(parents=True)
            manifest = [
                f"valid_from = {edition}-01-01",
                'authority_grade = "filing"',
                'casilla_source_refs = ["src-a"]',
            ]
            if none:
                manifest.append(none)
            (edition_dir / "revision.toml").write_text(
                f'[revisions."{edition}"]\n' + "\n".join(manifest) + "\n", encoding="utf-8"
            )
            rows = lineage if edition == "2024" else 'continuidad_id = "c1"\n'
            (edition_dir / "casillas" / "0001-casillas.toml").write_text(
                f'[[revisions."{edition}".casillas]]\nid = "01"\n{rows}', encoding="utf-8"
            )

    def test_a_want_of_lineage_root_whose_rows_are_chained_is_a_candidate(self, tmp_path: Path) -> None:
        self._rooted(tmp_path, reason="predecessor row without lineage")
        assert _edge(tmp_path, "2024", "2025").root_reason_resolved

    def test_the_same_root_with_an_unchained_row_is_not(self, tmp_path: Path) -> None:
        self._rooted(tmp_path, reason="predecessor row without lineage", chained=False)
        assert not _edge(tmp_path, "2024", "2025").root_reason_resolved

    def test_a_root_declared_for_another_reason_is_never_a_candidate(self, tmp_path: Path) -> None:
        """The exclusion that matters. Two live roots -- 131 on row order plus a
        dropped member, 165 on a lower authority grade -- have no unchained rows
        either, and a test keyed on 'pending lineage with nothing unchained'
        would have called both retractable while they are still correct."""
        self._rooted(tmp_path, reason="lower grade", cause=', cause = "lower_grade"')
        edge = _edge(tmp_path, "2024", "2025")
        assert not edge.root_reason_resolved, "a lower-grade root is not discharged by lineage arriving"


class TestVerdictStaleness:
    """A verdict older than the edition it judges is not a verdict.

    The harness measures a copy of the corpus at an instant. Five of the first
    eleven verdicts were superseded within sixteen minutes of being taken, by
    the same session's own writes. Treating a superseded verdict as current is
    exactly how a root-demotion candidate gets called free when it is not.
    """

    def _verdicts(self, root: Path, measured_at: str) -> Path:
        path = root / "verdicts.toml"
        path.write_text(
            "[[verdict]]\n"
            'modelo = "999"\npredecessor = "2024"\nsuccessor = "2025"\n'
            f'verdict = "proven_free"\nmeasured_at = "{measured_at}"\n',
            encoding="utf-8",
        )
        return path

    def _edition(self, root: Path) -> Path:
        edition_dir = root / "modelos" / "999" / "revisions" / "2025"
        (edition_dir / "casillas").mkdir(parents=True)
        (edition_dir / "revision.toml").write_text('[revisions."2025"]\nvalid_from = 2025-01-01\n', encoding="utf-8")
        return edition_dir

    def test_a_verdict_older_than_the_edition_reads_stale(self, tmp_path: Path) -> None:
        self._edition(tmp_path)
        path = self._verdicts(tmp_path, "2000-01-01T00:00:00")
        assert module.root_demotion_verdicts(tmp_path, path) == {("999", "2025"): "stale"}

    def test_a_verdict_newer_than_the_edition_stands(self, tmp_path: Path) -> None:
        self._edition(tmp_path)
        path = self._verdicts(tmp_path, "2099-01-01T00:00:00")
        assert module.root_demotion_verdicts(tmp_path, path) == {("999", "2025"): "proven_free"}

    def test_a_verdict_that_will_not_say_when_it_was_taken_is_superseded(self, tmp_path: Path) -> None:
        """A verdict with no measured_at cannot be shown to be current, and the
        safe reading of "cannot be shown current" is "not current"."""
        self._edition(tmp_path)
        path = self._verdicts(tmp_path, "")
        assert module.root_demotion_verdicts(tmp_path, path) == {("999", "2025"): "stale"}

    def test_an_absent_verdict_file_yields_no_verdicts_rather_than_failing(self, tmp_path: Path) -> None:
        self._edition(tmp_path)
        assert module.root_demotion_verdicts(tmp_path, tmp_path / "absent.toml") == {}


class TestAttestationAtRisk:
    """Dropping a member that differs only in its attestation destroys the attestation.

    `_comparable` strips the lineage claims before comparing, so such a row
    already compares EQUAL and is counted as ordinary restatement -- which is
    exactly the equality the identical-member drop tool consults. The 2,641 rows
    most at risk were therefore sitting inside the number that says they are
    safe to drop.

    Exercised against the function rather than a corpus: these are definitional
    questions about one pair of members, and a corpus-wide load answers them no
    better while costing a full compile on a contended machine.
    """

    def _pair(self, **stated: object) -> tuple[dict[str, object], dict[str, object]]:
        inherited = {"id": "01", "number": "01", "section": ("liquidacion",), "continuidad_id": "c1"}
        return inherited, {**inherited, **stated}

    def test_an_origin_the_predecessor_lacks_is_at_risk(self) -> None:
        inherited, stated = self._pair(continuidad_origin="seeded")
        assert module._drop_would_lose_attestation(inherited, stated)

    def test_an_origin_the_predecessor_also_states_is_not(self) -> None:
        """Dropping it loses nothing, because the inherited row carries the same
        claim. These are the 429 rows that are pinned but not at risk."""
        inherited, stated = self._pair(continuidad_origin="seeded")
        inherited = {**inherited, "continuidad_origin": "seeded"}
        assert not module._drop_would_lose_attestation(inherited, stated)

    def test_a_row_differing_in_source_refs_is_not_at_risk(self) -> None:
        """The ruling's boundary, and the one my first version got wrong.

        `source_refs` is provenance about the row, not the record that its chain
        was established, so a row differing there is a DIFFERENT row rather than
        the same row wearing a different attestation. Reusing the screen's
        restatement comparator counted these, because that comparator strips
        source_refs, legal_refs and additional_source_refs -- correct for
        restatement, too loose for this question.
        """
        inherited, stated = self._pair(continuidad_origin="seeded", source_refs=("src-b",))
        inherited = {**inherited, "source_refs": ("src-a",)}
        assert not module._drop_would_lose_attestation(inherited, stated)

    def test_a_row_differing_in_payload_is_not_at_risk(self) -> None:
        inherited, stated = self._pair(continuidad_origin="seeded", number="02")
        assert not module._drop_would_lose_attestation(inherited, stated)

    def test_an_identical_row_carrying_no_attestation_is_not_at_risk(self) -> None:
        inherited, stated = self._pair()
        assert not module._drop_would_lose_attestation(inherited, stated)

    def test_evidence_counts_as_an_attestation_not_only_origin(self) -> None:
        inherited, stated = self._pair(continuidad_evidence="design.md:3 [01]")
        assert module._drop_would_lose_attestation(inherited, stated)


class TestAttestationSplit:
    """On-edge risk is live; rooted risk materialises only if the root is retracted.

    A successor declaring its predecessor inherits today, so the drop tool can
    reach the row and that half is the wave's countdown. A none-root inherits
    nothing, so its rows are only at risk after a retraction -- which is why a
    retraction must not be followed by an identical-member drop before a
    lineage-only stub rule exists. An adjacent-edition scan sees only the first
    half, which is why modelo 100's rows are invisible to one.
    """

    def _corpus(self, root: Path, *, successor_declares: bool) -> None:
        rows = '[[revisions."{e}".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n{extra}'
        _write_edition(root, "2024")
        edition_dir = root / "modelos" / "999" / "revisions" / "2025"
        (edition_dir / "casillas").mkdir(parents=True)
        declaration = (
            'predecessor = "2024"'
            if successor_declares
            else 'predecessor = { none = { reason = "predecessor row without lineage" } }'
        )
        (edition_dir / "revision.toml").write_text(
            '[revisions."2025"]\nvalid_from = 2025-01-01\nauthority_grade = "filing"\n'
            f'casilla_source_refs = ["src-a"]\n{declaration}\n',
            encoding="utf-8",
        )
        (edition_dir / "casillas" / "0001-casillas.toml").write_text(
            rows.format(e="2025", extra='continuidad_origin = "seeded"\n'), encoding="utf-8"
        )

    def _kinds(self, root: Path) -> set[str]:
        statuses = scan_registry(root)
        edges(statuses)
        return {finding.kind for status in statuses for finding in status.findings}

    def test_a_declared_successor_counts_on_edge(self, tmp_path: Path) -> None:
        self._corpus(tmp_path, successor_declares=True)
        kinds = self._kinds(tmp_path)
        assert "attestation_at_risk_on_edge" in kinds
        assert "attestation_at_risk_rooted" not in kinds

    def test_a_rooted_successor_counts_rooted(self, tmp_path: Path) -> None:
        self._corpus(tmp_path, successor_declares=False)
        kinds = self._kinds(tmp_path)
        assert "attestation_at_risk_rooted" in kinds
        assert "attestation_at_risk_on_edge" not in kinds


class TestMismatchedDisposition:
    """A disposition signed for one failure while the coordinate fails as another.

    The kind check is right -- an entry written for an unserved year must not
    absorb the opposite failure if the corpus later serves that cell twice --
    but its consequence is silent: the entry stops applying, the coordinate
    reads unclassified, and the signature sits in the file describing a failure
    that is no longer the one occurring. Same species as a disposition whose
    coordinate is now served, and invisible to that measure because the
    coordinate IS still a gap; it just is not the gap somebody signed for.
    """

    def _quarterly(self, root: Path) -> None:
        """2022 serves 1T only; 2023 serves 0A.

        The 303 shape. 0A must be in the period DENOMINATOR -- the union of the
        tokens the modelo's own editions declare -- while being served by no
        edition in 2022. Declaring 0A on the 2022 edition itself makes it
        served, which is what the first version of this fixture did, and both
        tests then failed against a screen that was behaving correctly.
        """
        for edition, periods in (("2022", '["1T"]'), ("2023", '["0A"]')):
            edition_dir = root / "modelos" / "999" / "revisions" / edition
            (edition_dir / "casillas").mkdir(parents=True)
            (edition_dir / "revision.toml").write_text(
                f'[revisions."{edition}"]\n'
                f"valid_from = {edition}-01-01\nvalid_to = {edition}-12-31\n"
                'authority_grade = "filing"\ncasilla_source_refs = ["src-a"]\n'
                f"period_selector = {{ year_from = {edition}, year_to = {edition}, "
                f"periods = {periods} }}\n",
                encoding="utf-8",
            )
            (edition_dir / "casillas" / "0001-casillas.toml").write_text(
                f'[[revisions."{edition}".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n',
                encoding="utf-8",
            )

    def _kinds(self, root: Path, signed_kind: str) -> set[str]:
        from dev.registry.analysis.coverage_dispositions import load_coverage_dispositions

        path = root / "dispositions.toml"
        path.write_text(
            "[[disposition]]\n"
            'modelo = "999"\nfiling_year = 2022\nperiod = "0A"\n'
            f'kind = "{signed_kind}"\nclassification = "unauthored"\n'
            'reason = "nobody authored it"\nauthority = "orden-test-1:art-1"\n',
            encoding="utf-8",
        )
        gaps = module.coverage_gaps(scan_registry(root), (2022,), load_coverage_dispositions(path))
        return {gap.kind for gap in gaps if gap.period == "0A"}

    def test_a_signature_for_the_wrong_failure_is_named(self, tmp_path: Path) -> None:
        """0A is declared by the selector but served by no edition, so it fails as
        `promised_coordinate_unserved`; a signature for `coordinate_served_twice`
        no longer applies to it and says so."""
        self._quarterly(tmp_path)
        kinds = self._kinds(tmp_path, "coordinate_served_twice")
        assert "disposition_kind_mismatched" in kinds

    def test_a_signature_for_the_actual_failure_is_silent(self, tmp_path: Path) -> None:
        self._quarterly(tmp_path)
        kinds = self._kinds(tmp_path, "promised_coordinate_unserved")
        assert "disposition_kind_mismatched" not in kinds
        assert "promised_coordinate_unserved" in kinds


class TestBoundedAuthority:
    """A hung instrument says nothing, which is worse than a refused one.

    A field validator re-entered a non-reentrant authority lock, and every
    caller that validated a revision stopped returning -- silently. A screen run
    exited 0 with no output at all, and a pytest run did the same: no collection
    line, no summary, nothing to distinguish it from a pass. A refusal is a fact
    a reader can act on; a hang produces no line and takes every other
    measurement in the same process with it.
    """

    def test_work_that_finishes_returns_its_value(self) -> None:
        assert module._within_bound(lambda: "measured", "probe") == "measured"

    def test_work_that_overruns_returns_none_and_names_itself(self) -> None:
        import time

        original = module._AUTHORITY_BOUND_SECONDS
        before = len(module._LIMITATIONS)
        try:
            module._AUTHORITY_BOUND_SECONDS = 0.1
            assert module._within_bound(lambda: time.sleep(30), "probe") is None
        finally:
            module._AUTHORITY_BOUND_SECONDS = original
        added = module._LIMITATIONS[before:]
        assert any("probe_timed_out" in text for text in added), added

    def test_the_bound_does_not_wait_for_the_wedged_worker(self) -> None:
        """The point of the bound is that the worker may never finish, so
        returning must not depend on it doing so. A shutdown that waited would
        reproduce the hang it exists to prevent."""
        import time

        original = module._AUTHORITY_BOUND_SECONDS
        try:
            module._AUTHORITY_BOUND_SECONDS = 0.1
            started = time.monotonic()
            module._within_bound(lambda: time.sleep(20), "probe")
            assert time.monotonic() - started < 5, "returned only after the worker finished"
        finally:
            module._AUTHORITY_BOUND_SECONDS = original


class TestBoundIsStickyPerLabel:
    """One wedged dependency must cost the bound once, not once per caller.

    The bound protects a single call; the screen makes many. `_scenario_editions`
    is cached PER MODELO, so a corpus-wide report asks it about fifty-eight
    modelos -- and against a wedged authority each one would wait the full 300s
    and leak its own worker thread. That turns a hang into a five-hour hang with
    fifty-eight leaked threads, which is worse than the failure the bound was
    added to prevent.
    """

    def _isolated(self) -> None:
        module._BOUND_EXHAUSTED.discard("probe")

    def test_a_second_call_after_a_timeout_returns_immediately(self) -> None:
        import time

        original = module._AUTHORITY_BOUND_SECONDS
        self._isolated()
        try:
            module._AUTHORITY_BOUND_SECONDS = 0.2
            assert module._within_bound(lambda: time.sleep(20), "probe") is None
            started = time.monotonic()
            assert module._within_bound(lambda: time.sleep(20), "probe") is None
            elapsed = time.monotonic() - started
            assert elapsed < 0.05, f"second call waited {elapsed:.2f}s; the bound is not sticky"
        finally:
            module._AUTHORITY_BOUND_SECONDS = original
            self._isolated()

    def test_a_different_label_is_unaffected(self) -> None:
        """Stickiness is per dependency. One wedged path must not silence a
        healthy one -- that would be the suppression this screen keeps fixing."""
        import time

        original = module._AUTHORITY_BOUND_SECONDS
        self._isolated()
        module._BOUND_EXHAUSTED.discard("other-probe")
        try:
            module._AUTHORITY_BOUND_SECONDS = 0.2
            assert module._within_bound(lambda: time.sleep(20), "probe") is None
            assert module._within_bound(lambda: "fine", "other-probe") == "fine"
        finally:
            module._AUTHORITY_BOUND_SECONDS = original
            self._isolated()
            module._BOUND_EXHAUSTED.discard("other-probe")

    def test_the_limitation_says_it_covers_the_whole_run(self) -> None:
        """Asserted against the whole list, not the tail.

        `_note_limitation` DEDUPES -- it appends only text it has not already
        recorded -- so a sibling test that produced the identical string leaves
        nothing for a "what was added since" check to find. That is correct for
        the screen, which must not print one limitation fifty-eight times, and
        it made this tooth fail on a slice of an empty tail while the behaviour
        under test was working.
        """
        import time

        original = module._AUTHORITY_BOUND_SECONDS
        self._isolated()
        try:
            module._AUTHORITY_BOUND_SECONDS = 0.2
            module._within_bound(lambda: time.sleep(20), "probe")
        finally:
            module._AUTHORITY_BOUND_SECONDS = original
            self._isolated()
        assert any("probe_timed_out" in text and "whole run" in text for text in module._LIMITATIONS), (
            module._LIMITATIONS
        )


class TestDispositionPassesDoNotReportEachOther:
    """A served disposition must not also be reported as kind-mismatched.

    Both passes append synthetic gaps that describe a DISPOSITION rather than a
    coverage failure. A served coordinate's synthetic kind is
    `disposition_coordinate_served`, which differs from whatever kind somebody
    signed for -- so running the mismatch pass over the already-extended list
    reported every served disposition a second time, under a condition that
    means something else entirely.
    """

    def _served_tree(self, root: Path) -> None:
        for edition in ("2022", "2023"):
            edition_dir = root / "modelos" / "999" / "revisions" / edition
            (edition_dir / "casillas").mkdir(parents=True)
            (edition_dir / "revision.toml").write_text(
                f'[revisions."{edition}"]\n'
                f"valid_from = {edition}-01-01\nvalid_to = {edition}-12-31\n"
                'authority_grade = "filing"\ncasilla_source_refs = ["src-a"]\n'
                f'period_selector = {{ year_from = {edition}, year_to = {edition}, periods = ["0A"] }}\n',
                encoding="utf-8",
            )
            (edition_dir / "casillas" / "0001-casillas.toml").write_text(
                f'[[revisions."{edition}".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n', encoding="utf-8"
            )

    def test_a_served_coordinate_is_reported_once_not_twice(self, tmp_path: Path) -> None:
        from dev.registry.analysis.coverage_dispositions import load_coverage_dispositions

        self._served_tree(tmp_path)
        path = tmp_path / "dispositions.toml"
        path.write_text(
            "[[disposition]]\n"
            'modelo = "999"\nfiling_year = 2022\nperiod = "0A"\n'
            'kind = "promised_coordinate_unserved"\nclassification = "unauthored"\n'
            'reason = "nobody authored it"\nauthority = "orden-test-1:art-1"\n',
            encoding="utf-8",
        )
        gaps = module.coverage_gaps(scan_registry(tmp_path), (2022, 2023), load_coverage_dispositions(path))
        kinds = [gap.kind for gap in gaps if (gap.modelo, gap.filing_year, gap.period) == ("999", 2022, "0A")]
        assert kinds == ["disposition_coordinate_served"], kinds


class TestDomainPolicyIsDeferred:
    """The screen reports on a corpus whose domain package may not import.

    The family policy was read at module scope, so a domain-side breakage made
    this screen unimportable -- ``python -m`` died before argument parsing, and
    a measurement that cannot be imported goes quiet exactly when the question
    it answers is being asked. The policy is still canonical in the domain; only
    the moment of reading moved.
    """

    def test_importing_the_screen_does_not_read_the_family_policy(self) -> None:
        code = (
            "import sys\n"
            "import dev.registry.analysis.edition_delta_status\n"
            "print([name for name in sys.modules if name.endswith('keyed_families')])\n"
        )
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            cwd=Path(module.__file__).parents[3],
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        assert completed.stdout.strip() == "[]", completed.stdout

    def test_the_probe_can_see_the_policy_when_something_does_import_it(self) -> None:
        """Teeth for the test above: an empty list must mean absence, not a blind probe."""
        code = (
            "import sys\n"
            "import cadrumo.domain.calculations.registry.keyed_families\n"
            "print([name for name in sys.modules if name.endswith('keyed_families')])\n"
        )
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            cwd=Path(module.__file__).parents[3],
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        assert "keyed_families" in completed.stdout, completed.stdout

    def test_the_policy_still_reaches_the_screen_when_a_family_default_is_resolved(self) -> None:
        assert module._family_default_keys()["casillas"] == "casilla_source_refs"

    def test_the_inheritance_vocabulary_resolves_through_the_same_accessor(self) -> None:
        assert module._per_edition_families()
        assert module._inheritance().PER_EDITION is not module._inheritance().CASILLA


class TestForeignEditionToken:
    """The sibling branch of the edition-token check, which has never fired live.

    `foreign_edition_token` and `year_token_as_content` are the two outcomes of
    one test: an identifier carrying another edition's token is a stale REFERENCE
    when a sibling of the same family spells the same stem without it, and is
    CONTENT when nothing else spells that concept. The corpus exercises only the
    content branch (2 findings), so the reference branch reported clean with no
    test behind it -- a zero from a condition nothing had shown could speak.
    """

    def _modelo(self, root: Path, first_ids: tuple[str, ...], later_ids: tuple[str, ...]) -> None:
        def body(ids: tuple[str, ...], edition: str) -> str:
            return "".join(f'[[revisions."{edition}".formulas]]\nid = "{i}"\nexpression = "1"\n' for i in ids)

        _write_edition(root, "2024", families={"formulas": body(first_ids, "2024")})
        _write_edition(root, "2025", predecessor='"2024"', families={"formulas": body(later_ids, "2025")})

    def test_a_foreign_token_with_a_sibling_stem_is_a_stale_reference(self, tmp_path: Path) -> None:
        """`total-2024-neto` beside `total-neto`: the sibling proves the token is decoration."""
        self._modelo(tmp_path, ("total-neto",), ("total-2024-neto", "total-neto"))
        assert "foreign_edition_token" in _finding_kinds(tmp_path)

    def test_a_foreign_token_with_no_sibling_stem_is_content(self, tmp_path: Path) -> None:
        """The teeth for the branch above: with no bare stem anywhere the year is a datum.

        The sibling is sought across EVERY edition of the modelo rather than only
        the one declaring the identifier, so the bare stem must be absent from
        both editions -- a fixture that put it in the predecessor reported the
        reference branch and looked like a screen defect.
        """
        self._modelo(tmp_path, ("otra-cosa",), ("total-2024-neto",))
        kinds = _finding_kinds(tmp_path)
        assert "year_token_as_content" in kinds
        assert "foreign_edition_token" not in kinds


class TestSupersededDisposition:
    """A kind no disposition may sign cannot be repaired by rewriting the kind.

    `disposition_kind_mismatched` pooled two outcomes whose remedies are
    opposite. Where the coordinate's new kind is one the loader accepts, the
    signature is repairable in place. Where it is one the loader refuses --
    `promised_year_projected`, `awaiting_ejercicio_orden`,
    `pending_orden_declaration_stale` -- no value of `kind` makes the entry apply
    again, so the reasoning has to be re-homed before the entry goes. Reporting
    both as "mismatched" invites somebody to fix the second by editing a field
    the loader will reject.
    """

    def _corpus(self, root: Path, *, predecessor_year: bool) -> None:
        """A modelo serving 2022 only. With `predecessor_year`, it also serves 2021."""
        years = (2021, 2022) if predecessor_year else (2022,)
        for year in years:
            edition_dir = root / "modelos" / "999" / "revisions" / str(year)
            (edition_dir / "casillas").mkdir(parents=True)
            (edition_dir / "revision.toml").write_text(
                f'[revisions."{year}"]\n'
                f"valid_from = {year}-01-01\nvalid_to = {year}-12-31\n"
                'authority_grade = "filing"\n'
                'casilla_source_refs = ["src-a"]\n'
                f'period_selector = {{ year_from = {year}, year_to = {year}, periods = ["1T"] }}\n',
                encoding="utf-8",
            )
            (edition_dir / "casillas" / "0001-casillas.toml").write_text(
                f'[[revisions."{year}".casillas]]\nid = "01"\ncontinuidad_id = "c{year}"\n', encoding="utf-8"
            )
        _write_promise(root, (min(years), 2023))

    def _sign_2023(self, root: Path) -> object:
        from dev.registry.analysis.coverage_dispositions import load_coverage_dispositions

        path = root / "dispositions.toml"
        path.write_text(
            "[[disposition]]\n"
            'modelo = "999"\nfiling_year = 2023\nperiod = "*"\n'
            'kind = "promised_coordinate_unserved"\nclassification = "unauthored"\n'
            'reason = "signed for one kind while the screen now fails it as another"\n'
            'authority = "orden-test-1:art-1"\n',
            encoding="utf-8",
        )
        return load_coverage_dispositions(path)

    def _kinds(self, root: Path, *, predecessor_year: bool) -> set[str]:
        self._corpus(root, predecessor_year=predecessor_year)
        signed = self._sign_2023(root)
        years = (2021, 2022, 2023) if predecessor_year else (2022, 2023)
        return {gap.kind for gap in module.coverage_gaps(scan_registry(root), years, signed)}

    def test_a_coordinate_failing_as_an_unsignable_kind_is_superseded(self, tmp_path: Path) -> None:
        """2023 has a covered year below it, so it fails as the unsignable projected kind."""
        kinds = self._kinds(tmp_path, predecessor_year=True)
        assert "promised_year_projected" in kinds
        assert "disposition_kind_superseded" in kinds
        assert "disposition_kind_mismatched" not in kinds

    def test_a_coordinate_failing_as_a_signable_kind_is_merely_mismatched(self, tmp_path: Path) -> None:
        """The control: signed for a coordinate kind, failing as the year kind, which IS signable.

        The gap year must sit BELOW the served one. A gap year above a covered
        year is claimed by `promised_year_projected`, which is itself unsignable
        -- so the obvious fixture proves supersession twice and the split not at
        all.
        """
        from dev.registry.analysis.coverage_dispositions import load_coverage_dispositions

        edition_dir = tmp_path / "modelos" / "999" / "revisions" / "2023"
        (edition_dir / "casillas").mkdir(parents=True)
        (edition_dir / "revision.toml").write_text(
            '[revisions."2023"]\n'
            "valid_from = 2023-01-01\nvalid_to = 2023-12-31\n"
            'authority_grade = "filing"\n'
            'casilla_source_refs = ["src-a"]\n'
            'period_selector = { year_from = 2023, year_to = 2023, periods = ["1T"] }\n',
            encoding="utf-8",
        )
        (edition_dir / "casillas" / "0001-casillas.toml").write_text(
            '[[revisions."2023".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n', encoding="utf-8"
        )
        _write_promise(tmp_path, (2022, 2023))
        path = tmp_path / "dispositions.toml"
        path.write_text(
            "[[disposition]]\n"
            'modelo = "999"\nfiling_year = 2022\nperiod = "*"\n'
            'kind = "promised_coordinate_unserved"\nclassification = "unauthored"\n'
            'reason = "signed for the coordinate kind while the year kind is what fails"\n'
            'authority = "orden-test-1:art-1"\n',
            encoding="utf-8",
        )
        kinds = {
            gap.kind
            for gap in module.coverage_gaps(scan_registry(tmp_path), (2022, 2023), load_coverage_dispositions(path))
        }
        assert "promised_year_unserved" in kinds
        assert "disposition_kind_mismatched" in kinds
        assert "disposition_kind_superseded" not in kinds

    def test_a_synthetic_gap_leaves_its_classification_empty(self, tmp_path: Path) -> None:
        """A report ABOUT a signature must not read as a classified coordinate.

        The three synthetic passes once passed `False` into `disposition`, which
        pushed the message into `classification` and made every one of them count
        as classified unauthored debt in the coverage worklist.
        """
        self._corpus(tmp_path, predecessor_year=True)
        gaps = module.coverage_gaps(scan_registry(tmp_path), (2021, 2022, 2023), self._sign_2023(tmp_path))
        synthetic = [gap for gap in gaps if gap.kind in module._SYNTHETIC_COVERAGE_KINDS]
        assert synthetic, "fixture produced no synthetic gap, so this proves nothing"
        assert all(gap.classification == "" for gap in synthetic)
        assert all(not gap.classified for gap in synthetic)
        assert all(gap.disposition for gap in synthetic), "the reason must still be carried"


class TestOrderOnlyRefs:
    """Refs holding the whole default out of order are measured, not reclassified."""

    def _refs(self, root: Path, refs: str) -> set[str]:
        edition_dir = root / "modelos" / "999" / "revisions" / "2022"
        (edition_dir / "casillas").mkdir(parents=True)
        (edition_dir / "revision.toml").write_text(
            '[revisions."2022"]\n'
            "valid_from = 2022-01-01\nvalid_to = 2022-12-31\n"
            'authority_grade = "filing"\n'
            'casilla_source_refs = ["src-a", "src-b"]\n'
            'period_selector = { year_from = 2022, year_to = 2022, periods = ["1T"] }\n',
            encoding="utf-8",
        )
        (edition_dir / "casillas" / "0001-casillas.toml").write_text(
            f'[[revisions."2022".casillas]]\nid = "01"\ncontinuidad_id = "c1"\nsource_refs = {refs}\n',
            encoding="utf-8",
        )
        statuses = scan_registry(root)
        return {finding.kind for status in statuses for finding in status.findings}

    def test_the_default_present_but_not_leading_is_measured_and_still_irreducible(self, tmp_path: Path) -> None:
        """The 117/126/128/136/220 shape: addition listed first."""
        kinds = self._refs(tmp_path, '["extra", "src-a", "src-b"]')
        assert "row_source_refs_order_only" in kinds
        assert "row_source_refs_irreducible" in kinds, "the conservative bucket must not be vacated"

    def test_a_genuinely_irreducible_value_is_not_measured_as_order_only(self, tmp_path: Path) -> None:
        """The control: part of the default absent, so no reordering would lift it."""
        kinds = self._refs(tmp_path, '["extra", "src-a"]')
        assert "row_source_refs_irreducible" in kinds
        assert "row_source_refs_order_only" not in kinds

    def test_a_prefix_value_lifts_and_is_neither(self, tmp_path: Path) -> None:
        kinds = self._refs(tmp_path, '["src-a", "src-b", "extra"]')
        assert "row_source_refs_liftable" in kinds
        assert "row_source_refs_irreducible" not in kinds
        assert "row_source_refs_order_only" not in kinds


class TestConstraintsRefsReportTheSameFourOutcomes:
    """A row and its constraints table are classified by one helper and one rule set.

    The helper took a bool that hardcoded the ROW kind names, so a row reported
    four outcomes and its nested constraints table reported two: 81 constraint
    statements the edition default cannot reproduce were counted by nothing,
    while the catalogue said the family was "lifted by the same rules". A
    discarded outcome is indistinguishable from an empty population.
    """

    def _kinds(self, root: Path, constraint_refs: str) -> set[str]:
        edition_dir = root / "modelos" / "999" / "revisions" / "2022"
        (edition_dir / "casillas").mkdir(parents=True)
        (edition_dir / "revision.toml").write_text(
            '[revisions."2022"]\n'
            "valid_from = 2022-01-01\nvalid_to = 2022-12-31\n"
            'authority_grade = "filing"\n'
            'casilla_source_refs = ["src-a", "src-b"]\n'
            'period_selector = { year_from = 2022, year_to = 2022, periods = ["1T"] }\n',
            encoding="utf-8",
        )
        (edition_dir / "casillas" / "0001-casillas.toml").write_text(
            '[[revisions."2022".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n'
            f"constraints = {{ source_refs = {constraint_refs} }}\n",
            encoding="utf-8",
        )
        statuses = scan_registry(root)
        return {finding.kind for status in statuses for finding in status.findings}

    def test_a_constraints_value_the_default_cannot_reproduce_is_reported(self, tmp_path: Path) -> None:
        kinds = self._kinds(tmp_path, '["other-a", "other-b"]')
        assert "constraints_source_refs_irreducible" in kinds
        assert "constraints_source_refs_order_only" not in kinds

    def test_a_constraints_value_holding_the_default_out_of_order_is_measured_too(self, tmp_path: Path) -> None:
        kinds = self._kinds(tmp_path, '["extra", "src-a", "src-b"]')
        assert "constraints_source_refs_irreducible" in kinds
        assert "constraints_source_refs_order_only" in kinds

    def test_the_two_reducible_outcomes_still_report_on_their_own_kinds(self, tmp_path: Path) -> None:
        """The control: neither new kind may fire where the old two do, or the split leaks."""
        restated = self._kinds(tmp_path, '["src-a", "src-b"]')
        assert "constraints_source_refs_restated" in restated
        assert "constraints_source_refs_irreducible" not in restated
        liftable = self._kinds(tmp_path / "second", '["src-a", "src-b", "extra"]')
        assert "constraints_source_refs_liftable" in liftable
        assert "constraints_source_refs_irreducible" not in liftable

    def test_a_constraints_statement_never_borrows_a_row_kind(self, tmp_path: Path) -> None:
        """The bug in its exact shape: the row states nothing, so only constraint kinds may fire."""
        kinds = self._kinds(tmp_path, '["other-a", "other-b"]')
        assert not {kind for kind in kinds if kind.startswith("row_source_refs_")}


class TestKeylessKeyedFamiliesAreNamed:
    """A keyed family absent from the default-key mapping reports nothing, so the run must say so.

    `family_default_undeclared` can only fire for a family whose
    `source_default_key` exists. Three keyed families declare none, so they are
    silent by construction -- not clean. The catalogue used to assert the
    opposite outright ("Every keyed family carries such a key"), which turns a
    blind spot into a reassurance.
    """

    def _limitation(self) -> str:
        module._family_default_keys.cache_clear()
        module._LIMITATIONS.clear()
        module._family_default_keys()
        named = [text for text in module._LIMITATIONS if text.startswith("family_default_unmeasurable:")]
        assert len(named) == 1, f"expected exactly one such limitation, got {named}"
        return named[0]

    def test_every_keyed_family_without_a_key_is_named(self) -> None:
        """Derived from the schema here, so adding a key must shrink the limitation."""
        specs = module._keyed_families().CANONICAL_FAMILY_SPECS
        per_edition = module._inheritance().PER_EDITION
        expected = {
            spec.section for spec in specs if spec.source_default_key is None and spec.inheritance is not per_edition
        }
        assert expected, "no keyed family lacks a key, so this test can no longer prove anything"
        limitation = self._limitation()
        for family in expected:
            assert family in limitation

    def test_a_per_edition_family_without_a_key_is_not_named(self) -> None:
        """The control: per-edition families are never measured as restated, so silence is correct."""
        specs = module._keyed_families().CANONICAL_FAMILY_SPECS
        per_edition = module._inheritance().PER_EDITION
        excluded = {
            spec.section for spec in specs if spec.source_default_key is None and spec.inheritance is per_edition
        }
        assert excluded, "fixture assumption gone: no keyless per-edition family left to control against"
        limitation = self._limitation()
        for family in excluded:
            assert family not in limitation

    def test_a_family_carrying_a_key_is_measurable_and_unnamed(self) -> None:
        """Casillas is the loudest measured family; it must never appear as unmeasurable."""
        assert "casillas" in module._family_default_keys()
        assert "casillas" not in self._limitation()


class TestEveryDeclaredKindReachesTheSignal:
    """A kind declared but never emitted is invisible to anyone diffing two runs.

    The sibling suite asserts `emitted <= declared`, which catches an undeclared
    record and PASSES a declared one that nothing emits. That asymmetry hid
    `ledger_totality`: declared in the allowlist, emitted by nothing, a gate with
    proven teeth and no production caller for the length of a campaign. An
    emitted kind nobody documents and a declared record nobody emits are the same
    failure in opposite directions, and only the first is catchable by reading a
    docstring.

    This is the other direction. Every name in `CONDITIONS` and `MEASUREMENTS`
    must appear in the signal, zero count included -- the signal prints
    `condition <kind>=0` for a condition that did not fire, so presence is not
    conditional on the corpus and a fixture tree is enough.
    """

    def _signal(self, root: Path) -> str:
        _write_edition(root, "2024")
        _write_promise(root, (2024, 2024))
        return "\n".join(module._signal_lines(build_report(root)))

    def test_every_declared_condition_and_measurement_is_in_the_signal(self, tmp_path: Path) -> None:
        signal = self._signal(tmp_path)
        declared = (*module.CONDITIONS, *module.MEASUREMENTS)
        assert declared, "nothing declared, so this proves nothing"
        absent = [kind for kind in declared if kind not in signal]
        assert not absent, f"declared but never emitted, so invisible to a run diff: {sorted(absent)}"

    def test_the_check_can_fail(self, tmp_path: Path) -> None:
        """The control: a name absent from the signal must be detected as absent.

        Asserted against a name this screen does not declare rather than by
        mutating the declared tuples, so the production module is untouched.
        """
        signal = self._signal(tmp_path)
        assert "a_kind_this_screen_never_declares" not in signal


class TestEveryDeclaredKindIsDocumented:
    """A kind absent from its module catalogue is invisible to anyone reading it.

    27 of the two screens' 74 declared kinds had no catalogue entry at all, and
    the largest were conditions added DURING the campaign -- each went into the
    tuple, the emission site and the signal output, and not into the prose that
    claims to list them. Nothing contradicts an absent claim, so nothing caught
    it; this does.
    """

    @staticmethod
    def _undocumented(module: object, declared: set[str]) -> list[str]:
        source = Path(module.__file__ or "").read_text(encoding="utf-8")
        catalogue = source.split('"""', 2)[1]
        documented = set(re.findall(r"``([a-z_]+)``", catalogue))
        return sorted(declared - documented)

    def test_the_delta_screen_documents_every_kind_it_can_report(self) -> None:
        declared = (
            set(module.CONDITIONS)
            | set(module.MEASUREMENTS)
            | set(module.COVERAGE_CONDITIONS)
            | set(module._BLOCKER_CAUSES)
        )
        assert not self._undocumented(module, declared)

    def test_the_chain_screen_documents_every_kind_it_can_report(self) -> None:
        assert not self._undocumented(
            chain_contiguity, set(chain_contiguity.CONDITIONS) | set(chain_contiguity.MEASUREMENTS)
        )

    def test_the_check_itself_can_see_an_undocumented_kind(self) -> None:
        """Teeth: a name no catalogue mentions must come back as undocumented."""
        assert self._undocumented(module, {"a_kind_no_catalogue_names"}) == ["a_kind_no_catalogue_names"]
