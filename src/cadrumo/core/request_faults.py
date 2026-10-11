"""What a request model said was wrong with a request, with the request's values left out.

A request that fails its model fails for stated reasons: a field is missing, a
field is unknown, a value breaks a rule. A caller in another process can only
correct the request when those reasons reach it, and the request's own values
must not travel with them: a fault is written to wires, logs and transcripts
that the request itself never reaches.

A fault therefore carries where, what kind and why, and never the offending
value. The model's own wording is carried when it says nothing of the value it
refused. Wording that repeats the value is replaced by a fixed sentence, and
the location and the kind of the fault still say which rule it was.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Annotated, Final

from pydantic import BaseModel, Field, StringConstraints, ValidationError

from .models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG

MAX_REQUEST_FAULTS: Final = 32
"""How many faults one refusal carries; a request with more is told the first of them."""

VALUE_FREE_FAULT_MESSAGE: Final = "the value does not satisfy this field's rule"
"""What a fault says when the model's own wording would repeat the value it refused."""

_MAX_LOCATION_ITEMS: Final = 32
_MAX_LOCATION_ITEM_CHARACTERS: Final = 256
_MAX_MESSAGE_CHARACTERS: Final = 1024
_MAX_TYPE_CHARACTERS: Final = 128
_MAX_VALUES_READ: Final = 4096
_MIN_REPEATED_CHARACTERS: Final = 3
"""The shortest text read as a repeated value; shorter text occurs in any sentence by chance."""

type _LocationItem = Annotated[str, StringConstraints(max_length=_MAX_LOCATION_ITEM_CHARACTERS)] | int


class RequestFault(BaseModel):
    """One reason a request model refused a request: where, what kind and why, and never the value."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    location: Annotated[tuple[_LocationItem, ...], Field(max_length=_MAX_LOCATION_ITEMS)]
    """The path to the faulted member: field names, and positions within a sequence."""
    type: Annotated[str, StringConstraints(min_length=1, max_length=_MAX_TYPE_CHARACTERS)]
    """The kind of fault, as the request model names it."""
    message: Annotated[str, StringConstraints(min_length=1, max_length=_MAX_MESSAGE_CHARACTERS)]
    """The rule that was broken, in words that do not repeat the value."""


def _texts_of(value: object) -> list[str] | None:
    """Collect the text of every value inside a refused input: its strings and its numbers.

    Member names are not values, so a mapping contributes what it holds and
    not its keys. ``None`` means the input holds more values than are read,
    so no list of them is complete.
    """
    texts: list[str] = []
    pending: list[object] = [value]
    read = 0
    while pending:
        item = pending.pop()
        read += 1
        if read > _MAX_VALUES_READ:
            return None
        if item is None or isinstance(item, bool):
            continue
        if isinstance(item, str):
            texts.append(item)
        elif isinstance(item, int | float | Decimal):
            texts.append(str(item))
        elif isinstance(item, bytes | bytearray | memoryview):
            texts.append(bytes(item).decode("utf-8", errors="replace"))
        elif isinstance(item, BaseModel):
            pending.append(item.model_dump(mode="python"))
        elif isinstance(item, Mapping):
            pending.extend(item.values())
        elif isinstance(item, Sequence | set | frozenset):
            pending.extend(item)
        else:
            texts.append(str(item))
    return texts


def _repeats_a_value(message: str, refused: object) -> bool:
    """Tell whether a message says, as a word of its own, any value of the input it refused.

    An input too large to read through is answered as though it were repeated:
    a message is carried only when it is known to be free of the value.
    """
    texts = _texts_of(refused)
    if texts is None:
        return True
    spoken = message.casefold()
    for text in texts:
        candidate = text.strip().casefold()
        if len(candidate) < _MIN_REPEATED_CHARACTERS:
            continue
        if re.search(rf"(?<!\w){re.escape(candidate)}(?!\w)", spoken) is not None:
            return True
    return False


def _location(path: Sequence[object]) -> tuple[str | int, ...]:
    return tuple(
        item if isinstance(item, int) and not isinstance(item, bool) else str(item)[:_MAX_LOCATION_ITEM_CHARACTERS]
        for item in path[:_MAX_LOCATION_ITEMS]
    )


def request_faults(error: ValidationError) -> tuple[RequestFault, ...]:
    """Return the faults a request model reported, each without the value it refused.

    The model's report is read with the refused input beside each fault only
    so that a message repeating that input can be recognised and replaced.
    No fault keeps the input, the model's error context or its documentation
    link.
    """
    faults: list[RequestFault] = []
    for detail in error.errors(include_url=False, include_context=False, include_input=True)[:MAX_REQUEST_FAULTS]:
        message = detail["msg"]
        if not message or _repeats_a_value(message, detail.get("input")):
            message = VALUE_FREE_FAULT_MESSAGE
        faults.append(
            RequestFault(
                location=_location(detail["loc"]),
                type=detail["type"][:_MAX_TYPE_CHARACTERS],
                message=message[:_MAX_MESSAGE_CHARACTERS],
            )
        )
    return tuple(faults)


def request_fault_line(fault: RequestFault) -> str:
    """Spell one fault for a person: the member it is about, then the rule, or the rule alone for the whole request."""
    location = ".".join(str(part) for part in fault.location)
    return f"{location}: {fault.message}" if location else fault.message


def request_faults_text(faults: Sequence[RequestFault]) -> str:
    """Spell several faults as one line of text, for a record that holds text and not a list."""
    return "; ".join(request_fault_line(fault) for fault in faults)


__all__ = [
    "MAX_REQUEST_FAULTS",
    "VALUE_FREE_FAULT_MESSAGE",
    "RequestFault",
    "request_fault_line",
    "request_faults",
    "request_faults_text",
]
