"""Complete terminal-verdict coverage for Google Drive provider failures."""

from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass
from typing import override

import pytest

from .....core.operator_action_enums import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from ...google.tests.drive_media_server import drive_files_list_endpoint
from .. import (
    OutboundStorageConflictError,
    OutboundStorageError,
    OutboundStorageIntegrityError,
    OutboundStorageNetworkError,
    OutboundStorageNotFoundError,
    OutboundStoragePermissionError,
    OutboundStorageQuotaError,
    OutboundStorageUnavailableError,
)
from .. import _google_drive as drive_module
from .. import _google_drive_metadata as drive_metadata_module
from .._google_drive import GoogleDriveProvider
from .._google_drive_metadata import (
    DriveStoragePreconditionCondition,
    _drive_storage_content_hash,
    _parse_drive_modified_time,
    _parse_drive_size,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@dataclass(frozen=True)
class _CarrierContract:
    condition: DriveStoragePreconditionCondition
    outcome: NoRecoveryOutcome
    fact_keys: frozenset[str]


def _contract(
    condition: DriveStoragePreconditionCondition,
    outcome: NoRecoveryOutcome,
    *fact_keys: str,
) -> _CarrierContract:
    return _CarrierContract(condition, outcome, frozenset(fact_keys))


_FAILURE_CARRIER_TOTALITY: dict[str, _CarrierContract] = {
    "_translate_http_error:OutboundStoragePermissionError:drive request failed": _contract(
        DriveStoragePreconditionCondition.REQUEST_AUTHORIZED,
        NoRecoveryOutcome.SAFETY,
        "operation",
        "status",
        "authorization_sufficient",
    ),
    "_translate_http_error:OutboundStorageNotFoundError:drive request failed": _contract(
        DriveStoragePreconditionCondition.TARGET_PRESENT,
        NoRecoveryOutcome.OPERATOR_DECISION,
        "operation",
        "status",
        "target_present",
    ),
    "_translate_http_error:OutboundStorageConflictError:drive request failed": _contract(
        DriveStoragePreconditionCondition.REQUEST_CONFLICT_FREE,
        NoRecoveryOutcome.OPERATOR_DECISION,
        "operation",
        "status",
        "conflict_detected",
    ),
    "_translate_http_error:OutboundStorageQuotaError:drive request failed": _contract(
        DriveStoragePreconditionCondition.REQUEST_WITHIN_QUOTA,
        NoRecoveryOutcome.SAFETY,
        "operation",
        "status",
        "quota_available",
    ),
    "_translate_http_error:OutboundStorageUnavailableError:drive request failed": _contract(
        DriveStoragePreconditionCondition.REQUEST_AVAILABLE,
        NoRecoveryOutcome.SAFETY,
        "operation",
        "status",
        "available",
    ),
    "_translate_http_error:OutboundStorageNetworkError:drive request failed": _contract(
        DriveStoragePreconditionCondition.REQUEST_TRANSPORT_AVAILABLE,
        NoRecoveryOutcome.SAFETY,
        "operation",
        "status",
        "transport_available",
    ),
    "_service_factory:OutboundStorageNetworkError:googleapiclient is not importable": _contract(
        DriveStoragePreconditionCondition.API_CLIENT_AVAILABLE,
        NoRecoveryOutcome.SAFETY,
        "component",
        "client_available",
    ),
    "_execute:OutboundStorageNetworkError:drive request failed without translated error": _contract(
        DriveStoragePreconditionCondition.REQUEST_TRANSPORT_AVAILABLE,
        NoRecoveryOutcome.SAFETY,
        "operation",
        "status",
        "transport_available",
    ),
    "_resolve_vault_folder:OutboundStorageNetworkError:drive create_vault_folder returned no id": _contract(
        DriveStoragePreconditionCondition.RESPONSE_IDENTIFIER_PRESENT,
        NoRecoveryOutcome.OPERATOR_DECISION,
        "operation",
        "response_mapping",
        "identifier_present",
    ),
    "_verify_ownership_or_adopt:OutboundStorageConflictError:Drive folder exists under the configured root but is not marked as owned by this app": _contract(
        DriveStoragePreconditionCondition.OWNERSHIP_ALIGNED,
        NoRecoveryOutcome.OPERATOR_DECISION,
        "ownership_aligned",
    ),
    "_resolve_namespace_folder:OutboundStorageNetworkError:drive create_namespace_{namespace} returned no id": _contract(
        DriveStoragePreconditionCondition.RESPONSE_IDENTIFIER_PRESENT,
        NoRecoveryOutcome.OPERATOR_DECISION,
        "operation",
        "response_mapping",
        "identifier_present",
    ),
    "put:OutboundStorageNetworkError:drive write returned non-dict response": _contract(
        DriveStoragePreconditionCondition.RESPONSE_MAPPING,
        NoRecoveryOutcome.OPERATOR_DECISION,
        "operation",
        "response_mapping",
    ),
    "get:OutboundStorageNotFoundError:namespace is not present in Drive": _contract(
        DriveStoragePreconditionCondition.NAMESPACE_PRESENT,
        NoRecoveryOutcome.OPERATOR_DECISION,
        "operation",
        "namespace_present",
    ),
    "get:OutboundStorageNotFoundError:object is not present in Drive namespace": _contract(
        DriveStoragePreconditionCondition.OBJECT_PRESENT,
        NoRecoveryOutcome.OPERATOR_DECISION,
        "operation",
        "object_present",
    ),
    "get:OutboundStorageNetworkError:drive files.get_media returned non-bytes payload": _contract(
        DriveStoragePreconditionCondition.MEDIA_PAYLOAD_BYTES,
        NoRecoveryOutcome.OPERATOR_DECISION,
        "operation",
        "payload_bytes",
        "payload_type",
    ),
    "iter_objects:OutboundStorageNotFoundError:namespace is not present in Drive": _contract(
        DriveStoragePreconditionCondition.NAMESPACE_PRESENT,
        NoRecoveryOutcome.OPERATOR_DECISION,
        "operation",
        "namespace_present",
    ),
    "_build_media_body:OutboundStorageNetworkError:googleapiclient.http is not importable": _contract(
        DriveStoragePreconditionCondition.API_CLIENT_AVAILABLE,
        NoRecoveryOutcome.SAFETY,
        "component",
        "client_available",
    ),
    "_parse_drive_size:OutboundStorageIntegrityError:drive object metadata carries no usable size": _contract(
        DriveStoragePreconditionCondition.METADATA_SIZE_VALID,
        NoRecoveryOutcome.SAFETY,
        "field",
        "valid",
    ),
    "_parse_drive_size:OutboundStorageIntegrityError:drive object size is not an integer": _contract(
        DriveStoragePreconditionCondition.METADATA_SIZE_VALID,
        NoRecoveryOutcome.SAFETY,
        "field",
        "valid",
    ),
    "_parse_drive_size:OutboundStorageIntegrityError:drive object size is negative": _contract(
        DriveStoragePreconditionCondition.METADATA_SIZE_VALID,
        NoRecoveryOutcome.SAFETY,
        "field",
        "valid",
    ),
    "_parse_drive_modified_time:OutboundStorageIntegrityError:drive object metadata carries no modifiedTime": _contract(
        DriveStoragePreconditionCondition.METADATA_MODIFIED_TIME_VALID,
        NoRecoveryOutcome.SAFETY,
        "field",
        "valid",
    ),
    "_parse_drive_modified_time:OutboundStorageIntegrityError:drive object modifiedTime is not an RFC 3339 instant": _contract(
        DriveStoragePreconditionCondition.METADATA_MODIFIED_TIME_VALID,
        NoRecoveryOutcome.SAFETY,
        "field",
        "valid",
    ),
    "_parse_drive_modified_time:OutboundStorageIntegrityError:drive object modifiedTime carries no timezone": _contract(
        DriveStoragePreconditionCondition.METADATA_MODIFIED_TIME_VALID,
        NoRecoveryOutcome.SAFETY,
        "field",
        "valid",
    ),
    "_drive_storage_app_properties:OutboundStorageIntegrityError:drive object appProperties do not match the storage metadata contract": _contract(
        DriveStoragePreconditionCondition.METADATA_APP_PROPERTIES_VALID,
        NoRecoveryOutcome.SAFETY,
        "field",
        "valid",
    ),
}


def _literal(value: str | bool) -> str:
    return repr(value)


_FAILURE_CARRIER_FACT_EXPRESSIONS: dict[str, tuple[tuple[str, str], ...]] = {
    "_translate_http_error:OutboundStoragePermissionError:drive request failed": (
        ("operation", "action"),
        ("status", "context['status']"),
        ("authorization_sufficient", _literal(False)),
    ),
    "_translate_http_error:OutboundStorageNotFoundError:drive request failed": (
        ("operation", "action"),
        ("status", "context['status']"),
        ("target_present", _literal(False)),
    ),
    "_translate_http_error:OutboundStorageConflictError:drive request failed": (
        ("operation", "action"),
        ("status", "context['status']"),
        ("conflict_detected", _literal(True)),
    ),
    "_translate_http_error:OutboundStorageQuotaError:drive request failed": (
        ("operation", "action"),
        ("status", "context['status']"),
        ("quota_available", _literal(False)),
    ),
    "_translate_http_error:OutboundStorageUnavailableError:drive request failed": (
        ("operation", "action"),
        ("status", "context['status']"),
        ("available", _literal(False)),
    ),
    "_translate_http_error:OutboundStorageNetworkError:drive request failed": (
        ("operation", "action"),
        ("status", "context['status']"),
        ("transport_available", _literal(False)),
    ),
    "_service_factory:OutboundStorageNetworkError:googleapiclient is not importable": (
        ("component", _literal("discovery")),
        ("client_available", _literal(False)),
    ),
    "_execute:OutboundStorageNetworkError:drive request failed without translated error": (
        ("operation", "action"),
        ("status", _literal("unknown")),
        ("transport_available", _literal(False)),
    ),
    "_resolve_vault_folder:OutboundStorageNetworkError:drive create_vault_folder returned no id": (
        ("operation", _literal("create_vault_folder")),
        ("response_mapping", "isinstance(created, dict)"),
        ("identifier_present", "isinstance(created, dict) and 'id' in created"),
    ),
    "_verify_ownership_or_adopt:OutboundStorageConflictError:Drive folder exists under the configured root but is not marked as owned by this app": (
        ("ownership_aligned", _literal(False)),
    ),
    "_resolve_namespace_folder:OutboundStorageNetworkError:drive create_namespace_{namespace} returned no id": (
        ("operation", _literal("create_namespace")),
        ("response_mapping", "isinstance(created, dict)"),
        ("identifier_present", "isinstance(created, dict) and 'id' in created"),
    ),
    "put:OutboundStorageNetworkError:drive write returned non-dict response": (
        ("operation", "action"),
        ("response_mapping", _literal(False)),
    ),
    "get:OutboundStorageNotFoundError:namespace is not present in Drive": (
        ("operation", _literal("get")),
        ("namespace_present", _literal(False)),
    ),
    "get:OutboundStorageNotFoundError:object is not present in Drive namespace": (
        ("operation", _literal("get")),
        ("object_present", _literal(False)),
    ),
    "get:OutboundStorageNetworkError:drive files.get_media returned non-bytes payload": (
        ("operation", _literal("files.get_media")),
        ("payload_bytes", _literal(False)),
        ("payload_type", "type(payload).__name__"),
    ),
    "iter_objects:OutboundStorageNotFoundError:namespace is not present in Drive": (
        ("operation", _literal("iter_objects")),
        ("namespace_present", _literal(False)),
    ),
    "_build_media_body:OutboundStorageNetworkError:googleapiclient.http is not importable": (
        ("component", _literal("media_upload")),
        ("client_available", _literal(False)),
    ),
    "_parse_drive_size:OutboundStorageIntegrityError:drive object metadata carries no usable size": (
        ("field", _literal("size")),
        ("valid", _literal(False)),
    ),
    "_parse_drive_size:OutboundStorageIntegrityError:drive object size is not an integer": (
        ("field", _literal("size")),
        ("valid", _literal(False)),
    ),
    "_parse_drive_size:OutboundStorageIntegrityError:drive object size is negative": (
        ("field", _literal("size")),
        ("valid", _literal(False)),
    ),
    "_parse_drive_modified_time:OutboundStorageIntegrityError:drive object metadata carries no modifiedTime": (
        ("field", _literal("modifiedTime")),
        ("valid", _literal(False)),
    ),
    "_parse_drive_modified_time:OutboundStorageIntegrityError:drive object modifiedTime is not an RFC 3339 instant": (
        ("field", _literal("modifiedTime")),
        ("valid", _literal(False)),
    ),
    "_parse_drive_modified_time:OutboundStorageIntegrityError:drive object modifiedTime carries no timezone": (
        ("field", _literal("modifiedTime")),
        ("valid", _literal(False)),
    ),
    "_drive_storage_app_properties:OutboundStorageIntegrityError:drive object appProperties do not match the storage metadata contract": (
        ("field", _literal("appProperties")),
        ("valid", _literal(False)),
    ),
}

_EXTERNAL_ERROR_TYPES = {
    "OutboundStoragePermissionError",
    "OutboundStorageNotFoundError",
    "OutboundStorageConflictError",
    "OutboundStorageQuotaError",
    "OutboundStorageUnavailableError",
    "OutboundStorageNetworkError",
    "OutboundStorageIntegrityError",
}


def _call_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _carrier_message(call: ast.Call) -> str:
    assert call.args
    message = call.args[0]
    if isinstance(message, ast.Constant) and isinstance(message.value, str):
        return message.value
    if isinstance(message, ast.Name):
        assert message.id == "detail"
        return "drive request failed"
    assert isinstance(message, ast.JoinedStr)
    parts: list[str] = []
    for part in message.values:
        if isinstance(part, ast.Constant) and isinstance(part.value, str):
            parts.append(part.value)
        else:
            parts.append("{namespace}")
    return "".join(parts)


def _external_precondition(call: ast.Call) -> ast.Call:
    value = next((keyword.value for keyword in call.keywords if keyword.arg == "precondition_verdict"), None)
    assert isinstance(value, ast.Call) and _call_name(value.func) == "_drive_external_verdict"
    return value


def _condition_from_precondition(call: ast.Call) -> DriveStoragePreconditionCondition:
    assert call.args and isinstance(call.args[0], ast.Attribute)
    assert isinstance(call.args[0].value, ast.Name)
    assert call.args[0].value.id == "DriveStoragePreconditionCondition"
    return DriveStoragePreconditionCondition[call.args[0].attr]


def _outcome_from_precondition(call: ast.Call) -> NoRecoveryOutcome:
    value = next((keyword.value for keyword in call.keywords if keyword.arg == "outcome"), None)
    assert isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name)
    assert value.value.id == "NoRecoveryOutcome"
    return NoRecoveryOutcome[value.attr]


