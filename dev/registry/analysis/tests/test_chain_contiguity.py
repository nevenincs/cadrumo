"""Detector-teeth tests for the chain-contiguity screen.

Every test plants its defect into a temporary registry tree and proves the
screen names it, then proves the clean tree beside it is silent. The live
corpus is read in one test only, and only for an invariant that holds whatever
the corpus contains -- never a count, which would decay the moment the campaign
this screen serves makes progress.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from .. import chain_contiguity
from ..chain_contiguity import (
    _CHAIN_ROOT_KINDS,
    _RULING_LIMITATIONS,
    _STRUCTURE_DIFFERS,
    CONDITIONS,
    MEASUREMENTS,
    census,
    grounding_by_chain,
    read_evolutions,
    ruling_reference_findings,
    screen,
    spans_over_absent_editions,
)
from ..edition_delta_status import (
    _ROOT_KIND_BY_CAUSE,
    _bundled_registry_root,
    _root_kind,
    scan_registry,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "999"


def _edition(
    root: Path,
    edition: str,
    *,
    valid_from: str,
    chains: tuple[str, ...],
    predecessor: str = "",
    evolutions: str = "",
    duplicate: str = "",
) -> None:
    """Write one edition whose casillas carry the named chains.

    ``duplicate`` states one chain a second time under a different casilla id,
    which is the only way to build the ambiguity case: two rows, one lineage.
    """
    edition_dir = root / "modelos" / _MODELO / "revisions" / edition
    (edition_dir / "casillas").mkdir(parents=True)
    manifest = [f'[revisions."{edition}"]', f"valid_from = {valid_from}", 'authority_grade = "filing"']
    if predecessor:
        manifest.append(predecessor)
    (edition_dir / "revision.toml").write_text("\n".join(manifest) + "\n", encoding="utf-8")
    rows = [f'[[revisions."{edition}".casillas]]\nid = "box-{chain}"\ncontinuidad_id = "{chain}"\n' for chain in chains]
    if duplicate:
        rows.append(f'[[revisions."{edition}".casillas]]\nid = "box-{duplicate}-bis"\ncontinuidad_id = "{duplicate}"\n')
    (edition_dir / "casillas" / "0001-casillas.toml").write_text("".join(rows), encoding="utf-8")
    if evolutions:
        (edition_dir / "evolutions").mkdir()
        (edition_dir / "evolutions" / "0001-evolutions.toml").write_text(evolutions, encoding="utf-8")


def _evolution(edition: str, *, chain: str, start: str, end: str, kind: str = "label_evolved") -> str:
    return (
        f'[[revisions."{edition}".casilla_continuidad_evolutions]]\n'
        f'id = "ev-{chain}-{start}-{end}"\n'
        f'continuidad_id = "{chain}"\n'
        f'from_revision = "{start}"\n'
        f'to_revision = "{end}"\n'
        f'evolution_kind = "{kind}"\n'
    )


def _kinds(root: Path) -> list[str]:
    statuses = scan_registry(root)
    return [finding.kind for finding in screen(statuses, read_evolutions(root))]


class TestGroundedLiteralTracksTheDomainEnum:
    """The grounding test is a string literal against a vocabulary the domain owns.

    This screen compares `continuidad_origin` to the `_GROUNDED` literal instead of
    importing `CasillaLineageOrigin`, deliberately: it must keep reporting when the
    domain cannot be imported. The cost is a SILENT coupling -- rename that enum
    value and every link reads ungrounded, taking `chain_links_to_ground` from 7,253
    to the full 10,473 with no error raised anywhere. That is worse than the
    `_CHAIN_ROOT_KINDS` subscript, which at least fails closed with a KeyError.
    """

    def test_the_grounded_literal_is_a_member_of_the_domain_enum(self) -> None:
        from cadrumo.domain.calculations.registry.casilla_lineage import CasillaLineageOrigin

        assert _STRUCTURE_DIFFERS, "sanity: the module imported"
        assert chain_contiguity._GROUNDED in {origin.value for origin in CasillaLineageOrigin}

    def test_continues_a_chain_is_not_the_grounding_test(self) -> None:
        """Pins the trap: the domain property a reader finds first includes `seeded`.

        If these ever coincide, the screen's own docstring warning is wrong and
        should be removed rather than left to mislead in the other direction.
        """
        from cadrumo.domain.calculations.registry.casilla_lineage import CasillaLineageOrigin

        continues = {origin.value for origin in CasillaLineageOrigin if origin.continues_a_chain}
        assert continues == {"grounded", "seeded"}
        assert continues != {chain_contiguity._GROUNDED}, "the property is broader than the grounding test"

    def test_every_origin_in_the_corpus_is_a_declared_enum_member(self) -> None:
        """An origin value nobody declared would be counted as ungrounded in silence."""
        from cadrumo.domain.calculations.registry.casilla_lineage import CasillaLineageOrigin

        declared = {origin.value for origin in CasillaLineageOrigin}
        seen = {
            str(row["continuidad_origin"])
            for status in scan_registry(_bundled_registry_root())
            for row in status.rows_by_id.values()
            if row.get("continuidad_id") and row.get("continuidad_origin") is not None
        }
        assert seen, "the corpus states no origins, so this proves nothing"
        assert not seen - declared, f"origin values no enum member declares: {sorted(seen - declared)}"


class TestLimitationsAreDeclaredAndReachable:
    """A limitation whose emit site vanished is caught by nothing unless it is declared.

    The same third-category gap as on the delta screen: `CONDITIONS` and
    `MEASUREMENTS` are tuples and checkable both ways, while a limitation's name
    lived only as a literal where it is raised. A lost limitation reads as an axis
    that was measured and found clean.
    """

    def test_every_declared_limitation_has_an_emit_site(self) -> None:
        source = inspect.getsource(chain_contiguity)
        assert chain_contiguity.LIMITATIONS, "nothing declared, so this proves nothing"
        orphans = [name for name in chain_contiguity.LIMITATIONS if f'"{name}:' not in source]
        assert not orphans, f"declared with no emit site, so it can never fire: {sorted(orphans)}"

    def test_every_emitted_limitation_is_declared(self, tmp_path: Path) -> None:
        """Driven through the scoped-ruling path, the one limitation a fixture can raise."""
        path = tmp_path / "rulings.toml"
        path.write_text(
            "[[ruling]]\n"
            f'modelo = "{_MODELO}"\npredecessor = "2023"\nsuccessor = "2024"\n'
            'grounded = ["box-c1>box-c1"]\n',
            encoding="utf-8",
        )
        _RULING_LIMITATIONS.clear()
        ruling_reference_findings((), path)
        recorded = list(_RULING_LIMITATIONS)
        assert recorded, "the call recorded none, so this proves nothing"
        undeclared = [text for text in recorded if text.split(":", 1)[0] not in chain_contiguity.LIMITATIONS]
        assert not undeclared, f"emitted but not declared: {undeclared}"

    def test_the_emit_site_check_can_fail(self) -> None:
        """The control: a name with no emit site must be detected as having none."""
        assert '"a_limitation_this_screen_never_records:' not in inspect.getsource(chain_contiguity)


class TestEveryDeclaredConditionReachesTheSignal:
    """A condition declared but absent from the signal is invisible to a run diff.

    This suite already guards MEASUREMENTS in both directions --
    `set(MEASUREMENTS) <= set(counts)` is the reverse check -- while CONDITIONS
    are guarded one way only: `{finding.kind} <= set(CONDITIONS)` catches an
    undeclared kind and passes a declared one nothing emits. That asymmetry is
    what left `ledger_totality` on the sibling screen declared in an allowlist and
    emitted by nothing for a whole campaign.

    Asserted against the SIGNAL rather than against findings, because a condition
    that does not fire emits no finding by design while the signal still prints
    its zero -- so presence is a property of the instrument, not of the corpus,
    and an empty tree is enough.
    """

    def test_every_declared_condition_is_in_the_signal(self, tmp_path: Path) -> None:
        _edition(tmp_path, "2024", valid_from="2024-01-01", chains=("c1",))
        statuses = scan_registry(tmp_path)
        evolutions = read_evolutions(tmp_path)
        signal = "\n".join(chain_contiguity._signal_lines(screen(statuses, evolutions), census(statuses, evolutions)))
        assert CONDITIONS, "nothing declared, so this proves nothing"
        absent = [kind for kind in CONDITIONS if kind not in signal]
        assert not absent, f"declared but never emitted, so invisible to a run diff: {sorted(absent)}"

    def test_the_check_can_fail(self, tmp_path: Path) -> None:
        """The control, asserted against an undeclared name rather than by mutating the tuple."""
        _edition(tmp_path, "2024", valid_from="2024-01-01", chains=("c1",))
        statuses = scan_registry(tmp_path)
        evolutions = read_evolutions(tmp_path)
        signal = "\n".join(chain_contiguity._signal_lines(screen(statuses, evolutions), census(statuses, evolutions)))
        assert "a_condition_this_screen_never_declares" not in signal


class TestSharedChainIsCountedOncePerChain:
    """A chain id appearing in two modelos is ONE shared chain, however many rows carry it.

    Lineage ids are not namespaced by modelo, so the same id in two modelos either
    means the corpus reuses a label across forms -- which says nothing -- or it
    claims one box continues across two different modelos, which no evolution
    records. The measurement counts CHAINS in that state, not rows and not
    modelos, so a heavily-reused id cannot inflate it.
    """

    def _modelo(self, root: Path, modelo: str, *, chains: tuple[str, ...], rows_each: int = 1) -> None:
        edition_dir = root / "modelos" / modelo / "revisions" / "2024"
        (edition_dir / "casillas").mkdir(parents=True)
        (edition_dir / "revision.toml").write_text(
            '[revisions."2024"]\nvalid_from = 2024-01-01\nauthority_grade = "filing"\n', encoding="utf-8"
        )
        rows = "".join(
            f'[[revisions."2024".casillas]]\nid = "box-{chain}-{index}"\ncontinuidad_id = "{chain}"\n'
            for chain in chains
            for index in range(rows_each)
        )
        (edition_dir / "casillas" / "0001-casillas.toml").write_text(rows, encoding="utf-8")

    def _shared(self, root: Path) -> int:
        statuses = scan_registry(root)
        return census(statuses, read_evolutions(root))["chain_shared_across_modelos"]

    def test_one_id_in_two_modelos_is_one_shared_chain(self, tmp_path: Path) -> None:
        self._modelo(tmp_path, "998", chains=("c1",))
        self._modelo(tmp_path, "999", chains=("c1",))
        assert self._shared(tmp_path) == 1

    def test_the_same_id_on_many_rows_is_still_one_shared_chain(self, tmp_path: Path) -> None:
        """Rows do not inflate it: four rows carrying one shared id is still one chain."""
        self._modelo(tmp_path, "998", chains=("c1",), rows_each=2)
        self._modelo(tmp_path, "999", chains=("c1",), rows_each=2)
        assert self._shared(tmp_path) == 1

    def test_an_id_confined_to_one_modelo_is_not_shared(self, tmp_path: Path) -> None:
        """The control: the measurement must be able to report zero."""
        self._modelo(tmp_path, "998", chains=("c1",))
        self._modelo(tmp_path, "999", chains=("c2",))
        assert self._shared(tmp_path) == 0


class TestGroundingCensusCountsLinksNotRows:
    """The grounding numbers size a campaign, and nothing pinned what they count.

    `chain_links_to_ground` is the remaining grounding WORK: per chain, the links
    its occurrences do not yet ground, summed over chains that are not already
    complete. A chain's links are one fewer than the editions carrying it, and a
    link is grounded when the SUCCESSOR occurrence states a grounded origin --
    the later row carries the evidence for the step it makes. Counting rows
    instead of links, or counting every chain rather than only the incomplete
    ones, both produce a plausible number from the same corpus.
    """

    def _census(self, root: Path) -> dict[str, int]:
        statuses = scan_registry(root)
        return census(statuses, read_evolutions(root))

    def _grounded(self, root: Path, edition: str, *, chains: tuple[str, ...], valid_from: str) -> None:
        """One edition whose rows all state a grounded origin."""
        edition_dir = root / "modelos" / _MODELO / "revisions" / edition
        (edition_dir / "casillas").mkdir(parents=True)
        (edition_dir / "revision.toml").write_text(
            f'[revisions."{edition}"]\nvalid_from = {valid_from}\nauthority_grade = "filing"\n',
            encoding="utf-8",
        )
        rows = "".join(
            f'[[revisions."{edition}".casillas]]\nid = "box-{chain}"\ncontinuidad_id = "{chain}"\n'
            'continuidad_origin = "grounded"\n'
            for chain in chains
        )
        (edition_dir / "casillas" / "0001-casillas.toml").write_text(rows, encoding="utf-8")

    def test_a_two_edition_chain_is_one_link_not_two_rows(self, tmp_path: Path) -> None:
        """Two editions carrying one chain is ONE link, and ungrounded it is one unit of work."""
        _edition(tmp_path, "2023", valid_from="2023-01-01", chains=("c1",))
        _edition(tmp_path, "2024", valid_from="2024-01-01", chains=("c1",))
        counts = self._census(tmp_path)
        assert counts["chain_links_to_ground"] == 1
        assert counts["chain_fully_grounded"] == 0
        assert counts["chained_rows"] == 2, "two rows, one link -- the two must not be the same number"

    def test_grounding_the_successor_occurrence_completes_the_chain(self, tmp_path: Path) -> None:
        """The positive direction: a grounded successor moves the chain to fully grounded."""
        _edition(tmp_path, "2023", valid_from="2023-01-01", chains=("c1",))
        self._grounded(tmp_path, "2024", chains=("c1",), valid_from="2024-01-01")
        counts = self._census(tmp_path)
        assert counts["chain_links_to_ground"] == 0
        assert counts["chain_fully_grounded"] == 1

    def test_a_three_edition_chain_grounded_once_still_owes_one_link(self, tmp_path: Path) -> None:
        """Partial grounding reduces the work without completing the chain."""
        _edition(tmp_path, "2022", valid_from="2022-01-01", chains=("c1",))
        _edition(tmp_path, "2023", valid_from="2023-01-01", chains=("c1",))
        self._grounded(tmp_path, "2024", chains=("c1",), valid_from="2024-01-01")
        counts = self._census(tmp_path)
        assert counts["chain_links_to_ground"] == 1, "three editions are two links, one of them grounded"
        assert counts["chain_fully_grounded"] == 0, "a partly grounded chain is not complete"

    def test_a_chain_in_one_edition_only_has_no_links_and_is_not_counted_either_way(self, tmp_path: Path) -> None:
        """The control: a single occurrence is no link, so it is neither work nor complete."""
        _edition(tmp_path, "2023", valid_from="2023-01-01", chains=("c1",))
        counts = self._census(tmp_path)
        assert counts["chain_links_to_ground"] == 0
        assert counts["chain_fully_grounded"] == 0
        assert counts["chained_rows"] == 1

    def _sidecar(self, root: Path, *, start: str = "2023", end: str = "2024", malformed: bool = False) -> None:
        manifest = root / "modelos" / _MODELO / "revisions" / "2024" / "revision.toml"
        identity = 'member = "c1"' if malformed else 'continuidad_id = "c1"'
        with manifest.open("a", encoding="utf-8") as stream:
            stream.write(
                f'\n[[revisions."2024".lineage_attestations]]\n'
                'family = "casillas"\n'
                f'{identity}\n'
                f'from_revision = "{start}"\n'
                f'to_revision = "{end}"\n'
                'origin = "grounded"\n'
                'evidence = "focused exact-edge test"\n'
                'legal_refs = ["law:edge"]\n'
                'source_refs = ["source-edge"]\n'
            )

    def test_relocating_a_row_claim_to_its_sidecar_preserves_the_grounded_link(self, tmp_path: Path) -> None:
        _edition(tmp_path, "2023", valid_from="2023-01-01", chains=("c1",))
        _edition(
            tmp_path,
            "2024",
            valid_from="2024-01-01",
            chains=(),
            predecessor='predecessor = "2023"',
        )
        self._sidecar(tmp_path)

        statuses = scan_registry(tmp_path)
        counts = census(statuses, read_evolutions(tmp_path))

        assert counts["chain_links_to_ground"] == 0
        assert counts["chain_fully_grounded"] == 1
        assert counts["chained_rows"] == 1, "the sidecar must not inflate the stated-row census"

    @pytest.mark.parametrize(
        ("start", "end", "malformed"),
        (("2022", "2024", False), ("2023", "2025", False), ("2023", "2024", True)),
    )
    def test_malformed_or_wrong_edge_sidecars_are_not_treated_as_grounded(
        self,
        tmp_path: Path,
        start: str,
        end: str,
        malformed: bool,
    ) -> None:
        _edition(tmp_path, "2023", valid_from="2023-01-01", chains=("c1",))
        _edition(
            tmp_path,
            "2024",
            valid_from="2024-01-01",
            chains=(),
            predecessor='predecessor = "2023"',
        )
        self._sidecar(tmp_path, start=start, end=end, malformed=malformed)

        counts = self._census(tmp_path)

        assert counts["chain_fully_grounded"] == 0
        assert counts["chained_rows"] == 1

    def test_duplicate_sidecar_targets_are_not_treated_as_grounded(self, tmp_path: Path) -> None:
        _edition(tmp_path, "2023", valid_from="2023-01-01", chains=("c1",))
        _edition(
            tmp_path,
            "2024",
            valid_from="2024-01-01",
            chains=(),
            predecessor='predecessor = "2023"',
        )
        self._sidecar(tmp_path)
        self._sidecar(tmp_path)

        assert grounding_by_chain(scan_registry(tmp_path)) == {}

    def test_row_and_sidecar_cannot_both_own_the_target_claim(self, tmp_path: Path) -> None:
        _edition(tmp_path, "2023", valid_from="2023-01-01", chains=("c1",))
        _edition(
            tmp_path,
            "2024",
            valid_from="2024-01-01",
            chains=("c1",),
            predecessor='predecessor = "2023"',
        )
        row_file = tmp_path / "modelos" / _MODELO / "revisions" / "2024" / "casillas" / "0001-casillas.toml"
        row_file.write_text(row_file.read_text(encoding="utf-8") + 'continuidad_origin = "seeded"\n', encoding="utf-8")
        self._sidecar(tmp_path)

        assert grounding_by_chain(scan_registry(tmp_path))[f"{_MODELO}/c1"] == (0, 1)

    def test_malformed_sidecar_is_reported_as_a_limitation(self, tmp_path: Path) -> None:
        _edition(tmp_path, "2023", valid_from="2023-01-01", chains=("c1",))
        _edition(
            tmp_path,
            "2024",
            valid_from="2024-01-01",
            chains=(),
            predecessor='predecessor = "2023"',
        )
        self._sidecar(tmp_path)
        manifest = tmp_path / "modelos" / _MODELO / "revisions" / "2024" / "revision.toml"
        payload = manifest.read_text(encoding="utf-8").replace('evidence = "focused exact-edge test"\n', "")
        manifest.write_text(payload, encoding="utf-8")

        grounding_by_chain(scan_registry(tmp_path))

        assert any(text.startswith("lineage_attestations_unreadable:") for text in _RULING_LIMITATIONS)


class TestUncheckedRulingReferencesAreNamed:
    """A ruling whose edition this scan never read is unchecked, not clean.

    The rulings file is global while the statuses handed in may be scoped. An
    endpoint the scan did not read is skipped -- correctly, the question cannot be
    answered -- but silently, so a scoped run returns no findings for precisely
    the condition whose own docstring argues these accrue invisibly. Against the
    live corpus, scoping to one modelo skips every ruling endpoint: 2,937
    individual casilla references, reported as zero findings.
    """

    def _rulings(self, root: Path) -> Path:
        path = root / "rulings.toml"
        path.write_text(
            "[[ruling]]\n"
            f'modelo = "{_MODELO}"\npredecessor = "2023"\nsuccessor = "2024"\n'
            'grounded = ["box-c1>box-c1"]\n',
            encoding="utf-8",
        )
        return path

    def test_a_ruling_for_an_unscanned_edition_is_reported_as_unchecked(self, tmp_path: Path) -> None:
        path = self._rulings(tmp_path)
        _RULING_LIMITATIONS.clear()
        assert ruling_reference_findings((), path) == (), "nothing scanned means nothing checkable"
        assert any(text.startswith("ruling_references_unchecked:") for text in _RULING_LIMITATIONS), (
            "the skip must be reported, or zero findings reads as a clean bill"
        )

    def test_a_ruling_whose_editions_were_scanned_is_not_reported_as_unchecked(self, tmp_path: Path) -> None:
        """The control: the limitation must be able to stay silent."""
        _edition(tmp_path, "2023", valid_from="2023-01-01", chains=("c1",))
        _edition(tmp_path, "2024", valid_from="2024-01-01", chains=("c1",))
        path = self._rulings(tmp_path)
        _RULING_LIMITATIONS.clear()
        ruling_reference_findings(scan_registry(tmp_path), path)
        assert not [text for text in _RULING_LIMITATIONS if text.startswith("ruling_references_unchecked:")]

    def test_a_complete_run_does_not_inherit_an_earlier_scoped_run_s_answer(self, tmp_path: Path) -> None:
        """The answer is scope-dependent, so it belongs to the call and not the process.

        `_note_ruling_limitation` dedupes on exact text, which cannot help here:
        each scope produces a different string, so across two calls they
        accumulate and a complete run whose own answer is zero inherits the
        scoped run's. Verifying a scope fix by running scoped then full is
        exactly the sequence that hits it.
        """
        _edition(tmp_path, "2023", valid_from="2023-01-01", chains=("c1",))
        _edition(tmp_path, "2024", valid_from="2024-01-01", chains=("c1",))
        path = self._rulings(tmp_path)
        _RULING_LIMITATIONS.clear()
        ruling_reference_findings((), path)
        assert [text for text in _RULING_LIMITATIONS if text.startswith("ruling_references_unchecked:")], (
            "the scoped run must report, or this proves nothing about the reset"
        )
        ruling_reference_findings(scan_registry(tmp_path), path)
        assert not [text for text in _RULING_LIMITATIONS if text.startswith("ruling_references_unchecked:")], (
            "the complete run checked everything and must not carry the earlier run's count"
        )


class TestRootKindTableIsTotal:
    """Every root kind the owning screen can return must have a crossing kind here.

    `modelo_findings` subscripts `_CHAIN_ROOT_KINDS` with whatever `_root_kind`
    returns. The subscript is unguarded, so a fourth root kind added to the
    owning screen raises KeyError mid-scan rather than misreporting --
    fail-closed, but only discoverable by running it against a corpus that
    carries one.
    """

    def test_every_root_kind_the_owning_screen_returns_is_mapped(self) -> None:
        returnable = set(_ROOT_KIND_BY_CAUSE.values()) | {
            "root_pending_lineage",
            "root_by_law",
            "root_recoverable",
        }
        unmapped = returnable - set(_CHAIN_ROOT_KINDS)
        assert not unmapped, f"these root kinds would raise KeyError mid-scan: {sorted(unmapped)}"

    def test_the_fallback_kind_is_mapped(self) -> None:
        """An unrecognised cause defaults to recoverable, so that one must map."""
        assert _root_kind("", "a-cause-nobody-has-written-yet") in _CHAIN_ROOT_KINDS

    def test_a_structural_cause_is_classified_by_law_before_the_override(self) -> None:
        """Why the override exists: the owning screen calls this cause law, not recoverable.

        The comment here claimed the split came out of recoverable. It does not,
        and the difference decides what an unoverridden structural root would be
        reported as.
        """
        assert _root_kind("", _STRUCTURE_DIFFERS) == "root_by_law"
        assert _CHAIN_ROOT_KINDS["root_by_law"][0] == "chain_across_root_by_law"


class TestChainHoles:
    """A chain must run down the edition sequence without a gap."""

    def test_a_chain_absent_from_a_middle_edition_is_named(self, tmp_path: Path) -> None:
        _edition(tmp_path, "2023", valid_from="2023-01-01", chains=("c1",))
        _edition(tmp_path, "2024", valid_from="2024-01-01", chains=("c2",))
        _edition(tmp_path, "2025", valid_from="2025-01-01", chains=("c1",))
        assert "chain_skips_edition" in _kinds(tmp_path)

    def test_a_chain_carried_by_every_edition_is_silent(self, tmp_path: Path) -> None:
        _edition(tmp_path, "2023", valid_from="2023-01-01", chains=("c1",))
        _edition(tmp_path, "2024", valid_from="2024-01-01", chains=("c1",))
        _edition(tmp_path, "2025", valid_from="2025-01-01", chains=("c1",))
        assert "chain_skips_edition" not in _kinds(tmp_path)

    def test_a_delta_edition_that_does_not_restate_a_chain_is_not_a_hole(self, tmp_path: Path) -> None:
        """A delta edition states only what changed and inherits the rest.

        Reading a stated-row absence as a hole reported BOTH of the corpus's
        skips as defects when neither was one: 390/2024 declares predecessor
        2023 and 303/2024-hasta-08-y-2t declares 2023, and in each case the
        predecessor carries the very chain the successor was accused of
        dropping. The middle edition was never missing the box; it was never
        going to restate it.
        """
        _edition(tmp_path, "2023", valid_from="2023-01-01", chains=("c1",))
        _edition(
            tmp_path,
            "2024",
            valid_from="2024-01-01",
            chains=("c2",),
            predecessor='predecessor = "2023"',
        )
        _edition(tmp_path, "2025", valid_from="2025-01-01", chains=("c1",))
        assert "chain_skips_edition" not in _kinds(tmp_path)

    def test_a_full_copy_edition_that_drops_a_chain_is_still_a_hole(self, tmp_path: Path) -> None:
        """The exclusion must stay narrow. An edition that declares NO predecessor
        states its rows in full, so a chain it omits really is gone -- and that
        is the case this screen exists to find."""
        _edition(tmp_path, "2023", valid_from="2023-01-01", chains=("c1",))
        _edition(tmp_path, "2024", valid_from="2024-01-01", chains=("c2",))
        _edition(tmp_path, "2025", valid_from="2025-01-01", chains=("c1",))
        assert "chain_skips_edition" in _kinds(tmp_path)

    def test_a_retirement_excuses_the_hole_it_explains(self, tmp_path: Path) -> None:
        """The corpus stating the box left the form is not the corpus breaking a chain."""
        _edition(tmp_path, "2023", valid_from="2023-01-01", chains=("c1",))
        _edition(
            tmp_path,
            "2024",
            valid_from="2024-01-01",
            chains=("c2",),
            evolutions=_evolution("2024", chain="c1", start="2023", end="2024", kind="retired"),
        )
        _edition(tmp_path, "2025", valid_from="2025-01-01", chains=("c1",))
        assert "chain_skips_edition" not in _kinds(tmp_path)

    def test_a_chain_carried_after_its_retirement_is_named(self, tmp_path: Path) -> None:
        _edition(tmp_path, "2023", valid_from="2023-01-01", chains=("c1",))
        _edition(
            tmp_path,
            "2024",
            valid_from="2024-01-01",
            chains=("c2",),
            evolutions=_evolution("2024", chain="c1", start="2023", end="2024", kind="retired"),
        )
        _edition(tmp_path, "2025", valid_from="2025-01-01", chains=("c1",))
        assert "chain_resumed_after_retirement" in _kinds(tmp_path)

    def test_two_rows_of_one_edition_sharing_a_lineage_are_named(self, tmp_path: Path) -> None:
        _edition(tmp_path, "2024", valid_from="2024-01-01", chains=("c1",), duplicate="c1")
        assert "chain_ambiguous_in_edition" in _kinds(tmp_path)

    def test_one_row_per_lineage_is_silent(self, tmp_path: Path) -> None:
        _edition(tmp_path, "2024", valid_from="2024-01-01", chains=("c1", "c2"))
        assert "chain_ambiguous_in_edition" not in _kinds(tmp_path)


class TestChainsAcrossRoots:
    """Why a root exists decides what a chain crossing it means, so the two never pool."""

    _PENDING = 'predecessor = { none = { reason = "Stated in full: predecessor row without lineage." } }'
    _BY_LAW = 'predecessor = { none = { reason = "Parallel scheme variants sharing one validity window." } }'

    def test_a_chain_crossing_a_root_pending_lineage_is_named(self, tmp_path: Path) -> None:
        _edition(tmp_path, "2024", valid_from="2024-01-01", chains=("c1",))
        _edition(tmp_path, "2025", valid_from="2025-01-01", chains=("c1",), predecessor=self._PENDING)
        assert "chain_across_pending_root" in _kinds(tmp_path)

    def test_a_chain_crossing_a_root_by_law_is_reported_apart(self, tmp_path: Path) -> None:
        _edition(tmp_path, "2024", valid_from="2024-01-01", chains=("c1",))
        _edition(tmp_path, "2025", valid_from="2025-01-01", chains=("c1",), predecessor=self._BY_LAW)
        kinds = _kinds(tmp_path)
        assert "chain_across_root_by_law" in kinds
        assert "chain_across_pending_root" not in kinds

    def test_a_declared_predecessor_carries_no_root_finding(self, tmp_path: Path) -> None:
        _edition(tmp_path, "2024", valid_from="2024-01-01", chains=("c1",))
        _edition(tmp_path, "2025", valid_from="2025-01-01", chains=("c1",), predecessor='predecessor = "2024"')
        kinds = _kinds(tmp_path)
        assert "chain_across_pending_root" not in kinds
        assert "chain_across_root_by_law" not in kinds


class TestEvolutionRecords:
    """An evolution states one step's transition, at the edition that step arrives in."""

    def test_an_endpoint_the_modelo_does_not_declare_is_named(self, tmp_path: Path) -> None:
        _edition(
            tmp_path,
            "2025",
            valid_from="2025-01-01",
            chains=("c1",),
            evolutions=_evolution("2025", chain="c1", start="2019", end="2025"),
        )
        assert "evolution_endpoint_unknown" in _kinds(tmp_path)

    def test_a_record_landing_on_another_edition_is_named(self, tmp_path: Path) -> None:
        _edition(tmp_path, "2024", valid_from="2024-01-01", chains=("c1",))
        _edition(
            tmp_path,
            "2025",
            valid_from="2025-01-01",
            chains=("c1",),
            evolutions=_evolution("2025", chain="c1", start="2024", end="2024"),
        )
        assert "evolution_declared_off_endpoint" in _kinds(tmp_path)

    def test_a_span_whose_adjacent_step_is_also_recorded_restates_it(self, tmp_path: Path) -> None:
        """Both records present, so the longer one duplicates the adjacent one."""
        _edition(tmp_path, "2023", valid_from="2023-01-01", chains=("c1",))
        _edition(tmp_path, "2024", valid_from="2024-01-01", chains=("c1",))
        _edition(
            tmp_path,
            "2025",
            valid_from="2025-01-01",
            chains=("c1",),
            evolutions=(
                _evolution("2025", chain="c1", start="2024", end="2025")
                + _evolution("2025", chain="c1", start="2023", end="2025")
            ),
        )
        kinds = _kinds(tmp_path)
        assert "evolution_restates_ancestor" in kinds
        assert "evolution_spans_unrecorded_step" not in kinds

    def test_a_span_whose_adjacent_step_has_no_record_is_not_a_restatement(self, tmp_path: Path) -> None:
        """The teeth for the split: with no adjacent record the span is the only statement.

        An earlier version asserted the adjacent record existed instead of
        checking, and called this a restatement — so dropping it as a duplicate
        would have deleted the transition. 118 of the corpus's 669 findings were
        this case.
        """
        _edition(tmp_path, "2023", valid_from="2023-01-01", chains=("c1",))
        _edition(tmp_path, "2024", valid_from="2024-01-01", chains=("c1",))
        _edition(
            tmp_path,
            "2025",
            valid_from="2025-01-01",
            chains=("c1",),
            evolutions=_evolution("2025", chain="c1", start="2023", end="2025"),
        )
        kinds = _kinds(tmp_path)
        assert "evolution_spans_unrecorded_step" in kinds
        assert "evolution_restates_ancestor" not in kinds

    def test_an_evolution_reaching_over_editions_without_the_chain_is_measured_not_a_finding(
        self, tmp_path: Path
    ) -> None:
        """The span is the only way to state the transition, so reporting it would report the corpus for being right."""
        _edition(tmp_path, "2023", valid_from="2023-01-01", chains=("c1",))
        _edition(tmp_path, "2024", valid_from="2024-01-01", chains=("c2",))
        _edition(
            tmp_path,
            "2025",
            valid_from="2025-01-01",
            chains=("c1",),
            evolutions=_evolution("2025", chain="c1", start="2023", end="2025"),
        )
        assert "evolution_restates_ancestor" not in _kinds(tmp_path)
        statuses = scan_registry(tmp_path)
        assert spans_over_absent_editions(statuses, read_evolutions(tmp_path)) == 1

    def test_an_adjacent_evolution_is_silent(self, tmp_path: Path) -> None:
        _edition(tmp_path, "2024", valid_from="2024-01-01", chains=("c1",))
        _edition(
            tmp_path,
            "2025",
            valid_from="2025-01-01",
            chains=("c1",),
            evolutions=_evolution("2025", chain="c1", start="2024", end="2025"),
        )
        assert "evolution_restates_ancestor" not in _kinds(tmp_path)

    def test_an_evolution_naming_a_chain_neither_endpoint_carries_is_named(self, tmp_path: Path) -> None:
        _edition(tmp_path, "2024", valid_from="2024-01-01", chains=("c1",))
        _edition(
            tmp_path,
            "2025",
            valid_from="2025-01-01",
            chains=("c1",),
            evolutions=_evolution("2025", chain="ghost", start="2024", end="2025"),
        )
        assert "evolution_without_chain_members" in _kinds(tmp_path)

    def test_an_evolution_on_a_chain_a_delta_edition_only_inherits_is_not_orphaned(self, tmp_path: Path) -> None:
        """The 714 shape: the endpoint serves the chain without stating a row for it.

        714's editions 2022 through 2025 each declare a predecessor and state 23
        rows while materialising 111, so reading STATED rows called all 258 of
        its evolutions orphans.
        """
        _edition(tmp_path, "2024", valid_from="2024-01-01", chains=("c1", "inherited"))
        _edition(
            tmp_path,
            "2025",
            valid_from="2025-01-01",
            chains=("c1",),
            predecessor='predecessor = "2024"',
            evolutions=_evolution("2025", chain="inherited", start="2024", end="2025"),
        )
        assert "evolution_without_chain_members" not in _kinds(tmp_path)

    def test_a_delta_edition_whose_predecessor_also_lacks_the_chain_is_still_named(self, tmp_path: Path) -> None:
        """Teeth for the exemption above: inheritance must not excuse a true orphan.

        Widening the test from stated to materialised rows could have exempted
        every delta edition outright. Here the chain is carried nowhere in the
        modelo, so the evolution has no site and must still be reported.
        """
        _edition(tmp_path, "2024", valid_from="2024-01-01", chains=("c1",))
        _edition(
            tmp_path,
            "2025",
            valid_from="2025-01-01",
            chains=("c1",),
            predecessor='predecessor = "2024"',
            evolutions=_evolution("2025", chain="ghost", start="2024", end="2025"),
        )
        assert "evolution_without_chain_members" in _kinds(tmp_path)


