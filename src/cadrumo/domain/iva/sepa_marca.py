"""Marca SEPA derivation for the Modelo 303 cuenta-devolución (DID) block.

:func:`derive_sepa_marca` returns :class:`SepaMarca` from the country fields
carried by :class:`domain.deadlines.RefundAccount`, the refund-account
model consumed by Modelo 303 settlement flows.

The official Diseño de Registros DR303 ``DP303DID`` page carries a single
``Marca SEPA`` indicator (position 194, length 1) classifying the refund
account AEAT pays into:

* ``"1"`` — Cuenta España (the account is a Spanish IBAN, country ``ES``);
* ``"2"`` — UE SEPA (a SEPA-zone account that is not Spanish);
* ``"3"`` — Resto Países (an account outside the SEPA zone — a SWIFT-BIC plus
  foreign-bank block account).

The marca is a *derivation*, not an operator input: it follows from the
account's country (the IBAN's two-letter ISO 3166-1 country prefix for an
IBAN account, or the bank's ``bank_country_code`` for a non-IBAN SWIFT
account) and that country's membership of the SEPA zone. Deriving it rather
than asking for it removes an error-prone operator field and keeps the DID
block grounded in the account itself.

Grounding of the SEPA-zone membership set: the Single Euro Payments Area is
the geographic scheme defined by the European Payments Council (EPC). Its
participant list is the 27 EU member states, the three additional EEA states
(Iceland, Liechtenstein, Norway), and the non-EEA participants the EPC admits
to the schemes (Switzerland, Monaco, San Marino, Andorra, Vatican City State,
the United Kingdom, and the UK Crown Dependencies of Jersey, Guernsey, and the
Isle of Man, plus Gibraltar). Membership is by the ISO 3166-1 alpha-2 country
code that prefixes a SEPA IBAN, so the set below is keyed by that code.

Source: European Payments Council, "EPC List of SEPA Scheme Countries"
(EPC409-09); the SEPA geographic scope under Regulation (EU) No 260/2012.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from .establishment import SPAIN_COUNTRY_CODE


class SepaMarca(StrEnum):
    """Diseño DR303 ``Marca SEPA`` indicator for the cuenta-devolución block.

    The member *value* is the single-character token the DID page expects at
    position 194. ``ESPANA`` and ``UE_SEPA`` are the two SEPA-zone marcas
    (IBAN-only DID sub-fields); ``RESTO_PAISES`` is the non-SEPA marca that
    additionally carries the SWIFT-BIC and the foreign-bank block.
    """

    ESPANA = "1"
    """Cuenta España — a Spanish IBAN (country ``ES``)."""
    UE_SEPA = "2"
    """UE SEPA — a SEPA-zone account that is not Spanish."""
    RESTO_PAISES = "3"
    """Resto Países — an account outside the SEPA zone."""


#: ISO 3166-1 alpha-2 country code of Spain, the ``Marca SEPA = 1`` country.

#: The SEPA-zone country codes (excluding Spain, which is its own marca). A
#: refund account whose country is in this set is ``Marca SEPA = 2`` (UE SEPA);
#: a country outside it (and not ``ES``) is ``Marca SEPA = 3`` (Resto Países).
#: Keyed by the ISO 3166-1 alpha-2 code that prefixes a SEPA IBAN. Grounded in
#: the European Payments Council SEPA scheme participant list (EPC409-09) under
#: Regulation (EU) No 260/2012 — see the module docstring.
SEPA_ZONE_COUNTRY_CODES: Final[frozenset[str]] = frozenset(
    {
        # EU member states (27) other than Spain.
        "AT",  # Austria
        "BE",  # Belgium
        "BG",  # Bulgaria
        "HR",  # Croatia
        "CY",  # Cyprus
        "CZ",  # Czechia
        "DK",  # Denmark
        "EE",  # Estonia
        "FI",  # Finland
        "FR",  # France
        "DE",  # Germany
        "GR",  # Greece
        "HU",  # Hungary
        "IE",  # Ireland
        "IT",  # Italy
        "LV",  # Latvia
        "LT",  # Lithuania
        "LU",  # Luxembourg
        "MT",  # Malta
        "NL",  # Netherlands
        "PL",  # Poland
        "PT",  # Portugal
        "RO",  # Romania
        "SK",  # Slovakia
        "SI",  # Slovenia
        "SE",  # Sweden
        # Additional EEA states (non-EU).
        "IS",  # Iceland
        "LI",  # Liechtenstein
        "NO",  # Norway
        # Non-EEA EPC SEPA participants.
        "CH",  # Switzerland
        "MC",  # Monaco
        "SM",  # San Marino
        "AD",  # Andorra
        "VA",  # Vatican City State
        "GB",  # United Kingdom
        "GI",  # Gibraltar
        "JE",  # Jersey
        "GG",  # Guernsey
        "IM",  # Isle of Man
    },
)


def _account_country_code(*, iban: str | None, bank_country_code: str) -> str | None:
    """Return the ISO 3166-1 alpha-2 country code of a refund account.

    Prefers the IBAN's first two characters (the IBAN country prefix is the
    authoritative country of a SEPA account); falls back to the explicit
    ``bank_country_code`` for a non-IBAN SWIFT account. Returns ``None`` when
    neither a country-prefixed IBAN nor a bank country code is available.
    """
    if iban:
        canonical = iban.replace(" ", "").replace("-", "").upper()
        if len(canonical) >= 2 and canonical[:2].isalpha():
            return canonical[:2]
    code = bank_country_code.strip().upper()
    return code or None


def derive_sepa_marca(*, iban: str | None, bank_country_code: str = "") -> SepaMarca:
    """Derive the DR303 ``Marca SEPA`` for a refund account from its country.

    The country is taken from the IBAN's two-letter prefix (a SEPA IBAN
    account) or, absent an IBAN, from ``bank_country_code`` (a SWIFT account).
    ``ES`` yields :attr:`SepaMarca.ESPANA` (``"1"``); any other SEPA-zone
    country yields :attr:`SepaMarca.UE_SEPA` (``"2"``); a country outside the
    SEPA zone — or no resolvable country — yields
    :attr:`SepaMarca.RESTO_PAISES` (``"3"``), the marca that additionally
    carries the SWIFT-BIC and foreign-bank block.

    The membership set is grounded in the European Payments Council SEPA
    scheme participant list (see the module docstring); this is a derivation,
    never an operator input.

    Returns:
        The derived :class:`SepaMarca`.
    """
    country = _account_country_code(iban=iban, bank_country_code=bank_country_code)
    if country == SPAIN_COUNTRY_CODE:
        return SepaMarca.ESPANA
    if country is not None and country in SEPA_ZONE_COUNTRY_CODES:
        return SepaMarca.UE_SEPA
    return SepaMarca.RESTO_PAISES
