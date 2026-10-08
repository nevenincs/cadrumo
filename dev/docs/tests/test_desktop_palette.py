"""The desktop shell palette is a projection of the documentation theme.

The live tests compare the structural read of ``docs/conf.py`` with the values
Sphinx itself sees when it executes the configuration, and the stylesheet read
with the declarations the documentation ships. The fixture tests plant each
shape the generator must refuse.
"""

from __future__ import annotations

import runpy
from pathlib import Path

import pytest

from ..desktop_palette import (
    ACCENT_TOKENS,
    CONF_PATH,
    DARK_SELECTOR,
    STYLESHEET_PATH,
    Palette,
    PaletteSourceError,
    accent_variables,
    desktop_palette,
    main,
    render_palette,
    theme_variables,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CONF = """
_STACK = "Inter, sans-serif"
html_theme_options = {
    "light_css_variables": {"color-link": "#9e4029", "font-stack": _STACK},
    "dark_css_variables": {"color-link": "#e0785c"},
}
"""

_STYLESHEET = """
/* :root { --cadrumo-accent: #000000; } inside a comment is not a declaration */
:root {
  --cadrumo-accent: #c4553b;
  --cadrumo-header-h: 3.5rem;
  --cadrumo-accent-warning: light-dark(#7a4f0f, #d9a441);
  --cadrumo-accent-success: light-dark(#3a6249,#7fb494);
  --cadrumo-accent-danger: light-dark( #b3362a , #e08376 );
  --cadrumo-shadow-pop: 0 0 0 1px light-dark(rgb(0 0 0 / 5%), rgb(255 255 255 / 6%));
}
body[data-theme="dark"] { --cadrumo-accent: #ffffff; }
.label::before { content: "}{"; }
"""


def test_conf_variables_equal_what_sphinx_executes() -> None:
    executed = runpy.run_path(str(CONF_PATH))["html_theme_options"]

    read = theme_variables(CONF_PATH.read_text(encoding="utf-8"))

    assert read.light == executed["light_css_variables"]
    assert read.dark == executed["dark_css_variables"]


def test_the_shipped_palette_carries_every_theme_variable_and_split_accents() -> None:
    executed = runpy.run_path(str(CONF_PATH))["html_theme_options"]

    palette = desktop_palette(CONF_PATH.read_text(encoding="utf-8"), STYLESHEET_PATH.read_text(encoding="utf-8"))

    assert {name: value for name, value in palette.light.items() if name not in ACCENT_TOKENS} == {
        f"--{name}": value for name, value in executed["light_css_variables"].items()
    }
    assert {name: value for name, value in palette.dark.items() if name not in ACCENT_TOKENS} == {
        f"--{name}": value for name, value in executed["dark_css_variables"].items()
    }
    assert set(ACCENT_TOKENS) <= set(palette.light)
    for token in ("--cadrumo-accent-warning", "--cadrumo-accent-success", "--cadrumo-accent-danger"):
        assert palette.dark[token] != palette.light[token], token


def test_fixture_sources_project_into_the_two_scheme_blocks() -> None:
    palette = desktop_palette(_CONF, _STYLESHEET)

    assert palette == Palette(
        light={
            "--color-link": "#9e4029",
            "--font-stack": "Inter, sans-serif",
            "--cadrumo-accent": "#c4553b",
            "--cadrumo-accent-warning": "#7a4f0f",
            "--cadrumo-accent-success": "#3a6249",
            "--cadrumo-accent-danger": "#b3362a",
        },
        dark={
            "--color-link": "#e0785c",
            "--cadrumo-accent-warning": "#d9a441",
            "--cadrumo-accent-success": "#7fb494",
            "--cadrumo-accent-danger": "#e08376",
        },
    )
    rendered = render_palette(palette)
    assert ":root {\n  --color-link: #9e4029;\n" in rendered
    assert '\n[data-scheme="dark"] {\n  --color-link: #e0785c;\n' in rendered
    assert DARK_SELECTOR == '[data-scheme="dark"]'
    assert ":root[" not in rendered


@pytest.mark.parametrize(
    ("conf", "match"),
    [
        (_CONF + "html_theme_options = {}\n", "assigned once"),
        ("html_theme_options = dict(light_css_variables={})\n", "dict display"),
        (_CONF.replace('"#9e4029"', "'#9e' + '4029'"), "not a string literal"),
        (_CONF + '_STACK = "Other"\n', "not a string literal or a name bound once"),
        (_CONF.replace('"#e0785c"', '"#e0785c; color: red"'), "single CSS declaration value"),
        (_CONF.replace('"color-link": "#e0785c"', '"color-only-dark": "#e0785c"'), "without a light value"),
        (_CONF.replace('"dark_css_variables"', '"dark_variables"'), "dark_css_variables"),
        (_CONF.replace('"color-link": "#9e4029"', '"Color Link": "#9e4029"'), "variable name"),
    ],
)
def test_conf_shapes_the_generator_does_not_read_are_refused(conf: str, match: str) -> None:
    with pytest.raises(PaletteSourceError, match=match):
        theme_variables(conf)


@pytest.mark.parametrize(
    ("stylesheet", "match"),
    [
        (_STYLESHEET.replace("--cadrumo-accent-danger", "--cadrumo-accent-error"), "--cadrumo-accent-danger"),
        (_STYLESHEET + ":root { --cadrumo-accent: #c4553b; }\n", "exactly once"),
        (_STYLESHEET.replace("#c4553b", "var(--brand)"), "neither a hex colour"),
        (_STYLESHEET.replace("light-dark(#7a4f0f, #d9a441)", "light-dark(#7a4f0f)"), "neither a hex colour"),
        (_STYLESHEET + "/* open", "unterminated comment"),
        (_STYLESHEET + ":root {", "block open"),
        (_STYLESHEET + ":root { @media print { color: red; } }", "nested block"),
    ],
)
def test_stylesheet_shapes_the_generator_does_not_read_are_refused(stylesheet: str, match: str) -> None:
    with pytest.raises(PaletteSourceError, match=match):
        accent_variables(stylesheet)


def test_main_writes_the_palette_and_refuses_without_writing(tmp_path: Path) -> None:
    conf = tmp_path / "conf.py"
    stylesheet = tmp_path / "cadrumo-docs.css"
    output = tmp_path / "generated" / "palette.css"
    conf.write_text(_CONF, encoding="utf-8")
    stylesheet.write_text(_STYLESHEET, encoding="utf-8")
    arguments = ["--conf", str(conf), "--stylesheet", str(stylesheet), "--output", str(output)]

    assert main(arguments) == 0
    assert output.read_text(encoding="utf-8") == render_palette(desktop_palette(_CONF, _STYLESHEET))

    output.unlink()
    stylesheet.write_text(_STYLESHEET.replace("#c4553b", "var(--brand)"), encoding="utf-8")
    with pytest.raises(SystemExit) as refused:
        main(arguments)
    assert refused.value.code == 1
    assert not output.exists()
