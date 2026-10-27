"""Logging configuration entry point.

Provides :func:`get_logger` as the consistent logger factory to avoid scattered
bare logging instances, with :func:`configure_logging` installing the project
defaults. The installed log-record factory reads the active correlation
contextvars, so every record automatically picks up the active ``run_id`` /
``step_id`` while a run context is bound.

This module attaches the log-record secret scrubber. Every handler
attached through :func:`configure_logging` receives a
:class:`SecretScrubbingFilter` so sensitive fields are redacted before
formatting. Shape-based NIF, URL, and bearer-token matching is delegated
to :func:`~cadrumo.core.redaction.rules.redact_for_log`; this module keeps only
logging-specific key-paired placeholders such as cookies, passphrases, and
certificate serial suffixes.
Callers must omit private values before logging: the scrubber cannot infer
that an ordinary decimal or validation input is taxpayer data.

Encoded document payloads are contained at two seams, because the diagnostic
log is plaintext on disk and a scanned invoice that reaches it has left secure
storage. ``_ThirdPartyDebugFilter`` holds non-Cadrumo loggers below DEBUG
at every sink, so a model or HTTP client never gets to dump a request body
carrying an image; :class:`SecretScrubbingFilter` then redacts base64 payloads
out of the records that remain, including a payload reachable only by rendering
an opaque ``%s`` argument. The first seam needs no knowledge of the payload's
shape, and the second covers first-party records the first seam admits.

Logging is a diagnostic channel, not the CLI result contract. Operator-facing
success payloads and typed :class:`~cadrumo.core.json_contract.Notice` values are
rendered through the JSON/text output stack; this module only prepares redacted
log records and plaintext diagnostic log files rooted by settings.

Producers hand off bounded builtin snapshots before redaction or output. Opaque
arguments are omitted without invoking application rendering hooks. Independent
background sinks expose delivery counters and finite flush/shutdown attempts;
overload rejects diagnostic work rather than blocking application progress.
Queued redaction uses conservative lexical identity matching without borrowing
application registry locks; identity-shaped technical references may be hashed.
"""

from __future__ import annotations

import atexit
import logging
import math
import os
import re
import sys
import time
from codecs import getincrementalencoder
from collections import deque
from collections.abc import Callable, Generator, Iterable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import Context, ContextVar, copy_context
from enum import Enum
from io import BufferedRandom, BufferedWriter, RawIOBase, TextIOWrapper
from itertools import islice
from pathlib import Path
from threading import Event, Lock, Thread
from typing import TYPE_CHECKING, Any, TextIO, cast, overload, override

if TYPE_CHECKING:
    from .observability.context import RunContextInfo
from .cli_metadata import is_metadata_invocation
from .diagnostic_dispatch import DiagnosticDispatch, DispatchStatus
from .diagnostic_log import DiagnosticFormatter, stamp_diagnostic_record, stamp_diagnostic_scalar_fields
from .redaction.rules import (
    ALWAYS_REDACT_KEY_TERMS,
    is_sensitive_redaction_key,
    normalise_redaction_key,
    redact_for_log,
)
from .redaction.tax_identity_admission import lexical_tax_identity_redaction
from .type_guards import (
    is_object_list,
    is_object_list_or_tuple,
    is_object_mapping,
    is_object_set,
    is_object_tuple,
)

_configured = False
_factory_installed = False
# Built directly rather than through ``logging.makeLogRecord``, which dispatches
# via the process-global record factory. This set is the redaction filter's
# exemption list, so any field an installed factory adds would enrol itself as
# "standard" and escape scrubbing. Calling the factory here also re-enters this
# module through the observability layer while it is still initialising.
_STANDARD_LOG_RECORD_FIELDS = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__)
_EXCEPTION_FORMATTER = logging.Formatter()

SCRUB_FIELD_PATTERNS: tuple[str, ...] = (
    *sorted(ALWAYS_REDACT_KEY_TERMS),
    "access_token",
    "api_key",
    "bearer_header",
    "cert_password",
    "certificate_password",
    "certificate_serial",
    "cif",
    "llm_api_key",
    "oauth_access_token",
    "oauth_refresh_token",
    "profile_tax_id",
    "refresh_token",
    "session_cookie",
)
"""Log-message KEY-NAME redaction vocabulary: :data:`ALWAYS_REDACT_KEY_TERMS`
(the tree-wide shared base) plus this module's own generic logging-domain
additions. See :data:`cadrumo.core.redaction.rules.ALWAYS_REDACT_KEY_TERMS` for why
the base is never redeclared independently."""


def _is_cli_metadata_invocation() -> bool:
    """Return whether the current ``aeat`` CLI process renders metadata only.

    Help and version rendering must not initialise settings-derived diagnostic
    logging: an operator may need those state-free surfaces precisely because
    Cadrumo has refused a former product-state directory. Normal commands keep
    the existing logging configuration path.
    """
    program = Path(sys.argv[0])
    executable_names = {program.name.lower(), program.parent.name.lower()}
    if not executable_names.intersection({"aeat", "aeat.exe"}):
        return False
    return is_metadata_invocation(sys.argv[1:])


_SENSITIVE_KEY_SET = frozenset(normalise_redaction_key(pattern) for pattern in SCRUB_FIELD_PATTERNS)
_SENSITIVE_ASSIGNMENT_KEYS: tuple[str, ...] = (*sorted(SCRUB_FIELD_PATTERNS, key=lambda p: len(p), reverse=True),)

_SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?<![A-Za-z0-9])(?P<key>"
    + "|".join(re.escape(pattern) for pattern in _SENSITIVE_ASSIGNMENT_KEYS)
    + r")(?![A-Za-z0-9])(?P<separator>\s*[:=]\s*)"
    + r"(?P<value>\"[^\"]*\"|'[^']*'|[^,;\r\n]+?)"
    + r"(?=$|[,;\r\n]|\s+[A-Za-z0-9_.-]+\s*[:=])",
    flags=re.IGNORECASE,
)
_BEARER_TOKEN_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+\b")
_LLM_KEY_RE = re.compile(r"\b(?:sk-ant-|sk-proj-|sk-live-|sk-test-|sk-)[A-Za-z0-9_-]+\b")
_PLACEHOLDER_PATTERN = r"%(?:\([^)]+\))?[-#+ 0-9]*(?:\*|\d+)?(?:\.(?:\*|\d*))?[hlL]?[diouxXeEfFgGcrsa]"
_PERCENT_PLACEHOLDER_ONLY_RE = re.compile(rf"%%|{_PLACEHOLDER_PATTERN}")
_PERCENT_PLACEHOLDER_VALUE_RE = re.compile(rf"^{_PLACEHOLDER_PATTERN}$")
_PERCENT_PLACEHOLDER_RE = re.compile(
    rf"%%|(?:(?P<key>[A-Za-z0-9_.-]+)\s*[:=]\s*)?(?P<placeholder>{_PLACEHOLDER_PATTERN})"
)
_FORMAT_OPERAND_RE = re.compile(
    r"%(?:\((?P<mapping>[^)]+)\))?[-#+ 0-9]*(?P<width>\*)?"
    r"(?:\.(?P<precision>\*|\d*))?[hlL]?(?P<conversion>[diouxXeEfFgGcrsa])"
)
_FORMAT_SIZE_RE = re.compile(
    r"%(?:\([^)]+\))?[-#+ ]*(?P<width>\d+|\*)?(?:\.(?P<precision>\d+|\*))?[hlL]?[diouxXeEfFgGcrsa]"
)

#: Base64 payload embedded in a ``data:`` URI, the shape a vision request uses
#: when the image travels inline rather than as a bare field.
_DATA_URI_PAYLOAD_RE = re.compile(r"data:[A-Za-z0-9.+-]+/[A-Za-z0-9.+-]+;base64,[A-Za-z0-9+/=]+")

