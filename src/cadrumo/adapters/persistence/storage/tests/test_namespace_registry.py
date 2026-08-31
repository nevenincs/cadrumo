"""Tests for the secure-storage namespace and hierarchy registry."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest
from pydantic import ValidationError

from .....core import StorageCustodyProfile
from .....core.classification import SensitivityClass
from .....core.errors.error_codes import ERROR_REGISTRY, build_error_envelope
from .....core.product_identity import PRODUCT_IDENTITY
from .....tests import (
    ast_for_path,
    leaf_name,
    package_python_files,
    repo_relative,
)
from .. import (
    AEAT_BROWSER_SESSION_NAMESPACE,
    AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE,
    AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE,
    AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE,
    APPLICATION_EVIDENCE_BUNDLE_NAMESPACE,
    ATTACHMENT_BLOB_NAMESPACE,
    ATTACHMENT_MANIFEST_NAMESPACE,
    BLOB_MANIFEST_SCHEMA_VERSION,
    BUCKET_DB_DIRNAME,
    BUCKET_EVENT_HISTORY_NAMESPACE,
    BUCKET_LOCK_FILENAME,
    BUCKET_MANIFEST_FILENAME,
    BUCKETS_DIRNAME,
    CALCULATION_OBSERVATIONS_NAMESPACE,
    CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE,
    GOOGLE_DRIVE_CONFIG_NAMESPACE,
    GOOGLE_OAUTH_CLIENT_NAMESPACE,
    GOOGLE_OAUTH_METADATA_NAMESPACE,
    GOOGLE_OAUTH_TOKEN_NAMESPACE,
    INVOICE_CATALOGUE_NAMESPACE,
    IVA_COMPENSATION_HISTORY_NAMESPACE,
    IVA_WALLET_RECONCILIATION_DECISION_EVENTS_NAMESPACE,
    IVA_WALLET_RECONCILIATION_DECISIONS_NAMESPACE,
    LEDGER_PURCHASE_INVOICE_EVIDENCE_NAMESPACE,
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
    TEST_SECURE_BOUND_CONTRACT_NAMESPACE,
    TEST_SESSION_LIFECYCLE_NAMESPACE,
    TEST_SNAPSHOT_BASE_PROBE_NAMESPACE,
    TRANSACTION_PARTICIPATION_INDEX_NAMESPACE,
    WORKFLOW_STATE_NAMESPACE,
    SecureObjectNamespaceDefinition,
    StorageCustodyDisposition,
    StorageHierarchyRegistry,
    StorageNamespaceScope,
    StorageRemoteMirrorPolicy,
)
from .._namespace_registry import (
    STORAGE_NAMESPACE_REGISTRY,
    secure_object_logical_path,
    secure_object_namespace_logical_path,
)
from .._namespace_taxonomy import StoragePathAnchor, StoragePathKind
from .._storage_path_definitions import StoragePathDefinition
from ..errors import NamespaceRegistryError

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_secure_object_registry_names_application_namespaces() -> None:
    expedientes = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("live_expedientes_snapshot")
    repair = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("repair_integrity_decisions")

    assert expedientes == LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE
    assert repair == REPAIR_INTEGRITY_DECISION_NAMESPACE
    assert repair.sensitivity is SensitivityClass.AUDIT
    assert repair.object_key_grammar == "{decision_id_sha256_hex}"


def test_secure_object_registry_names_live_m036_declaration_namespace() -> None:
    """The M036 declarative-recording verbs
    persist operator declarations through this namespace.
    """
    from .._secure_object_namespaces import LIVE_M036_DECLARATION_NAMESPACE

    declaration = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("live_m036_declaration")

    assert declaration == LIVE_M036_DECLARATION_NAMESPACE
    assert declaration.namespace == "cadrumo.application.modelo.m036_declaration"
    assert declaration.sensitivity is SensitivityClass.IDENTITY
    assert declaration.object_key_grammar == "m036-declaration:{bucket_id}:{declaration_id}"


def test_secure_object_registry_names_m145_communication_record_namespace() -> None:
    """Modelo 145 local communication records persist through this namespace."""
    from .. import M145_COMMUNICATION_RECORD_NAMESPACE

    record = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("m145_communication_record")

    assert record == M145_COMMUNICATION_RECORD_NAMESPACE
    assert record.namespace == "cadrumo.application.modelo.m145_communication_record"
    assert record.sensitivity is SensitivityClass.FINANCIAL
    assert record.object_key_grammar == "m145-communication:{bucket_id}:{communication_record_id}"
    assert record.scope is StorageNamespaceScope.BUCKET_LOCAL


def test_secure_object_registry_names_live_justificante_capture_namespace() -> None:
    """The live justificante-capture verb persists the pulled receipt
    through this bucket-scoped FINANCIAL namespace (live-justificante-reconcile decision).
    """
    capture = STORAGE_NAMESPACE_REGISTRY.namespace_by_key("live_justificante_capture_snapshot")

    assert capture == LIVE_JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE
    assert capture.namespace == "cadrumo.application.live.justificante_capture_snapshot"
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
    assert inventory.namespace == "cadrumo.persistence.profile.inventory"
    assert inventory.sensitivity is SensitivityClass.FINANCIAL
    assert inventory.schema_version == 1
    assert inventory.require_default_object_key() == "default"

    assert assets == PROFILE_ASSETS_LEDGER_NAMESPACE
    assert assets.namespace == "cadrumo.persistence.profile.assets"
    assert assets.sensitivity is SensitivityClass.FINANCIAL
    assert assets.require_default_object_key() == "default"

    assert amortization == PROFILE_ASSETS_AMORTIZATION_LEDGER_NAMESPACE
    assert amortization.namespace == "cadrumo.persistence.profile.assets.amortization"
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

    assert registered.namespace == "cadrumo.domain.modelos.participation_index"
    assert registered.owner == "cadrumo.domain.modelos"
    assert registered.sensitivity is SensitivityClass.FINANCIAL
    assert registered.scope is StorageNamespaceScope.PROFILE_LOCAL
    assert registered.schema_version == 1
    assert registered.object_key_grammar == "{transaction_id}"
    assert registered.custody_disposition is StorageCustodyDisposition.DERIVED_REBUILDABLE


def test_modelo_catalogue_namespaces_pin_their_persisted_addresses() -> None:
    """The four modelo catalogue namespaces pin their on-disk storage addresses.

    A namespace string is the address previously-written rows live at, and a
    schema version is the envelope contract, so neither may drift silently: an
    edit orphans persisted envelopes rather than failing loudly. These four
    carried a second copy of both values in their domain modules, which acted as
    an incidental pin until the duplicate authority was removed. This test is the
    deliberate pin that replaces it, alongside the singleton catalogue object key
    each of the four addresses its single row by.
    """
    from .. import (
        MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE,
        MODELO_FILING_RECORD_CATALOGUE_NAMESPACE,
        MODELO_VERIFICATION_REPORT_CATALOGUE_NAMESPACE,
        MODELO_WORK_UNIT_CATALOGUE_NAMESPACE,
    )

    # Each address is pinned with its OWN schema version rather than a shared
    # literal. The four no longer sit at one version -- the calculation-revision
    # catalogue has bumped -- and collapsing that back to a single expected
    # value would make a correct per-namespace bump red for the wrong reason.
    # The pin stays per namespace, so a bump still requires a deliberate edit
    # here, which is the tripwire this test exists to be.
    expected_addresses = {
        MODELO_WORK_UNIT_CATALOGUE_NAMESPACE: ("cadrumo.domain.modelos.work_units", 1),
        MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE: ("cadrumo.domain.modelos.calculation_revisions", 4),
        MODELO_FILING_RECORD_CATALOGUE_NAMESPACE: ("cadrumo.domain.modelos.filing_records", 1),
        MODELO_VERIFICATION_REPORT_CATALOGUE_NAMESPACE: ("cadrumo.domain.modelos.verification_reports", 1),
    }

    for definition, (namespace, schema_version) in expected_addresses.items():
        assert definition.namespace == namespace
        assert definition.schema_version == schema_version, (
            f"{namespace} changed its envelope contract from {schema_version} to "
            f"{definition.schema_version}; a version is the contract previously written "
            "rows were stamped under, so confirm the bump is intended and update this pin"
        )
        assert definition.require_default_object_key() == SECURE_OBJECT_CATALOGUE_KEY
        assert definition.sensitivity is SensitivityClass.FINANCIAL
        # Each must resolve from the registry under its own key, so a definition
        # cannot satisfy this test while being absent from the authority set.
        assert STORAGE_NAMESPACE_REGISTRY.namespace_by_key(definition.key) is definition

    # The four are distinct addresses; a copy-paste collapsing two would pass
    # every per-definition assertion above.
    assert len({namespace for namespace, _ in expected_addresses.values()}) == 4


def test_every_registered_namespace_declares_explicit_custody_disposition() -> None:
    missing = [
        definition.key
        for definition in STORAGE_NAMESPACE_REGISTRY.namespaces
        if "custody_disposition" not in definition.model_fields_set
    ]

    assert missing == []
    assert {definition.custody_disposition for definition in STORAGE_NAMESPACE_REGISTRY.namespaces} <= set(
        StorageCustodyDisposition,
    )


def test_every_namespace_owner_resolves_to_a_real_module() -> None:
    """Every ``owner`` must name a module that still exists.

    The prefix assertion below checks only that an owner *starts with*
    ``cadrumo.``, which a relocated module keeps satisfying after its real path
    changes. Two rows had already rotted that way -- the test-topology refactor
    moved both modules under a ``tests/`` package and updated the importers but
    not these strings, because a string is a data consumer and no import breaks.
    Storage-namespace ownership is the record of who is accountable for a body
    of encrypted operator data, so a row naming a module that no longer exists
    reports an owner nobody can be held to.
    """
    unresolvable = [
        definition.owner
        for definition in STORAGE_NAMESPACE_REGISTRY.namespaces
        if definition.owner.startswith("cadrumo.") and not _module_exists(definition.owner)
    ]

    assert unresolvable == [], f"namespace owners naming modules that do not exist: {sorted(set(unresolvable))}"


def _module_exists(dotted_path: str) -> bool:
    """Report whether ``dotted_path`` is importable without importing it."""
    try:
        return importlib.util.find_spec(dotted_path) is not None
    except (ImportError, ValueError):
        # A parent package that does not exist raises rather than returning
        # None, which is the same answer for this gate's purposes.
        return False


def test_every_namespace_row_uses_cadrumo_owners_and_preserves_six_authority_segments() -> None:
    """Ownership and authority-segment invariants hold for every registered row.

    Deliberately gates on the PROPERTY, never on the row tally. This test
    asserted ``len(definitions) == 67`` and its name carried the same number,
    so adding a sixty-eighth namespace reddened it for no reason the assertion
    was written to catch. A count encodes the moment it was written, trains
    everyone to bump the constant, and then detects nothing — the registry is
    expected to grow, and growth is not the defect. What must hold at every
    size is that each row is cadrumo-owned and that the AEAT authority segments
    stay exactly as enumerated below.
    """
    definitions = STORAGE_NAMESPACE_REGISTRY.namespaces

    assert definitions, "the namespace registry must not be empty"
    assert all(
        definition.namespace.startswith(("cadrumo.", "cadrumo-test.", "cadrumo-tests.")) for definition in definitions
    )
    assert all(
        definition.owner.startswith(("cadrumo.", "cadrumo-test.", "cadrumo-tests.")) for definition in definitions
    )
    assert not any(
        definition.namespace.startswith(("aeat.", "aeat-test.", "aeat-tests.")) for definition in definitions
    )
    assert {
        (definition.key, definition.namespace, definition.owner)
        for definition in definitions
        if ".aeat." in definition.namespace
    } == {
        ("aeat_browser_sessions", "cadrumo.outbound.aeat.auth.sessions", "cadrumo.adapters.outbound.aeat.auth"),
        (
            "clave_movil_diagnostics",
            "cadrumo.outbound.aeat.auth.clave_movil.diagnostics",
            "cadrumo.adapters.outbound.aeat.auth",
        ),
        (
            "aeat_filed_declaration_artefacts",
            "cadrumo.outbound.aeat.sede.filed_declaration.artefacts",
            "cadrumo.adapters.outbound.aeat.sede",
        ),
        (
            "aeat_filed_declaration_observations",
            "cadrumo.outbound.aeat.sede.filed_declaration.observations",
            "cadrumo.adapters.outbound.aeat.sede",
        ),
        (
            "aeat_iva_wallet_observations",
            "cadrumo.outbound.aeat.sede.iva_compensation_wallet.observations",
            "cadrumo.adapters.outbound.aeat.sede",
        ),
    }


def test_custody_profile_projection_matches_bucket_custody_worked_examples() -> None:
    full_namespaces = STORAGE_NAMESPACE_REGISTRY.namespaces_for_custody_profile(StorageCustodyProfile.FULL)
    structured_namespaces = STORAGE_NAMESPACE_REGISTRY.namespaces_for_custody_profile(
        StorageCustodyProfile.STRUCTURED,
    )
    full_keys = {definition.key for definition in full_namespaces}
    structured_keys = {definition.key for definition in structured_namespaces}

    cross_period_keys = {
        CALCULATION_OBSERVATIONS_NAMESPACE.key,
        IVA_COMPENSATION_HISTORY_NAMESPACE.key,
        IVA_WALLET_RECONCILIATION_DECISIONS_NAMESPACE.key,
        IVA_WALLET_RECONCILIATION_DECISION_EVENTS_NAMESPACE.key,
    }
    evidence_keys = {
        ATTACHMENT_BLOB_NAMESPACE.key,
        ATTACHMENT_MANIFEST_NAMESPACE.key,
        APPLICATION_EVIDENCE_BUNDLE_NAMESPACE.key,
        LEDGER_PURCHASE_INVOICE_EVIDENCE_NAMESPACE.key,
    }

    assert cross_period_keys <= full_keys
    assert cross_period_keys <= structured_keys
    assert evidence_keys <= full_keys
    assert evidence_keys.isdisjoint(structured_keys)
    assert INVOICE_CATALOGUE_NAMESPACE.key in full_keys
    assert INVOICE_CATALOGUE_NAMESPACE.key in structured_keys
    assert BUCKET_EVENT_HISTORY_NAMESPACE.key in full_keys
    assert BUCKET_EVENT_HISTORY_NAMESPACE.key not in structured_keys
    assert TRANSACTION_PARTICIPATION_INDEX_NAMESPACE.key not in full_keys
    assert TRANSACTION_PARTICIPATION_INDEX_NAMESPACE.key not in structured_keys


def test_auth_session_cache_remote_namespaces_are_registered() -> None:
    expected_contracts = {
        "aeat_browser_sessions": (
            AEAT_BROWSER_SESSION_NAMESPACE,
            "cadrumo.outbound.aeat.auth.sessions",
            SensitivityClass.SESSION,
            "{storage_state_path_posix}",
        ),
        "clave_movil_diagnostics": (
            CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE,
            "cadrumo.outbound.aeat.auth.clave_movil.diagnostics",
            SensitivityClass.SESSION,
            "{diagnostic_id_or_timestamp_iso}",
        ),
        "google_oauth_client": (
            GOOGLE_OAUTH_CLIENT_NAMESPACE,
            "cadrumo.google.oauth.client",
            SensitivityClass.SECRET,
            "{profile}",
        ),
        "google_oauth_token": (
            GOOGLE_OAUTH_TOKEN_NAMESPACE,
            "cadrumo.google.oauth.token",
            SensitivityClass.SECRET,
            "{profile}",
        ),
        "google_oauth_metadata": (
            GOOGLE_OAUTH_METADATA_NAMESPACE,
            "cadrumo.google.oauth.metadata",
            SensitivityClass.FINANCIAL,
            "{profile}",
        ),
        "google_drive_config": (
            GOOGLE_DRIVE_CONFIG_NAMESPACE,
            "cadrumo.google.drive.config",
            SensitivityClass.FINANCIAL,
            "{profile}",
        ),
        "llm_cache": (
            LLM_CACHE_NAMESPACE,
            "cadrumo.outbound.llm.cache",
            SensitivityClass.DIAGNOSTIC,
            "{logical_root}|{provider}|{model}|{prompt_hash}|{args_hash}",
        ),
        "llm_usage": (
            LLM_USAGE_NAMESPACE,
            "cadrumo.outbound.llm.usage",
            SensitivityClass.DIAGNOSTIC,
            "{logical_root}|{created_at_iso}|{request_id}|{uuid4_hex}",
        ),
        "aeat_filed_declaration_artefacts": (
            AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE,
            "cadrumo.outbound.aeat.sede.filed_declaration.artefacts",
            SensitivityClass.FINANCIAL,
            "{sha256_hex}",
        ),
        "aeat_filed_declaration_observations": (
            AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE,
            "cadrumo.outbound.aeat.sede.filed_declaration.observations",
            SensitivityClass.FINANCIAL,
            "{sha256(modelo,ejercicio,period,expediente_id)}",
        ),
        "aeat_iva_wallet_observations": (
            AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE,
            "cadrumo.outbound.aeat.sede.iva_compensation_wallet.observations",
            SensitivityClass.FINANCIAL,
            "{sha256(taxpayer_nif,target_year,target_period,captured_at)}",
        ),
        "application_evidence_bundles": (
            APPLICATION_EVIDENCE_BUNDLE_NAMESPACE,
            "cadrumo.application.evidence.bundles",
            SensitivityClass.AUDIT,
            "{bundle_id}",
        ),
        "ledger_purchase_invoice_evidence": (
            LEDGER_PURCHASE_INVOICE_EVIDENCE_NAMESPACE,
            "cadrumo.application.ledger.purchase_invoice_evidence",
            SensitivityClass.FINANCIAL,
            "{bucket_id}",
        ),
        "live_expedientes_snapshot": (
            LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE,
            "cadrumo.application.live.expedientes_snapshot",
            SensitivityClass.FINANCIAL,
            "expedientes-snapshot:{bucket_id}:{snapshot_id}",
        ),
        "live_notifications_snapshot": (
            LIVE_NOTIFICATIONS_SNAPSHOT_NAMESPACE,
            "cadrumo.application.live.notifications_snapshot",
            SensitivityClass.FINANCIAL,
            "notifications-snapshot:{bucket_id}:{snapshot_id}",
        ),
        "live_verify_observations": (
            LIVE_VERIFY_OBSERVATION_NAMESPACE,
            "cadrumo.application.live.verify_observations",
            SensitivityClass.IDENTITY,
            "verify-observation:{bucket_id}:{observation_id}",
        ),
        "test_snapshot_base_probe": (
            TEST_SNAPSHOT_BASE_PROBE_NAMESPACE,
            "cadrumo.application.live.test_snapshot_base_probe",
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
    lockfile = STORAGE_NAMESPACE_REGISTRY.path_by_key("bucket_lock")
    blob_manifest = STORAGE_NAMESPACE_REGISTRY.path_by_key("blob_manifest")

    assert bucket_root.segment == BUCKETS_DIRNAME
    assert bucket_db.segment == BUCKET_DB_DIRNAME
    assert lockfile.segment == BUCKET_LOCK_FILENAME
    assert blob_manifest.schema_version == BLOB_MANIFEST_SCHEMA_VERSION


def test_the_retired_plaintext_manifest_has_no_path_definition() -> None:
    """The retirement is asserted, not merely left as an absence.

    A member that simply stops being declared is indistinguishable from one
    nobody got around to declaring -- which is the confusion that let this
    manifest sit half-retired, its reader deleted while the hierarchy still
    declared it as a live format. Naming the absence means re-adding a
    definition is a deliberate act that fails here first.
    """
    with pytest.raises(KeyError):
        STORAGE_NAMESPACE_REGISTRY.path_by_key("bucket_manifest")
    assert BUCKET_MANIFEST_FILENAME not in {path.segment for path in STORAGE_NAMESPACE_REGISTRY.paths}


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
        "namespace": "aeat-test",
        "owner": "aeat-test",
        "sensitivity": SensitivityClass.AUDIT,
        "schema_version": 1,
        "object_key_grammar": "{id}",
        "scope": StorageNamespaceScope.PROFILE_LOCAL,
        "custody_disposition": StorageCustodyDisposition.STRUCTURED_CUSTODY,
    }
    defaults.update(overrides)
    return SecureObjectNamespaceDefinition.model_validate(defaults)


def _assert_caused_by_namespace_registry_error(error: ValidationError, case_id: str) -> None:
    causes = [entry.get("ctx", {}).get("error") for entry in error.errors()]
    assert any(isinstance(cause, NamespaceRegistryError) for cause in causes), case_id


def test_namespace_definition_invariant_violations_raise_namespace_registry_error() -> None:
    cases: tuple[tuple[str, dict[str, object], str], ...] = (
        ("key-whitespace", {"key": " whitespace_key "}, "registry key must not carry surrounding whitespace"),
        ("key-path-separator", {"key": "path/sep"}, "registry key must be a storage-safe slug"),
        ("namespace-path-separator", {"namespace": "aeat/bad"}, "namespace must not contain path separators"),
        ("namespace-whitespace", {"namespace": " aeat.bad "}, "namespace must not carry surrounding whitespace"),
        (
            "default-key-whitespace",
            {"default_object_key": " bad "},
            "default object key must not carry surrounding whitespace",
        ),
        (
            "default-key-path-separator",
            {"default_object_key": "path/sep"},
            "default object key must not contain path separators",
        ),
    )

    for case_id, overrides, expected_message in cases:
        with pytest.raises(ValidationError) as exc_info:
            _make_namespace_definition(**overrides)

        errors = exc_info.value.errors()
        _assert_caused_by_namespace_registry_error(exc_info.value, case_id)
        assert any(expected_message in str(error) for error in errors), case_id


def test_namespace_definition_remote_mirror_policy_constraints_are_enforced() -> None:
    cases: tuple[tuple[str, dict[str, object], str], ...] = (
        (
            "ciphertext-requires-revision",
            {"remote_mirror_requires_revision": False},
            "ciphertext remote mirror namespaces require revision and integrity metadata",
        ),
        (
            "ciphertext-requires-integrity-manifest",
            {"remote_mirror_requires_integrity_manifest": False},
            "ciphertext remote mirror namespaces require revision and integrity metadata",
        ),
        (
            "test-only-rejects-metadata-requirements",
            {"remote_mirror_policy": StorageRemoteMirrorPolicy.TEST_ONLY},
            "local-only and test-only namespaces must not require remote mirror metadata",
        ),
    )

    for case_id, overrides, expected_message in cases:
        with pytest.raises(ValidationError) as exc_info:
            _make_namespace_definition(**overrides)

        assert any(expected_message in str(error) for error in exc_info.value.errors()), case_id


def _make_path_definition(**overrides: object) -> StoragePathDefinition:
    defaults: dict[str, object] = {
        "key": "test_path",
        "kind": StoragePathKind.DIRECTORY,
        "grammar": "<root>/test/",
        "owner": "aeat-test",
        "anchor": StoragePathAnchor.STORAGE_ROOT,
    }
    defaults.update(overrides)
    return StoragePathDefinition.model_validate(defaults)


def test_path_definition_invariant_violations_raise_namespace_registry_error() -> None:
    cases: tuple[tuple[str, dict[str, object], str], ...] = (
        ("key-whitespace", {"key": " bad_key "}, "path key must not carry surrounding whitespace"),
        ("key-path-separator", {"key": "path/sep"}, "path key must not contain path separators"),
        ("segment-whitespace", {"segment": " bad_segment "}, "path segment must not carry surrounding whitespace"),
        ("segment-path-separator", {"segment": "path/sep"}, "path segment must be a single component"),
    )

    for case_id, overrides, expected_message in cases:
        with pytest.raises(ValidationError) as exc_info:
            _make_path_definition(**overrides)

        errors = exc_info.value.errors()
        _assert_caused_by_namespace_registry_error(exc_info.value, case_id)
        assert any(expected_message in str(error) for error in errors), case_id


def test_duplicate_registry_entries_raise_namespace_registry_error() -> None:
    namespace = _make_namespace_definition()
    duplicate_workflow_state = WORKFLOW_STATE_NAMESPACE.model_copy(update={"key": "workflow_state_duplicate"})
    path = _make_path_definition(key="dup_path", grammar="<root>/dup/")
    cases = (
        (
            "namespace-key",
            (namespace, namespace),
            (),
            "duplicate secure-object namespace registry key",
        ),
        (
            "namespace-value",
            (WORKFLOW_STATE_NAMESPACE, duplicate_workflow_state),
            (),
            "duplicate secure-object namespace value",
        ),
        (
            "path-key",
            (),
            (path, path),
            "duplicate storage path registry key",
        ),
    )

    for case_id, namespaces, paths, expected_message in cases:
        with pytest.raises(ValidationError) as exc_info:
            StorageHierarchyRegistry(namespaces=namespaces, paths=paths)

        assert any(expected_message in str(error) for error in exc_info.value.errors()), case_id


def test_secure_object_logical_path_uses_registered_sql_grammar() -> None:
    path_definition = STORAGE_NAMESPACE_REGISTRY.path_by_key("secure_objects_table")

    marker = secure_object_logical_path("cadrumo.persistence.profile.assets", "default")

    assert path_definition.kind is StoragePathKind.LOGICAL_SQL
    assert path_definition.grammar == "db://secure_objects/<namespace>/<object_key>"
    assert marker.as_posix() == "db:/secure_objects/cadrumo.persistence.profile.assets/default"


def test_secure_object_namespace_logical_path_uses_registered_sql_grammar() -> None:
    path_definition = STORAGE_NAMESPACE_REGISTRY.path_by_key("secure_objects_table")

    marker = secure_object_namespace_logical_path("cadrumo.domain.attachments.blobs")

    assert path_definition.kind is StoragePathKind.LOGICAL_SQL
    assert path_definition.grammar == "db://secure_objects/<namespace>/<object_key>"
    assert marker.as_posix() == "db:/secure_objects/cadrumo.domain.attachments.blobs"


def test_every_discovered_production_secure_object_namespace_is_registered() -> None:
    registered = {definition.namespace for definition in STORAGE_NAMESPACE_REGISTRY.namespaces}
    discovered = _discover_production_secure_object_namespaces()

    assert {
        ATTACHMENT_BLOB_NAMESPACE.namespace,
        GOOGLE_OAUTH_CLIENT_NAMESPACE.namespace,
        WORKFLOW_STATE_NAMESPACE.namespace,
        "cadrumo.domain.transactions.bucket",
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
            if not _is_test_surface(path) and path.name != "_secure_object_namespaces.py"
        ),
    )


def _is_test_surface(path: Path) -> bool:
    relative = repo_relative(path)
    return (
        path.name.startswith("test_")
        or path.name == "conftest.py"
        or "/test_" in relative
        or relative.startswith("src/cadrumo/tests/")
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
    storage_exports = __import__("cadrumo.adapters.persistence.storage", fromlist=["*"])
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
        "cadrumo.adapters.persistence.storage",
        "cadrumo.adapters.persistence.storage._secure_object_namespaces",
        "_secure_object_namespaces",
    } or (
        node.level > 0
        and node.module
        in {
            "adapters.persistence.storage",
            "adapters.persistence.storage._secure_object_namespaces",
            "persistence.storage",
            "persistence.storage._secure_object_namespaces",
            "storage",
            "storage._secure_object_namespaces",
            "_secure_object_namespaces",
        }
    )


def _assignment_parts(node: ast.AST) -> tuple[list[ast.expr], ast.expr | None]:
    if isinstance(node, ast.Assign):
        return list(node.targets), node.value
    if isinstance(node, ast.AnnAssign):
        return [node.target], node.value
    return [], None


def _resolve_namespace_value(node: ast.expr, bindings: dict[str, str]) -> str | None:
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.startswith(f"{PRODUCT_IDENTITY.python_package}.")
    ):
        return node.value
    if isinstance(node, ast.Name):
        return bindings.get(node.id)
    if isinstance(node, ast.Attribute) and node.attr == "namespace" and isinstance(node.value, ast.Name):
        return bindings.get(node.value.id)
    return None


def _namespace_values_from_call(node: ast.Call, bindings: dict[str, str]) -> set[str]:
    values: set[str] = set()
    call_name = leaf_name(node.func)
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


def test_every_pinned_secure_object_method_still_exists() -> None:
    """Anchor the matcher's method set against the real repository.

    The namespace checks below fire on calls to these method names. A name the
    repository does not have can never match, so the entry contributes nothing
    while reading as coverage -- and the same silence would follow a rename of
    a method that IS checked today.

    Found stale on its first run: ``list_object_keys`` was pinned and
    :class:`SecureObjectRepository` has no such method.
    """
    from .. import SecureObjectRepository

    missing = sorted(name for name in _SECURE_OBJECT_METHODS if not hasattr(SecureObjectRepository, name))

    assert not missing, (
        f"these pinned secure-object methods do not exist on the repository: {missing}. Re-point "
        "each at its current name or drop it; a matcher keyed on a method nothing has checks "
        "nothing while looking like it does."
    )
