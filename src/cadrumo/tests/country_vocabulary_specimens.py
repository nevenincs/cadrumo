"""Specimens for the country axis, derived from the vocabulary rather than pinned.

Several behaviour classes on the country axis need an example of "a code this
system cannot place": the catalogue-gap advisory, the relief guard that must not
refuse a real export over a row we have not written, the degradation path that
keeps an unplaceable country distinguishable from an unstated one. Every one of
those is a property about the BOUNDARY, and every one was written by pinning a
country that happened to sit outside it.

**Pinning couples the test to a decision that was always going to move.** The
property is "a country we cannot place"; the country is an accident of when the
test was written. When the vocabulary widened by one argued tier, fifteen tests
across three lanes reddened -- not because any behaviour changed, but because
their specimen had been admitted. Worse than the count: one file's rationale
prose was written around that specimen being absent, so repointing its constant
would have left the explanation contradicting the data.

So the specimen is derived here instead, and a test using it follows the boundary
rather than pinning it. Widening the vocabulary becomes a pure data change.

**The derivation is deterministic**, because a specimen that varied between runs
would make a failure unreproducible and turn a red into a lottery. It sorts and
takes the first, so the same tree always yields the same specimen and a diff that
changes it says which boundary moved.

**Both spellings are derived independently, and they need not name one country.**
Deriving "the alpha-3 of the country this alpha-2 names" would need the alpha-2
to alpha-3 correspondence, which nothing in this repository provides -- it is the
standing residual both country gates state. The properties these specimens serve
are about the SPELLING axis rather than about a particular country, so
independence costs nothing: a test asking whether an unplaceable alpha-3 reaches
the same advisory as an unplaceable alpha-2 is answered by any two such codes.

See Also:
    :func:`~domain.iva.stated_country_code_status`
        The authority on whether a code is catalogued, which these are checked
        against rather than second-guessing.
"""

from __future__ import annotations

import json
import re
import tomllib
from functools import lru_cache
from pathlib import Path

from pydantic import TypeAdapter

from ..core.resources.bundled_data import bundled_path

__all__ = [
    "an_uncatalogued_alpha2",
    "an_uncatalogued_alpha3",
    "uncatalogued_alpha2_codes",
    "uncatalogued_alpha3_codes",
]

_SII_SCHEMA = ("corpus", "aeat_official", "einvoice_record_schemas", "sii", "SuministroInformacion.xsd")
_FACTURAE_CODES = ("corpus", "facturae", "facturae-3-2-2-country-codes.json")
_VOCABULARY = ("registry", "aeat", "iva", "country_names.toml")

#: Codes ISO reserves for private use. Excluded from the derivation because they
#: denote no country by construction, so the axis reports them as UNASSIGNED
#: rather than as a catalogue gap -- a different property with a different
#: advisory, and a specimen drawn from here would silently test the wrong one.
_USER_ASSIGNED = frozenset(
    {"AA", "ZZ"}
    | {f"Q{letter}" for letter in "MNOPQRSTUVWXYZ"}
    | {f"X{letter}" for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"},
)
_COUNTRY_ROWS = TypeAdapter(list[dict[str, object]])
_STRING_LIST = TypeAdapter(list[str])


@lru_cache(maxsize=1)
def _vocabulary() -> tuple[frozenset[str], frozenset[str]]:
    raw = tomllib.loads(Path(bundled_path(*_VOCABULARY)).read_text(encoding="utf-8"))
    payload = _COUNTRY_ROWS.validate_python(raw["country"])
    codes: set[str] = set()
    alpha3_codes: set[str] = set()
    for row in payload:
        code = row.get("code")
        alpha3 = row.get("alpha3")
        assert isinstance(code, str)
        assert isinstance(alpha3, str)
        codes.add(code)
        alpha3_codes.add(alpha3)
    return frozenset(codes), frozenset(alpha3_codes)


@lru_cache(maxsize=1)
def uncatalogued_alpha2_codes() -> tuple[str, ...]:
    """Return every alpha-2 code AEAT recognises that the vocabulary does not carry.

    Drawn from AEAT's own SII ``CountryType2`` enumeration rather than from a
    general register, so a specimen is a code the tax authority itself accepts on
    a submitted libro de registro -- which is what makes it a plausible catalogue
    gap rather than a string nobody would print.
    """
    schema = Path(bundled_path(*_SII_SCHEMA)).read_text(encoding="utf-8", errors="replace")
    block = re.search(r'<simpleType name="CountryType2">(.*?)</simpleType>', schema, re.S)
    assert block is not None, "AEAT's SII schema no longer declares CountryType2"
    recognised = frozenset(code for code in re.findall(r'value="([A-Z]{2})"', block.group(1)) if isinstance(code, str))
    carried, _ = _vocabulary()
    return tuple(sorted(recognised - carried - _USER_ASSIGNED))


@lru_cache(maxsize=1)
def uncatalogued_alpha3_codes() -> tuple[str, ...]:
    """Return every alpha-3 code Facturae can state that the vocabulary does not carry.

    Drawn from the Facturae ``CountryType`` enumeration for the same reason the
    alpha-2 side is drawn from AEAT's: it is the set a real structured document
    can actually state, so a specimen is a gap a document could genuinely present.
    """
    raw = json.loads(Path(bundled_path(*_FACTURAE_CODES)).read_text(encoding="utf-8"))
    statable = frozenset(_STRING_LIST.validate_python(raw["codes"]))
    _, carried = _vocabulary()
    return tuple(sorted(statable - carried))


def an_uncatalogued_alpha2() -> str:
    """Return one assigned alpha-2 code the bundled vocabulary does not carry.

    Raises:
        AssertionError: When the vocabulary carries every code AEAT recognises,
            which would leave the catalogue-gap properties untestable. That is a
            legitimate future state and it must fail loudly rather than let a
            gate pass over an empty population -- a property assertion over no
            specimen is satisfied by any implementation.
    """
    codes = uncatalogued_alpha2_codes()
    assert codes, "the vocabulary carries every code AEAT recognises; the catalogue-gap property has no specimen"
    return codes[0]


def an_uncatalogued_alpha3() -> str:
    """Return one alpha-3 code Facturae can state that the vocabulary does not carry.

    Raises:
        AssertionError: When no such code remains, on the same terms as the
            alpha-2 derivation.
    """
    codes = uncatalogued_alpha3_codes()
    assert codes, "the vocabulary carries every code Facturae can state; the catalogue-gap property has no specimen"
    return codes[0]
