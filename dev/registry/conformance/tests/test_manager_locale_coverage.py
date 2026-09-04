"""Tests for the conformance manager's locale-coverage arithmetic.

The manager renders facts computed elsewhere, with one exception: locale
coverage is the axis it adds itself, because the shipped composer does not reach
into the locale catalogue. That axis is 1,468 lines away from any test -
`dev.quality.module_test_reach` reports the module as reached by none - and it
carries an asymmetry its own docstring warns about.

``labels_required_per_locale`` counts the required leaves for ONE locale, since
every audited locale shares the key set. ``labels_translated`` is summed ACROSS
locales. Read as a fraction they exceed one, and the two derived properties are
the only place the difference is reconciled. Nothing asserted it.
"""

from __future__ import annotations

import pytest

from ..manager import RevisionLocaleCoverage

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _coverage(**overrides: object) -> RevisionLocaleCoverage:
    fields: dict[str, object] = {
        "audited_locales": ("es", "en", "ca", "hu"),
        "labels_required_per_locale": 100,
        "labels_translated": 400,
        "complete_locales": 4,
        "stale_keys": 0,
    }
    fields.update(overrides)
    return RevisionLocaleCoverage(**fields)  # type: ignore[arg-type]


def test_the_required_total_is_multiplied_by_the_audited_locales() -> None:
    """One locale's key set, times the locales measured.

    The stored field is deliberately per-locale because every audited locale
    shares the same keys, so the multiplication has to happen somewhere and this
    is the only place it does.
    """
    coverage = _coverage()

    assert coverage.labels_required_per_locale == 100
    assert coverage.labels_required_across_locales == 400


def test_full_coverage_leaves_nothing_untranslated() -> None:
    """Four locales fully authored is 400 of 400, not 400 of 100."""
    assert _coverage().labels_untranslated == 0


def test_a_partly_translated_revision_reports_the_shortfall_across_locales() -> None:
    """The gap is counted in leaves, summed the same way the translations are."""
    coverage = _coverage(labels_translated=250, complete_locales=2)

    assert coverage.labels_untranslated == 150


def test_the_two_figures_are_not_a_fraction_and_the_docstring_says_so() -> None:
    """Translated across locales exceeds required per locale, legitimately.

    This is the trap the field names exist to avoid: 400 translated against 100
    required is complete coverage of four locales, not a four-hundred per cent
    one. A reader dividing the stored fields gets four; dividing through the
    derived property gets one.
    """
    coverage = _coverage()

    assert coverage.labels_translated > coverage.labels_required_per_locale
    assert coverage.labels_translated == coverage.labels_required_across_locales


def test_a_single_locale_makes_the_two_totals_agree() -> None:
    """The degenerate case where the asymmetry vanishes, and must still hold."""
    coverage = _coverage(audited_locales=("es",), labels_translated=100, complete_locales=1)

    assert coverage.labels_required_across_locales == 100
    assert coverage.labels_untranslated == 0


def test_no_audited_locale_requires_nothing_rather_than_dividing_by_zero() -> None:
    """An empty audit is a real state and must not be read as full coverage.

    Required across locales is zero because nothing was measured, which is the
    absence this campaign keeps separating from a proven zero - the caller sees
    an empty ``audited_locales`` and knows which it is.
    """
    coverage = _coverage(audited_locales=(), labels_translated=0, complete_locales=0)

    assert coverage.labels_required_across_locales == 0
    assert coverage.labels_untranslated == 0
    assert coverage.audited_locales == ()


def test_the_counts_refuse_to_be_negative() -> None:
    """Every count is a population, and a negative population is a bug upstream."""
    for field in ("labels_required_per_locale", "labels_translated", "complete_locales", "stale_keys"):
        with pytest.raises(ValueError):
            _coverage(**{field: -1})


def test_stale_keys_are_carried_apart_from_the_translation_totals() -> None:
    """A leaf no registry key claims is not a translation, missing or present.

    Folding stale keys into either total would make a catalogue look better or
    worse for holding text nothing asks for.
    """
    coverage = _coverage(stale_keys=7)

    assert coverage.stale_keys == 7
    assert coverage.labels_untranslated == 0
