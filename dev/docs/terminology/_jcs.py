"""Strict ``cadrumo-jcs-utf8-lf-v1`` JSON bytes for the Rung-2 seam.

The Rung-2 matrix is consumed by Python build tooling and by a browser.  The
standard-library JSON encoder is deterministic for some inputs, but its
number spelling and key ordering are not the RFC 8785/ECMAScript contract.
This small, dependency-free encoder therefore owns the complete byte boundary
used by the matrix, manifest, bridge, and bundle hashes.

Only I-JSON values are accepted.  A caller must project domain objects to
plain JSON values before entering this function; no fallback conversion,
normalisation, or compatibility serializer is provided.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import Final

__all__ = ["CANONICAL_JSON_CONTRACT", "CanonicalJsonError", "canonical_json_bytes"]

CANONICAL_JSON_CONTRACT: Final[str] = "cadrumo-jcs-utf8-lf-v1"
_UTF_8: Final[str] = "utf-8"
_UTF_16_BE: Final[str] = "utf-16-be"
_SAFE_INTEGER_MAX: Final[int] = 9_007_199_254_740_991
_EXPONENT_RE = re.compile(r"^(?P<mantissa>-?(?:\d+\.?\d*|\.\d+))(?:[eE](?P<exponent>[+-]?\d+))?$")


class CanonicalJsonError(ValueError):
    """Raised when a value cannot cross the strict canonical JSON boundary."""


def canonical_json_bytes(value: object) -> bytes:
    """Return canonical UTF-8 JSON bytes followed by exactly one LF.

    The number formatting follows the ECMAScript/JCS presentation thresholds
    around ``1e-6`` and ``1e21`` while retaining Python's shortest-round-trip
    binary64 digit selection.  Python and JavaScript both use the same
    shortest-round-trip binary64 rule; only their presentation thresholds
    differ, which :func:`_ecmascript_number` normalises explicitly.
    """

    try:
        text = _serialize(value)
        return (text + "\n").encode(_UTF_8, "strict")
    except (UnicodeEncodeError, UnicodeDecodeError, OverflowError) as exc:
        raise CanonicalJsonError("value cannot be encoded as strict UTF-8 JSON") from exc


def _serialize(value: object) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return _string(value)
    if isinstance(value, int):
        if abs(value) > _SAFE_INTEGER_MAX:
            raise CanonicalJsonError("JSON integers must be in the safe binary64 domain")
        return str(value)
    if isinstance(value, float):
        return _ecmascript_number(value)
    if isinstance(value, Mapping):
        return _object(value)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_serialize(item) for item in value) + "]"
    raise CanonicalJsonError(f"unsupported JSON value type: {type(value).__name__}")


def _string(value: str) -> str:
    value = _normalise_unicode(value)
    escaped: list[str] = ['"']
    for character in value:
        code_point = ord(character)
        if character == '"':
            escaped.append('\\"')
        elif character == "\\":
            escaped.append("\\\\")
        elif code_point == 0x08:
            escaped.append("\\b")
        elif code_point == 0x09:
            escaped.append("\\t")
        elif code_point == 0x0A:
            escaped.append("\\n")
        elif code_point == 0x0C:
            escaped.append("\\f")
        elif code_point == 0x0D:
            escaped.append("\\r")
        elif code_point < 0x20:
            escaped.append(f"\\u{code_point:04x}")
        else:
            escaped.append(character)
    escaped.append('"')
    return "".join(escaped)


def _object(value: Mapping[object, object]) -> str:
    items: list[tuple[str, object]] = []
    seen: set[str] = set()
    for key, item in value.items():
        if not isinstance(key, str):
            raise CanonicalJsonError("JSON object keys must be strings")
        key = _normalise_unicode(key)
        if key in seen:
            raise CanonicalJsonError("JSON object keys must be unique")
        _strict_utf8(key)
        seen.add(key)
        items.append((key, item))

    items.sort(key=lambda pair: pair[0].encode(_UTF_16_BE, "strict"))
    return "{" + ",".join(_string(key) + ":" + _serialize(item) for key, item in items) + "}"


def _strict_utf8(value: str) -> None:
    """Reject lone UTF-16 surrogates rather than allowing replacement bytes."""

    try:
        _normalise_unicode(value).encode(_UTF_8, "strict")
    except UnicodeEncodeError as exc:
        raise CanonicalJsonError("JSON strings cannot contain lone surrogates") from exc


def _normalise_unicode(value: str) -> str:
    """Combine valid escaped surrogate pairs and reject lone surrogates."""

    characters: list[str] = []
    index = 0
    while index < len(value):
        code_point = ord(value[index])
        if 0xD800 <= code_point <= 0xDBFF:
            if index + 1 >= len(value):
                raise CanonicalJsonError("JSON strings cannot contain lone surrogates")
            low = ord(value[index + 1])
            if not 0xDC00 <= low <= 0xDFFF:
                raise CanonicalJsonError("JSON strings cannot contain lone surrogates")
            characters.append(chr(0x10000 + ((code_point - 0xD800) << 10) + (low - 0xDC00)))
            index += 2
            continue
        if 0xDC00 <= code_point <= 0xDFFF:
            raise CanonicalJsonError("JSON strings cannot contain lone surrogates")
        characters.append(value[index])
        index += 1
    return "".join(characters)


def _ecmascript_number(value: float) -> str:
    if not math.isfinite(value):
        raise CanonicalJsonError("JSON numbers must be finite")
    if value == 0.0:
        if math.copysign(1.0, value) < 0.0:
            raise CanonicalJsonError("negative zero is not admissible JSON")
        return "0"
    if value.is_integer() and abs(value) > _SAFE_INTEGER_MAX:
        raise CanonicalJsonError("integer-valued JSON numbers must be safely representable")

    match = _EXPONENT_RE.fullmatch(repr(value))
    if match is None:
        raise CanonicalJsonError("Python produced an unsupported binary64 representation")
    mantissa = match.group("mantissa")
    exponent = int(match.group("exponent") or "0")
    sign = ""
    if mantissa.startswith("-"):
        sign = "-"
        mantissa = mantissa[1:]

    integer_part, dot, fractional_part = mantissa.partition(".")
    digits = integer_part + fractional_part
    decimal_position = len(integer_part) + exponent

    leading_zeroes = len(digits) - len(digits.lstrip("0"))
    if leading_zeroes == len(digits):
        raise CanonicalJsonError("zero must be represented as the positive JSON zero")
    if leading_zeroes:
        digits = digits[leading_zeroes:]
        decimal_position -= leading_zeroes
    digits = digits.rstrip("0")

    magnitude = abs(value)
    if 1e-6 <= magnitude < 1e21:
        if decimal_position <= 0:
            return sign + "0." + ("0" * -decimal_position) + digits
        if decimal_position >= len(digits):
            return sign + digits + ("0" * (decimal_position - len(digits)))
        return sign + digits[:decimal_position] + "." + digits[decimal_position:]

    scientific_exponent = decimal_position - 1
    mantissa_text = digits[0]
    if len(digits) > 1:
        mantissa_text += "." + digits[1:]
    exponent_text = str(scientific_exponent)
    if scientific_exponent >= 0:
        exponent_text = "+" + exponent_text
    return sign + mantissa_text + "e" + exponent_text
