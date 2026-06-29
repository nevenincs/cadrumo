"""Tests for the secure-storage namespace and hierarchy registry."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest
from pydantic import ValidationError

from .....core.classification import SensitivityClass
from .....core.errors import ERROR_REGISTRY, build_error_envelope
from .....tests._inventory import ast_for_path, package_python_files, repo_relative
from .. import (
    AEAT_BROWSER_SESSION_NAMESPACE,
    AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE,
    AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE,
    AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE,
    APPLICATION_EVIDENCE_BUNDLE_NAMESPACE,
    ATTACHMENT_BLOB_NAMESPACE,
    BLOB_MANIFEST_SCHEMA_VERSION,
    BUCKET_DB_DIRNAME,
    BUCKET_LOCK_FILENAME,
    BUCKET_MANIFEST_FILENAME,
    BUCKETS_DIRNAME,
    CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE,
    GOOGLE_DRIVE_CONFIG_NAMESPACE,
    GOOGLE_OAUTH_CLIENT_NAMESPACE,
    GOOGLE_OAUTH_METADATA_NAMESPACE,
    GOOGLE_OAUTH_TOKEN_NAMESPACE,
    LEDGER_BUSINESS_OPERATION_INVOICE_NAMESPACE,
    LEDGER_PURCHASE_INVOICE_EVIDENCE_NAMESPACE,
    LIVE_CENSO_SNAPSHOT_NAMESPACE,
    LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE,
    LIVE_JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE,
    LIVE_NOTIFICATIONS_SNAPSHOT_NAMESPACE,
    LIVE_VERIFY_OBSERVATION_NAMESPACE,
    LLM_CACHE_NAMESPACE,
    LLM_USAGE_NAMESPACE,
    PROFILE_ASSETS_AMORTIZATION_LEDGER_NAMESPACE,
    PROFILE_ASSETS_LEDGER_NAMESPACE,
    PROFILE_INVENTORY_LEDGER_NAMESPACE,
    REPAIR_INTEGRITY_DECISION_NAMESPACE,
    SECURE_OBJECT_CATALOGUE_KEY,
    SECURE_OBJECT_DEFAULT_KEY,
    SECURE_OBJECT_WORKFLOW_STATE_KEY,
    STORAGE_NAMESPACE_REGISTRY,
    TEST_SECURE_BOUND_CONTRACT_NAMESPACE,
    TEST_SESSION_LIFECYCLE_NAMESPACE,
    TEST_SNAPSHOT_BASE_PROBE_NAMESPACE,
    WORKFLOW_STATE_NAMESPACE,
    SecureObjectNamespaceDefinition,
    StorageHierarchyRegistry,
    StorageNamespaceScope,
    StorageRemoteMirrorPolicy,
)
from .._namespace_registry import (
    StoragePathDefinition,
    StoragePathKind,
    secure_object_logical_path,
    secure_object_namespace_logical_path,
)
from ..errors import NamespaceRegistryError

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_registry_rejects_duplicate_namespace_values() -> None:
    first = WORKFLOW_STATE_NAMESPACE
    duplicate = first.model_copy(update={"key": "workflow_state_duplicate"})

    with pytest.raises(ValidationError, match="duplicate secure-object namespace value"):
        type(STORAGE_NAMESPACE_REGISTRY)(namespaces=(first, duplicate), paths=())


def test_secure_object_registry_names_application_namespaces() -> None:
    censo = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("live_censo_snapshot")
    repair = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("repair_integrity_decisions")

    assert censo == LIVE_CENSO_SNAPSHOT_NAMESPACE
    assert censo.sensitivity is SensitivityClass.IDENTITY
    assert censo.object_key_grammar == "censo-snapshot:{bucket_id}:{snapshot_id}"
    assert repair == REPAIR_INTEGRITY_DECISION_NAMESPACE
    assert repair.sensitivity is SensitivityClass.AUDIT
    assert repair.object_key_grammar == "{decision_id_sha256_hex}"


def test_secure_object_registry_names_live_m036_declaration_namespace() -> None:
    """The M036 declarative-recording verbs
    persist operator declarations through this namespace. Authority:
    2026-06-03-m036-lifecycle-verbs-research.
    """
    from .._namespace_registry import LIVE_M036_DECLARATION_NAMESPACE

    declaration = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("live_m036_declaration")

    assert declaration == LIVE_M036_DECLARATION_NAMESPACE
    assert declaration.namespace == "aeat.application.modelo.m036_declaration"
    assert declaration.sensitivity is SensitivityClass.IDENTITY
    assert declaration.object_key_grammar == "m036-declaration:{bucket_id}:{declaration_id}"


def test_secure_object_registry_names_live_justificante_capture_namespace() -> None:
    """The live justificante-capture verb persists the pulled receipt
    through this bucket-scoped FINANCIAL namespace (live-justificante-reconcile decision).
    """
    capture = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("live_justificante_capture_snapshot")

    assert capture == LIVE_JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE
    assert capture.namespace == "aeat.application.live.justificante_capture_snapshot"
    assert capture.sensitivity is SensitivityClass.FINANCIAL
    assert capture.object_key_grammar == "justificante-capture-snapshot:{bucket_id}:{snapshot_id}"
    assert capture.scope is StorageNamespaceScope.BUCKET_LOCAL


def test_singleton_object_keys_are_named_registry_values() -> None:
    workflow_state = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("workflow_state")
    invoice_catalogue = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("invoice_catalogue")
    inventory_ledger = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("profile_inventory_ledger")

    assert workflow_state.require_default_object_key() == SECURE_OBJECT_WORKFLOW_STATE_KEY
    assert invoice_catalogue.require_default_object_key() == SECURE_OBJECT_CATALOGUE_KEY
    assert inventory_ledger.require_default_object_key() == SECURE_OBJECT_DEFAULT_KEY


def test_profile_ledger_namespaces_are_registered() -> None:
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


def test_profile_ledger_namespace_registration_coverage_is_present() -> None:
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
        "transaction_participation_index",
    } <= registered_keys


def test_transaction_participation_index_namespace_is_registered() -> None:
    registered = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("transaction_participation_index")

    assert registered.namespace == "aeat.domain.modelos.participation_index"
    assert registered.owner == "aeat.domain.modelos"
    assert registered.sensitivity is SensitivityClass.FINANCIAL
    assert registered.scope is StorageNamespaceScope.PROFILE_LOCAL
    assert registered.schema_version == 1
    assert registered.object_key_grammar == "{transaction_id}"


def test_auth_session_cache_remote_namespaces_are_registered() -> None:
    expected_contracts = {
        "aeat_browser_sessions": (
            AEAT_BROWSER_SESSION_NAMESPACE,
            "aeat.outbound.aeat.auth.sessions",
            SensitivityClass.SESSION,
            "{storage_state_path_posix}",
        ),
        "clave_movil_diagnostics": (
            CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE,
            "aeat.outbound.aeat.auth.clave_movil.diagnostics",
            SensitivityClass.SESSION,
            "{diagnostic_id_or_timestamp_iso}",
        ),
        "google_oauth_client": (
            GOOGLE_OAUTH_CLIENT_NAMESPACE,
            "aeat.google.oauth.client",
            SensitivityClass.SECRET,
            "{profile}",
        ),
        "google_oauth_token": (
            GOOGLE_OAUTH_TOKEN_NAMESPACE,
            "aeat.google.oauth.token",
            SensitivityClass.SECRET,
            "{profile}",
        ),
        "google_oauth_metadata": (
            GOOGLE_OAUTH_METADATA_NAMESPACE,
            "aeat.google.oauth.metadata",
            SensitivityClass.FINANCIAL,
            "{profile}",
        ),
        "google_drive_config": (
            GOOGLE_DRIVE_CONFIG_NAMESPACE,
            "aeat.google.drive.config",
            SensitivityClass.FINANCIAL,
            "{profile}",
        ),
        "llm_cache": (
            LLM_CACHE_NAMESPACE,
            "aeat.outbound.llm.cache",
            SensitivityClass.DIAGNOSTIC,
            "{logical_root}|{provider}|{model}|{prompt_hash}|{args_hash}",
        ),
        "llm_usage": (
            LLM_USAGE_NAMESPACE,
            "aeat.outbound.llm.usage",
            SensitivityClass.DIAGNOSTIC,
            "{logical_root}|{created_at_iso}|{request_id}|{uuid4_hex}",
        ),
        "aeat_filed_declaration_artefacts": (
            AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE,
            "aeat.outbound.aeat.sede.filed_declaration.artefacts",
            SensitivityClass.FINANCIAL,
            "{sha256_hex}",
        ),
        "aeat_filed_declaration_observations": (
            AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE,
            "aeat.outbound.aeat.sede.filed_declaration.observations",
            SensitivityClass.FINANCIAL,
            "{sha256(modelo,ejercicio,period,expediente_id)}",
        ),
        "aeat_iva_wallet_observations": (
            AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE,
            "aeat.outbound.aeat.sede.iva_compensation_wallet.observations",
            SensitivityClass.FINANCIAL,
            "{sha256(taxpayer_nif,target_year,target_period,captured_at)}",
        ),
        "application_evidence_bundles": (
            APPLICATION_EVIDENCE_BUNDLE_NAMESPACE,
            "aeat.application.evidence.bundles",
            SensitivityClass.AUDIT,
            "{bundle_id}",
        ),
        "ledger_purchase_invoice_evidence": (
            LEDGER_PURCHASE_INVOICE_EVIDENCE_NAMESPACE,
            "aeat.application.ledger.purchase_invoice_evidence",
            SensitivityClass.FINANCIAL,
            "{bucket_id}",
        ),
        "ledger_business_operation_invoices": (
            LEDGER_BUSINESS_OPERATION_INVOICE_NAMESPACE,
            "aeat.application.ledger.business_operation_invoices",
            SensitivityClass.FINANCIAL,
            "{bucket_id}:{source_kind}",
        ),
        "live_expedientes_snapshot": (
            LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE,
            "aeat.application.live.expedientes_snapshot",
            SensitivityClass.FINANCIAL,
            "expedientes-snapshot:{bucket_id}:{snapshot_id}",
        ),
        "live_notifications_snapshot": (
            LIVE_NOTIFICATIONS_SNAPSHOT_NAMESPACE,
            "aeat.application.live.notifications_snapshot",
            SensitivityClass.FINANCIAL,
            "notifications-snapshot:{bucket_id}:{snapshot_id}",
        ),
        "live_verify_observations": (
            LIVE_VERIFY_OBSERVATION_NAMESPACE,
            "aeat.application.live.verify_observations",
            SensitivityClass.IDENTITY,
            "verify-observation:{bucket_id}:{observation_id}",
        ),
        "test_snapshot_base_probe": (
            TEST_SNAPSHOT_BASE_PROBE_NAMESPACE,
            "aeat.application.live.test_snapshot_base_probe",
            SensitivityClass.FINANCIAL,
            "snapshot-base-probe:{bucket_id}:{snapshot_id}",
        ),
    }

    for key, (expected, namespace, sensitivity, object_key_grammar) in expected_contracts.items():
        registered = STORAGE_NAMESPACE_REGISTRY.namespace_by_key(key)

        assert registered == expected
        assert registered.namespace == namespace
        assert registered.sensitivity is sensitivity
        assert registered.schema_version == 1
        assert registered.object_key_grammar == object_key_grammar


def test_auth_session_cache_namespace_registration_coverage_is_present() -> None:
    registered_keys = {definition.key for definition in STORAGE_NAMESPACE_REGISTRY.namespaces}

    assert {
        "aeat_browser_sessions",
        "clave_movil_diagnostics",
        "google_oauth_client",
        "google_oauth_token",
        "google_oauth_metadata",
        "google_drive_config",
        "llm_cache",
        "llm_usage",
        "aeat_filed_declaration_artefacts",
        "aeat_filed_declaration_observations",
        "aeat_iva_wallet_observations",
        "application_evidence_bundles",
        "ledger_purchase_invoice_evidence",
        "ledger_business_operation_invoices",
        "live_expedientes_snapshot",
        "live_notifications_snapshot",
        "live_verify_observations",
        "test_snapshot_base_probe",
        "test_secure_bound_contract",
    } <= registered_keys


def test_secure_namespaces_default_to_ciphertext_remote_mirror_policy() -> None:
    production_namespaces = tuple(
        namespace for namespace in STORAGE_NAMESPACE_REGISTRY.namespaces if not namespace.key.startswith("test_")
    )

    assert production_namespaces
    assert all(
        namespace.remote_mirror_policy is StorageRemoteMirrorPolicy.CIPHERTEXT_WITH_METADATA
        for namespace in production_namespaces
    )
    assert all(namespace.remote_mirror_requires_revision for namespace in production_namespaces)
    assert all(namespace.remote_mirror_requires_integrity_manifest for namespace in production_namespaces)


def test_test_only_namespaces_do_not_require_remote_mirror_metadata() -> None:
    expected_namespaces = {
        "test_secure_bound_contract": TEST_SECURE_BOUND_CONTRACT_NAMESPACE,
        "test_snapshot_base_probe": TEST_SNAPSHOT_BASE_PROBE_NAMESPACE,
        "test_session_lifecycle": TEST_SESSION_LIFECYCLE_NAMESPACE,
    }

    for key, expected_namespace in expected_namespaces.items():
        namespace = STORAGE_NAMESPACE_REGISTRY.namespace_by_key(key)

        assert namespace == expected_namespace
        assert namespace.remote_mirror_policy is StorageRemoteMirrorPolicy.TEST_ONLY
        assert namespace.remote_mirror_requires_revision is False
        assert namespace.remote_mirror_requires_integrity_manifest is False


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


# ---------------------------------------------------------------------------
# contract: NamespaceRegistryError error-registry and real-behavior invariant tests
# ---------------------------------------------------------------------------


def test_namespace_registry_error_is_in_error_registry() -> None:
    assert "INTEGRITY_STORAGE_NAMESPACE_REGISTRY" in ERROR_REGISTRY


def test_namespace_registry_error_round_trips_through_build_error_envelope() -> None:
    err = NamespaceRegistryError("test invariant violation")
    envelope = build_error_envelope(err)
    assert envelope.code == "INTEGRITY_STORAGE_NAMESPACE_REGISTRY"
    assert envelope.category == "INTEGRITY"
    assert envelope.message


def _make_namespace_definition(**overrides: object) -> SecureObjectNamespaceDefinition:
    defaults: dict[str, object] = {
        "key": "test_key",
        "namespace": "aeat.test",
        "owner": "aeat.test",
        "sensitivity": SensitivityClass.AUDIT,
        "schema_version": 1,
        "object_key_grammar": "{id}",
        "scope": StorageNamespaceScope.PROFILE_LOCAL,
    }
    defaults.update(overrides)
    return SecureObjectNamespaceDefinition.model_validate(defaults)


def _assert_caused_by_namespace_registry_error(error: ValidationError) -> None:
    causes = [entry.get("ctx", {}).get("error") for entry in error.errors()]
    assert any(isinstance(cause, NamespaceRegistryError) for cause in causes)


@pytest.mark.parametrize(
    "overrides",
    (
        {"key": " whitespace_key "},
        {"key": "path/sep"},
        {"namespace": "aeat/bad"},
        {"namespace": " aeat.bad "},
        {"default_object_key": " bad "},
        {"default_object_key": "path/sep"},
    ),
    ids=(
        "key-whitespace",
        "key-path-separator",
        "namespace-path-separator",
        "namespace-whitespace",
        "default-key-whitespace",
        "default-key-path-separator",
    ),
)
def test_namespace_definition_invariant_violations_raise_namespace_registry_error(
    overrides: Mapping[str, object],
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        _make_namespace_definition(**overrides)

    _assert_caused_by_namespace_registry_error(exc_info.value)


@pytest.mark.parametrize(
    ("overrides", "expected_message"),
    (
        (
            {"remote_mirror_requires_revision": False},
            "ciphertext remote mirror namespaces require revision and integrity metadata",
        ),
        (
            {"remote_mirror_requires_integrity_manifest": False},
            "ciphertext remote mirror namespaces require revision and integrity metadata",
        ),
        (
            {"remote_mirror_policy": StorageRemoteMirrorPolicy.TEST_ONLY},
            "local-only and test-only namespaces must not require remote mirror metadata",
        ),
    ),
    ids=(
        "ciphertext-requires-revision",
        "ciphertext-requires-integrity-manifest",
        "test-only-rejects-metadata-requirements",
    ),
)
def test_namespace_definition_remote_mirror_policy_constraints_are_enforced(
    overrides: Mapping[str, object],
    expected_message: str,
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        _make_namespace_definition(**overrides)

    assert any(expected_message in str(error) for error in exc_info.value.errors())


def _make_path_definition(**overrides: object) -> StoragePathDefinition:
    defaults: dict[str, object] = {
        "key": "test_path",
        "kind": StoragePathKind.DIRECTORY,
        "grammar": "<root>/test/",
        "owner": "aeat.test",
    }
    defaults.update(overrides)
    return StoragePathDefinition.model_validate(defaults)


@pytest.mark.parametrize(
    "overrides",
    (
        {"key": " bad_key "},
        {"key": "path/sep"},
        {"segment": " bad_segment "},
        {"segment": "path/sep"},
    ),
    ids=(
        "key-whitespace",
        "key-path-separator",
        "segment-whitespace",
        "segment-path-separator",
    ),
)
def test_path_definition_invariant_violations_raise_namespace_registry_error(
    overrides: Mapping[str, object],
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        _make_path_definition(**overrides)

    _assert_caused_by_namespace_registry_error(exc_info.value)


def test_duplicate_namespace_keys_raise_namespace_registry_error() -> None:
    ns = _make_namespace_definition()
    with pytest.raises(ValidationError) as exc_info:
        StorageHierarchyRegistry(namespaces=(ns, ns), paths=())
    errors = exc_info.value.errors()
    assert any("duplicate secure-object namespace registry key" in str(e) for e in errors)


def test_duplicate_namespace_values_raise_namespace_registry_error() -> None:
    ns1 = _make_namespace_definition(key="key_a")
    ns2 = _make_namespace_definition(key="key_b")
    with pytest.raises(ValidationError) as exc_info:
        StorageHierarchyRegistry(namespaces=(ns1, ns2), paths=())
    errors = exc_info.value.errors()
    assert any("duplicate secure-object namespace value" in str(e) for e in errors)


def test_duplicate_path_keys_raise_namespace_registry_error() -> None:
    path = StoragePathDefinition(
        key="dup_path",
        kind=StoragePathKind.DIRECTORY,
        grammar="<root>/dup/",
        owner="aeat.test",
    )
    with pytest.raises(ValidationError) as exc_info:
        StorageHierarchyRegistry(namespaces=(), paths=(path, path))
    errors = exc_info.value.errors()
    assert any("duplicate storage path registry key" in str(e) for e in errors)


def test_secure_object_logical_path_uses_registered_sql_grammar() -> None:
    path_definition = STORAGE_NAMESPACE_REGISTRY.path_by_key("secure_objects_table")

    marker = secure_object_logical_path("aeat.persistence.profile.assets", "default")

    assert path_definition.kind is StoragePathKind.LOGICAL_SQL
    assert path_definition.grammar == "db://secure_objects/<namespace>/<object_key>"
    assert marker.as_posix() == "db:/secure_objects/aeat.persistence.profile.assets/default"


def test_secure_object_namespace_logical_path_uses_registered_sql_grammar() -> None:
    path_definition = STORAGE_NAMESPACE_REGISTRY.path_by_key("secure_objects_table")

    marker = secure_object_namespace_logical_path("aeat.domain.attachments.blobs")

    assert path_definition.kind is StoragePathKind.LOGICAL_SQL
    assert path_definition.grammar == "db://secure_objects/<namespace>/<object_key>"
    assert marker.as_posix() == "db:/secure_objects/aeat.domain.attachments.blobs"


def test_every_discovered_production_secure_object_namespace_is_registered() -> None:
    registered = {definition.namespace for definition in STORAGE_NAMESPACE_REGISTRY.namespaces}
    discovered = _discover_production_secure_object_namespaces()

    assert {
        ATTACHMENT_BLOB_NAMESPACE.namespace,
        GOOGLE_OAUTH_CLIENT_NAMESPACE.namespace,
        WORKFLOW_STATE_NAMESPACE.namespace,
        "aeat.domain.transactions.bucket",
        AEAT_BROWSER_SESSION_NAMESPACE.namespace,
    } <= discovered
    assert sorted(discovered - registered) == []


_SECURE_OBJECT_METHODS = {
    "delete",
    "exists",
    "exists_by_raw_key",
    "iter_namespace_decryptability",
    "iter_records_with_failures",
    "list_keys",
    "list_object_keys",
    "list_records",
    "load",
    "peek_metadata",
    "probe_namespace_integrity",
    "save",
    "save_many",
    "save_with_raw_key",
}

_SECURE_BOUND_CLASS_NAMES = {
    "SecureBoundRepository",
    "_SecureBoundRepository",
}


def _discover_production_secure_object_namespaces() -> set[str]:
    namespaces: set[str] = set()
    for path in _iter_aeat_production_sources():
        tree = ast_for_path(path)
        assert tree is not None, f"{repo_relative(path)} must be parseable"
        bindings = _collect_namespace_value_bindings(tree)
        namespaces.update(_namespace_values_from_assignments(tree, bindings))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                namespaces.update(_namespace_values_from_call(node, bindings))
    return namespaces


def _iter_aeat_production_sources() -> tuple[Path, ...]:
    return tuple(
        sorted(
            path
            for path in package_python_files(include_data=True)
            if not _is_test_surface(path) and path.name != "_namespace_registry.py"
        ),
    )


def _is_test_surface(path: Path) -> bool:
    relative = repo_relative(path)
    return (
        path.name.startswith("test_")
        or path.name == "conftest.py"
        or "/test_" in relative
        or relative.startswith("src/aeat/tests/")
    )


def _collect_namespace_value_bindings(tree: ast.AST) -> dict[str, str]:
    bindings = _collect_imported_registry_namespace_bindings(tree)
    # Strictly monotonic fixed-point: each pass may only add new bindings,
    # never overwrite. Without this, two competing assignments to the same
    # *NAMESPACE identifier (e.g. shadowed in conditional branches) cause
    # the original rebind-on-mismatch loop to oscillate forever.
    max_passes = 64
    for _ in range(max_passes):
        discovered = False
        for node in ast.walk(tree):
            targets, value = _assignment_parts(node)
            if value is None:
                continue
            resolved = _resolve_namespace_value(value, bindings)
            if resolved is None:
                continue
            for target in targets:
                if not isinstance(target, ast.Name) or "NAMESPACE" not in target.id:
                    continue
                if target.id not in bindings:
                    bindings[target.id] = resolved
                    discovered = True
        if not discovered:
            return bindings
    raise RuntimeError(
        "namespace-binding fixed point did not converge within "
        f"{max_passes} passes; suspect cyclic NAMESPACE assignments in scanned module",
    )


def _namespace_values_from_assignments(tree: ast.AST, bindings: dict[str, str]) -> set[str]:
    values: set[str] = set()
    for node in ast.walk(tree):
        targets, value = _assignment_parts(node)
        if value is None:
            continue
        resolved = _resolve_namespace_value(value, bindings)
        if resolved is None:
            continue
        for target in targets:
            name = _target_name(target)
            if name is not None and _is_namespace_target_name(name):
                values.add(resolved)
    return values


def _collect_imported_registry_namespace_bindings(tree: ast.AST) -> dict[str, str]:
    storage_exports = __import__("aeat.adapters.persistence.storage", fromlist=["*"])
    namespace_by_export = {
        name: value.namespace
        for name, value in vars(storage_exports).items()
        if isinstance(value, SecureObjectNamespaceDefinition)
    }
    bindings: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not _is_storage_namespace_import(node):
            continue
        for alias in node.names:
            if alias.name in namespace_by_export:
                bindings[alias.asname or alias.name] = namespace_by_export[alias.name]
    return bindings


def _is_storage_namespace_import(node: ast.ImportFrom) -> bool:
    return node.module in {
        "aeat.adapters.persistence.storage",
        "aeat.adapters.persistence.storage._namespace_registry",
        "_namespace_registry",
    } or (
        node.level > 0
        and node.module
        in {
            "adapters.persistence.storage",
            "adapters.persistence.storage._namespace_registry",
            "persistence.storage",
            "persistence.storage._namespace_registry",
            "_namespace_registry",
        }
    )


def _assignment_parts(node: ast.AST) -> tuple[list[ast.expr], ast.expr | None]:
    if isinstance(node, ast.Assign):
        return list(node.targets), node.value
    if isinstance(node, ast.AnnAssign):
        return [node.target], node.value
    return [], None


def _resolve_namespace_value(node: ast.expr, bindings: dict[str, str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith("aeat."):
        return node.value
    if isinstance(node, ast.Name):
        return bindings.get(node.id)
    if isinstance(node, ast.Attribute) and node.attr == "namespace" and isinstance(node.value, ast.Name):
        return bindings.get(node.value.id)
    return None


def _namespace_values_from_call(node: ast.Call, bindings: dict[str, str]) -> set[str]:
    values: set[str] = set()
    call_name = _call_name(node.func)
    if call_name in _SECURE_OBJECT_METHODS:
        for keyword in node.keywords:
            if keyword.arg != "namespace":
                continue
            resolved = _resolve_namespace_value(keyword.value, bindings)
            if resolved is not None:
                values.add(resolved)
    if call_name in _SECURE_OBJECT_METHODS and node.args:
        resolved = _resolve_namespace_value(node.args[0], bindings)
        if resolved is not None:
            values.add(resolved)
    if call_name in _SECURE_BOUND_CLASS_NAMES:
        for keyword in node.keywords:
            if keyword.arg != "namespace":
                continue
            resolved = _resolve_namespace_value(keyword.value, bindings)
            if resolved is not None:
                values.add(resolved)
    return values


def _target_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _is_namespace_target_name(name: str) -> bool:
    return name == "namespace" or name.endswith("_NAMESPACE")


def _is_namespace_constant_name(name: str) -> bool:
    return name == "namespace" or "NAMESPACE" in name


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""
