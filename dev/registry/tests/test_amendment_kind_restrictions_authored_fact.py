"""Authored correction restrictions and pinned evidence, without publication."""

from __future__ import annotations

import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from cadrumo.application.modelo.action_errors import AmendmentKindNotPermittedError
from cadrumo.application.modelo.amendment_kind_resolution import assert_amendment_kind_permitted
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.hashing import sha256_hex
from cadrumo.core.period import Period
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.text_fold import normalise_corpus_text
from cadrumo.domain.calculations.registry.amendment_regime_policy import (
    permitted_amendment_kind_values_for_period,
    resolve_amendment_regime_policy,
)
from cadrumo.domain.calculations.registry.facts.payloads import MappingFactPayload
from cadrumo.domain.calculations.registry.facts.resolution import reading_dated_facts_below_support
from cadrumo.domain.calculations.registry.facts.schema import GovernedFactCatalogue
from cadrumo.domain.calculations.registry.governed_fact_scope import CandidateFactAuthority, validating_governed_facts
from cadrumo.domain.calculations.registry.tests.authored_editions import open_ended_revision, revision_covering
from cadrumo.domain.modelos.filing_record import FilingDeclarationKind

from ..compiler.fact_loader import load_governed_fact_file
from ..compiler.loader import load_modelo_directory, load_shared_catalogues
from ..compiler.validate_evidence import EvidenceValidator

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _candidate() -> CandidateFactAuthority:
    fact = load_governed_fact_file(bundled_path("registry", "aeat", "facts", "0135-amendment-regime-policy.toml"))
    support = load_shared_catalogues(bundled_path("registry", "aeat")).require_supported_filing_years()
    return CandidateFactAuthority(GovernedFactCatalogue(facts={fact.fact_id: fact}), support)


def _policy_dates() -> dict[str, date]:
    """Every dated entry the authored amendment-regime policy declares, by its key."""
    variant = _candidate().catalogue.facts["amendment-regime-policy"].variants[0]
    assert isinstance(variant.payload, MappingFactPayload)
    dated: dict[str, date] = {}
    for entry in variant.payload.entries:
        if isinstance(entry.key, str) and entry.key.endswith(".date"):
            dated[entry.key] = entry.value if isinstance(entry.value, date) else date.fromisoformat(str(entry.value))
    return dated


def _quarter_of(day: date) -> int:
    return (day.month - 1) // 3 + 1


_POLICY_DATES = _policy_dates()
_BOUNDARY_303 = _POLICY_DATES["boundary.303.date"]
_BOUNDARY_100 = _POLICY_DATES["boundary.100.date"]
_BOUNDARY_200 = _POLICY_DATES["boundary.200.date"]
_RESTRICTED_FROM_130 = _POLICY_DATES["restriction.130.date"]
_LATER_PERIOD_369 = _POLICY_DATES["later_period_adjustment.369.date"]
_PRE = frozenset({"complementaria", "sustitutiva"})
_POST = frozenset({"rectificativa"})


def test_only_the_evidenced_modelos_have_dated_restrictions() -> None:
    with validating_governed_facts(_candidate()), reading_dated_facts_below_support():
        policy = resolve_amendment_regime_policy(effective_date=_RESTRICTED_FROM_130)
        assert set(policy.kind_restrictions) == {"130", "131", "303", "100", "200"}
        for modelo, boundary in (("303", _BOUNDARY_303), ("100", _BOUNDARY_100), ("200", _BOUNDARY_200)):
            assert policy.rectificativa_effective_from[modelo] == boundary
            assert policy.kind_restrictions[modelo].effective_from == boundary
            assert policy.kind_restrictions[modelo].permitted_kinds == frozenset({"rectificativa"})
        quarter = _quarter_of(_RESTRICTED_FROM_130)
        before = (
            Period.from_year_and_code(_RESTRICTED_FROM_130.year, f"{quarter - 1}T")
            if quarter > 1
            else Period.from_year_and_code(_RESTRICTED_FROM_130.year - 1, "4T")
        )
        first = Period.from_year_and_code(_RESTRICTED_FROM_130.year, f"{quarter}T")
        for modelo in ("130", "131"):
            assert policy.kind_restrictions[modelo].effective_from == _RESTRICTED_FROM_130
            assert permitted_amendment_kind_values_for_period(modelo, before) == _PRE
            assert permitted_amendment_kind_values_for_period(modelo, first) == frozenset({"complementaria"})


