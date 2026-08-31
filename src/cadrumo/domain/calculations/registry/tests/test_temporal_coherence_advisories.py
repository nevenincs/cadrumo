"""Each temporal-coherence advisory is proven to fire on a deliberately broken revision.

The committed corpus satisfies all three conditions, so a test that only asserted
"the corpus is clean" would pass identically if the checks did nothing. Every
condition therefore gets a fixture built to violate exactly it, and the clean
corpus is asserted alongside so the checks are shown not to fire on correct data.

The parallel-regime case gets its own test because it is the false positive this
module was designed against: Modelo 369's OSS schemes share a start date and
partition the period axis, and a supersession check reading date order alone
would report them forever.
"""

from __future__ import annotations

from datetime import date

import pytest

from .....core.tax_domain import TaxDomain
from .....core.resources import bundled_path
from ..loader import load_registry_tree
from ..schema import ModeloDefinition, ModeloRevision
from ..schema_references import PeriodSelector
from ..validate_temporal_coherence import temporal_coherence_advisories

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _revision(
    revision_id: str,
    *,
    valid_from: date,
    valid_to: date | None,
    selector: PeriodSelector,
) -> ModeloRevision:
    return ModeloRevision.model_validate(
        {
            "id": revision_id,
            "localization_key": f"test.schema.revision.{revision_id}.label",
            "valid_from": valid_from,
            "valid_to": valid_to,
            "period_selector": selector,
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-modelo-303-instructions",),
        },
    )


def _modelo(revisions: dict[str, ModeloRevision]) -> ModeloDefinition:
    return ModeloDefinition.model_validate(
        {
            "id": "303",
            "title_localization_key": "test.schema.modelo.303.title",
            "official_name_localization_key": "test.schema.modelo.303.official_name",
            "tax_domain": TaxDomain.IVA,
            "cadence": "quarterly",
            "jurisdiction": "ES-AEAT",
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-modelo-303-instructions",),
            "revisions": revisions,
        },
    )


def test_the_committed_corpus_declares_coherent_temporal_windows() -> None:
    """The shipped registry trips none of the three conditions."""
    modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))

    assert temporal_coherence_advisories(modelos) == ()


def test_an_overlapping_successor_over_an_open_predecessor_is_reported() -> None:
    """A superseded revision that declares no terminus is advised."""
    quarterly = PeriodSelector(year_from=2024, periods=("1T", "2T", "3T", "4T"))
    modelo = _modelo(
        {
            "open": _revision("open", valid_from=date(2024, 1, 1), valid_to=None, selector=quarterly),
            "successor": _revision(
                "successor",
                valid_from=date(2025, 1, 1),
                valid_to=date(2025, 12, 31),
                selector=PeriodSelector(year_from=2025, periods=("1T", "2T", "3T", "4T")),
            ),
        },
    )

    advisories = temporal_coherence_advisories([modelo])

    assert any("declares no validity terminus" in line and "revision open" in line for line in advisories), advisories


def test_parallel_regimes_sharing_a_start_date_are_not_reported() -> None:
    """Anti-false-positive: regimes that partition the period axis never supersede each other.

    This is the Modelo 369 shape -- OSS esquema exterior and unión, same start
    date, disjoint periods, both legitimately open-ended.
    """
    modelo = _modelo(
        {
            "esquema-union": _revision(
                "esquema-union",
                valid_from=date(2021, 7, 1),
                valid_to=None,
                selector=PeriodSelector(year_from=2021, periods=("1T", "2T", "3T", "4T")),
            ),
            "esquema-exterior": _revision(
                "esquema-exterior",
                valid_from=date(2021, 7, 1),
                valid_to=None,
                selector=PeriodSelector(year_from=2021, periods=("EXT-1T", "EXT-2T")),
            ),
        },
    )

    assert temporal_coherence_advisories([modelo]) == ()


def test_a_later_starting_sibling_on_disjoint_periods_is_not_reported() -> None:
    """Starting later is not supersession when the two never compete for a period."""
    modelo = _modelo(
        {
            "quarterly": _revision(
                "quarterly",
                valid_from=date(2024, 1, 1),
                valid_to=None,
                selector=PeriodSelector(year_from=2024, periods=("1T", "2T")),
            ),
            "monthly": _revision(
                "monthly",
                valid_from=date(2025, 1, 1),
                valid_to=None,
                selector=PeriodSelector(year_from=2025, periods=("01", "02")),
            ),
        },
    )

    assert temporal_coherence_advisories([modelo]) == ()


def test_a_bounded_selector_with_an_open_validity_end_is_reported() -> None:
    """A selector bounded by year_to while validity stays open is advised."""
    modelo = _modelo(
        {
            "bounded": _revision(
                "bounded",
                valid_from=date(2024, 1, 1),
                valid_to=None,
                selector=PeriodSelector(year_from=2024, year_to=2024, periods=("1T",)),
            ),
        },
    )

    advisories = temporal_coherence_advisories([modelo])

    assert any("selector is bounded at year 2024" in line for line in advisories), advisories


def test_a_selector_start_disagreeing_with_declared_validity_is_reported() -> None:
    """A selector first year that is not the validity start year is advised."""
    modelo = _modelo(
        {
            "mismatch": _revision(
                "mismatch",
                valid_from=date(2024, 1, 1),
                valid_to=date(2024, 12, 31),
                selector=PeriodSelector(year_from=2023, periods=("1T",)),
            ),
        },
    )

    advisories = temporal_coherence_advisories([modelo])

    assert any("selector starts at year 2023" in line for line in advisories), advisories


def test_the_checks_never_raise_on_a_broken_revision() -> None:
    """Advisory means advisory: an incoherent revision yields findings, not an exception."""
    modelo = _modelo(
        {
            "broken": _revision(
                "broken",
                valid_from=date(2024, 1, 1),
                valid_to=None,
                selector=PeriodSelector(year_from=2019, year_to=2019, periods=("1T",)),
            ),
        },
    )

    advisories = temporal_coherence_advisories([modelo])

    assert len(advisories) >= 2, "a revision breaking two conditions should report both"
