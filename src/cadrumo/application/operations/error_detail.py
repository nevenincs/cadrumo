"""Bounded public detail of why one supervised operation refused or failed.

The operation journal records only a refused operation's registry code, or a
failed one's code and an opaque correlation digest, because an exception's
message, arguments and context must never enter credential-free persistence.
A frontend in another process therefore cannot render the operator-facing
error the in-process command would have shown: the typed reason, the row it
concerns, the remedy, or the record that failed its own contract.

This module carries exactly that much, and no more. When an executor stops
with a registered :class:`~cadrumo.core.errors.hierarchy.CadrumoError`, the
detail holds the registered code, its catalogue message key, the error
envelope's scrubbed context and any typed precondition verdict. When it stops
with a :class:`~pydantic.ValidationError` -- a record the application itself
built failed its contract -- the detail holds the record fault projection,
which names the record, the field path and the broken rule and never a value.
Anything else leaves no detail. The detail is stored as an encrypted operand,
referenced from the terminal receipt, and released only through the settled
result read with the definition's own RESULT authority.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from typing import TYPE_CHECKING, Annotated, Final, Literal, Self

from pydantic import BaseModel, Field, NonNegativeInt, StringConstraints, ValidationError, model_validator

from ...core.errors.error_codes import (
    get_registered_error_code,
    get_registered_error_code_by_code,
    public_error_context,
    scrub_error_context,
)
from ...core.errors.hierarchy import CadrumoError
from ...core.errors.record_fault import internal_record_fault_context
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationLifecycle, OperationTerminalCondition
from ..cli_exception_preconditions import cli_exception_envelope_view, nested_terminal_precondition_verdict
from ..operator_actions.models import PreconditionVerdict
from .frontend_requests import (
    OperationResultProjectionRefusalCode,
    OperationResultProjectionRefusalV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from .registry import OperationPublicDefinitionContractV1, OperationRegistry
from .schema_identity import OperationSchemaIdentityV1

if TYPE_CHECKING:
    from .models import OperationTerminalReceipt
    from .persistence.journal import (
        OperationObservationReader,
        OperationPersistedSnapshot,
        OperationSecureReferenceStore,
    )

#: Public schema identity under which a refused or failed operation's detail is read.
OPERATION_ERROR_DETAIL_SCHEMA_ID: Final[str] = "operation.error_detail"

#: Most context entries one detail carries; the rest are counted, never clipped silently.
MAX_OPERATION_ERROR_CONTEXT_ENTRIES: Final[int] = 64

#: Longest single context value carried; a longer value is counted as omitted.
MAX_OPERATION_ERROR_CONTEXT_VALUE_LENGTH: Final[int] = 4_096

#: Longest canonical JSON of one precondition verdict the detail carries.
MAX_OPERATION_ERROR_VERDICT_LENGTH: Final[int] = 32_768

_ERROR_CODE_PATTERN: Final[str] = r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$"
_MESSAGE_KEY_PATTERN: Final[str] = r"^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+$"
_CONTEXT_KEY_PATTERN: Final[str] = r"^[A-Za-z_][A-Za-z0-9_]*$"


class OperationErrorDetailKind(StrEnum):
    """Which of the two supported failure shapes a detail describes."""

    #: A registered domain or application error stopped the executor.
    REGISTERED_ERROR = "registered_error"
    #: A record the application built failed its own validation contract.
    RECORD_VALIDATION = "record_validation"


class OperationErrorContextEntryV1(BaseModel):
    """One scrubbed context fact, already rendered as the envelope renders it."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    key: Annotated[str, StringConstraints(min_length=1, max_length=128, pattern=_CONTEXT_KEY_PATTERN)]
    value: Annotated[str, StringConstraints(max_length=MAX_OPERATION_ERROR_CONTEXT_VALUE_LENGTH)]


