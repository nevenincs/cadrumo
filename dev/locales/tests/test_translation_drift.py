"""Real-behaviour tests for the translation-drift screen.

The screen's judgement is a comparison between two catalogues, and its risk is
answering a question it could not ask: a casilla the two catalogues do not label
under the same two revisions has no comparable pair, and a first version of this
measurement counted those as tracking a source change. Each condition is
exercised from input written here so none of them rests on the corpus happening
to contain it.
"""

from __future__ import annotations

import pytest

from ..translation_drift import KINDS, SOURCE_LOCALE, drift_findings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _catalogue(**revisions: str) -> dict[str, dict[str, dict[str, str]]]:
    """One modelo, one casilla, labelled under the revisions given."""
    return {"100": {"0001": dict(revisions)}}


def test_a_translation_varying_over_a_constant_source_is_drift() -> None:
    """Nothing in the official text justifies two renderings of one string."""
    findings = drift_findings(
        _catalogue(r2024="Ownership (%)", r2025="Ownership percentage"),
        _catalogue(r2024="Porcentaje", r2025="Porcentaje"),
        locale="en",
    )
    assert len(findings) == 1
    assert findings[0].kind == "translation_drifts_where_source_is_constant"
    assert findings[0].renderings == ("Ownership (%)", "Ownership percentage")
    assert findings[0].shared_revisions == 2


def test_a_translation_varying_with_its_source_is_doing_its_job() -> None:
    """Reported rather than filtered, because it is the larger population."""
    findings = drift_findings(
        _catalogue(r2024="Ownership (%)", r2025="Ownership share"),
        _catalogue(r2024="Porcentaje", r2025="Cuota"),
        locale="en",
    )
    assert [item.kind for item in findings] == ["translation_tracks_source_change"]


def test_a_source_change_the_translation_missed_is_reported() -> None:
    """The sharper defect, and invisible to a screen watching only translations.

    A filer reads text that no longer matches the official wording, and the
    translation itself gives no sign: it is constant, which is what a correct
    translation of an unchanged string also looks like.
    """
    findings = drift_findings(
        _catalogue(r2024="Ownership (%)", r2025="Ownership (%)"),
        _catalogue(r2024="Porcentaje", r2025="Cuota"),
        locale="en",
    )
    assert [item.kind for item in findings] == ["translation_missed_source_change"]


def test_a_casilla_both_catalogues_agree_on_is_not_a_finding() -> None:
    """Silence over the agreeing majority, or the report is the catalogue."""
    findings = drift_findings(
        _catalogue(r2024="Ownership (%)", r2025="Ownership (%)"),
        _catalogue(r2024="Porcentaje", r2025="Porcentaje"),
        locale="en",
    )
    assert findings == ()


def test_a_casilla_with_no_comparable_pair_is_reported_as_such() -> None:
    """A question that could not be asked is not an answer.

    The locale labels the casilla under two revisions, the source under one of
    them, so there is no pair to compare. Counting it as tracking a change - the
    first version's behaviour - credits the translation with following something
    nobody looked at.
    """
    findings = drift_findings(
        _catalogue(r2024="Ownership (%)", r2025="Ownership percentage"),
        _catalogue(r2024="Porcentaje"),
        locale="en",
    )
    assert [item.kind for item in findings] == ["source_coverage_insufficient"]
    assert findings[0].shared_revisions == 1


def test_a_single_revision_casilla_is_not_reported_at_all() -> None:
    """Nothing varies, so there is no disagreement to classify."""
    findings = drift_findings(_catalogue(r2024="Ownership (%)"), _catalogue(r2024="Porcentaje"), locale="en")
    assert findings == ()


