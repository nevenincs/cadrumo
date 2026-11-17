"""Submit one registered operation for a persona and settle it, recording the words its failure carries."""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from typing import Final, override

from pydantic import BaseModel

from ...application.modelo.edit_operator_input import ModeloEditOperatorInputV2, prepare_modelo_edit_operand
from ...application.modelo.work_calculation_contracts import (
    ModeloWorkCalculatePublicResultV3,
    ModeloWorkCalculateRequest,
)
from ...application.operations.error_detail import OperationErrorDetailV1, operation_error_detail_schema
from ...application.operations.frontend_projection import OperationPublicProjectionV1
from ...application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ...application.operations.models import OperationRequest
from ...core.logging import flush_logging
from ...core.operations import (
    TERMINAL_CONDITIONS_WITH_ERROR_DETAIL,
    OperationTerminalCondition,
    profile_operation_subject,
)
from .persona_prior_values import PriorValueAttestationError, attest_return_prior_values, entries_on
from .persona_work_income_statements import state_work_income_none
from .persona_work_inputs import WorkInputError, enter_work_inputs
from .persona_world import PERSONA_ACTOR, PersonaMaterialisationError, PersonaWorld


def settle_operation(
    world: PersonaWorld,
    definition_id: str,
    payload: BaseModel,
    *,
    subject: str | None = None,
) -> BaseModel | None:
    """Submit one registered operation, settle it, refuse anything but success, and return its public result.

    The operation addresses the profile unless ``subject`` names another subject, such as a work unit.
    A declaration edit travels as the window's volatile operator input: the
    operation is admitted on its amount-free request, then receives the staged
    intents as its financial operand.
    """
    subject_ref = subject or profile_operation_subject(str(world.profile_id))

    async def settle() -> OperationPublicProjectionV1:
        services = world.services
        if not isinstance(payload, ModeloEditOperatorInputV2):
            submitted = await services.submission.submit(
                OperationRequest(definition_id=definition_id, subject_ref=subject_ref, payload=payload),
                actor_ref=PERSONA_ACTOR,
            )
        else:
            prepared = prepare_modelo_edit_operand(
                definition_id=definition_id,
                profile_id=world.profile_id,
                subject_ref=subject_ref,
                input_json=payload.model_dump_json(),
            )
            try:
                submitted = await services.submission.submit(
                    OperationRequest(definition_id=definition_id, subject_ref=subject_ref, payload=prepared.request),
                    actor_ref=PERSONA_ACTOR,
                )
                if prepared.operand is None:
                    raise PersonaMaterialisationError(f"{definition_id} prepared no edit operand")
                await services.submission.supervisor.bind_typed_financial_operand(
                    submitted.receipt.operation_id, prepared.operand
                )
            finally:
                prepared.release()
        operation_id = submitted.receipt.operation_id
        await services.submission.start(operation_id)
        await services.submission.settled(operation_id)
        observed = await services.observation.observe(
            OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=256)
        )
        if not isinstance(observed, OperationObservationSuccessV1):
            raise PersonaMaterialisationError(f"{definition_id} could not be observed")
        return observed.projection

    with _failure_frames() as failures:
        terminal = asyncio.run(settle())
    result = public_result(world, terminal)
    if terminal.terminal_condition is not OperationTerminalCondition.SUCCEEDED:
        # A refusal names its registered code through its refusal reference; only a failure has an error code.
        code = (
            terminal.refusal_ref
            if terminal.terminal_condition is OperationTerminalCondition.REFUSED
            else terminal.failure_error_code
        )
        detail = _served_words(world, terminal)
        if detail is None and result is not None:
            # A refusal a definition records as its own typed result carries its sentence in that result.
            detail = _result_words(result.model_dump(mode="json", exclude={"profile_id"}))
            detail = result.model_dump_json(exclude={"profile_id"}) if detail is None else detail
        if detail is None:
            detail = failures.frames.get(str(terminal.operation_id), "no detail")
        raise PersonaMaterialisationError(f"{definition_id} settled {terminal.terminal_condition} ({code}): {detail}")
    return result


_EXECUTOR_LOGGER: Final[str] = "cadrumo.application.operations.supervisor_execution"
"""The logger the supervisor names a failed operation's exception type and code frames on."""


_FAILURE_RECORD: Final[re.Pattern[str]] = re.compile(
    r"^operation failed definition=\S+ operation=(?P<operation>\S+) diagnostic_ref=\S+ "
    r"exception_type=(?P<type>\S+) raising_frame=(?P<raising>\S+) application_frame=(?P<application>\S+)"
)


