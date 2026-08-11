"""EU intra-community NIF-IVA identification-number format authority.

A counterparty's intra-community IVA number — the *NIF-IVA intracomunitario*
declared on Modelo 303 / Modelo 349 — has a distinct structural format for each
EU Member State. AEAT's M349 validator (and the VIES registry behind it) bounces
a number whose shape does not match its country's published pattern, so the only
defence against silently building an un-fileable declaration is to validate the
*structure* (not live VIES existence) at the boundary where the number is
accepted.

This module is the single typed authority for that closed, regulatory-shaped
table, per the central-config discipline: the country -> pattern set lives here
in :mod:`core`, not inlined as a literal in a feature module. Consumers
(the ledger invoice counterparty boundary today; the Modelo 349 manual-entry row
in future) resolve a Member State's expected shape through
:func:`nif_iva_format_for_country` and refuse a malformed number with an
instructive, format-naming diagnostic.

Authority: the European Commission VIES national IVA-number structure rules
(``https://ec.europa.eu/taxation_customs/vies/``), grounded in Council Directive
2006/112/EC. Spain (``ES``) is deliberately absent: a Spanish identifier is
validated by the dedicated checksum authority :func:`validate_spanish_tax_id`,
not by a structural pattern. Northern Ireland (``XI``) is included because its
post-Brexit goods IVA prefix mirrors the GB structure and is accepted in
intra-community contexts.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

__all__ = [
    "NIF_IVA_FORMATS",
    "NifIvaFormatSpec",
    "NifIvaPrefix",
    "iso_country_for_nif_iva_prefix",
    "nif_iva_format_for_country",
    "nif_iva_prefix_for_country",
    "normalise_nif_iva",
]


class NifIvaPrefix(StrEnum):
    """Closed set of EU VIES IVA-number country prefixes (plus Northern Ireland).

    The values are the two-character prefix that *leads the IVA number*, which
    for every Member State equals its ISO 3166-1 alpha-2 code except Greece,
    whose IVA prefix is ``EL`` while its ISO code is ``GR``. Spain (``ES``) is
    excluded: Spanish identifiers route through
    :func:`core.identity.validate_spanish_tax_id`. ``XI`` is the
    post-Brexit Northern Ireland goods prefix accepted in intra-community
    contexts.
    """

    AT = "AT"
    BE = "BE"
    BG = "BG"
    CY = "CY"
    CZ = "CZ"
    DE = "DE"
    DK = "DK"
    EE = "EE"
    EL = "EL"
    FI = "FI"
    FR = "FR"
    HR = "HR"
    HU = "HU"
    IE = "IE"
    IT = "IT"
    LT = "LT"
    LU = "LU"
    LV = "LV"
    MT = "MT"
    NL = "NL"
    PL = "PL"
    PT = "PT"
    RO = "RO"
    SE = "SE"
    SI = "SI"
    SK = "SK"
    XI = "XI"


@dataclass(frozen=True, slots=True)
class NifIvaFormatSpec:
    """The structural format of one Member State's NIF-IVA.

    Attributes:
        prefix: The leading IVA prefix this spec validates.
        country_name: Human-readable country name for instructive diagnostics.
        pattern: Anchored regex matched against the full normalised IVA number
            (prefix included).
        description: Operator-facing description of the expected shape, e.g.
            ``"DE + 9 digits"``.
        example: A well-formed example number for the instructive refusal.
    """

    prefix: NifIvaPrefix
    country_name: str
    pattern: re.Pattern[str]
    description: str
    example: str


def _spec(prefix: NifIvaPrefix, country_name: str, pattern: str, description: str, example: str) -> NifIvaFormatSpec:
    return NifIvaFormatSpec(
        prefix=prefix,
        country_name=country_name,
        pattern=re.compile(pattern),
        description=description,
        example=example,
    )


# Per-Member-State NIF-IVA structures, sourced from the European Commission VIES
# national IVA-number format rules (Council Directive 2006/112/EC). Patterns are
# anchored and applied to the uppercased, separator-stripped IVA number with its
# two-character prefix.
NIF_IVA_FORMATS: Final[Mapping[NifIvaPrefix, NifIvaFormatSpec]] = {
    NifIvaPrefix.AT: _spec(NifIvaPrefix.AT, "Austria", r"^ATU\d{8}$", "ATU + 8 digits", "ATU12345678"),
    NifIvaPrefix.BE: _spec(
        NifIvaPrefix.BE, "Belgium", r"^BE[01]\d{9}$", "BE + 10 digits (first digit 0 or 1)", "BE0123456789"
    ),
    NifIvaPrefix.BG: _spec(NifIvaPrefix.BG, "Bulgaria", r"^BG\d{9,10}$", "BG + 9 or 10 digits", "BG123456789"),
    NifIvaPrefix.CY: _spec(NifIvaPrefix.CY, "Cyprus", r"^CY\d{8}[A-Z]$", "CY + 8 digits + 1 letter", "CY12345678L"),
    NifIvaPrefix.CZ: _spec(NifIvaPrefix.CZ, "Czechia", r"^CZ\d{8,10}$", "CZ + 8, 9 or 10 digits", "CZ12345678"),
    NifIvaPrefix.DE: _spec(NifIvaPrefix.DE, "Germany", r"^DE\d{9}$", "DE + 9 digits", "DE123456789"),
    NifIvaPrefix.DK: _spec(NifIvaPrefix.DK, "Denmark", r"^DK\d{8}$", "DK + 8 digits", "DK12345678"),
    NifIvaPrefix.EE: _spec(NifIvaPrefix.EE, "Estonia", r"^EE\d{9}$", "EE + 9 digits", "EE123456789"),
    NifIvaPrefix.EL: _spec(NifIvaPrefix.EL, "Greece", r"^EL\d{9}$", "EL + 9 digits", "EL123456789"),
    NifIvaPrefix.FI: _spec(NifIvaPrefix.FI, "Finland", r"^FI\d{8}$", "FI + 8 digits", "FI12345678"),
    NifIvaPrefix.FR: _spec(
        NifIvaPrefix.FR, "France", r"^FR[A-Z0-9]{2}\d{9}$", "FR + 2 letters/digits + 9 digits", "FR12345678901"
    ),
    NifIvaPrefix.HR: _spec(NifIvaPrefix.HR, "Croatia", r"^HR\d{11}$", "HR + 11 digits", "HR12345678901"),
    NifIvaPrefix.HU: _spec(NifIvaPrefix.HU, "Hungary", r"^HU\d{8}$", "HU + 8 digits", "HU12345678"),
    NifIvaPrefix.IE: _spec(
        NifIvaPrefix.IE,
        "Ireland",
        r"^IE(\d{7}[A-W]|\d[A-Z0-9+*]\d{5}[A-W]|\d{7}[A-W][A-W])$",
        "IE + 7 digits + 1-2 letters",
        "IE1234567T",
    ),
    NifIvaPrefix.IT: _spec(NifIvaPrefix.IT, "Italy", r"^IT\d{11}$", "IT + 11 digits", "IT12345678901"),
    NifIvaPrefix.LT: _spec(NifIvaPrefix.LT, "Lithuania", r"^LT(\d{9}|\d{12})$", "LT + 9 or 12 digits", "LT123456789"),
    NifIvaPrefix.LU: _spec(NifIvaPrefix.LU, "Luxembourg", r"^LU\d{8}$", "LU + 8 digits", "LU12345678"),
    NifIvaPrefix.LV: _spec(NifIvaPrefix.LV, "Latvia", r"^LV\d{11}$", "LV + 11 digits", "LV12345678901"),
    NifIvaPrefix.MT: _spec(NifIvaPrefix.MT, "Malta", r"^MT\d{8}$", "MT + 8 digits", "MT12345678"),
    NifIvaPrefix.NL: _spec(
        NifIvaPrefix.NL, "Netherlands", r"^NL\d{9}B\d{2}$", "NL + 9 digits + 'B' + 2 digits", "NL123456789B01"
    ),
    NifIvaPrefix.PL: _spec(NifIvaPrefix.PL, "Poland", r"^PL\d{10}$", "PL + 10 digits", "PL1234567890"),
    NifIvaPrefix.PT: _spec(NifIvaPrefix.PT, "Portugal", r"^PT\d{9}$", "PT + 9 digits", "PT123456789"),
    NifIvaPrefix.RO: _spec(NifIvaPrefix.RO, "Romania", r"^RO\d{2,10}$", "RO + 2 to 10 digits", "RO1234567890"),
    NifIvaPrefix.SE: _spec(NifIvaPrefix.SE, "Sweden", r"^SE\d{12}$", "SE + 12 digits", "SE123456789012"),
    NifIvaPrefix.SI: _spec(NifIvaPrefix.SI, "Slovenia", r"^SI\d{8}$", "SI + 8 digits", "SI12345678"),
    NifIvaPrefix.SK: _spec(NifIvaPrefix.SK, "Slovakia", r"^SK\d{10}$", "SK + 10 digits", "SK1234567890"),
    NifIvaPrefix.XI: _spec(
        NifIvaPrefix.XI,
        "Northern Ireland",
        r"^XI(\d{9}|\d{12}|GD\d{3}|HA\d{3})$",
        "XI + 9 or 12 digits (or GD/HA + 3 digits)",
        "XI123456789",
    ),
}


# ISO 3166-1 alpha-2 country code -> IVA prefix. Identity for every Member State
# except Greece (ISO ``GR`` -> IVA prefix ``EL``); ``EL`` and ``XI`` are accepted
# directly as already being prefixes.
_ISO_COUNTRY_TO_PREFIX: Final[Mapping[str, NifIvaPrefix]] = {
    **{prefix.value: prefix for prefix in NifIvaPrefix},
    "GR": NifIvaPrefix.EL,
}


# IVA prefix -> ISO 3166-1 alpha-2 country code, the inverse direction of
# ``_ISO_COUNTRY_TO_PREFIX``. Written rather than derived by inversion because
# that map is not injective: both ``EL`` and ``GR`` key the Greek prefix, so an
# inversion would resolve Greece to whichever key was read last.
_PREFIX_TO_ISO_COUNTRY: Final[Mapping[NifIvaPrefix, str]] = {
    **{prefix: prefix.value for prefix in NifIvaPrefix},
    NifIvaPrefix.EL: "GR",
}


def iso_country_for_nif_iva_prefix(prefix: NifIvaPrefix) -> str:
    """Return the ISO 3166-1 alpha-2 code the IVA *prefix* names.

    Identity for every Member State except Greece, whose IVA numbers lead with
    ``EL`` while its ISO code is ``GR``. That one divergence is the whole reason
    this exists: a caller reading a country off a printed IVA number and handing
    ``EL`` to an ISO-keyed catalogue gets no match, and a catalogue that answers
    "not a Member State" for Greece places a Greek party outside the EU.

    Northern Ireland's ``XI`` is returned unchanged. It is not an ISO country
    code, and it is deliberately not translated to ``GB``: the two are not
    interchangeable for IVA, and the catalogues that consume this carry ``XI``
    as its own member.
    """
    return _PREFIX_TO_ISO_COUNTRY[prefix]


def normalise_nif_iva(value: str) -> str:
    """Return the uppercased IVA number with whitespace and separators stripped.

    Operators routinely paste numbers carrying spaces, dots, or hyphens
    (``BE 0123.456.789``); the canonical form drops them so the structural
    pattern matches.
    """
    return value.strip().upper().replace(" ", "").replace("-", "").replace(".", "")


def nif_iva_prefix_for_country(iso_country: str) -> NifIvaPrefix | None:
    """Resolve an ISO-3166 alpha-2 country code (or IVA prefix) to its :class:`NifIvaPrefix`.

    Returns ``None`` for a country that has no NIF-IVA pattern (a non-EU
    counterparty, or Spain which uses the checksum validator).
    """
    return _ISO_COUNTRY_TO_PREFIX.get(iso_country.strip().upper())


def nif_iva_format_for_country(iso_country: str) -> NifIvaFormatSpec | None:
    """Return the :class:`NifIvaFormatSpec` for a country, or ``None`` if unknown.

    A ``None`` result means the country is not an EU Member State carrying a
    structural NIF-IVA pattern; the caller applies its generic prefix/body check
    instead of refusing the counterparty outright.
    """
    prefix = nif_iva_prefix_for_country(iso_country)
    if prefix is None:
        return None
    return NIF_IVA_FORMATS.get(prefix)
