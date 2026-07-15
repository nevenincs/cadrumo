"""Formatter grammar and strict-rendering contracts."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from .. import UnmatchedPlaceholderError, extract_placeholders
from .. import tr as render_translation

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_extract_placeholders_reports_runtime_root_kwargs_and_nested_specs() -> None:
    """Extraction matches kwargs consumed by attribute, index, and nested fields."""
    value = "{user.name!s} {items[0]!r} {amount:{width}.{precision}f} {} {0} {{escaped}} {not a placeholder}"

    assert extract_placeholders(value) == frozenset({"user", "items", "amount", "width", "precision"})


def test_extract_placeholders_recovers_named_fields_around_malformed_braces() -> None:
    """Malformed regions do not conceal independently valid supported fields."""
    assert extract_placeholders("broken { before {name!r} and {items[0]}") == frozenset({"name", "items"})


def test_strict_render_supports_attribute_index_and_nested_format_fields() -> None:
    """A complete runtime kwarg set renders every supported field form."""
    rendered = render_translation(
        "formatter_complete",
        locale="en",
        default="{user.name} {items[0]} {amount:{width}.{precision}f}",
        user=SimpleNamespace(name="Ana"),
        items=("first",),
        amount=12.345,
        width=7,
        precision=2,
    )

    assert rendered == "Ana first   12.35"


@pytest.mark.parametrize("missing", ["user", "items", "amount", "width", "precision"])
def test_strict_render_rejects_each_missing_root_or_nested_kwarg(missing: str) -> None:
    """Every root consumed by the runtime formatter remains a strict precondition."""
    values: dict[str, object] = {
        "user": SimpleNamespace(name="Ana"),
        "items": ("first",),
        "amount": 12.345,
        "width": 7,
        "precision": 2,
    }
    del values[missing]

    with pytest.raises(UnmatchedPlaceholderError) as exc_info:
        render_translation(
            "formatter_missing",
            locale="en",
            default="{user.name} {items[0]} {amount:{width}.{precision}f}",
            **values,
        )

    assert exc_info.value.name == missing


@pytest.mark.parametrize(
    "invalid_fragment",
    ['{"kind": 1}', "{not a placeholder}", "{}", "broken {"],
)
def test_strict_render_rejects_named_survivor_when_format_pass_fails(invalid_fragment: str) -> None:
    """An unrelated format error cannot return a supplied named token unresolved."""
    with pytest.raises(UnmatchedPlaceholderError) as exc_info:
        render_translation(
            "formatter_failed_pass",
            locale="en",
            default=f"{{name}} {invalid_fragment}",
            name="Ana",
        )

    assert exc_info.value.name == "name"
    assert "{name}" in exc_info.value.rendered


def test_strict_render_recovers_named_survivor_after_malformed_open_brace() -> None:
    """Malformed syntax before a named field cannot conceal its strict failure."""
    with pytest.raises(UnmatchedPlaceholderError) as exc_info:
        render_translation(
            "formatter_malformed_prefix",
            locale="en",
            default="broken { before {name}",
            name="Ana",
        )

    assert exc_info.value.name == "name"
    assert "{name}" in exc_info.value.rendered


def test_strict_render_accepts_escaped_literal_braces() -> None:
    """Escaped braces remain literal after a successful named format pass."""
    assert (
        render_translation(
            "formatter_escaped",
            locale="en",
            default="{{literal}} {name}",
            name="Ana",
        )
        == "{literal} Ana"
    )