class OperationErrorDetailV1(BaseModel):
    """The bounded public facts a frontend needs to render one stopped operation."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    detail_version: Literal[1] = 1
    kind: OperationErrorDetailKind
    error_code: Annotated[str, StringConstraints(min_length=3, max_length=128, pattern=_ERROR_CODE_PATTERN)] | None
    message_key: Annotated[str, StringConstraints(min_length=3, max_length=256, pattern=_MESSAGE_KEY_PATTERN)] | None
    context: Annotated[tuple[OperationErrorContextEntryV1, ...], Field(max_length=MAX_OPERATION_ERROR_CONTEXT_ENTRIES)]
    context_entries_omitted: NonNegativeInt = 0
    #: The typed precondition verdict as its canonical JSON. Its evidence model
    #: serializes differently from how it validates, so it cannot be a public
    #: schema member; the text is validated as the verdict on both sides.
    precondition_verdict_json: (
        Annotated[str, StringConstraints(min_length=2, max_length=MAX_OPERATION_ERROR_VERDICT_LENGTH)] | None
    ) = None

    @model_validator(mode="after")
    def _closed_shape(self) -> Self:
        keys = tuple(entry.key for entry in self.context)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("operation error detail context keys must be unique and ordered")
        if self.kind is OperationErrorDetailKind.REGISTERED_ERROR:
            if self.error_code is None:
                raise ValueError("a registered error detail requires its registered code")
            get_registered_error_code_by_code(self.error_code)
        elif self.error_code is not None or self.message_key is not None or self.precondition_verdict_json is not None:
            raise ValueError("a record validation detail carries only its fault context")
        self.precondition_verdict()
        return self

    def context_mapping(self) -> dict[str, str]:
        """Return the scrubbed context as the envelope's string mapping."""
        return {entry.key: entry.value for entry in self.context}

    def precondition_verdict(self) -> PreconditionVerdict | None:
        """Restore the typed verdict the stopped error carried, or ``None``."""
        if self.precondition_verdict_json is None:
            return None
        return PreconditionVerdict.model_validate_json(self.precondition_verdict_json)


@cache
def operation_error_detail_schema() -> OperationSchemaIdentityV1:
    """Return the one public schema identity of :class:`OperationErrorDetailV1`."""
    return OperationSchemaIdentityV1.from_model(
        schema_id=OPERATION_ERROR_DETAIL_SCHEMA_ID,
        schema_version=1,
        model_type=OperationErrorDetailV1,
    )


def _bounded_context(context: dict[str, str] | None) -> tuple[tuple[OperationErrorContextEntryV1, ...], int]:
    """Keep the context entries the detail can carry and count the others."""
    entries: list[OperationErrorContextEntryV1] = []
    omitted = 0
    for key, value in sorted((context or {}).items()):
        if (
            len(entries) >= MAX_OPERATION_ERROR_CONTEXT_ENTRIES
            or len(value) > MAX_OPERATION_ERROR_CONTEXT_VALUE_LENGTH
            or not key.isidentifier()
            or len(key) > 128
        ):
            omitted += 1
            continue
        entries.append(OperationErrorContextEntryV1(key=key, value=value))
    return tuple(entries), omitted


def _is_message_key(candidate: str) -> bool:
    """Return whether ``candidate`` is shaped as a catalogue key rather than free text."""
    return 3 <= len(candidate) <= 256 and re.fullmatch(_MESSAGE_KEY_PATTERN, candidate) is not None


def build_operation_error_detail(error: BaseException) -> OperationErrorDetailV1 | None:
    """Project the public facts of ``error``, or ``None`` when it has none to give.

    Free-text exception messages, arguments and raw values never enter the
    detail: a registered error contributes its code, its catalogue key and the
    envelope's scrubbed context; a validation fault contributes the record
    fault projection, which names fields and rules but never a value.
    """
    if isinstance(error, CadrumoError):
        try:
            registered = get_registered_error_code(error)
        except Exception:
            return None
        view = cli_exception_envelope_view(error)
        entries, omitted = _bounded_context(public_error_context(view))
        key = view.translated_message
        verdict = nested_terminal_precondition_verdict(error)
        verdict_json = None if verdict is None else verdict.model_dump_json()
        if verdict_json is not None and len(verdict_json) > MAX_OPERATION_ERROR_VERDICT_LENGTH:
            verdict_json = None
        return OperationErrorDetailV1(
            kind=OperationErrorDetailKind.REGISTERED_ERROR,
            error_code=registered.code,
            message_key=key if isinstance(key, str) and _is_message_key(key) else None,
            context=entries,
            context_entries_omitted=omitted,
            precondition_verdict_json=verdict_json,
        )
    if isinstance(error, ValidationError):
        entries, omitted = _bounded_context(scrub_error_context(internal_record_fault_context(error)))
        return OperationErrorDetailV1(
            kind=OperationErrorDetailKind.RECORD_VALIDATION,
            error_code=None,
            message_key=None,
            context=entries,
            context_entries_omitted=omitted,
        )
    return None


def _refusal(code: OperationResultProjectionRefusalCode) -> OperationResultProjectionRefusalV1:
    return OperationResultProjectionRefusalV1(code=code, requested_version=1, diagnostic_ref=None)


@dataclass(frozen=True, slots=True)
class _TerminalErrorDetailSnapshot:
    snapshot: OperationPersistedSnapshot
    receipt: OperationTerminalReceipt


