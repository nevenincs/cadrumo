"""Behaviour tests for the shared TOML helpers exported by :mod:`cadrumo.core`."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..toml import freeze_toml, parse_toml_text, read_toml, to_str_keyed_dict

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_to_str_keyed_dict_returns_str_keyed_copy() -> None:
    """A mapping with string keys is returned as a plain str-keyed dict."""
    result = to_str_keyed_dict({"a": 1, "b": [2, 3]}, error_factory=ValueError)
    assert result == {"a": 1, "b": [2, 3]}


def test_to_str_keyed_dict_rejects_non_string_key_via_error_factory() -> None:
    """A non-string key raises the exception built by ``error_factory``."""
    with pytest.raises(ValueError, match="TOML table keys must be strings"):
        to_str_keyed_dict({1: "x"}, error_factory=ValueError)


def test_valid_toml_payloads_parse_from_file_and_text(tmp_path: Path) -> None:
    """Well-formed TOML parses the same from files and in-memory text."""
    for case_name, text, expected in (
        (
            "section",
            'name = "value"\n[section]\nflag = true\n',
            {"name": "value", "section": {"flag": True}},
        ),
        ("flat", 'k = "v"\n', {"k": "v"}),
    ):
        target = tmp_path / f"{case_name}.toml"
        target.write_text(text, encoding="utf-8")

        assert read_toml(target, error_factory=ValueError) == expected
        assert parse_toml_text(text, error_factory=ValueError) == expected


def test_invalid_toml_wraps_decode_failure_via_error_factory(tmp_path: Path) -> None:
    """Invalid TOML raises the caller-supplied error type for both parser surfaces."""
    target = tmp_path / "bad.toml"
    target.write_text("not = valid = toml", encoding="utf-8")

    with pytest.raises(ValueError) as file_exc:
        read_toml(target, error_factory=ValueError)
    assert str(target) in str(file_exc.value)
    assert "invalid TOML" in str(file_exc.value)

    with pytest.raises(ValueError) as text_exc:
        parse_toml_text("not = valid = toml", error_factory=ValueError)
    assert "invalid TOML" in str(text_exc.value)


def test_read_toml_wraps_filesystem_error_via_error_factory(tmp_path: Path) -> None:
    """A missing file raises the caller-supplied error type, not a bare OSError."""
    missing = tmp_path / "missing.toml"
    with pytest.raises(ValueError) as exc_info:
        read_toml(missing, error_factory=ValueError)
    assert "cannot read TOML" in str(exc_info.value)


def test_freeze_toml_converts_lists_to_tuples_recursively() -> None:
    """Nested list values become nested tuples; dict structure is preserved."""
    frozen = freeze_toml({"a": [1, 2, [3, 4]], "b": {"c": [5]}})
    assert frozen == {"a": (1, 2, (3, 4)), "b": {"c": (5,)}}
