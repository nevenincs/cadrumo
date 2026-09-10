"""Behaviour tests for the shared TOML helpers exported by :mod:`cadrumo.core`."""

from __future__ import annotations

import tomllib
from datetime import UTC, date, datetime, time
from pathlib import Path

import pytest

from ..toml import freeze_toml, read_toml, render_toml, to_str_keyed_dict

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_to_str_keyed_dict_returns_str_keyed_copy() -> None:
    """A mapping with string keys is returned as a plain str-keyed dict."""
    result = to_str_keyed_dict({"a": 1, "b": [2, 3]}, error_factory=ValueError)
    assert result == {"a": 1, "b": [2, 3]}


def test_to_str_keyed_dict_rejects_non_string_key_via_error_factory() -> None:
    """A non-string key raises the exception built by ``error_factory``."""
    with pytest.raises(ValueError, match="TOML table keys must be strings"):
        to_str_keyed_dict({1: "x"}, error_factory=ValueError)


def test_valid_toml_payloads_parse_from_file(tmp_path: Path) -> None:
    """Well-formed TOML parses from files."""
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


def test_invalid_toml_wraps_decode_failure_via_error_factory(tmp_path: Path) -> None:
    """Invalid TOML raises the caller-supplied error type."""
    target = tmp_path / "bad.toml"
    target.write_text("not = valid = toml", encoding="utf-8")

    with pytest.raises(ValueError) as file_exc:
        read_toml(target, error_factory=ValueError)
    assert str(target) in str(file_exc.value)
    assert "invalid TOML" in str(file_exc.value)
    assert isinstance(file_exc.value.__cause__, tomllib.TOMLDecodeError)


def test_read_toml_wraps_invalid_utf8_as_invalid_toml(tmp_path: Path) -> None:
    """The file boundary keeps undecodable UTF-8 inside the public TOML error contract."""
    target = tmp_path / "invalid-encoding.toml"
    target.write_bytes(b"name = '\xff'")

    with pytest.raises(ValueError) as exc_info:
        read_toml(target, error_factory=ValueError)

    assert str(exc_info.value).startswith(f"{target}: invalid TOML:")
    assert isinstance(exc_info.value.__cause__, UnicodeDecodeError)


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


_EVERY_VALUE_SHAPE: dict[str, object] = {
    "title": 'quote " backslash \\ tab \t newline \n bell \x07 ñ',
    "count": -3,
    "ratio": 0.1,
    "tiny": 1e-07,
    "flag": False,
    "day": date(2025, 1, 1),
    "moment": datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC),
    "clock": time(6, 7, 8),
    "empty_array": [],
    "scalars": [1, 2, 3],
    "mixed": [{"a": 1}, 2],
    "inline_in_array": [[{"x": "y"}]],
    "empty_table": {},
    "key with space": "quoted key",
    "revisions": {
        "2025": {
            "review_status": "reviewed",
            "period_selector": {"periods": ["1T", "2T"]},
            "casillas": [
                {"id": "01", "section": ["a", "b"], "export": {"record": "0002"}, "nested": [{"k": 1}]},
                {"id": "02", "required": True},
            ],
        },
    },
}


def test_render_toml_parses_back_to_every_value_it_was_given() -> None:
    """Every value shape tomllib produces survives render then parse unchanged."""
    rendered = render_toml(_EVERY_VALUE_SHAPE)

    assert tomllib.loads(rendered) == _EVERY_VALUE_SHAPE


def test_render_toml_accepts_the_tuples_freeze_produces() -> None:
    """A frozen document renders the same text as the parsed one it came from."""
    assert render_toml(freeze_toml(_EVERY_VALUE_SHAPE)) == render_toml(_EVERY_VALUE_SHAPE)


def test_render_toml_writes_arrays_of_tables_as_array_headers() -> None:
    """Casilla-shaped rows keep the ``[[...]]`` block form the source files use."""
    rendered = render_toml({"revisions": {"2025": {"casillas": [{"id": "01"}, {"id": "02"}]}}})

    assert rendered == '[[revisions.2025.casillas]]\nid = "01"\n\n[[revisions.2025.casillas]]\nid = "02"\n'


def test_render_toml_places_comments_above_their_table_and_the_parser_drops_them() -> None:
    document = {"revisions": {"2025": {"casillas": [{"id": "01"}, {"id": "02"}]}}}

    rendered = render_toml(
        document,
        comments={(): "head: one\nhead: two", ("revisions", "2025", "casillas", 1): "row: second"},
    )

    assert rendered.splitlines() == [
        "# head: one",
        "# head: two",
        "[[revisions.2025.casillas]]",
        'id = "01"',
        "",
        "# row: second",
        "[[revisions.2025.casillas]]",
        'id = "02"',
    ]
    assert tomllib.loads(rendered) == document


def test_render_toml_refuses_a_value_with_no_toml_form() -> None:
    with pytest.raises(TypeError, match="no TOML form"):
        render_toml({"value": None})
    with pytest.raises(TypeError, match="keys must be strings"):
        render_toml({"table": {1: "x"}})
