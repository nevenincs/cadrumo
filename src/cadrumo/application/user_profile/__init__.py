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
:class:`ProfileCapsuleLifecycle`,
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
:mod:`entrypoints.cli.tests.test_lazy_command_tree` gate and the
producer-side probe in
:mod:`application.user_profile.tests.test_lazy_boundary` both enforce.

See Also:
    :mod:`domain.user_profile`
        Domain schema, value records, registry-selector contract, and lazy
        portable-export payload consumed by this facade.
    :class:`ProfileCapsuleLifecycle`
        Physical capsule service for registration and authenticated current-
        record publication over
        :class:`domain.user_profile.UserProfileRecord`.
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

from collections.abc import Callable
from functools import partial
from importlib import import_module
from types import ModuleType
from typing import TYPE_CHECKING

from ...core.identity import ProfileId
from ._language_resolver import register_language_resolver as _register_language_resolver

if TYPE_CHECKING:
    from ...domain.user_profile import (
        UserProfileFact,
        UserProfileFactValue,
        UserProfileRecord,
    )
    from ._bundle import (
        SUPPORTED_BUNDLE_SCHEMA_VERSIONS,
        UnsupportedBundleSchemaVersionError,
        deserialize_profile_bundle,
        register_imported_profile_bundle,
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
        cloud_evidence_upload_eligible_for_active_profile,
        resolve_active_capability,
        resolve_capability,
    )
    from ._censo_errors import (
        CensoSyncError,
    )
    from ._censo_sync import (
        CENSAL_ADOPTABLE_PATHS,
        CENSO_SOURCE_TAG,
        CensalIdentityMismatchError,
        CensalReconciliation,
        CensoSyncService,
        apply_censal_read,
        censal_facts_from_read,
        reconcile_censal_read,
    )
    from ._commands import (
        CompleteSetupCommand,
        EditProfileFieldCommand,
        EditProfileSectionCommand,
        ProfileImportResult,
        ProfileLifecycleResult,
        ProfilePreflightReport,
        ProfilePreflightRequirement,
        ProfileSnapshot,
        ProfileSnapshotRequest,
        ProfileStaleCheckReport,
        ProfileValidationIssue,
        ProfileValidationReport,
        RegisterProfileCommand,
    )
    from ._completeness import (
        conditional_profile_missing_required,
        iva_regime_required,
        missing_required_field_paths,
        profile_section_rows,
    )
    from ._cotejo_apply import (
        CENSO_CERTIFICATE_AXIS_PREFIX,
        CENSO_DIVERGENCE_NOTICE_CODE,
        CENSO_DIVERGENCE_PREFIX,
        CENSO_UNADOPTED_EVIDENCE_FIELDS,
        CensoDivergence,
        apply_cotejo,
        censo_divergence_notice,
        censo_unadopted_evidence,
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
        TYPED_CATEGORY_NAMESPACES,
        carried_namespace_definitions,
        restore_carried_objects,
        serialize_carried_objects,
    )
    from ._custody_pointer import ProfileCustodyPointerSnapshot
    from ._custody_repository import (
        ProfileCustodyTransactionRepository,
        compare_and_swap_profile_pointer,
        profile_custody_transaction_lock,
    )
    from ._custody_transactions import (
        ProfileCustodyDeleteConfirmation,
        ProfileCustodyHoldAssessment,
        ProfileCustodyHoldEvidence,
        ProfileCustodyInventoryWitness,
        ProfileCustodyTransactionConflictError,
        ProfileCustodyTransactionCorruptError,
        ProfileCustodyTransactionError,
        ProfileCustodyTransactionJournal,
        ProfileCustodyTransactionOperation,
        ProfileCustodyTransactionReceipt,
        ProfileCustodyTransactionRefusalError,
        ProfileCustodyTransactionState,
    )
    from ._filing_baseline import missing_filing_baseline_flags
    from ._keys_validation import list_profile_key_records, validate_profile_values
    from ._language_resolver import resolve_profile_output_language_hint
    from ._lifecycle import ProfileCapsuleLifecycle
    from ._login_session import (
        ProfileLoginOutcome,
        ProfileLoginThrottledError,
        close_profile_session_artefacts,
        login_profile,
        resolve_login_target,
        resume_active_profile_session,
    )
    from ._overview import (
        MASKED_PLACEHOLDER,
        ProfileFieldChoice,
        ProfileFieldView,
        ProfileOverview,
        ProfileSectionView,
        build_profile_overview,
        mask_profile_field,
        profile_field_choices,
        resolve_profile_field_label_for_path,
    )
    from ._preflight import (
        ProfilePreflightService,
        build_profile_preflight_requirement,
        format_profile_path_requirements,
        format_profile_preflight_requirement,
        format_profile_selector_requirements,
    )
    from ._profile_pointer_transaction import active_profile_pointer_transaction
    from ._profile_record_repository import (
        ProfileRecordRepository,
        activate_profile_record_session,
        bound_profile_record_session,
        close_active_profile_record_session,
        require_profile_record_session,
    )
    from ._profile_repository import CommittedProfileRepository, ProfileNotFoundError, ProfileSummary
    from ._projections import (
        EffectiveFact,
        fact_value,
        facts_to_values,
        projection_for_taxpayer,
        record_to_effective_facts,
        record_to_path_values,
        record_to_values,
        snapshot_to_values,
    )
    from ._registration import (
        PASSPHRASE_MINIMUM_LENGTH,
        PassphraseAssessment,
        ProfileRegistrationError,
        ProfileRegistrationOutcome,
        assess_passphrase,
        register_profile_with_credentials,
    )
    from ._repository import (
        USER_PROFILE_SNAPSHOT_NAMESPACE,
        UserProfileSnapshotRepository,
        user_profile_snapshot_object_key,
    )
    from ._section_rows import next_section_row_index, section_row_facts
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
        "EditProfileFieldCommand",
        "EditProfileSectionCommand",
        "ProfileImportResult",
        "ProfileLifecycleResult",
        "ProfilePreflightReport",
        "ProfilePreflightRequirement",
        "ProfileSnapshot",
        "ProfileSnapshotRequest",
        "ProfileStaleCheckReport",
        "ProfileValidationIssue",
        "ProfileValidationReport",
        "CompleteSetupCommand",
        "RegisterProfileCommand",
    },
)