#: Base64 renderings of the file magics a scanned or photographed document
#: arrives as. Matched without a word boundary because several magics begin
#: with ``/``, which is not a word character.
_BINARY_MAGIC_PAYLOAD_RE = re.compile(
    r"(?:iVBORw0KGg|/9j/4AAQ|R0lGODdh|R0lGODlh|UklGR|JVBERi0|SUkqA|TU0AK)[A-Za-z0-9+/]{16,}={0,2}",
)

#: Any sufficiently long unbroken base64 run, whatever produced it. Diagnostic
#: prose never contains one; an encoded document always does. This is the rule
#: that does not need to recognise the payload's shape, so a format the magic
#: alternation above has never heard of is still contained.
_OPAQUE_PAYLOAD_RE = re.compile(r"[A-Za-z0-9+/]{256,}={0,2}")

#: Ceiling on a ``bytes`` log argument before it is treated as a payload rather
#: than a diagnostic value. Decrypted document bytes must never be formatted
#: into a log line, and a %s-rendered ``bytes`` object writes them verbatim.
_MAX_LOGGED_BYTES = 256

_PAYLOAD_REDACTION_MARKER = "<redacted:payload>"

#: Stand-in for the operator's home directory in a logged path.
_HOME_DIRECTORY_MARKER = "~"


def _home_directory_prefixes() -> tuple[str, ...]:
    """Return the spellings of this machine's home directory, longest first.

    Both separators are produced because a path reaches a log line as whatever
    spelling its producer built -- ``Path`` renders native separators, while a
    URI, a config value, or a string-joined path can carry the other one on the
    same machine. Longest first so the drive-qualified form is replaced before
    a prefix of it.
    """
    home = Path.home()
    spellings = {str(home), str(home).replace("\\", "/"), home.as_posix()}
    return tuple(sorted((spelling for spelling in spellings if spelling), key=len, reverse=True))


def _mask_home_directory(value: str) -> str:
    """Replace this machine's home directory with ``~`` wherever it appears.

    A diagnostic path is worth keeping -- it is the only identity a failed
    write, fsync, or lock acquisition has -- but its leading segments are the
    operator's account name and local layout, which the diagnostic never needed.
    Masking the prefix keeps the part that answers "which file" and drops the
    part that answers "whose machine", so a log file attached to a bug report
    does not carry an identity with it.
    """
    for prefix in _HOME_DIRECTORY_PREFIXES:
        value = value.replace(prefix, _HOME_DIRECTORY_MARKER)
    return value


_HOME_DIRECTORY_PREFIXES: tuple[str, ...] = _home_directory_prefixes()


def _redact_payloads(value: str) -> str:
    """Redact encoded document payloads from ``value``.

    Sensitive financial documents may exist only transiently in process
    memory; a diagnostic log file is an on-disk plaintext store, so an image
    or PDF that reaches a log record has left its only sanctioned home. The
    three patterns run widest-last: a ``data:`` URI and a recognised file
    magic name the payload precisely, and the length rule then catches
    whatever neither recognised.
    """
    redacted = _DATA_URI_PAYLOAD_RE.sub(_PAYLOAD_REDACTION_MARKER, value)
    redacted = _BINARY_MAGIC_PAYLOAD_RE.sub(_PAYLOAD_REDACTION_MARKER, redacted)
    return _OPAQUE_PAYLOAD_RE.sub(_PAYLOAD_REDACTION_MARKER, redacted)


def _looks_sensitive_key(key: str | None) -> bool:
    """Return whether ``key`` should have its value redacted."""
    return is_sensitive_redaction_key(key, additional_exact_terms=_SENSITIVE_KEY_SET)


def _redacted_value(key: str | None, value: str) -> str:
    """Return the stable redaction marker for a sensitive value."""
    if key is not None and "serial" in key.lower():
        suffix = value[-4:] if len(value) >= 4 else "????"
        return f"<cert:....{suffix}>"
    return "<redacted>"


def _redact_around_placeholders(key: str | None, value: str) -> str:
    """Redact a sensitive assignment's value, preserving its %-format placeholders.

    A record's ``msg`` is scrubbed before ``%``-formatting runs, so a
    placeholder dropped here would leave the record with more args than slots
    and the whole line would be lost to a formatting error. Placeholders are
    therefore kept verbatim and only the literal runs around them are redacted
    -- which is exactly where an inline secret sits when a message mixes a
    real value with a placeholder, as in ``token=abc123 %s``.

    A value that is nothing but a placeholder carries no secret and is
    returned untouched, which is the ``credential=%s`` format-string shape the
    paired :func:`_scrub_positional_format` pass redacts at the argument instead.
    """
    if _PERCENT_PLACEHOLDER_VALUE_RE.fullmatch(value.strip()):
        return value
    marker = _redacted_value(key, value)
    pieces: list[str] = []
    cursor = 0
    for placeholder in _PERCENT_PLACEHOLDER_ONLY_RE.finditer(value):
        if placeholder.group(0) == "%%":
            continue  # An escaped percent is literal secret text, not an operand.
        if value[cursor : placeholder.start()].strip():
            pieces.append(marker)
        pieces.append(placeholder.group(0))
        cursor = placeholder.end()
    if value[cursor:].strip():
        pieces.append(marker)
    return "".join(pieces) if pieces else marker


def _scrub_text(value: str, *, key: str | None = None) -> str:
    """Redact sensitive fragments from a free-form string."""
    if not value:
        return value
    if _looks_sensitive_key(key):
        return _redacted_value(key, value)

    scrubbed = _redact_payloads(value)
    scrubbed = redact_for_log(scrubbed)
    scrubbed = _SENSITIVE_ASSIGNMENT_RE.sub(
        lambda match: (
            f"{match.group('key')}{match.group('separator')}"
            f"{_redact_around_placeholders(match.group('key'), match.group('value'))}"
        ),
        scrubbed,
    )
    scrubbed = _BEARER_TOKEN_RE.sub("Bearer <redacted>", scrubbed)
    scrubbed = _LLM_KEY_RE.sub("<redacted>", scrubbed)
    return _mask_home_directory(scrubbed)


@overload
def _scrub_value(value: str, *, key: str | None = ...) -> str: ...


@overload
def _scrub_value(value: Mapping[str, object], *, key: str | None = ...) -> dict[str, object]: ...


@overload
def _scrub_value(value: tuple[object, ...], *, key: str | None = ...) -> tuple[object, ...]: ...


@overload
def _scrub_value(value: list[object], *, key: str | None = ...) -> list[object]: ...


@overload
def _scrub_value(value: set[object], *, key: str | None = ...) -> set[object]: ...


@overload
def _scrub_value(value: object, *, key: str | None = ...) -> object: ...


def _scrub_items(values: Iterable[object], key: str | None) -> Iterator[object]:
    """Yield every element of a logging container, each recursively scrubbed.

    The element walk is shared by the tuple, list and set arms of
    :func:`_scrub_value`; each arm rebuilds its own concrete container from
    this stream so a subclass never dictates the reconstructed type.
    """
    return (_scrub_value(item, key=key) for item in values)


def _scrub_binary_value(value: bytes | bytearray) -> bytes | bytearray | str:
    """Keep short diagnostic bytes and replace larger document payloads."""
    return _PAYLOAD_REDACTION_MARKER if len(value) > _MAX_LOGGED_BYTES else value


def _scrub_mapping_value(value: Mapping[object, object]) -> dict[object, object]:
    """Rebuild a mapping while scrubbing each value with its key hint."""
    return {item_key: _scrub_value(item_value, key=str(item_key)) for item_key, item_value in value.items()}


