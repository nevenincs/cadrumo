"""Canonical raw TOML field names shared by registry loading stages."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

_PREDECESSOR_FIELD: Final = "predecessor"
_CASILLA_STORAGE_BASELINE_FIELD: Final = "casilla_storage_baseline"
_FAMILY_STORAGE_BASELINE_FIELD: Final = "family_storage_baseline"
_RESTATED_FAMILIES_FIELD: Final = "restated_families"
_CLEARED_FAMILIES_FIELD: Final = "cleared_families"
_NO_PREDECESSOR_TABLE_KEY: Final = "none"
_INHERITED_SECTION: Final = "casillas"
_RETIREMENT_SECTION: Final = "casilla_continuidad_evolutions"
_IDENTIFIER_EVOLUTIONS_SECTION: Final = "identifier_evolutions"
_EDITION_SOURCE_DEFAULT_FIELD: Final = "casilla_source_refs"
_EDITION_ORDEN_FIELD: Final = "orden_aplicabilidad"
_ROW_SOURCE_FIELD: Final = "source_refs"
_ROW_SOURCE_ADDITIONS_FIELD: Final = "additional_source_refs"
_ROW_LEGAL_FIELD: Final = "legal_refs"
_ROW_INHERITED_FROM_FIELD: Final = "inherited_from"
_ROW_CONSTRAINTS_FIELD: Final = "constraints"
_EXPORT_REFS_FIELD: Final = "export_refs"
_REFERENCE_SECTIONS: Final[Mapping[str, str]] = {
    "formula": "formulas",
    "binding": "bindings",
    "alternate_bindings": "bindings",
}
