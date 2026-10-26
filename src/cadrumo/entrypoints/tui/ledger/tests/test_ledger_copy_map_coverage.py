"""Every ledger state an operator can reach has a name, in every locale.

``review_status_label`` RAISES on an unmapped status, and both the entries
table and the review table label every row they draw. So a status the map does
not name is not a blank cell -- it takes the workspace down as soon as a row
carrying it is drawn.

That had already happened. ``LedgerReviewStatus`` has four members and the
hand-written map held three: ``EXCLUDED``, which
``ledger_transaction_review_status`` returns for a ``REVIEWED_EXCLUDED``
transaction, had no entry. Classifying one row as excluded and opening either
body raised ``unsupported Ledger review status``. Nothing referenced the enum,
so nothing could notice.

The map is derived from the enum now. These tests cover what derivation alone
cannot: that each derived key has authored copy in all four catalogues, since
``tr`` does not raise on a missing key -- it humanises the last dotted segment,
so an unnamed member would render English-looking text everywhere and nothing
would fail.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from .....application.ledger.workspace import (
    LedgerWorkspaceArea,
    LedgerWorkspaceAvailability,
    LedgerWorkspaceStatus,
)
from .....application.review.filter import LedgerReviewStatus
from ..controller import area_label, availability_label, review_status_label, status_label

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LOCALES = ("en", "es", "ca", "hu")
_LOCALES_ROOT = Path(__file__).resolve().parents[4] / "locales"

_PREFIX_BY_ENUM = {
    LedgerWorkspaceArea: "tui.ledger.area",
    LedgerWorkspaceAvailability: "tui.ledger.availability",
    LedgerReviewStatus: "tui.ledger.review_status",
    LedgerWorkspaceStatus: "tui.ledger.status",
}


def _resolve(catalogue: dict[str, object], dotted: str) -> str | None:
    """Walk the full dotted key; a member value may itself contain dots."""
    node: object = catalogue
    for segment in dotted.split("."):
        if not isinstance(node, dict) or segment not in node:
            return None
        node = node[segment]
    return node if isinstance(node, str) else None


def _catalogue(locale: str) -> dict[str, object]:
    loaded = yaml.safe_load((_LOCALES_ROOT / locale / "common.yml").read_text(encoding="utf-8"))
    return {str(key): value for key, value in loaded.items()}


@pytest.mark.parametrize("locale", _LOCALES)
def test_every_labelled_ledger_state_is_worded_in_this_locale(locale: str) -> None:
    """A member with no copy renders a humanised token, not a translation."""
    catalogue = _catalogue(locale)

    missing = [
        f"{prefix}.{member.value}"
        for enum_type, prefix in _PREFIX_BY_ENUM.items()
        for member in enum_type
        if _resolve(catalogue, f"{prefix}.{member.value}") is None
    ]

    assert not missing, f"{locale} has no wording for: {missing}"


def test_every_review_status_can_be_labelled_without_raising() -> None:
    """The live defect: an unnamed status crashed the table that drew it.

    Driven through the real label function for every enum member, so it fails
    if a member is ever added without copy -- which is exactly how ``EXCLUDED``
    came to be missing.
    """
    for status in LedgerReviewStatus:
        assert review_status_label(status.value).strip()


def test_a_status_outside_the_enum_is_still_refused() -> None:
    """Deriving the map must not turn the guard into an accept-anything.

    The refusal is what keeps a transport spelling from reaching the operator
    as though it were a state the product knows.
    """
    with pytest.raises(ValueError, match="unsupported Ledger review status"):
        review_status_label("not_a_status")


def test_every_area_availability_and_status_can_be_labelled() -> None:
    """The three sibling maps, exercised through their real label functions."""
    for area in LedgerWorkspaceArea:
        assert area_label(area).strip()
    for availability in LedgerWorkspaceAvailability:
        assert availability_label(availability).strip()
    for status in LedgerWorkspaceStatus:
        assert status_label(status).strip()


@pytest.mark.parametrize("locale", _LOCALES)
def test_no_ledger_label_is_blank(locale: str) -> None:
    """Blank copy is indistinguishable from an empty cell at the terminal."""
    catalogue = _catalogue(locale)

    blank = [
        f"{prefix}.{member.value}"
        for enum_type, prefix in _PREFIX_BY_ENUM.items()
        for member in enum_type
        if (_resolve(catalogue, f"{prefix}.{member.value}") or "").strip() == ""
    ]

    assert not blank
