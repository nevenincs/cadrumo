"""Real-behavior tests for the canonical :data:`~core.Hex64Str` primitive.

Every unrelated hex-64 identity concept the codebase carries (a registry
snapshot id, a ledger transaction id, a content digest, plus siblings owned
outside ``core`` such as a bucket event id and a durable auth-operation id)
is declared FROM this one primitive rather than each re-declaring its own
``StringConstraints(...)`` call, so the shape (lowercase, exactly 64 hex
characters) cannot drift between them. This suite covers the primitive itself
and EVERY ``core``-owned semantic alias, discovered by derivation rather than
by a hand-written list; the siblings owned by ``domain.buckets`` and
``application`` are pinned in their own test suites
(:mod:`~domain.buckets.tests.test_event_id`) to keep this ``core``-level
module importing only what ``core`` owns.

The alias set was hand-written and said "three". By the time anyone checked,
``core.identity`` exported eight -- the five relocated in during the identity
consolidation were never enrolled, so the suite whose stated purpose is
proving they stayed on the shared shape had never looked at them. A
hand-written register of a fact the package already states will drift, and it
drifts silently because nothing reads the register against its source. The set
is now derived by identity, which makes it complete by construction.

See Also:
    :mod:`~core.hex`
        Primitive definition under test.
    :mod:`~core.identity`
        Owner of the semantic aliases this suite derives its set from.
"""

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from ... import core as _core_package
from ...tests.fixtures.identity_holder import single_field_holder
from ..hex import Hex64Str
from .. import identity as _identity_package

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CANONICAL_DIGEST = hashlib.sha256(b"payload").hexdigest()

_INVALID_HEX64 = (
    pytest.param(_CANONICAL_DIGEST.upper(), id="uppercase"),
    pytest.param("a" * 63, id="too-short"),
    pytest.param("a" * 65, id="too-long"),
    pytest.param("g" * 64, id="non-hex"),
    pytest.param("", id="empty"),
)


def _hex64_aliases() -> dict[str, object]:
    """Every public alias bound to the canonical primitive, DERIVED not listed.

    This set was hand-written, and a hand-written set is a second register of a
    fact the package already states. It drifted exactly as such a register does:
    it named three aliases while ``core.identity`` exported eight, so the five
    relocated into this package during the identity consolidation were never
    proven to have stayed on the shared shape -- by the suite whose stated
    purpose is proving precisely that. The comment even instructed authors to
    add new concepts by hand, which is the maintenance burden that produced the
    gap.

    Deriving by identity (``value is Hex64Str``) makes the set complete BY
    CONSTRUCTION: a new alias is covered the moment it is declared, and one that
    stops being the primitive drops out and is caught by
    :func:`test_every_alias_is_defined_from_the_one_canonical_primitive`.
    """
    aliases: dict[str, object] = {"Hex64Str": Hex64Str}
    for package in (_core_package, _identity_package):
        for name in dir(package):
            if not name.startswith("_") and getattr(package, name, None) is Hex64Str:
                aliases[name] = Hex64Str
    return aliases


_ALIASES = _hex64_aliases()

#: The aliases this package is known to own. Not the authority on the set --
#: :func:`_hex64_aliases` is -- but a floor, so a derivation that silently
#: returns nothing cannot make every test below pass over an empty parametrize.
_KNOWN_ALIASES = frozenset(
    {
        "CalculationRevisionId",
        "ContentDigest",
        "FilingRecordId",
        "InvoiceId",
        "SnapshotId",
        "TransactionId",
        "VerificationReportId",
        "WorkUnitId",
    }
)


def test_the_alias_set_is_derived_and_not_empty() -> None:
    """The anti-vacuity guard on the derivation itself.

    Every other test here is parametrized over :data:`_ALIASES`. A derivation
    that returned only the primitive -- an import that moved, an introspection
    that stopped matching -- would leave those tests green over a set of one and
    prove nothing about any alias. This asserts the derivation actually reached
    the package before anything reads meaning into a pass.
    """
    assert set(_ALIASES) >= _KNOWN_ALIASES, (
        f"the derivation lost aliases this package is known to own: {sorted(_KNOWN_ALIASES - set(_ALIASES))}"
    )


@pytest.mark.parametrize("name", sorted(_ALIASES))
def test_alias_accepts_the_canonical_digest_shape(name: str) -> None:
    holder = single_field_holder("value", _ALIASES[name])
    built = holder.build(_CANONICAL_DIGEST)
    assert holder.value_of(built) == _CANONICAL_DIGEST


@pytest.mark.parametrize("name", sorted(_ALIASES))
@pytest.mark.parametrize("invalid", _INVALID_HEX64)
def test_alias_rejects_the_same_malformed_shapes(name: str, invalid: str) -> None:
    holder = single_field_holder("value", _ALIASES[name])
    with pytest.raises(ValidationError):
        holder.build(invalid)


def test_every_alias_is_defined_from_the_one_canonical_primitive() -> None:
    # "Defined from" means literal reuse of the same Annotated object, not a
    # second call to StringConstraints(...) that happens to match today and
    # can silently drift tomorrow.
    for name, alias in _ALIASES.items():
        if name == "Hex64Str":
            continue
        assert alias is Hex64Str, f"{name} must be Hex64Str itself, not a re-declared equivalent"
