"""Real-behaviour conformance for the corpus coverage report.

The coverage compiler derives the four enumerable target surfaces from the same
bundled authorities the product grounds against -- the approved Handbook
concept cards, the registry casilla projections (through the validated
authority, never raw TOML), the CLI projection, and the legal catalogue's
provision vocabulary -- and joins them against the committed relevance mapping
to list every uncovered target (the widening backlog).

No mocks: the concept, casilla, and legal surfaces run against the REAL bundled
authorities. Only the relevance mapping and the (subprocess-costly) CLI surface
are injected, so the join logic is exercised against a controlled mapping while
the derivable surface stays real. The independent oracle for the legal surface
is an own count of permalink-bearing catalogue provisions, derived from the
authority directly and independent of the report's own counting.
"""

from __future__ import annotations

import pytest

from cadrumo.core.external_constants import OutputLanguage
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority

from .._concept_cards import ConceptCardRecord, project_concept_cards
from .._coverage import (
    CoverageKind,
    KindCoverage,
    TerminologyCoverageReport,
    compute_coverage_report,
    coverage_report_path,
    legal_provision_ids,
    legal_target_record_id,
)
from .._miss_rate import load_committed_relevance
from .._sweep import SweepResult, TermRelevanceMapping, TermTargetRef
from ..casilla_projection import project_casilla_search_records
from ..search_record import CasillaSearchRecord, SearchRecordKind
from ..unified_record import to_search_record

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_EMPTY_CLI: dict[str, tuple[()]] = {"cli_command_records": (), "cli_option_records": ()}


from ...tests._authority_fixtures import authority

__all__ = ["authority"]


@pytest.fixture(scope="module")
def concept_cards() -> tuple[ConceptCardRecord, ...]:
    """Every Handbook concept card (bundled projection, run once)."""
    return project_concept_cards()[0]


@pytest.fixture(scope="module")
def casilla_records(authority: ValidatedRegistryAuthority) -> tuple[CasillaSearchRecord, ...]:
    """Every deduplicated casilla search record (bundled projection, run once)."""
    return project_casilla_search_records(authority)[0]


@pytest.fixture(scope="module")
def legal_ids(authority: ValidatedRegistryAuthority) -> tuple[str, ...]:
    """The permalink-bearing legal-provision ids (run once)."""
    return legal_provision_ids(authority)


def _sweep_from(record_ids: tuple[str, ...]) -> SweepResult:
    """Build a minimal committed-shaped mapping that references ``record_ids``."""
    targets = tuple(
        TermTargetRef(
            record_id=record_id,
            target="https://example.invalid/target",
            kind=SearchRecordKind.PAGE,
            surface="page",
            ranking_weight=0.5,
        )
        for record_id in record_ids
    )
    mapping = TermRelevanceMapping(
        query="regla de prorrata",
        concept_id="prorrata",
        language=OutputLanguage.ES,
        targets=targets,
    )
    return SweepResult(
        mappings=(mapping,),
        query_count=1,
        concept_count=1,
        failed_query_count=0,
        reindex_note="test-fixture: no reindex",
        score_floor=0.5,
    )


def test_report_is_deterministic_byte_for_byte(
    authority: ValidatedRegistryAuthority,
    concept_cards: tuple[ConceptCardRecord, ...],
    casilla_records: tuple[CasillaSearchRecord, ...],
    legal_ids: tuple[str, ...],
) -> None:
    """Two runs over identical inputs serialise to byte-identical JSON.

    The report carries no timestamp and no machine path, so determinism is the
    committed-artifact contract: a re-run on any machine yields the same bytes.
    """
    relevance = _sweep_from(("concept:prorrata", "page:how-to/choose-modelo"))

    def report() -> TerminologyCoverageReport:
        return compute_coverage_report(
            relevance=relevance,
            concept_cards=concept_cards,
            casilla_records=casilla_records,
            legal_ids=legal_ids,
            authority=authority,
            cli_command_records=(),
            cli_option_records=(),
        )

    first = report()
    second = report()

    assert first.model_dump_json(indent=2) == second.model_dump_json(indent=2)


def test_every_covered_id_is_a_member_of_the_derivable_surface(
    authority: ValidatedRegistryAuthority,
    concept_cards: tuple[ConceptCardRecord, ...],
    casilla_records: tuple[CasillaSearchRecord, ...],
    legal_ids: tuple[str, ...],
) -> None:
    """A covered id is always a derivable target; a non-derivable one is an orphan."""
    approved_concept_id = next(to_search_record(card).id for card in concept_cards if card.is_approved)
    casilla_id = to_search_record(casilla_records[0]).id
    legal_id = legal_target_record_id(legal_ids[0])
    orphan_page = "page:this/page/is/no/projection"
    orphan_code = "code:cadrumo.nonexistent.module"

    relevance = _sweep_from((approved_concept_id, casilla_id, legal_id, orphan_page, orphan_code))
    report = compute_coverage_report(
        relevance=relevance,
        concept_cards=concept_cards,
        casilla_records=casilla_records,
        legal_ids=legal_ids,
        authority=authority,
        **_EMPTY_CLI,
    )

    derivable = _derivable_surface(concept_cards, casilla_records, legal_ids)
    covered_ids = {approved_concept_id, casilla_id, legal_id}
    assert covered_ids <= derivable

    assert report.kind(CoverageKind.CONCEPT).covered == 1
    assert report.kind(CoverageKind.CASILLA).covered == 1
    assert report.kind(CoverageKind.LEGAL).covered == 1
    assert set(report.orphan_mapping_target_ids) == {orphan_page, orphan_code}
    assert covered_ids.isdisjoint(report.orphan_mapping_target_ids)
    assert report.referenced_target_count == 5


