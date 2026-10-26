"""Real-behaviour tests for the Tier-A external seed importers.

The importers parse a Tier-A export (an IATE TBX file, a UBTERM CSV) into the
strict typed intermediate, map each entry onto an EXISTING concept by its
Spanish ``preferred`` label, and ADD missing-language terms / short
descriptions while stamping ``seed_provenance`` with the licence-required
attribution. These tests parse the REAL committed fixture exports (no mocks)
and apply them to a controlled fixture concept tree written to a tmp dir,
proving parse -> map -> provenance-stamp end-to-end.

The licence gate is proven REAL: an ND / NC / unlicensed source is refused
before any value is read, and EuroVoc is refused until its licence is
verified. A seed never auto-approves a draft, never overwrites curated prose,
and the seeded tree stays loader-valid with a no-op re-scaffold.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from cadrumo.core.concept_lifecycle import ConceptLifecycle
from cadrumo.core.external_constants import OutputLanguage

from .._enrolment import EnrolmentCandidate
from .._scaffold import ScaffoldAction, scaffold_handbook
from .._seed_import import (
    SeedEntry,
    SeedImportError,
    SeedLicenceError,
    SeedSource,
    SeedTerm,
    apply_seed_entries,
    assert_source_ingestible,
    parse_iate_tbx,
    parse_ubterm_csv,
    source_attribution,
)
from ..enums import ConceptDomain, TermStatus
from ..loader import load_terminology_handbook

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_TODAY = date(2026, 6, 11)
_FIXTURES = Path(__file__).parent / "fixtures"

# A controlled concept whose es preferred label is the Spanish key the
# fixtures seed, deliberately MISSING the en / ca / hu sections so the seed
# has a real gap to fill. Mirrors the curation-test fixture pattern.
_PRORRATA_ES_ONLY = """
[concept]
concept_id = "prorrata"
domain = "concepto"
lifecycle = "draft"
created_at = 2026-06-10
updated_at = 2026-06-10

[language.es]
short_description = "Porcentaje de IVA deducible en actividad mixta."

