"""A ``previous_filing`` binding's source revisions must span every year it can ask for.

Real gate, real registry, no mocks: every test drives
:func:`validate_previous_filing_source_year_coverage` over the ACTUAL bundled
corpus loaded through :func:`resources`. The clean-corpus test is the
allowlist's own honesty proof — if either genuine gap it documents (Modelo
130 needing Modelo 100 at 2018/2019; the three Modelo 720 self-carries
needing 2011) ever closes or widens, this file is what catches it, not a
human re-reading the allowlist.
"""

from __future__ import annotations

import pytest

from .. import _validate_previous_filing_year_coverage as _module
from .._validate_previous_filing_year_coverage import validate_previous_filing_source_year_coverage
from ..authority import bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _loaded_modelos():
    modelos = bundled_authority().modelos
    return modelos, {modelo.id: modelo for modelo in modelos}


def test_the_bundled_corpus_carries_no_uncovered_or_stale_gap() -> None:
    """Every real ``previous_filing`` source-year requirement is either satisfied or allowlisted.

    Structural years (before the registry's own floor, or beyond what the
    source itself has published) are excluded before this point is reached;
    what remains is either genuinely covered or named in the allowlist with
    its reason and discharge condition. Zero failures proves BOTH halves at
    once: no unlisted gap, and no allowlist entry that has gone stale.
    """
    modelos, modelos_by_id = _loaded_modelos()

    failures = validate_previous_filing_source_year_coverage(modelos, modelos_by_id)

    assert failures == []


def test_a_widened_gap_is_not_silently_absorbed_by_the_narrower_allowance() -> None:
    """The same START year with a LARGER end must not match the documented allowance.

    Positive control for the gate actually biting: a real, immutable Modelo
    100 registry input without its real 2020 revision makes the Modelo 130
    carry's missing range grow from 2018-2019 to 2018-2020. The allowance
    names 2018 THROUGH 2019 specifically, so the wider gap must surface as a
    new failure, and the narrower allowance must itself go stale — proving
    the match is exact rather than start-year-only, which would have silently
    absorbed a real regression.
    """
    modelos, modelos_by_id = _loaded_modelos()
    modelo_100 = modelos_by_id["100"]
    modelo_100_without_2020 = modelo_100.model_copy(
        update={
            "revisions": {
                revision_id: revision for revision_id, revision in modelo_100.revisions.items() if revision_id != "2020"
            },
        },
    )
    failures = validate_previous_filing_source_year_coverage(
        modelos,
        {**modelos_by_id, modelo_100.id: modelo_100_without_2020},
    )

    assert any("2018-2020" in failure and "100" in failure for failure in failures), failures
    assert any("stale previous-filing year-coverage allowance" in failure for failure in failures), failures


def test_a_new_mid_range_gap_with_no_prior_allowance_is_caught() -> None:
    """A hole opening in the MIDDLE of a previously-clean range must surface too.

    Distinct from the widening test above (which extends an EXISTING gap's
    edge): here Modelo 100's 2022 revision drops out while 2020, 2021 and
    2023-2025 stay, opening a brand-new single-year hole nothing in
    ``_ALLOWANCES`` was ever written for.
    """
    modelos, modelos_by_id = _loaded_modelos()
    modelo_100 = modelos_by_id["100"]
    modelo_100_without_2022 = modelo_100.model_copy(
        update={
            "revisions": {
                revision_id: revision for revision_id, revision in modelo_100.revisions.items() if revision_id != "2022"
            },
        },
    )
    failures = validate_previous_filing_source_year_coverage(
        modelos,
        {**modelos_by_id, modelo_100.id: modelo_100_without_2022},
    )

    assert any("2022" in failure and "lacks" in failure and "'100'" in failure for failure in failures), failures
    # The pre-existing 2018-2019 allowance is untouched by this mutation and
    # must still be consumed rather than reported stale.
    assert not any("stale" in failure for failure in failures), failures


class TestClippedRequiredInterval:
    """Pure unit coverage for the two structural exclusions."""

    def test_a_year_before_the_registry_floor_is_clipped_to_the_floor(self) -> None:
        clipped = _module._clipped_required_interval(
            required_start=1998,
            required_end=2005,
            source_upper_bound=2010,
        )
        assert clipped == (2000, 2005)

    def test_an_open_ended_requirement_is_clipped_to_the_sources_own_ceiling(self) -> None:
        clipped = _module._clipped_required_interval(
            required_start=2019,
            required_end=None,
            source_upper_bound=2025,
        )
        assert clipped == (2019, 2025)

    def test_a_requirement_entirely_beyond_the_source_ceiling_is_fully_structural(self) -> None:
        """Nothing left to check: the whole span is "not yet published", not a gap."""
        clipped = _module._clipped_required_interval(
            required_start=2026,
            required_end=2030,
            source_upper_bound=2025,
        )
        assert clipped is None

    def test_both_sides_open_ended_keeps_the_open_requirement_uncapped(self) -> None:
        """When the source itself is open-ended there is no finite ceiling to clip against."""
        clipped = _module._clipped_required_interval(
            required_start=2019,
            required_end=None,
            source_upper_bound=None,
        )
        assert clipped == (2019, None)


class TestMissingYears:
    """Pure unit coverage for the finite missing-year walk, over the REAL Modelo 100 revisions."""

    def test_a_finite_range_reports_every_uncovered_year(self) -> None:
        modelos, _ = _loaded_modelos()
        modelo_100 = next(modelo for modelo in modelos if str(modelo.id) == "100")
        # Modelo 100 models 2020-2025 as one revision per year; asking for
        # 2018-2022 must report exactly the two years no revision carries.
        revisions = tuple(modelo_100.revisions.values())

        missing = _module._missing_years(start=2018, end=2022, period_matching_revisions=revisions)

        assert missing == (2018, 2019)
