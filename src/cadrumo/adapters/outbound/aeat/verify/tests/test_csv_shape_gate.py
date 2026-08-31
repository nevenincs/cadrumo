"""The public verifier refuses a malformed CSV before it asks AEAT.

``verify_csv`` used to accept any non-blank string, build a Sede URL from it,
and then treat any iframe echoing that same string as confirmation. A
one-character "CSV" therefore had a reachable path to a ``True`` verdict --
a claim that AEAT confirmed a document that cannot exist. The shape is checked
once, at the boundary, and again where the verdict is actually decided.
"""

from __future__ import annotations

import asyncio

import pytest

from ......core.aeat_csv import is_aeat_csv
from ......core.config import Settings
from ......domain.justificante import JustificanteVerificationError
from .. import _VERIFY_HOST, _response_confirms_valid_csv, verify_csv

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_VALID_CSV = "FIXTURECSV1234X7"
_SEDE_PATHS = Settings.external_constants().aeat.sede_paths
_COTEJO_PATH = _SEDE_PATHS.cotejo_query
_DOCUMENT_PATH = _SEDE_PATHS.cotejo_document


def _viewer_html(csv: str) -> str:
    return f'<html><body><iframe id="iframe-visualiza" src="{_DOCUMENT_PATH}?CSV={csv}"></iframe></body></html>'


@pytest.mark.parametrize("bad_csv", ["X", "", "   ", "short", "A" * 33, "BAD-CSV-12345678"])
def test_malformed_csv_is_refused_before_any_round_trip(bad_csv: str) -> None:
    """No browser session is built: the shape gate fires first."""
    with pytest.raises(JustificanteVerificationError):
        asyncio.run(verify_csv(bad_csv))


@pytest.mark.parametrize("bad_csv", ["X", "short", "A" * 33])
def test_a_matching_iframe_cannot_confirm_a_malformed_csv(bad_csv: str) -> None:
    """The exact audit probe: a page echoing a malformed value is not proof."""
    assert is_aeat_csv(bad_csv) is False

    confirmed = _response_confirms_valid_csv(
        _viewer_html(bad_csv),
        expected_csv=bad_csv,
        final_url=f"https://{_VERIFY_HOST}{_COTEJO_PATH}?CSV={bad_csv}",
    )

    assert confirmed is False


def test_a_well_shaped_csv_with_a_matching_iframe_still_confirms() -> None:
    """The gate must not break the case it exists to protect."""
    confirmed = _response_confirms_valid_csv(
        _viewer_html(_VALID_CSV),
        expected_csv=_VALID_CSV,
        final_url=f"https://{_VERIFY_HOST}{_COTEJO_PATH}?CSV={_VALID_CSV}",
    )

    assert confirmed is True


def test_a_well_shaped_csv_with_a_mismatched_iframe_does_not_confirm() -> None:
    confirmed = _response_confirms_valid_csv(
        _viewer_html("OTHERCSV98765432"),
        expected_csv=_VALID_CSV,
        final_url=f"https://{_VERIFY_HOST}{_COTEJO_PATH}?CSV={_VALID_CSV}",
    )

    assert confirmed is False
