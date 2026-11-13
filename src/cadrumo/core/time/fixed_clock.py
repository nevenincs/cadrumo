"""The test-host fixed clock: admission of one instant for one end-to-end storage root.

A test host compiled for automation may start the runtime with a fixed
instant, so the packaged window can reproduce a persona row the persona table
computes under :func:`~cadrumo.core.time.clock.frozen_clock`. Two launch slots
carry it: the instant, a UTC ISO 8601 value, and the absolute storage root it
is for. They are never settings fields, so no settings path reads them.

The runtime host and each profile worker read the two slots once at process
entry through :func:`admit_fixed_clock_from_environment` and refuse to start on
any unbound value. Admission only names the instant. The runtime host never
enters :func:`~cadrumo.core.time.clock.frozen_clock`; a profile worker enters
it around a registered operation's application work, and nowhere else.

A root once used under a fixed clock carries a marker beneath ``.runtime/``,
written by the native test host at the root's first admission. This module
only reads it: a marked root refuses every start without an admitted fixed
clock, and every start whose instant differs from the one the marker records.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Final, NoReturn

from ..errors.hierarchy import CoreValidationError
from ..storage_environment import host_installed_default_root, normalize_storage_path
from ..storage_taxonomy import StorageCategory
from ..storage_taxonomy_locations import storage_location
from .clock import live_tests_opt_in_active

FIXED_CLOCK_INSTANT_VARIABLE: Final = "CADRUMO_FIXED_CLOCK_INSTANT"
"""The launch slot naming the fixed instant, a UTC ISO 8601 value."""

FIXED_CLOCK_ROOT_VARIABLE: Final = "CADRUMO_FIXED_CLOCK_ROOT"
"""The launch slot naming the absolute storage root the fixed instant is for."""

FIXED_CLOCK_VARIABLES: Final = (FIXED_CLOCK_INSTANT_VARIABLE, FIXED_CLOCK_ROOT_VARIABLE)
"""Both launch slots, in declaration order."""

_MARKER_INSTANT_KEY: Final = "instant"


class FixedClockRefusal(StrEnum):
    """Why a fixed clock, or its absence, refuses a process start."""

    LONE_VARIABLE = "fixed_clock_lone_variable"
    INSTANT_NOT_UTC = "fixed_clock_instant_not_utc"
    ROOT_MISMATCH = "fixed_clock_root_mismatch"
    DEFAULT_ROOT = "fixed_clock_default_root"
    LIVE_TEST_OPT_IN = "fixed_clock_live_test_opt_in"
    MARKED_ROOT_WITHOUT_FIXED_CLOCK = "fixed_clock_marked_root_without_fixed_clock"
    MARKER_INSTANT_DIFFERS = "fixed_clock_marker_instant_differs"
    MARKER_UNREADABLE = "fixed_clock_marker_unreadable"


FIXED_CLOCK_REFUSAL_CONTEXT_KEY: Final = "fixed_clock_refusal"
"""The context key of a :class:`CoreValidationError` that carries a :class:`FixedClockRefusal`."""


def _refuse(refusal: FixedClockRefusal) -> NoReturn:
    raise CoreValidationError(
        "the fixed clock is not admitted for this process",
        context={FIXED_CLOCK_REFUSAL_CONTEXT_KEY: refusal.value},
    )


def fixed_clock_refusal(error: CoreValidationError) -> FixedClockRefusal | None:
    """Return the fixed-clock refusal ``error`` carries, or ``None`` when it is another validation failure."""
    value = (error.context or {}).get(FIXED_CLOCK_REFUSAL_CONTEXT_KEY)
    return FixedClockRefusal(value) if isinstance(value, str) else None


@dataclass(frozen=True, slots=True)
class FixedClock:
    """One admitted fixed instant and the storage root it was admitted for."""

    instant: datetime
    root: Path


@dataclass(frozen=True, slots=True)
class FixedClockMarker:
    """What a root's fixed-clock marker records; ``instant`` is ``None`` when the marker is unreadable."""

    instant: datetime | None


def _utc_instant(text: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(text.strip())
    except ValueError:
        _refuse(FixedClockRefusal.INSTANT_NOT_UTC)
    offset = parsed.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        _refuse(FixedClockRefusal.INSTANT_NOT_UTC)
    return parsed.astimezone(UTC)


def _same_root(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left)) == os.path.normcase(str(right))


def _admitted_root(text: str, pinned_root: Path) -> Path:
    candidate = Path(text.strip())
    if not candidate.is_absolute():
        _refuse(FixedClockRefusal.ROOT_MISMATCH)
    try:
        root = normalize_storage_path(candidate)
    except CoreValidationError:
        _refuse(FixedClockRefusal.ROOT_MISMATCH)
    if not _same_root(root, normalize_storage_path(pinned_root)):
        _refuse(FixedClockRefusal.ROOT_MISMATCH)
    return root


