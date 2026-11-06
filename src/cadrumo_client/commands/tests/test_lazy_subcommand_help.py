"""A lazy subcommand renders its help only when a help surface asks, in the language then current."""

from __future__ import annotations

import pytest
import typer

from ..suggestions import LazyFactoryTarget, LazySubcommand

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_help_is_rendered_on_demand_and_not_at_registration() -> None:
    rendered: list[str] = []
    language = ["es"]

    def render_help() -> str:
        rendered.append(language[0])
        return f"ayuda {language[0]}"

    child = LazySubcommand("child", LazyFactoryTarget(typer.Typer), help=render_help)

    assert rendered == []
    assert child.get_short_help_str() == "ayuda es"
    language[0] = "ca"
    assert child.help == "ayuda ca"
    assert child.short_help is None


def test_explicit_short_help_precedes_the_long_help() -> None:
    child = LazySubcommand(
        "child",
        LazyFactoryTarget(typer.Typer),
        help=lambda: "Long help text.",
        short_help=lambda: "Short.",
    )

    assert child.get_short_help_str() == "Short."


def test_a_child_without_help_has_empty_short_help() -> None:
    assert LazySubcommand("child", LazyFactoryTarget(typer.Typer)).get_short_help_str() == ""