def _scrub_tuple_value(value: tuple[object, ...], key: str | None) -> tuple[object, ...]:
    """Rebuild a tuple from recursively scrubbed logging values."""
    return tuple(_scrub_items(value, key))


def _scrub_list_value(value: list[object], key: str | None) -> list[object]:
    """Rebuild a list from recursively scrubbed logging values."""
    return list(_scrub_items(value, key))


def _scrub_set_value(value: set[object], key: str | None) -> set[object]:
    """Rebuild a set from recursively scrubbed logging values."""
    return set(_scrub_items(value, key))


# ANY-RETURN-RATIONALE-SCRUB-OVERLOAD-IMPL:
# The implementation overload returns Any to subsume all concrete overload
# return types per mypy overload rules.
def _scrub_value(value: object, *, key: str | None = None) -> Any:  # ANY-RETURN-RATIONALE-SCRUB-OVERLOAD-IMPL
    """Recursively scrub sensitive values in common logging payload shapes."""
    if isinstance(value, str):
        return _scrub_text(value, key=key)
    if isinstance(value, bytes | bytearray):
        return _scrub_binary_value(value)
    if is_object_mapping(value):
        return _scrub_mapping_value(value)
    if is_object_tuple(value):
        return _scrub_tuple_value(value, key)
    if is_object_list(value):
        return _scrub_list_value(value, key)
    if is_object_set(value):
        return _scrub_set_value(value, key)
    if _looks_sensitive_key(key):
        return _redacted_value(key, str(value))
    return _scrub_opaque_object(value)


# ANY-RETURN-RATIONALE-OPAQUE-LOG-ARGUMENT: the parameter and return mirror an
# arbitrary %-formatting operand, which the stdlib types as ``object``.
def _scrub_opaque_object(value: object) -> Any:  # ANY-RETURN-RATIONALE-OPAQUE-LOG-ARGUMENT
    """Redact a payload carried inside a non-string logging argument.

    Scrubbing the record's structured shapes is not enough on its own: a
    third-party client logs its whole request object with ``%s``, so the
    payload is never a ``str``, a ``Mapping`` or a sequence the recursive
    walk above descends into -- it is a field of an opaque object that only
    becomes text when the handler formats the record, downstream of every
    filter. Rendering the object here is what lets the payload rules see it.

    The same reasoning covers the home directory in a logged path: a
    :class:`~pathlib.Path` argument is not a ``str`` either, so masking it in
    :func:`_scrub_text` alone would leave ``target=%s`` carrying the operator's
    account name into the formatted line.

    The original object is returned untouched when it holds no payload and no
    home prefix, so the formatted record is unchanged for the overwhelming
    majority of arguments; only a rendering that actually matched is
    substituted.
    """
    if value is None or isinstance(value, int | float | complex):
        return value
    rendered = str(value)
    redacted = _mask_home_directory(_redact_payloads(rendered))
    return redacted if redacted != rendered else value


def _scrub_format_operand(
    value: object, key: str | None, placeholder: str, *, redacted: bool = False
) -> tuple[object, str]:
    """Keep the conversion compatible with a redacted operand.

    A numeric credential becomes a string marker. Numeric conversions cannot
    consume it, and string precision must not truncate the marker. Replacing
    that one conversion preserves the other operands' diagnostic formatting.
    """
    scrubbed = _scrub_value(value, key=key)
    operand = _FORMAT_OPERAND_RE.fullmatch(placeholder)
    if operand is not None and (
        redacted
        or _looks_sensitive_key(key)
        or (
            isinstance(scrubbed, str)
            and (not isinstance(value, str) or scrubbed != value)
            and operand.group("conversion") not in "sra"
        )
    ):
        mapping = operand.group("mapping")
        return scrubbed, f"%({mapping})s" if mapping is not None else "%s"
    return scrubbed, placeholder


def _scrub_positional_format(message: str, args: tuple[object, ...]) -> tuple[str, tuple[object, ...]]:
    """Scrub operands and their conversions together, including star widths."""
    pieces: list[str] = []
    scrubbed_args: list[object] = []
    cursor = 0
    index = 0
    for match in _PERCENT_PLACEHOLDER_RE.finditer(message):
        placeholder = match.group("placeholder")
        if placeholder is None:  # %% consumes no argument.
            continue
        operand = _FORMAT_OPERAND_RE.fullmatch(placeholder)
        if operand is None or operand.group("mapping") is not None:
            continue
        stars = int(operand.group("width") == "*") + int(operand.group("precision") == "*")
        if index + stars >= len(args):
            break  # Retain the stdlib's refusal of an invalid format/arity.
        value, conversion = _scrub_format_operand(args[index + stars], match.group("key"), placeholder)
        pieces.append(message[cursor : match.start("placeholder")])
        pieces.append(conversion)
        cursor = match.end("placeholder")
        if conversion == placeholder:
            scrubbed_args.extend(args[index : index + stars])
        scrubbed_args.append(value)
        index += stars + 1
    pieces.append(message[cursor:])
    scrubbed_args.extend(_scrub_value(value) for value in args[index:])
    return "".join(pieces), tuple(scrubbed_args)


def _scrub_mapping_format(message: str, args: Mapping[str, object]) -> tuple[str, dict[str, object]]:
    """Scrub mapping operands, preserving each use's conversion independently."""
    scrubbed_args = {str(key): _scrub_value(value, key=str(key)) for key, value in args.items()}
    redacted_keys: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        placeholder = match.group("placeholder")
        if placeholder is None:
            return match.group(0)
        operand = _FORMAT_OPERAND_RE.fullmatch(placeholder)
        if operand is None:
            return match.group(0)
        mapping_key = operand.group("mapping")
        if mapping_key is None or mapping_key not in args:
            return match.group(0)
        key = match.group("key") if _looks_sensitive_key(match.group("key")) else mapping_key
        value, conversion = _scrub_format_operand(args[mapping_key], key, placeholder)
        # A key used in a sensitive assignment must stay redacted in all uses.
        if _looks_sensitive_key(key):
            scrubbed_args[mapping_key] = value
            redacted_keys.add(mapping_key)
        return match.group(0)[: match.start("placeholder") - match.start()] + conversion

    rewritten = _PERCENT_PLACEHOLDER_RE.sub(replace, message)

    # A later sensitive assignment may redact a key previously used numerically.
    def compatible(match: re.Match[str]) -> str:
        placeholder = match.group("placeholder")
        if placeholder is None:
            return match.group(0)
        operand = _FORMAT_OPERAND_RE.fullmatch(placeholder)
        if operand is None:
            return match.group(0)
        mapping_key = operand.group("mapping")
        if mapping_key is None or mapping_key not in scrubbed_args:
            return match.group(0)
        _, conversion = _scrub_format_operand(
            scrubbed_args[mapping_key], None, placeholder, redacted=mapping_key in redacted_keys
        )
        return match.group(0)[: match.start("placeholder") - match.start()] + conversion

    return _PERCENT_PLACEHOLDER_RE.sub(compatible, rewritten), scrubbed_args


def _scrub_record_message_and_args(record: logging.LogRecord) -> None:
    """Scrub a record's message and all supported argument shapes."""
    raw_msg: object = record.msg
    scrubbed_msg = _scrub_text(raw_msg) if isinstance(raw_msg, str) else _scrub_value(raw_msg)
    record.msg = scrubbed_msg
    _scrub_record_args(record, scrubbed_msg)


