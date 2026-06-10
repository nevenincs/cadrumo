"""Backend-owned operator-surface contract for the CLI command tree.

Declares, in the application layer, the shape the CLI must present: the
accepted root command families, the canonical CRUD verb vocabulary, and
the help/landing documents. The CLI is a thin renderer of this contract
rather than its author.

Major declarations:

* :func:`get_operator_surface_contract` returning
  :class:`OperatorSurfaceContract`, with :data:`ACCEPTED_ROOTS` and
  :data:`MOUNTED_COMMAND_FAMILIES` — the root-surface definition.
* :class:`CrudVerb` and :data:`CANONICAL_CRUD_VERBS` with
  :class:`MutatingNounGroupContract` — the orthogonal CRUD vocabulary.
* :func:`build_help_document` and :func:`build_root_landing_report` with
  :class:`HelpDocument` and :class:`RootLandingReport` — the rendered
  help and landing surfaces.
* :class:`OperatorSurfaceContractError` — the contract-violation failure.
"""

from __future__ import annotations

from ._contract import (
    ACCEPTED_ROOTS,
    MOUNTED_COMMAND_FAMILIES,
    SOURCE_KIND_ALIASES,
    build_operator_surface_contract,
    get_operator_surface_contract,
    require_accepted_root,
    resolve_source_kind_alias,
)
from ._crud_contract import (
    CANONICAL_CRUD_VERBS,
    BucketEventSuffix,
    CrudContractCatalogue,
    CrudVerb,
    KeyValueVerb,
    LifecycleStateVerb,
    MutatingNounGroupContract,
    NounGroupExceptionKind,
    OrthogonalAxis,
    event_suffix_for,
)
from ._crud_registry import BUILTIN_CRUD_CATALOGUE, get_builtin_catalogue
from ._errors import OperatorSurfaceContractError
from ._help import (
    build_help_document,
    build_root_landing_report,
    render_help_text,
    render_root_landing_text,
)
from ._models import (
    FilingStatus,
    HelpDocument,
    HelpEntry,
    HelpSection,
    HelpSurface,
    LifecycleContract,
    ModeloLifecycleStep,
    MountedCommandDomain,
    MountedCommandFamily,
    OperatorMutability,
    OperatorSurfaceContract,
    OperatorSurfaceLogFields,
    RootLandingReport,
    RootSurface,
    RootSurfaceName,
    ServiceOwner,
    SourceKind,
    SourceKindAlias,
)

__all__ = [
    "ACCEPTED_ROOTS",
    "BUILTIN_CRUD_CATALOGUE",
    "CANONICAL_CRUD_VERBS",
    "MOUNTED_COMMAND_FAMILIES",
    "SOURCE_KIND_ALIASES",
    "BucketEventSuffix",
    "CrudContractCatalogue",
    "CrudVerb",
    "FilingStatus",
    "HelpDocument",
    "HelpEntry",
    "HelpSection",
    "HelpSurface",
    "KeyValueVerb",
    "LifecycleContract",
    "LifecycleStateVerb",
    "ModeloLifecycleStep",
    "MountedCommandDomain",
    "MountedCommandFamily",
    "MutatingNounGroupContract",
    "NounGroupExceptionKind",
    "OperatorMutability",
    "OperatorSurfaceContract",
    "OperatorSurfaceContractError",
    "OperatorSurfaceLogFields",
    "OrthogonalAxis",
    "RootLandingReport",
    "RootSurface",
    "RootSurfaceName",
    "ServiceOwner",
    "SourceKind",
    "SourceKindAlias",
    "build_help_document",
    "build_operator_surface_contract",
    "build_root_landing_report",
    "event_suffix_for",
    "get_builtin_catalogue",
    "get_operator_surface_contract",
    "render_help_text",
    "render_root_landing_text",
    "require_accepted_root",
    "resolve_source_kind_alias",
]
