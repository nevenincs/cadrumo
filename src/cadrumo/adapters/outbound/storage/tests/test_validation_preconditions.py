"""Totality and machine contracts for operator-reachable storage validation."""

from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass
from types import ModuleType

import pytest

from .....core import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from .. import OutboundStorageValidationError, ProviderKind
from .. import _factory as factory_module
from .. import _google_drive as drive_module
from .. import _key_validation as key_module
from .. import _local as local_module
from .._key_validation import assert_admissible_object_key_hmac

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@dataclass(frozen=True)
class _ValidationCarrier:
    """One current validation carrier and its owned terminal contract."""

    condition_id: str | None
    facts: dict[str, str | bool] | None
    provenance: ActionEvidenceProvenance | None
    typed: bool


_VALIDATION_CARRIER_TOTALITY: dict[str, _ValidationCarrier] = {
    "_key_validation:assert_admissible_object_key_hmac:storage.key.present": _ValidationCarrier(
        "storage.key.present",
        {"backend": "<caller>", "field": "object_key_hmac", "valid": False},
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        True,
    ),
    "_key_validation:assert_admissible_object_key_hmac:storage.key.admissible": _ValidationCarrier(
        "storage.key.admissible",
        {"backend": "<caller>", "field": "object_key_hmac", "valid": False},
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        True,
    ),
    "_factory:_parse_kind:adapters.outbound.storage.factory.errors.kind_empty": _ValidationCarrier(
        "storage.factory.provider_kind.valid",
        {"field": "cadrumo_storage_provider_kind", "valid": False},
        ActionEvidenceProvenance.APPLICATION_STATE,
        True,
    ),
    "_factory:_parse_kind:adapters.outbound.storage.factory.errors.kind_unknown": _ValidationCarrier(
        "storage.factory.provider_kind.valid",
        {"field": "cadrumo_storage_provider_kind", "valid": False},
        ActionEvidenceProvenance.APPLICATION_STATE,
        True,
    ),
    "_factory:_build_oauth_desktop_credentials:adapters.outbound.storage.factory.errors.google_client_missing": _ValidationCarrier(
        "storage.factory.google_oauth_client.present",
        {"backend": "google_drive", "field": "google_oauth_client", "valid": False},
        ActionEvidenceProvenance.APPLICATION_STATE,
        True,
    ),
    "_factory:_build_oauth_desktop_credentials:adapters.outbound.storage.factory.errors.google_token_missing": _ValidationCarrier(
        "storage.factory.google_oauth_token.present",
        {"backend": "google_drive", "field": "google_oauth_token", "valid": False},
        ActionEvidenceProvenance.APPLICATION_STATE,
        True,
    ),
    "_factory:get_storage_provider:adapters.outbound.storage.factory.errors.drive_root_missing": _ValidationCarrier(
        "storage.factory.google_drive_root_folder_id.present",
        {"backend": "google_drive", "field": "google_drive_root_folder_id", "valid": False},
        ActionEvidenceProvenance.APPLICATION_STATE,
        True,
    ),
    "_factory:get_storage_provider:adapters.outbound.storage.factory.errors.kind_unhandled": _ValidationCarrier(
        None,
        None,
        None,
        False,
    ),
    "_local:_validate_namespace:adapters.outbound.storage.local.errors.namespace_blank": _ValidationCarrier(
        "storage.local.namespace.valid",
        {"backend": "local", "field": "namespace", "valid": False},
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        True,
    ),
    "_local:_validate_namespace:adapters.outbound.storage.local.errors.namespace_forbidden_characters": _ValidationCarrier(
        "storage.local.namespace.valid",
        {"backend": "local", "field": "namespace", "valid": False},
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        True,
    ),
    "_local:put:adapters.outbound.storage.local.errors.content_hash_blank": _ValidationCarrier(
        "storage.local.content_hash.present",
        {"backend": "local", "field": "content_hash", "valid": False},
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        True,
    ),
    "_google_drive:_validate_namespace:adapters.outbound.storage.google_drive.errors.namespace_blank": _ValidationCarrier(
        "storage.google_drive.namespace.valid",
        {"backend": "google_drive", "field": "namespace", "valid": False},
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        True,
    ),
    "_google_drive:_validate_namespace:adapters.outbound.storage.google_drive.errors.namespace_forbidden_characters": _ValidationCarrier(
        "storage.google_drive.namespace.valid",
        {"backend": "google_drive", "field": "namespace", "valid": False},
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        True,
    ),
    "_google_drive:__init__:adapters.outbound.storage.google_drive.errors.root_folder_id_blank": _ValidationCarrier(
        "storage.google_drive.root_folder_id.present",
        {"backend": "google_drive", "field": "root_folder_id", "valid": False},
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        True,
    ),
    "_google_drive:__init__:adapters.outbound.storage.google_drive.errors.vault_folder_name_blank": _ValidationCarrier(
        "storage.google_drive.vault_folder_name.valid",
        {"backend": "google_drive", "field": "vault_folder_name", "valid": False},
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        True,
    ),
    "_google_drive:__init__:adapters.outbound.storage.google_drive.errors.former_vault_folder": _ValidationCarrier(
        "storage.google_drive.vault_folder_name.valid",
        {"backend": "google_drive", "field": "vault_folder_name", "valid": False},
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        True,
    ),
    "_google_drive:_resolve_vault_folder:adapters.outbound.storage.google_drive.errors.vault_entry_not_folder": _ValidationCarrier(
        "storage.google_drive.vault_entry.folder",
        {"backend": "google_drive", "field": "vault_folder_entry", "valid": False},
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        True,
    ),
    "_google_drive:put:adapters.outbound.storage.google_drive.errors.content_hash_blank": _ValidationCarrier(
        "storage.google_drive.content_hash.present",
        {"backend": "google_drive", "field": "content_hash", "valid": False},
        ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        True,
    ),
}