def _fact_keys_from_precondition(call: ast.Call) -> frozenset[str]:
    value = next((keyword.value for keyword in call.keywords if keyword.arg == "facts"), None)
    assert isinstance(value, ast.Dict)
    keys = []
    for key in value.keys:
        assert isinstance(key, ast.Constant) and isinstance(key.value, str)
        keys.append(key.value)
    return frozenset(keys)


def _fact_expressions_from_precondition(call: ast.Call) -> tuple[tuple[str, str], ...]:
    value = next((keyword.value for keyword in call.keywords if keyword.arg == "facts"), None)
    assert isinstance(value, ast.Dict)
    expressions: list[tuple[str, str]] = []
    for key, fact_value in zip(value.keys, value.values, strict=True):
        assert isinstance(key, ast.Constant) and isinstance(key.value, str)
        expressions.append((key.value, ast.unparse(fact_value)))
    return tuple(expressions)


def _external_failure_carriers() -> dict[str, ast.Call]:
    carriers: dict[str, ast.Call] = {}
    for module in (drive_module, drive_metadata_module):
        tree = ast.parse(inspect.getsource(module))

        class Visitor(ast.NodeVisitor):
            owner = "<module>"

            @override
            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                prior_owner = self.owner
                self.owner = node.name
                self.generic_visit(node)
                self.owner = prior_owner

            @override
            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                prior_owner = self.owner
                self.owner = node.name
                self.generic_visit(node)
                self.owner = prior_owner

            @override
            def visit_Call(self, node: ast.Call) -> None:
                error_type = _call_name(node.func)
                if error_type in _EXTERNAL_ERROR_TYPES:
                    key = f"{self.owner}:{error_type}:{_carrier_message(node)}"
                    assert key not in carriers, f"duplicate Drive failure carrier {key}"
                    carriers[key] = node
                self.generic_visit(node)

        Visitor().visit(tree)
    return carriers


