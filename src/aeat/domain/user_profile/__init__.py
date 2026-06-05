"""Central user-profile schema contract.

The package exposes the strict Pydantic records and loader for the
schema-oriented user profile backend. The primary runtime record is
:class:`UserProfileRecord`. The TOML file owns schema metadata;
runtime values are stored by the persistence layer.

The :class:`UserProfilePortableExport` re-export is resolved on demand
through a module-level ``__getattr__`` (PEP 562). The portable-export
bundle composes four heavy domain types (:class:`CalculationRevision`,
``WorkUnit``, ``Transaction``, :class:`ModeloRecord`) whose imports
cascade into the calculation registry; eagerly re-exporting it at this
boundary would drag the full ~69-submodule registry into every
consumer that touches the package surface, including the state-free
CLI surfaces enforced by
:mod:`aeat.entrypoints.cli.test_lazy_command_tree`. Every other
re-export (errors, value records, schema records, loader,
registry-contract) stays eager because each is genuinely lightweight
and every consumer pays for it unconditionally.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._errors import (
    ProfileAlreadyExistsError,
    ProfileNotFoundError,
    ProfilePreflightMissingError,
    ProfileSchemaValidationError,
    ProfileSnapshotHashMismatchError,
    ProfileSnapshotNotFoundError,
    StoredProfileDriftError,
    UserProfileSchemaLoadError,
)
from ._loader import load_user_profile_schema
from ._registry_contract import (
    UserProfileRegistryContractIssue,
    UserProfileRegistryContractReport,
    UserProfileRegistryContractSeverity,
    UserProfileSelectorIndex,
    build_user_profile_selector_index,
    profile_binding_selectors,
    validate_user_profile_registry_contract,
)
from ._schema import (
    ProfileFieldDefinition,
    ProfileFieldType,
    ProfileRemovePolicy,
    ProfileSchemaDefinition,
    ProfileSectionDefinition,
    ProfileSnapshotPolicy,
)
from ._values import (
    UserProfileFact,
    UserProfileFactValue,
    UserProfileRecord,
    UserProfileSnapshot,
    UserProfileStatus,
    new_profile_id,
    new_profile_snapshot_id,
)

if TYPE_CHECKING:
    from ._portable_export import UserProfilePortableExport


def __getattr__(name: str):
    """Resolve heavy re-exports on demand to keep the boundary lazy.

    The portable-export bundle's domain-type composition cascades into
    the calculation registry; routing the symbol through ``__getattr__``
    defers that cost to first-use rather than module-import.
    """
    if name == "UserProfilePortableExport":
        from ._portable_export import UserProfilePortableExport

        globals()[name] = UserProfilePortableExport
        return UserProfilePortableExport
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ProfileAlreadyExistsError",
    "ProfileFieldDefinition",
    "ProfileFieldType",
    "ProfileNotFoundError",
    "ProfilePreflightMissingError",
    "ProfileRemovePolicy",
    "ProfileSchemaDefinition",
    "ProfileSchemaValidationError",
    "ProfileSectionDefinition",
    "ProfileSnapshotHashMismatchError",
    "ProfileSnapshotNotFoundError",
    "ProfileSnapshotPolicy",
    "StoredProfileDriftError",
    "UserProfileFact",
    "UserProfileFactValue",
    "UserProfilePortableExport",
    "UserProfileRecord",
    "UserProfileRegistryContractIssue",
    "UserProfileRegistryContractReport",
    "UserProfileRegistryContractSeverity",
    "UserProfileSchemaLoadError",
    "UserProfileSelectorIndex",
    "UserProfileSnapshot",
    "UserProfileStatus",
    "build_user_profile_selector_index",
    "load_user_profile_schema",
    "new_profile_id",
    "new_profile_snapshot_id",
    "profile_binding_selectors",
    "validate_user_profile_registry_contract",
]
