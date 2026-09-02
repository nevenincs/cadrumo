"""The out-of-process protocol that opens one full-screen destination.

A sibling entrypoint may not import, load, annotate against or register from
the dedicated full-screen frontend: that frontend is an outermost process
entrypoint, and executing it as a child interpreter is the sanctioned way for
one entrypoint to reach the other. A command whose destination is a
full-screen surface therefore has to hand its subject INWARD as arguments and
read its result OUTWARD as data, because no live object survives the crossing.

This module is that crossing, and it is deliberately owned by neither side.
It sits beside both entrypoint packages rather than inside one, so the
argument surface and the outcome record have exactly one definition and
neither package has to import the other to agree with it. A copy per side
would agree only until someone edited one of them.

Two properties are load-bearing:

* The subject travels as IDENTIFIERS, never as a serialised domain record.
  The child re-resolves the subject through the application layer itself, so
  the surface it renders is read from persistence at the moment it renders,
  not from a snapshot the parent took earlier.
* Every value that steers behaviour is a stable machine token. Localized
  prose appears only as the ``detail`` payload of an outcome -- it is
  something the parent RENDERS, never something either side branches on.

The outcome cannot ride the child's standard output. The child inherits this
process's streams, because a full-screen session has to own the terminal for
its lifetime; anything it printed would land in front of the operator and
would be interleaved with the terminal control sequences the session emits.
So the parent names a file the child writes the outcome record into, and the
child's exit status says only whether the session ran to completion.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final


class FullScreenSessionProtocolError(ValueError):
    """A session request or outcome record that this protocol refuses to read."""


class FullScreenDestination(StrEnum):
    """The closed set of destinations a sibling entrypoint may request.

    The tokens are the canonical command identities the requesting commands
    already emit in their machine-readable envelopes, so a destination has one
    spelling across the whole product rather than a transport-only alias.
    """

    MODELO_WORK_REVIEW = "modelo.work.review"
    MODELO_WORK_SELECT = "modelo.work.select"


class FullScreenOutcomeKind(StrEnum):
    """How a completed session ended, as a stable token.

    ``COMPLETED`` is a destination that returns nothing leaving normally.
    ``SELECTED`` and ``CANCELLED`` are the two honest ends of a picker, kept
    distinct so an operator who chose nothing is not reported as having
    chosen. ``NOT_ADMITTED`` is a destination that declined to open, which is
    neither a completed read nor a failure of the session.
    """

    COMPLETED = "completed"
    SELECTED = "selected"
    CANCELLED = "cancelled"
    NOT_ADMITTED = "not_admitted"


DESTINATION_OPTION: Final[str] = "--destination"
OUTCOME_FILE_OPTION: Final[str] = "--outcome-file"
OUTPUT_LANGUAGE_OPTION: Final[str] = "--output-language"
WORK_UNIT_ID_OPTION: Final[str] = "--work-unit-id"
BUCKET_ID_OPTION: Final[str] = "--bucket-id"
INCLUDE_DISCARDED_FLAG: Final[str] = "--include-discarded"
SELF_TEST_FLAG: Final[str] = "--self-test"

OUTCOME_KIND_FIELD: Final[str] = "outcome"
OUTCOME_WORK_UNIT_ID_FIELD: Final[str] = "work_unit_id"
OUTCOME_DETAIL_FIELD: Final[str] = "detail"


@dataclass(frozen=True, slots=True)
class FullScreenSessionRequest:
    """One destination request, as it crosses into the child interpreter."""

    destination: FullScreenDestination
    outcome_file: Path
    work_unit_id: str | None = None
    bucket_id: str | None = None
    include_discarded: bool = False
    output_language: str | None = None
    self_test: bool = False


@dataclass(frozen=True, slots=True)
class FullScreenSessionOutcome:
    """What a completed session reports back, as it crosses out of the child."""

    kind: FullScreenOutcomeKind
    work_unit_id: str | None = None
    detail: str | None = None


def render_request_arguments(request: FullScreenSessionRequest) -> list[str]:
    """Build the child's argument list for one destination request."""
    arguments = [
        DESTINATION_OPTION,
        request.destination.value,
        OUTCOME_FILE_OPTION,
        str(request.outcome_file),
    ]
    if request.work_unit_id is not None:
        arguments += [WORK_UNIT_ID_OPTION, request.work_unit_id]
    if request.bucket_id is not None:
        arguments += [BUCKET_ID_OPTION, request.bucket_id]
    if request.output_language is not None:
        arguments += [OUTPUT_LANGUAGE_OPTION, request.output_language]
    if request.include_discarded:
        arguments.append(INCLUDE_DISCARDED_FLAG)
    if request.self_test:
        arguments.append(SELF_TEST_FLAG)
    return arguments


