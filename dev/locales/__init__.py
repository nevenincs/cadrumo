"""Locale-catalogue maintenance facade for shared YAML translations.

Contributor tooling: it maintains the four runtime catalogues that ship under
``src/cadrumo/locales/`` but is not itself part of the distribution. The
catalogue YAML (``en``, ``es``, ``ca``, ``hu``) and the allowlist JSON stay in
the package because the renderer loads them at runtime; only the maintenance
code lives here.

The package keeps those catalogues in sync with codebase translation keys and
enforces inter-locale parity. The developer CLI (``python -m dev.locales``)
owns edits through ``set``, ``remove``, ``scaffold``, ``scaffold --check``, and
``audit`` commands; the catalogue YAML is CLI-maintained, not hand-edited.

Major declarations:

* :class:`LocaleManager` loads, scaffolds, checks, and audits the runtime locale
  catalogues.
* :class:`StrictUniqueKeyLoader` rejects duplicate YAML keys at parse time.
* :func:`catalogue_write_guard` serialises catalogue edits and refuses a write
  that would discard a change landed by another writer.
* :data:`LocaleNode` documents the recursive locale-tree shape consumers walk.
"""

from __future__ import annotations

from ._ast_scanner import (
    declares_locale_keys,
    scan_namespace_markers,
    scan_namespace_markers_in_text,
    scan_source_text,
    scan_source_tree,
)
from ._colanding import (
    LAST_CHANGE,
    STAGED_CHANGE,
    ColandingFinding,
    ColandingResult,
    check_colanding,
    resolve_change,
)
from ._fstring_registry import get_registered_keys
from ._paths import DOCS_SRC_DIR, HARNESS_SRC_DIR, LOCALES_DIR, SRC_DIR
from ._registry_scanner import scan_modelo_schema_keys, scan_profile_schema_keys, scan_registry_keys
from ._revision_drift import (
    RevisionMoveCandidate,
    RevisionMoveReport,
    RevisionParityFindings,
    casilla_revision_pairs,
    classify_revision_moves,
    classify_revision_parity,
    revision_pairs,
)
from ._status import (
    RESERVED_INTERPOLATION_TOKENS,
    CatalogueLeafState,
    CatalogueStatusRecord,
    catalogue_status,
    classify_catalogue_leaf,
)
from ._subtree_move import (
    LocaleMoveConflict,
    LocaleMoveDisposition,
    LocaleMoveEntry,
    LocaleSubtreeMovePlan,
    LocaleSubtreeMoveResult,
    normalise_key_prefix,
    plan_locale_subtree_move,
)
from ._write_guard import CatalogueWriteGuard, catalogue_write_guard
from .manager import LocaleManager, LocaleNode, StrictUniqueKeyLoader

__all__ = [
    "DOCS_SRC_DIR",
    "HARNESS_SRC_DIR",
    "LAST_CHANGE",
    "LOCALES_DIR",
    "RESERVED_INTERPOLATION_TOKENS",
    "SRC_DIR",
    "STAGED_CHANGE",
    "CatalogueLeafState",
    "CatalogueStatusRecord",
    "CatalogueWriteGuard",
    "ColandingFinding",
    "ColandingResult",
    "LocaleManager",
    "LocaleMoveConflict",
    "LocaleMoveDisposition",
    "LocaleMoveEntry",
    "LocaleNode",
    "LocaleSubtreeMovePlan",
    "LocaleSubtreeMoveResult",
    "RevisionMoveCandidate",
    "RevisionMoveReport",
    "RevisionParityFindings",
    "StrictUniqueKeyLoader",
    "casilla_revision_pairs",
    "catalogue_status",
    "catalogue_write_guard",
    "check_colanding",
    "classify_catalogue_leaf",
    "classify_revision_moves",
    "classify_revision_parity",
    "declares_locale_keys",
    "get_registered_keys",
    "normalise_key_prefix",
    "plan_locale_subtree_move",
    "resolve_change",
    "revision_pairs",
    "scan_modelo_schema_keys",
    "scan_namespace_markers",
    "scan_namespace_markers_in_text",
    "scan_profile_schema_keys",
    "scan_registry_keys",
    "scan_source_text",
    "scan_source_tree",
]
