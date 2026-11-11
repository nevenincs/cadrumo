"""Process-local secure-object namespaces that only test suites write.

Each registration keeps its persisted identity and is registered by the
namespace registry alongside the product namespaces; its remote mirror policy
is test-only, so no mirror ever publishes these rows.
"""

from __future__ import annotations

from ....core.classification.policies import SensitivityClass
from .namespace_taxonomy import (
    StorageCustodyDisposition,
    StorageNamespaceScope,
    StorageRemoteMirrorPolicy,
)
from .secure_object_namespaces import SECURE_OBJECT_SCHEMA_VERSION_V1, SecureObjectNamespaceDefinition

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
    owner="cadrumo.entrypoints.cli.tests.test_session_lifecycle_roundtrip",
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
    owner="cadrumo.adapters.persistence.storage.envelope.tests.test_secure_bound_repository_contract",
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
    owner="cadrumo.adapters.persistence.storage.tests.test_secure_sql",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1,
    object_key_grammar="runtime-row",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    custody_disposition=StorageCustodyDisposition.PROCESS_LOCAL,
    remote_mirror_policy=StorageRemoteMirrorPolicy.TEST_ONLY,
    remote_mirror_requires_revision=False,
    remote_mirror_requires_integrity_manifest=False,
)
