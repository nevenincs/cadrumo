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

from pathlib import Path

import pytest

from ..legal_excerpt_vintage_screen import (
    Finding,
    Verdict,
    candidate_keys,
    clause_chunks,
    norm_root,
    ordinal_spellings,
    screen,
    structural_key,
    summarise,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT = Path(__file__).resolve().parents[3]


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
    findings, population = screen(_REPO_ROOT)
    assert population > 0
    assert len(findings) == population
    assert "COUNTS DO NOT RECONCILE" not in summarise(findings, population)


def test_the_octiesdecies_control_reaches_its_own_anchor_and_matches() -> None:
    """Corpus-pinned control: the family the old instrument called superseded.

    ``ley-37-1992:art-163-octiesdecies`` was reported at 100 per cent clause
    absence and triaged as possible wholesale supersession. Hand-checked, the
    excerpt and the consolidated unit are verbatim identical over the opening
    operative sentence. A failure here means either the derivation regressed or
    the bundled article genuinely changed -- both worth stopping for.
    """
    findings, _ = screen(_REPO_ROOT)
    finding = next(item for item in findings if item.entry_id == "ley-37-1992:art-163-octiesdecies")
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
    findings, _ = screen(_REPO_ROOT)
    finding = next(item for item in findings if item.entry_id == "ley-35-2006:art-81")
    assert finding.verdict in {Verdict.DIVERGES_GATE_FIRES, Verdict.DIVERGES_GATE_GREEN}
    assert finding.clauses_absent > 0
    assert finding.identity_confirmed
