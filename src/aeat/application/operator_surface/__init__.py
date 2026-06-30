"""Public re-export boundary for the backend-owned operator surface.

The package collects the application-layer command-shape declarations from
:mod:`aeat.application.operator_surface._contract`,
:mod:`aeat.application.operator_surface._models`,
:mod:`aeat.application.operator_surface._help`,
:mod:`aeat.application.operator_surface._crud_contract`,
:mod:`aeat.application.operator_surface._crud_registry`, and
:mod:`aeat.application.operator_surface._errors`. Command adapters consume this
surface as data and render it; they do not define a second contract.

Root-surface declarations flow through :func:`get_operator_surface_contract`,
:data:`ACCEPTED_ROOTS`, :data:`MOUNTED_COMMAND_FAMILIES`, and
:class:`OperatorSurfaceContract`. Source-kind aliases remain parser-only
:class:`SourceKindAlias` records that resolve through
:func:`resolve_source_kind_alias` to canonical
:class:`~aeat.core.BindingSourceKind` members. No operator-specific source-kind
taxonomy is introduced here.

The CRUD vocabulary is exposed through :class:`CrudVerb`,
:data:`CANONICAL_CRUD_VERBS`, :class:`MutatingNounGroupContract`,
:class:`CrudContractCatalogue`, and :func:`get_builtin_catalogue`. Help and
landing surfaces are exposed through :func:`build_help_document`,
:func:`build_root_landing_report`, :class:`HelpDocument`, and
:class:`RootLandingReport`. Refused surfaces use the registered
:class:`OperatorSurfaceContractError` path shared with
:func:`require_accepted_root`.
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
from ._manifest import (
    CommandSchemaRef,
    OperatorSurfaceManifest,
    build_operator_surface_manifest,
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
    SourceKindAlias,
)

__all__ = [
    "ACCEPTED_ROOTS",
    "BUILTIN_CRUD_CATALOGUE",
    "CANONICAL_CRUD_VERBS",
    "MOUNTED_COMMAND_FAMILIES",
    "SOURCE_KIND_ALIASES",
    "BucketEventSuffix",
    "CommandSchemaRef",
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
    "OperatorSurfaceManifest",
    "OrthogonalAxis",
    "RootLandingReport",
    "RootSurface",
    "RootSurfaceName",
    "ServiceOwner",
    "SourceKindAlias",
    "build_help_document",
    "build_operator_surface_contract",
    "build_operator_surface_manifest",
    "build_root_landing_report",
    "event_suffix_for",
    "get_builtin_catalogue",
    "get_operator_surface_contract",
    "render_help_text",
    "render_root_landing_text",
    "require_accepted_root",
    "resolve_source_kind_alias",
]
