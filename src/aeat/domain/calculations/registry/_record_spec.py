"""Shared record-specification constants for the fichero-BOE registry.

Single authoritative home for constants that govern how registry
record declarations are validated and normalised.  Moving these
here avoids the circular import that would arise from placing
cross-cutting constants inside ``_schema.py``, and gives tests a
stable import target independent of the schema implementation
details.
"""

from __future__ import annotations

from collections.abc import Mapping

ENCODING_ALIAS_MAP: Mapping[str, str] = {
    "latin-1": "iso-8859-1",
    "latin_1": "iso-8859-1",
    "iso-8859-1": "iso-8859-1",
    "iso_8859_1": "iso-8859-1",
    "cp1252": "cp1252",
    "windows-1252": "cp1252",
    "iso-8859-15": "iso-8859-15",
    "iso_8859_15": "iso-8859-15",
    "latin-9": "iso-8859-15",
}
"""Canonical-encoding map for fichero-BOE registry encoding declarations.

AEAT treats Windows-1252 and ISO-8859-1 as equivalent for fichero-BOE
purposes; Python codec aliases (``latin-1`` ↔ ``iso-8859-1``,
``windows-1252`` ↔ ``cp1252``, ``latin-9`` ↔ ``iso-8859-15``) resolve
to the same wire encoding.  The encoding-consistency validator in
:class:`~aeat.domain.calculations.registry._schema.ExportLayoutDefinition`
compares declared encodings through this map so a layout that mixes
``latin-1`` and ``iso-8859-1`` is treated as consistent rather than
flagged as a layout error.
"""
