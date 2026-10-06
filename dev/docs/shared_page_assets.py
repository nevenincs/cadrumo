"""Write what every page of a site root shares once, as files the pages link.

The theme declares its colour and font variables in a ``<style>`` element in
each page's head, and the interaction layer's strings rode along as an inline
JSON payload. Both are the same on every page of a root, so together they were
about eight kilobytes repeated per page. Here each becomes one static file: a
stylesheet loaded after every other sheet, where the inline block used to sit in
the cascade, and a script that publishes the strings before ``cadrumo-docs.js``
reads them.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from sphinx.application import Sphinx

THEME_VARIABLES_STYLESHEET: Final[str] = "cadrumo-theme-variables.css"
CHROME_STRINGS_SCRIPT: Final[str] = "cadrumo-chrome-strings.js"
#: The global ``cadrumo-docs.js`` reads its strings from.
CHROME_STRINGS_GLOBAL: Final[str] = "cadrumoChromeStrings"

#: After the ``html_css_files`` sheets (priority 800), as the theme's inline block was.
_STYLESHEET_PRIORITY: Final[int] = 900
#: Before the ``html_js_files`` scripts (priority 800), which read the strings.
_SCRIPT_PRIORITY: Final[int] = 700
#: After the theme's own ``builder-inited`` handler has settled the Pygments styles.
_WRITE_PRIORITY: Final[int] = 600


def _declarations(code_colors: Mapping[str, str], variables: Mapping[str, str]) -> str:
    declared = {
        "color-code-background": code_colors["background"],
        "color-code-foreground": code_colors["foreground"],
        **variables,
    }
    return "".join(f"--{name}:{value};" for name, value in declared.items())


def theme_variables_css(
    light: Mapping[str, str],
    dark: Mapping[str, str],
    *,
    light_code: Mapping[str, str],
    dark_code: Mapping[str, str],
) -> str:
    """Return the theme's variable declarations in the selectors its inline block uses."""
    light_rule = _declarations(light_code, light)
    dark_rule = _declarations(dark_code, dark)
    return (
        f"body{{{light_rule}}}\n"
        "@media not print{\n"
        f'body[data-theme="dark"]{{{dark_rule}}}\n'
        f'@media (prefers-color-scheme:dark){{body:not([data-theme="light"]){{{dark_rule}}}}}\n'
        "}\n"
    )


def chrome_strings_script(strings: Mapping[str, str]) -> str:
    """Return the script that publishes one root's chrome strings."""
    # ASCII-only JSON is a valid script in every encoding a host might assume.
    return f"window.{CHROME_STRINGS_GLOBAL}={json.dumps(dict(strings), ensure_ascii=True, sort_keys=True)};\n"


def _write_shared_page_assets(app: Sphinx) -> None:
    # Imported here: only a documentation build has Sphinx and the theme installed.
    from furo import get_pygments_style_colors
    from sphinx.builders.html import StandaloneHTMLBuilder
    from sphinx.highlighting import PygmentsBridge

    builder = app.builder
    if not isinstance(builder, StandaloneHTMLBuilder) or app.config.html_theme != "furo":
        return

    options = app.config.html_theme_options
    stylesheet = theme_variables_css(
        options.get("light_css_variables", {}),
        options.get("dark_css_variables", {}),
        light_code=get_pygments_style_colors(
            builder.highlighter.formatter_args["style"],
            fallbacks={"foreground": "black", "background": "white"},
        ),
        dark_code=get_pygments_style_colors(
            PygmentsBridge("html", app.config.pygments_dark_style).formatter_args["style"],
            fallbacks={"foreground": "white", "background": "black"},
        ),
    )
    static = Path(builder.outdir) / "_static"
    static.mkdir(parents=True, exist_ok=True)
    # Written before any page renders, so each page's link carries the file's checksum.
    (static / THEME_VARIABLES_STYLESHEET).write_text(stylesheet, encoding="utf-8", newline="\n")
    (static / CHROME_STRINGS_SCRIPT).write_text(
        chrome_strings_script(app.config.html_context.get("cadrumo_chrome", {})), encoding="utf-8", newline="\n"
    )


def register(app: Sphinx) -> None:
    """Link the shared files from every page and write them when the build starts."""
    app.add_css_file(THEME_VARIABLES_STYLESHEET, priority=_STYLESHEET_PRIORITY)
    app.add_js_file(CHROME_STRINGS_SCRIPT, priority=_SCRIPT_PRIORITY)
    app.connect("builder-inited", _write_shared_page_assets, priority=_WRITE_PRIORITY)
