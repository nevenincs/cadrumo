"""Central user-profile schema contract.

The package exposes the strict Pydantic records and loader for the
schema-oriented user profile backend. The TOML file owns schema metadata;
runtime values are stored by later application/persistence waves.
"""

from __future__ import annotations

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
    ProfileFactValue,
    UserProfileFact,
    UserProfilePortableExport,
    UserProfileRecord,
    UserProfileSnapshot,
    UserProfileStatus,
    new_profile_id,
    new_profile_snapshot_id,
)

__all__ = [
    "ProfileAlreadyExistsError",
    "ProfileFactValue",
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