def test_every_declared_condition_is_reachable() -> None:
    """A condition with no proof stops being reported without anyone noticing."""
    reached = set()
    for labels, source in (
        (_catalogue(a="x", b="y"), _catalogue(a="s", b="s")),
        (_catalogue(a="x", b="x"), _catalogue(a="s", b="t")),
        (_catalogue(a="x", b="y"), _catalogue(a="s", b="t")),
        (_catalogue(a="x", b="y"), _catalogue(a="s")),
    ):
        reached.update(item.kind for item in drift_findings(labels, source, locale="en"))
    assert reached == set(KINDS)


def test_the_live_screen_finds_every_condition_and_names_the_source_locale() -> None:
    """The corpus carries all four, so no condition rests on constructed input alone."""
    from ..translation_drift import screen_corpus

    findings = screen_corpus()
    assert findings, "no casilla varies anywhere, so this proves nothing"
    assert SOURCE_LOCALE not in {item.locale for item in findings}
    assert {item.kind for item in findings} == set(KINDS)
    drifting = [item for item in findings if item.kind == "translation_drifts_where_source_is_constant"]
    assert len(drifting) > 100, f"only {len(drifting)} drifting casillas; the screen is near-vacuous"


def test_a_difference_surviving_only_a_capital_is_mechanical() -> None:
    """Case, accent and punctuation are folded away before wording is compared."""
    from ..translation_drift import difference_kind

    assert difference_kind(("Contribuent titular", "contribuent titular")) == "identical_after_folding"
    assert difference_kind(("Situacio", "Situació")) == "identical_after_folding"
    assert difference_kind(("Ownership (%)", "Ownership %")) == "identical_after_folding"


def test_whitespace_is_checked_before_wording() -> None:
    """Two renderings differing by a doubled space are not a wording difference.

    They fold to different strings only by that space, so a wording comparison
    reached first would send a translator to look at nothing.
    """
    from ..translation_drift import difference_kind

    assert difference_kind(("per obres de conservacio", "per obres  de conservacio")) == "whitespace_only"


def test_reordered_words_are_shared_wording_and_new_words_are_not() -> None:
    """The split that decides whether a human has to read the source."""
    from ..translation_drift import difference_kind

    assert difference_kind(("Clau de situacio", "Situacio clau")) == "shared_wording"
    assert difference_kind(("Accrual tax year", "Accrual year")) == "shared_wording"
    assert difference_kind(("CNAE code of the main activity", "NACE identifier for principal trade")) == (
        "distinct_wording"
    )


def test_a_single_rendering_has_no_difference_to_describe() -> None:
    """Reporting one under any other kind counts a row that has no repair."""
    from ..translation_drift import difference_kind

    assert difference_kind(("Only one",)) == "not_applicable"
    assert difference_kind(()) == "not_applicable"


def test_the_threshold_is_a_declared_judgement_not_a_buried_one() -> None:
    """A reader who disagrees can move it and re-run rather than re-derive it."""
    from ..translation_drift import SHARED_WORDING_RATIO

    assert 0.0 < SHARED_WORDING_RATIO < 1.0


def test_every_difference_kind_is_reachable_and_the_live_corpus_carries_four() -> None:
    """A kind with no proof stops being assigned without anyone noticing.

    ``not_applicable`` is proven from constructed input alone: a drifting row
    always has at least two renderings, so the live corpus cannot produce it,
    which is exactly why it needs one.
    """
    from ..translation_drift import DIFFERENCE_KINDS, difference_kind, screen_corpus

    constructed = {
        difference_kind(pair)
        for pair in (
            ("a", "A"),
            ("a b", "a  b"),
            ("one two three", "three two one four"),
            ("wholly different", "nothing alike here"),
            ("single",),
        )
    }
    assert constructed == set(DIFFERENCE_KINDS)

    drifting = [item for item in screen_corpus() if item.kind == "translation_drifts_where_source_is_constant"]
    assert drifting, "no drifting casilla, so this proves nothing"
    assert "not_applicable" not in {item.difference for item in drifting}
    assert {item.difference for item in drifting} <= set(DIFFERENCE_KINDS)
