"""Project the runtime exit-reason table into the native contract."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from cadrumo.application.runtime.contracts import (
    RESERVED_RUNTIME_EXIT_CODES,
    RuntimeExitReason,
    RuntimeReservedExitCodes,
)

_UNSIGNED_EXIT_CODE_MAX = 0xFFFF_FFFF
_POSIX_EXIT_STATUS_MAX = 0xFF
# Names and owners become Rust string literals and constant suffixes without escaping.
_TOKEN = re.compile(r"[a-z][a-z0-9_]*")


def runtime_exit_section(native_host: Mapping[str, Any]) -> dict[str, Any]:
    """Return the exit reasons and reserved ranges, refusing any reason another owner already holds.

    The native interpreter host's range is a package fact taken from ``native_host``; the
    runtime's own copy of that range is not read here.
    """
    package_range = RuntimeReservedExitCodes(native_host["owner"], native_host["first"], native_host["last"])
    ranges = sorted(
        (*(item for item in RESERVED_RUNTIME_EXIT_CODES if item.owner != package_range.owner), package_range),
        key=lambda item: item.first,
    )
    for reserved in ranges:
        if not _TOKEN.fullmatch(reserved.owner):
            raise ValueError(f"Reserved exit code owner is not a contract token: {reserved.owner!r}")
        if not 0 < reserved.first <= reserved.last <= _UNSIGNED_EXIT_CODE_MAX:
            raise ValueError(f"Reserved exit codes are not an unsigned range: {reserved.owner}")
    for reason in RuntimeExitReason:
        owners = [reserved.owner for reserved in ranges if reason.value in reserved]
        if not _TOKEN.fullmatch(reason.name.lower()):
            raise ValueError(f"Runtime exit reason is not a contract token: {reason.name!r}")
        # POSIX reports only the low byte of an exit status.
        if not 0 < reason.value <= _POSIX_EXIT_STATUS_MAX or owners:
            raise ValueError(f"Runtime exit reason {reason.name} uses a reserved code: {reason.value} {owners}")
    return {
        "reasons": [{"name": reason.name.lower(), "code": reason.value} for reason in RuntimeExitReason],
        "reserved": [{"owner": reserved.owner, "first": reserved.first, "last": reserved.last} for reserved in ranges],
    }


def rust_runtime_exit_reasons(section: dict[str, Any]) -> list[str]:
    """Return Rust declarations for one contract's runtime exit section."""
    lines = [
        "pub struct RuntimeExitReason { pub name: &'static str, pub code: u32 }",
        "pub struct RuntimeReservedExitCodes { pub owner: &'static str, pub first: u32, pub last: u32 }",
    ]
    lines.extend(
        f"pub const RUNTIME_EXIT_{reason['name'].upper()}: u32 = {reason['code']};" for reason in section["reasons"]
    )
    lines.append("pub const RUNTIME_EXIT_REASONS: &[RuntimeExitReason] = &[")
    lines.extend(
        f'    RuntimeExitReason {{ name: "{reason["name"]}", code: {reason["code"]} }},'
        for reason in section["reasons"]
    )
    lines.append("];")
    lines.append("pub const RUNTIME_RESERVED_EXIT_CODES: &[RuntimeReservedExitCodes] = &[")
    lines.extend(
        f'    RuntimeReservedExitCodes {{ owner: "{reserved["owner"]}", first: {reserved["first"]}, '
        f"last: {reserved['last']} }},"
        for reserved in section["reserved"]
    )
    lines.append("];")
    return lines
