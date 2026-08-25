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
from typing import Final

from ....core.external_constants import LATIN_1_ENCODING

# Python codec underscore-alias for the same ISO-8859-1 codec.  Separate
# constant so the alias is grep-discoverable alongside the canonical
# ``LATIN_1_ENCODING`` (which uses the hyphenated form ``"latin-1"``).
_LATIN_1_CODEC_ALIAS: Final[str] = "latin_1"

ENCODING_ALIAS_MAP: Mapping[str, str] = {
    LATIN_1_ENCODING: "iso-8859-1",
    _LATIN_1_CODEC_ALIAS: "iso-8859-1",
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
:class:`~cadrumo.domain.calculations.registry.schema.ExportLayoutDefinition`
compares declared encodings through this map so a layout that mixes
``latin-1`` and ``iso-8859-1`` is treated as consistent rather than
flagged as a layout error.
"""
