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
        UserProfileFact as UserProfileFact,
    )
    from ...domain.user_profile import (
        UserProfileFactValue as UserProfileFactValue,
    )
    from ...domain.user_profile import (
        UserProfileRecord as UserProfileRecord,
    )
    from ._aggregate import (
        CommittedProfileView as CommittedProfileView,
    )
    from ._aggregate import (
        ProfileRestoreAuthority as ProfileRestoreAuthority,
    )
    from ._authentication import (
        ProfileAuthenticationRefusedError as ProfileAuthenticationRefusedError,
    )
    from ._authentication import (
        ProfilePasswordProofOperation as ProfilePasswordProofOperation,
    )
    from ._bundle import (
        SUPPORTED_BUNDLE_SCHEMA_VERSIONS as SUPPORTED_BUNDLE_SCHEMA_VERSIONS,
    )
    from ._bundle import (
        UnsupportedBundleSchemaVersionError as UnsupportedBundleSchemaVersionError,
    )
    from ._bundle import (
        deserialize_profile_bundle as deserialize_profile_bundle,
    )
    from ._bundle import (
        register_imported_profile_bundle as register_imported_profile_bundle,
    )
    from ._bundle import (
        serialize_profile_bundle as serialize_profile_bundle,
    )
    from ._bundle import (
        validate_bundle_payload as validate_bundle_payload,
    )
    from ._bundle_encryption import (
        EncryptedProfileBundleError as EncryptedProfileBundleError,
    )
    from ._bundle_encryption import (
        EncryptedProfileBundleExport as EncryptedProfileBundleExport,
    )
    from ._bundle_encryption import (
        decrypt_profile_bundle_with_passphrase as decrypt_profile_bundle_with_passphrase,
    )
    from ._bundle_encryption import (
        encrypt_profile_bundle_for_passphrase as encrypt_profile_bundle_for_passphrase,
    )
    from ._bundle_export import (
        PreparedProfileExport as PreparedProfileExport,
    )
    from ._bundle_export import (
        ProfileBundleExportPurpose as ProfileBundleExportPurpose,
    )
    from ._bundle_export import (
        ProfileBundleExportReconcileFailure as ProfileBundleExportReconcileFailure,
    )
    from ._bundle_export import (
        ProfileBundleExportReconciliation as ProfileBundleExportReconciliation,
    )
    from ._bundle_export import (
        ProfileBundleExportRequest as ProfileBundleExportRequest,
    )
    from ._bundle_export import (
        ProfileBundleExportResult as ProfileBundleExportResult,
    )
    from ._bundle_export import (
        ProfileBundleExportTarget as ProfileBundleExportTarget,
    )
    from ._bundle_export import (
        ProfileBundleExportTransport as ProfileBundleExportTransport,
    )
    from ._bundle_export import (
        bundle_data_categories as bundle_data_categories,
    )
    from ._bundle_export import (
        bundle_excluded_data_categories as bundle_excluded_data_categories,
    )
    from ._bundle_export import (
        export_profile_bundle as export_profile_bundle,
    )
    from ._bundle_export import (
        prepare_profile_export as prepare_profile_export,
    )
    from ._bundle_export import (
        publish_prepared_export as publish_prepared_export,
    )
    from ._bundle_export import (
        reconcile_prepared_exports as reconcile_prepared_exports,
    )
    from ._bundle_export_operation import (
        ProfileBundleExportJournalRepository as ProfileBundleExportJournalRepository,
    )
    from ._capabilities import (
        CapabilityDecision as CapabilityDecision,
    )
    from ._capabilities import (
        CapabilitySource as CapabilitySource,
    )
    from ._capabilities import (
        cloud_evidence_upload_eligible_for_active_profile as cloud_evidence_upload_eligible_for_active_profile,
    )
    from ._capabilities import (
        resolve_active_capability as resolve_active_capability,
    )
    from ._capabilities import (
        resolve_capability as resolve_capability,
    )
    from ._capsule_archive import (
        ProfileCapsuleArchiveError as ProfileCapsuleArchiveError,
    )
    from ._capsule_archive import (
        ProfileCapsuleArchiveInspection as ProfileCapsuleArchiveInspection,
    )
    from ._capsule_archive import (
        ProfileCapsuleArchiveReceipt as ProfileCapsuleArchiveReceipt,
    )
    from ._capsule_archive import (
        export_profile_capsule_archive as export_profile_capsule_archive,
    )
    from ._capsule_archive import (
        inspect_profile_capsule_archive as inspect_profile_capsule_archive,
    )
    from ._capsule_archive import (
        read_profile_capsule_archive as read_profile_capsule_archive,
    )
    from ._capsule_record import (
        ProfileRecordIntegrityError as ProfileRecordIntegrityError,
    )
    from ._capsule_record import (
        ProfileRecordSession as ProfileRecordSession,
    )
    from ._capsule_restore import (
        ProfileCapsuleSource as ProfileCapsuleSource,
    )
    from ._capsule_restore import (
        ProfileCapsuleSourceError as ProfileCapsuleSourceError,
    )
    from ._capsule_restore import (
        ProfileRestoreOutcome as ProfileRestoreOutcome,
    )
    from ._capsule_restore import (
        read_profile_capsule_source as read_profile_capsule_source,
    )
    from ._capsule_restore import (
        restore_profile_capsule_with_password as restore_profile_capsule_with_password,
    )
    from ._capsule_restore import (
        restore_profile_capsule_with_recovery_artifact as restore_profile_capsule_with_recovery_artifact,
    )
    from ._capsule_restore import (
        restore_profile_from_source_with_password as restore_profile_from_source_with_password,
    )
    from ._capsule_restore import (
        restore_profile_from_source_with_recovery_artifact as restore_profile_from_source_with_recovery_artifact,
    )
    from ._censal_observation import (
        CensalObservation as CensalObservation,
    )
    from ._censal_observation import (
        CensalObservationAddress as CensalObservationAddress,
    )
    from ._censal_observation import (
        CensalObservationIdentity as CensalObservationIdentity,
    )
    from ._censal_operation import (
        CENSAL_OPERATION_DEFINITION as CENSAL_OPERATION_DEFINITION,
    )
    from ._censal_operation import (
        CENSAL_OPERATION_DEFINITION_ID as CENSAL_OPERATION_DEFINITION_ID,
    )
    from ._censal_operation import (
        CENSAL_REVIEW_RESPONSE_SCHEMA_BINDING as CENSAL_REVIEW_RESPONSE_SCHEMA_BINDING,
    )
    from ._censal_operation import (
        CensalFieldIntent as CensalFieldIntent,
    )
    from ._censal_operation import (
        CensalOperationAcquisition as CensalOperationAcquisition,
    )
    from ._censal_operation import (
        CensalOperationOutcome as CensalOperationOutcome,
    )
    from ._censal_operation import (
        CensalOperationRequest as CensalOperationRequest,
    )
    from ._censal_operation import (
        CensalOperationResult as CensalOperationResult,
    )
    from ._censal_operation import (
        CensalProfileBaseline as CensalProfileBaseline,
    )
    from ._censal_operation import (
        CensalReviewedFieldIntent as CensalReviewedFieldIntent,
    )
    from ._censal_operation import CensalReviewResponse as CensalReviewResponse
    from ._censal_operation import build_censal_operation_definition as build_censal_operation_definition
    from ._censo_errors import (
        CensoSyncError as CensoSyncError,
    )
    from ._censo_sync import (
        CENSAL_ADOPTABLE_PATHS as CENSAL_ADOPTABLE_PATHS,
    )
    from ._censo_sync import (
        CENSO_SOURCE_TAG as CENSO_SOURCE_TAG,
    )
    from ._censo_sync import (
        CensalIdentityMismatchError as CensalIdentityMismatchError,
    )
    from ._censo_sync import (
        CensalReconciliation as CensalReconciliation,
    )
    from ._censo_sync import (
        CensoSyncService as CensoSyncService,
    )
    from ._censo_sync import (
        apply_censal_read as apply_censal_read,
    )
    from ._censo_sync import (
        censal_facts_from_read as censal_facts_from_read,
    )
    from ._censo_sync import (
        reconcile_censal_read as reconcile_censal_read,
    )
    from ._commands import (
        ProfileImportResult as ProfileImportResult,
    )
    from ._commands import (
        ProfilePreflightReport as ProfilePreflightReport,
    )
    from ._commands import (
        ProfilePreflightRequirement as ProfilePreflightRequirement,
    )
    from ._commands import (
        ProfileSnapshot as ProfileSnapshot,
    )
    from ._commands import (
        ProfileStaleCheckReport as ProfileStaleCheckReport,
    )
    from ._commands import (
        ProfileValidationIssue as ProfileValidationIssue,
    )
    from ._commands import (
        ProfileValidationReport as ProfileValidationReport,
    )
    from ._completeness import (
        conditional_profile_missing_required as conditional_profile_missing_required,
    )
    from ._completeness import (
        iva_regime_required as iva_regime_required,
    )
    from ._completeness import (
        missing_required_field_paths as missing_required_field_paths,
    )
    from ._completeness import (
        profile_section_rows as profile_section_rows,
    )
    from ._cotejo_apply import (
        CENSO_CERTIFICATE_AXIS_PREFIX as CENSO_CERTIFICATE_AXIS_PREFIX,
    )
    from ._cotejo_apply import (
        CENSO_DIVERGENCE_NOTICE_CODE as CENSO_DIVERGENCE_NOTICE_CODE,
    )
    from ._cotejo_apply import (
        CENSO_DIVERGENCE_PREFIX as CENSO_DIVERGENCE_PREFIX,
    )
    from ._cotejo_apply import (
        CENSO_UNADOPTED_EVIDENCE_FIELDS as CENSO_UNADOPTED_EVIDENCE_FIELDS,
    )
    from ._cotejo_apply import (
        CensoDivergence as CensoDivergence,
    )
    from ._cotejo_apply import (
        apply_cotejo as apply_cotejo,
    )
    from ._cotejo_apply import (
        censo_divergence_notice as censo_divergence_notice,
    )
    from ._cotejo_apply import (
        censo_unadopted_evidence as censo_unadopted_evidence,
    )
    from ._cotejo_apply import (
        divergence_facts as divergence_facts,
    )
    from ._cotejo_apply import (
        open_censo_divergences as open_censo_divergences,
    )
    from ._custody_carry import (
        TYPED_CATEGORY_NAMESPACES as TYPED_CATEGORY_NAMESPACES,
    )
    from ._custody_carry import (
        carried_namespace_definitions as carried_namespace_definitions,
    )
    from ._custody_carry import (
        restore_carried_objects as restore_carried_objects,
    )
    from ._custody_carry import (
        serialize_carried_objects as serialize_carried_objects,
    )
    from ._custody_hold_models import (
        ProfileCustodyRetentionOverride as ProfileCustodyRetentionOverride,
    )
    from ._custody_pointer import (
        ProfileCustodyPointerSnapshot as ProfileCustodyPointerSnapshot,
    )
    from ._custody_ports import (
        ProfileBucketSessionPort as ProfileBucketSessionPort,
    )
    from ._custody_ports import (
        ProfileBucketStoragePathsPort as ProfileBucketStoragePathsPort,
    )
    from ._custody_ports import (
        ProfileBucketStoragePort as ProfileBucketStoragePort,
    )
    from ._custody_ports import (
        ProfileCustodyBucketEventHistoryPort as ProfileCustodyBucketEventHistoryPort,
    )
    from ._custody_ports import (
        ProfileCustodyEnvelopePort as ProfileCustodyEnvelopePort,
    )
    from ._custody_ports import (
        ProfileCustodyLocalRecordStore as ProfileCustodyLocalRecordStore,
    )
    from ._custody_ports import (
        ProfileCustodyPasswordMaterialPort as ProfileCustodyPasswordMaterialPort,
    )
    from ._custody_ports import (
        ProfileCustodyRecordSessionMaterial as ProfileCustodyRecordSessionMaterial,
    )
    from ._custody_ports import (
        ProfileCustodyRecoveryEnrollmentMaterial as ProfileCustodyRecoveryEnrollmentMaterial,
    )
    from ._custody_ports import (
        ProfileCustodyRecoveryEnvelopePort as ProfileCustodyRecoveryEnvelopePort,
    )
    from ._custody_ports import (
        ProfileCustodyRegistrationMaterial as ProfileCustodyRegistrationMaterial,
    )
    from ._custody_ports import (
        ProfileCustodySecureObjectNamespace as ProfileCustodySecureObjectNamespace,
    )
    from ._custody_ports import (
        ProfileCustodySecureObjectRawRowPort as ProfileCustodySecureObjectRawRowPort,
    )
    from ._custody_ports import (
        ProfileCustodySecureObjectRecordPort as ProfileCustodySecureObjectRecordPort,
    )
    from ._custody_ports import (
        ProfileCustodySecureObjectRepositoryPort as ProfileCustodySecureObjectRepositoryPort,
    )
    from ._custody_ports import (
        ProfileCustodySentinelPort as ProfileCustodySentinelPort,
    )
    from ._custody_ports import (
        ProfileCustodyUnlockPort as ProfileCustodyUnlockPort,
    )
    from ._custody_ports import (
        ProfileLoginThrottleEvaluationPort as ProfileLoginThrottleEvaluationPort,
    )
    from ._custody_ports import (
        ProfilePersistedSessionPort as ProfilePersistedSessionPort,
    )
    from ._custody_ports import (
        ProfileRecordCryptoError as ProfileRecordCryptoError,
    )
    from ._custody_ports import (
        ProfileRecordCryptoPort as ProfileRecordCryptoPort,
    )
    from ._custody_ports import (
        ProfileRecordEncryptedBlob as ProfileRecordEncryptedBlob,
    )
    from ._custody_ports import (
        ProfileSecureObjectInventoryPort as ProfileSecureObjectInventoryPort,
    )
    from ._custody_ports import (
        ProfileSessionResumeOutcomePort as ProfileSessionResumeOutcomePort,
    )
    from ._custody_ports import (
        canonical_snapshot_bytes as canonical_snapshot_bytes,
    )
    from ._custody_ports import (
        canonical_snapshot_digest as canonical_snapshot_digest,
    )
    from ._custody_ports import (
        canonical_snapshot_payload as canonical_snapshot_payload,
    )
    from ._custody_ports import (
        create_profile_custody_registration_material as create_profile_custody_registration_material,
    )
    from ._custody_ports import (
        default_profile_bucket_event_history_repository as default_profile_bucket_event_history_repository,
    )
    from ._custody_ports import (
        default_profile_bucket_storage as default_profile_bucket_storage,
    )
    from ._custody_ports import (
        default_profile_custody_local_record_store as default_profile_custody_local_record_store,
    )
    from ._custody_ports import (
        default_profile_record_crypto_port as default_profile_record_crypto_port,
    )
    from ._custody_ports import (
        default_profile_secure_object_inventory as default_profile_secure_object_inventory,
    )
    from ._custody_ports import (
        ensure_profile_custody_owner_root as ensure_profile_custody_owner_root,
    )
    from ._custody_ports import (
        inventory_committed_profile_custody as inventory_committed_profile_custody,
    )
    from ._custody_ports import (
        map_profile_authentication_proof_failure as map_profile_authentication_proof_failure,
    )
    from ._custody_ports import (
        profile_advance_session_idle_deadline as profile_advance_session_idle_deadline,
    )
    from ._custody_ports import (
        profile_bind_bucket_session as profile_bind_bucket_session,
    )
    from ._custody_ports import (
        profile_current_bucket_session as profile_current_bucket_session,
    )
    from ._custody_ports import (
        profile_custody_owner_root as profile_custody_owner_root,
    )
    from ._custody_ports import (
        profile_custody_record_session_material as profile_custody_record_session_material,
    )
    from ._custody_ports import (
        profile_custody_recovery_envelope_path as profile_custody_recovery_envelope_path,
    )
    from ._custody_ports import (
        profile_custody_secure_object_namespace as profile_custody_secure_object_namespace,
    )
    from ._custody_ports import (
        profile_custody_secure_object_repository as profile_custody_secure_object_repository,
    )
    from ._custody_ports import (
        profile_is_authentication_failure as profile_is_authentication_failure,
    )
    from ._custody_ports import (
        profile_is_keyring_unavailable as profile_is_keyring_unavailable,
    )
    from ._custody_ports import (
        profile_is_persisted_session as profile_is_persisted_session,
    )
    from ._custody_ports import (
        profile_session_serves_bucket as profile_session_serves_bucket,
    )
    from ._custody_ports import (
        prove_profile_recovery_artifact as prove_profile_recovery_artifact,
    )
    from ._custody_ports import (
        refuse_profile_login_without_password_channel as refuse_profile_login_without_password_channel,
    )
    from ._custody_ports import (
        unlock_profile_custody_password as unlock_profile_custody_password,
    )
    from ._custody_ports import (
        verify_profile_custody_dek_against_sentinel as verify_profile_custody_dek_against_sentinel,
    )
    from ._custody_repository import (
        ProfileCustodyTransactionRepository as ProfileCustodyTransactionRepository,
    )
    from ._custody_repository import (
        compare_and_swap_profile_pointer as compare_and_swap_profile_pointer,
    )
    from ._custody_repository import (
        profile_custody_transaction_lock as profile_custody_transaction_lock,
    )
    from ._custody_transactions import (
        ProfileCustodyDeleteConfirmation as ProfileCustodyDeleteConfirmation,
    )
    from ._custody_transactions import (
        ProfileCustodyHoldAssessment as ProfileCustodyHoldAssessment,
    )
    from ._custody_transactions import (
        ProfileCustodyHoldEvidence as ProfileCustodyHoldEvidence,
    )
    from ._custody_transactions import (
        ProfileCustodyInventoryWitness as ProfileCustodyInventoryWitness,
    )
    from ._custody_transactions import (
        ProfileCustodyTransactionConflictError as ProfileCustodyTransactionConflictError,
    )
    from ._custody_transactions import (
        ProfileCustodyTransactionCorruptError as ProfileCustodyTransactionCorruptError,
    )
    from ._custody_transactions import (
        ProfileCustodyTransactionError as ProfileCustodyTransactionError,
    )
    from ._custody_transactions import (
        ProfileCustodyTransactionJournal as ProfileCustodyTransactionJournal,
    )
    from ._custody_transactions import (
        ProfileCustodyTransactionOperation as ProfileCustodyTransactionOperation,
    )
    from ._custody_transactions import (
        ProfileCustodyTransactionReceipt as ProfileCustodyTransactionReceipt,
    )
    from ._custody_transactions import (
        ProfileCustodyTransactionRefusalError as ProfileCustodyTransactionRefusalError,
    )
    from ._custody_transactions import (
        ProfileCustodyTransactionState as ProfileCustodyTransactionState,
    )
    from ._fact_write import (
        ProfileFactWriteDoor as ProfileFactWriteDoor,
    )
    from ._fact_write import (
        apply_manager_profile_field_mutation as apply_manager_profile_field_mutation,
    )
    from ._fact_write import (
        apply_profile_fact_changes as apply_profile_fact_changes,
    )
    from ._filing_baseline import (
        missing_filing_baseline_flags as missing_filing_baseline_flags,
    )
    from ._keys_validation import (
        list_profile_key_records as list_profile_key_records,
    )
    from ._keys_validation import (
        validate_profile_values as validate_profile_values,
    )
    from ._language_resolver import (
        resolve_profile_output_language_hint as resolve_profile_output_language_hint,
    )
    from ._lifecycle import (
        ProfileCapsuleLifecycle as ProfileCapsuleLifecycle,
    )
    from ._login_session import (
        ProfileLoginOutcome as ProfileLoginOutcome,
    )
    from ._login_session import (
        ProfileLoginThrottledError as ProfileLoginThrottledError,
    )
    from ._login_session import (
        bind_resumed_profile_session as bind_resumed_profile_session,
    )
    from ._login_session import (
        close_profile_session_artefacts as close_profile_session_artefacts,
    )
    from ._login_session import (
        login_profile as login_profile,
    )
    from ._login_session import (
        logout_active_profile as logout_active_profile,
    )
    from ._login_session import (
        resolve_login_target as resolve_login_target,
    )
    from ._overview import (
        MASKED_PLACEHOLDER as MASKED_PLACEHOLDER,
    )
    from ._overview import (
        ProfileFieldChoice as ProfileFieldChoice,
    )
    from ._overview import (
        ProfileFieldView as ProfileFieldView,
    )
    from ._overview import (
        ProfileOverview as ProfileOverview,
    )
    from ._overview import (
        ProfileSectionView as ProfileSectionView,
    )
    from ._overview import (
        build_profile_overview as build_profile_overview,
    )
    from ._overview import (
        mask_profile_field as mask_profile_field,
    )
    from ._overview import (
        profile_field_choices as profile_field_choices,
    )
    from ._overview import (
        resolve_profile_field_label_for_path as resolve_profile_field_label_for_path,
    )
    from ._passphrase_rotation import (
        ProfilePassphraseRotationError as ProfilePassphraseRotationError,
    )
    from ._passphrase_rotation import (
        ProfilePassphraseRotationOutcome as ProfilePassphraseRotationOutcome,
    )
    from ._passphrase_rotation import (
        rotate_profile_passphrase as rotate_profile_passphrase,
    )
    from ._preflight import (
        ProfilePreflightService as ProfilePreflightService,
    )
    from ._preflight import (
        build_profile_preflight_requirement as build_profile_preflight_requirement,
    )
    from ._preflight import (
        format_profile_path_requirements as format_profile_path_requirements,
    )
    from ._preflight import (
        format_profile_preflight_requirement as format_profile_preflight_requirement,
    )
    from ._preflight import (
        format_profile_selector_requirements as format_profile_selector_requirements,
    )
    from ._profile_pointer_transaction import (
        active_profile_pointer_transaction as active_profile_pointer_transaction,
    )
    from ._profile_record_repository import (
        ProfileRecordRepository as ProfileRecordRepository,
    )
    from ._profile_record_repository import (
        activate_profile_record_session as activate_profile_record_session,
    )
    from ._profile_record_repository import (
        bound_profile_record_session as bound_profile_record_session,
    )
    from ._profile_record_repository import (
        close_active_profile_record_session as close_active_profile_record_session,
    )
    from ._profile_record_repository import (
        profile_record_session_if_authenticated as profile_record_session_if_authenticated,
    )
    from ._profile_record_repository import (
        require_profile_record_session as require_profile_record_session,
    )
    from ._profile_repository import (
        CommittedProfileRepository as CommittedProfileRepository,
    )
    from ._profile_repository import (
        ProfileNotFoundError as ProfileNotFoundError,
    )
    from ._profile_repository import (
        ProfileSummary as ProfileSummary,
    )
    from ._projections import (
        EffectiveFact as EffectiveFact,
    )
    from ._projections import (
        fact_value as fact_value,
    )
    from ._projections import (
        facts_to_values as facts_to_values,
    )
    from ._projections import (
        projection_for_taxpayer as projection_for_taxpayer,
    )
    from ._projections import (
        record_to_effective_facts as record_to_effective_facts,
    )
    from ._projections import (
        record_to_path_values as record_to_path_values,
    )
    from ._projections import (
        record_to_values as record_to_values,
    )
    from ._projections import (
        snapshot_to_values as snapshot_to_values,
    )
    from ._prospective_password import (
        ProspectiveProfilePasswordRefusal as ProspectiveProfilePasswordRefusal,
    )
    from ._prospective_password import (
        prospective_profile_password_refusal as prospective_profile_password_refusal,
    )
    from ._recovery_custody import (
        ProfileRecoveryArtifactReceipt as ProfileRecoveryArtifactReceipt,
    )
    from ._recovery_custody import (
        ProfileRecoveryEnrollment as ProfileRecoveryEnrollment,
    )
    from ._recovery_custody import (
        export_profile_recovery_artifact as export_profile_recovery_artifact,
    )
    from ._recovery_custody import (
        mint_profile_creation_recovery as mint_profile_creation_recovery,
    )
    from ._recovery_custody import (
        restore_profile_from_recovery_artifact as restore_profile_from_recovery_artifact,
    )
    from ._recovery_custody import (
        restore_profile_with_password as restore_profile_with_password,
    )
    from ._registration import (
        ProfileRegistrationConflictError as ProfileRegistrationConflictError,
    )
    from ._registration import (
        ProfileRegistrationError as ProfileRegistrationError,
    )
    from ._registration import (
        ProfileRegistrationOutcome as ProfileRegistrationOutcome,
    )
    from ._registration import (
        register_profile_with_credentials as register_profile_with_credentials,
    )
    from ._repository import (
        USER_PROFILE_SNAPSHOT_NAMESPACE as USER_PROFILE_SNAPSHOT_NAMESPACE,
    )
    from ._repository import (
        UserProfileSnapshotRepository as UserProfileSnapshotRepository,
    )
    from ._repository import (
        user_profile_snapshot_object_key as user_profile_snapshot_object_key,
    )
    from ._section_rows import (
        ProfileRepeatableRowMutationOutcome as ProfileRepeatableRowMutationOutcome,
    )
    from ._section_rows import (
        add_profile_repeatable_section_row as add_profile_repeatable_section_row,
    )
    from ._section_rows import (
        next_section_row_index as next_section_row_index,
    )
    from ._section_rows import (
        section_row_facts as section_row_facts,
    )
    from ._validation import (
        COMPLETENESS_ISSUE_CODES as COMPLETENESS_ISSUE_CODES,
    )
    from ._validation import (
        ProfileValidationService as ProfileValidationService,
    )
    from ._validation import (
        reject_invalid_profile_facts as reject_invalid_profile_facts,
    )