def test_every_supported_year_keeps_only_complementaria_for_m130_and_m131() -> None:
    candidate = _candidate()
    with validating_governed_facts(candidate):
        for year in range(candidate.support.floor, candidate.support.horizon + 1):
            for code in ("1T", "2T", "3T", "4T"):
                for modelo in ("130", "131"):
                    assert permitted_amendment_kind_values_for_period(
                        modelo, Period.from_year_and_code(year, code)
                    ) == frozenset({"complementaria"}), (modelo, year, code)


@pytest.mark.parametrize("modelo", ["130", "131"])
@pytest.mark.parametrize("kind", [FilingDeclarationKind.SUSTITUTIVA, FilingDeclarationKind.RECTIFICATIVA])
def test_existing_application_guard_refuses_unsupported_kinds_in_the_candidate_scope(
    modelo: str, kind: FilingDeclarationKind
) -> None:
    candidate = _candidate()
    period = Period.from_year_and_code(candidate.support.horizon, "1T")
    with validating_governed_facts(candidate):
        assert_amendment_kind_permitted(
            modelo=modelo, period=period, amendment_kind=FilingDeclarationKind.COMPLEMENTARIA
        )
        with pytest.raises(AmendmentKindNotPermittedError) as refused:
            assert_amendment_kind_permitted(modelo=modelo, period=period, amendment_kind=kind)
    assert refused.value.context is not None
    assert refused.value.context["requested_kind"] == kind.value
    assert refused.value.context["accepted_kinds"] == "complementaria"


@pytest.mark.parametrize(
    ("modelo", "year", "code", "expected"),
    [
        ("303", _BOUNDARY_303.year, f"{_quarter_of(_BOUNDARY_303) - 1}T", _PRE),
        ("303", _BOUNDARY_303.year, f"{_BOUNDARY_303.month - 1:02d}", _PRE),
        ("303", _BOUNDARY_303.year, f"{_quarter_of(_BOUNDARY_303)}T", _POST),
        ("303", _BOUNDARY_303.year, f"{_BOUNDARY_303.month:02d}", _POST),
        ("303", _BOUNDARY_303.year, f"{_quarter_of(_BOUNDARY_303) + 1}T", _POST),
        ("100", _BOUNDARY_100.year - 1, "0A", _PRE),
        ("100", _BOUNDARY_100.year, "0A", _POST),
        ("200", _BOUNDARY_200.year - 1, "0A", _PRE),
        ("200", _BOUNDARY_200.year, "0A", _POST),
        ("200", _BOUNDARY_200.year + 1, "0A", _POST),
        ("349", _BOUNDARY_303.year, "1T", _PRE),
        ("390", _BOUNDARY_303.year, "0A", _PRE),
        ("369", _LATER_PERIOD_369.year, f"{_quarter_of(_LATER_PERIOD_369) - 1}T", _PRE),
        ("369", _LATER_PERIOD_369.year, f"{_quarter_of(_LATER_PERIOD_369)}T", frozenset()),
    ],
)
def test_candidate_restricts_post_boundary_periods_and_preserves_other_procedures(
    modelo: str, year: int, code: str, expected: frozenset[str]
) -> None:
    with validating_governed_facts(_candidate()), reading_dated_facts_below_support():
        assert permitted_amendment_kind_values_for_period(modelo, Period.from_year_and_code(year, code)) == expected


def test_every_supported_year_intersects_the_dated_rectificativa_regime() -> None:
    candidate = _candidate()
    pre = _PRE
    post = _POST
    with validating_governed_facts(candidate):
        for year in range(candidate.support.floor, candidate.support.horizon + 1):
            for code in (
                "01",
                "02",
                "03",
                "04",
                "05",
                "06",
                "07",
                "08",
                "09",
                "10",
                "11",
                "12",
                "1T",
                "2T",
                "3T",
                "4T",
            ):
                period = Period.from_year_and_code(year, code)
                expected = post if period.end_date >= _BOUNDARY_303 else pre
                assert permitted_amendment_kind_values_for_period("303", period) == expected, (year, code)
            for modelo, boundary in (("100", _BOUNDARY_100), ("200", _BOUNDARY_200)):
                period = Period.from_year_and_code(year, "0A")
                expected = post if period.end_date >= boundary else pre
                assert permitted_amendment_kind_values_for_period(modelo, period) == expected, (modelo, year)


