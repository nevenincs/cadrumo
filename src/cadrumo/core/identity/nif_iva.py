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
expected shape through :func:`nif_iva_format_for_country` and refuse a malformed
number with an instructive, format-naming diagnostic.

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
from typing import Self

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from ..errors.hierarchy import CoreValidationError

__all__ = [
    "NifIvaFormatSpec",
    "NifIvaPrefix",
    "iso_country_for_nif_iva_prefix",
    "nif_iva_format_for_country",
    "nif_iva_prefix_for_country",
    "normalise_nif_iva",
]


class NifIvaPrefix(str):
    """Opaque NIF-IVA prefix projected from the facts registry.

    Membership is deliberately not represented by a Python enum. The registry
    owns the 27 prefixes, including the ``GR`` -> ``EL`` country divergence and
    ``XI``. A token can only be constructed by the typed registry projection.
    """

    __slots__ = ()

    def __new__(cls, value: str, *, _registry_validated: bool = False) -> Self:
        if not _registry_validated:
            raise TypeError("NifIvaPrefix tokens must be projected from the facts registry")
        if not isinstance(value, str) or not value:
            raise ValueError("NIF-IVA prefix must be a non-empty string")
        return str.__new__(cls, value)

    @classmethod
    def _from_registry(cls, value: str) -> Self:
        return cls(value, _registry_validated=True)

    @classmethod
    def _require_registry_token(cls, value: object) -> Self:
        if isinstance(value, cls):
            return value
        raise CoreValidationError("NifIvaPrefix must be a registry-projected token")

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: object,
        _handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        return core_schema.no_info_plain_validator_function(
            cls._require_registry_token,
            json_schema_input_schema=core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )

    @property
    def value(self) -> str:
        return str(self)

    @property
    def name(self) -> str:
        return str(self)


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
    from ...domain.calculations.registry.nif_iva_catalogue import (
        resolve_nif_iva_catalogue,
    )

    return resolve_nif_iva_catalogue().iso_country_for_prefix(prefix)


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
    from ...domain.calculations.registry.nif_iva_catalogue import (
        resolve_nif_iva_catalogue,
    )

    return resolve_nif_iva_catalogue().prefix_for_country(iso_country)


def nif_iva_format_for_country(iso_country: str) -> NifIvaFormatSpec | None:
    """Return the :class:`NifIvaFormatSpec` for a country, or ``None`` if unknown.

    A ``None`` result means the country is not an EU Member State carrying a
    structural NIF-IVA pattern; the caller applies its generic prefix/body check
    instead of refusing the counterparty outright.
    """
    from ...domain.calculations.registry.nif_iva_catalogue import (
        resolve_nif_iva_catalogue,
    )

    return resolve_nif_iva_catalogue().format_for_country(iso_country)