def _scrub_record_args(record: logging.LogRecord, message: object) -> None:
    """Scrub record arguments, retaining placeholder-aware positional arity."""
    if is_object_list_or_tuple(record.args) and isinstance(message, str):
        record.msg, scrubbed_args = _scrub_positional_format(message, tuple(record.args))
        # ``logging.LogRecord.args`` is annotated ``tuple[object, ...]
        # | Mapping[str, object] | None``; ``list`` is not in the
        # union even though logging accepts it at runtime.
        # Normalising to a tuple sidesteps the union mismatch
        # without changing the runtime contract.
        record.args = tuple(scrubbed_args)
        return
    if isinstance(record.args, Mapping):
        if isinstance(message, str):
            record.msg, record.args = _scrub_mapping_format(message, record.args)
        else:
            record.args = {str(k): _scrub_value(v, key=str(k)) for k, v in record.args.items()}
        return
    if isinstance(record.args, tuple | list):
        # Residual tuple/list args reach only when ``record.msg`` is not a
        # str (the positional branch above requires a str format). Preserve
        # the original ``_scrub_value`` element-wise scrubbing so no args
        # path skips redaction.
        record.args = tuple(_scrub_value(item) for item in record.args)


def _scrub_record_exception(record: logging.LogRecord) -> None:
    """Scrub formatted exception text while retaining the exception tuple."""
    # ``exc_info=False`` reaches the record unchanged; only an exception tuple names one to format.
    if isinstance(record.exc_info, tuple):
        record.exc_text = _scrub_text(_EXCEPTION_FORMATTER.formatException(record.exc_info))
    elif record.exc_text is not None and record.exc_text:
        record.exc_text = _scrub_text(record.exc_text)


def _scrub_record_extras(record: logging.LogRecord) -> None:
    """Scrub non-standard record attributes in place."""
    for key, value in tuple(record.__dict__.items()):
        if key in _STANDARD_LOG_RECORD_FIELDS or key in {"msg", "args", "exc_info", "exc_text"}:
            continue
        record.__dict__[key] = _scrub_value(value, key=key)


class SecretScrubbingFilter(logging.Filter):
    """Redact sensitive fields from log records before formatting.

    The filter mutates each :class:`logging.LogRecord` in place so handlers,
    stderr diagnostics, and JSONL run sinks see the same scrubbed record. It is
    deliberately narrower than CLI output redaction: structured command results
    still route through :mod:`cadrumo.core.output_rendering` or
    :mod:`cadrumo.core.json_contract`, while this filter protects logging-only
    message text, %-format args, exception text, and ``extra`` fields.
    """

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        """Scrub sensitive values from ``record`` in-place and return ``True`` to allow it.

        Args:
            record: The log record whose ``msg``, ``args``, ``exc_info``,
                ``exc_text``, and extra fields are scrubbed before formatting.

        Returns:
            Always ``True`` — every record is allowed through after scrubbing.
        """
        if _scrubbed_record.get() is record:
            return True
        stamp_diagnostic_scalar_fields(record)
        _scrub_record_message_and_args(record)
        _scrub_record_exception(record)
        _scrub_record_extras(record)
        return True


def _install_run_context_record_factory() -> None:
    """Install a :class:`logging.LogRecord` factory that stamps ``run_id`` / ``step_id``.

    The contextvars live in :mod:`cadrumo.core.observability.context`. They are
    imported lazily inside the closure so this function never triggers
    a partial import of :mod:`cadrumo.core.observability` (which would create a
    cycle through :mod:`cadrumo.core.config` → :mod:`cadrumo.adapters.outbound.aeat.auth` → this module).

    Both fields are EXPECTED to be empty strings on every record a normal CLI
    invocation emits, and that is the accepted design rather than a gap. Wrapping
    commands in run-trace context was deliberately retired from the CLI: material
    state-transition audit is owned by bucket event history and evidence replay by
    the evidence bundle, so a generic command-wrapper trace would be a parallel
    audit vocabulary over the same events. Nothing in a production path enters a
    run context, so nothing populates these.

    They are populated for the surfaces that do enter one — replay and
    golden-output capture, where the run-trace subsystem is the record/replay
    foundation. This note exists because an always-empty ``run_id`` on every log
    line reads as unwired plumbing, and has twice been reported as one.
    """
    global _factory_installed
    if _factory_installed:
        return
    previous_factory = logging.getLogRecordFactory()
    # Cache the contextvars across record creations. The `import` statement
    # is cheap after the first call (``sys.modules`` lookup), but hoisting
    # it into the closure eliminates the repeated try/except on every
    # single log record — the factory runs in the hottest path of the
    # logging subsystem.
    cached_vars: tuple[ContextVar[RunContextInfo | None], ContextVar[str | None]] | None = None

    # KWARGS-ANY-RATIONALE-LOG-RECORD-FACTORY: signature mirrors the stdlib
    # logging.setLogRecordFactory contract whose *args/**kwargs are the raw
    # LogRecord constructor arguments.
    def _factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        nonlocal cached_vars
        # The stdlib probes a lone operand as a Mapping before logger filters.
        # An opaque object's class/metaclass hooks must not run in that probe.
        if len(args) > 5 and type(args[5]) is tuple:
            arguments = cast(tuple[object, ...], args[5])
            if len(arguments) == 1:
                candidate = arguments[0]
                kind = type(candidate)
                if not (
                    kind is str
                    or kind is int
                    or kind is float
                    or kind is bool
                    or kind is bytes
                    or kind is bytearray
                    or kind is tuple
                    or kind is list
                    or kind is dict
                    or candidate is None
                ):
                    args = (*args[:5], (_snapshot_value(candidate),), *args[6:])
        record = previous_factory(*args, **kwargs)
        if cached_vars is None:
            from .observability.context import RUN_CONTEXT_VAR, STEP_CONTEXT_VAR

            cached_vars = (RUN_CONTEXT_VAR, STEP_CONTEXT_VAR)
        run_var, step_var = cached_vars
        ctx = run_var.get(None)
        record.run_id = ctx.run_id if ctx is not None else ""
        record.step_id = step_var.get(None) or ""
        if _OPERATOR_DOCUMENT_OUTPUT.get():
            record.__dict__["_cadrumo_operator_document_output"] = True
        stamp_diagnostic_record(record)
        return record

    logging.setLogRecordFactory(_factory)
    _factory_installed = True


class DropRunEventFilter(logging.Filter):
    """Suppress observability ``run_event`` records on the stderr handler.

    Records carrying a ``run_event`` extra are the per-run JSONL sink's
    diet — they are already delivered to the attached structured sink. Echoing them
    on stderr as well would spam the console with one
    ``run.event NAVIGATION`` line per step; suppressing them here
    removes the noise while leaving the record intact for any other
    handler (including the JSONL sink).
    """

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        return getattr(record, "run_event", None) is None


#: First-party namespaces for Cadrumo and its hosted automation diagnostics. SDK
#: request-body DEBUG remains excluded even when it originates inside the automation.
_FIRST_PARTY_LOGGER_ROOTS = {"cadrumo"}


def register_first_party_logger(namespace: str) -> None:
    """Enroll this process's owning application namespace for scrubbed diagnostics."""
    if not namespace.isidentifier():
        raise ValueError("a logger namespace must be one application identifier")
    _FIRST_PARTY_LOGGER_ROOTS.add(namespace)


class _ThirdPartyDebugFilter(logging.Filter):
    """Hold third-party loggers below DEBUG at every sink that writes to disk.

    The root logger runs at DEBUG so Cadrumo's own diagnostics are complete,
    and that level is inherited by every third-party library in the process.
    An HTTP or model client at DEBUG dumps its full request object, and for a
    vision request that object carries the document itself -- so the record is
    written to the plaintext diagnostic log before any payload rule has to be
    right about its shape.

    Dropping the record at the handler is the categorical half of the defence:
    the record is never formatted, so nothing depends on recognising what the
    library chose to log, and the log stops accruing request-body volume it
    was never meant to hold. :class:`SecretScrubbingFilter` remains the other
    half, covering first-party records this filter deliberately lets through.

    Named libraries are not enumerated. A list would have to be extended for
    every dependency added later, and the one that leaks is the one nobody
    remembered to add.
    """

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        """Return whether ``record`` may reach the handler.

        Args:
            record: The candidate log record.

        Returns:
            ``True`` for any record at INFO or above, and for DEBUG records
            emitted by a first-party registered application logger.
        """
        if record.levelno >= logging.INFO:
            return True
        return any(record.name == root or record.name.startswith(f"{root}.") for root in _FIRST_PARTY_LOGGER_ROOTS)


