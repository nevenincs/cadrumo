"""Canonical authored field names used by edition delta storage."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Final

_MODELOS: Final = "modelos"

_CASILLAS: Final = "casillas"

_MANIFEST: Final = "revision.toml"

_ROW_SOURCE: Final = "source_refs"

_ROW_SOURCE_ADDITIONS: Final = "additional_source_refs"

_ROW_LEGAL: Final = "legal_refs"

_EDITION_DEFAULTED_FIELDS: Final = frozenset({_ROW_SOURCE, _ROW_LEGAL})

_CONSTRAINTS: Final = "constraints"

_REPORT_FAMILY: Final = "audit-runs"

_REPORT_LABEL: Final = "report-registry-edition-migration"

_LINEAGE: Final = "continuidad_id"

_REFERENCE_SECTIONS: Final[Mapping[str, str]] = {
    "formula": "formulas",
    "binding": "bindings",
    "alternate_bindings": "bindings",
}

_RETIRED: Final = "retired"

_REVISION_SEGMENT: Final = r'(?:"[^"\n]+"|[^".\]\n]+)'

_ROW_HEADER: Final = re.compile(rf"^\[\[revisions\.{_REVISION_SEGMENT}\.casillas\]\]\s*$")

_CONSTRAINTS_HEADER: Final = re.compile(rf"^\[revisions\.{_REVISION_SEGMENT}\.casillas\.constraints\]\s*$")

_TOML_ESCAPES: Final[Mapping[str, str]] = {
    "\\": "\\\\",
    '"': '\\"',
    "\b": "\\b",
    "\t": "\\t",
    "\n": "\\n",
    "\f": "\\f",
    "\r": "\\r",
}

_FAMILY_SOURCE_DEFAULTS: Final[tuple[tuple[str, str], ...]] = (("formulas", "formula_source_refs"),)

_DECLARED_DEFAULT_KEYS: Final[frozenset[str]] = frozenset(
    {"casilla_source_refs", *(key for _section, key in _FAMILY_SOURCE_DEFAULTS)}
)

_DATE_TAG: Final = "\x00date"
