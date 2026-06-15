"""Application-layer command and result contracts for the user profile backend.

This package owns the lifecycle API contracts for the centralised
schema-driven profile backend. The domain layer
(``aeat.domain.user_profile``) owns the schema, value records, and
registry-contract validation; this package owns the application-layer
service surface: strict Pydantic command and result records that flow
between the CLI thin adapters, the secure-storage persistence wiring,
and the calculation/filing/aggregation consumers.

The records here have no business logic — they are the typed contract.
The service implementations live in sibling modules
(``ProfileLifecycleService``, ``ProfileSnapshotService``,
``ProfileValidationService``, ``ProfilePreflightService``) and the
secure-storage adapters that consume these records. The aggregate passed
across service boundaries is :class:`UserProfileRecord`.

Every re-exported name is resolved on demand through module-level
``__getattr__`` (PEP 562). Top-level imports in this file are reserved
for genuinely lightweight setup (the active-profile language-resolver
registration) so the boundary itself does not drag the domain-record /
registry / service module surfaces into ``sys.modules``. The
state-free CLI surfaces (``aeat``, ``aeat --version``, ``aeat --help``)
must not pay the registry cost via this boundary, which the
:mod:`aeat.entrypoints.cli.test_lazy_command_tree` gate and the
producer-side probe in
:mod:`aeat.application.user_profile.test_lazy_boundary` both enforce.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.identity import ProfileId
from ._language_resolver import register_language_resolver as _register_language_resolver

if TYPE_CHECKING:
    from ...domain.user_profile import (
        UserProfileFact,
        UserProfileFactValue,
        UserProfileRecord,
        UserProfileStatus,
    )
    from ._bundle import (
        SUPPORTED_BUNDLE_SCHEMA_VERSIONS,
        UnsupportedBundleSchemaVersionError,
        deserialize_profile_bundle,
        serialize_profile_bundle,
    )
    from ._capabilities import (
        CapabilityDecision,
        CapabilitySource,
        resolve_active_capability,
        resolve_capability,
    )
    from ._censo_errors import (
        CensoApplyConflictError,
        CensoFieldValidationError,
        CensoNotAvailableError,
        CensoSyncError,
    )
    from ._censo_sync import (
        CENSO_DERIVED_SOURCE_TAG,
        CENSO_SOURCE_TAG,
        CensoApplyResult,
        CensoComparisonStatus,
        CensoFactSource,
        CensoFieldComparison,
        CensoProfileComparison,
        CensoSyncService,
    )
    from ._commands import (
        DuplicateProfileCommand,
        EditProfileFieldCommand,
        EditProfileSectionCommand,
        ProfileImportResult,
        ProfileLifecycleResult,
        ProfileListing,
        ProfileListResult,
        ProfilePreflightReport,
        ProfilePreflightRequirement,
        ProfileSnapshot,
        ProfileSnapshotRequest,
        ProfileStaleCheckReport,
        ProfileValidationIssue,
        ProfileValidationReport,
        RegisterProfileCommand,
        RemoveProfileCommand,
        RenameProfileCommand,
    )
    from ._custody import (
        CustodyRecoverResult,
        CustodyRecoveryEnrollment,
        CustodyRecoveryStatus,
        CustodyRecoveryVerification,
        CustodyRekeyResult,
        inspect_recovery_status,
        mint_recovery_code,
        recover_secret_store,
        recovery_wrap_path,
        rekey_secret_store,
        verify_recovery_code,
    )
    from ._lifecycle import ProfileLifecycleService
    from ._orchestration import (
        ProfileAlreadyRegisteredError,
        build_lifecycle_service,
        delete_profile_with_lifecycle_span,
        fact_value,
        logout_active_profile,
        profile_create_storage_span,
        profile_storage_session,
        read_active_profile,
        register_active_profile,
        remove_active_profile,
        remove_profile_bucket_directory,
        rename_profile,
        select_profile,
        select_profile_with_lifecycle_span,
        set_active_field,
        set_active_fields,
    )
    from ._preflight import ProfilePreflightService
    from ._profile_repository import ProfileRepository
    from ._projections import (
        facts_to_values,
        projection_for_taxpayer,
        record_to_path_values,
        record_to_values,
        snapshot_to_values,
    )
    from ._repository import (
        USER_PROFILE_SNAPSHOT_NAMESPACE,
        USER_PROFILE_VALUE_NAMESPACE,
        UserProfileLifecycleRepository,
        UserProfileSnapshotRepository,
        user_profile_snapshot_object_key,
        user_profile_value_object_key,
    )
    from ._validation import ProfileValidationService

# W09.P43.S166: replace the prior side-effect import with an explicit
# register call so the registration point is greppable rather than
# hidden behind a noqa-protected import. Runs after all module-level
# imports settle so the call sits in a clear initialiser slot. The
# resolver implementation defers its workflow / orchestration imports
# inside its body so this call does not trigger a heavy cascade.
_register_language_resolver()


_COMMAND_NAMES: frozenset[str] = frozenset(
    {
        "DuplicateProfileCommand",
        "EditProfileFieldCommand",
        "EditProfileSectionCommand",
        "ProfileImportResult",
        "ProfileLifecycleResult",
        "ProfileListResult",
        "ProfileListing",
        "ProfilePreflightReport",
        "ProfilePreflightRequirement",
        "ProfileSnapshot",
        "ProfileSnapshotRequest",
        "ProfileStaleCheckReport",
        "ProfileValidationIssue",
        "ProfileValidationReport",
        "RegisterProfileCommand",
        "RemoveProfileCommand",
        "RenameProfileCommand",
    },
)

_DOMAIN_RECORD_NAMES: frozenset[str] = frozenset(
    {
        "UserProfileFact",
        "UserProfileFactValue",
        "UserProfileRecord",
        "UserProfileStatus",
    },
)


def __getattr__(name: str):
    """Lazy-import every re-exported name to keep the boundary light."""
    if name in _COMMAND_NAMES:
        from . import _commands

        return getattr(_commands, name)
    if name in _DOMAIN_RECORD_NAMES:
        from ...domain import user_profile as _domain_user_profile

        return getattr(_domain_user_profile, name)
    if name == "ProfileLifecycleService":
        from ._lifecycle import ProfileLifecycleService

        return ProfileLifecycleService
    if name in (
        "CensoApplyConflictError",
        "CensoFieldValidationError",
        "CensoNotAvailableError",
        "CensoSyncError",
    ):
        from . import _censo_errors

        return getattr(_censo_errors, name)
    if name in (
        "CENSO_DERIVED_SOURCE_TAG",
        "CENSO_SOURCE_TAG",
        "CensoApplyResult",
        "CensoComparisonStatus",
        "CensoFactSource",
        "CensoFieldComparison",
        "CensoProfileComparison",
        "CensoSyncService",
    ):
        from . import _censo_sync

        return getattr(_censo_sync, name)
    if name in (
        "facts_to_values",
        "projection_for_taxpayer",
        "record_to_path_values",
        "record_to_values",
        "snapshot_to_values",
    ):
        from . import _projections

        return getattr(_projections, name)
    if name == "ProfilePreflightService":
        from ._preflight import ProfilePreflightService

        return ProfilePreflightService
    if name == "ProfileValidationService":
        from ._validation import ProfileValidationService

        return ProfileValidationService
    if name in (
        "SUPPORTED_BUNDLE_SCHEMA_VERSIONS",
        "UnsupportedBundleSchemaVersionError",
        "deserialize_profile_bundle",
        "serialize_profile_bundle",
    ):
        from . import _bundle

        return getattr(_bundle, name)
    if name in (
        "CustodyRecoverResult",
        "CustodyRecoveryEnrollment",
        "CustodyRecoveryStatus",
        "CustodyRecoveryVerification",
        "CustodyRekeyResult",
        "inspect_recovery_status",
        "mint_recovery_code",
        "recover_secret_store",
        "recovery_wrap_path",
        "rekey_secret_store",
        "verify_recovery_code",
    ):
        from . import _custody

        return getattr(_custody, name)
    if name in (
        "ProfileAlreadyRegisteredError",
        "build_lifecycle_service",
        "delete_profile_with_lifecycle_span",
        "fact_value",
        "logout_active_profile",
        "profile_create_storage_span",
        "profile_storage_session",
        "read_active_profile",
        "register_active_profile",
        "remove_active_profile",
        "remove_profile_bucket_directory",
        "rename_profile",
        "select_profile",
        "select_profile_with_lifecycle_span",
        "set_active_field",
        "set_active_fields",
    ):
        from . import _orchestration

        return getattr(_orchestration, name)
    if name in (
        "USER_PROFILE_SNAPSHOT_NAMESPACE",
        "USER_PROFILE_VALUE_NAMESPACE",
        "UserProfileLifecycleRepository",
        "UserProfileSnapshotRepository",
        "user_profile_snapshot_object_key",
        "user_profile_value_object_key",
    ):
        from . import _repository

        return getattr(_repository, name)
    if name == "ProfileRepository":
        from ._profile_repository import ProfileRepository

        return ProfileRepository
    if name in (
        "CapabilityDecision",
        "CapabilitySource",
        "resolve_active_capability",
        "resolve_capability",
    ):
        from . import _capabilities

        return getattr(_capabilities, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "CENSO_DERIVED_SOURCE_TAG",
    "CENSO_SOURCE_TAG",
    "SUPPORTED_BUNDLE_SCHEMA_VERSIONS",
    "USER_PROFILE_SNAPSHOT_NAMESPACE",
    "USER_PROFILE_VALUE_NAMESPACE",
    "CapabilityDecision",
    "CapabilitySource",
    "CensoApplyConflictError",
    "CensoApplyResult",
    "CensoComparisonStatus",
    "CensoFactSource",
    "CensoFieldComparison",
    "CensoFieldValidationError",
    "CensoNotAvailableError",
    "CensoProfileComparison",
    "CensoSyncError",
    "CensoSyncService",
    "CustodyRecoverResult",
    "CustodyRecoveryEnrollment",
    "CustodyRecoveryStatus",
    "CustodyRecoveryVerification",
    "CustodyRekeyResult",
    "DuplicateProfileCommand",
    "EditProfileFieldCommand",
    "EditProfileSectionCommand",
    "ProfileAlreadyRegisteredError",
    "ProfileId",
    "ProfileImportResult",
    "ProfileLifecycleResult",
    "ProfileLifecycleService",
    "ProfileListResult",
    "ProfileListing",
    "ProfilePreflightReport",
    "ProfilePreflightRequirement",
    "ProfilePreflightService",
    "ProfileRepository",
    "ProfileSnapshot",
    "ProfileSnapshotRequest",
    "ProfileStaleCheckReport",
    "ProfileValidationIssue",
    "ProfileValidationReport",
    "ProfileValidationService",
    "RegisterProfileCommand",
    "RemoveProfileCommand",
    "RenameProfileCommand",
    "UnsupportedBundleSchemaVersionError",
    "UserProfileFact",
    "UserProfileFactValue",
    "UserProfileLifecycleRepository",
    "UserProfileRecord",
    "UserProfileSnapshotRepository",
    "UserProfileStatus",
    "build_lifecycle_service",
    "delete_profile_with_lifecycle_span",
    "deserialize_profile_bundle",
    "fact_value",
    "facts_to_values",
    "inspect_recovery_status",
    "logout_active_profile",
    "mint_recovery_code",
    "profile_create_storage_span",
    "profile_storage_session",
    "projection_for_taxpayer",
    "read_active_profile",
    "record_to_path_values",
    "record_to_values",
    "recover_secret_store",
    "recovery_wrap_path",
    "register_active_profile",
    "rekey_secret_store",
    "remove_active_profile",
    "remove_profile_bucket_directory",
    "rename_profile",
    "resolve_active_capability",
    "resolve_capability",
    "select_profile",
    "select_profile_with_lifecycle_span",
    "serialize_profile_bundle",
    "set_active_field",
    "set_active_fields",
    "snapshot_to_values",
    "user_profile_snapshot_object_key",
    "user_profile_value_object_key",
    "verify_recovery_code",
]
