"""Behaviour tests for the shared TOML helpers exported by :mod:`aeat.core`."""

from __future__ import annotations

from pathlib import Path

import pytest

from .. import freeze_toml, parse_toml_text, read_toml, to_str_keyed_dict

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class _SampleError(Exception):
    """Stand-in domain error for the error_factory contract."""


def test_to_str_keyed_dict_returns_str_keyed_copy() -> None:
    """A mapping with string keys is returned as a plain str-keyed dict."""
    result = to_str_keyed_dict({"a": 1, "b": [2, 3]}, error_factory=_SampleError)
    assert result == {"a": 1, "b": [2, 3]}


def test_to_str_keyed_dict_rejects_non_string_key_via_error_factory() -> None:
    """A non-string key raises the exception built by ``error_factory``."""
    with pytest.raises(_SampleError, match="TOML table keys must be strings"):
        to_str_keyed_dict({1: "x"}, error_factory=_SampleError)


def test_read_toml_parses_a_valid_committed_file(tmp_path: Path) -> None:
    """A well-formed TOML file round-trips through read_toml."""
    target = tmp_path / "ok.toml"
    target.write_text('name = "value"\n[section]\nflag = true\n', encoding="utf-8")
    parsed = read_toml(target, error_factory=_SampleError)
    assert parsed["name"] == "value"
    assert parsed["section"] == {"flag": True}


def test_read_toml_wraps_decode_failure_via_error_factory(tmp_path: Path) -> None:
    """Invalid TOML raises the caller-supplied error type with a path-tagged message."""
    target = tmp_path / "bad.toml"
    target.write_text("not = valid = toml", encoding="utf-8")
    with pytest.raises(_SampleError) as exc_info:
        read_toml(target, error_factory=_SampleError)
    assert str(target) in str(exc_info.value)
    assert "invalid TOML" in str(exc_info.value)


def test_read_toml_wraps_filesystem_error_via_error_factory(tmp_path: Path) -> None:
    """A missing file raises the caller-supplied error type, not a bare OSError."""
    missing = tmp_path / "missing.toml"
    with pytest.raises(_SampleError) as exc_info:
        read_toml(missing, error_factory=_SampleError)
    assert "cannot read TOML" in str(exc_info.value)


def test_parse_toml_text_parses_an_in_memory_payload() -> None:
    """A well-formed TOML payload round-trips through parse_toml_text."""
    parsed = parse_toml_text('k = "v"\n', error_factory=_SampleError)
    assert parsed == {"k": "v"}


def test_parse_toml_text_wraps_decode_failure_via_error_factory() -> None:
    """Invalid TOML raises the caller-supplied error type."""
    with pytest.raises(_SampleError) as exc_info:
        parse_toml_text("not = valid = toml", error_factory=_SampleError)
    assert "invalid TOML" in str(exc_info.value)


def test_freeze_toml_converts_lists_to_tuples_recursively() -> None:
    """Nested list values become nested tuples; dict structure is preserved."""
    frozen = freeze_toml({"a": [1, 2, [3, 4]], "b": {"c": [5]}})
    assert frozen == {"a": (1, 2, (3, 4)), "b": {"c": (5,)}}
