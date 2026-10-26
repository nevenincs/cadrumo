"""Closed language vocabulary for the AEAT declaration ``Aux`` block.

Every Modelo 100 XSD AEAT publishes opens its ``Declaracion`` with a mandatory
``Aux`` block whose ``Idioma`` element is restricted to a four-value pattern,
``(E|G|C|V){1}``, identically across the 2020-2025 schemas. The value names the
language the declaration is rendered in, and AEAT publishes no other spelling of
it: it is a closed set, so it belongs in ``core`` as an enum rather than as a
string literal at the site that writes the element.

The set is NOT the application's own output-language vocabulary. Cadrumo renders
its interface in four languages of its own choosing, and that list neither
matches nor constrains this one -- an operator reading the CLI in English still
files a declaration in one of AEAT's four. Mapping one onto the other would be a
category error, which is the mistake this separate home exists to prevent.

Not to be confused with:

- :class:`~core.output_rendering.OutputFormat` and the CLI's language settings,
  which select how the application talks to the operator.
- The ``Aux`` block's sibling ``VERSION`` element, which is a producer/format
  token with no closed value set published anywhere and is therefore declared on
  the export layout rather than enumerated here.

Hydration happens at the registry boundary: the export layout declares the token
and strict schema validation resolves it to a member.
"""

from __future__ import annotations

from enum import StrEnum


class DeclaracionIdioma(StrEnum):
    """Languages the AEAT declaration ``Aux/Idioma`` element accepts.

    Members carry the exact single-character tokens the XSD pattern admits, so a
    member compares, hashes, and serialises identically to the character AEAT
    expects on the wire.
    """

    CASTELLANO = "E"
    """Castellano -- the language a Spanish-language filing declares."""

    GALLEGO = "G"
    """Gallego."""

    CATALAN = "C"
    """Català."""

    VALENCIANO = "V"
    """Valencià."""


__all__ = ["DeclaracionIdioma"]
