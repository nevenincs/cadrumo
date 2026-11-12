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
Anything else leaves no detail.

Either detail also carries the finished sentence a frontend shows for it, in
the language the worker's catalogue renders. A frontend that holds no tax
vocabulary of its own shows that sentence as served. It is worded only from
the catalogue key and the scrubbed, bounded context the detail itself
carries, never from an exception's free text or raw context, so it discloses
nothing the detail does not. The detail is stored as an encrypted operand,
referenced from the terminal receipt, and released only through the settled
result read with the definition's own RESULT authority.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from typing import TYPE_CHECKING, Annotated, Final, Literal, Self

from pydantic import BaseModel, Field, NonNegativeInt, StringConstraints, ValidationError, model_validator

from ...core.errors.error_codes import (
    ErrorCode,
    get_registered_error_code,
    get_registered_error_code_by_code,
    public_error_context,
    scrub_error_context,
)
from ...core.errors.hierarchy import CadrumoError, RecordedRegisteredError
from ...core.errors.record_fault import internal_record_fault_context
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import (
    extract_placeholders,
    lookup_translation,
    normalise_supported_language,
    output_language,
    tr,
)
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import TERMINAL_CONDITIONS_WITH_ERROR_DETAIL, OperationLifecycle
from ..cli_exception_preconditions import cli_exception_envelope_view, nested_terminal_precondition_verdict
from ..operator_actions.models import PreconditionVerdict
from ..operator_actions.served_actions import serve_precondition_verdict
from .frontend_requests import (
    OperationResultProjectionRefusalCode,
    OperationResultProjectionRefusalV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from .next_step import OperationNextStepV1, error_next_step
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

#: Longest served sentence; a longer one gives way to its code's own sentence.
MAX_OPERATION_ERROR_WORDS_LENGTH: Final[int] = 2_048

#: The sentence served when neither the error's key nor its code's key can be worded from the detail.
UNWORDED_REGISTERED_ERROR_LOCALE_KEY: Final[str] = "application.operations.error_detail.unworded"

#: The sentence served for a record the application built that failed its own contract.
RECORD_FAULT_WORDS_LOCALE_KEY: Final[str] = "application.operations.error_detail.record_fault"

_ERROR_CODE_PATTERN: Final[str] = r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$"
_MESSAGE_KEY_PATTERN: Final[str] = r"^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+$"
_CONTEXT_KEY_PATTERN: Final[str] = r"^[A-Za-z_][A-Za-z0-9_]*$"


class OperationErrorDetailKind(StrEnum):
    """Which of the two supported failure shapes a detail describes."""

    #: A registered domain or application error stopped the executor.
    REGISTERED_ERROR = "registered_error"
    #: A record the application built failed its own validation contract.
    RECORD_VALIDATION = "record_validation"


_KEY_MIN_LENGTH = 3
_MESSAGE_KEY_MAX_LENGTH = 256
_EMPTY_JSON_OBJECT_LENGTH = 2


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
    error_code: (
        Annotated[str, StringConstraints(min_length=_KEY_MIN_LENGTH, max_length=128, pattern=_ERROR_CODE_PATTERN)]
        | None
    )
    message_key: (
        Annotated[
            str,
            StringConstraints(
                min_length=_KEY_MIN_LENGTH, max_length=_MESSAGE_KEY_MAX_LENGTH, pattern=_MESSAGE_KEY_PATTERN
            ),
        ]
        | None
    )
    context: Annotated[tuple[OperationErrorContextEntryV1, ...], Field(max_length=MAX_OPERATION_ERROR_CONTEXT_ENTRIES)]
    context_entries_omitted: NonNegativeInt = 0
    #: The typed precondition verdict as its canonical JSON. Its evidence model
    #: serializes differently from how it validates, so it cannot be a public
    #: schema member; the text is validated as the verdict on both sides.
    precondition_verdict_json: (
        Annotated[
            str, StringConstraints(min_length=_EMPTY_JSON_OBJECT_LENGTH, max_length=MAX_OPERATION_ERROR_VERDICT_LENGTH)
        ]
        | None
    ) = None
    #: The finished sentence a frontend shows for this stop, worded from the
    #: catalogue key and this detail's own scrubbed context. ``None`` only on
    #: a detail recorded before sentences were served.
    refusal_words: (
        Annotated[str, StringConstraints(min_length=1, max_length=MAX_OPERATION_ERROR_WORDS_LENGTH)] | None
    ) = None
    #: The language ``refusal_words`` is in: the one the worker's catalogue rendered.
    refusal_words_language: OutputLanguage | None = None
    #: The registered operation the refusal names for putting it right, as a closed kind with the declaration
    #: it concerns and the words that offer it, in ``refusal_words_language``. ``None`` when the refusal names none.
    next_step: OperationNextStepV1 | None = None

    @model_validator(mode="after")
    def _closed_shape(self) -> Self:
        keys = tuple(entry.key for entry in self.context)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("operation error detail context keys must be unique and ordered")
        self._check_word_language()
        if self.kind is OperationErrorDetailKind.REGISTERED_ERROR:
            if self.error_code is None:
                raise ValueError("a registered error detail requires its registered code")
            get_registered_error_code_by_code(self.error_code)
        elif (
            self.error_code is not None
            or self.message_key is not None
            or self.precondition_verdict_json is not None
            or self.next_step is not None
        ):
            raise ValueError("a record validation detail carries only its fault context")
        self.precondition_verdict()
        return self

    def _check_word_language(self) -> None:
        """Keep the refusal and its offered step bound to their served language."""
        if (self.refusal_words is None) != (self.refusal_words_language is None):
            raise ValueError("served words name the language they are in")
        if self.next_step is not None and self.refusal_words_language is None:
            raise ValueError("a served step is worded in the language of the refusal's own words")

    def context_mapping(self) -> dict[str, str]:
        """Return the scrubbed context as the envelope's string mapping."""
        return {entry.key: entry.value for entry in self.context}

    def precondition_verdict(self) -> PreconditionVerdict | None:
        """Restore the typed verdict the stopped error carried, or ``None``."""
        if self.precondition_verdict_json is None:
            return None
        return PreconditionVerdict.model_validate_json(self.precondition_verdict_json)

    def recorded_error(self) -> RecordedRegisteredError | None:
        """Raise-ready form of the registered error the detail records, keeping its verdict.

        ``None`` for a record fault, which has no registered error of its own.
        """
        if self.kind is not OperationErrorDetailKind.REGISTERED_ERROR or self.error_code is None:
            return None
        return RecordedRegisteredError(
            self.error_code,
            context=self.context_mapping(),
            translated_message=self.message_key,
            precondition_verdict=self.precondition_verdict(),
        )


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
    return (
        _KEY_MIN_LENGTH <= len(candidate) <= _MESSAGE_KEY_MAX_LENGTH
        and re.fullmatch(_MESSAGE_KEY_PATTERN, candidate) is not None
    )


def served_words_language() -> OutputLanguage:
    """The language the worker's catalogue renders in, the one ``tr`` uses here."""
    return OutputLanguage(normalise_supported_language(output_language()) or OutputLanguage.EN.value)


def _worded(key: str, language: OutputLanguage, context: dict[str, str]) -> str | None:
    """``key``'s sentence filled from ``context`` alone, or ``None`` when it cannot be finished.

    A sentence whose placeholder has no carried value, whose catalogue entry is
    missing, or that comes out over the bound is not served: a frontend would
    show a half-filled template or a bare key.
    """
    template = lookup_translation(key, locale=language.value)
    if template is None:
        return None
    names = extract_placeholders(template)
    if not names <= context.keys():
        return None
    try:
        words = tr(key, locale=language.value, **{name: context[name] for name in names}).strip()
    except Exception:
        return None
    if not words or extract_placeholders(words) or len(words) > MAX_OPERATION_ERROR_WORDS_LENGTH:
        return None
    return words


def _registered_error_words(
    registered: ErrorCode,
    error_key: str | None,
    entries: tuple[OperationErrorContextEntryV1, ...],
) -> tuple[str, OutputLanguage]:
    """The sentence served for a registered error, chosen as the error envelope chooses its message.

    The error's own catalogue key comes first unless its code's registry entry
    owns the public message; then the code's own catalogue sentence; last a
    sentence that names the code. Only the detail's scrubbed context fills them.
    """
    language = served_words_language()
    context = {entry.key: entry.value for entry in entries}
    registry_owned = registered.public_message_from_registry or ".canonical_" in registered.message_key
    keys = (registered.message_key,) if registry_owned or error_key is None else (error_key, registered.message_key)
    for key in keys:
        words = _worded(key, language, context)
        if words is not None:
            return words, language
    return tr(UNWORDED_REGISTERED_ERROR_LOCALE_KEY, locale=language.value, error_code=registered.code), language


def build_operation_error_detail(error: BaseException) -> OperationErrorDetailV1 | None:
    """Project the public facts of ``error``, or ``None`` when it has none to give.

    Free-text exception messages, arguments and raw values never enter the
    detail: a registered error contributes its code, its catalogue key and the
    envelope's scrubbed context; a validation fault contributes the record
    fault projection, which names fields and rules but never a value. The
    served sentence is worded from those same facts.
    """
    if isinstance(error, CadrumoError):
        try:
            registered = get_registered_error_code(error)
        except Exception:
            return None
        view = cli_exception_envelope_view(error)
        entries, omitted = _bounded_context(public_error_context(view))
        key = view.translated_message
        message_key = key if isinstance(key, str) and _is_message_key(key) else None
        words, language = _registered_error_words(registered, message_key, entries)
        verdict = nested_terminal_precondition_verdict(error)
        verdict_json = None if verdict is None else serve_precondition_verdict(verdict, language).model_dump_json()
        if verdict_json is not None and len(verdict_json) > MAX_OPERATION_ERROR_VERDICT_LENGTH:
            verdict_json = None
        return OperationErrorDetailV1(
            kind=OperationErrorDetailKind.REGISTERED_ERROR,
            error_code=registered.code,
            message_key=message_key,
            context=entries,
            context_entries_omitted=omitted,
            precondition_verdict_json=verdict_json,
            refusal_words=words,
            refusal_words_language=language,
            next_step=error_next_step(error, language),
        )
    if isinstance(error, ValidationError):
        entries, omitted = _bounded_context(scrub_error_context(internal_record_fault_context(error)))
        words, language = _record_fault_words(error)
        return OperationErrorDetailV1(
            kind=OperationErrorDetailKind.RECORD_VALIDATION,
            error_code=None,
            message_key=None,
            context=entries,
            context_entries_omitted=omitted,
            refusal_words=words,
            refusal_words_language=language,
        )
    return None


def operation_refusal_words(error: BaseException) -> tuple[str, OutputLanguage] | None:
    """The sentence a typed refusal detail serves for ``error``, worded as the error detail words it.

    A definition that records its own refusal detail instead of the error
    detail carries this sentence in it, so every refusal a frontend reads is
    worded by the same rules. ``None`` for an error with no public facts.
    """
    if isinstance(error, CadrumoError):
        try:
            registered = get_registered_error_code(error)
        except Exception:
            return None
        view = cli_exception_envelope_view(error)
        entries, _omitted = _bounded_context(public_error_context(view))
        key = view.translated_message
        return _registered_error_words(
            registered, key if isinstance(key, str) and _is_message_key(key) else None, entries
        )
    if isinstance(error, ValidationError):
        return _record_fault_words(error)
    return None


def operation_catalogue_refusal_words(
    error_code: str, message_key: str, context: Mapping[str, str] | None = None
) -> tuple[str, OutputLanguage]:
    """The sentence a typed refusal serves from a catalogue key written for a frontend, worded as an error is.

    A definition whose frontends show the served words verbatim keeps those
    sentences under their own keys, apart from a command line's messages, which
    may name options only a command line has. The definition authored the key,
    so it is worded before the code's own sentence even when the code's registry
    entry owns the public message of an error raised under it. Only ``context``,
    scrubbed and bounded as an error detail's is, fills a placeholder: a key
    that needs none discloses nothing the refusal's registered ``error_code``
    and key do not. A key that cannot be worded gives way to the code's own
    sentence, then to one that names the code.
    """
    registered = get_registered_error_code_by_code(error_code)
    entries, _omitted = _bounded_context(None if context is None else dict(context))
    language = served_words_language()
    words = _worded(message_key, language, {entry.key: entry.value for entry in entries})
    if words is not None:
        return words, language
    return _registered_error_words(registered, None, ())


def _registered_cause(error: ValidationError) -> CadrumoError | None:
    """The registered error a validator raised for the first failed rule, where one crossed the boundary.

    A validator callback raises a registered error, and the Pydantic boundary
    carries it as the ``__cause__`` of the ``ValueError`` the record's
    validation reports. A rule with no registered cause has none.
    """
    for failure in error.errors():
        raised = failure.get("ctx", {}).get("error")
        cause = getattr(raised, "__cause__", None)
        if isinstance(cause, CadrumoError):
            return cause
    return None


def _record_fault_words(error: ValidationError) -> tuple[str, OutputLanguage]:
    """The sentence served for a record that failed its contract.

    When the first failed rule was a registered refusal raised inside the
    record's own validator, that refusal's sentence is served, worded from its
    scrubbed and bounded public context as a registered error's detail would
    be. Otherwise the record fault's own sentence.
    """
    cause = _registered_cause(error)
    words = None if cause is None else operation_refusal_words(cause)
    if words is not None:
        return words
    language = served_words_language()
    return tr(RECORD_FAULT_WORDS_LOCALE_KEY, locale=language.value), language


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
    if receipt.condition not in TERMINAL_CONDITIONS_WITH_ERROR_DETAIL or receipt.error_detail_ref is None:
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
    "MAX_OPERATION_ERROR_WORDS_LENGTH",
    "OPERATION_ERROR_DETAIL_SCHEMA_ID",
    "RECORD_FAULT_WORDS_LOCALE_KEY",
    "UNWORDED_REGISTERED_ERROR_LOCALE_KEY",
    "OperationErrorContextEntryV1",
    "OperationErrorDetailKind",
    "OperationErrorDetailV1",
    "build_operation_error_detail",
    "operation_catalogue_refusal_words",
    "operation_error_detail_schema",
    "operation_refusal_words",
    "resolve_operation_error_detail",
    "served_words_language",
]