def _assert_terminal_contract(
    error: OutboundStorageError,
    condition: DriveStoragePreconditionCondition,
    outcome: NoRecoveryOutcome,
    facts: dict[str, str | bool],
) -> None:
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == condition.value
    assert verdict.action is None
    assert verdict.argument_bindings == ()
    assert verdict.missing_argument_names == ()
    assert verdict.conditionality is ActionConditionality.NOT_APPLICABLE
    assert verdict.no_recovery_outcome is outcome
    assert len(verdict.evidence) == 1
    evidence = verdict.evidence[0]
    assert evidence.condition_id == condition.value
    assert evidence.evidence_id == f"{condition.value}.observation"
    assert evidence.provenance is ActionEvidenceProvenance.RUNTIME_OBSERVATION
    assert dict(evidence.values) == facts


def _provider() -> GoogleDriveProvider:
    return GoogleDriveProvider(credentials=object(), root_folder_id="drive-root", vault_folder_name="cadrumo-vault")


def _owned_folder(identifier: str, name: str) -> dict[str, object]:
    return {
        "id": identifier,
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "appProperties": {"cadrumo_vault_app": "cadrumo"},
    }


def test_drive_failure_carrier_totality_uses_the_canonical_no_action_authority() -> None:
    observed = _external_failure_carriers()
    assert set(observed) == set(_FAILURE_CARRIER_TOTALITY)
    assert set(_FAILURE_CARRIER_FACT_EXPRESSIONS) == set(_FAILURE_CARRIER_TOTALITY)

    for key, call in observed.items():
        expected = _FAILURE_CARRIER_TOTALITY[key]
        precondition = _external_precondition(call)
        assert _condition_from_precondition(precondition) is expected.condition, key
        assert _outcome_from_precondition(precondition) is expected.outcome, key
        assert _fact_keys_from_precondition(precondition) == expected.fact_keys, key
        assert _fact_expressions_from_precondition(precondition) == _FAILURE_CARRIER_FACT_EXPRESSIONS[key], key

    source = "\n".join(inspect.getsource(module) for module in (drive_module, drive_metadata_module))
    assert "PreconditionVerdict(" not in source
    assert "ConditionEvidence(" not in source


