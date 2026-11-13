"""The fixed-clock admission every Python entry repeats: each refusal, and the one admitted shape."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from ...config import override_settings
from ...errors.hierarchy import CoreValidationError
from ...storage_environment import normalize_storage_path
from ..clock import wall_now
from ..fixed_clock import (
    FIXED_CLOCK_INSTANT_VARIABLE,
    FIXED_CLOCK_ROOT_VARIABLE,
    FixedClock,
    FixedClockMarker,
    FixedClockRefusal,
    admit_fixed_clock,
    admit_fixed_clock_from_environment,
    fixed_clock_marker_path,
    fixed_clock_refusal,
    read_fixed_clock_marker,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _past_instant() -> datetime:
    """A whole-second instant well before today, derived from the wall clock rather than named."""
    return (wall_now() - timedelta(days=400)).replace(microsecond=0)


def _admit(
    root: Path,
    *,
    instant_text: str | None,
    root_text: str | None,
    default_root: Path | None = None,
    live_tests_opt_in: bool = False,
    marker: FixedClockMarker | None = None,
) -> FixedClock | None:
    return admit_fixed_clock(
        instant_text=instant_text,
        root_text=root_text,
        pinned_root=root,
        default_root=default_root,
        live_tests_opt_in=live_tests_opt_in,
        marker=marker,
    )


def _refusal_of(error: pytest.ExceptionInfo[CoreValidationError]) -> FixedClockRefusal | None:
    return fixed_clock_refusal(error.value)


def _write_marker(root: Path, document: object) -> None:
    path = fixed_clock_marker_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


def test_no_slots_and_no_marker_admit_nothing(tmp_path: Path) -> None:
    assert _admit(tmp_path, instant_text=None, root_text=None) is None
    assert _admit(tmp_path, instant_text="", root_text="  ") is None


def test_both_slots_bound_to_the_pinned_root_admit_the_instant(tmp_path: Path) -> None:
    instant = _past_instant()

    admitted = _admit(tmp_path, instant_text=instant.isoformat(), root_text=str(tmp_path))

    assert admitted is not None
    assert admitted.instant == instant
    assert admitted.instant.tzinfo is UTC
    assert admitted.root == normalize_storage_path(tmp_path)


def test_a_z_suffixed_instant_is_utc(tmp_path: Path) -> None:
    instant = _past_instant()
    spelled = instant.replace(tzinfo=None).isoformat() + "Z"

    admitted = _admit(tmp_path, instant_text=spelled, root_text=str(tmp_path))

    assert admitted is not None
    assert admitted.instant == instant


@pytest.mark.parametrize("present", ["instant", "root"])
def test_a_lone_slot_is_refused(tmp_path: Path, present: str) -> None:
    instant_text = _past_instant().isoformat() if present == "instant" else None
    root_text = str(tmp_path) if present == "root" else None

    with pytest.raises(CoreValidationError) as error:
        _admit(tmp_path, instant_text=instant_text, root_text=root_text)

    assert _refusal_of(error) is FixedClockRefusal.LONE_VARIABLE


@pytest.mark.parametrize(
    "spelling",
    [
        pytest.param(lambda instant: instant.replace(tzinfo=None).isoformat(), id="naive"),
        pytest.param(lambda instant: instant.astimezone(timezone(timedelta(hours=1))).isoformat(), id="offset"),
        pytest.param(lambda _instant: "not an instant", id="malformed"),
    ],
)
def test_an_instant_that_is_not_utc_is_refused(tmp_path: Path, spelling: Callable[[datetime], str]) -> None:
    with pytest.raises(CoreValidationError) as error:
        _admit(tmp_path, instant_text=spelling(_past_instant()), root_text=str(tmp_path))

    assert _refusal_of(error) is FixedClockRefusal.INSTANT_NOT_UTC


def test_a_root_other_than_the_pinned_root_is_refused(tmp_path: Path) -> None:
    pinned = tmp_path / "pinned"
    other = tmp_path / "other"

    with pytest.raises(CoreValidationError) as error:
        _admit(pinned, instant_text=_past_instant().isoformat(), root_text=str(other))

    assert _refusal_of(error) is FixedClockRefusal.ROOT_MISMATCH


def test_a_relative_root_is_refused(tmp_path: Path) -> None:
    with pytest.raises(CoreValidationError) as error:
        _admit(tmp_path, instant_text=_past_instant().isoformat(), root_text="relative-root")

    assert _refusal_of(error) is FixedClockRefusal.ROOT_MISMATCH


def test_the_channel_default_root_is_refused(tmp_path: Path) -> None:
    with pytest.raises(CoreValidationError) as error:
        _admit(tmp_path, instant_text=_past_instant().isoformat(), root_text=str(tmp_path), default_root=tmp_path)

    assert _refusal_of(error) is FixedClockRefusal.DEFAULT_ROOT


def test_the_live_test_opt_in_is_refused(tmp_path: Path) -> None:
    with pytest.raises(CoreValidationError) as error:
        _admit(tmp_path, instant_text=_past_instant().isoformat(), root_text=str(tmp_path), live_tests_opt_in=True)

    assert _refusal_of(error) is FixedClockRefusal.LIVE_TEST_OPT_IN


def test_a_marked_root_without_a_fixed_clock_is_refused(tmp_path: Path) -> None:
    with pytest.raises(CoreValidationError) as error:
        _admit(tmp_path, instant_text=None, root_text=None, marker=FixedClockMarker(instant=_past_instant()))

    assert _refusal_of(error) is FixedClockRefusal.MARKED_ROOT_WITHOUT_FIXED_CLOCK


def test_a_marked_root_started_with_another_instant_is_refused(tmp_path: Path) -> None:
    recorded = _past_instant()
    marker = FixedClockMarker(instant=recorded)

    with pytest.raises(CoreValidationError) as error:
        _admit(
            tmp_path,
            instant_text=(recorded + timedelta(days=1)).isoformat(),
            root_text=str(tmp_path),
            marker=marker,
        )

    assert _refusal_of(error) is FixedClockRefusal.MARKER_INSTANT_DIFFERS
    admitted = _admit(tmp_path, instant_text=recorded.isoformat(), root_text=str(tmp_path), marker=marker)
    assert admitted is not None
    assert admitted.instant == recorded


def test_an_unreadable_marker_is_refused(tmp_path: Path) -> None:
    with pytest.raises(CoreValidationError) as error:
        _admit(
            tmp_path,
            instant_text=_past_instant().isoformat(),
            root_text=str(tmp_path),
            marker=FixedClockMarker(instant=None),
        )

    assert _refusal_of(error) is FixedClockRefusal.MARKER_UNREADABLE


def test_another_validation_failure_carries_no_fixed_clock_refusal() -> None:
    assert fixed_clock_refusal(CoreValidationError("unrelated")) is None


def test_the_marker_is_read_from_the_runtime_directory(tmp_path: Path) -> None:
    instant = _past_instant()
    assert read_fixed_clock_marker(tmp_path) is None

    _write_marker(tmp_path, {"instant": instant.isoformat()})

    assert fixed_clock_marker_path(tmp_path).parent.name == ".runtime"
    assert read_fixed_clock_marker(tmp_path) == FixedClockMarker(instant=instant)


@pytest.mark.parametrize(
    "document",
    [
        pytest.param(["instant"], id="not-an-object"),
        pytest.param({"instant": "not an instant"}, id="malformed-instant"),
        pytest.param({"instant": 1}, id="not-text"),
        pytest.param({"instant": "x", "root": "y"}, id="extra-member"),
    ],
)
def test_a_malformed_marker_reads_as_unreadable(tmp_path: Path, document: object) -> None:
    _write_marker(tmp_path, document)

    assert read_fixed_clock_marker(tmp_path) == FixedClockMarker(instant=None)


def test_environment_admission_reads_both_slots_and_the_marker(tmp_path: Path) -> None:
    instant = _past_instant()
    environ = {FIXED_CLOCK_INSTANT_VARIABLE: instant.isoformat(), FIXED_CLOCK_ROOT_VARIABLE: str(tmp_path)}

    admitted = admit_fixed_clock_from_environment(environ, pinned_root=tmp_path)

    assert admitted is not None
    assert admitted.instant == instant
    _write_marker(tmp_path, {"instant": instant.isoformat()})
    with pytest.raises(CoreValidationError) as error:
        admit_fixed_clock_from_environment({}, pinned_root=tmp_path)
    assert _refusal_of(error) is FixedClockRefusal.MARKED_ROOT_WITHOUT_FIXED_CLOCK


def test_environment_admission_refuses_under_the_live_test_opt_in(tmp_path: Path) -> None:
    environ = {FIXED_CLOCK_INSTANT_VARIABLE: _past_instant().isoformat(), FIXED_CLOCK_ROOT_VARIABLE: str(tmp_path)}

    with override_settings(cadrumo_live_tests_enabled="1"), pytest.raises(CoreValidationError) as error:
        admit_fixed_clock_from_environment(environ, pinned_root=tmp_path)

    assert _refusal_of(error) is FixedClockRefusal.LIVE_TEST_OPT_IN
