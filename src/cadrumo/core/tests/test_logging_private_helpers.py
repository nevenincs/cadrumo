"""Private logging-helper contracts owned by the core package."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from ..logging import _prepare_log_directory, _scrub_value

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_prepare_log_directory_returns_none_for_creatable_path(tmp_path: Path) -> None:
    """A writable target yields no failure reason and materialises the directory."""

    log_file = tmp_path / "probe-logs" / "cadrumo.log"

    reason = _prepare_log_directory(log_file)

    assert reason is None
    assert log_file.parent.is_dir()


def test_prepare_log_directory_reports_reason_when_path_uncreatable(tmp_path: Path) -> None:
    """A log directory routed under a real file cannot be created and reports why.

    Reproduces the class of failure the Windows PowerShell testimonial hit: an
    ``CADRUMO_LOCAL_STORAGE_ROOT`` that resolves to an inaccessible / non-directory
    path. The helper must return a diagnostic reason string instead of letting
    the underlying ``OSError`` escape.
    """

    blocker = tmp_path / "not-a-directory"
    blocker.write_text("x", encoding="utf-8")
    log_file = blocker / "probe-logs" / "cadrumo.log"

    reason = _prepare_log_directory(log_file)

    assert reason is not None
    assert not log_file.parent.exists()
    # The reason names the concrete OS error type so triage sees the cause.
    assert "Error" in reason


def test_scrub_value_non_sensitive_overloads_preserve_shape() -> None:
    """Non-sensitive scalar/container inputs preserve their public shape."""

    for value, expected_type, expected in (
        ("hello world", str, "hello world"),
        (("safe-value", "also-safe"), tuple, ("safe-value", "also-safe")),
        (["one", "two"], list, ["one", "two"]),
        ({"alpha", "beta"}, set, {"alpha", "beta"}),
    ):
        result = _scrub_value(value)
        assert isinstance(result, expected_type)
        assert result == expected


def test_scrub_value_mapping_overload_returns_dict() -> None:
    """Mapping input must produce a dict result."""

    result = _scrub_value({"account": "visible", "secret": "hidden"})
    assert isinstance(result, dict)
    assert result["account"] == "visible"
    assert result["secret"] == "<redacted>"


def test_scrub_value_object_overload_passes_through_non_sensitive() -> None:
    """An arbitrary object with a non-sensitive key passes through unchanged."""

    obj = object()
    result = _scrub_value(obj, key="count")
    assert result is obj


def test_scrub_value_sensitive_key_redacts_to_marker() -> None:
    """Any input paired with a sensitive key is redacted to the public marker."""

    for value in ("super-secret", 12345):
        result = _scrub_value(value, key="token")
        assert isinstance(result, str)
        assert result == "<redacted>"


def test_scrub_value_nested_mapping_scrubs_recursively() -> None:
    """Nested dicts must have their sensitive leaves redacted at every depth."""

    payload = {"outer": {"token": "s3cr3t", "count": 3}}
    result = _scrub_value(payload)
    assert isinstance(result, dict)
    outer_raw = result["outer"]
    assert isinstance(outer_raw, dict)
    outer = cast(dict[str, object], outer_raw)
    assert outer["token"] == "<redacted>"
    assert outer["count"] == 3
