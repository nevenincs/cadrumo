"""Locale-catalogue maintenance facade for shared YAML translations.

The package keeps the four runtime catalogues (``en``, ``es``, ``ca``, ``hu``)
in sync with codebase translation keys and enforces inter-locale parity. The
developer CLI (``python -m cadrumo.locales``) owns edits through ``set``,
``remove``, ``scaffold``, ``scaffold --check``, and ``audit`` commands; the
catalogue YAML is CLI-maintained, not hand-edited.

Major declarations:

* :class:`LocaleManager` loads, scaffolds, checks, and audits the runtime locale
  catalogues.
* :class:`StrictUniqueKeyLoader` rejects duplicate YAML keys at parse time.
* :class:`LocaleError` reports maintenance failures.
"""

from __future__ import annotations

from ._ast_scanner import scan_namespace_markers, scan_source_tree
from ._fstring_registry import get_registered_keys
from ._registry_scanner import scan_modelo_schema_keys, scan_profile_schema_keys, scan_registry_keys
from ._status import (
    RESERVED_INTERPOLATION_TOKENS,
    CatalogueLeafState,
    CatalogueStatusRecord,
    catalogue_status,
    classify_catalogue_leaf,
)
from .manager import LocaleError, LocaleManager, StrictUniqueKeyLoader

__all__ = [
    "RESERVED_INTERPOLATION_TOKENS",
    "CatalogueLeafState",
    "CatalogueStatusRecord",
    "LocaleError",
    "LocaleManager",
    "StrictUniqueKeyLoader",
    "catalogue_status",
    "classify_catalogue_leaf",
    "get_registered_keys",
    "scan_modelo_schema_keys",
    "scan_namespace_markers",
    "scan_profile_schema_keys",
    "scan_registry_keys",
    "scan_source_tree",
]
