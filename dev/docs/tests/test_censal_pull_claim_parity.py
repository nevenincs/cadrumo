"""The censal how-to's filled-field claim is bound to the adoptable tuple.

``docs/how-to/censo-update.md`` tells an operator which profile fields a censal
pull fills. That list is a restatement of
:data:`~cadrumo.application.user_profile.CENSAL_ADOPTABLE_PATHS`, and a
restatement drifts: the tuple changed twice during the censal campaign and the
page kept naming the fiscal ID long after it was removed from it.

The drift is operator-facing rather than cosmetic. The ownership guard
deliberately lets a read through when the profile carries no recorded fiscal
identity — the ordinary first-read case — so an operator with a blank
``identity.tax_id`` could follow the page, watch the pull succeed, and be left
with that field still blank and nothing having said so. The page had promised
the one field the pull cannot write.

So the gate asserts the page's claim EQUALS the tuple, in both directions: a
field added to the tuple and not documented fails, and a field documented but
not adoptable fails. It also pins the fiscal ID as the specific case that
started this, since that path is projected — the guard needs it as an input —
and adopting it is what must never be claimed.
"""

from __future__ import annotations

import re

import pytest

from cadrumo.application.user_profile.censo_sync import CENSAL_ADOPTABLE_PATHS

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_GUIDE = REPO_ROOT / "docs" / "how-to" / "censo-update.md"

#: How the page names each adoptable path in prose. Keyed by the schema path so
#: a tuple change surfaces here as a missing key rather than as silent drift.
_PROSE_FOR_PATH: dict[str, str] = {
    "contact.fiscal_address": "fiscal address",
    "contact.postcode": "postcode",
    "contact.fiscal_address_cadastral_reference": "cadastral reference",
}

#: The sentence that enumerates what a pull writes.
_CLAIM = re.compile(r"^The pull fills (?P<fields>[^.]+)\.", re.MULTILINE)


def _claimed_fields() -> list[str]:
    """Return the field phrases the guide says a pull fills.

    Normalised for the possessive the page addresses the operator with, so
    "your fiscal address" and "fiscal address" are the same claim. Only that
    one prefix is stripped: anything else the prose grows should surface as a
    mismatch to be looked at rather than be silently absorbed.
    """
    text = _GUIDE.read_text(encoding="utf-8")
    match = _CLAIM.search(text)
    assert match, f"{_GUIDE.name} no longer states what the pull fills; the claim gate cannot bind"
    raw = match.group("fields").replace(" and ", ", ")
    return [part.strip().removeprefix("your ").strip() for part in raw.split(",") if part.strip()]


def test_every_adoptable_path_is_named_in_the_guide() -> None:
    """A field the pull writes must be documented as filled."""
    claimed = _claimed_fields()
    for path in CENSAL_ADOPTABLE_PATHS:
        prose = _PROSE_FOR_PATH.get(path)
        assert prose is not None, (
            f"{path} was added to CENSAL_ADOPTABLE_PATHS with no documented prose name; "
            "add it here and to the guide's claim sentence"
        )
        assert prose in claimed, f"the guide does not tell an operator the pull fills {path!r} ({prose!r})"


def test_the_guide_claims_nothing_the_pull_does_not_fill() -> None:
    """A field documented as filled must actually be adoptable."""
    documented = set(_claimed_fields())
    adoptable = {_PROSE_FOR_PATH[path] for path in CENSAL_ADOPTABLE_PATHS if path in _PROSE_FOR_PATH}
    overclaimed = documented - adoptable
    assert not overclaimed, (
        f"the guide promises the pull fills {sorted(overclaimed)}, which is not in CENSAL_ADOPTABLE_PATHS"
    )


def test_the_fiscal_id_is_never_claimed_as_filled() -> None:
    """The case that started this: read for ownership, never written.

    Kept as its own assertion rather than folded into the equality checks
    because the path is genuinely PROJECTED — the ownership guard consumes it —
    so a future reader can mistake "the read carries it" for "the pull writes
    it", which is exactly the confusion the page shipped.
    """
    assert "identity.tax_id" not in CENSAL_ADOPTABLE_PATHS
    claimed = " ".join(_claimed_fields()).lower()
    assert "fiscal id" not in claimed, "the guide again promises the pull fills the fiscal ID; it never adopts it"


def test_the_guide_says_the_fiscal_id_is_read_to_confirm_ownership() -> None:
    """The refusal paragraph must follow from the claim, not contradict it.

    The page states elsewhere that a pull refuses a record whose fiscal ID is
    not the profile's. That is only coherent if the same page says the ID is
    READ rather than written — otherwise the two sentences assert that the pull
    both fills the field and compares against it.
    """
    text = _GUIDE.read_text(encoding="utf-8").lower()
    assert "does not fill your fiscal id" in text
    assert "confirm the record" in text