#: Extra key marking a record whose content the emitter has ALREADY written to
#: the operator's stream as a structured document. Pass it through ``extra`` on
#: any log call that accompanies such a write.
OPERATOR_DOCUMENT_LOG_EXTRA = "operator_document"
_OPERATOR_DOCUMENT_OUTPUT: ContextVar[bool] = ContextVar("cadrumo_operator_document_output", default=False)


@contextmanager
def operator_document_output() -> Generator[None]:
    """Keep invocation diagnostics in their file while stderr carries a JSON document.

    Records capture the scope when created, so deferred delivery and copied
    async/thread contexts keep the same routing. Other invocations and text
    output retain their stderr diagnostics; no process or handler level changes.
    """
    _install_run_context_record_factory()
    token = _OPERATOR_DOCUMENT_OUTPUT.set(True)
    try:
        yield
    finally:
        _OPERATOR_DOCUMENT_OUTPUT.reset(token)


def _operator_document_record(record: logging.LogRecord) -> bool:
    """Recognize document routing captured at emission, even after its scope ends."""
    return (
        getattr(record, OPERATOR_DOCUMENT_LOG_EXTRA, None) is not None
        or getattr(record, "_cadrumo_operator_document_output", False) is True
    )


#: Line format of every ``cadrumo.log`` record. Readers that parse the file,
#: such as the desktop log view, receive this value rather than a copy.
LOG_FILE_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s | %(diagnostic_context)s"


class DropOperatorDocumentEchoFilter(logging.Filter):
    """Keep document-scoped diagnostics and rendered failures off stderr only.

    stderr is the machine-readable error channel: the CLI's terminal boundary
    writes the JSON error document there, and an automation or script parses that
    stream. A diagnostic log record about the same failure is therefore a
    *duplicate* on stderr, and a harmful one — the record carries the raw
    exception and its traceback, so echoing it prepends internal frames and the
    unredacted exception text to a document whose whole purpose is to present a
    translated, redacted message instead.

    Suppressing the echo here keeps the record intact for every other handler,
    so the rotating file sink still receives the full traceback. That matters:
    the INTERNAL document tells the operator to consult the diagnostic logs, so
    the traceback has to actually be in them.
    """

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        return not _operator_document_record(record)


def default_log_file_path() -> Path:
    """Return the file path for non-interactive project logs.

    Resolved through the taxonomy accessor rather than by reading
    ``cadrumo_log_dir`` here. Both answer the same today, because the settings
    field is what the accessor consults first -- but only one of them stays
    correct if the member's resolution ever gains a case. A call site that
    reads the field directly has quietly opted out of whatever the accessor
    decides, and it does so invisibly, by continuing to work.

    An explicit ``CADRUMO_LOG_DIR`` override still wins, and still keeps the
    log isolated per workspace rather than mixing every session's records into
    one system-wide file.

    The filename itself is read off the taxonomy's ``LOG_FILE`` member rather
    than declared as an untethered string literal here.
    """
    from .storage_taxonomy import StorageCategory
    from .storage_taxonomy_locations import storage_location, storage_path

    filename = Path(storage_location(StorageCategory.LOG_FILE).subpath).name
    return storage_path(StorageCategory.LOGS).expanduser() / filename


def _prepare_log_directory(log_file: Path) -> str | None:
    """Best-effort create the diagnostic log directory.

    Returns ``None`` when the directory already exists or was created, and a
    short ``"<ErrorType>: <detail>"`` reason string when creation failed with
    an :exc:`OSError`.

    File logging is a best-effort diagnostic channel, not the operator result
    contract. An ``CADRUMO_LOCAL_STORAGE_ROOT`` / ``CADRUMO_LOG_DIR`` that the
    process cannot create — an inaccessible Windows path the operator's
    account may not write, a path routed under a non-directory, a
    ``PermissionError`` — MUST degrade to stderr-only logging rather than
    crash CLI startup. Because configuration can run on the first log record,
    before any CLI error boundary exists, an unguarded ``mkdir`` here escapes
    as a raw Python traceback. Swallowing the
    :exc:`OSError` into a reason string keeps startup alive; the caller
    surfaces the reason as an instructive, redacted diagnostic.
    """
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return f"{type(exc).__name__}: {exc}"
    return None


def _install_secret_scrubbing_filters() -> None:
    """Attach one :class:`SecretScrubbingFilter` to the root logger and each handler."""
    root_logger = logging.getLogger()
    if not any(isinstance(active_filter, _DispatchFilter) for active_filter in root_logger.filters):
        root_logger.filters.insert(0, _DispatchFilter())
    if not any(isinstance(active_filter, SecretScrubbingFilter) for active_filter in root_logger.filters):
        root_logger.addFilter(SecretScrubbingFilter())
    for handler in root_logger.handlers:
        if not any(isinstance(active_filter, SecretScrubbingFilter) for active_filter in handler.filters):
            handler.addFilter(SecretScrubbingFilter())


def configure_logging() -> None:
    """Schedule idempotent diagnostic configuration without entering its I/O."""
    _submit_work(_configure_logging)


def _configure_logging() -> None:
    """Configure the project-wide diagnostic logging defaults.

    Installs settings-derived stderr/file handlers, the run-context record
    factory, and :class:`SecretScrubbingFilter` on the root logger plus every
    configured handler. The file handler writes redacted diagnostic plaintext
    under :func:`default_log_file_path`; this module does not encrypt logs or
    persist them through secure-object repositories.

    When the diagnostic log directory cannot be created (an inaccessible
    ``CADRUMO_LOCAL_STORAGE_ROOT`` / ``CADRUMO_LOG_DIR``), logging degrades to
    stderr-only and records an instructive diagnostic naming the likely
    remedy — it never crashes CLI startup with a raw traceback.

    The function is idempotent, so hosts and the first-record placeholder can
    both reach it without duplicating handlers.
    """
    global _configured
    if _configured or _is_cli_metadata_invocation():
        return

    from .config import load_settings
    from .config_state_root import FormerProductStateError

    try:
        log_file = default_log_file_path()
        settings = load_settings()
    except FormerProductStateError:
        # A normal command must reach the typed CLI refusal boundary instead
        # of crashing while its import-time logger tries to open former state.
        # Do not configure a file handler or inspect the rejected root.
        _configured = True
        _retire_first_record_configuration()
        return
    log_directory_failure = _prepare_log_directory(log_file)
    file_logging_enabled = log_directory_failure is None

    from .log_file_handler import AnnouncingRotatingFileHandler

    stderr = _DiagnosticStreamHandler(sys.stderr)
    stderr.setLevel(settings.cadrumo_log_stderr_level)
    stderr.addFilter(DropOperatorDocumentEchoFilter())
    sinks: list[logging.Handler] = [stderr]
    if file_logging_enabled:
        file = AnnouncingRotatingFileHandler(
            str(log_file),
            maxBytes=settings.cadrumo_log_file_max_bytes,
            backupCount=settings.cadrumo_log_file_backup_count,
            encoding="utf-8",
            delay=True,
        )
        file.setLevel(settings.cadrumo_log_file_level)
        sinks.append(file)
    for sink in sinks:
        sink.setFormatter(DiagnosticFormatter(LOG_FILE_FORMAT))
        sink.addFilter(DropRunEventFilter())
        sink.addFilter(_ThirdPartyDebugFilter())
        sink.addFilter(SecretScrubbingFilter())
    root_logger = logging.getLogger()
    previous = tuple(root_logger.handlers)
    root_logger.handlers = [
        handler
        for handler in previous
        if not isinstance(handler, _AsyncDiagnosticHandler | _ConfigureOnFirstRecordHandler)
    ]
    root_logger.handlers.extend(_AsyncDiagnosticHandler(sink) for sink in sinks)
    root_logger.setLevel(settings.cadrumo_log_root_level)
    for handler in previous:
        if isinstance(handler, _AsyncDiagnosticHandler):
            handler.close()
    for name in ("alembic.runtime.plugins", "pdfminer", "pikepdf._core"):
        logging.getLogger(name).setLevel(logging.WARNING)

    # Local import: the observability layer imports ``cadrumo.core.logging`` for
    # its own get_logger() seed, so attaching the filter at module
    # import time would create a circular import. Inside this function
    # the import is safe because configure_logging() runs after both
    # modules finish loading.
    _install_run_context_record_factory()
    _install_secret_scrubbing_filters()

    _configured = True
    _flush_pending_records()

    if not file_logging_enabled:
        # Surface the degrade at ERROR so it clears the default ERROR-gated
        # stderr handler (a WARNING would be swallowed) and flows through the
        # secret-scrubbing filter installed above. Never silent: the operator
        # is told what failed and the concrete remedy, in place of the raw
        # import-time traceback this degrade replaces.
        logging.getLogger(__name__).error(
            "Diagnostic file logging disabled: cannot create the log directory %s (%s). "
            "Continuing with stderr-only logging. Ensure CADRUMO_LOCAL_STORAGE_ROOT / CADRUMO_LOG_DIR "
            "points at a path your account can write; on Windows check the folder's permissions, "
            "run from a directory you own, or set CADRUMO_LOCAL_STORAGE_ROOT to a writable location.",
            log_file.parent,
            log_directory_failure,
        )