class _FailureFrames(logging.Handler):
    """Collect, per operation id, the exception type and code frames the supervisor logs for a failure.

    A failed operation serves no sentence and keeps its exception message out of every record by design, so
    these code coordinates are what makes a failure without a refusal code diagnosable from the table. The
    application delivers records to handlers formatted, on its dispatch thread, so the handler reads the
    formatted message and the caller flushes the dispatch before reading the frames.
    """

    def __init__(self) -> None:
        super().__init__(logging.ERROR)
        self.frames: dict[str, str] = {}

    @override
    def emit(self, record: logging.LogRecord) -> None:
        found = _FAILURE_RECORD.match(record.getMessage())
        if found is None:
            return
        self.frames[found["operation"]] = (
            f"{found['type']} raised at {found['raising']} (application frame {found['application']})"
        )


@contextmanager
def _failure_frames() -> Generator[_FailureFrames]:
    handler = _FailureFrames()
    logger = logging.getLogger(_EXECUTOR_LOGGER)
    logger.addHandler(handler)
    try:
        yield handler
        flush_logging()
    finally:
        logger.removeHandler(handler)


def _result_words(value: object) -> str | None:
    """The ``refusal_words`` sentence a typed refusal result carries, on one line, wherever it nests."""
    if isinstance(value, Mapping):
        words = str(value.get("refusal_words") or "")
        if words.strip():
            return " ".join(words.split())
        children: Sequence[object] = tuple(value.values())
    elif isinstance(value, list | tuple):
        children = value
    else:
        return None
    found: str | None = None
    for child in children:
        found = _result_words(child)
        if found is not None:
            break
    return found


def _served_words(world: PersonaWorld, terminal: OperationPublicProjectionV1) -> str | None:
    """The sentence the application serves an operator for a refused or failed operation, on one line.

    This reads the recorded error detail through the settled-result read, as the command line and the
    workbench do, so the words are those a frontend shows. ``None`` when the operation recorded none.
    """
    if terminal.terminal_condition not in TERMINAL_CONDITIONS_WITH_ERROR_DETAIL:
        return None
    contract = terminal.definition_contract
    resolved = asyncio.run(
        world.services.result.resolve(
            OperationResultProjectionRequestV1(
                operation_id=terminal.operation_id,
                terminal_revision=terminal.revision,
                definition_contract_digest=contract.definition_contract_digest,
                result_schema=operation_error_detail_schema(),
            ),
            OperationErrorDetailV1,
        )
    )
    if not isinstance(resolved, OperationResultProjectionSuccessV1):
        return None
    words = resolved.projection.refusal_words if isinstance(resolved.projection, OperationErrorDetailV1) else None
    return None if words is None else " ".join(words.split())


def run_operation[Projection: BaseModel](
    world: PersonaWorld,
    definition_id: str,
    payload: BaseModel,
    projection: type[Projection],
    *,
    subject: str | None = None,
) -> Projection:
    """Settle one registered operation and return its public result as ``projection``.

    A calculation of a return the persona gives values for is preceded, on its first
    calculation, by their entry through the declaration edit, as an operator enters them.
    A calculation of a return the persona states a prior value for is followed by the
    attestation of that value, where the application offers it, and calculated again so
    the result reads the stated figure.
    """
    if isinstance(payload, ModeloWorkCalculateRequest) and world.work_inputs:
        enter_return_work_inputs(world, payload.work_unit_id)
    result = settle_operation(world, definition_id, payload, subject=subject)
    if not isinstance(result, projection):
        raise PersonaMaterialisationError(f"{definition_id} published no {projection.__name__}")
    if isinstance(payload, ModeloWorkCalculateRequest) and isinstance(result, ModeloWorkCalculatePublicResultV3):
        result = _with_attested_prior_values(world, definition_id, payload, result, subject=subject)
        if not isinstance(result, projection):
            raise PersonaMaterialisationError(f"{definition_id} published no {projection.__name__}")
    return result


def attested_before_calculating(world: PersonaWorld, *, modelo: str, year: int, period: str) -> bool:
    """Whether the return's attested prior figures are stated before its first calculation.

    So they are for a return the persona attests figures on and enters no work input on: its calculation refuses
    while a required source return is neither held nor stated. A return with work inputs keeps the order an operator
    follows: its inputs are entered when it is first calculated, and its attestations follow that calculation.
    """
    if not entries_on(world.attested_prior_values, world.envelope, modelo=modelo, filing_year=year, period=period):
        return False
    return not any(
        item.modelo == modelo and item.period == period and item.year.resolve(world.envelope) == year
        for item in world.work_inputs
    )