def parse_request_arguments(arguments: list[str]) -> FullScreenSessionRequest | None:
    """Read a destination request, or report that none was made.

    ``None`` means the arguments carry no destination at all, which is the
    root session's own invocation shape and not an error. Anything else is
    validated strictly and refused when incomplete: a child that guessed a
    subject would render a surface nobody asked for.
    """
    if DESTINATION_OPTION not in arguments:
        return None
    values: dict[str, str] = {}
    include_discarded = False
    self_test = False
    valued_options = frozenset(
        {
            DESTINATION_OPTION,
            OUTCOME_FILE_OPTION,
            WORK_UNIT_ID_OPTION,
            BUCKET_ID_OPTION,
            OUTPUT_LANGUAGE_OPTION,
        }
    )
    index = 0
    while index < len(arguments):
        token = arguments[index]
        if token == INCLUDE_DISCARDED_FLAG:
            include_discarded = True
            index += 1
        elif token == SELF_TEST_FLAG:
            self_test = True
            index += 1
        elif token in valued_options:
            if index + 1 >= len(arguments):
                raise FullScreenSessionProtocolError(f"{token} was given without a value")
            if token in values:
                raise FullScreenSessionProtocolError(f"{token} was given more than once")
            values[token] = arguments[index + 1]
            index += 2
        else:
            raise FullScreenSessionProtocolError(f"unrecognised session argument {token!r}")
    destination_token = values[DESTINATION_OPTION]
    try:
        destination = FullScreenDestination(destination_token)
    except ValueError as exc:
        raise FullScreenSessionProtocolError(f"unknown session destination {destination_token!r}") from exc
    outcome_file = values.get(OUTCOME_FILE_OPTION)
    if outcome_file is None:
        raise FullScreenSessionProtocolError(
            f"a session destination must name its outcome record with {OUTCOME_FILE_OPTION}"
        )
    return FullScreenSessionRequest(
        destination=destination,
        outcome_file=Path(outcome_file),
        work_unit_id=values.get(WORK_UNIT_ID_OPTION),
        bucket_id=values.get(BUCKET_ID_OPTION),
        include_discarded=include_discarded,
        output_language=values.get(OUTPUT_LANGUAGE_OPTION),
        self_test=self_test,
    )


def render_outcome(outcome: FullScreenSessionOutcome) -> str:
    """Serialise one outcome record for the parent to read.

    JSON rather than the product's tab-separated line grammar, because
    ``detail`` carries localized prose whose own tabs and newlines would
    otherwise be indistinguishable from record structure.
    """
    return json.dumps(
        {
            OUTCOME_KIND_FIELD: outcome.kind.value,
            OUTCOME_WORK_UNIT_ID_FIELD: outcome.work_unit_id,
            OUTCOME_DETAIL_FIELD: outcome.detail,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def parse_outcome(record: str) -> FullScreenSessionOutcome:
    """Read one outcome record, refusing anything this protocol does not define."""
    try:
        payload = json.loads(record)
    except json.JSONDecodeError as exc:
        raise FullScreenSessionProtocolError("the session outcome record is not readable") from exc
    if not isinstance(payload, dict):
        raise FullScreenSessionProtocolError("the session outcome record is not a single record")
    unknown = sorted(
        set(payload) - {OUTCOME_KIND_FIELD, OUTCOME_WORK_UNIT_ID_FIELD, OUTCOME_DETAIL_FIELD},
    )
    if unknown:
        raise FullScreenSessionProtocolError(f"the session outcome record carries unknown fields: {unknown}")
    kind_token = payload.get(OUTCOME_KIND_FIELD)
    if not isinstance(kind_token, str):
        raise FullScreenSessionProtocolError("the session outcome record declares no outcome token")
    try:
        kind = FullScreenOutcomeKind(kind_token)
    except ValueError as exc:
        raise FullScreenSessionProtocolError(f"unknown session outcome {kind_token!r}") from exc
    return FullScreenSessionOutcome(
        kind=kind,
        work_unit_id=_optional_text(payload.get(OUTCOME_WORK_UNIT_ID_FIELD), OUTCOME_WORK_UNIT_ID_FIELD),
        detail=_optional_text(payload.get(OUTCOME_DETAIL_FIELD), OUTCOME_DETAIL_FIELD),
    )


def _optional_text(value: object, field: str) -> str | None:
    """Narrow an absent-or-text outcome field without coercing a foreign type."""
    if value is None or isinstance(value, str):
        return value
    raise FullScreenSessionProtocolError(f"the session outcome field {field!r} is not text")


__all__ = [
    "BUCKET_ID_OPTION",
    "DESTINATION_OPTION",
    "INCLUDE_DISCARDED_FLAG",
    "OUTCOME_DETAIL_FIELD",
    "OUTCOME_FILE_OPTION",
    "OUTCOME_KIND_FIELD",
    "OUTCOME_WORK_UNIT_ID_FIELD",
    "OUTPUT_LANGUAGE_OPTION",
    "SELF_TEST_FLAG",
    "WORK_UNIT_ID_OPTION",
    "FullScreenDestination",
    "FullScreenOutcomeKind",
    "FullScreenSessionOutcome",
    "FullScreenSessionProtocolError",
    "FullScreenSessionRequest",
    "parse_outcome",
    "parse_request_arguments",
    "render_outcome",
    "render_request_arguments",
]
