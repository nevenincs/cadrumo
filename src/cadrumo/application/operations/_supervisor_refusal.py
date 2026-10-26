"""Bind private refusal evidence to a registered safe public projection."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

from ...core.operations import OperationLifecycle, OperationTerminalCondition
from .errors import OperationDeclarationError
from .models import OperationTerminalReceipt
from .persistence.journal import OperationPersistedSnapshot
from .refusal_evidence import OperationRefusalEvidence
from .registry import OperationRegistry, OperationResultProjector
from .schema_identity import OperationSchemaIdentityV1

if TYPE_CHECKING:
    from .persistence.journal import OperationSecureReferenceStore


async def _validated_refusal_receipt(
    *,
    registry: OperationRegistry,
    operands: OperationSecureReferenceStore | None,
    snapshot: OperationPersistedSnapshot,
    evidence: OperationRefusalEvidence,
    settled_at: datetime,
) -> OperationTerminalReceipt:
    """Bind deliberately constructed encrypted evidence before refusing work."""
    schema, projector, result_type, operand_store = _require_refusal_receipt_declaration(
        registry=registry,
        operands=operands,
        snapshot=snapshot,
        evidence=evidence,
    )
    evidence = OperationRefusalEvidence.model_validate(evidence.model_dump(mode="python"))
    receipt = OperationTerminalReceipt(
        identity=snapshot.identity,
        revision=snapshot.revision + 1,
        condition=OperationTerminalCondition.REFUSED,
        effect=snapshot.effect,
        settled_at=settled_at,
        refusal_ref=evidence.refusal_code,
        refusal_detail_ref=evidence.detail_ref,
    )
    stored = await operand_store.resolve(evidence.detail_ref, result_type)
    if type(stored) is not result_type:
        raise OperationDeclarationError("operation refusal evidence has an undeclared model")
    binding = registry.lookup_public_schema_binding(schema)
    projected = projector(stored, receipt)
    if type(projected) is not binding.model_type:
        raise OperationDeclarationError("operation refusal evidence has an undeclared projection")
    binding.model_type.model_validate(projected.model_dump(mode="python"))
    return receipt


def _require_refusal_receipt_declaration(
    *,
    registry: OperationRegistry,
    operands: OperationSecureReferenceStore | None,
    snapshot: OperationPersistedSnapshot,
    evidence: OperationRefusalEvidence,
) -> tuple[
    OperationSchemaIdentityV1,
    OperationResultProjector,
    type[BaseModel],
    OperationSecureReferenceStore,
]:
    """Require an exact running registration for the encrypted refusal detail."""
    definition = registry.lookup(snapshot.identity.definition_id)
    registration = registry.lookup_public_registration(snapshot.identity.definition_id)
    schema = registration.contract.result_schema
    projector = registration.result_projector
    result_type = definition.result_type
    if (
        snapshot.lifecycle is not OperationLifecycle.RUNNING
        or snapshot.definition_contract_digest != registration.contract.definition_contract_digest
        or evidence.refusal_code not in definition.refusal_detail_codes
        or evidence.refusal_code not in registration.contract.refusal_detail_codes
        or result_type is None
        or schema is None
        or projector is None
        or operands is None
    ):
        raise OperationDeclarationError("operation refusal evidence is not declared")
    return schema, projector, result_type, operands


__all__ = ["_validated_refusal_receipt"]