_SOURCE_MODULES = (key_module, factory_module, local_module, drive_module)


def _call_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _constant_string(node: ast.expr) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _precondition_condition(call: ast.Call) -> str | None:
    precondition = next((keyword.value for keyword in call.keywords if keyword.arg == "precondition_verdict"), None)
    if not isinstance(precondition, ast.Call) or not precondition.args:
        return None
    return _constant_string(precondition.args[0])


def _translated_message(call: ast.Call) -> str | None:
    value = next((keyword.value for keyword in call.keywords if keyword.arg == "translated_message"), None)
    return _constant_string(value) if value is not None else None


def _validation_carriers(module: ModuleType) -> dict[str, ast.Call]:
    source = inspect.getsource(module)
    tree = ast.parse(source)
    carriers: dict[str, ast.Call] = {}

    class Visitor(ast.NodeVisitor):
        owner = "<module>"

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            prior_owner = self.owner
            self.owner = node.name
            self.generic_visit(node)
            self.owner = prior_owner

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self.visit_FunctionDef(node)

        def visit_Call(self, node: ast.Call) -> None:
            if _call_name(node.func) == "OutboundStorageValidationError":
                message = _translated_message(node)
                condition = _precondition_condition(node)
                identity = message or condition
                assert identity is not None, f"{module.__name__}:{self.owner} has no stable validation identity"
                key = f"{module.__name__.rsplit('.', maxsplit=1)[-1]}:{self.owner}:{identity}"
                assert key not in carriers, f"duplicate carrier identity {key}"
                carriers[key] = node
            self.generic_visit(node)

    Visitor().visit(tree)
    return carriers


def _provider_kind_branch_members() -> set[str]:
    tree = ast.parse(inspect.getsource(factory_module.get_storage_provider))
    members: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare) or len(node.ops) != 1 or not isinstance(node.ops[0], ast.Is):
            continue
        if not isinstance(node.left, ast.Name) or node.left.id != "kind" or len(node.comparators) != 1:
            continue
        comparator = node.comparators[0]
        if (
            isinstance(comparator, ast.Attribute)
            and isinstance(comparator.value, ast.Name)
            and comparator.value.id == "ProviderKind"
        ):
            members.add(comparator.attr)
    return members


def _assert_terminal_contract(error: OutboundStorageValidationError, carrier: _ValidationCarrier) -> None:
    assert carrier.typed
    assert carrier.condition_id is not None
    assert carrier.facts is not None
    assert carrier.provenance is not None
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == carrier.condition_id
    assert verdict.action is None
    assert verdict.argument_bindings == ()
    assert verdict.missing_argument_names == ()
    assert verdict.conditionality is ActionConditionality.NOT_APPLICABLE
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    assert len(verdict.evidence) == 1
    evidence = verdict.evidence[0]
    assert evidence.condition_id == carrier.condition_id
    assert evidence.evidence_id == f"{carrier.condition_id}.observation"
    assert evidence.provenance is carrier.provenance
    assert dict(evidence.values) == carrier.facts


def test_storage_validation_carrier_totality_and_canonical_construction() -> None:
    observed = {key: call for module in _SOURCE_MODULES for key, call in _validation_carriers(module).items()}
    assert set(observed) == set(_VALIDATION_CARRIER_TOTALITY)

    for key, call in observed.items():
        carrier = _VALIDATION_CARRIER_TOTALITY[key]
        condition = _precondition_condition(call)
        assert (condition is not None) is carrier.typed, key
        assert condition == carrier.condition_id, key

    for module in _SOURCE_MODULES:
        source = inspect.getsource(module)
        assert "PreconditionVerdict(" not in source
        assert "ConditionEvidence(" not in source
        assert "no_action_precondition_verdict" in source


def test_factory_unhandled_kind_exclusion_is_closed_over_the_provider_enum() -> None:
    """The sole untyped branch follows an exhaustive parse and branch partition."""
    assert set(ProviderKind.__members__) == _provider_kind_branch_members()
    assert {factory_module._parse_kind(kind.value) for kind in ProviderKind} == set(ProviderKind)
    excluded = _VALIDATION_CARRIER_TOTALITY[
        "_factory:get_storage_provider:adapters.outbound.storage.factory.errors.kind_unhandled"
    ]
    assert not excluded.typed


@pytest.mark.parametrize(
    ("backend", "value", "carrier_key"),
    (
        ("local", " ", "_key_validation:assert_admissible_object_key_hmac:storage.key.present"),
        ("google_drive", "abc'defg", "_key_validation:assert_admissible_object_key_hmac:storage.key.admissible"),
    ),
)
def test_object_key_validation_emits_the_exact_terminal_contract(
    backend: str,
    value: str,
    carrier_key: str,
) -> None:
    with pytest.raises(OutboundStorageValidationError) as raised:
        assert_admissible_object_key_hmac(value, backend=backend)

    carrier = _VALIDATION_CARRIER_TOTALITY[carrier_key]
    expected_facts = dict(carrier.facts or {})
    expected_facts["backend"] = backend
    _assert_terminal_contract(
        raised.value,
        _ValidationCarrier(carrier.condition_id, expected_facts, carrier.provenance, carrier.typed),
    )