[[language.es.term]]
label = "prorrata de deduccion"
term_status = "preferred"
"""


def _write_tree(tmp_path: Path, *fragments: tuple[str, str]) -> Path:
    concepts_dir = tmp_path / "concepts"
    concepts_dir.mkdir()
    for name, body in fragments:
        (concepts_dir / f"{name}.toml").write_text(body, encoding="utf-8")
    return concepts_dir


# ---------------------------------------------------------------------------
# Licence gate — the hard, structural refusal
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        SeedSource.TERMCAT_OBERTA,
        SeedSource.TERMCAT_UOC_IATE,
        SeedSource.RAE_DPEJ,
        SeedSource.MICROSOFT_TERMINOLOGY,
    ],
)
def test_excluded_source_is_refused(source: SeedSource) -> None:
    """An ND / NC / unlicensed source is refused before any value is read.

    The licence gate is real, not honor-system: reformatting a CC BY-ND
    source into Handbook records is itself a derivative, so the refusal is
    categorical and names the reason.
    """
    with pytest.raises(SeedLicenceError) as excinfo:
        assert_source_ingestible(source)
    assert source.value in str(excinfo.value)


def test_eurovoc_refused_until_licence_verified() -> None:
    """EuroVoc is refused until its download-page licence is confirmed.

    EuroVoc is ingestible only after licence verification on the Publications
    Office download page. That verification has not been done in this
    environment, so the gate refuses it and says why.
    """
    with pytest.raises(SeedLicenceError) as excinfo:
        assert_source_ingestible(SeedSource.EUROVOC)
    assert "licence not yet verified" in str(excinfo.value)


@pytest.mark.parametrize("source", [SeedSource.IATE, SeedSource.UBTERM])
def test_tier_a_source_is_ingestible_with_attribution(source: SeedSource) -> None:
    """IATE and UBTERM are ingestible and carry a non-empty attribution string."""
    assert_source_ingestible(source)  # does not raise
    attribution = source_attribution(source)
    assert attribution.strip()
    # The attribution names the source / licence so it survives onto the card.
    assert source.value in attribution.lower() or "CC BY" in attribution or "European Union" in attribution


def test_excluded_source_has_no_attribution() -> None:
    """``source_attribution`` refuses an excluded source (no laundering path)."""
    with pytest.raises(SeedLicenceError):
        source_attribution(SeedSource.TERMCAT_OBERTA)


# ---------------------------------------------------------------------------
# Parsers — real fixture export -> typed intermediate
# ---------------------------------------------------------------------------


def test_parse_iate_tbx_filters_and_maps_terms() -> None:
    """The IATE TBX parser reads the real fixture, filtering reliability + domain.

    The fixture carries three entries: a finance term at reliability 9, a
    finance term at reliability 1 (below the floor), and an off-domain
    chemistry term. With ``min_reliability=3`` and the ``finance`` domain
    filter only the first survives, and its termType maps fullForm ->
    preferred, synonym -> admitted.
    """
    entries = parse_iate_tbx(
        _FIXTURES / "iate-sample.tbx",
        min_reliability=3,
        domains=frozenset({"finance", "law", "taxation"}),
    )
    assert len(entries) == 1
    entry = entries[0]
    assert entry.source is SeedSource.IATE
    assert entry.spanish_key == "prorrata de deduccion"
    assert entry.source_entry_id == "IATE-1126728"

    by_lang_label = {(term.language, term.label): term.term_status for term in entry.terms}
    assert by_lang_label[(OutputLanguage.ES, "prorrata de deduccion")] is TermStatus.PREFERRED
    assert by_lang_label[(OutputLanguage.EN, "deductible proportion")] is TermStatus.PREFERRED
    assert by_lang_label[(OutputLanguage.EN, "pro rata")] is TermStatus.ADMITTED
    assert by_lang_label[(OutputLanguage.HU, "levonasi hanyad")] is TermStatus.PREFERRED


def test_parse_iate_tbx_without_domain_filter_keeps_reliable_entries() -> None:
    """Without a domain filter the reliability floor still drops the weak entry."""
    entries = parse_iate_tbx(_FIXTURES / "iate-sample.tbx", min_reliability=3, domains=None)
    keys = {entry.spanish_key for entry in entries}
    assert "prorrata de deduccion" in keys
    assert "termino fuera de dominio" in keys  # off-domain but reliable, no filter
    assert "termino poco fiable" not in keys  # reliability 1 < 3


def test_parse_ubterm_csv_reads_trilingual_rows() -> None:
    """The UBTERM CSV parser reads the real fixture into trilingual seed entries."""
    entries = parse_ubterm_csv(_FIXTURES / "ubterm-sample.csv")
    by_key = {entry.spanish_key: entry for entry in entries}
    assert set(by_key) == {"prorrata de deduccion", "sujeto pasivo"}

    prorrata = by_key["prorrata de deduccion"]
    assert prorrata.source is SeedSource.UBTERM
    langs = {term.language for term in prorrata.terms}
    assert langs == {OutputLanguage.ES, OutputLanguage.CA, OutputLanguage.EN}
    es_term = next(t for t in prorrata.terms if t.language is OutputLanguage.ES)
    assert es_term.short_description == "Percentatge d'IVA deduible en activitat mixta."


def test_parse_ubterm_csv_rejects_missing_es_column(tmp_path: Path) -> None:
    """A CSV without the required ``es`` column is refused, not silently empty."""
    bad = tmp_path / "bad.csv"
    bad.write_text("ca,en\nx,y\n", encoding="utf-8")
    with pytest.raises(SeedImportError):
        parse_ubterm_csv(bad)


# ---------------------------------------------------------------------------
# Mapper — gap-fill, provenance stamp, preserve, no auto-approve
# ---------------------------------------------------------------------------


def test_apply_seeds_fills_missing_languages_and_stamps_provenance(tmp_path: Path) -> None:
    """Seeds fill missing-language sections and stamp the required attribution.

    The controlled ``prorrata`` concept has only an ``es`` section; the IATE
    fixture supplies en + hu. After apply the concept gains en and hu sections
    (with the seeded terms) and carries ``seed_provenance`` stamped with IATE's
    attribution. ``es`` (already present) is untouched.
    """
    concepts_dir = _write_tree(tmp_path, ("prorrata", _PRORRATA_ES_ONLY))
    entries = parse_iate_tbx(
        _FIXTURES / "iate-sample.tbx",
        min_reliability=3,
        domains=frozenset({"finance"}),
    )

    result = apply_seed_entries(entries, concepts_dir=concepts_dir, today=_TODAY)

    assert result.matched_concepts == ("prorrata",)
    assert result.unmatched_keys == ()
    assert result.languages_added == 2  # en + hu

    reloaded = load_terminology_handbook(concepts_dir).concept("prorrata")
    langs = {section.language for section in reloaded.languages}
    assert langs == {OutputLanguage.ES, OutputLanguage.EN, OutputLanguage.HU}

    en = next(s for s in reloaded.languages if s.language is OutputLanguage.EN)
    en_labels = {term.label: term.term_status for term in en.terms}
    assert en_labels["deductible proportion"] is TermStatus.PREFERRED
    assert en_labels["pro rata"] is TermStatus.ADMITTED

    assert reloaded.seed_provenance is not None
    assert reloaded.seed_provenance.source == SeedSource.IATE.value
    assert "European Union" in reloaded.seed_provenance.attribution
    assert reloaded.seed_provenance.source_entry_id == "IATE-1126728"


def test_apply_seeds_does_not_overwrite_curated_es(tmp_path: Path) -> None:
    """A seed never overwrites a curated value: the existing es short_description survives.

    The UBTERM fixture carries a Spanish gloss in ``definition_es``; the es
    section already exists with a curated short_description, so the seed must
    NOT touch it. The new ca section gets the ca preferred label as its card
    text (a source value, never invented prose -- there is no ca gloss in the
    fixture).
    """
    concepts_dir = _write_tree(tmp_path, ("prorrata", _PRORRATA_ES_ONLY))
    entries = parse_ubterm_csv(_FIXTURES / "ubterm-sample.csv")

    apply_seed_entries(entries, concepts_dir=concepts_dir, today=_TODAY)

    reloaded = load_terminology_handbook(concepts_dir).concept("prorrata")
    es = next(s for s in reloaded.languages if s.language is OutputLanguage.ES)
    assert es.short_description == "Porcentaje de IVA deducible en actividad mixta."
    ca = next(s for s in reloaded.languages if s.language is OutputLanguage.CA)
    assert ca.short_description == "prorrata de deduccio"  # the ca source label, not a fabricated gloss
    ca_labels = {term.label for term in ca.terms}
    assert "prorrata de deduccio" in ca_labels


def test_apply_seeds_never_auto_approves_a_draft(tmp_path: Path) -> None:
    """A seeded draft stays a draft -- a seed never satisfies approved-completeness."""
    concepts_dir = _write_tree(tmp_path, ("prorrata", _PRORRATA_ES_ONLY))
    entries = parse_iate_tbx(_FIXTURES / "iate-sample.tbx", min_reliability=3, domains=frozenset({"finance"}))

    apply_seed_entries(entries, concepts_dir=concepts_dir, today=_TODAY)

    reloaded = load_terminology_handbook(concepts_dir).concept("prorrata")
    assert reloaded.lifecycle is ConceptLifecycle.DRAFT


def test_apply_seeds_is_idempotent(tmp_path: Path) -> None:
    """A second identical seed run is a no-op (no new languages or aliases)."""
    concepts_dir = _write_tree(tmp_path, ("prorrata", _PRORRATA_ES_ONLY))
    entries = parse_iate_tbx(_FIXTURES / "iate-sample.tbx", min_reliability=3, domains=frozenset({"finance"}))

    first = apply_seed_entries(entries, concepts_dir=concepts_dir, today=_TODAY)
    assert first.languages_added == 2
    second = apply_seed_entries(entries, concepts_dir=concepts_dir, today=_TODAY)
    assert second.languages_added == 0
    assert second.aliases_added == 0
    assert second.matched_concepts == ("prorrata",)


def test_apply_seeds_reports_unmatched_keys(tmp_path: Path) -> None:
    """A seed whose Spanish key matches no concept is reported, never invented.

    The UBTERM fixture's ``sujeto pasivo`` row has no matching concept in the
    single-concept tree; it must surface in ``unmatched_keys`` rather than
    creating a fabricated concept.
    """
    concepts_dir = _write_tree(tmp_path, ("prorrata", _PRORRATA_ES_ONLY))
    entries = parse_ubterm_csv(_FIXTURES / "ubterm-sample.csv")

    result = apply_seed_entries(entries, concepts_dir=concepts_dir, today=_TODAY)
    assert "sujeto pasivo" in result.unmatched_keys
    assert "prorrata" in result.matched_concepts
    # No fabricated concept was created.
    ids = {c.concept_id for c in load_terminology_handbook(concepts_dir).concepts}
    assert ids == {"prorrata"}


def test_seeded_tree_stays_loader_valid_and_dry_run_does_not_write(tmp_path: Path) -> None:
    """A dry-run apply computes the result without writing any fragment."""
    concepts_dir = _write_tree(tmp_path, ("prorrata", _PRORRATA_ES_ONLY))
    entries = parse_iate_tbx(_FIXTURES / "iate-sample.tbx", min_reliability=3, domains=frozenset({"finance"}))

    before = (concepts_dir / "prorrata.toml").read_text(encoding="utf-8")
    result = apply_seed_entries(entries, concepts_dir=concepts_dir, today=_TODAY, write=False)
    after = (concepts_dir / "prorrata.toml").read_text(encoding="utf-8")

    assert result.languages_added == 2
    assert result.written_paths == ()
    assert before == after  # nothing written


def test_re_scaffold_after_seeding_is_a_no_op(tmp_path: Path) -> None:
    """A re-scaffold after seeding preserves the seeded values (msgmerge PRESERVE).

    Seeds add curated-grade translations; the scaffold's PRESERVE outcome
    must carry them verbatim, so re-scaffolding the seeded tree (with the
    matching enrolment candidate present) produces NO new drafts and NO
    retires for the seeded concept -- it is UNCHANGED.
    """
    concepts_dir = _write_tree(tmp_path, ("prorrata", _PRORRATA_ES_ONLY))
    entries = parse_iate_tbx(_FIXTURES / "iate-sample.tbx", min_reliability=3, domains=frozenset({"finance"}))
    seeded = apply_seed_entries(entries, concepts_dir=concepts_dir, today=_TODAY)

    # The PRESERVE claim below is only meaningful if seeding actually added
    # something. With an empty entry set - a renamed fixture, a domain filter
    # that stops matching - apply_seed_entries is a no-op, and re-scaffolding
    # an unseeded tree preserves it trivially while every assertion still
    # holds. The result carries that evidence and was discarded.
    assert seeded.matched_concepts == ("prorrata",), seeded
    assert seeded.languages_added > 0, seeded

    before = (concepts_dir / "prorrata.toml").read_text(encoding="utf-8")
    candidates = {
        "prorrata": EnrolmentCandidate(concept_id="prorrata", domain=ConceptDomain.CONCEPTO),
    }
    plan = scaffold_handbook(concepts_dir, candidates, today=_TODAY)
    after = (concepts_dir / "prorrata.toml").read_text(encoding="utf-8")

    assert plan.counts[ScaffoldAction.SCAFFOLD_EMPTY] == 0
    assert plan.counts[ScaffoldAction.RETIRE] == 0
    assert before == after  # seeded values preserved byte-for-byte


def test_bundled_handbook_stays_loader_valid_after_step() -> None:
    """The committed bundled tree still loads and validates (no fragments seeded).

    This step ships importers + fixtures, not seeded production fragments, so
    the bundled Handbook is unchanged and its full validator inventory passes.
    """
    from ..validators import default_handbook_validators

    handbook = load_terminology_handbook(validators=default_handbook_validators())
    assert len(handbook.concepts) >= 95


def test_seed_entry_refuses_unattributed_source() -> None:
    """A SeedEntry whose source has no attribution is refused at construction.

    Defence in depth: a source enum member with no attribution mapping (the
    excluded sources) cannot be built into a SeedEntry, so no un-attributed
    value can reach the mapper. The refusal surfaces through pydantic's
    ValidationError wrapping the SeedImportError raised by the entry
    validator.
    """
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as excinfo:
        SeedEntry(
            source=SeedSource.RAE_DPEJ,
            spanish_key="x",
            terms=(SeedTerm(language=OutputLanguage.ES, label="x", term_status=TermStatus.PREFERRED),),
        )
    assert "has no attribution" in str(excinfo.value)