async def _terminal_snapshot_or_refusal(
    reader: OperationObservationReader,
    request: OperationResultProjectionRequestV1,
) -> _TerminalErrorDetailSnapshot | OperationResultProjectionRefusalV1:
    from .persistence.journal import OperationPersistedSnapshot
    from .projection_services import read_snapshot

    snapshot = await read_snapshot(reader, request.operation_id)
    if snapshot is None:
        return _refusal(OperationResultProjectionRefusalCode.UNKNOWN_OPERATION)
    if not isinstance(snapshot, OperationPersistedSnapshot):
        return _refusal(OperationResultProjectionRefusalCode.RESULT_PROJECTION_UNAVAILABLE)
    receipt = snapshot.terminal_receipt
    if snapshot.lifecycle is not OperationLifecycle.TERMINAL or receipt is None:
        return _refusal(OperationResultProjectionRefusalCode.OPERATION_NOT_TERMINAL)
    if snapshot.revision != request.terminal_revision:
        return _refusal(OperationResultProjectionRefusalCode.STALE_OPERATION_REVISION)
    return _TerminalErrorDetailSnapshot(snapshot=snapshot, receipt=receipt)


def _contract_or_refusal(
    snapshot: OperationPersistedSnapshot,
    registry: OperationRegistry,
    request: OperationResultProjectionRequestV1,
) -> OperationPublicDefinitionContractV1 | OperationResultProjectionRefusalV1:
    try:
        contract = registry.lookup_public_registration(snapshot.identity.definition_id).contract
    except Exception:
        return _refusal(OperationResultProjectionRefusalCode.DEFINITION_CONTRACT_MISMATCH)
    if (
        snapshot.definition_contract_digest != contract.definition_contract_digest
        or request.definition_contract_digest != contract.definition_contract_digest
    ):
        return _refusal(OperationResultProjectionRefusalCode.DEFINITION_CONTRACT_MISMATCH)
    return contract


def _detail_shape_refusal(
    receipt: OperationTerminalReceipt,
    request: OperationResultProjectionRequestV1,
) -> ContentDigest | OperationResultProjectionRefusalV1:
    if request.result_schema != operation_error_detail_schema():
        return _refusal(OperationResultProjectionRefusalCode.RESULT_SCHEMA_MISMATCH)
    if (
        receipt.condition not in {OperationTerminalCondition.REFUSED, OperationTerminalCondition.FAILED}
        or receipt.error_detail_ref is None
    ):
        return _refusal(OperationResultProjectionRefusalCode.RESULT_PROJECTION_UNAVAILABLE)
    return receipt.error_detail_ref


async def _read_encrypted_error_detail(
    operands: OperationSecureReferenceStore,
    reference: ContentDigest,
) -> OperationErrorDetailV1 | OperationResultProjectionRefusalV1:
    try:
        stored = await operands.resolve(reference, OperationErrorDetailV1)
        return OperationErrorDetailV1.model_validate(stored.model_dump(mode="python"))
    except Exception:
        return _refusal(OperationResultProjectionRefusalCode.RESULT_PROJECTION_UNAVAILABLE)


async def resolve_operation_error_detail(
    reader: OperationObservationReader,
    registry: OperationRegistry,
    operands: OperationSecureReferenceStore,
    request: OperationResultProjectionRequestV1,
) -> OperationResultProjectionSuccessV1[OperationErrorDetailV1] | OperationResultProjectionRefusalV1:
    """Release one refused or failed operation's stored detail, or a typed refusal."""
    terminal = await _terminal_snapshot_or_refusal(reader, request)
    if isinstance(terminal, OperationResultProjectionRefusalV1):
        return terminal
    contract = _contract_or_refusal(terminal.snapshot, registry, request)
    if isinstance(contract, OperationResultProjectionRefusalV1):
        return contract
    reference = _detail_shape_refusal(terminal.receipt, request)
    if isinstance(reference, OperationResultProjectionRefusalV1):
        return reference
    detail = await _read_encrypted_error_detail(operands, reference)
    if isinstance(detail, OperationResultProjectionRefusalV1):
        return detail
    return OperationResultProjectionSuccessV1[OperationErrorDetailV1](
        result_schema=operation_error_detail_schema(),
        definition_contract_digest=contract.definition_contract_digest,
        projection=detail,
    )


__all__ = [
    "MAX_OPERATION_ERROR_CONTEXT_ENTRIES",
    "MAX_OPERATION_ERROR_CONTEXT_VALUE_LENGTH",
    "MAX_OPERATION_ERROR_VERDICT_LENGTH",
    "OPERATION_ERROR_DETAIL_SCHEMA_ID",
    "OperationErrorContextEntryV1",
    "OperationErrorDetailKind",
    "OperationErrorDetailV1",
    "build_operation_error_detail",
    "operation_error_detail_schema",
    "resolve_operation_error_detail",
]