class TestLiveCorpus:
    """One reading of the shipped corpus, asserting only invariants that survive progress."""

    def test_every_finding_names_a_declared_condition(self) -> None:
        root = _bundled_registry_root()
        statuses = scan_registry(root)
        findings = screen(statuses, read_evolutions(root))
        assert {finding.kind for finding in findings} <= set(CONDITIONS)

    def test_the_census_carries_every_declared_measurement(self) -> None:
        root = _bundled_registry_root()
        statuses = scan_registry(root)
        counts = census(statuses, read_evolutions(root))
        assert set(MEASUREMENTS) <= set(counts)

    def test_a_root_crossing_condition_reports_far_fewer_sites_than_findings(self) -> None:
        """The site count must measure the unit a person acts on, not the evidence weight.

        A root-crossing finding is emitted once per chain crossing one root, so
        quoting findings alone overstated the remaining work by three orders of
        magnitude. If the two ever coincide on this condition the measurement has
        stopped distinguishing them and the report is misleading again.
        """
        root = _bundled_registry_root()
        findings = screen(scan_registry(root), read_evolutions(root))
        crossings = [f for f in findings if f.kind == "chain_across_pending_root"]
        sites = {(f.modelo, f.edition) for f in crossings}
        assert crossings, "the corpus carries no pending-root crossings, so this asserts nothing"
        assert len(sites) * 10 < len(crossings), (
            f"{len(crossings)} findings over {len(sites)} sites: the counts have converged"
        )


