"""The NIF canary that fences the published key off from real tax data.

``UnsecuredMasterKeyProvider`` returns a PUBLISHED deterministic key and
provides zero confidentiality. It exists so testing and tutorial scenarios keep
the substrate's encryption pipeline intact without key management, and the only
thing standing between it and a real taxpayer's records is this canary: the
moment a bucket's profile carries a real NIF, NIE or CIF, activation must
refuse.

That fence had no test. ``looks_like_real_tax_id`` -- the predicate the whole
guarantee rests on -- had no coverage at all, and neither refusal function was
named by any test in the tree. The one file mentioning
``UnsecuredModeRefusedError`` covers the Google OAuth surface, not this.

The two directions are asserted together on purpose. A guard that refuses
everything would pass a refusal-only suite while making the unsecured mode
useless, and a guard that admits everything is the breach itself; only the pair
shows the canary discriminating. The padding case is here because a canary keyed
on an exact string is bypassed by a space, and the malformed-check-letter case
because that is where this predicate deliberately admits -- pinned so a later
loosening of tax-id parsing cannot silently narrow the fence without reddening
something.

Real classifier, real provider objects, real refusal type. Nothing is mocked.
"""

from __future__ import annotations

import pytest

from ......tests.master_key import EphemeralMasterKeyProvider
from ...errors import UnsecuredModeRefusedError
from .._master_key import UnsecuredMasterKeyProvider, refuse_unsecured_with_real_nif
from .._master_key_tax_id import looks_like_real_tax_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

#: Tax ids that identify a real taxpayer, one per accepted Spanish form. Each is
#: check-digit valid, which is what makes it reach the synthetic-set test at all.
_REAL_TAX_IDS = ("12345678Z", "X1234567L", "B12345674")

#: The placeholders the refusal message itself offers as the way to keep using
#: unsecured mode. They are pinned here rather than imported from the private
#: frozenset because the property under test is that THESE exact strings are the
#: sanctioned escape: reading the set the code reads would agree with any edit to
#: it, including one that quietly admitted a real id.
_SYNTHETIC_TAX_IDS = ("00000000T", "X0000000T", "Z0000000T", "Y0000000Z", "B00000000")


@pytest.mark.parametrize("tax_id", _REAL_TAX_IDS)
def test_a_real_tax_id_is_classified_real(tax_id: str) -> None:
    """NIF, NIE and CIF each reach the canary."""
    assert looks_like_real_tax_id(tax_id) is True


@pytest.mark.parametrize("tax_id", _SYNTHETIC_TAX_IDS)
def test_every_sanctioned_placeholder_is_classified_synthetic(tax_id: str) -> None:
    """The documented escape hatch must actually work.

    The refusal message tells the operator to use a synthetic placeholder and
    names one. If any of these classified real, unsecured mode would refuse the
    profiles it exists to serve and the advice would be wrong.
    """
    assert looks_like_real_tax_id(tax_id) is False


@pytest.mark.parametrize("padded", ["   12345678Z", "12345678Z   ", "  12345678Z  "])
def test_whitespace_cannot_smuggle_a_real_tax_id_past_the_canary(padded: str) -> None:
    """DISCRIMINATING: the classifier canonicalises before deciding.

    A canary comparing raw strings is defeated by a leading space, and the
    profile value arrives from operator input where padding is ordinary.
    """
    assert looks_like_real_tax_id(padded) is True


@pytest.mark.parametrize("value", ["", "   ", "not-a-nif", "1234567", "12345678A"])
def test_an_unparseable_tax_id_is_not_treated_as_real(value: str) -> None:
    """Where this predicate deliberately admits, pinned rather than assumed.

    ``12345678A`` is the case worth naming: the digits are a real NIF's but the
    check letter is wrong, so it identifies nobody and is admitted. That is
    defensible -- an id that fails its own check digit is not a taxpayer
    identity -- but it is a decision, not an accident, and it lives one
    refactor away from mattering. If tax-id parsing is ever loosened to accept
    a bad check letter, the fence silently widens to admit real people's
    numbers; this pins the boundary so that change reds here first.
    """
    assert looks_like_real_tax_id(value) is False


@pytest.mark.parametrize("tax_id", _REAL_TAX_IDS)
def test_the_unsecured_provider_refuses_a_real_tax_id(tax_id: str) -> None:
    """The breach this whole apparatus exists to prevent."""
    with pytest.raises(UnsecuredModeRefusedError):
        refuse_unsecured_with_real_nif(tax_id, provider=UnsecuredMasterKeyProvider())


@pytest.mark.parametrize("tax_id", _SYNTHETIC_TAX_IDS)
def test_the_unsecured_provider_admits_a_synthetic_tax_id(tax_id: str) -> None:
    """ANTI-TAUTOLOGY: the guard is not simply refusing everything.

    Without this, a canary hard-wired to raise would satisfy every refusal
    assertion above while making the unsecured backend unusable -- and the
    suite would read as proof of a working fence.
    """
    refuse_unsecured_with_real_nif(tax_id, provider=UnsecuredMasterKeyProvider())


@pytest.mark.parametrize("tax_id", _REAL_TAX_IDS)
def test_a_secured_provider_is_not_fenced_by_the_canary(tax_id: str) -> None:
    """The canary is scoped to the published key, not to real tax ids.

    A real NIF under a provider holding real key material is the ordinary
    production case. Refusing here would fence off exactly the profiles the
    application exists for, so the no-op branch is as load-bearing as the
    refusal and is asserted against a real provider object rather than a stand-in.
    """
    refuse_unsecured_with_real_nif(tax_id, provider=EphemeralMasterKeyProvider())
