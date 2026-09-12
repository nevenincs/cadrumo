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
    _bundled_registry_root,
    census,
    read_evolutions,
    screen,
    spans_over_absent_editions,
)
from ..edition_delta_status import scan_registry

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
