"""Detector-teeth tests for the chain-contiguity screen.

Every test plants its defect into a temporary registry tree and proves the
screen names it, then proves the clean tree beside it is silent. The live
corpus is read in one test only, and only for an invariant that holds whatever
the corpus contains -- never a count, which would decay the moment the campaign
this screen serves makes progress.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..chain_contiguity import (
    CONDITIONS,
    MEASUREMENTS,
    census,
    read_evolutions,
    ruling_reference_findings,
    screen,
    spans_over_absent_editions,
)
from ..edition_delta_status import _bundled_registry_root, scan_registry

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

    def test_an_evolution_reaching_past_an_edition_that_carries_the_chain_is_named(self, tmp_path: Path) -> None:
        _edition(tmp_path, "2023", valid_from="2023-01-01", chains=("c1",))
        _edition(tmp_path, "2024", valid_from="2024-01-01", chains=("c1",))
        _edition(
            tmp_path,
            "2025",
            valid_from="2025-01-01",
            chains=("c1",),
            evolutions=_evolution("2025", chain="c1", start="2023", end="2025"),
        )
        assert "evolution_restates_ancestor" in _kinds(tmp_path)

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
