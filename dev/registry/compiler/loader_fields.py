"""Canonical raw TOML field names shared by registry loading stages."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

PREDECESSOR_FIELD: Final = "predecessor"
CASILLA_STORAGE_BASELINE_FIELD: Final = "casilla_storage_baseline"
FAMILY_STORAGE_BASELINE_FIELD: Final = "family_storage_baseline"
_RESTATED_FAMILIES_FIELD: Final = "restated_families"
CLEARED_FAMILIES_FIELD: Final = "cleared_families"
DISPOSITIONS_FIELD: Final = "family_dispositions"
DISPOSITION_REMOVALS_FIELD: Final = "family_disposition_removals"
NO_PREDECESSOR_TABLE_KEY: Final = "none"
INHERITED_SECTION: Final = "casillas"
RETIREMENT_SECTION: Final = "casilla_continuidad_evolutions"
_IDENTIFIER_EVOLUTIONS_SECTION: Final = "identifier_evolutions"
EDITION_SOURCE_DEFAULT_FIELD: Final = "casilla_source_refs"
EDITION_ORDEN_FIELD: Final = "orden_aplicabilidad"
ROW_SOURCE_FIELD: Final = "source_refs"
ROW_SOURCE_ADDITIONS_FIELD: Final = "additional_source_refs"
ROW_LEGAL_FIELD: Final = "legal_refs"
ROW_INHERITED_FROM_FIELD: Final = "inherited_from"
ROW_CONSTRAINTS_FIELD: Final = "constraints"
EXPORT_REFS_FIELD: Final = "export_refs"
REFERENCE_SECTIONS: Final[Mapping[str, str]] = {
    "formula": "formulas",
    "binding": "bindings",
    "alternate_bindings": "bindings",
}