def set_log_level(level: int, *, file_level: int = logging.DEBUG) -> None:
    """Apply ``level`` to the root logger and every attached handler.

    The root logger itself is always set to ``logging.DEBUG`` so no
    record is discarded before reaching a handler; each handler then
    applies its own level gate.  ``FileHandler`` instances receive
    ``file_level`` (default ``DEBUG``) to keep the diagnostic log
    comprehensive.  All other handlers (typically the stderr stream
    handler) receive ``level``.

    Configuration and sink-level changes are queued before subsequent records.

    Args:
        level: The effective level for non-file handlers (e.g.
            ``logging.INFO`` for verbose mode).
        file_level: The level applied to :class:`logging.FileHandler`
            instances (default ``logging.DEBUG``).
    """
    # Admit records immediately; the queued command precedes their sink-level checks.
    logging.getLogger().setLevel(logging.DEBUG)

    def apply() -> None:
        _configure_logging()
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        for handler in root_logger.handlers:
            target = handler.sink if isinstance(handler, _AsyncDiagnosticHandler) else handler
            target.setLevel(file_level if isinstance(target, logging.FileHandler) else level)
            handler.setLevel(logging.NOTSET if isinstance(handler, _AsyncDiagnosticHandler) else target.level)

    _submit_work(apply)


_configuration_deferred = False


def defer_logging_configuration() -> None:
    """Keep CLI parse/preflight state-free until dispatch is authorized."""
    global _configuration_deferred
    _configuration_deferred = True


def resume_logging_configuration() -> None:
    """Release a prior startup deferral without configuring by itself."""
    global _configuration_deferred
    _configuration_deferred = False


def logging_configuration_deferred() -> bool:
    """Return whether a host is still keeping this process's logging state-free."""
    return _configuration_deferred


_PENDING_RECORD_LIMIT = 200
_pending_records: deque[logging.LogRecord] = deque(maxlen=_PENDING_RECORD_LIMIT)
_root_level_before_buffering: int | None = None


class _ConfigureOnFirstRecordHandler(logging.Handler):
    """Root placeholder that installs the project configuration on first use.

    Obtaining a logger must not load settings or open the diagnostic log file:
    most production modules do so at import. Hosts configure explicitly at
    their process boundary; this placeholder covers the time before any host
    did. A warning or worse configures logging on the spot. Quieter records
    are held, newest :data:`_PENDING_RECORD_LIMIT` only, and replayed through
    the real handlers once configuration runs, so a host that configures late
    still keeps its early diagnostics. While configuration is deferred or
    suppressed, a warning goes to :data:`logging.lastResort`, which a root
    with any handler no longer reaches.
    """

    configuring = False

    @override
    def handle(self, record: logging.LogRecord) -> bool:
        if _active_record.get() is not record:
            _enqueue_record(record)
            return True
        return bool(super().handle(record))

    @override
    def emit(self, record: logging.LogRecord) -> None:
        if _active_record.get() is not record:
            _enqueue_record(record)
            return
        root_logger = logging.getLogger()
        walked = root_logger.handlers
        position = walked.index(self) if self in walked else 0
        _configure_for_first_record(self, record)
        if _defer_record_if_placeholder(self, root_logger, record):
            return
        _forward_first_record(self, root_logger, walked, position, record)


def _configure_for_first_record(handler: _ConfigureOnFirstRecordHandler, record: logging.LogRecord) -> None:
    if (
        record.levelno < logging.WARNING
        or _configured
        or _configuration_deferred
        or record.__dict__.get("_cadrumo_configuration_deferred") is True
        or type(handler).configuring
    ):
        return
    type(handler).configuring = True
    try:
        _configure_logging()
    finally:
        type(handler).configuring = False


def _defer_record_if_placeholder(
    handler: _ConfigureOnFirstRecordHandler,
    root_logger: logging.Logger,
    record: logging.LogRecord,
) -> bool:
    if handler not in root_logger.handlers:
        return False
    if record.levelno >= logging.WARNING:
        _handle_as_last_resort(record)
    else:
        _hold_pending_record(record)
    return True


def _forward_first_record(
    handler: _ConfigureOnFirstRecordHandler,
    root_logger: logging.Logger,
    walked: list[logging.Handler],
    position: int,
    record: logging.LogRecord,
) -> None:
    # ``Logger.callHandlers`` is still walking the handler list it read before
    # configuration ran. If removal mutated that list in place, only the
    # configured handlers before this placeholder are ours. If removal replaced
    # it (CPython 3.13.15 and 3.14.7 onward, gh-79366), all configured handlers
    # are ours and the triggering record must be forwarded to each one.
    configured = root_logger.handlers
    ours = configured if configured is not walked else configured[: position + 1]
    for active_handler in ours:
        if record.levelno >= active_handler.level:
            active_handler.handle(record)


def _handle_as_last_resort(record: logging.LogRecord) -> None:
    if _operator_document_record(record):
        _hold_pending_record(record)
        return
    last_resort = logging.lastResort
    if last_resort is not None and record.levelno >= last_resort.level:
        last_resort.handle(record)


def _hold_pending_record(record: logging.LogRecord) -> None:
    if len(_pending_records) == _PENDING_RECORD_LIMIT:
        _dispatch.discard()
    _pending_records.append(record)


def _flush_pending_records() -> None:
    """Replay held records through the handlers configuration installed."""
    global _root_level_before_buffering
    _root_level_before_buffering = None
    while _pending_records:
        record = _pending_records.popleft()
        _deliver_work(record)


def _retire_first_record_configuration() -> None:
    """Drop the placeholder and its held records when configuration is refused."""
    global _root_level_before_buffering
    root_logger = logging.getLogger()
    for handler in [handler for handler in root_logger.handlers if isinstance(handler, _ConfigureOnFirstRecordHandler)]:
        root_logger.removeHandler(handler)
    _pending_records.clear()
    if _root_level_before_buffering is not None:
        root_logger.setLevel(_root_level_before_buffering)
        _root_level_before_buffering = None


