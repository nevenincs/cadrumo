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
