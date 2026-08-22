"""Public re-export boundary for the backend-owned operator surface.

The package collects the application-layer command-shape declarations from
:mod:`application.operator_surface._contract`,
:mod:`application.operator_surface._models`,
:mod:`application.operator_surface._help`,
:mod:`application.operator_surface._crud_contract`,
:mod:`application.operator_surface._crud_registry`, and
:mod:`application.operator_surface._errors`. Command adapters consume this
surface as data and render it; they do not define a second contract.

Root-surface declarations flow through :func:`get_operator_surface_contract`,
:data:`ACCEPTED_ROOTS`, :data:`MOUNTED_COMMAND_FAMILIES`, and
:class:`OperatorSurfaceContract`. Source-kind aliases remain parser-only
:class:`SourceKindAlias` records that resolve through
:func:`resolve_source_kind_alias` to canonical
:class:`core.BindingSourceKind` members. No operator-specific source-kind
taxonomy is introduced here.

The CRUD vocabulary is exposed through :class:`CrudVerb`,
:data:`CANONICAL_CRUD_VERBS`, :class:`MutatingNounGroupContract`,
:class:`CrudContractCatalogue`, and :func:`get_builtin_catalogue`. Help and
landing surfaces are exposed through :func:`build_help_document`,
:func:`build_root_landing_report`, :class:`HelpDocument`, and
:class:`RootLandingReport`. Refused surfaces use the registered
:class:`OperatorSurfaceContractError` path shared with
:func:`require_accepted_root`.

The agent-facing capability manifest is assembled by
:func:`build_operator_surface_manifest` from the cached
:class:`OperatorSurfaceContract` plus CLI-owned JSON schema references. The
application layer owns the command contract and mutability taxonomy; entrypoint
adapters own rendering, command-tree traversal, and schema-registry enumeration.

See Also:
    ``cadrumo_harness.mcp``
        Tool-exposure entrypoint that consumes the same manifest without
        duplicating the operator-surface contract.
    :mod:`core.json_contract`
        CLI result-schema registry supplied to the manifest by entrypoint
        adapters.
"""

from __future__ import annotations

from ._action_resolution import (
    resolve_catalogue_action,
    resolve_notice_action,
)
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
    ExplicitExclusionInventoryRow,
    InputSchemaInventoryRow,
    LiveLeafInventoryRow,
    ManifestActionResolution,
    MountedFamilyInventoryRow,
    OperatorSurfaceManifest,
    OperatorSurfaceReconciliation,
    ProfilePolicyInventoryRow,
    ReconciledOperatorLeaf,
    ReconciliationSurface,
    ResolvedCatalogueAction,
    ResolvedManifestActionProfile,
    ResultSchemaInventoryRow,
    SurfaceExposureInventoryRow,
    build_operator_surface_manifest,
    reconcile_operator_surface_inventory,
    resolve_action_catalogue,
    resolve_manifest_action_profiles,
)
from ._models import (
    FamilyMountState,
    FilingStatus,
    HelpDocument,
    HelpEntry,
    HelpSection,
    HelpSurface,
    LifecycleContract,
    ManifestActionProfile,
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
    "ExplicitExclusionInventoryRow",
    "FamilyMountState",
    "FilingStatus",
    "HelpDocument",
    "HelpEntry",
    "HelpSection",
    "HelpSurface",
    "InputSchemaInventoryRow",
    "KeyValueVerb",
    "LifecycleContract",
    "LifecycleStateVerb",
    "LiveLeafInventoryRow",
    "ManifestActionProfile",
    "ManifestActionResolution",
    "ModeloLifecycleStep",
    "MountedCommandDomain",
    "MountedCommandFamily",
    "MountedFamilyInventoryRow",
    "MutatingNounGroupContract",
    "NounGroupExceptionKind",
    "OperatorMutability",
    "OperatorSurfaceContract",
    "OperatorSurfaceContractError",
    "OperatorSurfaceLogFields",
    "OperatorSurfaceManifest",
    "OperatorSurfaceReconciliation",
    "OrthogonalAxis",
    "ProfilePolicyInventoryRow",
    "ReconciledOperatorLeaf",
    "ReconciliationSurface",
    "ResolvedCatalogueAction",
    "ResolvedManifestActionProfile",
    "ResultSchemaInventoryRow",
    "RootLandingReport",
    "RootSurface",
    "RootSurfaceName",
    "ServiceOwner",
    "SourceKindAlias",
    "SurfaceExposureInventoryRow",
    "build_help_document",
    "build_operator_surface_contract",
    "build_operator_surface_manifest",
    "build_root_landing_report",
    "event_suffix_for",
    "get_builtin_catalogue",
    "get_operator_surface_contract",
    "reconcile_operator_surface_inventory",
    "render_help_text",
    "render_root_landing_text",
    "require_accepted_root",
    "resolve_action_catalogue",
    "resolve_catalogue_action",
    "resolve_manifest_action_profiles",
    "resolve_notice_action",
    "resolve_source_kind_alias",
]