class TestRulingReferences:
    """A ruling naming a row its edition does not carry takes the whole modelo.

    It does not refuse one row: it raises out of the ruling application. And it
    stays invisible while the modelo sits on the seeder's exclusion list, which
    is where adjudication-only modelos live — so a corpus can accrue these and
    meet them all at once when a campaign finishes and the exclusion lifts.
    """

    def _corpus(self, root: Path) -> tuple:
        _edition(root, "2021", valid_from="2021-01-01", chains=("c1",))
        _edition(root, "2022", valid_from="2022-01-01", chains=("c1",))
        return scan_registry(root)

    def _rulings(self, root: Path, body: str) -> Path:
        path = root / "rulings.toml"
        path.write_text(body, encoding="utf-8")
        return path

    def test_a_predecessor_row_the_edition_does_not_carry_is_named(self, tmp_path: Path) -> None:
        statuses = self._corpus(tmp_path)
        path = self._rulings(
            tmp_path,
            '[[ruling]]\nmodelo = "999"\npredecessor = "2021"\nsuccessor = "2022"\n'
            'grounded = ["box-nobody-has>box-c1"]\n',
        )
        (finding,) = ruling_reference_findings(statuses, path)
        assert finding.kind == "ruling_reference_unknown"
        assert finding.chain == "box-nobody-has"
        assert finding.edition == "2021"

    def test_a_ruling_whose_rows_all_exist_is_silent(self, tmp_path: Path) -> None:
        statuses = self._corpus(tmp_path)
        path = self._rulings(
            tmp_path,
            '[[ruling]]\nmodelo = "999"\npredecessor = "2021"\nsuccessor = "2022"\ngrounded = ["box-c1>box-c1"]\n',
        )
        assert ruling_reference_findings(statuses, path) == ()

    def test_a_merged_entry_is_not_read_as_an_identifier(self, tmp_path: Path) -> None:
        """`merged` entries are compound `A + B` expressions, not ids.

        Treating them as ids reported every one of them as broken — eleven
        false findings in the sweep that found the two real ones.
        """
        statuses = self._corpus(tmp_path)
        path = self._rulings(
            tmp_path,
            '[[ruling]]\nmodelo = "999"\npredecessor = "2021"\nsuccessor = "2022"\nmerged = ["box-c1 + box-other"]\n',
        )
        assert ruling_reference_findings(statuses, path) == ()

    def test_a_single_id_list_is_checked_against_the_successor_only(self, tmp_path: Path) -> None:
        """`new_on_form` names a SUCCESSOR row; checking it against the predecessor
        reported 167 breakages where there were 2."""
        statuses = self._corpus(tmp_path)
        path = self._rulings(
            tmp_path,
            '[[ruling]]\nmodelo = "999"\npredecessor = "2021"\nsuccessor = "2022"\nnew_on_form = ["box-c1"]\n',
        )
        assert ruling_reference_findings(statuses, path) == (), "box-c1 exists in the successor"

    def test_an_absent_rulings_file_reports_nothing(self, tmp_path: Path) -> None:
        assert ruling_reference_findings(self._corpus(tmp_path), tmp_path / "absent.toml") == ()


