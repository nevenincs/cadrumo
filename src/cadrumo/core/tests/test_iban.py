"""``iban_mod_97`` must refuse a string it cannot validate, not silently pass it.

The callee previously trusted its caller to have already matched
:data:`IBAN_SHAPE_RE`. Every current caller does -- but the guard lived at
every call site and nowhere in the callee, the same convention-enforced-
invariant shape this project keeps finding and fixing elsewhere: a fifth
caller that forgets its own shape gate would get a mod-97 residue computed
over a string too short to be a real IBAN, and roughly one in ninety-seven
malformed strings would land on a false ``1`` -- a silent "valid" verdict
for something that cannot be an IBAN at all.

``iban_mod_97("ES82")`` is the reproduction: four characters, no BBAN, and
the arithmetic tolerates it anyway. Nothing before this fix demanded a real
IBAN shape inside the function itself.
"""

from __future__ import annotations

import pytest

from ..iban import IBAN_SHAPE_RE, iban_mod_97, normalise_iban

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Real, checksum-valid accounts, canonical form. Shared with
#: ``test_redaction_printed_iban.py``'s corpus so both proofs are grounded in
#: the same genuine IBANs rather than a hand-typed literal that merely looks
#: plausible.
_GENUINE_IBANS = [
    "ES9121000418450200051332",
    "DE89370400440532013000",
    "GB29NWBK60161331926819",
    "FR1420041010050500013M02606",
]

#: Strings a caller might hand to ``iban_mod_97`` if it forgot its own shape
#: gate. None of these can possibly be a real IBAN -- too short, wrong body
#: alphabet, or no BBAN at all -- so every one must be refused.
_MALFORMED_INPUTS = [
    "ES82",
    "",
    "ES",
    "1234567890123456",
    "es9121000418450200051332",
    "ES91 2100 0418 4502 0005 1332",
]


def test_the_reproduction_previously_returned_a_false_valid_residue() -> None:
    """Anti-tautology: prove the exact defect the fix closes.

    Before folding the shape check into the callee, ``iban_mod_97("ES82")``
    computed a residue of 1 -- a false "valid" -- over a four-character
    string with no BBAN at all. This is the literal reproduction from the
    finding, proving the bug was real before asserting it is closed below.
    """
    rearranged = "ES82"[4:] + "ES82"[:4]
    numeric = "".join(ch if ch.isdigit() else str(ord(ch) - ord("A") + 10) for ch in rearranged)
    assert int(numeric) % 97 == 1, (
        "the raw mod-97 arithmetic (bypassing iban_mod_97's shape gate) must still "
        "yield the false-valid residue this fix closes -- otherwise the reproduction "
        "no longer demonstrates the defect"
    )


@pytest.mark.parametrize("malformed", _MALFORMED_INPUTS)
def test_iban_mod_97_refuses_input_it_cannot_validate(malformed: str) -> None:
    """The fixed behaviour: the callee itself refuses a non-IBAN-shaped string."""
    with pytest.raises(ValueError, match="ISO 13616"):
        iban_mod_97(malformed)


@pytest.mark.parametrize("genuine", _GENUINE_IBANS)
def test_iban_mod_97_still_accepts_every_genuine_iban(genuine: str) -> None:
    """No regression: real IBANs, canonical form, still check out."""
    assert IBAN_SHAPE_RE.match(genuine), f"{genuine!r} is not shaped like an IBAN"
    assert iban_mod_97(genuine) == 1


def test_a_caller_that_omits_its_own_shape_gate_is_now_refused_not_silently_accepted() -> None:
    """The scenario the fix exists for: a hypothetical fifth caller.

    Simulates a caller that normalises the printed form but -- unlike every
    real caller today -- never checks :data:`IBAN_SHAPE_RE` before asking for
    the residue. Before the fix this returned ``1`` (accepted). After the
    fix it must raise, because the callee itself is the one place the
    invariant cannot be forgotten.
    """

    def _caller_without_its_own_shape_gate(printed: str) -> int:
        canonical = normalise_iban(printed)
        # Deliberately no ``IBAN_SHAPE_RE.match(canonical)`` check here --
        # this is exactly the omission the fix must survive.
        return iban_mod_97(canonical)

    with pytest.raises(ValueError, match="ISO 13616"):
        _caller_without_its_own_shape_gate("es82")

    # And the same gate-omitting caller still accepts a genuine IBAN, so the
    # fix closes the hole without breaking the real path.
    assert _caller_without_its_own_shape_gate("ES91 2100 0418 4502 0005 1332") == 1