def _install_first_record_configuration() -> None:
    global _root_level_before_buffering
    root_logger = logging.getLogger()
    if _configured or any(isinstance(handler, _ConfigureOnFirstRecordHandler) for handler in root_logger.handlers):
        return
    root_logger.addHandler(_ConfigureOnFirstRecordHandler())
    if root_logger.level == logging.WARNING:
        # The stdlib default would discard quieter records before the
        # placeholder could hold them; configuration sets the real level.
        _root_level_before_buffering = root_logger.level
        root_logger.setLevel(logging.DEBUG)


_install_first_record_configuration()


def get_logger(name: str) -> logging.Logger:
    """Return the project logger for the given module name.

    Preferred over direct :func:`logging.getLogger` in production modules
    because it attaches :class:`SecretScrubbingFilter` directly to the
    returned logger. It never configures logging: hosts call
    :func:`configure_logging` at their process boundary, and a record that
    reaches the root first installs the configuration itself.

    Args:
        name: The name of the module, typically __name__.

    Returns:
        The named logging.Logger instance.
    """
    # Stamping run context onto records loads no settings and opens nothing, so
    # it is installed here rather than waiting for a host to configure logging;
    # otherwise records made before configuration carry no ``run_id`` at all.
    _install_run_context_record_factory()
    logger = logging.getLogger(name)
    if not any(isinstance(active_filter, _DispatchFilter) for active_filter in logger.filters):
        logger.filters.insert(0, _DispatchFilter())
    if not any(isinstance(active_filter, SecretScrubbingFilter) for active_filter in logger.filters):
        logger.addFilter(SecretScrubbingFilter())
    return logger


_active_record: ContextVar[logging.LogRecord | None] = ContextVar("diagnostic_delivery_record", default=None)
_scrubbed_record: ContextVar[logging.LogRecord | None] = ContextVar("diagnostic_scrubbed_record", default=None)
_sink_workers: list[DiagnosticDispatch[logging.LogRecord]] = []
_stdlib_shutdown = logging.shutdown


def _snapshot_value(value: object, *, depth: int = 0, budget: list[int] | None = None) -> object:
    """Copy bounded builtin shapes without invoking application rendering hooks."""
    if budget is None:
        budget = [256, 65536]
    budget[0] -= 1
    if depth >= 6 or budget[0] < 0:
        return "<omitted:nesting>"
    if type(value) is str:
        if len(value) > 16384 or len(value) * 4 > budget[1]:
            return "<omitted:oversized-text>"
        budget[1] -= len(value) * 4
        return value
    if type(value) is int:
        integer = value
        return integer if integer.bit_length() <= 4096 else "<omitted:oversized-number>"
    if type(value) is float or type(value) is bool or value is None:
        return value
    if type(value) is bytes or type(value) is bytearray:
        binary = value
        return bytes(binary) if len(binary) <= 256 else "<redacted:payload>"
    if type(value) is dict:
        mapping = cast(dict[object, object], value)
        return {
            cast(str, _snapshot_value(key, depth=depth + 1, budget=budget)): _snapshot_value(
                item, depth=depth + 1, budget=budget
            )
            for key, item in islice(mapping.items(), 64)
            if type(key) is str and len(key) <= 256
        }
    if type(value) is tuple or type(value) is list:
        sequence = cast(tuple[object, ...] | list[object], value)
        return tuple(_snapshot_value(item, depth=depth + 1, budget=budget) for item in sequence[:64])
    if issubclass(type(value), Enum):
        members = cast(dict[object, object], Enum.__dict__["__dict__"].__get__(value))
        return _snapshot_value(dict[object, object].get(members, "_value_"), depth=depth + 1, budget=budget)
    # Opaque arguments may hide documents or execute arbitrary __str__/__repr__.
    return "<omitted:opaque-value>"


def _snapshot_record(record: logging.LogRecord) -> logging.LogRecord:
    snapshot = logging.LogRecord.__new__(logging.LogRecord)
    budget = [256, 65536]
    snapshot.__dict__ = {
        key: None if key == "exc_info" else _snapshot_value(value, budget=budget)
        for key, value in islice(record.__dict__.items(), 128)
        if type(key) is str and len(key) <= 256
    }
    if isinstance(record.exc_info, tuple) and isinstance(record.exc_info[1], BaseException):
        snapshot.__dict__["_cadrumo_exception_snapshot"] = _snapshot_exception(record.exc_info[1], budget)
    snapshot.__dict__["_cadrumo_snapshot_weight"] = 1024 + 65536 - budget[1] + (256 - budget[0]) * 32
    return snapshot


def _snapshot_exception(error: BaseException, budget: list[int]) -> tuple[object, ...]:
    """Keep bounded causal frames and builtin arguments without retaining live frames."""
    chain: list[object] = []
    seen: set[int] = set()
    while id(error) not in seen and len(chain) < 8:
        seen.add(id(error))
        name = _snapshot_value(type.__dict__["__name__"].__get__(type(error)), budget=budget)
        arguments = _snapshot_value(BaseException.__dict__["args"].__get__(error), budget=budget)
        frames: list[tuple[str, int, str]] = []
        traceback = BaseException.__dict__["__traceback__"].__get__(error)
        while traceback is not None and len(frames) < 32:
            code = traceback.tb_frame.f_code
            frames.append(
                (
                    str(_snapshot_value(code.co_filename, budget=budget)),
                    traceback.tb_lineno,
                    str(_snapshot_value(code.co_name, budget=budget)),
                )
            )
            traceback = traceback.tb_next
        cause = BaseException.__dict__["__cause__"].__get__(error)
        context = BaseException.__dict__["__context__"].__get__(error)
        suppressed = BaseException.__dict__["__suppress_context__"].__get__(error)
        following = cause if cause is not None else None if suppressed else context
        chain.append((name, arguments, tuple(frames), "cause" if cause is not None else "context"))
        if not isinstance(following, BaseException):
            break
        error = following
    return tuple(chain)


def _bound_format(record: logging.LogRecord) -> None:
    """Reject allocation-sized printf requests before any formatter evaluates them."""
    if not bool(record.args) or not isinstance(record.msg, str):
        return
    for index, match in enumerate(_FORMAT_SIZE_RE.finditer(record.msg)):
        sizes = (match.group("width"), match.group("precision"))
        oversized = any(size and size != "*" and (len(size) > 5 or int(size) > 16384) for size in sizes)
        if "*" in sizes and isinstance(record.args, tuple):
            oversized |= any(type(arg) is int and abs(arg) > 16384 for arg in record.args)
        if index >= 64 or oversized:
            record.msg, record.args = "<omitted:oversized-format>", None
            return


def _enqueue_record(record: logging.LogRecord) -> None:
    if _active_record.get() is not None:
        _dispatch.discard()
        return
    # Several root handlers can see one third-party record. Admit it once.
    if record.__dict__.get("_cadrumo_queued_pid") == os.getpid():
        return
    record.__dict__["_cadrumo_queued_pid"] = os.getpid()
    record.__dict__["_cadrumo_configuration_deferred"] = _configuration_deferred
    try:
        _submit_work(_snapshot_record(record))
    except Exception:
        # A malformed foreign LogRecord must not change the caller's result.
        _dispatch.discard()
        return


class _DispatchFilter(logging.Filter):
    @override
    def filter(self, record: logging.LogRecord) -> bool:
        if _active_record.get() is record:
            return True
        _enqueue_record(record)
        return False


