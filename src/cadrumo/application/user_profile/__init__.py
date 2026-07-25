"""Lazy application facade for schema-driven user-profile operations.

This package is the application boundary for the centralised profile
backend. The domain layer (:mod:`domain.user_profile`) owns the
schema, value records, selector registry contract, and portable-export
payload type :class:`domain.user_profile.UserProfilePortableExport`.
This package owns the command/result records and service entry points
that operate on that contract: lifecycle orchestration, validation and
preflight checks, Censo synchronisation, capability and custody helpers,
consumer projections, bucket-scoped storage sessions, and portable
bundle serialisation.

The records here have no business logic; they are the typed contract
passed between CLI adapters, secure-storage persistence wiring,
bucket-maintenance flows, Modelo readiness gates, workflow adapters, and
calculation/filing/aggregation consumers. The aggregate passed across
service boundaries is :class:`domain.user_profile.UserProfileRecord`.
The service implementations live in sibling modules and are exposed as
lazy facade members, including
:class:`ProfileLifecycleService`,
:class:`UserProfileSnapshotRepository`,
:class:`ProfileValidationService`, and
:class:`ProfilePreflightService`.

Portable export composition follows the same split.
:func:`serialize_profile_bundle` and :func:`deserialize_profile_bundle` live
on this facade so CLI config and bucket-maintenance code compose through
top-level re-exports, while the bundle payload remains the domain-layer
:class:`domain.user_profile.UserProfilePortableExport`. The current v3 bundle
is the only accepted import shape. Its default
:attr:`adapters.persistence.storage.StorageCustodyProfile.STRUCTURED` scope
carries the typed profile, work-unit, ledger, calculation, and filing categories
plus registry-selected secure-object rows. Sealed bucket backup requests
:attr:`adapters.persistence.storage.StorageCustodyProfile.FULL`,
which asserts every populated secure-object namespace has a registry
custody disposition before export. Generic carried rows use their natural
object keys rather than stored HMAC lookup digests, so import can
re-save them through the target bucket's secure-object substrate and
re-encrypt under the recipient bucket DEK.

Custody helpers exposed here are application commands over storage-owned
secret-store primitives. :func:`create_recovery_code`,
:func:`rotate_recovery_code`, :func:`verify_recovery_code`,
:func:`change_passphrase`, and :func:`recover_secret_store` resolve runtime
settings, update active-bucket
recovery metadata when needed, and return typed result records while leaving key
wrapping and recovery envelope persistence in :mod:`adapters.persistence.storage`.

Projection and baseline helpers such as
:func:`record_to_path_values`, :func:`projection_for_taxpayer`, and
:func:`missing_filing_baseline_flags` provide the canonical schema-path and
deadline-engine shapes consumed by filing gates instead of recreating profile
fact decoding downstream.

Every re-exported name is resolved on demand through module-level
``__getattr__`` (PEP 562). Top-level imports in this file are reserved
for genuinely lightweight setup (:class:`core.identity.ProfileId`
and the active-profile language-resolver registration) so the boundary
itself does not drag the domain portable-export / registry / service
module surfaces into ``sys.modules``. The state-free CLI surfaces
(``aeat``, ``aeat --version``, ``aeat --help``) must not pay the
registry cost via this boundary, which the
:mod:`entrypoints.cli.test_lazy_command_tree` gate and the
producer-side probe in
:mod:`application.user_profile.test_lazy_boundary` both enforce.

See Also:
    :mod:`domain.user_profile`
        Domain schema, value records, registry-selector contract, and lazy
        portable-export payload consumed by this facade.
    :class:`ProfileLifecycleService`
        Application service for register, edit, rename, duplicate, snapshot, and
        remove operations over :class:`domain.user_profile.UserProfileRecord`.
    :class:`CensoSyncService`
        Read-only censo-derived home-office afectación ratio for the ledger
        proportional-deduction path.
    :mod:`application.bucket_maintenance`
        Bucket lifecycle facade that composes this package's portable-bundle
        serialiser and deserialiser for sealed export/import.
    :mod:`adapters.persistence.storage`
        Secure-object repository, namespace custody registry, and master-key
        recovery primitives composed by this facade without owning storage
        policy.
    :mod:`application.modelo`
        Filing-grade modelo workflows that consume profile preflight and
        projection helpers from this boundary.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._profile_repository import TAX_ID_FACT_PATH

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
        validate_bundle_payload,
    )
    from ._bundle_encryption import (
        EncryptedProfileBundleError,
        EncryptedProfileBundleExport,
        decrypt_profile_bundle_with_passphrase,
        encrypt_profile_bundle_for_passphrase,
    )
    from ._bundle_export import (
        PreparedProfileExport,
        ProfileBundleExportPurpose,
        ProfileBundleExportReconcileFailure,
        ProfileBundleExportReconciliation,
        ProfileBundleExportRequest,
        ProfileBundleExportResult,
        ProfileBundleExportTarget,
        ProfileBundleExportTransport,
        bundle_data_categories,
        bundle_excluded_data_categories,
        export_profile_bundle,
        prepare_profile_export,
        publish_prepared_export,
        reconcile_prepared_exports,
    )
    from ._bundle_export_operation import (
        ProfileBundleExportJournalRepository,
    )
    from ._capabilities import (
        CapabilityDecision,
        CapabilitySource,
        resolve_active_capability,
        resolve_capability,
    )
    from ._censo_errors import (
        CensoSyncError,
    )
    from ._censo_sync import (
        CENSO_DERIVED_SOURCE_TAG,
        CENSO_SOURCE_TAG,
        CensoSyncService,
    )
    from ._commands import (
        CompleteSetupCommand,
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
        ReactivateProfileCommand,
        RegisterProfileCommand,
        RemoveProfileCommand,
        RenameProfileCommand,
    )
    from ._completeness import iva_regime_required
    from ._cotejo_apply import (
        CENSO_DIVERGENCE_NOTICE_CODE,
        CENSO_DIVERGENCE_PREFIX,
        CensoDivergence,
        apply_cotejo,
        censo_divergence_notice,
        divergence_facts,
        open_censo_divergences,
    )
    from ._custody import (
        CustodyPassphraseChangeResult,
        CustodyRecoverResult,
        CustodyRecoveryEnrollmentResult,
        CustodyRecoveryStatus,
        CustodyRecoveryVerification,
        change_passphrase,
        create_recovery_code,
        inspect_recovery_status,
        recover_secret_store,
        recovery_wrap_path,
        rotate_recovery_code,
        verify_recovery_code,
    )
    from ._custody_carry import (
        carried_namespace_definitions,
        restore_carried_objects,
        serialize_carried_objects,
    )
    from ._filing_baseline import missing_filing_baseline_flags
    from ._integrity import ProfileIntegrityError
    from ._keys_validation import list_profile_key_records, validate_profile_values
    from ._language_resolver import resolve_profile_output_language_hint
    from ._lifecycle import ProfileLifecycleService
    from ._login_session import (
        ProfileLoginOutcome,
        ProfileLoginThrottledError,
        close_profile_session_artefacts,
        login_profile,
        resume_active_profile_session,
    )
    from ._orchestration import (
        ProfileAlreadyRegisteredError,
        ProfileLogoutOverrideError,
        build_lifecycle_service,
        complete_setup_with_lifecycle_span,
        delete_profile_with_lifecycle_span,
        fact_value,
        logout_active_profile,
        profile_create_storage_span,
        profile_storage_session,
        reactivate_profile_with_lifecycle_span,
        refuse_duplicate_label,
        register_active_profile,
        remove_active_profile,
        remove_profile_bucket_directory,
        rename_profile,
        require_registered_label,
        select_profile,
        select_profile_with_lifecycle_span,
        set_active_field,
        set_active_fields,
    )
    from ._preflight import ProfilePreflightService
    from ._profile_pointer_transaction import active_profile_pointer_transaction
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

# An explicit register call replaces a side-effect import so the
# registration point is greppable rather than hidden behind a
# suppression-protected import. Runs after all module-level imports settle so
# the call sits in a clear initialiser slot. The resolver implementation
# defers its workflow / orchestration imports inside its body so this
# call does not trigger a heavy cascade.
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
        "CompleteSetupCommand",
        "ReactivateProfileCommand",
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


#: Re-exported name -> owning module (dotted, relative to this package, resolved
#: through :func:`importlib.import_module`). Every branch of the former PEP-562
#: ``__getattr__`` name-resolution ladder is one row here; the domain records
#: resolve through the domain package's public facade, every other row through
#: an intra-package private submodule.
_LAZY_EXPORTS: dict[str, str] = {
    name: module
    for module, names in (
        ("._commands", tuple(_COMMAND_NAMES)),
        ("...domain.user_profile", tuple(_DOMAIN_RECORD_NAMES)),
        ("._lifecycle", ("ProfileLifecycleService",)),
        ("._censo_errors", ("CensoSyncError",)),
        ("._censo_sync", ("CENSO_DERIVED_SOURCE_TAG", "CENSO_SOURCE_TAG", "CensoSyncService")),
        (
            "._projections",
            (
                "facts_to_values",
                "projection_for_taxpayer",
                "record_to_path_values",
                "record_to_values",
                "snapshot_to_values",
            ),
        ),
        ("._preflight", ("ProfilePreflightService",)),
        ("._validation", ("ProfileValidationService",)),
        (
            "._bundle",
            (
                "SUPPORTED_BUNDLE_SCHEMA_VERSIONS",
                "UnsupportedBundleSchemaVersionError",
                "deserialize_profile_bundle",
                "serialize_profile_bundle",
                "validate_bundle_payload",
            ),
        ),
        (
            "._bundle_export",
            (
                "PreparedProfileExport",
                "ProfileBundleExportPurpose",
                "ProfileBundleExportReconcileFailure",
                "ProfileBundleExportReconciliation",
                "ProfileBundleExportRequest",
                "ProfileBundleExportResult",
                "ProfileBundleExportTarget",
                "ProfileBundleExportTransport",
                "bundle_data_categories",
                "bundle_excluded_data_categories",
                "export_profile_bundle",
                "prepare_profile_export",
                "publish_prepared_export",
                "reconcile_prepared_exports",
            ),
        ),
        (
            "._bundle_export_operation",
            ("ProfileBundleExportJournalRepository",),
        ),
        (
            "._bundle_encryption",
            (
                "EncryptedProfileBundleError",
                "EncryptedProfileBundleExport",
                "decrypt_profile_bundle_with_passphrase",
                "encrypt_profile_bundle_for_passphrase",
            ),
        ),
        (
            "._custody",
            (
                "CustodyPassphraseChangeResult",
                "CustodyRecoverResult",
                "CustodyRecoveryEnrollmentResult",
                "CustodyRecoveryStatus",
                "CustodyRecoveryVerification",
                "change_passphrase",
                "create_recovery_code",
                "inspect_recovery_status",
                "recover_secret_store",
                "recovery_wrap_path",
                "rotate_recovery_code",
                "verify_recovery_code",
            ),
        ),
        (
            "._cotejo_apply",
            (
                "CENSO_DIVERGENCE_NOTICE_CODE",
                "CENSO_DIVERGENCE_PREFIX",
                "CensoDivergence",
                "apply_cotejo",
                "censo_divergence_notice",
                "divergence_facts",
                "open_censo_divergences",
            ),
        ),
        ("._filing_baseline", ("missing_filing_baseline_flags",)),
        ("._completeness", ("iva_regime_required",)),
        ("._keys_validation", ("list_profile_key_records", "validate_profile_values")),
        ("._language_resolver", ("resolve_profile_output_language_hint",)),
        ("._profile_pointer_transaction", ("active_profile_pointer_transaction",)),
        (
            "._login_session",
            (
                "ProfileLoginOutcome",
                "ProfileLoginThrottledError",
                "close_profile_session_artefacts",
                "ProfileRegistrationError",
    "ProfileRegistrationOutcome",
    "assess_passphrase",
    "login_profile",
    "register_profile_with_credentials",
                "resume_active_profile_session",
            ),
        ),
        (
            "._registration",
            (
                "PASSPHRASE_MINIMUM_LENGTH",
                "PassphraseAssessment",
                "ProfileRegistrationError",
                "ProfileRegistrationOutcome",
                "assess_passphrase",
                "register_profile_with_credentials",
            ),
        ),
        (
            "._orchestration",
            (
                "ProfileAlreadyRegisteredError",
                "ProfileLogoutOverrideError",
                "build_lifecycle_service",
                "complete_setup_with_lifecycle_span",
                "delete_profile_with_lifecycle_span",
                "fact_value",
                "logout_active_profile",
                "profile_create_storage_span",
                "profile_storage_session",
                "reactivate_profile_with_lifecycle_span",
                "refuse_duplicate_label",
                "register_active_profile",
                "remove_active_profile",
                "remove_profile_bucket_directory",
                "rename_profile",
                "require_registered_label",
                "select_profile",
                "select_profile_with_lifecycle_span",
                "set_active_field",
                "set_active_fields",
            ),
        ),
        (
            "._repository",
            (
                "USER_PROFILE_SNAPSHOT_NAMESPACE",
                "USER_PROFILE_VALUE_NAMESPACE",
                "UserProfileLifecycleRepository",
                "UserProfileSnapshotRepository",
                "user_profile_snapshot_object_key",
                "user_profile_value_object_key",
            ),
        ),
        ("._profile_repository", ("ProfileRepository", "TAX_ID_FACT_PATH")),
        (
            "._capabilities",
            ("CapabilityDecision", "CapabilitySource", "resolve_active_capability", "resolve_capability"),
        ),
        ("._integrity", ("ProfileIntegrityError",)),
        (
            "._custody_carry",
            ("carried_namespace_definitions", "restore_carried_objects", "serialize_carried_objects"),
        ),
    )
    for name in names
}


def __getattr__(name: str):
    """Lazy-import every re-exported name to keep the boundary light."""
    module_path = _LAZY_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(importlib.import_module(module_path, __name__), name)


__all__ = [
    "CENSO_DERIVED_SOURCE_TAG",
    "CENSO_DIVERGENCE_NOTICE_CODE",
    "CENSO_DIVERGENCE_PREFIX",
    "CENSO_SOURCE_TAG",
    "SUPPORTED_BUNDLE_SCHEMA_VERSIONS",
    "TAX_ID_FACT_PATH",
    "USER_PROFILE_SNAPSHOT_NAMESPACE",
    "USER_PROFILE_VALUE_NAMESPACE",
    "CapabilityDecision",
    "CapabilitySource",
    "CensoDivergence",
    "CensoSyncError",
    "CensoSyncService",
    "CompleteSetupCommand",
    "CustodyPassphraseChangeResult",
    "CustodyRecoverResult",
    "CustodyRecoveryEnrollmentResult",
    "CustodyRecoveryStatus",
    "CustodyRecoveryVerification",
    "DuplicateProfileCommand",
    "EditProfileFieldCommand",
    "EditProfileSectionCommand",
    "EncryptedProfileBundleError",
    "EncryptedProfileBundleExport",
    "PreparedProfileExport",
    "ProfileAlreadyRegisteredError",
    "ProfileBundleExportJournalRepository",
    "ProfileBundleExportPurpose",
    "ProfileBundleExportReconcileFailure",
    "ProfileBundleExportReconciliation",
    "ProfileBundleExportRequest",
    "ProfileBundleExportResult",
    "ProfileBundleExportTarget",
    "ProfileBundleExportTransport",
    "ProfileId",
    "ProfileImportResult",
    "ProfileIntegrityError",
    "ProfileLifecycleResult",
    "ProfileLifecycleService",
    "ProfileListResult",
    "ProfileListing",
    "ProfileLoginOutcome",
    "ProfileLoginThrottledError",
    "ProfileLogoutOverrideError",
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
    "ReactivateProfileCommand",
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
    "active_profile_pointer_transaction",
    "apply_cotejo",
    "build_lifecycle_service",
    "bundle_data_categories",
    "bundle_excluded_data_categories",
    "carried_namespace_definitions",
    "censo_divergence_notice",
    "change_passphrase",
    "close_profile_session_artefacts",
    "complete_setup_with_lifecycle_span",
    "create_recovery_code",
    "decrypt_profile_bundle_with_passphrase",
    "delete_profile_with_lifecycle_span",
    "deserialize_profile_bundle",
    "divergence_facts",
    "encrypt_profile_bundle_for_passphrase",
    "export_profile_bundle",
    "fact_value",
    "facts_to_values",
    "inspect_recovery_status",
    "iva_regime_required",
    "list_profile_key_records",
    "login_profile",
    "logout_active_profile",
    "missing_filing_baseline_flags",
    "open_censo_divergences",
    "prepare_profile_export",
    "profile_create_storage_span",
    "profile_storage_session",
    "projection_for_taxpayer",
    "publish_prepared_export",
    "reactivate_profile_with_lifecycle_span",
    "reconcile_prepared_exports",
    "record_to_path_values",
    "record_to_values",
    "recover_secret_store",
    "recovery_wrap_path",
    "refuse_duplicate_label",
    "register_active_profile",
    "remove_active_profile",
    "remove_profile_bucket_directory",
    "rename_profile",
    "require_registered_label",
    "resolve_active_capability",
    "resolve_capability",
    "resolve_profile_output_language_hint",
    "restore_carried_objects",
    "resume_active_profile_session",
    "rotate_recovery_code",
    "select_profile",
    "select_profile_with_lifecycle_span",
    "serialize_carried_objects",
    "serialize_profile_bundle",
    "set_active_field",
    "set_active_fields",
    "snapshot_to_values",
    "user_profile_snapshot_object_key",
    "user_profile_value_object_key",
    "validate_bundle_payload",
    "validate_profile_values",
    "verify_recovery_code",
]
