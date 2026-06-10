"""Canonical AEAT modelo identifier enumeration.

This module exposes the closed set of AEAT modelo *identifiers* the codebase
references.  Almost every member has a directory under
``src/aeat/_data/registry/aeat/modelos/`` and is therefore registry-loadable;
the enum value is the bare three-digit code string (``"036"``, ``"100"``, …) so
it is directly substitutable for the existing bare-string usage throughout the
codebase.

A small set of members are known modelos that the code references as
identifiers but which have **no registry definition by design** — currently the
retired :data:`Modelo.M037` (censo simplificada, suppressed by
Orden HAC/1526/2024).  These are enumerated in :data:`NON_REGISTRY_MODELOS`.
They are real codes with implementation support (lifecycle routing, portal
entries), but ``ValidatedRegistryAuthority.validate_modelo`` raises for them and
no registry TOML exists or may be created for them.

Filing-grade authority — deadline windows, period restrictions, and casilla
definitions — remains the :class:`~aeat.domain.calculations.registry.ValidatedRegistryAuthority`
and the typed :class:`~aeat.domain.calculations.registry.RegistrySnapshot` it
produces.  This enum is the closed-set *identifier* type: it tells you which
modelos exist; the registry tells you what (if anything) they contain.

A gate test in ``src/aeat/core/tests/test_modelo.py`` binds the registry-backed
members to ``registry_modelo_codes()`` (enum minus :data:`NON_REGISTRY_MODELOS`)
so the two cannot drift silently, and pins every non-registry member to its
deliberately-absent registry definition.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["NON_REGISTRY_MODELOS", "Modelo"]


class Modelo(StrEnum):
    """Closed enumeration of AEAT modelo identifier codes.

    Each member's *name* is the prefixed form (``M036``, ``M100``, …) and
    its *value* is the bare three-digit code string (``"036"``, ``"100"``, …).
    Because :class:`Modelo` inherits from :class:`str` via :class:`~enum.StrEnum`,
    every member compares equal to its raw string value::

        Modelo.M303 == "303"   # True
        Modelo.M303 == Modelo.M303   # True

    The registry-backed members are bound to the registry directory listing by a
    gate test; adding a new modelo to the registry without updating this enum
    will fail that test.  Members in :data:`NON_REGISTRY_MODELOS` (the retired
    :data:`M037`) are known identifiers with no registry definition by design.
    """

    M036 = "036"
    M037 = "037"
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


#: Known modelo identifiers that intentionally have **no registry definition**.
#: These are real, code-referenced modelos for which
#: :meth:`~aeat.domain.calculations.registry.ValidatedRegistryAuthority.validate_modelo`
#: raises and no registry TOML exists or may be created.  Currently only the
#: retired :data:`Modelo.M037` (censo simplificada, suppressed by
#: Orden HAC/1526/2024; superseded by :data:`Modelo.M036`).  The registry-parity
#: gate excludes these so the enum can carry retired-but-supported codes without
#: implying the registry can load them.
NON_REGISTRY_MODELOS: frozenset[Modelo] = frozenset({Modelo.M037})
