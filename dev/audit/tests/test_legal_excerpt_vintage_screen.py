"""Prove the vintage screen bridges both surfaces and refuses to lose an entry.

The instrument this screen replaces failed in two ways at once, and both are
pinned here. It derived a consolidated anchor from a form that BOE does not
use, so it landed on a NEIGHBOURING provision and reported total divergence
against perfectly current text; and when derivation reached nothing at all the
entry fell silently out of the comparison, so the published coverage ratio was
measured against a denominator that excluded a third of its own population.

Every case drives the real functions. The two corpus-pinned controls at the end
drive the whole screen over the real bundled corpus, because a derivation that
works on synthetic tokens and misses on the real anchor scheme is precisely the
failure that produced this rewrite.
"""

from __future__ import annotations

import pytest

from cadrumo.core.corpus_text import resolve_anchored_extracted_unit
from cadrumo.core.directory_scan import scan_directory

from ..._paths import REPO_ROOT
from ...corpus.fetch_boe_normative import (
    ArticleRedaction,
    NormativeAcquisitionError,
    article_block_title,
    article_redaction_markup,
    assert_serves_the_article_in_force,
)
from ..legal_catalogue import LEGAL_DIR, load_legal_entries, required_text_by_entry
from ..legal_excerpt_vintage_screen import (
    Finding,
    OracleKind,
    Verdict,
    _classify,
    _is_vintaged,
    article_payloads,
    candidate_keys,
    clause_chunks,
    confirms_citation,
    norm_root,
    ordinal_spellings,
    readable_units,
    screen,
    structural_key,
    summarise,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT = REPO_ROOT


def test_a_latin_ordinal_is_concatenated_into_the_anchor() -> None:
    """The core bridge: hyphenated citation, separator-free sidecar anchor.

    ``art-163-octiesdecies`` and ``#a163octiesdecies`` name one provision and
    nothing in the corpus connects them. Getting this wrong resolved the whole
    ``art-163-*`` family onto article 163 itself.
    """
    keys = candidate_keys("art-163-octiesdecies")
    assert "a163octiesdecies" in keys
    assert "Articulo 163 octiesdecies" in keys


def test_a_bare_article_number_still_derives() -> None:
    assert candidate_keys("art-81") == ("Articulo 81", "a81")


def test_an_apartado_suffix_narrows_within_the_article_and_is_dropped() -> None:
    """A consolidated file carries the whole article, not its apartados."""
    assert candidate_keys("art-68.1") == ("Articulo 68", "a68")


def test_a_vintage_year_suffix_is_not_read_as_a_sub_article() -> None:
    assert candidate_keys("art-52-2015") == ("Articulo 52", "a52")


def test_the_hyphenated_sub_article_key_is_never_emitted() -> None:
    """Canonicalisation strips the hyphen, so ``a6-3`` collides with article 63.

    This exact key was emitted during authoring and silently resolved
    ``rdleg-1-2004:art-6.3`` onto ``Artículo 63``. Pinned so the plausible
    'try the narrower anchor first' reading cannot come back.
    """
    assert not any("-" in key for key in candidate_keys("art-6.3") if not key.startswith("Articulo"))
    assert "a6-3" not in candidate_keys("art-6.3")


def test_a_disposicion_derives_its_written_ordinal() -> None:
    """BOE titles disposiciones in words, and the catalogue cites them in digits."""
    keys = candidate_keys("da-14")
    assert "Disposicion adicional decimocuarta" in keys


def test_the_elided_ordinal_spelling_is_offered() -> None:
    """BOE writes 'decimoctava', not 'decimaoctava'.

    ``ley-58-2003:da-18`` is unreachable without it, and dropped silently out
    of the comparison for exactly this reason.
    """
    assert "decimoctava" in ordinal_spellings(18, feminine=True)


def test_both_gendered_tens_are_offered_because_boe_uses_both() -> None:
    """The same corpus carries 'vigésima primera' and 'vigésimo primera'."""
    spellings = ordinal_spellings(21, feminine=True)
    assert "vigesima primera" in spellings
    assert "vigesimo primera" in spellings


def test_an_ordinal_outside_the_supported_range_is_reported_as_nothing() -> None:
    """An empty return becomes an unresolved verdict, never a wrong answer."""
    assert ordinal_spellings(0, feminine=True) == ()
    assert ordinal_spellings(100, feminine=True) == ()


def test_an_orden_apartado_derives_a_masculine_ordinal_heading() -> None:
    """An orden structures by 'Primero.', 'Sexto.', not by numbered articles."""
    assert "Sexto" in candidate_keys("apartado-6")


def test_an_unrecognised_token_derives_nothing_rather_than_guessing() -> None:
    assert candidate_keys("") == ()
    assert candidate_keys("preambulo") == ()


def test_structural_key_ignores_accent_nbsp_and_caption() -> None:
    """The corpus and the catalogue disagree on all three often enough to matter."""
    assert structural_key("Artículo 43. Silencio administrativo.") == structural_key("Articulo\xa043")
    assert structural_key("Artículo 79. Deducciones.") == "a79"


def test_a_curated_title_yields_no_usable_structural_key() -> None:
    """An excerpt titled 'Ley 35/2006 Art. 48 ...' cannot confirm its identity.

    The screen must report that weakness rather than treat the derived key as
    corroborated, so the truncating split here is the intended behaviour.
    """
    assert structural_key("Ley 35/2006 Art. 48 rendimientos") == "ley352006art"


def test_clause_chunks_drop_enumerators_and_keep_operative_text() -> None:
    """An enumerator counted as an absent clause would drown the real signal."""
    text = "Uno.\n1.\nLos empresarios o profesionales que realicen entregas de bienes quedan obligados a repercutir."
    chunks = clause_chunks(text)
    assert len(chunks) == 1
    assert chunks[0].startswith("los empresarios o profesionales")


def test_norm_root_takes_the_shortest_bundled_prefix() -> None:
    """A longer prefix is a sibling excerpt of the same norm, not the norm."""
    stems = frozenset({"ley-37-1992", "ley-37-1992-art-163", "ley-37-1992-art-163-octiesdecies"})
    assert norm_root("ley-37-1992-art-163-octiesdecies", stems) == ("ley-37-1992", "art-163-octiesdecies")


def test_norm_root_reports_nothing_for_a_consolidated_file() -> None:
    assert norm_root("ley-37-1992", frozenset({"ley-37-1992"})) is None


def test_the_summary_refuses_a_split_that_does_not_reconcile() -> None:
    """The guarantee the previous instrument lacked.

    A verdict list shorter than its input population means entries were lost on
    the way, and any ratio printed from it is measured against a denominator
    nobody can check.
    """
    findings = [Finding("a:art-1", Verdict.MATCHES, ""), Finding("a:art-2", Verdict.MATCHES, "")]
    assert "COUNTS DO NOT RECONCILE" in summarise(findings, population=3)
    assert "COUNTS DO NOT RECONCILE" not in summarise(findings, population=2)


def test_every_verdict_appears_in_a_reconciled_summary() -> None:
    """No verdict class may be dropped from the published split."""
    findings = [Finding(f"a:art-{index}", verdict, "") for index, verdict in enumerate(Verdict)]
    rendered = summarise(findings, population=len(findings))
    for verdict in Verdict:
        assert verdict.value in rendered


def test_a_resolution_failure_renders_its_reason() -> None:
    """An unresolved entry must say why, or it is a drop-out with extra steps."""
    rendered = Finding("x:da-99", Verdict.UNRESOLVED, "no candidate key reached a unit").render()
    assert "unresolved" in rendered
    assert "no candidate key reached a unit" in rendered


def test_the_screen_reconciles_over_the_real_corpus() -> None:
    """Exhaustiveness over the real population, not over a fixture.

    The screen's central claim is that its verdict classes cover every entry it
    reads. Proved against the bundled corpus so a shape nobody anticipated
    cannot slip through as a silent omission.
    """
    result = screen(_REPO_ROOT)
    assert result.population > 0
    assert len(result.findings) == result.population
    assert "COUNTS DO NOT RECONCILE" not in summarise(list(result.findings), result.population)


def test_the_octiesdecies_control_reaches_its_own_anchor_and_matches() -> None:
    """Corpus-pinned control: the family the old instrument called superseded.

    ``ley-37-1992:art-163-octiesdecies`` was reported at 100 per cent clause
    absence and triaged as possible wholesale supersession. Hand-checked, the
    excerpt and the consolidated unit are verbatim identical over the opening
    operative sentence. A failure here means either the derivation regressed or
    the bundled article genuinely changed -- both worth stopping for.
    """
    finding = next(item for item in screen(_REPO_ROOT).findings if item.entry_id == "ley-37-1992:art-163-octiesdecies")
    assert finding.resolved_anchor == "#a163octiesdecies"
    assert finding.verdict is Verdict.MATCHES
    assert finding.opening_sentence_matches
    assert finding.identity_confirmed


def test_the_art_81_control_still_comes_out_divergent() -> None:
    """Corpus-pinned control against over-reach.

    ``ley-35-2006:art-81`` carries a repealed cotizaciones ceiling alongside
    post-2023 text and is divergent by hand-checked evidence. An instrument
    that turned the octiesdecies family green while also turning this green
    would be agreeing with everything rather than measuring anything.
    """
    finding = next(item for item in screen(_REPO_ROOT).findings if item.entry_id == "ley-35-2006:art-81")
    assert finding.verdict in {Verdict.DIVERGES_GATE_FIRES, Verdict.DIVERGES_GATE_GREEN}
    assert finding.clauses_absent > 0
    assert finding.identity_confirmed


def test_a_norm_named_after_its_own_year_is_not_a_declared_vintage() -> None:
    """The false-clean-verdict guard, and the reason it exists.

    ``vintaged`` asserts that divergence from current text is CORRECT by
    design, so a wrong one excuses real staleness. Almost every norm carries
    its enactment year in its name, and reading a trailing year as a vintage
    suffix called 29 bare-norm excerpts vintaged the moment the population
    widened. A vintage year FOLLOWS a citation token; a norm year does not.
    """
    assert _is_vintaged("ley-35-2006-art-52-2015")
    assert _is_vintaged("ley-58-2003-da-18-2021")
    assert not _is_vintaged("orden-hac-590-2021")
    assert not _is_vintaged("trlirnr-rdleg-5-2004")
    assert not _is_vintaged("ley-12-2002")


def test_the_article_payload_population_is_reached_through_its_own_oracle() -> None:
    """Corpus-pinned control: the newly reachable population is really measured.

    These entries cite an excerpt whose norm ships no whole-norm consolidation,
    so before the article payloads were bundled they had no oracle at all --
    and before the population boundary was split on unit count they were not
    even counted. A regression here means either the second oracle stopped
    resolving or the boundary silently swallowed them again.
    """
    findings = screen(_REPO_ROOT).findings
    reached = [item for item in findings if item.oracle_kind is OracleKind.ARTICLE_REDACTION]
    assert len(reached) > 20
    assert all(item.clauses_total > 0 for item in reached)
    dividends = next(item for item in reached if item.entry_id == "convenio-es-de-2011:art-10")
    assert dividends.identity_confirmed
    assert dividends.opening_sentence_matches
    assert dividends.resolved_anchor == "#a10"


def test_the_catalogue_anchor_is_reported_when_it_disagrees_with_boe() -> None:
    """BOE's block id is positional; matching on the catalogue anchor mis-pairs.

    Article 10 of the Spain-Netherlands convention lives at block ``a1-2`` and
    article 11 of the Spain-Morocco convention at ``ar-10``. An instrument
    keyed on the catalogue's own anchor would have compared each against a
    different provision and reported the difference as supersession.
    """
    findings = screen(_REPO_ROOT).findings
    netherlands = next(item for item in findings if item.entry_id == "convenio-es-nl-1971:art-10")
    assert netherlands.boe_block == "a1-2"
    assert netherlands.anchor_names_another_block
    morocco = next(item for item in findings if item.entry_id == "convenio-es-ma-1978:art-11")
    assert morocco.boe_block == "ar-10"
    assert morocco.anchor_names_another_block
    # The same provision spelled two ways is a disagreement and NOT a hazard;
    # collapsing the two would make the reported list unactionable.
    germany = next(item for item in findings if item.entry_id == "convenio-es-de-2011:art-10")
    assert germany.anchor_disagrees
    assert not germany.anchor_names_another_block


def test_the_entries_citing_their_whole_norm_are_counted_not_skipped() -> None:
    """The population boundary must state its exclusion, not perform it silently.

    An entry citing its norm's whole consolidated file has no excerpt to
    compare and is out of scope. An excerpt whose norm ships no consolidation
    looks identical at that test and is squarely IN scope; 97 such entries left
    the population before it was counted.
    """
    result = screen(_REPO_ROOT)
    assert result.cites_consolidated_norm > 0
    assert len(result.findings) == result.population
    single_unit_excerpts = [item for item in result.findings if item.oracle_kind is not OracleKind.CONSOLIDATED_NORM]
    assert single_unit_excerpts, "the recovered subpopulation must be present in the findings, not skipped"


def test_a_redaction_is_sliced_by_identity_and_never_by_position() -> None:
    """Order is the trap: this endpoint emits oldest first, ``act.php`` newest first."""
    payload = (
        "<response><status><code>200</code><text>ok</text></status><data>"
        '<bloque id="a9" tipo="precepto" titulo="Artículo 9">'
        '<version id_norma="BOE-A-1990-1" fecha_publicacion="19900101" fecha_vigencia="19900101">'
        "<p>el tipo sera del 3 por 100.</p></version>"
        '<version id_norma="BOE-A-2020-2" fecha_publicacion="20200101" fecha_vigencia="20200101">'
        "<p>el tipo sera del 21 por 100.</p></version>"
        "</bloque></data></response>"
    )
    in_force = assert_serves_the_article_in_force(payload, document_id="BOE-A-1990-1", block="a9")
    assert in_force.vigencia == "20200101"
    assert "21 por 100" in article_redaction_markup(payload, in_force)
    assert "3 por 100" not in article_redaction_markup(payload, in_force)
    superseded = ArticleRedaction(amending_norm="BOE-A-1990-1", vigencia="19900101")
    assert "3 por 100" in article_redaction_markup(payload, superseded)
    assert article_block_title(payload) == "Artículo 9"


def test_the_take_the_first_redaction_error_would_show_here_as_a_false_clean() -> None:
    """Corpus-pinned control on the redaction the screen reads.

    ``ley-19-1991:art-30`` (cuota íntegra del Impuesto sobre el Patrimonio) is
    served by a payload carrying several redactions oldest first. Measured
    against the ORIGINAL 1991 redaction the excerpt comes out ``matches`` --
    a full false clean verdict on a provision whose scale has been rewritten
    repeatedly. Measured against the redaction in force it diverges. A failure
    here means the screen started reading a redaction that is not the one in
    force, which is the single defect that would invert its conclusions.
    """
    finding = next(item for item in screen(_REPO_ROOT).findings if item.entry_id == "ley-19-1991:art-30")
    assert finding.oracle_kind is OracleKind.ARTICLE_REDACTION
    assert finding.verdict is not Verdict.MATCHES
    assert finding.clauses_absent > 0


def test_a_tied_redaction_date_refuses_rather_than_picking() -> None:
    """Art. 91 of LIVA carries two redactions dated 19950120, at 3 % and 4 %.

    An arbitrary pick between them can return the SUPERSEDED rate, which is the
    exact defect the article endpoint was reached for. The refusal is what makes
    ``oracle_indeterminate`` a real verdict rather than a decorative one.
    """
    payload = (
        "<response><status><code>200</code><text>ok</text></status><data>"
        '<bloque id="a91" tipo="precepto" titulo="Artículo 91">'
        '<version id_norma="BOE-A-1994-1" fecha_publicacion="19941230" fecha_vigencia="19950120">'
        "<p>el tipo sera del 3 por 100.</p></version>"
        '<version id_norma="BOE-A-1995-2" fecha_publicacion="19951230" fecha_vigencia="19950120">'
        "<p>el tipo sera del 4 por 100.</p></version>"
        "</bloque></data></response>"
    )
    with pytest.raises(NormativeAcquisitionError, match="share the latest fecha_vigencia"):
        assert_serves_the_article_in_force(payload, document_id="BOE-A-1994-1", block="a91")


def test_a_superset_excerpt_no_longer_hides_inside_matches() -> None:
    """Corpus-pinned control on the direction the screen could not see.

    RGAT article 25 is the measured case. Its article-endpoint capture carries
    every clause of the consolidated article AND two operative lettered clauses
    -- the empresarios/profesionales and the personas jurídicas limbs of the old
    apartado 2 list -- that the current article does not contain. Counting only
    the clauses of current text absent from the excerpt reported that pairing
    ``matches``, under a docstring asserting there was nothing for a gate to
    catch: blind in exactly the direction the governing decision's negative
    clause exists to express.

    Driven off the two bundled DOCUMENTS rather than off whichever entry cites
    them, because which document an entry cites is catalogue authoring and
    moves for reasons that have nothing to do with whether this count works.
    The classification is the real one; only the pairing is supplied.
    """
    corpus = _REPO_ROOT / "src/cadrumo/_data/corpus/normatives/html"
    excerpt_units = readable_units(corpus / "rd-1065-2007-art-25.html.extracted.json")
    assert len(excerpt_units) == 1
    rendered = resolve_anchored_extracted_unit(
        corpus / "rd-1065-2007.html.extracted.json", anchor="a25", include_title=True
    )
    current_title, _, current_text = rendered.partition("\n")
    finding = _classify(
        "rd-1065-2007:art-25",
        {},
        "rd-1065-2007-art-25",
        excerpt_units[0],
        current_title,
        current_text,
        identity_confirmed=False,
        citation_confirmed=True,
        resolved_anchor="#a25",
        oracle_kind=OracleKind.CONSOLIDATED_NORM,
    )
    assert finding.clauses_absent == 0
    assert finding.clauses_extra >= 2
    assert finding.verdict is Verdict.EXCERPT_CARRIES_MORE


def test_a_provenance_banner_is_not_counted_as_excerpt_side_divergence() -> None:
    """The artefact that must NOT be lumped in with the real case.

    ``rd-439-2007:art-115`` also carries one excerpt clause the current article
    lacks, and it is a curator's stamp -- "Texto consolidado BOE-A-2007-6820,
    artículo 115, redacción vigente tras Real Decreto 1008/2023" -- not a clause
    of the provision. Counting it would put a correctly-transcribed excerpt on
    the same worklist as a surviving repealed clause, and a worklist that is
    half annotation gets read by nobody.
    """
    finding = next(item for item in screen(_REPO_ROOT).findings if item.entry_id == "rd-439-2007:art-115")
    assert finding.clauses_extra == 0
    assert finding.clauses_absent == 0
    assert finding.verdict is Verdict.MATCHES


def test_matches_now_means_neither_direction_diverges() -> None:
    """The verdict's claim must hold in both directions, or it is not a match.

    Paired with the two controls above so the class cannot be satisfied by an
    instrument that simply reports everything as carrying more.
    """
    findings = screen(_REPO_ROOT).findings
    matching = [item for item in findings if item.verdict is Verdict.MATCHES]
    assert matching
    assert all(item.clauses_absent == 0 and item.clauses_extra == 0 for item in matching)
    octiesdecies = next(item for item in findings if item.entry_id == "ley-37-1992:art-163-octiesdecies")
    assert octiesdecies.verdict is Verdict.MATCHES
    assert octiesdecies.clauses_extra == 0


def test_the_excerpt_side_class_is_counted_as_a_measured_divergence() -> None:
    """It must reach the published split, not sit in a footnote.

    An entry the screen can see but the summary cannot report is the same
    silent-subpopulation defect one layer up.
    """
    findings = [
        Finding("a:art-1", Verdict.MATCHES, ""),
        Finding("a:art-2", Verdict.EXCERPT_CARRIES_MORE, "", clauses_extra=2),
        Finding("a:art-3", Verdict.DIVERGES_GATE_FIRES, "", clauses_absent=1),
    ]
    rendered = summarise(findings, population=3)
    assert "excerpt_carries_more" in rendered
    assert "comparable: 3 of 3" in rendered
    assert "of 2 measured divergences" in rendered
    assert "1 excerpt-side only" in rendered


def test_a_finding_renders_both_directions() -> None:
    """A reader of the worklist must see the count that used to be invisible."""
    rendered = Finding(
        "a:art-1", Verdict.EXCERPT_CARRIES_MORE, "", clauses_total=4, clauses_absent=0, clauses_extra=3
    ).render()
    assert "0/4 current clauses absent from the excerpt" in rendered
    assert "3 excerpt clauses absent from the current text" in rendered


def test_a_declared_vintage_is_still_a_vintage_when_it_carries_more() -> None:
    """The deliberate case must not be reclassified as the defect.

    A vintaged excerpt legitimately holds text current law dropped, which is
    precisely the shape ``excerpt_carries_more`` names. Reading the excerpt-side
    count before the vintage declaration would turn every deliberately
    historical document into the defect it was authored to be exempt from.
    """
    findings = screen(_REPO_ROOT).findings
    vintaged = [item for item in findings if item.verdict is Verdict.VINTAGED]
    assert vintaged
    assert all(_is_vintaged(item.detail) for item in vintaged)
    assert not any(_is_vintaged(item.detail) for item in findings if item.verdict is Verdict.EXCERPT_CARRIES_MORE)


def test_the_catalogue_citation_token_binds_the_unit_compared_against() -> None:
    """The check that is not self-confirming, and the one case it catches.

    The excerpt-heading check leads with the excerpt's own title as its first
    lookup key, so where that key resolves the check largely restates itself.
    This one compares the reached unit against a heading derived from the entry
    id, written by a different author in a different file.
    """
    assert confirms_citation("art-25", "Artículo 25. Especialidades del número.")
    assert not confirms_citation("art-25", "Artículo 26. Otra cosa.")
    assert not confirms_citation("preambulo", "Artículo 25.")


def test_a_written_ordinal_is_reported_unbound_and_never_misresolved() -> None:
    """Corpus-pinned control: a spelling variant is not a resolution defect.

    ``orden-hac-1504-2024:art-9`` resolves to a unit BOE titles "Artículo
    noveno" against a derived "Articulo 9". Promoting that to ``misresolved``
    would put a benign variant in the bucket reserved for a comparison made
    against the wrong article, and a reader who learns the bucket lies stops
    reading it.
    """
    finding = next(item for item in screen(_REPO_ROOT).findings if item.entry_id == "orden-hac-1504-2024:art-9")
    assert not finding.citation_confirmed
    assert finding.verdict is not Verdict.MISRESOLVED
    assert finding.clauses_total > 0


def test_only_the_shared_loader_walks_the_legal_catalogue() -> None:
    """The duplication the hoist removed must not grow back.

    Two screens each carried the same directory constant, the same
    byte-identical refusal and the same glob-to-tomllib walk, and the copies had
    already diverged in what they returned. Keyed on the directory path rather
    than on a function name, so a re-implementation under any name is caught.
    """
    audit_modules = scan_directory(_REPO_ROOT / "dev" / "audit", pattern="*.py")
    assert audit_modules
    walkers = [path.name for path in audit_modules if str(LEGAL_DIR.as_posix()) in path.read_text(encoding="utf-8")]
    assert walkers == ["legal_catalogue.py"]


def test_the_shared_loader_projects_required_text_without_a_second_walk() -> None:
    """The narrower consumer's view must come off the wider read.

    Proved over the real catalogue: every entry the full read returns is
    present in the projection, so the attribution screen cannot silently see a
    smaller population than the vintage screen does.
    """
    entries = load_legal_entries(_REPO_ROOT)
    projected = required_text_by_entry(entries)
    assert entries
    assert set(projected) == set(entries)
    declared = [entry_id for entry_id, body in entries.items() if isinstance(body.get("required_text"), list)]
    assert declared
    for entry_id in declared:
        phrases = entries[entry_id]["required_text"]
        assert isinstance(phrases, list)
        assert projected[entry_id] == tuple(str(phrase) for phrase in phrases)


def test_the_loader_refuses_a_missing_catalogue_rather_than_reading_nothing() -> None:
    """An empty read would print a clean worklist for every screen in the package."""
    with pytest.raises(SystemExit, match="legal catalogue is missing"):
        load_legal_entries(_REPO_ROOT / "does-not-exist")


def test_every_bundled_article_payload_states_one_redaction_in_force() -> None:
    """Every payload the screen reads must reduce to exactly one text in force.

    Read off the bundled corpus rather than a fixture: a payload that ties, or
    whose block id drifts from its filename, would otherwise be discovered as a
    silent ``oracle_indeterminate`` in a published split.
    """
    corpus = _REPO_ROOT / "src/cadrumo/_data/corpus/normatives/html"
    payloads = article_payloads(corpus)
    assert payloads
    for document_id, items in payloads.items():
        for item in items:
            markup = item.path.read_text(encoding="utf-8")
            in_force = assert_serves_the_article_in_force(markup, document_id=document_id, block=item.block)
            assert in_force.vigencia
            assert item.title
            assert article_redaction_markup(markup, in_force).strip()
