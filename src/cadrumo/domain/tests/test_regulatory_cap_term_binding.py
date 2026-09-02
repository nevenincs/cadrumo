"""Runtime proof that every enrolled regulatory cap can bind."""

from __future__ import annotations

import pytest

from .regulatory_cap_witnesses import REGULATORY_CAP_WITNESSES

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SiteKey = tuple[str, str]


@pytest.mark.parametrize(
    "site",
    sorted(REGULATORY_CAP_WITNESSES),
    ids=lambda site: f"{site[0]}::{site[1]}",
)
def test_each_regulatory_cap_is_a_term_that_binds(site: _SiteKey) -> None:
    """The enrolled witness proves its capped and uncapped terms diverge."""
    wide, narrow = REGULATORY_CAP_WITNESSES[site]()

    assert wide != narrow, (
        f"{site[0]}::{site[1]}: both witness terms yield {wide!r}; "
        "the witness's other term dominates or the cap is no longer applied"
    )
