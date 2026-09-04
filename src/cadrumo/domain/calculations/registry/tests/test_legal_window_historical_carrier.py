"""Teeth for the historical-carrier admission on the substantive-law window check.

A revision that carries HISTORICAL values legitimately cites the provisions that
governed those periods: modelo 303's 2022 revision can hold the pre-2015 prorrata
especial margin whose wording was repealed in 2014. The citation defends the
VALUE's window, which sits inside the provision's force, not the revision's,
which does not.

The exemption is deliberately hard to earn, and each test below pins one clause
of it. Containment rather than overlap, a closed value window, a law-fixing axis,
and carrier exclusivity are what stop this from becoming a way to launder a stale
citation, which is the defect the whole window check exists to catch.
"""

from __future__ import annotations

from datetime import date

import pytest

from .._snapshot_internals import _historical_carrier_admits
from ..schema_references import LegalReference

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_GOVERNS_FROM = date(1993, 1, 1)
_GOVERNS_TO = date(2014, 12, 31)


def _repealed_reference() -> LegalReference:
    """A substantive-law citation whose wording left force at the end of 2014."""
    return LegalReference.model_validate(
        {
            "id": "ley-37-1992:art-103-original",
            "evidence_tier": "legal_authority",
            "authority": "boe",
            "kind": "ley",
            "corpus_ref": "corpus/normatives/html/ley-37-1992.html#a103",
            "document_id": "BOE-A-1992-28740",
            "article": "103",
            "permalink": "https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740#a103",
            "published_at": date(1992, 12, 29),
            "required_text": ("regla de prorrata",),
            "effective_from": _GOVERNS_FROM,
            "effective_to": _GOVERNS_TO,
            "review_status": "agent_reviewed",
            "reviewed_at": date(2026, 9, 4),
            "reviewed_by": "fixture for the historical-carrier gate; not authored into the tree",
        },
    )


def test_a_value_window_inside_the_governed_span_is_admitted() -> None:
    """The case the gate exists to allow: historical value, historical provision."""
    assert _historical_carrier_admits(
        _repealed_reference(),
        ((_GOVERNS_FROM, _GOVERNS_TO, "filing_period"),),
    )


def test_a_narrower_contained_window_is_admitted() -> None:
    """Containment, not equality: a value need not span the whole provision."""
    assert _historical_carrier_admits(
        _repealed_reference(),
        ((date(2000, 1, 1), date(2010, 12, 31), "filing_period"),),
    )


def test_a_current_era_value_grounded_in_repealed_wording_is_refused() -> None:
    """TEETH: the stale-citation defect the whole window check exists to catch."""
    assert not _historical_carrier_admits(
        _repealed_reference(),
        ((date(2022, 1, 1), None, "filing_period"),),
    )


def test_an_open_ended_value_window_is_refused() -> None:
    """TEETH: the exemption cannot be bought by declaring an open window.

    An open window can never be contained in a closed governed span, so the
    cheapest route to a false admission is closed off by construction.
    """
    assert not _historical_carrier_admits(
        _repealed_reference(),
        ((_GOVERNS_FROM, None, "filing_period"),),
    )


def test_a_closed_but_uncontained_window_is_refused() -> None:
    """TEETH: overlap is not enough, and a post-repeal window earns nothing."""
    assert not _historical_carrier_admits(
        _repealed_reference(),
        ((date(2015, 1, 1), date(2021, 12, 31), "filing_period"),),
    )


def test_a_window_straddling_the_repeal_is_refused() -> None:
    """TEETH: partial containment is refused, so a value cannot reach past force."""
    assert not _historical_carrier_admits(
        _repealed_reference(),
        ((date(2010, 1, 1), date(2016, 12, 31), "filing_period"),),
    )


def test_a_submission_date_value_never_earns_the_exemption() -> None:
    """TEETH: when a declaration was filed fixes no applicable law.

    Contained on every other clause, and still refused, so the axis check cannot
    pass vacuously.
    """
    assert not _historical_carrier_admits(
        _repealed_reference(),
        ((_GOVERNS_FROM, _GOVERNS_TO, "submission_date"),),
    )


def test_a_reference_cited_outside_parameters_earns_nothing() -> None:
    """TEETH: carrier exclusivity, which the caller enforces by passing no spans.

    A reference some non-parameter record also cites has no parameter carrier to
    defend it, and must be checked against the revision window as before.
    """
    assert not _historical_carrier_admits(_repealed_reference(), ())
