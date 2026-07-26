"""Typed registry for secure-storage namespace and hierarchy contracts.

Each :class:`SecureObjectNamespaceDefinition` carries a
:class:`SensitivityClass` field that governs the at-rest encryption
treatment applied by the substrate for every object in that namespace.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator

from ....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ....core.classification import SensitivityClass
from ._namespace_taxonomy import (
    _CUSTODY_PROFILE_DISPOSITIONS,
    StorageCustodyDisposition,
    StorageCustodyProfile,
    StorageNamespaceScope,
    StoragePathKind,
    StorageRemoteMirrorPolicy,
)
from .errors import NamespaceRegistryError

SECURE_OBJECT_SCHEMA_VERSION_V1 = 1
SECURE_OBJECT_CATALOGUE_KEY = "catalogue"
SECURE_OBJECT_DEFAULT_KEY = "default"
SECURE_OBJECT_WORKFLOW_STATE_KEY = "state"

BUCKETS_DIRNAME = "buckets"
BUCKET_DB_DIRNAME = "db"
BUCKET_BLOBS_DIRNAME = "blobs"
BUCKET_AUDIT_DIRNAME = "audit"
BUCKET_MANIFEST_FILENAME = "manifest.toml"
BUCKET_LOCK_FILENAME = ".lock"
BUCKET_OUTPUT_LANGUAGE_HINT_FILENAME = "output-language.hint"
KEYSTORE_DIRNAME = "keystore"
BUCKET_DEK_FILENAME = "bucket.dek.json"
PROFILE_SESSION_FILENAME = "session.v1.json"
LOGIN_THROTTLE_FILENAME = "login-throttle.json"
#: Directory holding the application-owned config-reset journal. The
#: application module owns the durable journal itself; the name is declared
#: here so the on-disk hierarchy has one inventory, and the enrollment gate
#: pins the two declarations together.
CONFIG_RESET_JOURNAL_DIRNAME = "reset-operations"
BLOB_MANIFEST_SCHEMA_VERSION = 1
SECRET_RECORD_SCHEMA_VERSION = 1
_SECURE_OBJECTS_TABLE_PATH_KEY = "secure_objects_table"
FORMER_PRODUCT_NAMESPACE_PREFIXES = ("aeat.", "aeat-test.", "aeat-tests.")


def is_former_product_namespace(namespace: str) -> bool:
    """Return whether ``namespace`` uses a retired product-owned prefix."""
    return namespace.startswith(FORMER_PRODUCT_NAMESPACE_PREFIXES)


class SecureObjectNamespaceDefinition(BaseModel):
    """Contract for one encrypted SQL secure-object namespace."""

    model_config = _STRICT_FROZEN

    key: str = Field(min_length=1)
    namespace: str = Field(min_length=1, max_length=128)
    owner: str = Field(min_length=1)
    sensitivity: SensitivityClass
    schema_version: int = Field(ge=1)
    object_key_grammar: str = Field(min_length=1)
    scope: StorageNamespaceScope
    custody_disposition: StorageCustodyDisposition
    default_object_key: str | None = Field(default=None, min_length=1)
    remote_mirror_policy: StorageRemoteMirrorPolicy = StorageRemoteMirrorPolicy.CIPHERTEXT_WITH_METADATA
    remote_mirror_requires_revision: bool = True
    remote_mirror_requires_integrity_manifest: bool = True

    @field_validator("key")
    @classmethod
    def _key_is_registry_safe(cls, value: str) -> str:
        if value != value.strip():
            raise NamespaceRegistryError("registry key must not carry surrounding whitespace")
        if any(separator in value for separator in ("/", "\\", ":", ".")):
            raise NamespaceRegistryError("registry key must be a storage-safe slug")
        return value

    @field_validator("namespace")
    @classmethod
    def _namespace_is_sql_safe(cls, value: str) -> str:
        if value != value.strip():
            raise NamespaceRegistryError("namespace must not carry surrounding whitespace")
        if "/" in value or "\\" in value:
            raise NamespaceRegistryError("namespace must not contain path separators")
        return value

    @field_validator("default_object_key")
    @classmethod
    def _default_key_is_repository_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value != value.strip():
            raise NamespaceRegistryError("default object key must not carry surrounding whitespace")
        if "/" in value or "\\" in value:
            raise NamespaceRegistryError("default object key must not contain path separators")
        return value

    @model_validator(mode="after")
    def _remote_mirror_policy_is_consistent(self) -> SecureObjectNamespaceDefinition:
        if self.remote_mirror_policy is StorageRemoteMirrorPolicy.CIPHERTEXT_WITH_METADATA:
            if not self.remote_mirror_requires_revision or not self.remote_mirror_requires_integrity_manifest:
                raise NamespaceRegistryError(
                    "ciphertext remote mirror namespaces require revision and integrity metadata",
                )
        elif self.remote_mirror_requires_revision or self.remote_mirror_requires_integrity_manifest:
            raise NamespaceRegistryError("local-only and test-only namespaces must not require remote mirror metadata")
        return self

    def require_default_object_key(self) -> str:
        """Return the singleton object key or raise when the namespace is multi-key."""
        if self.default_object_key is None:
            raise NamespaceRegistryError(f"namespace {self.namespace!r} does not define a singleton object key")
        return self.default_object_key


class StoragePathDefinition(BaseModel):
    """Contract for one storage hierarchy path or logical marker."""

    model_config = _STRICT_FROZEN

    key: str = Field(min_length=1)
    kind: StoragePathKind
    grammar: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    segment: str | None = Field(default=None, min_length=1)
    schema_version: int | None = Field(default=None, ge=1)

    @field_validator("key")
    @classmethod
    def _key_is_registry_safe(cls, value: str) -> str:
        if value != value.strip():
            raise NamespaceRegistryError("path key must not carry surrounding whitespace")
        if any(separator in value for separator in ("/", "\\")):
            raise NamespaceRegistryError("path key must not contain path separators")
        return value

    @field_validator("segment")
    @classmethod
    def _segment_is_single_path_component(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value != value.strip():
            raise NamespaceRegistryError("path segment must not carry surrounding whitespace")
        if "/" in value or "\\" in value:
            raise NamespaceRegistryError("path segment must be a single component")
        return value


class StorageHierarchyRegistry(BaseModel):
    """Registry carrying the known secure-storage hierarchy contracts."""

    model_config = _STRICT_FROZEN

    namespaces: tuple[SecureObjectNamespaceDefinition, ...]
    paths: tuple[StoragePathDefinition, ...]

    @model_validator(mode="after")
    def _reject_duplicate_keys_and_namespaces(self) -> StorageHierarchyRegistry:
        namespace_keys = [item.key for item in self.namespaces]
        namespace_values = [item.namespace for item in self.namespaces]
        path_keys = [item.key for item in self.paths]
        if len(namespace_keys) != len(set(namespace_keys)):
            raise NamespaceRegistryError("duplicate secure-object namespace registry key")
        if len(namespace_values) != len(set(namespace_values)):
            raise NamespaceRegistryError("duplicate secure-object namespace value")
        if len(path_keys) != len(set(path_keys)):
            raise NamespaceRegistryError("duplicate storage path registry key")
        return self

    def namespace_by_key(self, key: str) -> SecureObjectNamespaceDefinition:
        """Return a :class:`SecureObjectNamespaceDefinition` by registry key."""
        for namespace in self.namespaces:
            if namespace.key == key:
                return namespace
        raise KeyError(key)

    def namespace_by_value(self, value: str) -> SecureObjectNamespaceDefinition:
        """Return a :class:`SecureObjectNamespaceDefinition` by persisted namespace value."""
        for namespace in self.namespaces:
            if namespace.namespace == value:
                return namespace
        raise KeyError(value)

    def path_by_key(self, key: str) -> StoragePathDefinition:
        """Return a :class:`StoragePathDefinition` by registry key."""
        for path in self.paths:
            if path.key == key:
                return path
        raise KeyError(key)

    def namespaces_for_custody_profile(
        self,
        profile: StorageCustodyProfile,
    ) -> tuple[SecureObjectNamespaceDefinition, ...]:
        """Return carried :class:`SecureObjectNamespaceDefinition` rows for a custody profile."""
        dispositions = _CUSTODY_PROFILE_DISPOSITIONS[profile]
        return tuple(namespace for namespace in self.namespaces if namespace.custody_disposition in dispositions)


def secure_object_logical_path(namespace: str, object_key: str) -> Path:
    """Return the registry-defined logical SQL marker for one secure object."""
    definition = STORAGE_NAMESPACE_REGISTRY.path_by_key(_SECURE_OBJECTS_TABLE_PATH_KEY)
    marker_root = definition.grammar.removesuffix("/<namespace>/<object_key>")
    return Path(marker_root) / namespace / object_key


def secure_object_namespace_logical_path(namespace: str) -> Path:
    """Return the registry-defined logical SQL marker for one secure-object namespace."""
    definition = STORAGE_NAMESPACE_REGISTRY.path_by_key(_SECURE_OBJECTS_TABLE_PATH_KEY)
    marker_root = definition.grammar.removesuffix("/<namespace>/<object_key>")
    return Path(marker_root) / namespace


WORKFLOW_STATE_NAMESPACE = SecureObjectNamespaceDefinition(
    key="workflow_state",
    namespace="cadrumo.workflow",
    owner="cadrumo.application.workflow",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="state",
    default_object_key=SECURE_OBJECT_WORKFLOW_STATE_KEY,
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    custody_disposition=StorageCustodyDisposition.PROCESS_LOCAL,
)
WORKFLOW_RUN_NAMESPACE = SecureObjectNamespaceDefinition(
    key="workflow_runs",
    namespace="cadrumo.application.workflow.runs",
    owner="cadrumo.application.workflow",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{run_id}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.PROCESS_LOCAL,
)
USER_PROFILE_VALUE_NAMESPACE = SecureObjectNamespaceDefinition(
    key="user_profile_value",
    namespace="cadrumo.application.user_profile.value",
    owner="cadrumo.application.user_profile",
    sensitivity=SensitivityClass.IDENTITY,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="user-profile:{profile_id}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY,
)
USER_PROFILE_SNAPSHOT_NAMESPACE = SecureObjectNamespaceDefinition(
    key="user_profile_snapshot",
    namespace="cadrumo.application.user_profile.snapshot",
    owner="cadrumo.application.user_profile",
    sensitivity=SensitivityClass.IDENTITY,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="user-profile-snapshot:{profile_id}:{snapshot_id}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY,
)
PROFILE_INVENTORY_LEDGER_NAMESPACE = SecureObjectNamespaceDefinition(
    key="profile_inventory_ledger",
    namespace="cadrumo.persistence.profile.inventory",
    owner="cadrumo.adapters.persistence.profile.inventory",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="default",
    default_object_key=SECURE_OBJECT_DEFAULT_KEY,
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY,
)
PROFILE_ASSETS_LEDGER_NAMESPACE = SecureObjectNamespaceDefinition(
    key="profile_assets_ledger",
    namespace="cadrumo.persistence.profile.assets",
    owner="cadrumo.adapters.persistence.profile.assets",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="default",
    default_object_key=SECURE_OBJECT_DEFAULT_KEY,
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY,
)
PROFILE_ASSETS_AMORTIZATION_LEDGER_NAMESPACE = SecureObjectNamespaceDefinition(
    key="profile_assets_amortization_ledger",
    namespace="cadrumo.persistence.profile.assets.amortization",
    owner="cadrumo.adapters.persistence.profile.assets",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="default",
    default_object_key=SECURE_OBJECT_DEFAULT_KEY,
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY,
)
PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE = SecureObjectNamespaceDefinition(
    key="profile_bienes_inversion_iva_register",
    namespace="cadrumo.persistence.profile.bienes_inversion",
    owner="cadrumo.adapters.persistence.profile.bienes_inversion",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="default",
    default_object_key=SECURE_OBJECT_DEFAULT_KEY,
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY,
)
PROFILE_PRORRATA_REGISTER_NAMESPACE = SecureObjectNamespaceDefinition(
    key="profile_prorrata_register",
    namespace="cadrumo.persistence.profile.prorrata_register",
    owner="cadrumo.adapters.persistence.profile.prorrata_register",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="default",
    default_object_key=SECURE_OBJECT_DEFAULT_KEY,
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY,
)
REPAIR_INTEGRITY_DECISION_NAMESPACE = SecureObjectNamespaceDefinition(
    key="repair_integrity_decisions",
    namespace="cadrumo.application.repair_integrity.decisions",
    owner="cadrumo.application.repair_integrity",
    sensitivity=SensitivityClass.AUDIT,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{decision_id_sha256_hex}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    # Host-local storage-repair decisions are bound to the host that made them and
    # are not portable bucket data; they are not carried by an export.
    custody_disposition=StorageCustodyDisposition.PROCESS_LOCAL,
)
APPLICATION_FILING_HISTORY_NAMESPACE = SecureObjectNamespaceDefinition(
    key="application_filing_history",
    namespace="cadrumo.application.filing.history",
    owner="cadrumo.application.filing",
    sensitivity=SensitivityClass.AUDIT,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{modelo}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY,
)
AUTH_APODERADO_CONFIGURATION_NAMESPACE = SecureObjectNamespaceDefinition(
    key="auth_apoderado_configuration",
    namespace="cadrumo.auth.apoderado",
    owner="cadrumo.application.auth",
    sensitivity=SensitivityClass.IDENTITY,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{bucket_id}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    # Durable per-bucket apoderamiento setup (represented NIF + granted scopes): it
    # is not a host credential or session and is not re-derivable, so it must
    # survive a recovery restore. Sealed-only because it carries identity data.
    custody_disposition=StorageCustodyDisposition.FULL_CUSTODY_ONLY,
)
CALCULATION_OBSERVATIONS_NAMESPACE = SecureObjectNamespaceDefinition(
    key="calculation_observations",
    namespace="cadrumo.calculations.observations",
    owner="cadrumo.application.calculations",
    sensitivity=SensitivityClass.AUDIT,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    # Single-filer rows key on (modelo, filing_year, period); a per-grupo-member
    # filing widens the same key with an optional trailing member NIF so two
    # members' filings for one triple persist as distinct rows (the 353<-322
    # per_grupo_member fan-in). Both live in this one namespace.
    object_key_grammar="{modelo}:{filing_year}:{period}[:{member_nif}]",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY,
)
# Per-perceptor retención records (perceptor NIF + scheme + taxable base +
# retención) for the M180/M193 calc-mesh perceptor-count resolver. The
# DEDICATED store lets the distinct-NIF count be computed from one persisted
# source shared by the pull and calculate surfaces — never the wrong sum of
# quarterly aggregate counts.
# FINANCIAL sensitivity: perceptor NIFs are identity-bearing financial data and
# live encrypted at rest, never plaintext.
RETENCION_OBSERVATIONS_NAMESPACE = SecureObjectNamespaceDefinition(
    key="retencion_observations",
    namespace="cadrumo.retenciones.observations",
    owner="cadrumo.application.aggregation",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    # The perceptor NIF is sha256-hashed in the object key (mirroring the
    # iva-wallet-decision key convention) so the plaintext NIF lives ONLY inside
    # the encrypted payload, never in a repository identifier.
    object_key_grammar="{modelo}:{filing_year}:{period}:{sha256(perceptor_nif)}:{scheme}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY,
)
WITHHOLDING_OBSERVATIONS_NAMESPACE = SecureObjectNamespaceDefinition(
    key="withholding_observations",
    namespace="cadrumo.withholding.observations",
    owner="cadrumo.application.aggregation",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    # The perceptor NIF is sha256-hashed in the object key (mirroring the
    # iva-wallet-decision key convention) so the plaintext NIF lives ONLY inside
    # the encrypted payload, never in a repository identifier. The clave/subclave
    # are non-identifying AEAT percepcion codes, so they stay plain in the key.
    object_key_grammar="{modelo}:{filing_year}:{period}:{sha256(perceptor_tax_id)}:{clave}:{subclave}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY,
)
IVA_WALLET_RECONCILIATION_DECISIONS_NAMESPACE = SecureObjectNamespaceDefinition(
    key="iva_wallet_reconciliation_decisions",
    namespace="cadrumo.calculations.iva_wallet.reconciliation_decisions",
    owner="cadrumo.application.calculations",
    sensitivity=SensitivityClass.AUDIT,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="iva-wallet-decision:{sha256(taxpayer_nif,target_year,target_period)}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY,
)
IVA_WALLET_RECONCILIATION_DECISION_EVENTS_NAMESPACE = SecureObjectNamespaceDefinition(
    key="iva_wallet_reconciliation_decision_events",
    namespace="cadrumo.calculations.iva_wallet.reconciliation_decision_events",
    owner="cadrumo.application.calculations",
    sensitivity=SensitivityClass.AUDIT,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="iva-wallet-decision-event:{sha256(decision_identity_and_payload)}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY,
)
MODELO_RECONCILIATION_RECORDS_NAMESPACE = SecureObjectNamespaceDefinition(
    key="modelo_reconciliation_records",
    namespace="cadrumo.modelo.reconciliation.records",
    owner="cadrumo.application.modelo",
    sensitivity=SensitivityClass.AUDIT,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    # N records per work unit, never one that overwrites: reconciliation is
    # repeatable and `reconcile history` is a shipped verb, so a key that
    # collapsed runs would destroy the history this store exists to hold. The
    # trailing segment is the content-addressed id of the MODELO_RECONCILED
    # bucket event this record is co-written with, which already folds the
    # reconciliation instant, the actor and the verdict — so it distinguishes
    # every run and binds record to event by identity rather than by a
    # cross-reference field that could drift.
    #
    # No revision id participates. Both the receipt-total and the
    # declaracion-casilla reconciles emit a `no_persisted_revision` advisory and
    # still produce a report, and an identity-header reconcile needs no revision
    # at all; a revision-derived key could not store those runs.
    object_key_grammar="modelo-reconciliation:{work_unit_id}:{bucket_event_id}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY,
)
IVA_COMPENSATION_HISTORY_NAMESPACE = SecureObjectNamespaceDefinition(
    key="iva_compensation_history",
    namespace="cadrumo.calculations.iva_compensation.history",
    owner="cadrumo.application.calculations",
    sensitivity=SensitivityClass.AUDIT,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="303:{filing_year}:{period}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY,
)
LIVE_IVA_REMOTE_STATE_ACQUISITIONS_NAMESPACE = SecureObjectNamespaceDefinition(
    key="live_iva_remote_state_acquisitions",
    namespace="cadrumo.application.live.iva_remote_state_acquisitions",
    owner="cadrumo.application.live",
    sensitivity=SensitivityClass.AUDIT,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar=(
        "live-iva-acquisition:{target_year}:{target_period}:{timestamp}:{sha256(redacted_manifest_seed)}"
    ),
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.FULL_CUSTODY_ONLY,
)
APPLICATION_EVIDENCE_BUNDLE_NAMESPACE = SecureObjectNamespaceDefinition(
    key="application_evidence_bundles",
    namespace="cadrumo.application.evidence.bundles",
    owner="cadrumo.application.evidence",
    sensitivity=SensitivityClass.AUDIT,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{bundle_id}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    custody_disposition=StorageCustodyDisposition.FULL_CUSTODY_ONLY,
)
LEDGER_PURCHASE_INVOICE_EVIDENCE_NAMESPACE = SecureObjectNamespaceDefinition(
    key="ledger_purchase_invoice_evidence",
    namespace="cadrumo.application.ledger.purchase_invoice_evidence",
    owner="cadrumo.application.ledger",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{bucket_id}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    custody_disposition=StorageCustodyDisposition.FULL_CUSTODY_ONLY,
)
LEDGER_BUSINESS_OPERATION_INVOICE_NAMESPACE = SecureObjectNamespaceDefinition(
    key="ledger_business_operation_invoices",
    namespace="cadrumo.application.ledger.business_operation_invoices",
    owner="cadrumo.application.ledger",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{bucket_id}:{source_kind}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY,
)
LEDGER_CLASSIFICATION_RULES_NAMESPACE = SecureObjectNamespaceDefinition(
    key="ledger_classification_rules",
    namespace="cadrumo.ledger.classification.rules",
    owner="cadrumo.application.ledger",
    sensitivity=SensitivityClass.AUDIT,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{rule_id}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY,
)
LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE = SecureObjectNamespaceDefinition(
    key="live_borrador_100_snapshot",
    namespace="cadrumo.application.live.borrador_100_snapshot",
    owner="cadrumo.application.live",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="modelo-100-borrador-snapshot:{bucket_id}:{snapshot_id}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    custody_disposition=StorageCustodyDisposition.FULL_CUSTODY_ONLY,
)
LIVE_M036_DECLARATION_NAMESPACE = SecureObjectNamespaceDefinition(
    key="live_m036_declaration",
    namespace="cadrumo.application.modelo.m036_declaration",
    owner="cadrumo.application.modelo",
    sensitivity=SensitivityClass.IDENTITY,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="m036-declaration:{bucket_id}:{declaration_id}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY,
)
M145_COMMUNICATION_RECORD_NAMESPACE = SecureObjectNamespaceDefinition(
    key="m145_communication_record",
    namespace="cadrumo.application.modelo.m145_communication_record",
    owner="cadrumo.application.modelo",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="m145-communication:{bucket_id}:{communication_record_id}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY,
)
TEST_SNAPSHOT_BASE_PROBE_NAMESPACE = SecureObjectNamespaceDefinition(
    key="test_snapshot_base_probe",
    namespace="cadrumo.application.live.test_snapshot_base_probe",
    owner="cadrumo.application.live",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="snapshot-base-probe:{bucket_id}:{snapshot_id}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    custody_disposition=StorageCustodyDisposition.PROCESS_LOCAL,
    remote_mirror_policy=StorageRemoteMirrorPolicy.TEST_ONLY,
    remote_mirror_requires_revision=False,
    remote_mirror_requires_integrity_manifest=False,
)
TEST_SESSION_LIFECYCLE_NAMESPACE = SecureObjectNamespaceDefinition(
    key="test_session_lifecycle",
    namespace="cadrumo-test.session.lifecycle",
    owner="cadrumo.entrypoints.cli.test_session_lifecycle_roundtrip",
    sensitivity=SensitivityClass.OPERATIONAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="roundtrip-row",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    custody_disposition=StorageCustodyDisposition.PROCESS_LOCAL,
    remote_mirror_policy=StorageRemoteMirrorPolicy.TEST_ONLY,
    remote_mirror_requires_revision=False,
    remote_mirror_requires_integrity_manifest=False,
)
TEST_SECURE_BOUND_CONTRACT_NAMESPACE = SecureObjectNamespaceDefinition(
    key="test_secure_bound_contract",
    namespace="cadrumo-test.envelope.secure_bound_contract",
    owner="cadrumo.adapters.persistence.storage.envelope.test_secure_bound_repository_contract",
    sensitivity=SensitivityClass.AUDIT,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{id}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    custody_disposition=StorageCustodyDisposition.PROCESS_LOCAL,
    remote_mirror_policy=StorageRemoteMirrorPolicy.TEST_ONLY,
    remote_mirror_requires_revision=False,
    remote_mirror_requires_integrity_manifest=False,
)
TEST_RUNTIME_PROFILE_NAMESPACE = SecureObjectNamespaceDefinition(
    key="test_runtime_profile",
    namespace="cadrumo-tests.runtime.profile",
    owner="cadrumo-tests.test_secure_sql",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="runtime-row",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    custody_disposition=StorageCustodyDisposition.PROCESS_LOCAL,
    remote_mirror_policy=StorageRemoteMirrorPolicy.TEST_ONLY,
    remote_mirror_requires_revision=False,
    remote_mirror_requires_integrity_manifest=False,
)
LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE = SecureObjectNamespaceDefinition(
    key="live_expedientes_snapshot",
    namespace="cadrumo.application.live.expedientes_snapshot",
    owner="cadrumo.application.live",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="expedientes-snapshot:{bucket_id}:{snapshot_id}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    custody_disposition=StorageCustodyDisposition.FULL_CUSTODY_ONLY,
)
LIVE_NOTIFICATIONS_SNAPSHOT_NAMESPACE = SecureObjectNamespaceDefinition(
    key="live_notifications_snapshot",
    namespace="cadrumo.application.live.notifications_snapshot",
    owner="cadrumo.application.live",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="notifications-snapshot:{bucket_id}:{snapshot_id}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    custody_disposition=StorageCustodyDisposition.FULL_CUSTODY_ONLY,
)
LIVE_JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE = SecureObjectNamespaceDefinition(
    key="live_justificante_capture_snapshot",
    namespace="cadrumo.application.live.justificante_capture_snapshot",
    owner="cadrumo.application.live",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="justificante-capture-snapshot:{bucket_id}:{snapshot_id}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    custody_disposition=StorageCustodyDisposition.FULL_CUSTODY_ONLY,
)
LIVE_VERIFY_OBSERVATION_NAMESPACE = SecureObjectNamespaceDefinition(
    key="live_verify_observations",
    namespace="cadrumo.application.live.verify_observations",
    owner="cadrumo.application.live",
    sensitivity=SensitivityClass.IDENTITY,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="verify-observation:{bucket_id}:{observation_id}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    custody_disposition=StorageCustodyDisposition.FULL_CUSTODY_ONLY,
)
ATTACHMENT_BLOB_NAMESPACE = SecureObjectNamespaceDefinition(
    key="attachment_blobs",
    namespace="cadrumo.domain.attachments.blobs",
    owner="cadrumo.adapters.persistence.storage.attachment",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{sha256_hex}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.FULL_CUSTODY_ONLY,
)
ATTACHMENT_MANIFEST_NAMESPACE = SecureObjectNamespaceDefinition(
    key="attachment_manifests",
    namespace="cadrumo.domain.attachments.manifests",
    owner="cadrumo.adapters.persistence.storage.attachment",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{attachment_id_sha256_hex}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.FULL_CUSTODY_ONLY,
)
AEAT_BROWSER_SESSION_NAMESPACE = SecureObjectNamespaceDefinition(
    key="aeat_browser_sessions",
    namespace="cadrumo.outbound.aeat.auth.sessions",
    owner="cadrumo.adapters.outbound.aeat.auth",
    sensitivity=SensitivityClass.SESSION,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{storage_state_path_posix}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    custody_disposition=StorageCustodyDisposition.PROCESS_LOCAL,
)
CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE = SecureObjectNamespaceDefinition(
    key="clave_movil_diagnostics",
    namespace="cadrumo.outbound.aeat.auth.clave_movil.diagnostics",
    owner="cadrumo.adapters.outbound.aeat.auth",
    sensitivity=SensitivityClass.SESSION,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{diagnostic_id_or_timestamp_iso}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    custody_disposition=StorageCustodyDisposition.PROCESS_LOCAL,
)
GOOGLE_OAUTH_CLIENT_NAMESPACE = SecureObjectNamespaceDefinition(
    key="google_oauth_client",
    namespace="cadrumo.google.oauth.client",
    owner="cadrumo.adapters.outbound.google",
    sensitivity=SensitivityClass.SECRET,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{profile}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.PROCESS_LOCAL,
)
GOOGLE_OAUTH_TOKEN_NAMESPACE = SecureObjectNamespaceDefinition(
    key="google_oauth_token",
    namespace="cadrumo.google.oauth.token",
    owner="cadrumo.adapters.outbound.google",
    sensitivity=SensitivityClass.SECRET,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{profile}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.PROCESS_LOCAL,
)
GOOGLE_OAUTH_METADATA_NAMESPACE = SecureObjectNamespaceDefinition(
    key="google_oauth_metadata",
    namespace="cadrumo.google.oauth.metadata",
    owner="cadrumo.adapters.outbound.google",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{profile}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.PROCESS_LOCAL,
)
GOOGLE_DRIVE_CONFIG_NAMESPACE = SecureObjectNamespaceDefinition(
    key="google_drive_config",
    namespace="cadrumo.google.drive.config",
    owner="cadrumo.adapters.outbound.google",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{profile}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.PROCESS_LOCAL,
)
GOOGLE_CREDENTIAL_SOURCE_NAMESPACE = SecureObjectNamespaceDefinition(
    key="google_credential_source",
    namespace="cadrumo.google.credential.source",
    owner="cadrumo.adapters.outbound.google",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{profile}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.PROCESS_LOCAL,
)
LLM_CACHE_NAMESPACE = SecureObjectNamespaceDefinition(
    key="llm_cache",
    namespace="cadrumo.outbound.llm.cache",
    owner="cadrumo.adapters.outbound.llm",
    sensitivity=SensitivityClass.DIAGNOSTIC,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{logical_root}|{provider}|{model}|{prompt_hash}|{args_hash}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.PROCESS_LOCAL,
)
LLM_USAGE_NAMESPACE = SecureObjectNamespaceDefinition(
    key="llm_usage",
    namespace="cadrumo.outbound.llm.usage",
    owner="cadrumo.adapters.outbound.llm",
    sensitivity=SensitivityClass.DIAGNOSTIC,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{logical_root}|{created_at_iso}|{request_id}|{uuid4_hex}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.PROCESS_LOCAL,
)
LLM_RUN_TELEMETRY_NAMESPACE = SecureObjectNamespaceDefinition(
    key="llm_run_telemetry",
    namespace="cadrumo.outbound.llm.run_telemetry",
    owner="cadrumo.adapters.outbound.llm",
    sensitivity=SensitivityClass.DIAGNOSTIC,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{logical_root}|{started_at_iso}|{run_id}|{uuid4_hex}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.PROCESS_LOCAL,
)
AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE = SecureObjectNamespaceDefinition(
    key="aeat_filed_declaration_artefacts",
    namespace="cadrumo.outbound.aeat.sede.filed_declaration.artefacts",
    owner="cadrumo.adapters.outbound.aeat.sede",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{sha256_hex}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.FULL_CUSTODY_ONLY,
)
AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE = SecureObjectNamespaceDefinition(
    key="aeat_filed_declaration_observations",
    namespace="cadrumo.outbound.aeat.sede.filed_declaration.observations",
    owner="cadrumo.adapters.outbound.aeat.sede",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{sha256(modelo,ejercicio,period,expediente_id)}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.FULL_CUSTODY_ONLY,
)
AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE = SecureObjectNamespaceDefinition(
    key="aeat_iva_wallet_observations",
    namespace="cadrumo.outbound.aeat.sede.iva_compensation_wallet.observations",
    owner="cadrumo.adapters.outbound.aeat.sede",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{sha256(taxpayer_nif,target_year,target_period,captured_at)}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.FULL_CUSTODY_ONLY,
)
MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE = SecureObjectNamespaceDefinition(
    key="modelo_review_package_signing_key",
    namespace="cadrumo.application.modelo.review_package_signing_key",
    owner="cadrumo.application.modelo",
    sensitivity=SensitivityClass.SECRET,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="review-package-signing-key:{bucket_id}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.PROCESS_LOCAL,
)
MODELO_REVIEW_PACKAGE_RECIPIENT_FINGERPRINT_REGISTRY_NAMESPACE = SecureObjectNamespaceDefinition(
    key="modelo_review_package_recipient_fingerprint_registry",
    namespace="cadrumo.application.modelo.review_package_recipient_fingerprint_registry",
    owner="cadrumo.application.modelo",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="default",
    default_object_key=SECURE_OBJECT_DEFAULT_KEY,
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY,
)
MODELO_REVIEW_PACKAGE_RECIPIENT_REPLAY_GUARD_NAMESPACE = SecureObjectNamespaceDefinition(
    key="modelo_review_package_recipient_replay_guard",
    namespace="cadrumo.application.modelo.review_package_recipient_replay_guard",
    owner="cadrumo.application.modelo",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="default",
    default_object_key=SECURE_OBJECT_DEFAULT_KEY,
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY,
)
MODELO_REVIEW_PACKAGE_RECIPIENT_ENCRYPTION_KEY_NAMESPACE = SecureObjectNamespaceDefinition(
    key="modelo_review_package_recipient_encryption_key",
    namespace="cadrumo.application.modelo.review_package_recipient_encryption_key",
    owner="cadrumo.application.modelo",
    sensitivity=SensitivityClass.SECRET,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="review-package-recipient-encryption-key:{bucket_id}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.PROCESS_LOCAL,
)

BUCKET_EVENT_HISTORY_NAMESPACE = SecureObjectNamespaceDefinition(
    key="bucket_event_history",
    namespace="cadrumo.domain.buckets.event_history",
    owner="cadrumo.domain.buckets",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="catalogue",
    default_object_key=SECURE_OBJECT_CATALOGUE_KEY,
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.FULL_CUSTODY_ONLY,
)
SUBMISSION_RECORDS_NAMESPACE = SecureObjectNamespaceDefinition(
    key="submission_records",
    namespace="cadrumo.domain.submission.records",
    owner="cadrumo.domain.submission",
    sensitivity=SensitivityClass.AUDIT,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{submission_id}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY,
)
JUSTIFICANTE_METADATA_NAMESPACE = SecureObjectNamespaceDefinition(
    key="justificante_metadata",
    namespace="cadrumo.domain.justificante.metadata",
    owner="cadrumo.domain.justificante",
    sensitivity=SensitivityClass.AUDIT,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{csv}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY,
)
FILING_DRAFTS_NAMESPACE = SecureObjectNamespaceDefinition(
    key="filing_drafts",
    namespace="cadrumo.domain.filing.drafts",
    owner="cadrumo.domain.filing",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{draft_id}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY,
)
FILING_AMENDMENTS_NAMESPACE = SecureObjectNamespaceDefinition(
    key="filing_amendments",
    namespace="cadrumo.domain.filing.amendments",
    owner="cadrumo.domain.filing",
    sensitivity=SensitivityClass.AUDIT,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{amendment_id}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY,
)
INVOICE_CATALOGUE_NAMESPACE = SecureObjectNamespaceDefinition(
    key="invoice_catalogue",
    namespace="cadrumo.domain.invoices",
    owner="cadrumo.domain.invoices",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="catalogue",
    default_object_key=SECURE_OBJECT_CATALOGUE_KEY,
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY,
)
TRANSACTION_CATALOGUE_NAMESPACE = SecureObjectNamespaceDefinition(
    key="transaction_catalogue",
    namespace="cadrumo.domain.transactions.bucket",
    owner="cadrumo.domain.transactions",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    # One secure-object row per transaction keyed transaction:{bucket_id}:{tx_id}
    # (transaction_object_key), plus a single per-bucket membership-index row keyed
    # transaction-index:{bucket_id} (transaction_index_object_key). The unrelated
    # transaction-catalogue:{bucket_id} token is a BucketEvent audit object_id, not
    # a secure-object key, and must not be conflated with this key grammar.
    object_key_grammar="transaction:{bucket_id}:{transaction_id}; transaction-index:{bucket_id}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY,
)
USAGE_RATIO_PROFILE_NAMESPACE = SecureObjectNamespaceDefinition(
    key="usage_ratio_profile",
    namespace="cadrumo.domain.usage_ratios",
    owner="cadrumo.domain.usage_ratios",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="profile:{bucket_id}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY,
)
MODELO_WORK_UNIT_CATALOGUE_NAMESPACE = SecureObjectNamespaceDefinition(
    key="modelo_work_unit_catalogue",
    namespace="cadrumo.domain.modelos.work_units",
    owner="cadrumo.domain.modelos",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="catalogue",
    default_object_key=SECURE_OBJECT_CATALOGUE_KEY,
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY,
)
MODELO_VERIFICATION_REPORT_CATALOGUE_NAMESPACE = SecureObjectNamespaceDefinition(
    key="modelo_verification_report_catalogue",
    namespace="cadrumo.domain.modelos.verification_reports",
    owner="cadrumo.domain.modelos",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="catalogue",
    default_object_key=SECURE_OBJECT_CATALOGUE_KEY,
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY,
)
MODELO_FILING_RECORD_CATALOGUE_NAMESPACE = SecureObjectNamespaceDefinition(
    key="modelo_filing_record_catalogue",
    namespace="cadrumo.domain.modelos.filing_records",
    owner="cadrumo.domain.modelos",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="catalogue",
    default_object_key=SECURE_OBJECT_CATALOGUE_KEY,
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY,
)
MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE = SecureObjectNamespaceDefinition(
    key="modelo_calculation_revision_catalogue",
    namespace="cadrumo.domain.modelos.calculation_revisions",
    owner="cadrumo.domain.modelos",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="catalogue",
    default_object_key=SECURE_OBJECT_CATALOGUE_KEY,
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY,
)
TRANSACTION_PARTICIPATION_INDEX_NAMESPACE = SecureObjectNamespaceDefinition(
    key="transaction_participation_index",
    namespace="cadrumo.domain.modelos.participation_index",
    owner="cadrumo.domain.modelos",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{transaction_id}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
    custody_disposition=StorageCustodyDisposition.DERIVED_REBUILDABLE,
)
DOMAIN_NAMESPACE_DEFINITIONS = (
    BUCKET_EVENT_HISTORY_NAMESPACE,
    SUBMISSION_RECORDS_NAMESPACE,
    JUSTIFICANTE_METADATA_NAMESPACE,
    FILING_DRAFTS_NAMESPACE,
    FILING_AMENDMENTS_NAMESPACE,
    INVOICE_CATALOGUE_NAMESPACE,
    TRANSACTION_CATALOGUE_NAMESPACE,
    USAGE_RATIO_PROFILE_NAMESPACE,
    MODELO_WORK_UNIT_CATALOGUE_NAMESPACE,
    MODELO_VERIFICATION_REPORT_CATALOGUE_NAMESPACE,
    MODELO_FILING_RECORD_CATALOGUE_NAMESPACE,
    MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE,
    TRANSACTION_PARTICIPATION_INDEX_NAMESPACE,
)

STORAGE_PATH_DEFINITIONS = (
    StoragePathDefinition(
        key="bucket_root",
        kind=StoragePathKind.DIRECTORY,
        grammar="<root>/buckets/<bucket_id>/",
        owner="cadrumo.adapters.persistence.storage.bucket",
        segment=BUCKETS_DIRNAME,
    ),
    StoragePathDefinition(
        key="bucket_db",
        kind=StoragePathKind.DIRECTORY,
        grammar="<root>/buckets/<bucket_id>/db/",
        owner="cadrumo.adapters.persistence.storage.bucket",
        segment=BUCKET_DB_DIRNAME,
    ),
    StoragePathDefinition(
        key="bucket_blobs",
        kind=StoragePathKind.DIRECTORY,
        grammar="<root>/buckets/<bucket_id>/blobs/",
        owner="cadrumo.adapters.persistence.storage.bucket",
        segment=BUCKET_BLOBS_DIRNAME,
    ),
    StoragePathDefinition(
        key="bucket_audit",
        kind=StoragePathKind.DIRECTORY,
        grammar="<root>/buckets/<bucket_id>/audit/",
        owner="cadrumo.adapters.persistence.storage.bucket",
        segment=BUCKET_AUDIT_DIRNAME,
    ),
    StoragePathDefinition(
        key="bucket_manifest",
        kind=StoragePathKind.FILE,
        grammar="<root>/buckets/<bucket_id>/manifest.toml",
        owner="cadrumo.adapters.persistence.storage.bucket",
        segment=BUCKET_MANIFEST_FILENAME,
    ),
    StoragePathDefinition(
        key="bucket_lock",
        kind=StoragePathKind.FILE,
        grammar="<root>/buckets/<bucket_id>/.lock",
        owner="cadrumo.adapters.persistence.storage.bucket",
        segment=BUCKET_LOCK_FILENAME,
    ),
    StoragePathDefinition(
        key="bucket_output_language_hint",
        kind=StoragePathKind.FILE,
        grammar="<root>/buckets/<bucket_id>/output-language.hint",
        owner="cadrumo.adapters.persistence.storage.bucket",
        segment=BUCKET_OUTPUT_LANGUAGE_HINT_FILENAME,
    ),
    StoragePathDefinition(
        key="keystore_bucket",
        kind=StoragePathKind.DIRECTORY,
        grammar="<root>/keystore/<bucket_id>/",
        owner="cadrumo.adapters.persistence.storage.master_key",
        segment=KEYSTORE_DIRNAME,
    ),
    StoragePathDefinition(
        key="bucket_dek",
        kind=StoragePathKind.FILE,
        grammar="<root>/keystore/<bucket_id>/bucket.dek.json",
        owner="cadrumo.adapters.persistence.storage.master_key",
        segment=BUCKET_DEK_FILENAME,
    ),
    StoragePathDefinition(
        key="profile_session",
        kind=StoragePathKind.FILE,
        grammar="<root>/keystore/<bucket_id>/session.v1.json",
        owner="cadrumo.adapters.persistence.storage.master_key",
        segment=PROFILE_SESSION_FILENAME,
    ),
    StoragePathDefinition(
        key="login_throttle",
        kind=StoragePathKind.FILE,
        grammar="<root>/keystore/<bucket_id>/login-throttle.json",
        owner="cadrumo.adapters.persistence.storage.master_key",
        segment=LOGIN_THROTTLE_FILENAME,
    ),
    StoragePathDefinition(
        key="config_reset_journal",
        kind=StoragePathKind.FILE,
        grammar="<root>/reset-operations/<operation_id>.json",
        owner="cadrumo.application.config_reset",
        segment=CONFIG_RESET_JOURNAL_DIRNAME,
    ),
    StoragePathDefinition(
        key="secure_objects_table",
        kind=StoragePathKind.LOGICAL_SQL,
        grammar="db://secure_objects/<namespace>/<object_key>",
        owner="cadrumo.adapters.persistence.storage.sql",
    ),
    StoragePathDefinition(
        key="blob_manifest",
        kind=StoragePathKind.BLOB_OBJECT,
        grammar="<root>/blobs/<sha256[:2]>/<sha256>.manifest.json",
        owner="cadrumo.adapters.persistence.storage.blob_store",
        schema_version=BLOB_MANIFEST_SCHEMA_VERSION,
    ),
)

STORAGE_NAMESPACE_REGISTRY = StorageHierarchyRegistry(
    namespaces=(
        WORKFLOW_STATE_NAMESPACE,
        WORKFLOW_RUN_NAMESPACE,
        USER_PROFILE_VALUE_NAMESPACE,
        USER_PROFILE_SNAPSHOT_NAMESPACE,
        PROFILE_INVENTORY_LEDGER_NAMESPACE,
        PROFILE_ASSETS_LEDGER_NAMESPACE,
        PROFILE_ASSETS_AMORTIZATION_LEDGER_NAMESPACE,
        PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE,
        PROFILE_PRORRATA_REGISTER_NAMESPACE,
        REPAIR_INTEGRITY_DECISION_NAMESPACE,
        APPLICATION_FILING_HISTORY_NAMESPACE,
        AUTH_APODERADO_CONFIGURATION_NAMESPACE,
        CALCULATION_OBSERVATIONS_NAMESPACE,
        RETENCION_OBSERVATIONS_NAMESPACE,
        WITHHOLDING_OBSERVATIONS_NAMESPACE,
        IVA_WALLET_RECONCILIATION_DECISIONS_NAMESPACE,
        IVA_WALLET_RECONCILIATION_DECISION_EVENTS_NAMESPACE,
        MODELO_RECONCILIATION_RECORDS_NAMESPACE,
        IVA_COMPENSATION_HISTORY_NAMESPACE,
        LIVE_IVA_REMOTE_STATE_ACQUISITIONS_NAMESPACE,
        APPLICATION_EVIDENCE_BUNDLE_NAMESPACE,
        LEDGER_PURCHASE_INVOICE_EVIDENCE_NAMESPACE,
        LEDGER_BUSINESS_OPERATION_INVOICE_NAMESPACE,
        LEDGER_CLASSIFICATION_RULES_NAMESPACE,
        LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE,
        LIVE_M036_DECLARATION_NAMESPACE,
        M145_COMMUNICATION_RECORD_NAMESPACE,
        TEST_SNAPSHOT_BASE_PROBE_NAMESPACE,
        TEST_SESSION_LIFECYCLE_NAMESPACE,
        TEST_SECURE_BOUND_CONTRACT_NAMESPACE,
        TEST_RUNTIME_PROFILE_NAMESPACE,
        LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE,
        LIVE_NOTIFICATIONS_SNAPSHOT_NAMESPACE,
        LIVE_JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE,
        LIVE_VERIFY_OBSERVATION_NAMESPACE,
        ATTACHMENT_BLOB_NAMESPACE,
        ATTACHMENT_MANIFEST_NAMESPACE,
        AEAT_BROWSER_SESSION_NAMESPACE,
        CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE,
        GOOGLE_OAUTH_CLIENT_NAMESPACE,
        GOOGLE_OAUTH_TOKEN_NAMESPACE,
        GOOGLE_OAUTH_METADATA_NAMESPACE,
        GOOGLE_DRIVE_CONFIG_NAMESPACE,
        GOOGLE_CREDENTIAL_SOURCE_NAMESPACE,
        LLM_CACHE_NAMESPACE,
        LLM_USAGE_NAMESPACE,
        LLM_RUN_TELEMETRY_NAMESPACE,
        AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE,
        AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE,
        AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE,
        MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE,
        MODELO_REVIEW_PACKAGE_RECIPIENT_FINGERPRINT_REGISTRY_NAMESPACE,
        MODELO_REVIEW_PACKAGE_RECIPIENT_REPLAY_GUARD_NAMESPACE,
        MODELO_REVIEW_PACKAGE_RECIPIENT_ENCRYPTION_KEY_NAMESPACE,
        *DOMAIN_NAMESPACE_DEFINITIONS,
    ),
    paths=STORAGE_PATH_DEFINITIONS,
)

__all__ = [
    "AEAT_BROWSER_SESSION_NAMESPACE",
    "AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE",
    "AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE",
    "AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE",
    "APPLICATION_EVIDENCE_BUNDLE_NAMESPACE",
    "APPLICATION_FILING_HISTORY_NAMESPACE",
    "ATTACHMENT_BLOB_NAMESPACE",
    "ATTACHMENT_MANIFEST_NAMESPACE",
    "AUTH_APODERADO_CONFIGURATION_NAMESPACE",
    "BLOB_MANIFEST_SCHEMA_VERSION",
    "BUCKETS_DIRNAME",
    "BUCKET_AUDIT_DIRNAME",
    "BUCKET_BLOBS_DIRNAME",
    "BUCKET_DB_DIRNAME",
    "BUCKET_DEK_FILENAME",
    "BUCKET_LOCK_FILENAME",
    "BUCKET_MANIFEST_FILENAME",
    "CALCULATION_OBSERVATIONS_NAMESPACE",
    "CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE",
    "CONFIG_RESET_JOURNAL_DIRNAME",
    "DOMAIN_NAMESPACE_DEFINITIONS",
    "GOOGLE_CREDENTIAL_SOURCE_NAMESPACE",
    "GOOGLE_DRIVE_CONFIG_NAMESPACE",
    "GOOGLE_OAUTH_CLIENT_NAMESPACE",
    "GOOGLE_OAUTH_METADATA_NAMESPACE",
    "GOOGLE_OAUTH_TOKEN_NAMESPACE",
    "IVA_COMPENSATION_HISTORY_NAMESPACE",
    "IVA_WALLET_RECONCILIATION_DECISIONS_NAMESPACE",
    "IVA_WALLET_RECONCILIATION_DECISION_EVENTS_NAMESPACE",
    "KEYSTORE_DIRNAME",
    "LEDGER_BUSINESS_OPERATION_INVOICE_NAMESPACE",
    "LEDGER_CLASSIFICATION_RULES_NAMESPACE",
    "LEDGER_PURCHASE_INVOICE_EVIDENCE_NAMESPACE",
    "LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE",
    "LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE",
    "LIVE_IVA_REMOTE_STATE_ACQUISITIONS_NAMESPACE",
    "LIVE_JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE",
    "LIVE_M036_DECLARATION_NAMESPACE",
    "LIVE_NOTIFICATIONS_SNAPSHOT_NAMESPACE",
    "LIVE_VERIFY_OBSERVATION_NAMESPACE",
    "LLM_CACHE_NAMESPACE",
    "LLM_RUN_TELEMETRY_NAMESPACE",
    "LLM_USAGE_NAMESPACE",
    "LOGIN_THROTTLE_FILENAME",
    "M145_COMMUNICATION_RECORD_NAMESPACE",
    "MODELO_RECONCILIATION_RECORDS_NAMESPACE",
    "MODELO_REVIEW_PACKAGE_RECIPIENT_FINGERPRINT_REGISTRY_NAMESPACE",
    "MODELO_REVIEW_PACKAGE_RECIPIENT_REPLAY_GUARD_NAMESPACE",
    "MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE",
    "PROFILE_ASSETS_AMORTIZATION_LEDGER_NAMESPACE",
    "PROFILE_ASSETS_LEDGER_NAMESPACE",
    "PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE",
    "PROFILE_INVENTORY_LEDGER_NAMESPACE",
    "PROFILE_PRORRATA_REGISTER_NAMESPACE",
    "PROFILE_SESSION_FILENAME",
    "REPAIR_INTEGRITY_DECISION_NAMESPACE",
    "SECRET_RECORD_SCHEMA_VERSION",
    "SECURE_OBJECT_CATALOGUE_KEY",
    "SECURE_OBJECT_DEFAULT_KEY",
    "SECURE_OBJECT_SCHEMA_VERSION_V1",
    "SECURE_OBJECT_WORKFLOW_STATE_KEY",
    "STORAGE_NAMESPACE_REGISTRY",
    "STORAGE_PATH_DEFINITIONS",
    "TEST_SECURE_BOUND_CONTRACT_NAMESPACE",
    "TEST_SESSION_LIFECYCLE_NAMESPACE",
    "TEST_SNAPSHOT_BASE_PROBE_NAMESPACE",
    "USER_PROFILE_SNAPSHOT_NAMESPACE",
    "USER_PROFILE_VALUE_NAMESPACE",
    "WORKFLOW_RUN_NAMESPACE",
    "WORKFLOW_STATE_NAMESPACE",
    "SecureObjectNamespaceDefinition",
    "StorageCustodyDisposition",
    "StorageCustodyProfile",
    "StorageHierarchyRegistry",
    "StorageNamespaceScope",
    "StoragePathDefinition",
    "StoragePathKind",
    "StorageRemoteMirrorPolicy",
    "secure_object_logical_path",
    "secure_object_namespace_logical_path",
]
