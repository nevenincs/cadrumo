"""Backend-owned operator surface contract for the redesigned command tree."""

from __future__ import annotations

from ._contract import (
    ACCEPTED_ROOTS,
    RETIRED_OPERATOR_SURFACES,
    SOURCE_KIND_ALIASES,
    build_operator_surface_contract,
    get_operator_surface_contract,
    require_accepted_root,
    resolve_source_kind_alias,
    retired_surface_suggestion,
)
from ._errors import OperatorSurfaceContractError
from ._models import (
    LifecycleContract,
    ModeloLifecycleStep,
    OperatorSurfaceContract,
    OperatorSurfaceLogFields,
    RetiredOperatorSurface,
    RootSurface,
    RootSurfaceName,
    ServiceOwner,
    SourceKind,
    SourceKindAlias,
)

__all__ = [
    "ACCEPTED_ROOTS",
    "RETIRED_OPERATOR_SURFACES",
    "SOURCE_KIND_ALIASES",
    "LifecycleContract",
    "ModeloLifecycleStep",
    "OperatorSurfaceContract",
    "OperatorSurfaceContractError",
    "OperatorSurfaceLogFields",
    "RetiredOperatorSurface",
    "RootSurface",
    "RootSurfaceName",
    "ServiceOwner",
    "SourceKind",
    "SourceKindAlias",
    "build_operator_surface_contract",
    "get_operator_surface_contract",
    "require_accepted_root",
    "resolve_source_kind_alias",
    "retired_surface_suggestion",
]
