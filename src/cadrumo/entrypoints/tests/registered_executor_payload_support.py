"""Build exact typed requests and their real local scenario state."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from pydantic import BaseModel

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    profile_authority_contexts as _profile_contexts_for_test,
)
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

from ...application.modelo.aggregate_request import ModeloAggregateOperationRequest
from ...application.modelo.invoice_withholding_capture_contracts import (
    MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID,
)
from ...application.operations.operation_definition import OperationDefinition
from ...application.user_profile.automation_operations import build_automation_operation_definitions
from .aggregate_operation_test_support import aggregate_conformance_command
from .invoice_evidence_operation_test_support import prepare_invoice_evidence_conformance_case
from .invoice_withholding_operation_test_support import seed_invoice_withholding_conformance_case
from .registered_executor_payload_context import PayloadBuilder, PayloadContext, PayloadResult
from .registered_executor_payload_ledger_support import LEDGER_BUILDERS
from .registered_executor_payload_live_support import LIVE_BUILDERS
from .registered_executor_payload_modelo_support import MODELO_BUILDERS
from .registered_executor_payload_profile_support import PROFILE_BUILDERS
from .registered_executor_seeding_support import _prorrata_case


def _owned_once(*tables: dict[str, PayloadBuilder]) -> dict[str, PayloadBuilder]:
    """Merge the behaviour tables, refusing an operation that two of them claim."""
    merged: dict[str, PayloadBuilder] = {}
    for table in tables:
        shared = merged.keys() & table.keys()
        assert not shared, f"payload builders declared more than once: {sorted(shared)}"
        merged.update(table)
    return merged


_BUILDERS = _owned_once(PROFILE_BUILDERS, LIVE_BUILDERS, MODELO_BUILDERS, LEDGER_BUILDERS)


def _family_payload(ctx: PayloadContext) -> PayloadResult | None:
    """Return the request of an operation whose scenario a shared family module owns."""
    definition_id = ctx.definition_id
    if definition_id in {"ledger.evidence.extract", "ledger.evidence.confirm"}:
        evidence_case = prepare_invoice_evidence_conformance_case(
            definition_id, profile_id=ctx.profile_id, operation=ctx.operation
        )
        return ctx.profile_subject, evidence_case.request, None
    if definition_id.startswith("ledger.prorrata."):
        prorrata_case = _prorrata_case(definition_id, profile_id=ctx.profile_id, operation=ctx.operation)
        return ctx.profile_subject, prorrata_case.request, None
    if definition_id == "modelo.aggregate":
        return (
            ctx.profile_subject,
            ModeloAggregateOperationRequest.from_inputs(
                profile_id=ctx.profile_id, command=aggregate_conformance_command(operation=ctx.operation)
            ),
            None,
        )
    if definition_id == MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID:
        withholding_seed = seed_invoice_withholding_conformance_case(ctx.profile_id, operation=ctx.operation)
        return ctx.profile_subject, withholding_seed.request, None
    if definition_id in {item.definition_id for item in build_automation_operation_definitions()}:
        # The default production graph has no trusted runtime owner. The
        # dedicated administration integration suite proves positive execution
        # of every member with real custody and an explicitly bound owner.
        return (
            ctx.raw_profile_subject,
            ctx.definition.request_type.model_validate({"profile_id": ctx.profile_id, "request_id": UUID(int=1)}),
            b"synthetic" if ctx.definition.ephemeral_secret is not None else None,
        )
    return None


def _payload(
    definition: OperationDefinition, *, profile_id: UUID, tmp_path: Path, operation: PinnedAuthorityOperation
) -> tuple[str, BaseModel, bytes | None]:
    """Use only the exact request type exported by the registered definition."""
    _profile_create_context_for_test, profile_decode_context_for_test = _profile_contexts_for_test()
    ctx = PayloadContext(
        definition=definition,
        profile_id=profile_id,
        tmp_path=tmp_path,
        operation=operation,
        decode_context=profile_decode_context_for_test,
    )
    family = _family_payload(ctx)
    if family is not None:
        return family
    builder = _BUILDERS.get(definition.definition_id)
    if builder is None:
        raise AssertionError(f"no conformance scenario for {definition.definition_id}")
    return builder(ctx)
