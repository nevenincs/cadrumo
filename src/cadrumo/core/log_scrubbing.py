"""Redaction of logging records and their bounded values."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Iterator, Mapping
from contextvars import ContextVar
from pathlib import Path
from typing import Any, overload, override

from .diagnostic_log import stamp_diagnostic_scalar_fields
from .redaction.rules import (
    ALWAYS_REDACT_KEY_TERMS,
    is_sensitive_redaction_key,
    normalise_redaction_key,
    redact_for_log,
)
from .type_guards import is_object_list, is_object_list_or_tuple, is_object_mapping, is_object_set, is_object_tuple

SCRUBBED_RECORD: ContextVar[logging.LogRecord | None] = ContextVar("diagnostic_scrubbed_record", default=None)

# Built directly rather than through ``logging.makeLogRecord``, which dispatches
# via the process-global record factory. This set is the redaction filter's
# exemption list, so any field an installed factory adds would enrol itself as
# "standard" and escape scrubbing. Calling the factory here also re-enters this
# module through the observability layer while it is still initialising.
STANDARD_LOG_RECORD_FIELDS = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__)
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
FORMAT_SIZE_RE = re.compile(
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


def scrub_text(value: str, *, key: str | None = None) -> str:
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
def scrub_value(value: str, *, key: str | None = ...) -> str: ...


@overload
def scrub_value(value: Mapping[str, object], *, key: str | None = ...) -> dict[str, object]: ...


@overload
def scrub_value(value: tuple[object, ...], *, key: str | None = ...) -> tuple[object, ...]: ...


@overload
def scrub_value(value: list[object], *, key: str | None = ...) -> list[object]: ...


@overload
def scrub_value(value: set[object], *, key: str | None = ...) -> set[object]: ...


@overload
def scrub_value(value: object, *, key: str | None = ...) -> object: ...


def _scrub_items(values: Iterable[object], key: str | None) -> Iterator[object]:
    """Yield every element of a logging container, each recursively scrubbed.

    The element walk is shared by the tuple, list and set arms of
    :func:`scrub_value`; each arm rebuilds its own concrete container from
    this stream so a subclass never dictates the reconstructed type.
    """
    return (scrub_value(item, key=key) for item in values)


def _scrub_binary_value(value: bytes | bytearray) -> bytes | bytearray | str:
    """Keep short diagnostic bytes and replace larger document payloads."""
    return _PAYLOAD_REDACTION_MARKER if len(value) > _MAX_LOGGED_BYTES else value


def _scrub_mapping_value(value: Mapping[object, object]) -> dict[object, object]:
    """Rebuild a mapping while scrubbing each value with its key hint."""
    return {item_key: scrub_value(item_value, key=str(item_key)) for item_key, item_value in value.items()}


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
def scrub_value(value: object, *, key: str | None = None) -> Any:  # ANY-RETURN-RATIONALE-SCRUB-OVERLOAD-IMPL
    """Recursively scrub sensitive values in common logging payload shapes."""
    if isinstance(value, str):
        return scrub_text(value, key=key)
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
    :func:`scrub_text` alone would leave ``target=%s`` carrying the operator's
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
    scrubbed = scrub_value(value, key=key)
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
    scrubbed_args.extend(scrub_value(value) for value in args[index:])
    return "".join(pieces), tuple(scrubbed_args)


def _scrub_mapping_format(message: str, args: Mapping[str, object]) -> tuple[str, dict[str, object]]:
    """Scrub mapping operands, preserving each use's conversion independently."""
    scrubbed_args = {str(key): scrub_value(value, key=str(key)) for key, value in args.items()}
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
    scrubbed_msg = scrub_text(raw_msg) if isinstance(raw_msg, str) else scrub_value(raw_msg)
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
            record.args = {str(k): scrub_value(v, key=str(k)) for k, v in record.args.items()}
        return
    if isinstance(record.args, tuple | list):
        # Residual tuple/list args reach only when ``record.msg`` is not a
        # str (the positional branch above requires a str format). Preserve
        # the original ``scrub_value`` element-wise scrubbing so no args
        # path skips redaction.
        record.args = tuple(scrub_value(item) for item in record.args)


def _scrub_record_exception(record: logging.LogRecord) -> None:
    """Scrub formatted exception text while retaining the exception tuple."""
    # ``exc_info=False`` reaches the record unchanged; only an exception tuple names one to format.
    if isinstance(record.exc_info, tuple):
        record.exc_text = scrub_text(_EXCEPTION_FORMATTER.formatException(record.exc_info))
    elif record.exc_text is not None and record.exc_text:
        record.exc_text = scrub_text(record.exc_text)


def _scrub_record_extras(record: logging.LogRecord) -> None:
    """Scrub non-standard record attributes in place."""
    for key, value in tuple(record.__dict__.items()):
        if key in STANDARD_LOG_RECORD_FIELDS or key in {"msg", "args", "exc_info", "exc_text"}:
            continue
        record.__dict__[key] = scrub_value(value, key=key)


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
        if SCRUBBED_RECORD.get() is record:
            return True
        stamp_diagnostic_scalar_fields(record)
        _scrub_record_message_and_args(record)
        _scrub_record_exception(record)
        _scrub_record_extras(record)
        return True
