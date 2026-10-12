"""What refused a request before it became an operation, in the words the command line shows.

A request that fails its model fails for stated reasons: a field is missing, a
field is unknown, a value breaks a rule. A caller in another process can only
correct the request when those reasons reach it, and it is told what a person
at the command line is told, including any guidance the validator wrote.

A fault therefore repeats what the validator chose to say, as the command line
does: where, what kind, and the validator's own message. It never attaches the
refused object: the input, the error context and the documentation link of the
model's report stay behind, because an input can be a whole nested payload and
none of it is wording anyone chose.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Final

from pydantic import BaseModel, Field, StringConstraints, ValidationError

from .errors.error_codes import get_registered_error_code, resolve_error_message
from .errors.hierarchy import CadrumoError
from .models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG

MAX_REQUEST_FAULTS: Final = 32
"""How many faults one refusal carries; a request with more is told the first of them."""

_MAX_LOCATION_ITEMS: Final = 32
_MAX_LOCATION_ITEM_CHARACTERS: Final = 256
_MAX_MESSAGE_CHARACTERS: Final = 1024
_MAX_TYPE_CHARACTERS: Final = 128

type _LocationItem = Annotated[str, StringConstraints(max_length=_MAX_LOCATION_ITEM_CHARACTERS)] | int


class RequestFault(BaseModel):
    """One reason a request was refused: where, what kind, and the validator's own message."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    location: Annotated[tuple[_LocationItem, ...], Field(max_length=_MAX_LOCATION_ITEMS)]
    """The path to the faulted member: field names, and positions within a sequence."""
    type: Annotated[str, StringConstraints(min_length=1, max_length=_MAX_TYPE_CHARACTERS)]
    """The kind of fault: the request model's name for it, or a registered error's code."""
    message: Annotated[str, StringConstraints(min_length=1, max_length=_MAX_MESSAGE_CHARACTERS)]
    """What the validator said, as the command line shows it."""


def _location(path: Sequence[object]) -> tuple[str | int, ...]:
    return tuple(
        item if isinstance(item, int) and not isinstance(item, bool) else str(item)[:_MAX_LOCATION_ITEM_CHARACTERS]
        for item in path[:_MAX_LOCATION_ITEMS]
    )


def request_faults(error: ValidationError) -> tuple[RequestFault, ...]:
    """Return the faults a request model reported, each with its location, kind and message as reported.

    The report is read without the refused input, the model's error context
    and its documentation link, so no fault can hold any of them.
    """
    return tuple(
        RequestFault(
            location=_location(detail["loc"]),
            type=detail["type"][:_MAX_TYPE_CHARACTERS],
            message=detail["msg"][:_MAX_MESSAGE_CHARACTERS],
        )
        for detail in error.errors(include_url=False, include_context=False, include_input=False)[:MAX_REQUEST_FAULTS]
    )


def registered_error_fault(error: CadrumoError) -> RequestFault:
    """Return the one fault of a registered error a validator raised and the request model did not wrap.

    Such an error refuses the whole request, so the fault has no location. Its
    kind is the error's registered code and its message is the one the command
    line prints for the same error.
    """
    code = get_registered_error_code(error)
    return RequestFault(
        location=(),
        type=code.code[:_MAX_TYPE_CHARACTERS],
        message=resolve_error_message(error, code)[:_MAX_MESSAGE_CHARACTERS],
    )


def request_fault_line(fault: RequestFault) -> str:
    """Spell one fault for a person: the member it is about, then the rule, or the rule alone for the whole request."""
    location = ".".join(str(part) for part in fault.location)
    return f"{location}: {fault.message}" if location else fault.message


def request_faults_text(faults: Sequence[RequestFault]) -> str:
    """Spell several faults as one line of text, for a record that holds text and not a list."""
    return "; ".join(request_fault_line(fault) for fault in faults)


__all__ = [
    "MAX_REQUEST_FAULTS",
    "RequestFault",
    "registered_error_fault",
    "request_fault_line",
    "request_faults",
    "request_faults_text",
]