def _present(value: str | None) -> str | None:
    return value if value is not None and value.strip() else None


def admit_fixed_clock(
    *,
    instant_text: str | None,
    root_text: str | None,
    pinned_root: Path,
    default_root: Path | None,
    live_tests_opt_in: bool,
    marker: FixedClockMarker | None,
) -> FixedClock | None:
    """Admit the fixed clock the two launch slots name, or report that none was supplied.

    Args:
        instant_text: The instant slot's value; blank or ``None`` when absent.
        root_text: The root slot's value; blank or ``None`` when absent.
        pinned_root: The absolute storage root this process is pinned to.
        default_root: The channel's per-user default root, or ``None`` when
            this host resolves none.
        live_tests_opt_in: Whether the live-test opt-in is set.
        marker: The root's fixed-clock marker, or ``None`` when it has none.

    Returns:
        The admitted fixed clock, or ``None`` when neither slot is set and the
        root carries no marker.

    Raises:
        CoreValidationError: Carrying a :class:`FixedClockRefusal` under
            :data:`FIXED_CLOCK_REFUSAL_CONTEXT_KEY` when the start must be refused.
    """
    instant_value, root_value = _present(instant_text), _present(root_text)
    if instant_value is None and root_value is None:
        if marker is not None:
            _refuse(FixedClockRefusal.MARKED_ROOT_WITHOUT_FIXED_CLOCK)
        return None
    if instant_value is None or root_value is None:
        _refuse(FixedClockRefusal.LONE_VARIABLE)
    instant = _utc_instant(instant_value)
    root = _admitted_root(root_value, pinned_root)
    if default_root is not None and _same_root(root, normalize_storage_path(default_root)):
        _refuse(FixedClockRefusal.DEFAULT_ROOT)
    if live_tests_opt_in:
        _refuse(FixedClockRefusal.LIVE_TEST_OPT_IN)
    if marker is not None:
        if marker.instant is None:
            _refuse(FixedClockRefusal.MARKER_UNREADABLE)
        if marker.instant != instant:
            _refuse(FixedClockRefusal.MARKER_INSTANT_DIFFERS)
    return FixedClock(instant=instant, root=root)


def fixed_clock_marker_path(root: Path) -> Path:
    """Return where ``root`` keeps its fixed-clock marker."""
    return root / storage_location(StorageCategory.RUNTIME_FIXED_CLOCK_MARKER).relative_path()


def read_fixed_clock_marker(root: Path) -> FixedClockMarker | None:
    """Read ``root``'s fixed-clock marker: ``None`` when absent, an unreadable marker when malformed.

    The marker is a JSON object whose only member, ``instant``, is the admitted
    UTC ISO 8601 instant.
    """
    path = fixed_clock_marker_path(root)
    try:
        payload = path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError:
        return FixedClockMarker(instant=None)
    try:
        document = json.loads(payload)
    except ValueError:
        return FixedClockMarker(instant=None)
    if not isinstance(document, dict) or set(document) != {_MARKER_INSTANT_KEY}:
        return FixedClockMarker(instant=None)
    value = document[_MARKER_INSTANT_KEY]
    if not isinstance(value, str):
        return FixedClockMarker(instant=None)
    try:
        return FixedClockMarker(instant=_utc_instant(value))
    except CoreValidationError:
        return FixedClockMarker(instant=None)


def _channel_default_root(environ: Mapping[str, str]) -> Path | None:
    try:
        return host_installed_default_root(environ)
    except CoreValidationError:
        # A host that resolves no per-user default has no default root to aim at.
        return None


def admit_fixed_clock_from_environment(environ: Mapping[str, str], *, pinned_root: Path) -> FixedClock | None:
    """Read both launch slots from ``environ`` once and admit them for ``pinned_root``.

    Raises:
        CoreValidationError: Carrying a :class:`FixedClockRefusal` when the start must be refused.
    """
    return admit_fixed_clock(
        instant_text=environ.get(FIXED_CLOCK_INSTANT_VARIABLE),
        root_text=environ.get(FIXED_CLOCK_ROOT_VARIABLE),
        pinned_root=pinned_root,
        default_root=_channel_default_root(environ),
        live_tests_opt_in=live_tests_opt_in_active(),
        marker=read_fixed_clock_marker(pinned_root),
    )


__all__ = [
    "FIXED_CLOCK_INSTANT_VARIABLE",
    "FIXED_CLOCK_REFUSAL_CONTEXT_KEY",
    "FIXED_CLOCK_ROOT_VARIABLE",
    "FIXED_CLOCK_VARIABLES",
    "FixedClock",
    "FixedClockMarker",
    "FixedClockRefusal",
    "admit_fixed_clock",
    "admit_fixed_clock_from_environment",
    "fixed_clock_marker_path",
    "fixed_clock_refusal",
    "read_fixed_clock_marker",
]