@pytest.mark.parametrize(
    ("status", "error_type", "condition", "outcome", "state_fact"),
    (
        (
            401,
            OutboundStoragePermissionError,
            DriveStoragePreconditionCondition.REQUEST_AUTHORIZED,
            NoRecoveryOutcome.SAFETY,
            ("authorization_sufficient", False),
        ),
        (
            404,
            OutboundStorageNotFoundError,
            DriveStoragePreconditionCondition.TARGET_PRESENT,
            NoRecoveryOutcome.OPERATOR_DECISION,
            ("target_present", False),
        ),
        (
            409,
            OutboundStorageConflictError,
            DriveStoragePreconditionCondition.REQUEST_CONFLICT_FREE,
            NoRecoveryOutcome.OPERATOR_DECISION,
            ("conflict_detected", True),
        ),
        (
            429,
            OutboundStorageQuotaError,
            DriveStoragePreconditionCondition.REQUEST_WITHIN_QUOTA,
            NoRecoveryOutcome.SAFETY,
            ("quota_available", False),
        ),
        (
            503,
            OutboundStorageUnavailableError,
            DriveStoragePreconditionCondition.REQUEST_AVAILABLE,
            NoRecoveryOutcome.SAFETY,
            ("available", False),
        ),
        (
            418,
            OutboundStorageNetworkError,
            DriveStoragePreconditionCondition.REQUEST_TRANSPORT_AVAILABLE,
            NoRecoveryOutcome.SAFETY,
            ("transport_available", False),
        ),
    ),
)
def test_real_drive_http_failures_have_exact_terminal_contracts(
    status: int,
    error_type: type[OutboundStorageError],
    condition: DriveStoragePreconditionCondition,
    outcome: NoRecoveryOutcome,
    state_fact: tuple[str, bool],
) -> None:
    with drive_files_list_endpoint(pages=(), status=status) as endpoint:
        provider = _provider()
        provider._service = endpoint.service
        with pytest.raises(error_type) as raised:
            provider._resolve_vault_folder()

    _assert_terminal_contract(
        raised.value,
        condition,
        outcome,
        {"operation": "resolve_vault_folder", "status": str(status), state_fact[0]: state_fact[1]},
    )


