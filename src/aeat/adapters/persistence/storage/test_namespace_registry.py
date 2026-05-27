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
    PROFILE_ASSETS_AMORTIZATION_LEDGER_NAMESPACE,
    PROFILE_ASSETS_LEDGER_NAMESPACE,
    PROFILE_INVENTORY_LEDGER_NAMESPACE,
    REPAIR_INTEGRITY_DECISION_NAMESPACE,
    SECURE_OBJECT_CATALOGUE_KEY,
    SECURE_OBJECT_DEFAULT_KEY,
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
    inventory_ledger = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("profile_inventory_ledger")

    assert workflow_state.require_default_object_key() == SECURE_OBJECT_WORKFLOW_STATE_KEY
    assert invoice_catalogue.require_default_object_key() == SECURE_OBJECT_CATALOGUE_KEY
    assert inventory_ledger.require_default_object_key() == SECURE_OBJECT_DEFAULT_KEY


def test_profile_ledger_namespaces_are_registered_for_w03_s21() -> None:
    inventory = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("profile_inventory_ledger")
    assets = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("profile_assets_ledger")
    amortization = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("profile_assets_amortization_ledger")

    assert inventory == PROFILE_INVENTORY_LEDGER_NAMESPACE
    assert inventory.namespace == "aeat.persistence.profile.inventory"
    assert inventory.sensitivity is SensitivityClass.FINANCIAL
    assert inventory.schema_version == 1
    assert inventory.require_default_object_key() == "default"

    assert assets == PROFILE_ASSETS_LEDGER_NAMESPACE
    assert assets.namespace == "aeat.persistence.profile.assets"
    assert assets.sensitivity is SensitivityClass.FINANCIAL
    assert assets.require_default_object_key() == "default"

    assert amortization == PROFILE_ASSETS_AMORTIZATION_LEDGER_NAMESPACE
    assert amortization.namespace == "aeat.persistence.profile.assets.amortization"
    assert amortization.sensitivity is SensitivityClass.FINANCIAL
    assert amortization.require_default_object_key() == "default"


def test_w03_s21_namespace_registration_coverage_is_present() -> None:
    registered_keys = {definition.key for definition in STORAGE_NAMESPACE_REGISTRY.namespaces}

    assert {
        "profile_inventory_ledger",
        "profile_assets_ledger",
        "profile_assets_amortization_ledger",
        "ledger_classification_rules",
        "invoice_catalogue",
        "application_filing_history",
        "filing_drafts",
        "filing_amendments",
        "iva_wallet_reconciliation_decisions",
        "iva_wallet_reconciliation_decision_events",
        "iva_compensation_history",
        "calculation_observations",
        "modelo_calculation_revision_catalogue",
    } <= registered_keys


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
