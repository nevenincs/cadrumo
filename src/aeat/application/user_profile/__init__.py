"""Lazy application facade for schema-driven user-profile operations.

This package is the application boundary for the centralised profile
backend. The domain layer (:mod:`aeat.domain.user_profile`) owns the
schema, value records, selector registry contract, and portable-export
payload type :class:`~aeat.domain.user_profile.UserProfilePortableExport`.
This package owns the command/result records and service entry points
that operate on that contract: lifecycle orchestration, validation and
preflight checks, Censo synchronisation, capability and custody helpers,
consumer projections, bucket-scoped storage sessions, and portable
bundle serialisation.

The records here have no business logic; they are the typed contract
passed between CLI adapters, secure-storage persistence wiring,
bucket-maintenance flows, Modelo readiness gates, workflow adapters, and
calculation/filing/aggregation consumers. The aggregate passed across
service boundaries is :class:`~aeat.domain.user_profile.UserProfileRecord`.
The service implementations live in sibling modules and are exposed as
lazy facade members, including
:class:`~aeat.application.user_profile.ProfileLifecycleService`,
:class:`~aeat.application.user_profile.UserProfileSnapshotRepository`,
:class:`~aeat.application.user_profile.ProfileValidationService`, and
:class:`~aeat.application.user_profile.ProfilePreflightService`.

Portable export composition follows the same split.
:func:`~aeat.application.user_profile.serialize_profile_bundle` and
:func:`~aeat.application.user_profile.deserialize_profile_bundle` live on
this facade so CLI config and bucket-maintenance code compose through
top-level re-exports, while the bundle payload remains the domain-layer
:class:`~aeat.domain.user_profile.UserProfilePortableExport`. Projection
and baseline helpers such as
:func:`~aeat.application.user_profile.record_to_path_values`,
:func:`~aeat.application.user_profile.projection_for_taxpayer`, and
:func:`~aeat.application.user_profile.missing_filing_baseline_flags`
provide the canonical schema-path and deadline-engine shapes consumed by
filing gates instead of recreating profile fact decoding downstream.

Every re-exported name is resolved on demand through module-level
``__getattr__`` (PEP 562). Top-level imports in this file are reserved
for genuinely lightweight setup (:class:`~aeat.core.identity.ProfileId`
and the active-profile language-resolver registration) so the boundary
itself does not drag the domain portable-export / registry / service
module surfaces into ``sys.modules``. The state-free CLI surfaces
(``aeat``, ``aeat --version``, ``aeat --help``) must not pay the
registry cost via this boundary, which the
:mod:`aeat.entrypoints.cli.test_lazy_command_tree` gate and the
producer-side probe in
:mod:`aeat.application.user_profile.test_lazy_boundary` both enforce.

See Also:
    :mod:`aeat.domain.user_profile`
        Domain schema, value records, registry-selector contract, and lazy
        portable-export payload consumed by this facade.
    :class:`~aeat.application.user_profile.ProfileLifecycleService`
        Application service for register, edit, rename, duplicate, snapshot, and
        remove operations over :class:`~aeat.domain.user_profile.UserProfileRecord`.
    :class:`~aeat.application.user_profile.CensoSyncService`
        Censo snapshot comparison and profile-fact application service.
    :mod:`aeat.application.bucket_maintenance`
        Bucket lifecycle facade that composes this package's portable-bundle
        serialiser and deserialiser for sealed export/import.
    :mod:`aeat.application.modelo`
        Filing-grade modelo workflows that consume profile preflight and
        projection helpers from this boundary.
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
    from ._filing_baseline import missing_filing_baseline_flags
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
    if name == "missing_filing_baseline_flags":
        from ._filing_baseline import missing_filing_baseline_flags

        return missing_filing_baseline_flags
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
    "missing_filing_baseline_flags",
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
