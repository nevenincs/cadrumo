"""Registered read that answers an unsaved split the way the split writer would take it; it writes nothing.

The answer covers what the parts themselves decide: how many there are, each one's amount
and description, and whether they add up to the movement. Whether a finalized declaration
cites the movement, and whether its converted EUR value distributes across these amounts,
stay the writer's to refuse when the split is saved.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Annotated, Final, Literal
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.bucket_pointer import require_active_bucket_id
from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.time.clock import now
from ...domain.transactions.classification_effects import takes_changes
from ...domain.transactions.models import Transaction
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES
from ..operations.models import OperationRequest, OperationTerminalReceipt, require_succeeded_terminal_receipt
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .actions_common import display_decimal
from .actions_split_merge import SPLIT_CHILDREN_MIN, split_amount_problem
from .read_access import resolve_ledger_request_read_access
from .split_operation import LEDGER_SPLIT_CHILDREN_MAX, LEDGER_SPLIT_PART_DESCRIPTION_MAX, LedgerSplitChildRequest
from .transaction_repository import transaction_catalogue_repository

LEDGER_SPLIT_CHECK_OPERATION_DEFINITION_ID: Final = "ledger.split.check"

# Wider than the writer takes, so an overlong part is answered with its own problem
# rather than the whole read being refused.
_MAX_ASKED_PARTS: Final = LEDGER_SPLIT_CHILDREN_MAX * 2
_MAX_ASKED_TEXT: Final = 4_096
_AskedText = Annotated[str, Field(max_length=_MAX_ASKED_TEXT)]

SplitProblemKind = Literal[
    "gone",
    "not_active",
    "count",
    "amount",
    "description",
    "description_long",
    "sum",
]


class LedgerSplitCheckPart(BaseModel):
    """One unsaved part as typed. No amount asks for what the other parts leave, on the last part only."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    amount: _AskedText | None = None
    description: _AskedText = ""


class LedgerSplitCheckRequest(BaseModel):
    """The movement to split and its unsaved parts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    transaction_id: TransactionId
    parts: Annotated[tuple[LedgerSplitCheckPart, ...], Field(max_length=_MAX_ASKED_PARTS)]


class LedgerSplitProblem(BaseModel):
    """The first thing the writer would refuse, with what naming it takes."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: SplitProblemKind
    index: int | None = None
    max: int | None = None
    difference: str | None = None
    over: bool | None = None


class LedgerSplitCheckResult(BaseModel):
    """What is left for the last part, the first problem, and the parts as the writer takes them."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    remainder: str | None = None
    problem: LedgerSplitProblem | None = None
    children: tuple[LedgerSplitChildRequest, ...] = ()


class LedgerSplitCheckExecutionResult(BaseModel):
    """Worker-side envelope of the answer."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result: LedgerSplitCheckResult


def _typed_amount(text: str) -> Decimal | None:
    # The grammar refuses the shape read two ways, so "1.000" is never taken for one.
    return try_parse_canonical_decimal(text, signed=False)


def _remainder(parent_amount: Decimal, typed: tuple[Decimal | None, ...]) -> Decimal | None:
    """Return what the others leave the open last part, positive or negative; None when one is unreadable."""
    if any(amount is None for amount in typed):
        return None
    return parent_amount - sum((amount for amount in typed if amount is not None), start=Decimal("0"))


def _description_problem(index: int, description: str) -> LedgerSplitProblem | None:
    if not description:
        return LedgerSplitProblem(kind="description", index=index)
    if len(description) > LEDGER_SPLIT_PART_DESCRIPTION_MAX:
        return LedgerSplitProblem(kind="description_long", index=index, max=LEDGER_SPLIT_PART_DESCRIPTION_MAX)
    return None


def _sum_problem(difference: Decimal) -> LedgerSplitProblem:
    return LedgerSplitProblem(kind="sum", difference=display_decimal(abs(difference)), over=difference > 0)


def _typed_amounts(parts: tuple[LedgerSplitCheckPart, ...]) -> list[Decimal | None]:
    return [_typed_amount(part.amount) if part.amount is not None else None for part in parts]


def _amounts_answer(
    parent_amount: Decimal, parts: tuple[LedgerSplitCheckPart, ...]
) -> tuple[tuple[Decimal, ...] | None, Decimal | None, LedgerSplitProblem | None]:
    """Read each part's amount; return the amounts, what the open part took, and the first amount problem."""
    open_last = bool(parts) and parts[-1].amount is None
    named = parts[:-1] if open_last else parts
    typed = _typed_amounts(named)
    left = _remainder(parent_amount, tuple(typed)) if open_last else None
    unreadable = next((index for index, amount in enumerate(typed) if amount is None), None)
    if unreadable is not None:
        return None, None, LedgerSplitProblem(kind="amount", index=unreadable)
    amounts = [amount for amount in typed if amount is not None]
    if not open_last:
        return tuple(amounts), None, None
    return _with_open_part(amounts, left, len(parts) - 1)


def _with_open_part(
    amounts: list[Decimal], left: Decimal | None, open_index: int
) -> tuple[tuple[Decimal, ...] | None, Decimal | None, LedgerSplitProblem | None]:
    """Give the open last part what the named parts leave, refusing when nothing or less than nothing is left."""
    if left is None or left == 0:
        return None, None, LedgerSplitProblem(kind="amount", index=open_index)
    if left < 0:
        return None, None, _sum_problem(-left)
    return (*amounts, left), left, None