def attest_before_first_calculation(
    world: PersonaWorld, *, modelo: str, year: int, period: str, work_unit_id: str
) -> None:
    """State the return's attested prior figures on its work unit before its first calculation, where they are so stated.

    An entry the admitted baseline does not offer the attestation on is not submitted, as after a calculation: the
    application then reads the figure from a source it holds, such as an earlier quarter of the same year, and that
    source governs. Every attested binding is one its edition declares (``check_prior_value_bindings``), so an
    unoffered entry cannot hide a binding the edition lacks.
    """
    if not attested_before_calculating(world, modelo=modelo, year=year, period=period):
        return

    def settle(definition_id: str, payload: BaseModel, *, subject: str | None = None) -> BaseModel | None:
        return settle_operation(world, definition_id, payload, subject=subject)

    try:
        attest_return_prior_values(
            world.attested_prior_values,
            envelope=world.envelope,
            profile_id=world.profile_id,
            work_unit_id=work_unit_id,
            modelo=modelo,
            filing_year=year,
            period=period,
            settle=settle,
        )
    except PriorValueAttestationError as error:
        raise PersonaMaterialisationError(f"{modelo} {year} {period}: {error}") from error


def enter_return_work_inputs(world: PersonaWorld, work_unit_id: str) -> None:
    """Enter the values the persona gives for the work unit's return, before its first calculation."""

    def settle(definition_id: str, payload: BaseModel, *, subject: str | None = None) -> BaseModel | None:
        return settle_operation(world, definition_id, payload, subject=subject)

    try:
        enter_work_inputs(
            world.work_inputs,
            envelope=world.envelope,
            operation=world.operation,
            profile_id=world.profile_id,
            work_unit_id=work_unit_id,
            settle=settle,
        )
    except WorkInputError as error:
        raise PersonaMaterialisationError(str(error)) from error


def _with_attested_prior_values(
    world: PersonaWorld,
    definition_id: str,
    payload: ModeloWorkCalculateRequest,
    calculated: ModeloWorkCalculatePublicResultV3,
    *,
    subject: str | None,
) -> BaseModel:
    """``calculated``, or its calculation again once the persona's stated prior values and work-income statements are made."""
    unit = calculated.unit
    if not state_offered_statements(
        world,
        modelo=unit.modelo,
        filing_year=unit.filing_year,
        period=unit.period.code,
        work_unit_id=calculated.work_unit_id,
    ):
        return calculated
    recalculated = settle_operation(world, definition_id, payload, subject=subject)
    if not isinstance(recalculated, ModeloWorkCalculatePublicResultV3):
        raise PersonaMaterialisationError(f"{definition_id} published no calculation after the attestation")
    return recalculated


def state_offered_statements(
    world: PersonaWorld, *, modelo: str, filing_year: int, period: str, work_unit_id: str
) -> bool:
    """Make the persona's stated prior values and work-income statements the work unit's form offers; whether any was made.

    A return that made one must be calculated again to read the stated figure. The statements travel as calculating
    edits, so a work unit that took one holds a calculation.
    """

    def settle(
        definition_id: str,
        payload: BaseModel,
        *,
        subject: str | None = None,
    ) -> BaseModel | None:
        return settle_operation(world, definition_id, payload, subject=subject)

    try:
        attested = attest_return_prior_values(
            world.attested_prior_values,
            envelope=world.envelope,
            profile_id=world.profile_id,
            work_unit_id=work_unit_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            settle=settle,
        ).applied
        stated = state_work_income_none(
            world.work_income_none_statements,
            envelope=world.envelope,
            profile_id=world.profile_id,
            modelo=modelo,
            filing_year=filing_year,
            work_unit_id=work_unit_id,
            settle=settle,
        )
    except PriorValueAttestationError as error:
        raise PersonaMaterialisationError(str(error)) from error
    return attested is not None or stated


def public_result(world: PersonaWorld, terminal: OperationPublicProjectionV1) -> BaseModel | None:
    """The public result, or refusal detail, a settled operation publishes, in its registered model."""
    contract = terminal.definition_contract
    if contract.result_schema is None or (terminal.result_ref is None and terminal.refusal_ref is None):
        return None
    registration = world.registry.lookup_public_registration(terminal.definition_id)
    (model,) = (
        binding.model_type for binding in registration.schema_bindings if binding.identity == contract.result_schema
    )
    resolved = asyncio.run(
        world.services.result.resolve(
            OperationResultProjectionRequestV1(
                operation_id=terminal.operation_id,
                terminal_revision=terminal.revision,
                definition_contract_digest=contract.definition_contract_digest,
                result_schema=contract.result_schema,
            ),
            model,
        )
    )
    if not isinstance(resolved, OperationResultProjectionSuccessV1):
        return None
    projection = resolved.projection
    return projection if isinstance(projection, BaseModel) else None


__all__ = [
    "attest_before_first_calculation",
    "attested_before_calculating",
    "enter_return_work_inputs",
    "public_result",
    "run_operation",
    "settle_operation",
    "state_offered_statements",
]
