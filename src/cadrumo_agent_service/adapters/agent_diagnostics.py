"""Bridge hosted agent diagnostics into the scrubbed application log, never its protocol bytes."""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import math
import re
from collections import OrderedDict
from datetime import datetime
from threading import Lock
from typing import Final

from cadrumo.core.hashing import reject_duplicate_json_members, reject_json_constant

_LINE_BYTES: Final = 64 * 1024
_CLI_DETAIL: Final = re.compile(
    rb"^(?:Traceback |[ \t]+|[\w.]+(?:Error|Exception):|During handling |The above exception).*$"
)
_LEVELS: Final = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}
_CLI_LINE: Final = re.compile(r"^(WARNING|ERROR|CRITICAL) (cadrumo_agent(?:\.[\w.]+)?): (.*)$", re.DOTALL)
# Operational scalars only. Conversation/tool arguments and arbitrary nested
# extras are not diagnostic context and must never enter the plaintext feed.
_FIELDS: Final = frozenset(
    {
        "action",
        "event",
        "service",
        "gateway_port",
        "worker_port",
        "port",
        "duration_ms",
        "elapsed_ms",
        "elapsed_seconds",
        "exit_code",
        "error_type",
        "reason",
        "status",
        "trace_id",
        "span_id",
    }
)


class AgentDiagnosticSink:
    """Preserve producer identity and severity; collapse duplicate stderr/file copies."""

    def __init__(self) -> None:
        """Create a bounded, thread-safe duplicate window for one hosted run."""
        self._seen: OrderedDict[tuple[object, ...], None] = OrderedDict()
        self._lock = Lock()
        self._problems: dict[str, int] = {}

    def line(self, data: bytes, *, pid: int, cli: bool = False) -> None:
        """Accept only the agent diagnostic schema or its CLI logger format."""
        try:
            if len(data) > _LINE_BYTES:
                raise ValueError
            text = data.decode("utf-8")
            if cli and (match := _CLI_LINE.fullmatch(text)):
                level, name, message = match.groups()
                record = logging.makeLogRecord(
                    {
                        "name": name,
                        "levelno": _LEVELS[level],
                        "levelname": level,
                        "msg": message,
                        "args": (),
                        "process": pid,
                        "_cadrumo_process_role": "extension_service",
                    }
                )
            else:
                entry = json.loads(
                    text, object_pairs_hook=reject_duplicate_json_members, parse_constant=reject_json_constant
                )
                if not isinstance(entry, dict):
                    return
                if entry.get("schema") != "cadrumo-agent.log/1":
                    if str(entry.get("schema", "")).startswith("cadrumo-agent.log/"):
                        raise ValueError
                    return
                level = entry["level"]
                name, message = entry["name"], entry["message"]
                producer, sequence = entry["pid"], entry["seq"]
                timestamp = entry["timestamp"]
                if (
                    level not in _LEVELS
                    or not isinstance(name, str)
                    or not name
                    or len(name) > 512
                    or not isinstance(message, str)
                    or type(producer) is not int
                    or producer <= 0
                    or type(sequence) is not int
                    or sequence <= 0
                    or not isinstance(timestamp, str)
                ):
                    raise ValueError
                instant = datetime.fromisoformat(timestamp)
                if instant.tzinfo is None:
                    raise ValueError
                service = entry.get("service")
                role = "extension_service"
                exception = entry.get("exception")
                if isinstance(exception, str) and exception:
                    message += "\n" + exception
                values = {
                    key: value
                    for key, value in entry.items()
                    if key in _FIELDS
                    and (type(value) in (str, int, bool) or (isinstance(value, float) and math.isfinite(value)))
                }
                record = logging.makeLogRecord(
                    {
                        **values,
                        "name": name,
                        "levelno": _LEVELS[level],
                        "levelname": level,
                        "msg": message,
                        "args": (),
                        "created": instant.timestamp(),
                        "process": producer,
                        "_cadrumo_process_role": role,
                        "agent_sequence": sequence,
                    }
                )
                identity = (
                    producer,
                    service,
                    sequence,
                    timestamp,
                    name,
                    hashlib.sha256(entry["message"].encode()).digest(),
                )
                with self._lock:
                    if identity in self._seen:
                        return
                    self._seen[identity] = None
                    if len(self._seen) > 8192:
                        self._seen.popitem(last=False)
            # Logger.handle preserves the child's timestamp/PID and applies the
            # real application handlers, including credential/payload scrubbing.
            with contextlib.suppress(Exception):
                logging.getLogger(record.name).handle(record)
        except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
            self.problem("agent_diagnostic_record_rejected")

    def problem(self, message: str) -> None:
        """Report loss without reproducing untrusted bytes or credential paths."""
        with self._lock:
            count = self._problems.get(message, 0) + 1
            self._problems[message] = count
        # First failure and powers of two keep a bad stream observable without
        # letting it flood the shared log. The count states accumulated loss.
        if count & (count - 1) == 0:
            with contextlib.suppress(Exception):
                logging.getLogger(__name__).warning(message, extra={"diagnostic_rejected_count": count})


class AgentDiagnosticLines:
    """Bounded framing for arbitrary pipe/file chunks, including partial UTF-8 writes."""

    def __init__(self, sink: AgentDiagnosticSink, *, pid: int, cli: bool = False) -> None:
        """Attribute CLI records to the child while trusting schema records' own PID."""
        self._sink, self._pid, self._cli = sink, pid, cli
        self._partial = bytearray()
        self._oversize = False
        self._cli_record = bytearray()

    def _line(self, data: bytes) -> None:
        if self._cli:
            text = data.decode("utf-8", errors="replace")
            if _CLI_LINE.fullmatch(text):
                self._flush_cli()
                self._cli_record.extend(data)
                return
            if self._cli_record and (not data or _CLI_DETAIL.fullmatch(data)):
                if len(self._cli_record) + len(data) + 1 <= _LINE_BYTES:
                    self._cli_record.extend(b"\n" + data)
                else:
                    self._sink.problem("agent_diagnostic_line_too_large")
                return
            self._flush_cli()
        self._sink.line(data, pid=self._pid, cli=self._cli)

    def _flush_cli(self) -> None:
        if self._cli_record:
            self._sink.line(bytes(self._cli_record), pid=self._pid, cli=True)
            self._cli_record.clear()

    def feed(self, chunk: bytes) -> None:
        """Forward completed lines and discard an oversized line through its newline."""
        for index, part in enumerate(chunk.split(b"\n")):
            if index:
                if self._oversize:
                    self._sink.problem("agent_diagnostic_line_too_large")
                elif self._partial:
                    self._line(bytes(self._partial).rstrip(b"\r"))
                self._partial.clear()
                self._oversize = False
            if len(self._partial) + len(part) > _LINE_BYTES:
                self._oversize = True
                self._partial.clear()
            elif not self._oversize:
                self._partial.extend(part)

    def finish(self) -> None:
        """Drain a last unterminated diagnostic after the writer has ended."""
        if self._partial or self._oversize:
            self.feed(b"\n")
        self._flush_cli()