def _checked_amounts(
    parent_amount: Decimal,
    parts: tuple[LedgerSplitCheckPart, ...],
    amounts: tuple[Decimal, ...] | None,
    amount_problem: LedgerSplitProblem | None,
    descriptions: tuple[str, ...],
) -> tuple[Decimal, ...] | LedgerSplitProblem:
    """Return the amounts the writer would take, or the first thing it would refuse."""
    if not SPLIT_CHILDREN_MIN <= len(parts) <= LEDGER_SPLIT_CHILDREN_MAX:
        return LedgerSplitProblem(kind="count", max=LEDGER_SPLIT_CHILDREN_MAX)
    if amounts is None:
        return amount_problem or LedgerSplitProblem(kind="amount", index=0)
    for index, description in enumerate(descriptions):
        problem = _description_problem(index, description)
        if problem is not None:
            return problem
    found = split_amount_problem(parent_amount=parent_amount, amounts=amounts)
    if found is None:
        return amounts
    if found.index is not None:
        return LedgerSplitProblem(kind="amount", index=found.index)
    return _sum_problem(found.child_sum - parent_amount)


def _children(
    amounts: tuple[Decimal, ...], descriptions: tuple[str, ...]
) -> tuple[LedgerSplitChildRequest, ...] | LedgerSplitProblem:
    """Spell each part as the writer's request, or name the part whose figure the request cannot spell."""
    children: list[LedgerSplitChildRequest] = []
    for index, (amount, description) in enumerate(zip(amounts, descriptions, strict=True)):
        try:
            children.append(LedgerSplitChildRequest(amount=display_decimal(amount), description=description))
        except ValidationError:
            # A worked-out figure the request cannot spell: three fraction digits read two ways.
            return LedgerSplitProblem(kind="amount", index=index)
    return tuple(children)


def check_split(
    profile_id: UUID,
    parent: Transaction | None,
    parts: tuple[LedgerSplitCheckPart, ...],
) -> LedgerSplitCheckResult:
    """Answer unsaved parts of ``parent`` through the writer's own amount rule and request model."""
    if parent is None:
        return LedgerSplitCheckResult(profile_id=profile_id, problem=LedgerSplitProblem(kind="gone"))
    if not takes_changes(parent.lifecycle_state):
        return LedgerSplitCheckResult(profile_id=profile_id, problem=LedgerSplitProblem(kind="not_active"))
    amounts, left, amount_problem = _amounts_answer(parent.raw.amount, parts)
    remainder = display_decimal(left) if left is not None else None
    descriptions = tuple(part.description.strip() for part in parts)
    checked = _checked_amounts(parent.raw.amount, parts, amounts, amount_problem, descriptions)
    children = _children(checked, descriptions) if not isinstance(checked, LedgerSplitProblem) else checked
    if isinstance(children, LedgerSplitProblem):
        return LedgerSplitCheckResult(profile_id=profile_id, remainder=remainder, problem=children)
    return LedgerSplitCheckResult(profile_id=profile_id, remainder=remainder, children=children)


class LedgerSplitCheckExecutor:
    """Answer unsaved parts inside the exact profile's worker."""

    async def execute(
        self,
        request: OperationRequest[LedgerSplitCheckRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Check the exact profile, then answer from the one stored movement the request names."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        subject = profile_operation_subject(bucket_id)
        if (
            request.definition_id != LEDGER_SPLIT_CHECK_OPERATION_DEFINITION_ID
            or context.identity.definition_id != LEDGER_SPLIT_CHECK_OPERATION_DEFINITION_ID
            or request.subject_ref != subject
            or context.identity.subject_ref != subject
            or require_active_bucket_id() != bucket_id
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(LEDGER_SPLIT_CHECK_OPERATION_DEFINITION_ID)

        def answer() -> LedgerSplitCheckResult:
            repository = transaction_catalogue_repository(bucket_id=bucket_id)
            catalogue = repository.load_by_ids((payload.transaction_id,))
            parent = catalogue.transactions.get(payload.transaction_id)
            return check_split(payload.profile_id, parent, payload.parts)

        result = await asyncio.to_thread(answer)
        return await context.operands.put(LedgerSplitCheckExecutionResult(result=result), written_at=now())


def _project_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not LedgerSplitCheckExecutionResult:
        raise ValueError("invalid ledger split check result")
    require_succeeded_terminal_receipt(
        receipt,
        definition_id=LEDGER_SPLIT_CHECK_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(result.result.profile_id)),
        effect=OperationEffect.NONE,
        message="ledger split check has an incompatible terminal receipt",
    )
    return result.result


def build_ledger_split_check_definition() -> OperationDefinition:
    """Declare the exact-profile read of an unsaved split."""
    return build_single_phase_definition(
        definition_id=LEDGER_SPLIT_CHECK_OPERATION_DEFINITION_ID,
        request_type=LedgerSplitCheckRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=LedgerSplitCheckExecutionResult,
        executor_type=LedgerSplitCheckExecutor,
        build=LedgerSplitCheckExecutor,
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES,
    )


def resolve_ledger_split_check_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Bind the read to the exact profile, as every ledger read is."""
    return resolve_ledger_request_read_access(
        request,
        context,
        definition_id=LEDGER_SPLIT_CHECK_OPERATION_DEFINITION_ID,
        request_type=LedgerSplitCheckRequest,
    )


def build_ledger_split_check_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind bounded schemas, exact-profile access and receipt projection."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerSplitCheckResult,
        result_projector=_project_result,
        access_resolver=resolve_ledger_split_check_access,
    )


__all__ = [
    "LEDGER_SPLIT_CHECK_OPERATION_DEFINITION_ID",
    "LedgerSplitCheckExecutor",
    "LedgerSplitCheckPart",
    "LedgerSplitCheckRequest",
    "LedgerSplitCheckResult",
    "LedgerSplitProblem",
    "SplitProblemKind",
    "build_ledger_split_check_definition",
    "build_ledger_split_check_registration",
    "check_split",
    "resolve_ledger_split_check_access",
]