def _deliver_work(work: logging.LogRecord | Callable[[], None]) -> None:
    if not isinstance(work, logging.LogRecord):
        work()
        return
    token = _active_record.set(work)
    try:
        exception = work.__dict__.pop("_cadrumo_exception_snapshot", None)
        if exception is not None:
            sections: list[str] = []
            for name, arguments, frames, relation in reversed(exception):
                if sections:
                    sections.append(f"\nException {relation}:\n")
                stack = "".join(f'  File "{path}", line {line}, in {function}\n' for path, line, function in frames)
                sections.append(f"Traceback (most recent call last):\n{stack}{name}: {arguments}")
            work.exc_text = "\n".join(sections)
        _bound_format(work)
        with lexical_tax_identity_redaction():
            SecretScrubbingFilter().filter(work)
        scrubbed = _scrubbed_record.set(work)
        try:
            logging.getLogger(work.name).handle(work)
        finally:
            _scrubbed_record.reset(scrubbed)
    finally:
        _active_record.reset(token)


class _AsyncDiagnosticHandler(logging.Handler):
    def __init__(self, sink: logging.Handler) -> None:
        super().__init__(logging.NOTSET)
        self.sink = sink
        self._worker = DiagnosticDispatch(
            self._write,
            name=f"diagnostic-{type(sink).__name__}",
            capacity=8192,
            finish=sink.close,
        )
        _sink_workers.append(self._worker)

    @override
    def handle(self, record: logging.LogRecord) -> bool:
        # Foreign loggers bypass logger-attached filters during propagation.
        # Intercept before handler filters can enter redaction or registry I/O.
        if _active_record.get() is not record:
            _enqueue_record(record)
            return True
        return bool(super().handle(record))

    def _write(self, record: logging.LogRecord) -> None:
        token = _active_record.set(record)
        scrubbed = _scrubbed_record.set(record)
        try:
            self.sink.handle(record)
        finally:
            _scrubbed_record.reset(scrubbed)
            _active_record.reset(token)

    @override
    def emit(self, record: logging.LogRecord) -> None:
        if _active_record.get() is record:
            if record.levelno < self.sink.level:
                return
            snapshot = logging.LogRecord.__new__(logging.LogRecord)
            snapshot.__dict__ = record.__dict__.copy()
            self._worker.submit(snapshot, weight=record.__dict__.get("_cadrumo_snapshot_weight", 1024))
        else:
            _enqueue_record(record)

    @override
    def close(self) -> None:
        self._worker.close(timeout=0)
        super().close()


class _DiagnosticStreamHandler(logging.StreamHandler[TextIO]):
    def __init__(self, stream: TextIO, *, follow_stderr: bool = False) -> None:
        super().__init__(stream)
        self._follow_stderr = follow_stderr
        self._raw: RawIOBase | None = None
        self._encoder = getincrementalencoder("utf-8")("backslashreplace")
        self._prepare_stream()

    def _prepare_stream(self) -> None:
        self._raw = None
        if type(self.stream) is TextIOWrapper:
            buffer = self.stream.buffer
            raw = (
                cast("BufferedWriter[RawIOBase] | BufferedRandom", buffer).raw
                if isinstance(buffer, BufferedWriter | BufferedRandom)
                else buffer
            )
            if isinstance(raw, RawIOBase):
                self._raw = raw
                self._encoder = getincrementalencoder(self.stream.encoding)(self.stream.errors or "backslashreplace")

    @override
    def emit(self, record: logging.LogRecord) -> None:
        if self._follow_stderr and sys.stderr is not self.stream and sys.stderr is not None:
            # setStream flushes the old stream, which can itself be blocked.
            self.stream = sys.stderr
            self._prepare_stream()
        if self._raw is None:
            super().emit(record)
            return
        # A daemon must never hold stderr's BufferedWriter lock: CPython takes
        # that lock again during finalization, beyond our bounded shutdown.
        data = self._encoder.encode((self.format(record) + self.terminator).replace("\n", os.linesep))
        with _stderr_write_guard:
            remaining = memoryview(data)
            while remaining:
                written = self._raw.write(remaining)
                if written is None or written <= 0:
                    raise OSError("diagnostic stream delivery failed")
                remaining = remaining[written:]

    @override
    def handleError(self, record: logging.LogRecord) -> None:
        # The stdlib fallback prints the unsanitized record and arguments.
        raise OSError("diagnostic stream delivery failed") from None


_stderr_write_guard = Lock()


def _reset_stderr_write_guard() -> None:
    global _stderr_write_guard
    _stderr_write_guard = Lock()


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_reset_stderr_write_guard)


_dispatch = DiagnosticDispatch[logging.LogRecord | Callable[[], None]](
    _deliver_work, name="diagnostic-records", capacity=8192
)


def _submit_work(work: logging.LogRecord | Callable[[], None]) -> None:
    """Keep configuration settings without retaining an invocation's authority lease."""
    if _configured:
        weight = work.__dict__.get("_cadrumo_snapshot_weight", 1024) if isinstance(work, logging.LogRecord) else 1024
        _dispatch.submit(work, weight=weight)
        return
    context = Context()
    for variable, value in copy_context().items():
        if variable.name == "settings_override":
            context.run(variable.set, value)
    weight = work.__dict__.get("_cadrumo_snapshot_weight", 1024) if isinstance(work, logging.LogRecord) else 1024
    _dispatch.submit(lambda: context.run(_deliver_work, work), weight=weight)


def flush_logging(*, timeout: float = 2.0) -> bool:
    """Attempt delivery within one bound; ordinary log calls never wait for this."""
    deadline = time.monotonic() + (max(0.0, timeout) if math.isfinite(timeout) else 0.0)
    if not _dispatch.flush(timeout=max(0.0, deadline - time.monotonic())):
        return False
    complete = True
    for worker in tuple(_sink_workers):
        complete = worker.flush(timeout=max(0.0, deadline - time.monotonic())) and complete
    return complete


def diagnostic_delivery_status() -> dict[str, DispatchStatus]:
    """Read delivery health without acquiring any formatter, handler or file lock."""
    return {
        "records": _dispatch.status(),
        **{f"sink_{index}": worker.status() for index, worker in enumerate(tuple(_sink_workers))},
    }


_shutdown_guard = Lock()
_shutdown_finished = Event()
_shutdown_thread: Thread | None = None


def shutdown_logging(*, timeout: float = 2.0) -> None:
    """Also bound stdlib shutdown, whose default waits indefinitely on sink locks."""
    global _shutdown_thread
    deadline = time.monotonic() + (max(0.0, timeout) if math.isfinite(timeout) else 0.0)
    flush_logging(timeout=max(0.0, deadline - time.monotonic()))
    for worker in tuple(_sink_workers):
        worker.close(timeout=max(0.0, deadline - time.monotonic()))

    def finish() -> None:
        try:
            _stdlib_shutdown()
        finally:
            _shutdown_finished.set()

    with _shutdown_guard:
        if _shutdown_thread is None:
            _shutdown_thread = Thread(target=finish, name="diagnostic-shutdown", daemon=True)
            try:
                _shutdown_thread.start()
            except RuntimeError:
                _shutdown_finished.set()
    _shutdown_finished.wait(max(0.0, deadline - time.monotonic()))


atexit.unregister(_stdlib_shutdown)
atexit.register(shutdown_logging)

# Preserve caller-installed fallback handlers. The stdlib default must use the
# same isolated sink as configured diagnostics, including before configuration.
if type(logging.lastResort) is getattr(logging, "_StderrHandler", None):
    _fallback_sink = _DiagnosticStreamHandler(sys.stderr, follow_stderr=True)
    _fallback_sink.addFilter(DropOperatorDocumentEchoFilter())
    _fallback_sink.addFilter(DropRunEventFilter())
    _fallback_sink.addFilter(_ThirdPartyDebugFilter())
    _fallback_handler = _AsyncDiagnosticHandler(_fallback_sink)
    _fallback_handler.setLevel(logging.WARNING)
    logging.lastResort = _fallback_handler
