"""Registered read of the closed vocabularies a ledger entry form offers.

Each list comes from its owner, so a frontend holds no list of its own. A code
with no ``label_key`` is named by whoever shows it; a country or currency code
is an international standard's token, and the backend holds no name for it.

The country and currency lists are what is known, not what is allowed: a ledger
record checks those codes by shape, so a real jurisdiction outside these lists
stays recordable. The other lists are closed by the writers that read them.
"""

from __future__ import annotations

import asyncio
from typing import Final, Literal
from uuid import UUID

from pydantic import BaseModel

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.bucket_pointer import require_active_bucket_id
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.irnr_tipo_renta import resolve_tipo_renta_irnr_catalogue
from ...domain.calculations.registry.iva_deduction_catalogue import iva_deduction_fact_kinds
from ...domain.iva.establishment import catalogued_country_codes
from ...domain.transactions.m210_income_classification import m210_payer_modes
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES
from ..operations.models import (
    OperationRequest,
    OperationTerminalReceipt,
    require_succeeded_terminal_receipt,
)
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .invoice_label_vocabulary import CURRENCY_CODES
from .read_access import resolve_ledger_read_access

LEDGER_ENTRY_OPTIONS_OPERATION_DEFINITION_ID: Final = "ledger.entry-options"

ENTRY_OPTION_LABEL_PREFIX: Final = "application.ledger.entry_options."
"""Where the words of the served tokens live, one family under it per kind of word."""

type EntryOptionFamily = Literal["country", "currency", "deduction_fact_kind", "m210_payer_mode", "m210_tipo_renta"]


class LedgerEntryOptionsRequest(BaseModel):
    """Ask for the vocabularies; they do not vary by ledger row."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID


class LedgerEntryOptionProjection(BaseModel):
    """One offered value and, where the backend words it, the key of its word."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    value: str
    label_key: str | None = None


class LedgerEntryOptionFamilyProjection(BaseModel):
    """One vocabulary."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    family: EntryOptionFamily
    options: tuple[LedgerEntryOptionProjection, ...]


class LedgerEntryOptionsProjection(BaseModel):
    """Every vocabulary a ledger entry form offers."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    families: tuple[LedgerEntryOptionFamilyProjection, ...]


class LedgerEntryOptionsExecutionResult(BaseModel):
    """Private result kept in the worker's encrypted operation record."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result: LedgerEntryOptionsProjection


def _codes(values: frozenset[str]) -> tuple[LedgerEntryOptionProjection, ...]:
    return tuple(LedgerEntryOptionProjection(value=value) for value in sorted(values))


def _worded(word_family: str, tokens: tuple[str, ...]) -> tuple[LedgerEntryOptionProjection, ...]:
    return tuple(
        LedgerEntryOptionProjection(value=token, label_key=f"{ENTRY_OPTION_LABEL_PREFIX}{word_family}.{token}")
        for token in tokens
    )


def _tipo_renta_options(operation: PinnedAuthorityOperation) -> tuple[LedgerEntryOptionProjection, ...]:
    """Offer the official codes a calculation can project, each worded by its income concept.

    A fetch-gated code has no projected concept and the calculation refuses it,
    so it is not offered; a row that already stores one keeps it.
    """
    catalogue = resolve_tipo_renta_irnr_catalogue(authority=operation)
    return tuple(
        LedgerEntryOptionProjection(
            value=definition.code,
            label_key=f"{ENTRY_OPTION_LABEL_PREFIX}m210_income_concept.{definition.concept.value}",
        )
        for definition in catalogue.code_definitions
        if definition.concept is not None and not definition.fetch_gated
    )


def ledger_entry_options(profile_id: UUID, *, operation: PinnedAuthorityOperation) -> LedgerEntryOptionsProjection:
    """Read every vocabulary from its owner, under one pinned authority generation."""
    families: tuple[tuple[EntryOptionFamily, tuple[LedgerEntryOptionProjection, ...]], ...] = (
        ("country", _codes(catalogued_country_codes(operation=operation))),
        ("currency", _codes(CURRENCY_CODES)),
        (
            "deduction_fact_kind",
            _worded("deduction_fact_kind", tuple(kind.value for kind in iva_deduction_fact_kinds(authority=operation))),
        ),
        ("m210_payer_mode", _worded("m210_payer_mode", tuple(mode.value for mode in m210_payer_modes(operation=operation)))),
        ("m210_tipo_renta", _tipo_renta_options(operation)),
    )
    return LedgerEntryOptionsProjection(
        profile_id=profile_id,
        families=tuple(LedgerEntryOptionFamilyProjection(family=family, options=options) for family, options in families),
    )


class LedgerEntryOptionsExecutor:
    """Answer the vocabularies inside the exact profile's worker."""

    async def execute(
        self,
        request: OperationRequest[LedgerEntryOptionsRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Check the exact profile, then answer from the pinned authority; nothing is written."""
        bucket_id = str(request.payload.profile_id)
        subject = profile_operation_subject(bucket_id)
        if (
            request.definition_id != LEDGER_ENTRY_OPTIONS_OPERATION_DEFINITION_ID
            or context.identity.definition_id != LEDGER_ENTRY_OPTIONS_OPERATION_DEFINITION_ID
            or request.subject_ref != subject
            or context.identity.subject_ref != subject
            or require_active_bucket_id() != bucket_id
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(LEDGER_ENTRY_OPTIONS_OPERATION_DEFINITION_ID)
        options = await asyncio.to_thread(
            ledger_entry_options, request.payload.profile_id, operation=context.authority_operation
        )
        return await context.operands.put(LedgerEntryOptionsExecutionResult(result=options), written_at=now())


def _project_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not LedgerEntryOptionsExecutionResult:
        raise ValueError("invalid ledger entry options result")
    require_succeeded_terminal_receipt(
        receipt,
        definition_id=LEDGER_ENTRY_OPTIONS_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(result.result.profile_id)),
        effect=OperationEffect.NONE,
        message="ledger entry options has an incompatible terminal receipt",
    )
    return result.result


def build_ledger_entry_options_definition() -> OperationDefinition:
    """Declare the exact-profile read of the ledger entry vocabularies."""
    return build_single_phase_definition(
        definition_id=LEDGER_ENTRY_OPTIONS_OPERATION_DEFINITION_ID,
        request_type=LedgerEntryOptionsRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=LedgerEntryOptionsExecutionResult,
        executor_type=LedgerEntryOptionsExecutor,
        build=LedgerEntryOptionsExecutor,
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES,
    )


def resolve_ledger_entry_options_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Bind the read to the exact profile, as every ledger read is."""
    if request.definition_id != LEDGER_ENTRY_OPTIONS_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, LedgerEntryOptionsRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())


def build_ledger_entry_options_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind bounded schemas, exact-profile access and receipt projection."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerEntryOptionsProjection,
        result_projector=_project_result,
        access_resolver=resolve_ledger_entry_options_access,
    )


__all__ = [
    "ENTRY_OPTION_LABEL_PREFIX",
    "LEDGER_ENTRY_OPTIONS_OPERATION_DEFINITION_ID",
    "EntryOptionFamily",
    "LedgerEntryOptionFamilyProjection",
    "LedgerEntryOptionProjection",
    "LedgerEntryOptionsExecutionResult",
    "LedgerEntryOptionsExecutor",
    "LedgerEntryOptionsProjection",
    "LedgerEntryOptionsRequest",
    "build_ledger_entry_options_definition",
    "build_ledger_entry_options_registration",
    "ledger_entry_options",
    "resolve_ledger_entry_options_access",
]