def test_sociedades_procedure_evidence_does_not_promote_the_boundary_year_revision() -> None:
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "200"))
    boundary_revision = revision_covering("200", _BOUNDARY_200.year)
    assert modelo.revisions[boundary_revision.id].authority_grade is RegistryAuthorityGrade.CALCULATION
    assert modelo.revisions[open_ended_revision("200").id].authority_grade is RegistryAuthorityGrade.FILING


@pytest.mark.parametrize(
    ("modelo", "source_id", "corpus_path"),
    [
        ("303", "aeat-manual-iva-2025", "corpus/manuals/iva/2025/source.pdf"),
        ("100", "aeat-renta-2025-manual-parte1", "corpus/manuals/renta/2025/part1/source.pdf"),
        ("200", "aeat-modelo-200-manual-2024", "corpus/manuals/sociedades/2024/source.pdf"),
    ],
)
def test_rectificativa_restrictions_cite_exact_pinned_affirmative_procedure_guidance(
    modelo: str, source_id: str, corpus_path: str
) -> None:
    # The digest, publisher URL, fetch instant and edition are what the corpus manifest beside the pdf recorded.
    manifest = json.loads(bundled_path(corpus_path).with_name("manifest.json").read_text(encoding="utf-8"))
    digest = manifest["sha256"]
    source_url = manifest["source_pdf_url"]
    retrieved_at = datetime.fromisoformat(manifest["fetched_at"]).astimezone(ZoneInfo("Europe/Madrid")).date()
    edition = manifest["year"]
    variant = _candidate().catalogue.facts["amendment-regime-policy"].variants[0]
    assert isinstance(variant.payload, MappingFactPayload)
    entries = {entry.key: entry.value for entry in variant.payload.entries}
    assert entries[f"restriction.{modelo}.source"] == source_id
    if modelo == "200":
        assert entries["boundary.200.source"] == source_id
    assert source_id in variant.source_refs
    (citation,) = (citation for citation in variant.source_citations if citation.source_ref == source_id)
    catalogues = load_shared_catalogues(bundled_path("registry", "aeat"))
    source = catalogues.sources[source_id]
    assert source.authority == "aeat"
    assert source.evidence_tier == "official_source_guidance"
    assert source.corpus_path == corpus_path
    assert source.sha256 == digest
    assert source.retrieved_at == retrieved_at
    assert source.source_url == source_url
    assert source.applies_from == date(edition, 1, 1)
    assert source.applies_to == date(edition, 12, 31)
    source_bytes = bundled_path(corpus_path).read_bytes()
    assert len(source_bytes) == source.bytes
    assert sha256_hex(source_bytes) == digest
    evidence = EvidenceValidator(legal_refs={}, source_refs=catalogues.sources, source_root=bundled_path())
    text = evidence.source_text(source)
    assert text is not None
    for required in citation.required_text:
        assert normalise_corpus_text(required) in text, (source_id, required)


def test_new_citations_match_the_exact_pinned_canonical_instructions_and_designs() -> None:
    candidate = _candidate()
    variant = candidate.catalogue.facts["amendment-regime-policy"].variants[0]
    catalogues = load_shared_catalogues(bundled_path("registry", "aeat"))
    evidence = EvidenceValidator(legal_refs={}, source_refs=catalogues.sources, source_root=bundled_path())
    expected_sources = {
        "aeat-modelo-130-instructions",
        "aeat-dr-130-2019-v12",
        "aeat-modelo-131-instructions",
        "aeat-dr-131-2019-2023-v101",
        "aeat-dr-131-2024",
        "aeat-dr-131-2025",
        "aeat-dr-131-2026",
        "aeat-dr-131-2026-late",
    }
    citations = {
        citation.source_ref: citation
        for citation in variant.source_citations
        if citation.source_ref in expected_sources
    }
    assert set(citations) == expected_sources
    for source_id, citation in citations.items():
        source = catalogues.sources[source_id]
        assert sha256_hex(bundled_path(source.corpus_path).read_bytes()) == source.sha256, source_id
        text = evidence.source_text(source)
        assert text is not None, source_id
        for required in citation.required_text:
            assert normalise_corpus_text(required) in text, (source_id, required)
