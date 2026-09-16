"""EU intra-community NIF-IVA identification-number format authority.

A counterparty's intra-community IVA number — the *NIF-IVA intracomunitario*
declared on Modelo 303 / Modelo 349 — has a distinct structural format for each
EU Member State. AEAT's M349 validator (and the VIES registry behind it) bounces
a number whose shape does not match its country's published pattern, so the only
defence against silently building an un-fileable declaration is to validate the
*structure* (not live VIES existence) at the boundary where the number is
accepted.

This module is the typed kernel for that regulatory-shaped value. The country,
prefix, and pattern records live in the non-Modelo facts registry; this module
keeps only the opaque projected token, compiled-pattern value object, and
normalisation mechanics. Consumers (the ledger invoice counterparty boundary
today; the Modelo 349 manual-entry row in future) resolve a Member State's
expected shape through the domain registry and refuse a malformed number with
an instructive, format-naming diagnostic.

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
from dataclasses import dataclass

from ...core.registry_token import StrictRegistryToken

__all__ = [
    "NifIvaFormatSpec",
    "NifIvaPrefix",
    "is_nif_iva_structurally_shaped",
    "normalise_nif_iva",
]


class NifIvaPrefix(StrictRegistryToken):
    """Opaque NIF-IVA prefix projected from the facts registry.

    Membership is deliberately not represented by a Python enum. The registry
    owns the 27 prefixes, including the ``GR`` -> ``EL`` country divergence and
    ``XI``. A token can only be constructed by the typed registry projection.
    """

    __slots__ = ()

    _empty_value_message = "NIF-IVA prefix must be a non-empty string"


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


def normalise_nif_iva(value: str) -> str:
    """Return the uppercased IVA number with whitespace and separators stripped.

    Operators routinely paste numbers carrying spaces, dots, or hyphens
    (``BE 0123.456.789``); the canonical form drops them so the structural
    pattern matches.
    """
    return value.strip().upper().replace(" ", "").replace("-", "").replace(".", "")


def is_nif_iva_structurally_shaped(value: str) -> bool:
    """Return whether *value* has a generic prefixed tax-identifier shape.

    This is deliberately only lexical structure. Country membership and dated
    per-country patterns are domain-registry policy and are resolved by
    :mod:`cadrumo.domain.calculations.registry.nif_iva_catalogue`.
    """
    normalised = normalise_nif_iva(value)
    if len(normalised) < 9 or len(normalised) > 15:
        return False
    prefix, body = normalised[:2], normalised[2:]
    if not prefix.isalpha() or not body.isalnum():
        return False
    if prefix in {"AA", "XX", "ZZ"}:
        return False
    digits = sum(character.isdigit() for character in body)
    return digits * 2 >= len(body)
