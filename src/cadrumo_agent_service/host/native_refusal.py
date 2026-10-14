"""The native interpreter host's launch-profile refusal, read from the last line it wrote to standard error.

An image's launch profile is applied by the native host before Python starts.
A launch that breaks it ends with one machine-readable standard-error line,
``{"native_refusal": "<code>", "subject": "<name>"}``, and exit status 125. The
code is closed. The subject names the variable or invocation concerned and never
carries the offending value. Nothing else the agent writes to standard error is
read.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, ValidationError

STANDARD_ERROR_TAIL_BYTES: Final = 4 * 1024
"""How much of the end of its standard error the host keeps; the refusal line is the last line in it."""

_SUBJECT_MAX_CHARACTERS: Final = 128
# A name, a module or an option: never a path, a quoted value or any other free text.
_SUBJECT: Final = re.compile(rf"[A-Za-z0-9_.:+\- ]{{1,{_SUBJECT_MAX_CHARACTERS}}}")


class NativeLaunchRefusalCode(StrEnum):
    """The closed codes of a native launch-profile refusal."""

    LAUNCH_VALUE_MISSING = "launch_value_missing"
    LAUNCH_VALUE_MALFORMED = "launch_value_malformed"
    INVOCATION_UNDECLARED = "invocation_undeclared"


@dataclass(frozen=True, slots=True)
class NativeLaunchRefusal:
    """What a refusing native host reported; a field is ``None`` when the host's line did not state it validly."""

    code: NativeLaunchRefusalCode | None
    subject: str | None


class _RefusalLine(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    native_refusal: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    subject: str = Field(max_length=4 * _SUBJECT_MAX_CHARACTERS)


def native_launch_refusal_from(standard_error_tail: bytes) -> NativeLaunchRefusal:
    """Read the host's refusal from the end of an agent's standard error.

    The caller has already seen the host's exit status, which alone says the
    launch profile refused. A last line that is not exactly the host's line, a
    code outside the closed set and a subject that is not a plain name each read
    as absent, so no other output reaches a diagnostic.
    """
    lines = [line.strip() for line in standard_error_tail.splitlines()]
    last = next((line for line in reversed(lines) if line), b"")
    try:
        document = _RefusalLine.model_validate_json(last)
    except ValidationError:
        return NativeLaunchRefusal(code=None, subject=None)
    try:
        code = NativeLaunchRefusalCode(document.native_refusal)
    except ValueError:
        code = None
    subject = document.subject if _SUBJECT.fullmatch(document.subject) else None
    return NativeLaunchRefusal(code=code, subject=subject)
