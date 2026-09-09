"""Contract, digest, and registration helpers for the operation registry.

The public registry classes remain in :mod:`registry` so their import and
serialization identities stay stable.  This module contains the value-level
work used to derive and validate their public contract fixed point.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

from pydantic import BaseModel

from ...core.hashing import content_hash_hex
from ...core.identity import ContentDigest
from ...core.operations import OperationInteractionKind
from ._model_contract import require_strict_frozen_operation_model_graph

if TYPE_CHECKING:
    from .registry import (
        OperationDefinition,
        OperationPublicDefinitionContractV1,
        OperationPublicDefinitionRegistrationV1,
    )


def schema_identity_key(identity: Any) -> tuple[str, int, ContentDigest]:
    """Return the complete identity tuple, including its fingerprint."""
    return identity.schema_id, identity.schema_version, identity.schema_fingerprint


def public_schema_bindings(
    registration: OperationPublicDefinitionRegistrationV1,
) -> dict[tuple[str, int, ContentDigest], type[BaseModel]]:
    """Index each registered public schema binding by its complete identity."""
    return {schema_identity_key(binding.identity): binding.model_type for binding in registration.schema_bindings}


def declared_public_schema_identities(
    contract: OperationPublicDefinitionContractV1,
) -> set[tuple[str, int, ContentDigest]]:
    """Collect every schema identity declared by one public contract manifest."""
    return {
        schema_identity_key(identity)
        for identity in (
            contract.request_schema,
            contract.result_schema,
            contract.review_projection_schema,
            contract.interaction_response_schema,
            contract.workspace_refresh_target_schema,
        )
        if identity is not None
    }


def validate_public_schema_manifest(
    bindings: dict[tuple[str, int, ContentDigest], type[BaseModel]],
    declared_identities: set[tuple[str, int, ContentDigest]],
) -> None:
    """Require schema bindings to cover exactly the contract manifest."""
    if set(bindings) != declared_identities:
        raise ValueError("public operation schema bindings must exactly match the declared manifest")


def validate_public_request_binding(
    definition: OperationDefinition,
    contract: OperationPublicDefinitionContractV1,
    bindings: dict[tuple[str, int, ContentDigest], type[BaseModel]],
) -> None:
    """Require the declared request identity to bind the definition model."""
    if bindings[schema_identity_key(contract.request_schema)] is not definition.request_type:
        raise ValueError("public operation request schema must bind the definition request type")


def validate_public_result_registration(
    definition: OperationDefinition,
    registration: OperationPublicDefinitionRegistrationV1,
    contract: OperationPublicDefinitionContractV1,
    bindings: dict[tuple[str, int, ContentDigest], type[BaseModel]],
) -> None:
    """Match result schema and projector declarations to the definition result."""
    if definition.result_type is None:
        validate_resultless_public_registration(registration, contract)
        return
    validate_resultful_public_registration(definition, registration, contract, bindings)


def validate_resultless_public_registration(
    registration: OperationPublicDefinitionRegistrationV1,
    contract: OperationPublicDefinitionContractV1,
) -> None:
    """Refuse result declarations for an operation without a result model."""
    if contract.result_schema is not None:
        raise ValueError("result-less operation definition cannot declare a public result schema")
    if registration.result_projector is not None:
        raise ValueError("result-less operation definition cannot declare a result projector")


def validate_resultful_public_registration(
    definition: OperationDefinition,
    registration: OperationPublicDefinitionRegistrationV1,
    contract: OperationPublicDefinitionContractV1,
    bindings: dict[tuple[str, int, ContentDigest], type[BaseModel]],
) -> None:
    """Match a result-bearing operation's schema and optional projection adapter."""
    if contract.result_schema is not None:
        bound_result_type = bindings[schema_identity_key(contract.result_schema)]
        distinct_result_projection = bound_result_type is not definition.result_type
        if distinct_result_projection != (registration.result_projector is not None):
            raise ValueError(
                "a public result schema distinct from the definition result type requires one registered "
                "result projector, and one identical to it must not declare one"
            )
    elif registration.result_projector is not None:
        raise ValueError("a result projector requires a declared public result schema")


def validate_public_review_registration(
    definition: OperationDefinition,
    registration: OperationPublicDefinitionRegistrationV1,
    contract: OperationPublicDefinitionContractV1,
) -> None:
    """Match REVIEW declarations, operand validation, and projector shape."""
    declares_review = OperationInteractionKind.REVIEW in definition.interaction_kinds
    validate_public_review_declarations(declares_review, registration, contract)
    validate_public_review_implementations(registration)


def validate_public_review_declarations(
    declares_review: bool,
    registration: OperationPublicDefinitionRegistrationV1,
    contract: OperationPublicDefinitionContractV1,
) -> None:
    """Require each REVIEW contract and runtime registration arm together."""
    if declares_review != (contract.review_projection_schema is not None):
        raise ValueError("REVIEW operation definitions require one public review schema")
    if declares_review != (registration.review_projector is not None):
        raise ValueError("REVIEW operation definitions require one registered review projector")
    if declares_review != (registration.reviewed_operand_type is not None):
        raise ValueError("REVIEW operation definitions require one registered reviewed operand type")