class TestStructuralRootIsNotRecoverable:
    """A root measured as structurally different is not work, and must not read as it.

    `official_structure_differs` is authored from a per-family materialisation
    harness: the record design really is reordered and the edition genuinely
    cannot be materialised from its predecessor. No lineage or grounding pass
    changes that, so a chain crossing such a root is expected and permanent --
    the box is the same concept while the editions cannot be merged, and both
    are true at once. Pooling these with roots awaiting seeding reported 620 of
    728 crossings as recoverable when nothing recovers them.
    """

    def _rooted(self, root: Path, cause: str) -> None:
        _edition(root, "2023", valid_from="2023-01-01", chains=("c1",))
        clause = ', cause = "' + cause + '"' if cause else ""
        reason = "Stated in full: this edition cannot be materialised exactly from the edition before it."
        _edition(
            root,
            "2024",
            valid_from="2024-01-01",
            chains=("c1",),
            predecessor='predecessor = { none = { reason = "' + reason + '"' + clause + " } }",
        )

    def test_a_structural_cause_reports_a_structural_crossing(self, tmp_path: Path) -> None:
        self._rooted(tmp_path, "official_structure_differs")
        kinds = _kinds(tmp_path)
        assert "chain_across_structural_root" in kinds
        assert "chain_across_recoverable_root" not in kinds

    def test_a_want_of_lineage_cause_is_still_a_pending_crossing(self, tmp_path: Path) -> None:
        """The exclusion stays narrow: a root awaiting seeding is still work."""
        self._rooted(tmp_path, "predecessor_row_without_lineage")
        kinds = _kinds(tmp_path)
        assert "chain_across_pending_root" in kinds
        assert "chain_across_structural_root" not in kinds

    def test_the_declared_cause_beats_the_wording(self, tmp_path: Path) -> None:
        """The classification reads the cause first, as the owning screen does.

        This call passed the reason alone, so every root carrying a cause code
        was classified from prose -- which moved 69 of 222/2024's crossings into
        the wrong bucket while the comment above it said that must not happen.
        """
        self._rooted(tmp_path, "official_structure_differs")
        assert "chain_across_structural_root" in _kinds(tmp_path)
