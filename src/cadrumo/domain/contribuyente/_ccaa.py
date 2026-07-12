"""The closed catalogue of ordinary common-regime Spanish autonomous communities.

Lives in its own module so wizard descriptor construction can reference
the enum without triggering the rest of ``cadrumo.domain.contribuyente``'s
import-time chain.

Canonical CCAA shape
--------------------
This module is the **single canonical owner** of the CCAA type.  All
other packages must import from here; no parallel CCAA enum may exist
elsewhere in the codebase.

Canonical value space
~~~~~~~~~~~~~~~~~~~~~
Each member's *value* is the lowercase Spanish name token used by the
TOML dispatch tables (e.g. ``andalucia``, ``madrid``).  The dispatch
table keys in ``registry/aeat/modelos/100/revisions/2025.toml`` are
deliberately written to match these values so no translation is
required at the binding-resolution boundary.

Retired ISO-code Mapping
~~~~~~~~~~~~~~~~~~~~~~~~
:meth:`CCAA.from_iso_code` maps the 3-letter codes that were used by
the now-deleted ``RentaCCAA`` enum (``AND`` → ``ANDALUCIA``, etc.) for
call sites that still need to translate those retired codes.
"""

from __future__ import annotations

from enum import StrEnum

from ...core.errors import ProfileAnswerTypeError
from ...core.logging import get_logger

# Maps the 3-letter ISO-like codes from the former ``RentaCCAA`` enum to
# the canonical CCAA member names.  Foral regimes (NAV, PVA) and the two
# autonomous cities (CEU, MEL) were present in RentaCCAA but fall outside
# the common-regime scope of this enum; callers must handle them separately
# (see ``ForalRegimeError`` in ``cadrumo.domain.contribuyente``).
_ISO_CODE_MAP: dict[str, str] = {
    "AND": "ANDALUCIA",
    "ARA": "ARAGON",
    "AST": "ASTURIAS",
    "BAL": "BALEARES",
    "CAN": "CANARIAS",
    "CAB": "CANTABRIA",
    "CLM": "CASTILLA_LA_MANCHA",
    "CYL": "CASTILLA_Y_LEON",
    "CAT": "CATALUNA",
    "VAL": "COMUNIDAD_VALENCIANA",
    "EXT": "EXTREMADURA",
    "GAL": "GALICIA",
    "LAR": "LA_RIOJA",
    "MAD": "MADRID",
    "MUR": "MURCIA",
}


class CCAA(StrEnum):
    """Ordinary common-regime autonomous communities for residence profile data.

    The canonical value for each member is the lowercase Spanish name token
    (e.g. ``"andalucia"``, ``"madrid"``).  These tokens match the dispatch
    table keys in the Renta 100 registry TOML verbatim.

    Foral regimes (País Vasco, Navarra) and the autonomous cities (Ceuta,
    Melilla) are intentionally excluded; those raise
    :class:`domain.contribuyente.ForalRegimeError` when a user selects them.
    """

    ANDALUCIA = "andalucia"
    ARAGON = "aragon"
    ASTURIAS = "asturias"
    BALEARES = "baleares"
    CANARIAS = "canarias"
    CANTABRIA = "cantabria"
    CASTILLA_LA_MANCHA = "castilla_la_mancha"
    CASTILLA_Y_LEON = "castilla_y_leon"
    CATALUNA = "cataluna"
    COMUNIDAD_VALENCIANA = "comunidad_valenciana"
    EXTREMADURA = "extremadura"
    GALICIA = "galicia"
    LA_RIOJA = "la_rioja"
    MADRID = "madrid"
    MURCIA = "murcia"

    @classmethod
    def from_iso_code(cls, code: str) -> CCAA:
        """Return the canonical member for a 3-letter ISO-like CCAA code.

        The code set corresponds to the values used by the former
        ``RentaCCAA`` enum (``AND``, ``ARA``, ``AST``, …).  Foral-regime
        codes (``NAV``, ``PVA``) and autonomous-city codes (``CEU``,
        ``MEL``) are not members of this enum; pass-through to the
        foral-regime error path is the caller's responsibility.

        Args:
            code: 3-letter ISO-like CCAA code (e.g. ``"AND"``, ``"MAD"``).

        Returns:
            The matching :class:`CCAA` member.

        Raises:
            KeyError: when ``code`` is not a recognised 3-letter alias.
        """
        upper = code.strip().upper()
        member_name = _ISO_CODE_MAP.get(upper)
        if member_name is None:
            valid = ", ".join(sorted(_ISO_CODE_MAP))
            raise KeyError(f"unknown ISO CCAA code {code!r}; recognised codes: {valid}")
        return cls[member_name]

    @classmethod
    def from_label(cls, label: str) -> CCAA:
        """Parse a free-form label into the canonical member.

        Accepts both the canonical lowercase token (``"andalucia"``) and
        the 3-letter ISO-like code (``"AND"``), case-insensitively.
        Underscores and hyphens are normalised to underscores before
        matching.

        Args:
            label: Free-form label to parse into a :class:`CCAA` member.

        Returns:
            The matching :class:`CCAA` member.

        Raises:
            ProfileAnswerTypeError: when ``label`` cannot be mapped to any member.
        """
        normalised = label.strip().lower().replace("-", "_")
        # Try canonical value first.
        try:
            return cls(normalised)
        except ValueError as exc:
            get_logger(__name__).debug(
                "CCAA.from_label: canonical lookup failed for %r; trying ISO code (%s)",
                label,
                exc,
            )
        # Try 3-letter ISO code (case-insensitive).
        upper = normalised.upper()
        member_name = _ISO_CODE_MAP.get(upper)
        if member_name is not None:
            return cls[member_name]
        valid = ", ".join(sorted(m.value for m in cls))
        raise ProfileAnswerTypeError(f"unknown CCAA label {label!r}; valid values: {valid}")


__all__ = ["CCAA"]