def validate_public_review_implementations(registration: OperationPublicDefinitionRegistrationV1) -> None:
    """Validate the reviewed operand graph before the REVIEW projector shape."""
    if registration.reviewed_operand_type is not None:
        require_strict_frozen_operation_model_graph(
            registration.reviewed_operand_type,
            path="reviewed operand",
            reject_mutable_annotations=True,
            require_validated_defaults=True,
        )
    if registration.review_projector is not None:
        require_positional_callable_signature(
            registration.review_projector,
            arity=2,
            label="REVIEW projector",
        )


def validate_public_refresh_registration(
    registration: OperationPublicDefinitionRegistrationV1,
    contract: OperationPublicDefinitionContractV1,
) -> None:
    """Require refresh schema and adapter declarations to move together."""
    declares_refresh = contract.workspace_refresh_target_schema is not None
    if declares_refresh != (registration.workspace_refresh_adapter is not None):
        raise ValueError("Workspace refresh schema and adapter must be declared together")
    if registration.workspace_refresh_adapter is not None:
        require_positional_callable_signature(
            registration.workspace_refresh_adapter,
            arity=1,
            label="Workspace refresh adapter",
        )


def validate_public_result_projector_signature(registration: OperationPublicDefinitionRegistrationV1) -> None:
    """Validate the optional projector on the registration model boundary."""
    if registration.result_projector is not None:
        require_positional_callable_signature(
            registration.result_projector,
            arity=2,
            label="result projector",
        )


def validate_public_registration(
    definition: OperationDefinition,
    registration: OperationPublicDefinitionRegistrationV1,
    *,
    contract_builder: Callable[..., object],
) -> None:
    """Run the ordered live-registration checks for one operation definition."""
    contract = registration.contract
    bindings = public_schema_bindings(registration)
    declared_identities = declared_public_schema_identities(contract)
    validate_public_schema_manifest(bindings, declared_identities)
    validate_public_request_binding(definition, contract, bindings)
    validate_public_result_registration(definition, registration, contract, bindings)
    validate_public_result_projector_signature(registration)
    validate_public_review_registration(definition, registration, contract)
    validate_public_refresh_registration(registration, contract)
    validate_public_contract_fixed_point(definition, contract, contract_builder=contract_builder)


def validate_public_contract_fixed_point(
    definition: OperationDefinition,
    contract: OperationPublicDefinitionContractV1,
    *,
    contract_builder: Callable[..., object],
) -> None:
    """Require the manifest to equal the value derived from live definition data."""
    expected = contract_builder(
        definition,
        request_schema=contract.request_schema,
        result_schema=contract.result_schema,
        review_projection_schema=contract.review_projection_schema,
        interaction_response_schema=contract.interaction_response_schema,
        workspace_refresh_target_schema=contract.workspace_refresh_target_schema,
    )
    if expected != contract:
        raise ValueError("public operation definition contract is not a live-registry fixed point")


def definition_contract_digest(contract: OperationPublicDefinitionContractV1) -> ContentDigest:
    """Derive the digest over one public definition contract."""
    return content_hash_hex(definition_contract_value(contract, include_digest=False))


def contract_set_digest(
    definitions: tuple[OperationPublicDefinitionContractV1, ...],
) -> ContentDigest:
    """Derive the digest over the canonical public contract set."""
    payload = {
        "contract_set_version": 1,
        "definitions": [definition_contract_value(definition, include_digest=True) for definition in definitions],
    }
    return content_hash_hex(payload)


def definition_contract_value(
    contract: OperationPublicDefinitionContractV1,
    *,
    include_digest: bool,
) -> dict[str, object]:
    """Return the explicitly ordered, JSON-safe value governed by the digest."""
    payload: dict[str, object] = {}
    payload.update(definition_contract_identity_value(contract))
    payload.update(definition_contract_schema_value(contract))
    payload.update(definition_contract_policy_value(contract))
    if include_digest:
        payload["definition_contract_digest"] = contract.definition_contract_digest
    return payload


def definition_contract_identity_value(contract: OperationPublicDefinitionContractV1) -> dict[str, object]:
    """Return manifest and operation identity fields in digest order."""
    return {
        "manifest_version": contract.manifest_version,
        "definition_id": contract.definition_id,
        "action_reference": (
            None if contract.action_reference is None else contract.action_reference.model_dump(mode="json")
        ),
    }


