"""The supervisor line grammar is closed, bounded and strict."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import TypeAdapter

from cadrumo.application.runtime.contracts import RuntimeExitReason

from ..supervised_protocol import (
    MAX_LINE_BYTES,
    RuntimeAnnouncement,
    RuntimeBusy,
    RuntimeHeartbeat,
    RuntimeReady,
    RuntimeRefused,
    RuntimeStopping,
    SupervisorLineError,
    SupervisorLineFraming,
    SupervisorLineRefusal,
    SupervisorPing,
    SupervisorSessionEnd,
    SupervisorStop,
    SupervisorStopIfIdle,
    decode_supervisor_command,
    encode_runtime_announcement,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_LARGEST = 2**53 - 1


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        (b'{"type":"ping","seq":0}', SupervisorPing(seq=0)),
        (b'{"seq":9007199254740991,"type":"ping"}', SupervisorPing(seq=_LARGEST)),
        (b'{"type":"stop"}', SupervisorStop()),
        (b' {"type": "stop-if-idle"}\r', SupervisorStopIfIdle()),
        (b'{"type":"session-end"}', SupervisorSessionEnd()),
    ],
)
def test_each_supervisor_command_decodes_to_its_type(line: bytes, expected: object) -> None:
    assert decode_supervisor_command(line) == expected


@pytest.mark.parametrize(
    "line",
    [
        b"",
        b"null",
        b"[]",
        b'"stop"',
        b"{}",
        b'{"type":"STOP"}',
        b'{"type":"reboot"}',
        b'{"type":"stop","reason":64}',
        b'{"type":"ping"}',
        b'{"type":"ping","seq":-1}',
        b'{"type":"ping","seq":9007199254740992}',
        b'{"type":"ping","seq":1.0}',
        b'{"type":"ping","seq":"1"}',
        b'{"type":"ping","seq":true}',
        b'{"type":"ping","seq":NaN}',
        b'{"type":"ping","seq":1,"seq":1}',
        b'{"type":"stop","note":"\xc3\xa9"}',
        b'{"type":"stop"} {"type":"stop"}',
    ],
)
def test_lines_outside_the_grammar_are_malformed(line: bytes) -> None:
    with pytest.raises(SupervisorLineError) as refused:
        decode_supervisor_command(line)
    assert refused.value.reason is SupervisorLineRefusal.MALFORMED
    # The refusal carries only its bounded code, never the refused line.
    assert str(refused.value) == "malformed"


def test_a_line_at_the_bound_is_oversized_before_parsing() -> None:
    with pytest.raises(SupervisorLineError) as refused:
        decode_supervisor_command(b'{"type":"stop"}' + b" " * MAX_LINE_BYTES)
    assert refused.value.reason is SupervisorLineRefusal.OVERSIZED


def test_framing_joins_split_lines_and_keeps_order() -> None:
    framing = SupervisorLineFraming()
    assert framing.feed(b'{"type":"st') == []
    assert framing.feed(b'op"}\n{"type":"ping","seq":1}\n{"ty') == [b'{"type":"stop"}', b'{"type":"ping","seq":1}']
    assert framing.feed(b'pe":"stop"}\n') == [b'{"type":"stop"}']


def test_framing_accepts_a_line_that_exactly_fills_the_bound() -> None:
    framing = SupervisorLineFraming()
    largest = b"x" * (MAX_LINE_BYTES - 1)
    assert framing.feed(largest[:100]) == []
    assert framing.feed(largest[100:] + b"\n") == [largest]
    assert framing.feed(b"x" * MAX_LINE_BYTES + b"\n") == [SupervisorLineRefusal.OVERSIZED]


def test_framing_discards_an_oversized_line_once_and_resumes() -> None:
    framing = SupervisorLineFraming()
    assert framing.feed(b"y" * (3 * MAX_LINE_BYTES)) == []
    assert framing.feed(b"z" * MAX_LINE_BYTES) == []
    assert framing.feed(b'tail\n{"type":"stop"}\n') == [SupervisorLineRefusal.OVERSIZED, b'{"type":"stop"}']


def _largest_announcements() -> list[RuntimeReady | RuntimeHeartbeat | RuntimeStopping | RuntimeBusy | RuntimeRefused]:
    return [
        RuntimeReady(
            boot_id=uuid4(),
            pid=_LARGEST,
            version="v" * 64,
            storage_identity="f" * 64,
            admission="development",
        ),
        RuntimeHeartbeat(seq=_LARGEST, tick_age_ms=_LARGEST, frontends=_LARGEST, in_flight_operations=_LARGEST),
        RuntimeHeartbeat(seq=0, tick_age_ms=None, frontends=0, in_flight_operations=0),
        RuntimeStopping(reason=RuntimeExitReason.SESSION_END_SETTLE),
        RuntimeBusy(),
        RuntimeRefused(code=SupervisorLineRefusal.OVERSIZED),
    ]


@pytest.mark.parametrize("message", _largest_announcements())
def test_every_announcement_is_one_bounded_line_that_round_trips(
    message: RuntimeReady | RuntimeHeartbeat | RuntimeStopping | RuntimeBusy | RuntimeRefused,
) -> None:
    line = encode_runtime_announcement(message)
    assert line.endswith(b"\n") and line.count(b"\n") == 1 and len(line) <= MAX_LINE_BYTES
    assert line.isascii()
    decoded = TypeAdapter(RuntimeAnnouncement).validate_json(line[:-1], strict=True)
    assert decoded == message


def test_stopping_names_the_numeric_exit_reason() -> None:
    line = encode_runtime_announcement(RuntimeStopping(reason=RuntimeExitReason.SUPERVISOR_STOP))
    assert line == b'{"type":"stopping","reason":64}\n'