_DOMAIN_RECORD_NAMES: frozenset[str] = frozenset(
    {
        "UserProfileFact",
        "UserProfileFactValue",
        "UserProfileRecord",
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
        ("._lifecycle", ("ProfileCapsuleLifecycle",)),
        ("._censo_errors", ("CensoSyncError",)),
        (
            "._censo_sync",
            (
                "CENSAL_ADOPTABLE_PATHS",
                "CENSO_SOURCE_TAG",
                "CensalIdentityMismatchError",
                "CensalReconciliation",
                "CensoSyncService",
                "apply_censal_read",
                "censal_facts_from_read",
                "reconcile_censal_read",
            ),
        ),
        (
            "._projections",
            (
                "facts_to_values",
                "fact_value",
                "projection_for_taxpayer",
                "EffectiveFact",
                "record_to_effective_facts",
                "record_to_path_values",
                "record_to_values",
                "snapshot_to_values",
            ),
        ),
        (
            "._preflight",
            (
                "ProfilePreflightService",
                "build_profile_preflight_requirement",
                "format_profile_path_requirements",
                "format_profile_path_requirements",
                "format_profile_preflight_requirement",
                "format_profile_selector_requirements",
            ),
        ),
        ("._validation", ("ProfileValidationService",)),
        (
            "._bundle",
            (
                "SUPPORTED_BUNDLE_SCHEMA_VERSIONS",
                "UnsupportedBundleSchemaVersionError",
                "deserialize_profile_bundle",
                "register_imported_profile_bundle",
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
                "CENSO_CERTIFICATE_AXIS_PREFIX",
                "CENSO_DIVERGENCE_NOTICE_CODE",
                "CENSO_DIVERGENCE_PREFIX",
                "CENSO_UNADOPTED_EVIDENCE_FIELDS",
                "CensoDivergence",
                "apply_cotejo",
                "censo_divergence_notice",
                "censo_unadopted_evidence",
                "divergence_facts",
                "open_censo_divergences",
            ),
        ),
        ("._filing_baseline", ("missing_filing_baseline_flags",)),
        (
            "._completeness",
            (
                "conditional_profile_missing_required",
                "iva_regime_required",
                "missing_required_field_paths",
                "profile_section_rows",
            ),
        ),
        ("._section_rows", ("next_section_row_index", "section_row_facts")),
        ("._keys_validation", ("list_profile_key_records", "validate_profile_values")),
        ("._language_resolver", ("resolve_profile_output_language_hint",)),
        ("._profile_pointer_transaction", ("active_profile_pointer_transaction",)),
        (
            "._custody_transactions",
            (
                "ProfileCustodyDeleteConfirmation",
                "ProfileCustodyHoldAssessment",
                "ProfileCustodyHoldEvidence",
                "ProfileCustodyInventoryWitness",
                "ProfileCustodyTransactionConflictError",
                "ProfileCustodyTransactionCorruptError",
                "ProfileCustodyTransactionError",
                "ProfileCustodyTransactionJournal",
                "ProfileCustodyTransactionOperation",
                "ProfileCustodyTransactionReceipt",
                "ProfileCustodyTransactionRefusalError",
                "ProfileCustodyTransactionState",
            ),
        ),
        (
            "._custody_pointer",
            ("ProfileCustodyPointerSnapshot",),
        ),
        (
            "._custody_repository",
            (
                "ProfileCustodyTransactionRepository",
                "compare_and_swap_profile_pointer",
                "profile_custody_transaction_lock",
            ),
        ),
        (
            "._login_session",
            (
                "ProfileLoginOutcome",
                "ProfileLoginThrottledError",
                "close_profile_session_artefacts",
                "login_profile",
                "resolve_login_target",
                "resume_active_profile_session",
            ),
        ),
        (
            "._overview",
            (
                "MASKED_PLACEHOLDER",
                "ProfileFieldChoice",
                "ProfileFieldView",
                "ProfileOverview",
                "ProfileSectionView",
                "build_profile_overview",
                "mask_profile_field",
                "profile_field_choices",
                "resolve_profile_field_label_for_path",
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
            "._profile_record_repository",
            (
                "ProfileRecordRepository",
                "activate_profile_record_session",
                "bound_profile_record_session",
                "close_active_profile_record_session",
                "require_profile_record_session",
            ),
        ),
        (
            "._repository",
            (
                "USER_PROFILE_SNAPSHOT_NAMESPACE",
                "UserProfileSnapshotRepository",
                "user_profile_snapshot_object_key",
            ),
        ),
        ("._profile_repository", ("CommittedProfileRepository", "ProfileNotFoundError", "ProfileSummary")),
        (
            "._capabilities",
            (
                "CapabilityDecision",
                "CapabilitySource",
                "cloud_evidence_upload_eligible_for_active_profile",
                "resolve_active_capability",
                "resolve_capability",
            ),
        ),
        (
            "._custody_carry",
            (
                "TYPED_CATEGORY_NAMESPACES",
                "carried_namespace_definitions",
                "restore_carried_objects",
                "serialize_carried_objects",
            ),
        ),
    )
    for name in names
}


# Each target is a closed literal from ``_LAZY_EXPORTS``.  Binding the target
# to a loader once keeps the PEP-562 boundary lazy without allowing the
# requested attribute name to become an import path.
_LAZY_MODULE_LOADERS: dict[str, Callable[[], ModuleType]] = {
    module_path: partial(import_module, module_path, __name__) for module_path in frozenset(_LAZY_EXPORTS.values())
}


def __getattr__(name: str):
    """Lazy-import every re-exported name to keep the boundary light."""
    module_path = _LAZY_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    loader = _LAZY_MODULE_LOADERS.get(module_path)
    if loader is None:
        raise RuntimeError(f"missing lazy loader for {module_path!r}")
    return getattr(loader(), name)


__all__ = [
    "CENSAL_ADOPTABLE_PATHS",
    "CENSO_CERTIFICATE_AXIS_PREFIX",
    "CENSO_DIVERGENCE_NOTICE_CODE",
    "CENSO_DIVERGENCE_PREFIX",
    "CENSO_SOURCE_TAG",
    "CENSO_UNADOPTED_EVIDENCE_FIELDS",
    "MASKED_PLACEHOLDER",
    "PASSPHRASE_MINIMUM_LENGTH",
    "SUPPORTED_BUNDLE_SCHEMA_VERSIONS",
    "TYPED_CATEGORY_NAMESPACES",
    "USER_PROFILE_SNAPSHOT_NAMESPACE",
    "CapabilityDecision",
    "CapabilitySource",
    "CensalIdentityMismatchError",
    "CensalReconciliation",
    "CensoDivergence",
    "CensoSyncError",
    "CensoSyncService",
    "CommittedProfileRepository",
    "CompleteSetupCommand",
    "CustodyPassphraseChangeResult",
    "CustodyRecoverResult",
    "CustodyRecoveryEnrollmentResult",
    "CustodyRecoveryStatus",
    "CustodyRecoveryVerification",
    "EditProfileFieldCommand",
    "EditProfileSectionCommand",
    "EffectiveFact",
    "EncryptedProfileBundleError",
    "EncryptedProfileBundleExport",
    "PassphraseAssessment",
    "PreparedProfileExport",
    "ProfileBundleExportJournalRepository",
    "ProfileBundleExportPurpose",
    "ProfileBundleExportReconcileFailure",
    "ProfileBundleExportReconciliation",
    "ProfileBundleExportRequest",
    "ProfileBundleExportResult",
    "ProfileBundleExportTarget",
    "ProfileBundleExportTransport",
    "ProfileCapsuleLifecycle",
    "ProfileCustodyDeleteConfirmation",
    "ProfileCustodyHoldAssessment",
    "ProfileCustodyHoldEvidence",
    "ProfileCustodyInventoryWitness",
    "ProfileCustodyPointerSnapshot",
    "ProfileCustodyTransactionConflictError",
    "ProfileCustodyTransactionCorruptError",
    "ProfileCustodyTransactionError",
    "ProfileCustodyTransactionJournal",
    "ProfileCustodyTransactionOperation",
    "ProfileCustodyTransactionReceipt",
    "ProfileCustodyTransactionRefusalError",
    "ProfileCustodyTransactionRepository",
    "ProfileCustodyTransactionState",
    "ProfileFieldChoice",
    "ProfileFieldView",
    "ProfileId",
    "ProfileImportResult",
    "ProfileLifecycleResult",
    "ProfileLoginOutcome",
    "ProfileLoginThrottledError",
    "ProfileNotFoundError",
    "ProfileOverview",
    "ProfilePreflightReport",
    "ProfilePreflightRequirement",
    "ProfilePreflightService",
    "ProfileRecordRepository",
    "ProfileRegistrationError",
    "ProfileRegistrationOutcome",
    "ProfileSectionView",
    "ProfileSnapshot",
    "ProfileSnapshotRequest",
    "ProfileStaleCheckReport",
    "ProfileSummary",
    "ProfileValidationIssue",
    "ProfileValidationReport",
    "ProfileValidationService",
    "RegisterProfileCommand",
    "UnsupportedBundleSchemaVersionError",
    "UserProfileFact",
    "UserProfileFactValue",
    "UserProfileRecord",
    "UserProfileSnapshotRepository",
    "activate_profile_record_session",
    "active_profile_pointer_transaction",
    "apply_censal_read",
    "apply_cotejo",
    "assess_passphrase",
    "bound_profile_record_session",
    "build_profile_overview",
    "build_profile_preflight_requirement",
    "bundle_data_categories",
    "bundle_excluded_data_categories",
    "carried_namespace_definitions",
    "censal_facts_from_read",
    "censo_divergence_notice",
    "censo_unadopted_evidence",
    "change_passphrase",
    "close_active_profile_record_session",
    "close_profile_session_artefacts",
    "cloud_evidence_upload_eligible_for_active_profile",
    "compare_and_swap_profile_pointer",
    "conditional_profile_missing_required",
    "create_recovery_code",
    "decrypt_profile_bundle_with_passphrase",
    "deserialize_profile_bundle",
    "divergence_facts",
    "encrypt_profile_bundle_for_passphrase",
    "export_profile_bundle",
    "fact_value",
    "facts_to_values",
    "format_profile_path_requirements",
    "format_profile_preflight_requirement",
    "format_profile_selector_requirements",
    "inspect_recovery_status",
    "iva_regime_required",
    "list_profile_key_records",
    "login_profile",
    "mask_profile_field",
    "missing_filing_baseline_flags",
    "missing_required_field_paths",
    "next_section_row_index",
    "open_censo_divergences",
    "prepare_profile_export",
    "profile_custody_transaction_lock",
    "profile_field_choices",
    "profile_section_rows",
    "projection_for_taxpayer",
    "publish_prepared_export",
    "reconcile_censal_read",
    "reconcile_prepared_exports",
    "record_to_effective_facts",
    "record_to_path_values",
    "record_to_values",
    "recover_secret_store",
    "recovery_wrap_path",
    "register_imported_profile_bundle",
    "register_profile_with_credentials",
    "require_profile_record_session",
    "resolve_active_capability",
    "resolve_capability",
    "resolve_login_target",
    "resolve_profile_field_label_for_path",
    "resolve_profile_output_language_hint",
    "restore_carried_objects",
    "resume_active_profile_session",
    "rotate_recovery_code",
    "section_row_facts",
    "serialize_carried_objects",
    "serialize_profile_bundle",
    "snapshot_to_values",
    "user_profile_snapshot_object_key",
    "validate_bundle_payload",
    "validate_profile_values",
    "verify_recovery_code",
]
