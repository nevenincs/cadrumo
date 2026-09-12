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

from pathlib import Path

import pytest

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


def _edge(root: Path, predecessor: str, successor: str) -> Edge:
    found = [
        edge for edge in edges(scan_registry(root)) if (edge.predecessor, edge.successor) == (predecessor, successor)
    ]
    assert len(found) == 1, f"expected one {predecessor}->{successor} edge, got {len(found)}"
    return found[0]


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
            modelo == "999" and year == 2024 and kind != "disposition_coordinate_served"
            for modelo, year, kind in kinds
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
        (edition_dir / "revision.toml").write_text(
            '[revisions."2025"]\nvalid_from = 2025-01-01\n', encoding="utf-8"
        )
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
        edition_dir = root / "modelos" / "999" / "revisions" / "2022"
        (edition_dir / "casillas").mkdir(parents=True)
        (edition_dir / "revision.toml").write_text(
            '[revisions."2022"]\n'
            "valid_from = 2022-01-01\nvalid_to = 2022-12-31\n"
            'authority_grade = "filing"\ncasilla_source_refs = ["src-a"]\n'
            'period_selector = { year_from = 2022, year_to = 2022, periods = ["1T", "0A"] }\n',
            encoding="utf-8",
        )
        (edition_dir / "casillas" / "0001-casillas.toml").write_text(
            '[[revisions."2022".casillas]]\nid = "01"\ncontinuidad_id = "c1"\n', encoding="utf-8"
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
