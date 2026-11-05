"""Canonical authored field names used by edition delta storage."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Final

MODELOS: Final = "modelos"

CASILLAS: Final = "casillas"

MANIFEST: Final = "revision.toml"

ROW_SOURCE: Final = "source_refs"

ROW_SOURCE_ADDITIONS: Final = "additional_source_refs"

ROW_LEGAL: Final = "legal_refs"

EDITION_DEFAULTED_FIELDS: Final = frozenset({ROW_SOURCE, ROW_LEGAL})

CONSTRAINTS: Final = "constraints"

REPORT_FAMILY: Final = "audit-runs"

REPORT_LABEL: Final = "report-registry-edition-migration"

LINEAGE: Final = "continuidad_id"

REFERENCE_SECTIONS: Final[Mapping[str, str]] = {
    "formula": "formulas",
    "binding": "bindings",
    "alternate_bindings": "bindings",
}

_RETIRED: Final = "retired"

REVISION_SEGMENT: Final = r'(?:"[^"\n]+"|[^".\]\n]+)'

ROW_HEADER: Final = re.compile(rf"^\[\[revisions\.{REVISION_SEGMENT}\.casillas\]\]\s*$")

CONSTRAINTS_HEADER: Final = re.compile(rf"^\[revisions\.{REVISION_SEGMENT}\.casillas\.constraints\]\s*$")

TOML_ESCAPES: Final[Mapping[str, str]] = {
    "\\": "\\\\",
    '"': '\\"',
    "\b": "\\b",
    "\t": "\\t",
    "\n": "\\n",
    "\f": "\\f",
    "\r": "\\r",
}

FAMILY_SOURCE_DEFAULTS: Final[tuple[tuple[str, str], ...]] = (("formulas", "formula_source_refs"),)

DECLARED_DEFAULT_KEYS: Final[frozenset[str]] = frozenset(
    {"casilla_source_refs", *(key for _section, key in FAMILY_SOURCE_DEFAULTS)}
)

DATE_TAG: Final = "\x00date"