def test_per_kind_counts_partition_the_derivable_surface(
    authority: ValidatedRegistryAuthority,
    concept_cards: tuple[ConceptCardRecord, ...],
    casilla_records: tuple[CasillaSearchRecord, ...],
    legal_ids: tuple[str, ...],
) -> None:
    """For every kind, covered + uncovered == total, uncovered is sorted, and disjoint."""
    approved_concept_id = next(to_search_record(card).id for card in concept_cards if card.is_approved)
    relevance = _sweep_from((approved_concept_id,))
    report = compute_coverage_report(
        relevance=relevance,
        concept_cards=concept_cards,
        casilla_records=casilla_records,
        legal_ids=legal_ids,
        authority=authority,
        **_EMPTY_CLI,
    )

    for entry in report.kinds:
        assert entry.covered + len(entry.uncovered_ids) == entry.total
        assert entry.covered <= entry.total
        assert list(entry.uncovered_ids) == sorted(entry.uncovered_ids)
        assert approved_concept_id not in entry.uncovered_ids

    concept = report.kind(CoverageKind.CONCEPT)
    assert concept.total == sum(1 for card in concept_cards if card.is_approved)
    assert concept.covered == 1
    assert concept.coverage_fraction == pytest.approx(1 / concept.total)


def test_legal_surface_matches_permalink_bearing_provisions(
    authority: ValidatedRegistryAuthority,
    concept_cards: tuple[ConceptCardRecord, ...],
    casilla_records: tuple[CasillaSearchRecord, ...],
    legal_ids: tuple[str, ...],
) -> None:
    """The legal surface size equals an independent count of permalink provisions."""
    independent = sum(
        1
        for entry in authority.catalogues.legal.values()
        if getattr(entry, "permalink", None) and str(entry.permalink).strip()
    )
    report = compute_coverage_report(
        relevance=_sweep_from(()),
        concept_cards=concept_cards,
        casilla_records=casilla_records,
        legal_ids=legal_ids,
        authority=authority,
        **_EMPTY_CLI,
    )

    assert report.kind(CoverageKind.LEGAL).total == independent == len(legal_ids)


def test_coverage_report_pydantic_roundtrip(
    authority: ValidatedRegistryAuthority,
    concept_cards: tuple[ConceptCardRecord, ...],
    casilla_records: tuple[CasillaSearchRecord, ...],
    legal_ids: tuple[str, ...],
) -> None:
    """A report survives a strict JSON save -> load cycle with full equality."""
    report = compute_coverage_report(
        relevance=_sweep_from(("concept:prorrata", "legal:not-a-real-provision")),
        concept_cards=concept_cards,
        casilla_records=casilla_records,
        legal_ids=legal_ids,
        authority=authority,
        **_EMPTY_CLI,
    )

    restored = TerminologyCoverageReport.model_validate_json(report.model_dump_json())

    assert restored == report
    assert isinstance(restored.kinds[0], KindCoverage)


def test_report_over_the_committed_mapping_is_grounded(
    authority: ValidatedRegistryAuthority,
    concept_cards: tuple[ConceptCardRecord, ...],
    casilla_records: tuple[CasillaSearchRecord, ...],
    legal_ids: tuple[str, ...],
) -> None:
    """Against the real committed mapping the report is populated and honest.

    The refreshed manifest-admissible relevance references real concept cards,
    casillas, and legal provisions (so those surfaces show real coverage) and
    does not emit synthetic source-code targets as orphan mapping targets.
    """
    committed = load_committed_relevance()
    report = compute_coverage_report(
        relevance=committed,
        concept_cards=concept_cards,
        casilla_records=casilla_records,
        legal_ids=legal_ids,
        authority=authority,
        **_EMPTY_CLI,
    )

    assert report.referenced_target_count > 0
    assert report.kind(CoverageKind.CONCEPT).covered > 0
    assert report.kind(CoverageKind.LEGAL).covered > 0
    # The refreshed manifest-admissible relevance emits no synthetic code
    # targets, so the orphan report contains no ``code:`` ids.
    assert not any(orphan.startswith("code:") for orphan in report.orphan_mapping_target_ids)
    assert coverage_report_path().name == "coverage-report.json"


def _derivable_surface(
    concept_cards: tuple[ConceptCardRecord, ...],
    casilla_records: tuple[CasillaSearchRecord, ...],
    legal_ids: tuple[str, ...],
) -> set[str]:
    concept = {to_search_record(card).id for card in concept_cards if card.is_approved}
    casilla = {to_search_record(record).id for record in casilla_records}
    legal = {legal_target_record_id(legal_id) for legal_id in legal_ids}
    return concept | casilla | legal
