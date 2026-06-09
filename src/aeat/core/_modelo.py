"""Canonical AEAT modelo identifier enumeration.

This module exposes the closed set of AEAT modelo identifiers known to the
registry.  Every directory name under ``src/aeat/_data/registry/aeat/modelos/``
corresponds to one :class:`Modelo` member; the enum value is the bare three-digit
code string (``"036"``, ``"100"``, …) so it is directly substitutable for the
existing bare-string uso throughout the codebase.

Filing-grade authority — deadline windows, period restrictions, and casilla
definitions — remains the :class:`~aeat.domain.calculations.registry.ValidatedRegistryAuthority`
and the typed :class:`~aeat.domain.calculations.registry.RegistrySnapshot` it
produces.  This enum is the closed-set *identifier* type: it tells you which
modelos exist; the registry tells you what they contain.

A gate test in ``src/aeat/core/tests/test_modelo.py`` binds the enum set to
``registry_modelo_codes()`` so the two cannot drift silently.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["Modelo"]


class Modelo(StrEnum):
    """Closed enumeration of AEAT modelo identifier codes.

    Each member's *name* is the prefixed form (``M036``, ``M100``, …) and
    its *value* is the bare three-digit code string (``"036"``, ``"100"``, …).
    Because :class:`Modelo` inherits from :class:`str` via :class:`~enum.StrEnum`,
    every member compares equal to its raw string value::

        Modelo.M303 == "303"   # True
        Modelo.M303 == Modelo.M303   # True

    The set is bound to the registry directory listing by a gate test; adding a
    new modelo to the registry without updating this enum will fail that test.
    """

    M036 = "036"
    M100 = "100"
    M111 = "111"
    M115 = "115"
    M123 = "123"
    M130 = "130"
    M131 = "131"
    M151 = "151"
    M180 = "180"
    M184 = "184"
    M190 = "190"
    M193 = "193"
    M200 = "200"
    M202 = "202"
    M210 = "210"
    M232 = "232"
    M303 = "303"
    M308 = "308"
    M309 = "309"
    M322 = "322"
    M347 = "347"
    M349 = "349"
    M353 = "353"
    M360 = "360"
    M369 = "369"
    M390 = "390"
    M714 = "714"
    M720 = "720"
    M721 = "721"
    M840 = "840"
