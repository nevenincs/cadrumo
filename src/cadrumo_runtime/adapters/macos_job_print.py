"""Parse bounded launchd job status and resource coalition facts."""

from __future__ import annotations

from dataclasses import dataclass

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError

_PRINT_LIMIT = 64 * 1024
MAXIMUM_MACOS_PID = 2_147_483_647
_COALITION_FIELDS: frozenset[str] = frozenset(("ID", "type", "state", "active count", "name"))


@dataclass(frozen=True, slots=True)
class MacosJobCoalition:
    """The resource coalition launchd reports for one job."""

    coalition_id: int
    state: str
    active_count: int


@dataclass(frozen=True, slots=True)
class MacosJobPrint:
    """Closed facts from launchd's effective view of one job."""

    state: str
    pid: int | None
    coalition: MacosJobCoalition | None


def _decimal(value: str, *, minimum: int) -> int:
    if not value.isascii() or not value.isdecimal() or len(value) > 20 or int(value) < minimum:
        raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
    return int(value)


def _read_block(lines: list[str], index: int, end: int) -> tuple[tuple[str, ...], int]:
    members: list[str] = []
    while True:
        if index >= end:
            raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
        member = lines[index]
        index += 1
        if member == "\t}":
            break
        if not member.startswith("\t\t"):
            raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
        members.append(member[2:])
    return tuple(members), index


def _field_line(line: str, scalars: dict[str, str], blocks: dict[str, tuple[str, ...]]) -> tuple[str, str]:
    if not line.startswith("\t") or line.startswith("\t\t"):
        raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
    key, separator, value = line[1:].partition(" = ")
    if not separator or not key or key in scalars or key in blocks:
        raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
    return key, value


def _job_fields(lines: list[str]) -> tuple[dict[str, str], dict[str, tuple[str, ...]]]:
    scalars: dict[str, str] = {}
    blocks: dict[str, tuple[str, ...]] = {}
    end = len(lines) - 1
    index = 1
    while index < end:
        line = lines[index]
        index += 1
        if not line:
            continue
        key, value = _field_line(line, scalars, blocks)
        if value != "{":
            scalars[key] = value
            continue
        blocks[key], index = _read_block(lines, index, end)
    return scalars, blocks


def _coalition(coalition_block: tuple[str, ...] | None, label: str) -> MacosJobCoalition | None:
    if coalition_block is None:
        return None
    fields: dict[str, str] = {}
    for member in coalition_block:
        key, separator, value = member.partition(" = ")
        if not separator or key not in _COALITION_FIELDS or key in fields:
            raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
        fields[key] = value
    if frozenset(fields) != _COALITION_FIELDS or fields["type"] != "resource" or fields["name"] != label:
        raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
    if not fields["state"]:
        raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
    coalition = MacosJobCoalition(
        coalition_id=_decimal(fields["ID"], minimum=1),
        state=fields["state"],
        active_count=_decimal(fields["active count"], minimum=0),
    )
    return coalition


def _state_and_pid(scalars: dict[str, str]) -> tuple[str, int | None]:
    state = scalars.get("state")
    if not (state is not None and state):
        raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
    printed_pid = scalars.get("pid")
    pid = None if printed_pid is None else _decimal(printed_pid, minimum=1)
    if pid is not None and pid > MAXIMUM_MACOS_PID:
        raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
    return state, pid


def parse_macos_job_print(text: str, *, target: str, label: str) -> MacosJobPrint:
    """Parse launchd's bounded print view of one job; any unknown shape refuses.

    Blocks other than the resource coalition are kept opaque. The coalition
    block must carry exactly its five known fields and name the job's label.

    Args:
        text: Complete ``launchctl print`` output for the job.
        target: Exact ``gui/<uid>/<label>`` service target that was printed.
        label: Exact job label the coalition must be named after.
    """
    if len(text.encode("utf-8")) > _PRINT_LIMIT or any(ord(char) < 32 and char not in "\n\t" for char in text):
        raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
    lines = text.splitlines()
    if len(lines) < 2 or lines[0] != target + " = {" or lines[-1] != "}":
        raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
    scalars, blocks = _job_fields(lines)
    state, pid = _state_and_pid(scalars)
    coalition = _coalition(blocks.get("resource coalition"), label)
    return MacosJobPrint(state=state, pid=pid, coalition=coalition)
