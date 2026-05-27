"""Tests for the secure-storage namespace and hierarchy registry."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aeat.adapters.persistence.storage import (
    BLOB_MANIFEST_SCHEMA_VERSION,
    BUCKET_DB_DIRNAME,
    BUCKET_LOCK_FILENAME,
    BUCKET_MANIFEST_FILENAME,
    BUCKETS_DIRNAME,
    LIVE_CENSUS_SNAPSHOT_NAMESPACE,
    REPAIR_INTEGRITY_DECISION_NAMESPACE,
    SECURE_OBJECT_CATALOGUE_KEY,
    SECURE_OBJECT_WORKFLOW_STATE_KEY,
    STORAGE_NAMESPACE_REGISTRY,
    WORKFLOW_STATE_NAMESPACE,
    SecureObjectNamespaceDefinition,
    StorageNamespaceScope,
)
from aeat.core.classification import SensitivityClass

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def test_registry_rejects_duplicate_namespace_values() -> None:
    first = WORKFLOW_STATE_NAMESPACE
    duplicate = first.model_copy(update={"key": "workflow_state_duplicate"})

    with pytest.raises(ValidationError, match="duplicate secure-object namespace value"):
        type(STORAGE_NAMESPACE_REGISTRY)(namespaces=(first, duplicate), paths=())


def test_secure_object_registry_names_application_namespaces() -> None:
    census = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("live_census_snapshot")
    repair = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("repair_integrity_decisions")

    assert census == LIVE_CENSUS_SNAPSHOT_NAMESPACE
    assert census.sensitivity is SensitivityClass.IDENTITY
    assert census.object_key_grammar == "census-snapshot:{bucket_id}:{snapshot_id}"
    assert repair == REPAIR_INTEGRITY_DECISION_NAMESPACE
    assert repair.sensitivity is SensitivityClass.AUDIT
    assert repair.object_key_grammar == "{decision_id_sha256_hex}"


def test_singleton_object_keys_are_named_registry_values() -> None:
    workflow_state = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("workflow_state")
    invoice_catalogue = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("invoice_catalogue")

    assert workflow_state.require_default_object_key() == SECURE_OBJECT_WORKFLOW_STATE_KEY
    assert invoice_catalogue.require_default_object_key() == SECURE_OBJECT_CATALOGUE_KEY


def test_registry_path_definitions_name_persisted_hierarchy_segments() -> None:
    bucket_root = STORAGE_NAMESPACE_REGISTRY.path_by_key("bucket_root")
    bucket_db = STORAGE_NAMESPACE_REGISTRY.path_by_key("bucket_db")
    manifest = STORAGE_NAMESPACE_REGISTRY.path_by_key("bucket_manifest")
    lockfile = STORAGE_NAMESPACE_REGISTRY.path_by_key("bucket_lock")
    blob_manifest = STORAGE_NAMESPACE_REGISTRY.path_by_key("blob_manifest")

    assert bucket_root.segment == BUCKETS_DIRNAME
    assert bucket_db.segment == BUCKET_DB_DIRNAME
    assert manifest.segment == BUCKET_MANIFEST_FILENAME
    assert lockfile.segment == BUCKET_LOCK_FILENAME
    assert blob_manifest.schema_version == BLOB_MANIFEST_SCHEMA_VERSION


def test_namespace_definition_rejects_pathlike_namespaces() -> None:
    with pytest.raises(ValidationError, match="namespace must not contain path separators"):
        SecureObjectNamespaceDefinition(
            key="bad_namespace",
            namespace="aeat/bad",
            owner="aeat.test",
            sensitivity=SensitivityClass.AUDIT,
            schema_version=1,
            object_key_grammar="{id}",
            scope=StorageNamespaceScope.PROFILE_LOCAL,
        )