# An explicit register call replaces a side-effect import so the
# registration point is greppable rather than hidden behind a
# suppression-protected import. Runs after all module-level imports settle so
# the call sits in a clear initialiser slot. The resolver implementation
# defers its workflow / orchestration imports inside its body so this
# call does not trigger a heavy cascade.
_register_language_resolver()


#: Re-exported name -> owning module (dotted, relative to this package, resolved
#: through :func:`importlib.import_module`). Every branch of the former PEP-562
#: ``__getattr__`` name-resolution ladder is one row here; the domain records
#: resolve through the domain package's public facade, every other row through
#: an intra-package private submodule.
#:
#: A STATIC dict literal, deliberately, and it must not go back to being built.
#: This table was once a comprehension over ``(module, names)`` pairs, which
#: made a name listed under two modules silently survivable: the later pair won
#: and the wrong home resolved correctly until the pairs were reordered, at
#: which point ``__getattr__`` raises :exc:`AttributeError` at the import site.
#: Spelled as a literal, the same mistake is a repeated key, which ruff refuses
#: as ``F601`` before it can be committed. Nothing at runtime can see it either
#: way -- both forms collapse the duplicate -- so the literal form IS the check.
#:
#: The same truth is stated three times in this module: the ``TYPE_CHECKING``
#: block above, this table, and ``__all__`` below, all hand-synchronised. That
#: is the standing cause of this class of slip and it is not addressed here.
_LAZY_EXPORTS: dict[str, str] = {
    "ProfileBucketStoragePathsPort": "._custody_ports",
    "ProfileBucketStoragePort": "._custody_ports",
    "ProfileCustodyBucketEventHistoryPort": "._custody_ports",
    "ProfileCustodyRecordSessionMaterial": "._custody_ports",
    "ProfileCustodyRecoveryEnrollmentMaterial": "._custody_ports",
    "ProfileCustodyRegistrationMaterial": "._custody_ports",
    "ProfileCustodySecureObjectNamespace": "._custody_ports",
    "ProfileCustodySecureObjectRawRowPort": "._custody_ports",
    "ProfileCustodySecureObjectRecordPort": "._custody_ports",
    "ProfileCustodyUnlockPort": "._custody_ports",
    "ProfileLoginThrottleEvaluationPort": "._custody_ports",
    "ProfileRecordCryptoError": "._custody_ports",
    "ProfileRecordCryptoPort": "._custody_ports",
    "ProfileRecordEncryptedBlob": "._custody_ports",
    "ProfileSecureObjectInventoryPort": "._custody_ports",
    "create_profile_custody_registration_material": "._custody_ports",
    "default_profile_bucket_event_history_repository": "._custody_ports",
    "default_profile_record_crypto_port": "._custody_ports",
    "export_profile_recovery_artifact": "._recovery_custody",
    "mint_profile_creation_recovery": "._recovery_custody",
    "profile_advance_session_idle_deadline": "._custody_ports",
    "profile_custody_record_session_material": "._custody_ports",
    "profile_custody_secure_object_namespace": "._custody_ports",
    "profile_custody_secure_object_repository": "._custody_ports",
    "profile_is_authentication_failure": "._custody_ports",
    "profile_is_keyring_unavailable": "._custody_ports",
    "map_profile_authentication_proof_failure": "._custody_ports",
    "profile_is_persisted_session": "._custody_ports",
    "profile_session_serves_bucket": "._custody_ports",
    "prove_profile_recovery_artifact": "._custody_ports",
    "refuse_profile_login_without_password_channel": "._custody_ports",
    "unlock_profile_custody_password": "._custody_ports",
    "verify_profile_custody_dek_against_sentinel": "._custody_ports",
    "profile_custody_recovery_envelope_path": "._custody_ports",
    "ProfileCustodyLocalRecordStore": "._custody_ports",
    "canonical_snapshot_bytes": "._custody_ports",
    "canonical_snapshot_digest": "._custody_ports",
    "canonical_snapshot_payload": "._custody_ports",
    "default_profile_custody_local_record_store": "._custody_ports",
    "ensure_profile_custody_owner_root": "._custody_ports",
    "profile_custody_owner_root": "._custody_ports",
    "default_profile_bucket_storage": "._custody_ports",
    "inventory_committed_profile_custody": "._custody_ports",
    "default_profile_secure_object_inventory": "._custody_ports",
    "profile_bind_bucket_session": "._custody_ports",
    "profile_current_bucket_session": "._custody_ports",
    "CENSAL_ADOPTABLE_PATHS": "._censo_sync",
    "CensalObservation": "._censal_observation",
    "CensalObservationAddress": "._censal_observation",
    "CensalObservationIdentity": "._censal_observation",
    "CENSAL_OPERATION_DEFINITION": "._censal_operation",
    "CENSAL_OPERATION_DEFINITION_ID": "._censal_operation",
    "CENSAL_REVIEW_RESPONSE_SCHEMA_BINDING": "._censal_operation",
    "CensalFieldIntent": "._censal_operation",
    "CensalOperationAcquisition": "._censal_operation",
    "CensalOperationOutcome": "._censal_operation",
    "CensalOperationRequest": "._censal_operation",
    "CensalOperationResult": "._censal_operation",
    "CensalProfileBaseline": "._censal_operation",
    "CensalReviewedFieldIntent": "._censal_operation",
    "CensalReviewResponse": "._censal_operation",
    "build_censal_operation_definition": "._censal_operation",
    "build_censal_operation_registration": "._censal_operation",
    "build_user_profile_operation_definitions": "._operation_definitions",
    "build_user_profile_operation_registrations": "._operation_definitions",
    "CENSO_CERTIFICATE_AXIS_PREFIX": "._cotejo_apply",
    "CENSO_DIVERGENCE_NOTICE_CODE": "._cotejo_apply",
    "CENSO_DIVERGENCE_PREFIX": "._cotejo_apply",
    "CENSO_SOURCE_TAG": "._censo_sync",
    "CENSO_UNADOPTED_EVIDENCE_FIELDS": "._cotejo_apply",
    "COMPLETENESS_ISSUE_CODES": "._validation",
    "CapabilityDecision": "._capabilities",
    "CapabilitySource": "._capabilities",
    "CensalIdentityMismatchError": "._censo_sync",
    "CensalReconciliation": "._censo_sync",
    "CensoDivergence": "._cotejo_apply",
    "CensoSyncError": "._censo_errors",
    "CensoSyncService": "._censo_sync",
    "CommittedProfileRepository": "._profile_repository",
    "EffectiveFact": "._projections",
    "EncryptedProfileBundleError": "._bundle_encryption",
    "EncryptedProfileBundleExport": "._bundle_encryption",
    "MASKED_PLACEHOLDER": "._overview",
    "PreparedProfileExport": "._bundle_export",
    "ProfileBucketSessionPort": "._custody_ports",
    "ProfileBundleExportJournalRepository": "._bundle_export_operation",
    "ProfileBundleExportPurpose": "._bundle_export",
    "ProfileBundleExportReconcileFailure": "._bundle_export",
    "ProfileBundleExportReconciliation": "._bundle_export",
    "ProfileBundleExportRequest": "._bundle_export",
    "ProfileBundleExportResult": "._bundle_export",
    "ProfileBundleExportTarget": "._bundle_export",
    "ProfileBundleExportTransport": "._bundle_export",
    "ProfileCapsuleLifecycle": "._lifecycle",
    "ProfileCustodyDeleteConfirmation": "._custody_transactions",
    "ProfileCustodyEnvelopePort": "._custody_ports",
    "ProfileCustodyHoldAssessment": "._custody_transactions",
    "ProfileCustodyRetentionOverride": "._custody_hold_models",
    "ProfileCustodyHoldEvidence": "._custody_transactions",
    "ProfileCustodyInventoryWitness": "._custody_transactions",
    "ProfileCustodyPasswordMaterialPort": "._custody_ports",
    "ProfileCustodyPointerSnapshot": "._custody_pointer",
    "ProfileCustodyRecoveryEnvelopePort": "._custody_ports",
    "ProfileCustodySecureObjectRepositoryPort": "._custody_ports",
    "ProfileCustodySentinelPort": "._custody_ports",
    "ProfileCustodyTransactionConflictError": "._custody_transactions",
    "ProfileCustodyTransactionCorruptError": "._custody_transactions",
    "ProfileCustodyTransactionError": "._custody_transactions",
    "ProfileCustodyTransactionJournal": "._custody_transactions",
    "ProfileCustodyTransactionOperation": "._custody_transactions",
    "ProfileCustodyTransactionReceipt": "._custody_transactions",
    "ProfileCustodyTransactionRefusalError": "._custody_transactions",
    "ProfileCustodyTransactionRepository": "._custody_repository",
    "ProfileCustodyTransactionState": "._custody_transactions",
    "ProfileFieldChoice": "._overview",
    "ProfileFieldView": "._overview",
    "ProfileFactWriteDoor": "._fact_write",
    "ProfileImportResult": "._commands",
    "ProfileLoginOutcome": "._login_session",
    "ProfileLoginThrottledError": "._login_session",
    "ProfileNotFoundError": "._profile_repository",
    "ProfileOverview": "._overview",
    "ProfilePersistedSessionPort": "._custody_ports",
    "ProfilePreflightReport": "._commands",
    "ProfilePreflightRequirement": "._commands",
    "ProfilePreflightService": "._preflight",
    "ProfileAuthenticationRefusedError": "._authentication",
    "ProfilePasswordProofOperation": "._authentication",
    "ProspectiveProfilePasswordRefusal": "._prospective_password",
    "prospective_profile_password_refusal": "._prospective_password",
    "ProfilePassphraseRotationError": "._passphrase_rotation",
    "ProfilePassphraseRotationOutcome": "._passphrase_rotation",
    "ProfileRecordRepository": "._profile_record_repository",
    "ProfileRepeatableRowMutationOutcome": "._section_rows",
    "ProfileRecordIntegrityError": "._capsule_record",
    "ProfileRecordSession": "._capsule_record",
    "bound_profile_record_session": "._profile_record_repository",
    "ProfileRecoveryArtifactReceipt": "._recovery_custody",
    "ProfileRecoveryEnrollment": "._recovery_custody",
    "ProfileRegistrationConflictError": "._registration",
    "ProfileRegistrationError": "._registration",
    "ProfileRegistrationOutcome": "._registration",
    "ProfileSectionView": "._overview",
    "ProfileSessionResumeOutcomePort": "._custody_ports",
    "ProfileSnapshot": "._commands",
    "ProfileStaleCheckReport": "._commands",
    "ProfileSummary": "._profile_repository",
    "ProfileValidationIssue": "._commands",
    "ProfileValidationReport": "._commands",
    "ProfileValidationService": "._validation",
    "SUPPORTED_BUNDLE_SCHEMA_VERSIONS": "._bundle",
    "TYPED_CATEGORY_NAMESPACES": "._custody_carry",
    "USER_PROFILE_SNAPSHOT_NAMESPACE": "._repository",
    "UnsupportedBundleSchemaVersionError": "._bundle",
    "UserProfileFact": "...domain.user_profile",
    "UserProfileFactValue": "...domain.user_profile",
    "UserProfileRecord": "...domain.user_profile",
    "UserProfileSnapshotRepository": "._repository",
    "activate_profile_record_session": "._profile_record_repository",
    "active_profile_pointer_transaction": "._profile_pointer_transaction",
    "add_profile_repeatable_section_row": "._section_rows",
    "apply_censal_read": "._censo_sync",
    "apply_cotejo": "._cotejo_apply",
    "apply_manager_profile_field_mutation": "._fact_write",
    "apply_profile_fact_changes": "._fact_write",
    "build_profile_overview": "._overview",
    "build_profile_preflight_requirement": "._preflight",
    "bundle_data_categories": "._bundle_export",
    "bundle_excluded_data_categories": "._bundle_export",
    "carried_namespace_definitions": "._custody_carry",
    "censal_facts_from_read": "._censo_sync",
    "censo_divergence_notice": "._cotejo_apply",
    "censo_unadopted_evidence": "._cotejo_apply",
    "close_active_profile_record_session": "._profile_record_repository",
    "close_profile_session_artefacts": "._login_session",
    "cloud_evidence_upload_eligible_for_active_profile": "._capabilities",
    "compare_and_swap_profile_pointer": "._custody_repository",
    "conditional_profile_missing_required": "._completeness",
    "decrypt_profile_bundle_with_passphrase": "._bundle_encryption",
    "deserialize_profile_bundle": "._bundle",
    "divergence_facts": "._cotejo_apply",
    "encrypt_profile_bundle_for_passphrase": "._bundle_encryption",
    "export_profile_bundle": "._bundle_export",
    "fact_value": "._projections",
    "facts_to_values": "._projections",
    "format_profile_path_requirements": "._preflight",
    "format_profile_preflight_requirement": "._preflight",
    "format_profile_selector_requirements": "._preflight",
    "iva_regime_required": "._completeness",
    "list_profile_key_records": "._keys_validation",
    "login_profile": "._login_session",
    "logout_active_profile": "._login_session",
    "mask_profile_field": "._overview",
    "missing_filing_baseline_flags": "._filing_baseline",
    "missing_required_field_paths": "._completeness",
    "next_section_row_index": "._section_rows",
    "open_censo_divergences": "._cotejo_apply",
    "prepare_profile_export": "._bundle_export",
    "profile_custody_transaction_lock": "._custody_repository",
    "profile_field_choices": "._overview",
    "profile_record_session_if_authenticated": "._profile_record_repository",
    "profile_section_rows": "._completeness",
    "projection_for_taxpayer": "._projections",
    "publish_prepared_export": "._bundle_export",
    "reconcile_censal_read": "._censo_sync",
    "reconcile_prepared_exports": "._bundle_export",
    "record_to_effective_facts": "._projections",
    "record_to_path_values": "._projections",
    "record_to_values": "._projections",
    "register_imported_profile_bundle": "._bundle",
    "PROFILE_CAPSULE_ARCHIVE_MAX_PAYLOAD_BYTES": "._capsule_archive",
    "ProfileCapsuleArchiveError": "._capsule_archive",
    "ProfileCapsuleArchiveInspection": "._capsule_archive",
    "ProfileCapsuleArchiveReceipt": "._capsule_archive",
    "ProfileCapsuleSource": "._capsule_restore",
    "ProfileCapsuleSourceError": "._capsule_restore",
    "CommittedProfileView": "._aggregate",
    "ProfileRestoreAuthority": "._aggregate",
    "ProfileRestoreOutcome": "._capsule_restore",
    "export_profile_capsule_archive": "._capsule_archive",
    "inspect_profile_capsule_archive": "._capsule_archive",
    "read_profile_capsule_archive": "._capsule_archive",
    "read_profile_capsule_source": "._capsule_restore",
    "register_profile_with_credentials": "._registration",
    "restore_profile_capsule_with_password": "._capsule_restore",
    "restore_profile_capsule_with_recovery_artifact": "._capsule_restore",
    "restore_profile_from_source_with_password": "._capsule_restore",
    "restore_profile_from_source_with_recovery_artifact": "._capsule_restore",
    "rotate_profile_passphrase": "._passphrase_rotation",
    "reject_invalid_profile_facts": "._validation",
    "require_profile_record_session": "._profile_record_repository",
    "resolve_active_capability": "._capabilities",
    "resolve_capability": "._capabilities",
    "resolve_login_target": "._login_session",
    "resolve_profile_field_label_for_path": "._overview",
    "resolve_profile_output_language_hint": "._language_resolver",
    "restore_carried_objects": "._custody_carry",
    "restore_profile_from_recovery_artifact": "._recovery_custody",
    "restore_profile_with_password": "._recovery_custody",
    "bind_resumed_profile_session": "._login_session",
    "section_row_facts": "._section_rows",
    "serialize_carried_objects": "._custody_carry",
    "serialize_profile_bundle": "._bundle",
    "snapshot_to_values": "._projections",
    "user_profile_snapshot_object_key": "._repository",
    "validate_bundle_payload": "._bundle",
    "validate_profile_values": "._keys_validation",
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
    "CENSAL_OPERATION_DEFINITION",
    "CENSAL_OPERATION_DEFINITION_ID",
    "CENSAL_REVIEW_RESPONSE_SCHEMA_BINDING",
    "CENSO_CERTIFICATE_AXIS_PREFIX",
    "CENSO_DIVERGENCE_NOTICE_CODE",
    "CENSO_DIVERGENCE_PREFIX",
    "CENSO_SOURCE_TAG",
    "CENSO_UNADOPTED_EVIDENCE_FIELDS",
    "COMPLETENESS_ISSUE_CODES",
    "MASKED_PLACEHOLDER",
    "PROFILE_CAPSULE_ARCHIVE_MAX_PAYLOAD_BYTES",
    "SUPPORTED_BUNDLE_SCHEMA_VERSIONS",
    "TYPED_CATEGORY_NAMESPACES",
    "USER_PROFILE_SNAPSHOT_NAMESPACE",
    "CapabilityDecision",
    "CapabilitySource",
    "CensalFieldIntent",
    "CensalIdentityMismatchError",
    "CensalObservation",
    "CensalObservationAddress",
    "CensalObservationIdentity",
    "CensalOperationAcquisition",
    "CensalOperationOutcome",
    "CensalOperationRequest",
    "CensalOperationResult",
    "CensalProfileBaseline",
    "CensalReconciliation",
    "CensalReviewResponse",
    "CensalReviewedFieldIntent",
    "CensoDivergence",
    "CensoSyncError",
    "CensoSyncService",
    "CommittedProfileRepository",
    "CommittedProfileView",
    "EffectiveFact",
    "EncryptedProfileBundleError",
    "EncryptedProfileBundleExport",
    "PreparedProfileExport",
    "ProfileAuthenticationRefusedError",
    "ProfileBucketSessionPort",
    "ProfileBundleExportJournalRepository",
    "ProfileBundleExportPurpose",
    "ProfileBundleExportReconcileFailure",
    "ProfileBundleExportReconciliation",
    "ProfileBundleExportRequest",
    "ProfileBundleExportResult",
    "ProfileBundleExportTarget",
    "ProfileBundleExportTransport",
    "ProfileCapsuleArchiveError",
    "ProfileCapsuleArchiveInspection",
    "ProfileCapsuleArchiveReceipt",
    "ProfileCapsuleLifecycle",
    "ProfileCapsuleSource",
    "ProfileCapsuleSourceError",
    "ProfileCustodyDeleteConfirmation",
    "ProfileCustodyEnvelopePort",
    "ProfileCustodyHoldAssessment",
    "ProfileCustodyHoldEvidence",
    "ProfileCustodyInventoryWitness",
    "ProfileCustodyPasswordMaterialPort",
    "ProfileCustodyPointerSnapshot",
    "ProfileCustodyRecoveryEnvelopePort",
    "ProfileCustodyRetentionOverride",
    "ProfileCustodySecureObjectRepositoryPort",
    "ProfileCustodySentinelPort",
    "ProfileCustodyTransactionConflictError",
    "ProfileCustodyTransactionCorruptError",
    "ProfileCustodyTransactionError",
    "ProfileCustodyTransactionJournal",
    "ProfileCustodyTransactionOperation",
    "ProfileCustodyTransactionReceipt",
    "ProfileCustodyTransactionRefusalError",
    "ProfileCustodyTransactionRepository",
    "ProfileCustodyTransactionState",
    "ProfileFactWriteDoor",
    "ProfileFieldChoice",
    "ProfileFieldView",
    "ProfileId",
    "ProfileImportResult",
    "ProfileLoginOutcome",
    "ProfileLoginThrottledError",
    "ProfileNotFoundError",
    "ProfileOverview",
    "ProfilePassphraseRotationError",
    "ProfilePassphraseRotationOutcome",
    "ProfilePasswordProofOperation",
    "ProfilePersistedSessionPort",
    "ProfilePreflightReport",
    "ProfilePreflightRequirement",
    "ProfilePreflightService",
    "ProfileRecordIntegrityError",
    "ProfileRecordRepository",
    "ProfileRecordSession",
    "ProfileRecoveryArtifactReceipt",
    "ProfileRecoveryEnrollment",
    "ProfileRegistrationConflictError",
    "ProfileRegistrationError",
    "ProfileRegistrationOutcome",
    "ProfileRepeatableRowMutationOutcome",
    "ProfileRestoreAuthority",
    "ProfileRestoreOutcome",
    "ProfileSectionView",
    "ProfileSessionResumeOutcomePort",
    "ProfileSnapshot",
    "ProfileStaleCheckReport",
    "ProfileSummary",
    "ProfileValidationIssue",
    "ProfileValidationReport",
    "ProfileValidationService",
    "ProspectiveProfilePasswordRefusal",
    "UnsupportedBundleSchemaVersionError",
    "UserProfileFact",
    "UserProfileFactValue",
    "UserProfileRecord",
    "UserProfileSnapshotRepository",
    "activate_profile_record_session",
    "active_profile_pointer_transaction",
    "add_profile_repeatable_section_row",
    "apply_censal_read",
    "apply_cotejo",
    "apply_manager_profile_field_mutation",
    "apply_profile_fact_changes",
    "bind_resumed_profile_session",
    "bound_profile_record_session",
    "build_censal_operation_definition",
    "build_censal_operation_registration",
    "build_profile_overview",
    "build_profile_preflight_requirement",
    "build_user_profile_operation_definitions",
    "build_user_profile_operation_registrations",
    "bundle_data_categories",
    "bundle_excluded_data_categories",
    "carried_namespace_definitions",
    "censal_facts_from_read",
    "censo_divergence_notice",
    "censo_unadopted_evidence",
    "close_active_profile_record_session",
    "close_profile_session_artefacts",
    "cloud_evidence_upload_eligible_for_active_profile",
    "compare_and_swap_profile_pointer",
    "conditional_profile_missing_required",
    "decrypt_profile_bundle_with_passphrase",
    "deserialize_profile_bundle",
    "divergence_facts",
    "encrypt_profile_bundle_for_passphrase",
    "export_profile_bundle",
    "export_profile_capsule_archive",
    "export_profile_recovery_artifact",
    "fact_value",
    "facts_to_values",
    "format_profile_path_requirements",
    "format_profile_preflight_requirement",
    "format_profile_selector_requirements",
    "inspect_profile_capsule_archive",
    "iva_regime_required",
    "list_profile_key_records",
    "login_profile",
    "logout_active_profile",
    "mask_profile_field",
    "mint_profile_creation_recovery",
    "missing_filing_baseline_flags",
    "missing_required_field_paths",
    "next_section_row_index",
    "open_censo_divergences",
    "prepare_profile_export",
    "profile_custody_transaction_lock",
    "profile_field_choices",
    "profile_record_session_if_authenticated",
    "profile_section_rows",
    "projection_for_taxpayer",
    "prospective_profile_password_refusal",
    "publish_prepared_export",
    "read_profile_capsule_archive",
    "read_profile_capsule_source",
    "reconcile_censal_read",
    "reconcile_prepared_exports",
    "record_to_effective_facts",
    "record_to_path_values",
    "record_to_values",
    "register_imported_profile_bundle",
    "register_profile_with_credentials",
    "reject_invalid_profile_facts",
    "require_profile_record_session",
    "resolve_active_capability",
    "resolve_capability",
    "resolve_login_target",
    "resolve_profile_field_label_for_path",
    "resolve_profile_output_language_hint",
    "restore_carried_objects",
    "restore_profile_capsule_with_password",
    "restore_profile_capsule_with_recovery_artifact",
    "restore_profile_from_recovery_artifact",
    "restore_profile_from_source_with_password",
    "restore_profile_from_source_with_recovery_artifact",
    "restore_profile_with_password",
    "rotate_profile_passphrase",
    "section_row_facts",
    "serialize_carried_objects",
    "serialize_profile_bundle",
    "snapshot_to_values",
    "user_profile_snapshot_object_key",
    "validate_bundle_payload",
    "validate_profile_values",
]