def test_foreign_drive_folder_conflict_has_an_exact_operator_decision_contract() -> None:
    with drive_files_list_endpoint(
        pages=(
            {
                "files": [
                    {
                        "id": "foreign-vault",
                        "name": "cadrumo-vault",
                        "mimeType": "application/vnd.google-apps.folder",
                        "appProperties": {"cadrumo_vault_app": "foreign"},
                    }
                ]
            },
        )
    ) as endpoint:
        provider = _provider()
        provider._service = endpoint.service
        with pytest.raises(OutboundStorageConflictError) as raised:
            provider._resolve_vault_folder()

    _assert_terminal_contract(
        raised.value,
        DriveStoragePreconditionCondition.OWNERSHIP_ALIGNED,
        NoRecoveryOutcome.OPERATOR_DECISION,
        {"ownership_aligned": False},
    )


@pytest.mark.parametrize(
    ("pages", "operation", "condition", "facts"),
    (
        (
            ({"files": [_owned_folder("vault-id", "cadrumo-vault")]}, {"files": []}),
            "get",
            DriveStoragePreconditionCondition.NAMESPACE_PRESENT,
            {"operation": "get", "namespace_present": False},
        ),
        (
            (
                {"files": [_owned_folder("vault-id", "cadrumo-vault")]},
                {"files": [_owned_folder("namespace-id", "ledger_transaction")]},
                {"files": []},
            ),
            "get",
            DriveStoragePreconditionCondition.OBJECT_PRESENT,
            {"operation": "get", "object_present": False},
        ),
        (
            ({"files": [_owned_folder("vault-id", "cadrumo-vault")]}, {"files": []}),
            "iter_objects",
            DriveStoragePreconditionCondition.NAMESPACE_PRESENT,
            {"operation": "iter_objects", "namespace_present": False},
        ),
    ),
    ids=("get-namespace", "get-object", "iter-objects-namespace"),
)
def test_real_drive_absence_failures_have_exact_operator_decision_contracts(
    pages: tuple[dict[str, object], ...],
    operation: str,
    condition: DriveStoragePreconditionCondition,
    facts: dict[str, str | bool],
) -> None:
    with drive_files_list_endpoint(pages=pages) as endpoint:
        provider = _provider()
        provider._service = endpoint.service
        with pytest.raises(OutboundStorageNotFoundError) as raised:
            if operation == "get":
                provider.get("ledger_transaction", "a" * 64)
            else:
                list(provider.iter_objects("ledger_transaction"))

    _assert_terminal_contract(raised.value, condition, NoRecoveryOutcome.OPERATOR_DECISION, facts)


@pytest.mark.parametrize(
    ("case", "condition", "facts"),
    (
        ("size", DriveStoragePreconditionCondition.METADATA_SIZE_VALID, {"field": "size", "valid": False}),
        (
            "modified-time",
            DriveStoragePreconditionCondition.METADATA_MODIFIED_TIME_VALID,
            {"field": "modifiedTime", "valid": False},
        ),
        (
            "app-properties",
            DriveStoragePreconditionCondition.METADATA_APP_PROPERTIES_VALID,
            {"field": "appProperties", "valid": False},
        ),
    ),
)
def test_malformed_drive_metadata_has_exact_safety_contracts(
    case: str,
    condition: DriveStoragePreconditionCondition,
    facts: dict[str, str | bool],
) -> None:
    with pytest.raises(OutboundStorageIntegrityError) as raised:
        if case == "size":
            _parse_drive_size("not-an-integer", provider_object_id="drive-file")
        elif case == "modified-time":
            _parse_drive_modified_time("not-a-time", provider_object_id="drive-file")
        else:
            _drive_storage_content_hash({"id": "drive-file", "appProperties": {"content_hash": "sha256-x"}})

    _assert_terminal_contract(raised.value, condition, NoRecoveryOutcome.SAFETY, facts)
