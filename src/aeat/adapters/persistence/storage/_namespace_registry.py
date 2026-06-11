"""Typed registry for secure-storage namespace and hierarchy contracts.

Each :class:`SecureObjectNamespaceDefinition` carries a
:class:`SensitivityClass` field that governs the at-rest encryption
treatment applied by the substrate for every object in that namespace.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator

from ....core._models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ....core.classification import SensitivityClass
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
KEYSTORE_DIRNAME = "keystore"
BUCKET_DEK_FILENAME = "bucket.dek.json"
BLOB_MANIFEST_SCHEMA_VERSION = 1
SECRET_RECORD_SCHEMA_VERSION = 1
_SECURE_OBJECTS_TABLE_PATH_KEY = "secure_objects_table"


class StorageNamespaceScope(StrEnum):
    """Logical custody scope for a secure-object namespace."""

    PROFILE_LOCAL = "profile_local"
    BUCKET_LOCAL = "bucket_local"
    PROCESS_LOCAL = "process_local"


class StorageRemoteMirrorPolicy(StrEnum):
    """Remote-provider mirroring policy for one secure-object namespace."""

    CIPHERTEXT_WITH_METADATA = "ciphertext_with_metadata"
    LOCAL_ONLY = "local_only"
    TEST_ONLY = "test_only"


class StoragePathKind(StrEnum):
    """Persistent storage hierarchy node kind."""

    DIRECTORY = "directory"
    FILE = "file"
    LOGICAL_SQL = "logical_sql"
    BLOB_OBJECT = "blob_object"


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
    namespace="aeat.workflow",
    owner="aeat.application.workflow",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="state",
    default_object_key=SECURE_OBJECT_WORKFLOW_STATE_KEY,
    scope=StorageNamespaceScope.BUCKET_LOCAL,
)
WORKFLOW_RUN_NAMESPACE = SecureObjectNamespaceDefinition(
    key="workflow_runs",
    namespace="aeat.application.workflow.runs",
    owner="aeat.application.workflow",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{run_id}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
)
USER_PROFILE_VALUE_NAMESPACE = SecureObjectNamespaceDefinition(
    key="user_profile_value",
    namespace="aeat.application.user_profile.value",
    owner="aeat.application.user_profile",
    sensitivity=SensitivityClass.IDENTITY,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="user-profile:{profile_id}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
)
USER_PROFILE_SNAPSHOT_NAMESPACE = SecureObjectNamespaceDefinition(
    key="user_profile_snapshot",
    namespace="aeat.application.user_profile.snapshot",
    owner="aeat.application.user_profile",
    sensitivity=SensitivityClass.IDENTITY,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="user-profile-snapshot:{profile_id}:{snapshot_id}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
)
PROFILE_INVENTORY_LEDGER_NAMESPACE = SecureObjectNamespaceDefinition(
    key="profile_inventory_ledger",
    namespace="aeat.persistence.profile.inventory",
    owner="aeat.adapters.persistence.profile.inventory",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="default",
    default_object_key=SECURE_OBJECT_DEFAULT_KEY,
    scope=StorageNamespaceScope.BUCKET_LOCAL,
)
PROFILE_ASSETS_LEDGER_NAMESPACE = SecureObjectNamespaceDefinition(
    key="profile_assets_ledger",
    namespace="aeat.persistence.profile.assets",
    owner="aeat.adapters.persistence.profile.assets",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="default",
    default_object_key=SECURE_OBJECT_DEFAULT_KEY,
    scope=StorageNamespaceScope.BUCKET_LOCAL,
)
PROFILE_ASSETS_AMORTIZATION_LEDGER_NAMESPACE = SecureObjectNamespaceDefinition(
    key="profile_assets_amortization_ledger",
    namespace="aeat.persistence.profile.assets.amortization",
    owner="aeat.adapters.persistence.profile.assets",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="default",
    default_object_key=SECURE_OBJECT_DEFAULT_KEY,
    scope=StorageNamespaceScope.BUCKET_LOCAL,
)
REPAIR_INTEGRITY_DECISION_NAMESPACE = SecureObjectNamespaceDefinition(
    key="repair_integrity_decisions",
    namespace="aeat.application.repair_integrity.decisions",
    owner="aeat.application.repair_integrity",
    sensitivity=SensitivityClass.AUDIT,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{decision_id_sha256_hex}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
)
APPLICATION_FILING_HISTORY_NAMESPACE = SecureObjectNamespaceDefinition(
    key="application_filing_history",
    namespace="aeat.application.filing.history",
    owner="aeat.application.filing",
    sensitivity=SensitivityClass.AUDIT,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{modelo}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
)
AUTH_APODERADO_CONFIGURATION_NAMESPACE = SecureObjectNamespaceDefinition(
    key="auth_apoderado_configuration",
    namespace="aeat.auth.apoderado",
    owner="aeat.application.auth",
    sensitivity=SensitivityClass.IDENTITY,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{bucket_id}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
)
CALCULATION_OBSERVATIONS_NAMESPACE = SecureObjectNamespaceDefinition(
    key="calculation_observations",
    namespace="aeat.calculations.observations",
    owner="aeat.application.calculations",
    sensitivity=SensitivityClass.AUDIT,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{modelo}:{filing_year}:{period}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
)
IVA_WALLET_RECONCILIATION_DECISIONS_NAMESPACE = SecureObjectNamespaceDefinition(
    key="iva_wallet_reconciliation_decisions",
    namespace="aeat.calculations.iva_wallet.reconciliation_decisions",
    owner="aeat.application.calculations",
    sensitivity=SensitivityClass.AUDIT,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="iva-wallet-decision:{sha256(taxpayer_nif,target_year,target_period)}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
)
IVA_WALLET_RECONCILIATION_DECISION_EVENTS_NAMESPACE = SecureObjectNamespaceDefinition(
    key="iva_wallet_reconciliation_decision_events",
    namespace="aeat.calculations.iva_wallet.reconciliation_decision_events",
    owner="aeat.application.calculations",
    sensitivity=SensitivityClass.AUDIT,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="iva-wallet-decision-event:{sha256(decision_identity_and_payload)}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
)
IVA_COMPENSATION_HISTORY_NAMESPACE = SecureObjectNamespaceDefinition(
    key="iva_compensation_history",
    namespace="aeat.calculations.iva_compensation.history",
    owner="aeat.application.calculations",
    sensitivity=SensitivityClass.AUDIT,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="303:{filing_year}:{period}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
)
LIVE_IVA_REMOTE_STATE_ACQUISITIONS_NAMESPACE = SecureObjectNamespaceDefinition(
    key="live_iva_remote_state_acquisitions",
    namespace="aeat.application.live.iva_remote_state_acquisitions",
    owner="aeat.application.live",
    sensitivity=SensitivityClass.AUDIT,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar=(
        "live-iva-acquisition:{target_year}:{target_period}:{timestamp}:{sha256(redacted_manifest_seed)}"
    ),
    scope=StorageNamespaceScope.PROFILE_LOCAL,
)
APPLICATION_EVIDENCE_BUNDLE_NAMESPACE = SecureObjectNamespaceDefinition(
    key="application_evidence_bundles",
    namespace="aeat.application.evidence.bundles",
    owner="aeat.application.evidence",
    sensitivity=SensitivityClass.AUDIT,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{bundle_id}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
)
LEDGER_PURCHASE_INVOICE_EVIDENCE_NAMESPACE = SecureObjectNamespaceDefinition(
    key="ledger_purchase_invoice_evidence",
    namespace="aeat.application.ledger.purchase_invoice_evidence",
    owner="aeat.application.ledger",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{bucket_id}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
)
LEDGER_BUSINESS_OPERATION_INVOICE_NAMESPACE = SecureObjectNamespaceDefinition(
    key="ledger_business_operation_invoices",
    namespace="aeat.application.ledger.business_operation_invoices",
    owner="aeat.application.ledger",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{bucket_id}:{source_kind}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
)
LEDGER_CLASSIFICATION_RULES_NAMESPACE = SecureObjectNamespaceDefinition(
    key="ledger_classification_rules",
    namespace="aeat.ledger.classification.rules",
    owner="aeat.application.ledger",
    sensitivity=SensitivityClass.AUDIT,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{rule_id}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
)
LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE = SecureObjectNamespaceDefinition(
    key="live_borrador_100_snapshot",
    namespace="aeat.application.live.borrador_100_snapshot",
    owner="aeat.application.live",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="modelo-100-borrador-snapshot:{bucket_id}:{snapshot_id}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
)
LIVE_CENSO_SNAPSHOT_NAMESPACE = SecureObjectNamespaceDefinition(
    key="live_censo_snapshot",
    namespace="aeat.application.live.censo_snapshot",
    owner="aeat.application.live",
    sensitivity=SensitivityClass.IDENTITY,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="censo-snapshot:{bucket_id}:{snapshot_id}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
)
LIVE_M036_DECLARATION_NAMESPACE = SecureObjectNamespaceDefinition(
    key="live_m036_declaration",
    namespace="aeat.application.modelo.m036_declaration",
    owner="aeat.application.modelo",
    sensitivity=SensitivityClass.IDENTITY,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="m036-declaration:{bucket_id}:{declaration_id}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
)
TEST_SNAPSHOT_BASE_PROBE_NAMESPACE = SecureObjectNamespaceDefinition(
    key="test_snapshot_base_probe",
    namespace="aeat.application.live.test_snapshot_base_probe",
    owner="aeat.application.live",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="snapshot-base-probe:{bucket_id}:{snapshot_id}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    remote_mirror_policy=StorageRemoteMirrorPolicy.TEST_ONLY,
    remote_mirror_requires_revision=False,
    remote_mirror_requires_integrity_manifest=False,
)
TEST_SESSION_LIFECYCLE_NAMESPACE = SecureObjectNamespaceDefinition(
    key="test_session_lifecycle",
    namespace="aeat.test.session.lifecycle",
    owner="aeat.entrypoints.cli.test_session_lifecycle_roundtrip",
    sensitivity=SensitivityClass.OPERATIONAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="roundtrip-row",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    remote_mirror_policy=StorageRemoteMirrorPolicy.TEST_ONLY,
    remote_mirror_requires_revision=False,
    remote_mirror_requires_integrity_manifest=False,
)
TEST_SECURE_BOUND_CONTRACT_NAMESPACE = SecureObjectNamespaceDefinition(
    key="test_secure_bound_contract",
    namespace="aeat.test.envelope.secure_bound_contract_dummy",
    owner="aeat.adapters.persistence.storage.envelope.test_secure_bound_repository_contract",
    sensitivity=SensitivityClass.AUDIT,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{id}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    remote_mirror_policy=StorageRemoteMirrorPolicy.TEST_ONLY,
    remote_mirror_requires_revision=False,
    remote_mirror_requires_integrity_manifest=False,
)
TEST_RUNTIME_PROFILE_NAMESPACE = SecureObjectNamespaceDefinition(
    key="test_runtime_profile",
    namespace="aeat.tests.runtime.profile",
    owner="aeat.tests.test_secure_sql",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="runtime-row",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    remote_mirror_policy=StorageRemoteMirrorPolicy.TEST_ONLY,
    remote_mirror_requires_revision=False,
    remote_mirror_requires_integrity_manifest=False,
)
LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE = SecureObjectNamespaceDefinition(
    key="live_expedientes_snapshot",
    namespace="aeat.application.live.expedientes_snapshot",
    owner="aeat.application.live",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="expedientes-snapshot:{bucket_id}:{snapshot_id}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
)
LIVE_NOTIFICATIONS_SNAPSHOT_NAMESPACE = SecureObjectNamespaceDefinition(
    key="live_notifications_snapshot",
    namespace="aeat.application.live.notifications_snapshot",
    owner="aeat.application.live",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="notifications-snapshot:{bucket_id}:{snapshot_id}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
)
LIVE_JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE = SecureObjectNamespaceDefinition(
    key="live_justificante_capture_snapshot",
    namespace="aeat.application.live.justificante_capture_snapshot",
    owner="aeat.application.live",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="justificante-capture-snapshot:{bucket_id}:{snapshot_id}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
)
LIVE_VERIFY_OBSERVATION_NAMESPACE = SecureObjectNamespaceDefinition(
    key="live_verify_observations",
    namespace="aeat.application.live.verify_observations",
    owner="aeat.application.live",
    sensitivity=SensitivityClass.IDENTITY,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="verify-observation:{bucket_id}:{observation_id}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
)
ATTACHMENT_BLOB_NAMESPACE = SecureObjectNamespaceDefinition(
    key="attachment_blobs",
    namespace="aeat.domain.attachments.blobs",
    owner="aeat.adapters.persistence.storage.attachment",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{sha256_hex}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
)
ATTACHMENT_MANIFEST_NAMESPACE = SecureObjectNamespaceDefinition(
    key="attachment_manifests",
    namespace="aeat.domain.attachments.manifests",
    owner="aeat.adapters.persistence.storage.attachment",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{attachment_id_sha256_hex}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
)
AEAT_BROWSER_SESSION_NAMESPACE = SecureObjectNamespaceDefinition(
    key="aeat_browser_sessions",
    namespace="aeat.outbound.aeat.auth.sessions",
    owner="aeat.adapters.outbound.aeat.auth",
    sensitivity=SensitivityClass.SESSION,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{storage_state_path_posix}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
)
CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE = SecureObjectNamespaceDefinition(
    key="clave_movil_diagnostics",
    namespace="aeat.outbound.aeat.auth.clave_movil.diagnostics",
    owner="aeat.adapters.outbound.aeat.auth",
    sensitivity=SensitivityClass.SESSION,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{diagnostic_id_or_timestamp_iso}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
)
GOOGLE_OAUTH_CLIENT_NAMESPACE = SecureObjectNamespaceDefinition(
    key="google_oauth_client",
    namespace="aeat.google.oauth.client",
    owner="aeat.adapters.outbound.google",
    sensitivity=SensitivityClass.SECRET,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{profile}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
)
GOOGLE_OAUTH_TOKEN_NAMESPACE = SecureObjectNamespaceDefinition(
    key="google_oauth_token",
    namespace="aeat.google.oauth.token",
    owner="aeat.adapters.outbound.google",
    sensitivity=SensitivityClass.SECRET,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{profile}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
)
GOOGLE_OAUTH_METADATA_NAMESPACE = SecureObjectNamespaceDefinition(
    key="google_oauth_metadata",
    namespace="aeat.google.oauth.metadata",
    owner="aeat.adapters.outbound.google",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{profile}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
)
GOOGLE_DRIVE_CONFIG_NAMESPACE = SecureObjectNamespaceDefinition(
    key="google_drive_config",
    namespace="aeat.google.drive.config",
    owner="aeat.adapters.outbound.google",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{profile}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
)
LLM_CACHE_NAMESPACE = SecureObjectNamespaceDefinition(
    key="llm_cache",
    namespace="aeat.outbound.llm.cache",
    owner="aeat.adapters.outbound.llm",
    sensitivity=SensitivityClass.DIAGNOSTIC,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{logical_root}|{provider}|{model}|{prompt_hash}|{args_hash}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
)
LLM_USAGE_NAMESPACE = SecureObjectNamespaceDefinition(
    key="llm_usage",
    namespace="aeat.outbound.llm.usage",
    owner="aeat.adapters.outbound.llm",
    sensitivity=SensitivityClass.DIAGNOSTIC,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{logical_root}|{created_at_iso}|{request_id}|{uuid4_hex}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
)
AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE = SecureObjectNamespaceDefinition(
    key="aeat_filed_declaration_artefacts",
    namespace="aeat.outbound.aeat.sede.filed_declaration.artefacts",
    owner="aeat.adapters.outbound.aeat.sede",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{sha256_hex}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
)
AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE = SecureObjectNamespaceDefinition(
    key="aeat_filed_declaration_observations",
    namespace="aeat.outbound.aeat.sede.filed_declaration.observations",
    owner="aeat.adapters.outbound.aeat.sede",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{sha256(modelo,ejercicio,period,expediente_id)}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
)
AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE = SecureObjectNamespaceDefinition(
    key="aeat_iva_wallet_observations",
    namespace="aeat.outbound.aeat.sede.iva_compensation_wallet.observations",
    owner="aeat.adapters.outbound.aeat.sede",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="{sha256(taxpayer_nif,target_year,target_period,captured_at)}",
    scope=StorageNamespaceScope.PROFILE_LOCAL,
)

DOMAIN_NAMESPACE_DEFINITIONS = (
    SecureObjectNamespaceDefinition(
        key="bucket_event_history",
        namespace="aeat.domain.buckets.event_history",
        owner="aeat.domain.buckets",
        sensitivity=SensitivityClass.FINANCIAL,
        schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
        object_key_grammar="catalogue",
        default_object_key=SECURE_OBJECT_CATALOGUE_KEY,
        scope=StorageNamespaceScope.PROFILE_LOCAL,
    ),
    SecureObjectNamespaceDefinition(
        key="submission_records",
        namespace="aeat.domain.submission.records",
        owner="aeat.domain.submission",
        sensitivity=SensitivityClass.AUDIT,
        schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
        object_key_grammar="{submission_id}",
        scope=StorageNamespaceScope.PROFILE_LOCAL,
    ),
    SecureObjectNamespaceDefinition(
        key="justificante_metadata",
        namespace="aeat.domain.justificante.metadata",
        owner="aeat.domain.justificante",
        sensitivity=SensitivityClass.AUDIT,
        schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
        object_key_grammar="{csv}",
        scope=StorageNamespaceScope.PROFILE_LOCAL,
    ),
    SecureObjectNamespaceDefinition(
        key="filing_drafts",
        namespace="aeat.domain.filing.drafts",
        owner="aeat.domain.filing",
        sensitivity=SensitivityClass.FINANCIAL,
        schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
        object_key_grammar="{draft_id}",
        scope=StorageNamespaceScope.PROFILE_LOCAL,
    ),
    SecureObjectNamespaceDefinition(
        key="filing_amendments",
        namespace="aeat.domain.filing.amendments",
        owner="aeat.domain.filing",
        sensitivity=SensitivityClass.AUDIT,
        schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
        object_key_grammar="{amendment_id}",
        scope=StorageNamespaceScope.PROFILE_LOCAL,
    ),
    SecureObjectNamespaceDefinition(
        key="invoice_catalogue",
        namespace="aeat.domain.invoices",
        owner="aeat.domain.invoices",
        sensitivity=SensitivityClass.FINANCIAL,
        schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
        object_key_grammar="catalogue",
        default_object_key=SECURE_OBJECT_CATALOGUE_KEY,
        scope=StorageNamespaceScope.PROFILE_LOCAL,
    ),
    SecureObjectNamespaceDefinition(
        key="transaction_catalogue",
        namespace="aeat.domain.transactions.bucket",
        owner="aeat.domain.transactions",
        sensitivity=SensitivityClass.FINANCIAL,
        schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
        object_key_grammar="transaction-catalogue:{bucket_id}",
        scope=StorageNamespaceScope.BUCKET_LOCAL,
    ),
    SecureObjectNamespaceDefinition(
        key="usage_ratio_profile",
        namespace="aeat.domain.usage_ratios",
        owner="aeat.domain.usage_ratios",
        sensitivity=SensitivityClass.FINANCIAL,
        schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
        object_key_grammar="profile:{bucket_id}",
        scope=StorageNamespaceScope.BUCKET_LOCAL,
    ),
    SecureObjectNamespaceDefinition(
        key="modelo_work_unit_catalogue",
        namespace="aeat.domain.modelos.work_units",
        owner="aeat.domain.modelos",
        sensitivity=SensitivityClass.FINANCIAL,
        schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
        object_key_grammar="catalogue",
        default_object_key=SECURE_OBJECT_CATALOGUE_KEY,
        scope=StorageNamespaceScope.PROFILE_LOCAL,
    ),
    SecureObjectNamespaceDefinition(
        key="modelo_verification_report_catalogue",
        namespace="aeat.domain.modelos.verification_reports",
        owner="aeat.domain.modelos",
        sensitivity=SensitivityClass.FINANCIAL,
        schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
        object_key_grammar="catalogue",
        default_object_key=SECURE_OBJECT_CATALOGUE_KEY,
        scope=StorageNamespaceScope.PROFILE_LOCAL,
    ),
    SecureObjectNamespaceDefinition(
        key="modelo_filing_record_catalogue",
        namespace="aeat.domain.modelos.filing_records",
        owner="aeat.domain.modelos",
        sensitivity=SensitivityClass.FINANCIAL,
        schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
        object_key_grammar="catalogue",
        default_object_key=SECURE_OBJECT_CATALOGUE_KEY,
        scope=StorageNamespaceScope.PROFILE_LOCAL,
    ),
    SecureObjectNamespaceDefinition(
        key="modelo_calculation_revision_catalogue",
        namespace="aeat.domain.modelos.calculation_revisions",
        owner="aeat.domain.modelos",
        sensitivity=SensitivityClass.FINANCIAL,
        schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
        object_key_grammar="catalogue",
        default_object_key=SECURE_OBJECT_CATALOGUE_KEY,
        scope=StorageNamespaceScope.PROFILE_LOCAL,
    ),
    SecureObjectNamespaceDefinition(
        key="transaction_participation_index",
        namespace="aeat.domain.modelos.participation_index",
        owner="aeat.domain.modelos",
        sensitivity=SensitivityClass.FINANCIAL,
        schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
        object_key_grammar="{transaction_id}",
        scope=StorageNamespaceScope.PROFILE_LOCAL,
    ),
)

STORAGE_PATH_DEFINITIONS = (
    StoragePathDefinition(
        key="bucket_root",
        kind=StoragePathKind.DIRECTORY,
        grammar="<root>/buckets/<bucket_id>/",
        owner="aeat.adapters.persistence.storage.bucket",
        segment=BUCKETS_DIRNAME,
    ),
    StoragePathDefinition(
        key="bucket_db",
        kind=StoragePathKind.DIRECTORY,
        grammar="<root>/buckets/<bucket_id>/db/",
        owner="aeat.adapters.persistence.storage.bucket",
        segment=BUCKET_DB_DIRNAME,
    ),
    StoragePathDefinition(
        key="bucket_blobs",
        kind=StoragePathKind.DIRECTORY,
        grammar="<root>/buckets/<bucket_id>/blobs/",
        owner="aeat.adapters.persistence.storage.bucket",
        segment=BUCKET_BLOBS_DIRNAME,
    ),
    StoragePathDefinition(
        key="bucket_audit",
        kind=StoragePathKind.DIRECTORY,
        grammar="<root>/buckets/<bucket_id>/audit/",
        owner="aeat.adapters.persistence.storage.bucket",
        segment=BUCKET_AUDIT_DIRNAME,
    ),
    StoragePathDefinition(
        key="bucket_manifest",
        kind=StoragePathKind.FILE,
        grammar="<root>/buckets/<bucket_id>/manifest.toml",
        owner="aeat.adapters.persistence.storage.bucket",
        segment=BUCKET_MANIFEST_FILENAME,
    ),
    StoragePathDefinition(
        key="bucket_lock",
        kind=StoragePathKind.FILE,
        grammar="<root>/buckets/<bucket_id>/.lock",
        owner="aeat.adapters.persistence.storage.bucket",
        segment=BUCKET_LOCK_FILENAME,
    ),
    StoragePathDefinition(
        key="keystore_bucket",
        kind=StoragePathKind.DIRECTORY,
        grammar="<root>/keystore/<bucket_id>/",
        owner="aeat.adapters.persistence.storage.master_key",
        segment=KEYSTORE_DIRNAME,
    ),
    StoragePathDefinition(
        key="bucket_dek",
        kind=StoragePathKind.FILE,
        grammar="<root>/keystore/<bucket_id>/bucket.dek.json",
        owner="aeat.adapters.persistence.storage.master_key",
        segment=BUCKET_DEK_FILENAME,
    ),
    StoragePathDefinition(
        key="secure_objects_table",
        kind=StoragePathKind.LOGICAL_SQL,
        grammar="db://secure_objects/<namespace>/<object_key>",
        owner="aeat.adapters.persistence.storage.sql",
    ),
    StoragePathDefinition(
        key="blob_manifest",
        kind=StoragePathKind.BLOB_OBJECT,
        grammar="<root>/blobs/<sha256[:2]>/<sha256>.manifest.json",
        owner="aeat.adapters.persistence.storage.blob_store",
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
        REPAIR_INTEGRITY_DECISION_NAMESPACE,
        APPLICATION_FILING_HISTORY_NAMESPACE,
        AUTH_APODERADO_CONFIGURATION_NAMESPACE,
        CALCULATION_OBSERVATIONS_NAMESPACE,
        IVA_WALLET_RECONCILIATION_DECISIONS_NAMESPACE,
        IVA_WALLET_RECONCILIATION_DECISION_EVENTS_NAMESPACE,
        IVA_COMPENSATION_HISTORY_NAMESPACE,
        LIVE_IVA_REMOTE_STATE_ACQUISITIONS_NAMESPACE,
        APPLICATION_EVIDENCE_BUNDLE_NAMESPACE,
        LEDGER_PURCHASE_INVOICE_EVIDENCE_NAMESPACE,
        LEDGER_BUSINESS_OPERATION_INVOICE_NAMESPACE,
        LEDGER_CLASSIFICATION_RULES_NAMESPACE,
        LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE,
        LIVE_CENSO_SNAPSHOT_NAMESPACE,
        LIVE_M036_DECLARATION_NAMESPACE,
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
        LLM_CACHE_NAMESPACE,
        LLM_USAGE_NAMESPACE,
        AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE,
        AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE,
        AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE,
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
    "DOMAIN_NAMESPACE_DEFINITIONS",
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
    "LIVE_CENSO_SNAPSHOT_NAMESPACE",
    "LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE",
    "LIVE_IVA_REMOTE_STATE_ACQUISITIONS_NAMESPACE",
    "LIVE_JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE",
    "LIVE_M036_DECLARATION_NAMESPACE",
    "LIVE_NOTIFICATIONS_SNAPSHOT_NAMESPACE",
    "LIVE_VERIFY_OBSERVATION_NAMESPACE",
    "LLM_CACHE_NAMESPACE",
    "LLM_USAGE_NAMESPACE",
    "PROFILE_ASSETS_AMORTIZATION_LEDGER_NAMESPACE",
    "PROFILE_ASSETS_LEDGER_NAMESPACE",
    "PROFILE_INVENTORY_LEDGER_NAMESPACE",
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
    "StorageHierarchyRegistry",
    "StorageNamespaceScope",
    "StoragePathDefinition",
    "StoragePathKind",
    "StorageRemoteMirrorPolicy",
    "secure_object_logical_path",
    "secure_object_namespace_logical_path",
]