def definition_contract_schema_value(contract: OperationPublicDefinitionContractV1) -> dict[str, object]:
    """Return declared public schema identities in digest order."""
    return {
        "request_schema": contract.request_schema.model_dump(mode="json"),
        "result_schema": None if contract.result_schema is None else contract.result_schema.model_dump(mode="json"),
        "review_projection_schema": (
            None
            if contract.review_projection_schema is None
            else contract.review_projection_schema.model_dump(mode="json")
        ),
        "interaction_response_schema": (
            None
            if contract.interaction_response_schema is None
            else contract.interaction_response_schema.model_dump(mode="json")
        ),
        "workspace_refresh_target_schema": (
            None
            if contract.workspace_refresh_target_schema is None
            else contract.workspace_refresh_target_schema.model_dump(mode="json")
        ),
    }


def definition_contract_policy_value(contract: OperationPublicDefinitionContractV1) -> dict[str, object]:
    """Return policy and capability fields in digest order."""
    return {
        "interaction_kinds": tuple(sorted(item.value for item in contract.interaction_kinds)),
        "request_storage": contract.request_storage.value,
        "durability": contract.durability.value,
        "cancellation": contract.cancellation.value,
        "deadline": contract.deadline.value,
        "replay": contract.replay.value,
        "baseline": contract.baseline.value,
        "sensitive_input": contract.sensitive_input.value,
        "conflict_scope": contract.conflict_scope.value,
        "owned_resources": tuple(sorted(item.value for item in contract.owned_resources)),
        "permitted_effects": tuple(sorted(item.value for item in contract.permitted_effects)),
        "close_policy": contract.close_policy.value,
        "reconciliation_policy": contract.reconciliation_policy.value,
        "permitted_frontends": tuple(sorted(item.value for item in contract.permitted_frontends)),
        "ephemeral_secret_required": contract.ephemeral_secret_required,
    }


def build_public_contract(
    *,
    contract_type: type[BaseModel],
    definition: OperationDefinition,
    request_schema: Any,
    result_schema: Any,
    review_projection_schema: Any,
    interaction_response_schema: Any,
    workspace_refresh_target_schema: Any,
) -> Any:
    """Build a public contract through the caller-owned Pydantic class."""
    capabilities = definition.capabilities
    values: dict[str, object] = {
        "definition_id": definition.definition_id,
        "action_reference": definition.action_reference,
        "request_schema": request_schema,
        "result_schema": result_schema,
        "review_projection_schema": review_projection_schema,
        "interaction_response_schema": interaction_response_schema,
        "workspace_refresh_target_schema": workspace_refresh_target_schema,
        "interaction_kinds": definition.interaction_kinds,
        "request_storage": capabilities.request_storage,
        "durability": capabilities.durability,
        "cancellation": capabilities.cancellation,
        "deadline": capabilities.deadline,
        "replay": capabilities.replay,
        "baseline": capabilities.baseline,
        "sensitive_input": capabilities.sensitive_input,
        "conflict_scope": capabilities.conflict_scope,
        "owned_resources": capabilities.owned_resources,
        "permitted_effects": capabilities.permitted_effects,
        "close_policy": capabilities.close_policy,
        "reconciliation_policy": definition.reconciliation_policy,
        "permitted_frontends": definition.permitted_frontends,
        "ephemeral_secret_required": definition.ephemeral_secret is not None,
    }
    contract_type_any = cast(Any, contract_type)
    provisional = contract_type_any.model_construct(
        **values,
        definition_contract_digest=cast(ContentDigest, "0" * 64),
    )
    return contract_type_any(
        **values,
        definition_contract_digest=definition_contract_digest(provisional),
    )


def require_positional_callable_signature(
    callable_value: Callable[..., object],
    *,
    arity: int,
    label: str,
) -> None:
    """Require one synchronous callable with exactly the declared arity."""
    if inspect.iscoroutinefunction(callable_value) or inspect.iscoroutinefunction(type(callable_value).__call__):
        raise ValueError(f"operation {label} must be synchronous")
    try:
        signature = inspect.signature(callable_value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"operation {label} must expose an inspectable signature") from error
    parameters = tuple(signature.parameters.values())
    positional_kinds = (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    if len(parameters) != arity or any(parameter.kind not in positional_kinds for parameter in parameters):
        raise ValueError(f"operation {label} must accept exactly {arity} positional arguments")


__all__ = [
    "build_public_contract",
    "contract_set_digest",
    "declared_public_schema_identities",
    "definition_contract_digest",
    "definition_contract_identity_value",
    "definition_contract_policy_value",
    "definition_contract_schema_value",
    "definition_contract_value",
    "public_schema_bindings",
    "require_positional_callable_signature",
    "schema_identity_key",
    "validate_public_contract_fixed_point",
    "validate_public_refresh_registration",
    "validate_public_registration",
    "validate_public_request_binding",
    "validate_public_result_registration",
    "validate_public_review_declarations",
    "validate_public_review_implementations",
    "validate_public_review_registration",
    "validate_public_schema_manifest",
    "validate_resultful_public_registration",
    "validate_resultless_public_registration",
]
