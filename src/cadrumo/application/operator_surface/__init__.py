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

Consumer-specific projections of these protocol-neutral contracts belong to
the consuming distribution, not to the base application.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._help import build_help_document, build_root_landing_report, render_help_text, render_root_landing_text
    from ._help_models import HelpDocument, HelpEntry, HelpSection, HelpSurface, RootLandingReport

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
    "ModeloCalculationRouteId",
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
    "SupportedModeloCalculationWorkflow",
    "SupportedModeloCalculationWorkflowCatalogue",
    "SurfaceExposureInventoryRow",
    "build_help_document",
    "build_operator_surface_contract",
    "build_root_landing_report",
    "build_supported_modelo_calculation_workflow_catalogue",
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

_EXPORT_MODULES = {
    **dict.fromkeys(("resolve_catalogue_action", "resolve_notice_action"), "._action_resolution"),
    **dict.fromkeys(
        (
            "ModeloCalculationRouteId",
            "SupportedModeloCalculationWorkflow",
            "SupportedModeloCalculationWorkflowCatalogue",
            "build_supported_modelo_calculation_workflow_catalogue",
        ),
        "._calculation_workflows",
    ),
    **dict.fromkeys(
        (
            "ACCEPTED_ROOTS",
            "MOUNTED_COMMAND_FAMILIES",
            "SOURCE_KIND_ALIASES",
            "build_operator_surface_contract",
            "get_operator_surface_contract",
            "require_accepted_root",
            "resolve_source_kind_alias",
        ),
        "._contract",
    ),
    **dict.fromkeys(
        (
            "CANONICAL_CRUD_VERBS",
            "BucketEventSuffix",
            "CrudContractCatalogue",
            "CrudVerb",
            "KeyValueVerb",
            "LifecycleStateVerb",
            "MutatingNounGroupContract",
            "NounGroupExceptionKind",
            "OrthogonalAxis",
            "event_suffix_for",
        ),
        "._crud_contract",
    ),
    **dict.fromkeys(("BUILTIN_CRUD_CATALOGUE", "get_builtin_catalogue"), "._crud_registry"),
    "OperatorSurfaceContractError": "._errors",
    **dict.fromkeys(
        ("build_help_document", "build_root_landing_report", "render_help_text", "render_root_landing_text"),
        "._help",
    ),
    **dict.fromkeys(("HelpDocument", "HelpEntry", "HelpSection", "HelpSurface", "RootLandingReport"), "._help_models"),
    **dict.fromkeys(
        (
            "CommandSchemaRef",
            "ExplicitExclusionInventoryRow",
            "InputSchemaInventoryRow",
            "LiveLeafInventoryRow",
            "ManifestActionResolution",
            "MountedFamilyInventoryRow",
            "OperatorSurfaceReconciliation",
            "ProfilePolicyInventoryRow",
            "ReconciledOperatorLeaf",
            "ReconciliationSurface",
            "ResolvedCatalogueAction",
            "ResolvedManifestActionProfile",
            "ResultSchemaInventoryRow",
            "SurfaceExposureInventoryRow",
            "reconcile_operator_surface_inventory",
            "resolve_action_catalogue",
            "resolve_manifest_action_profiles",
        ),
        "._manifest",
    ),
    **dict.fromkeys(
        (
            "FamilyMountState",
            "FilingStatus",
            "LifecycleContract",
            "ManifestActionProfile",
            "ModeloLifecycleStep",
            "MountedCommandDomain",
            "MountedCommandFamily",
            "OperatorMutability",
            "OperatorSurfaceContract",
            "OperatorSurfaceLogFields",
            "RootSurface",
            "RootSurfaceName",
            "ServiceOwner",
            "SourceKindAlias",
        ),
        "._models",
    ),
}


def __getattr__(name: str) -> object:
    """Resolve public contracts without importing unrelated operator domains."""
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name, __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Report eager and deferred public names."""
    return sorted(set(__all__) | set(globals()))
