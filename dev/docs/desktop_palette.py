"""The desktop shell's colour palette, generated from the documentation theme.

The shell sits beside the documentation and must wear the same colours, so it
reads the documentation's own tokens rather than copies of them. This module
projects them into one stylesheet for the shell's build:

- every Furo variable ``docs/conf.py`` sets in ``html_theme_options``, light
  values under ``:root`` and dark values under ``[data-scheme="dark"]``, with
  Furo's variable names unchanged;
- the Cadrumo accent tokens ``docs/_static/cadrumo-docs.css`` declares on
  ``:root``, with each ``light-dark(light, dark)`` pair split across the two
  blocks.

The dark block uses the plain attribute selector, never ``:root[...]``, so a
nested always-dark area of the shell resolves the dark values too.

Both sources are read structurally and refused when their shape is not the
one described here: ``conf.py`` through its syntax tree, never by executing
it, and the stylesheet through a small tokenizer that understands comments,
strings and blocks.
"""

from __future__ import annotations

import argparse
import ast
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from cadrumo.core.atomic_write import atomic_write_text
from dev._paths import REPO_ROOT, UTF_8

CONF_PATH: Final[Path] = REPO_ROOT / "docs" / "conf.py"
STYLESHEET_PATH: Final[Path] = REPO_ROOT / "docs" / "_static" / "cadrumo-docs.css"

#: Light values apply everywhere; the dark block is a plain attribute selector
#: so the document root and any nested always-dark area both resolve it.
LIGHT_SELECTOR: Final[str] = ":root"
DARK_SELECTOR: Final[str] = '[data-scheme="dark"]'

#: The Cadrumo tokens the shell takes from the documentation stylesheet.
ACCENT_TOKENS: Final[tuple[str, ...]] = (
    "--cadrumo-accent",
    "--cadrumo-accent-warning",
    "--cadrumo-accent-success",
    "--cadrumo-accent-danger",
)

_THEME_OPTIONS: Final[str] = "html_theme_options"
_SCHEMES: Final[tuple[str, str]] = ("light_css_variables", "dark_css_variables")
_VARIABLE_NAME: Final[re.Pattern[str]] = re.compile(r"[a-z][a-z0-9-]*")
# A declaration value may not end the declaration, open or close a block, or
# start markup; anything else Furo itself would emit verbatim.
_UNSAFE_VALUE: Final[re.Pattern[str]] = re.compile(r"[;{}<>\\\n\r]|/\*")
_COLOUR: Final[str] = r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})"
_PLAIN_COLOUR: Final[re.Pattern[str]] = re.compile(_COLOUR)
_LIGHT_DARK: Final[re.Pattern[str]] = re.compile(rf"light-dark\(\s*({_COLOUR})\s*,\s*({_COLOUR})\s*\)")


class PaletteSourceError(ValueError):
    """A palette source does not have the shape this generator reads."""


@dataclass(frozen=True)
class Palette:
    """Custom properties for the light scheme and the dark overrides."""

    light: dict[str, str]
    dark: dict[str, str]


def _module_strings(tree: ast.Module) -> dict[str, str | None]:
    """Map each module-level name to its string literal, or None when it is not one.

    A name assigned more than once maps to None, so it can never be resolved.
    """
    names: dict[str, str | None] = {}
    for node in tree.body:
        targets: Sequence[ast.expr]
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        literal = value.value if isinstance(value, ast.Constant) and isinstance(value.value, str) else None
        for target in targets:
            if isinstance(target, ast.Name):
                names[target.id] = None if target.id in names else literal
    return names


def _theme_options(tree: ast.Module) -> ast.Dict:
    """Return the single module-level ``html_theme_options`` dict display."""
    displays = [
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == _THEME_OPTIONS for target in node.targets)
    ]
    if len(displays) != 1 or not isinstance(displays[0], ast.Dict):
        raise PaletteSourceError(f"{_THEME_OPTIONS} must be assigned once, to a dict display")
    return displays[0]


def _variables(display: ast.Dict, scheme: str, strings: Mapping[str, str | None]) -> dict[str, str]:
    """Read one ``*_css_variables`` mapping, resolving names to module string literals."""
    found = [
        value
        for key, value in zip(display.keys, display.values, strict=True)
        if isinstance(key, ast.Constant) and key.value == scheme
    ]
    if len(found) != 1 or not isinstance(found[0], ast.Dict):
        raise PaletteSourceError(f"{_THEME_OPTIONS}[{scheme!r}] must appear once, as a dict display")
    variables: dict[str, str] = {}
    for key, value in zip(found[0].keys, found[0].values, strict=True):
        if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
            raise PaletteSourceError(f"{scheme} keys must be string literals")
        name = key.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            text: str | None = value.value
        elif isinstance(value, ast.Name):
            text = strings.get(value.id)
        else:
            text = None
        if text is None:
            raise PaletteSourceError(f"{scheme}[{name!r}] is not a string literal or a name bound once to one")
        variables[_checked_name(name, scheme)] = _checked_value(text, f"{scheme}[{name!r}]")
    if not variables:
        raise PaletteSourceError(f"{scheme} declares no variables")
    return variables


def _checked_name(name: str, where: str) -> str:
    if name in {"--", ""} or not _VARIABLE_NAME.fullmatch(name):
        raise PaletteSourceError(f"{where} carries a variable name CSS cannot hold: {name!r}")
    return name


def _checked_value(value: str, where: str) -> str:
    stripped = value.strip()
    if not stripped or _UNSAFE_VALUE.search(stripped):
        raise PaletteSourceError(f"{where} carries a value that is not a single CSS declaration value")
    return stripped


def theme_variables(conf_source: str) -> Palette:
    """Read Furo's light and dark variables out of ``conf.py`` source text."""
    tree = ast.parse(conf_source)
    display = _theme_options(tree)
    strings = _module_strings(tree)
    light, dark = (_variables(display, scheme, strings) for scheme in _SCHEMES)
    unknown = sorted(set(dark) - set(light))
    if unknown:
        raise PaletteSourceError(f"dark variables without a light value: {unknown}")
    return Palette(light=light, dark=dark)


def _root_declarations(stylesheet: str) -> list[tuple[str, str]]:
    """Return the declarations of every top-level ``:root`` block, in order."""
    declarations: list[tuple[str, str]] = []
    depth = 0
    prelude: list[str] = []
    block: list[str] = []
    selectors: list[str] = []
    index = 0
    while index < len(stylesheet):
        char = stylesheet[index]
        if stylesheet.startswith("/*", index):
            end = stylesheet.find("*/", index + 2)
            if end < 0:
                raise PaletteSourceError("the stylesheet has an unterminated comment")
            index = end + 2
            continue
        if char in "\"'":
            end = index + 1
            while end < len(stylesheet) and stylesheet[end] != char:
                end += 2 if stylesheet[end] == "\\" else 1
            if end >= len(stylesheet):
                raise PaletteSourceError("the stylesheet has an unterminated string")
            (block if depth else prelude).append(stylesheet[index : end + 1])
            index = end + 1
            continue
        if char == "{":
            if depth == 0:
                selectors.append("".join(prelude).strip())
                prelude.clear()
                block.clear()
            elif selectors[-1] == ":root":
                raise PaletteSourceError("a :root block contains a nested block")
            depth += 1
        elif char == "}":
            if depth == 0:
                raise PaletteSourceError("the stylesheet closes a block it never opened")
            depth -= 1
            if depth == 0:
                if selectors[-1] == ":root":
                    declarations.extend(_declarations("".join(block)))
                prelude.clear()
        elif depth == 0:
            prelude.append(char)
            if char == ";":
                prelude.clear()
        elif depth == 1:
            block.append(char)
        index += 1
    if depth:
        raise PaletteSourceError("the stylesheet leaves a block open")
    return declarations


def _declarations(block: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for statement in block.split(";"):
        if not statement.strip():
            continue
        name, separator, value = statement.partition(":")
        if not separator:
            raise PaletteSourceError(f"a :root block holds a statement that is not a declaration: {statement!r}")
        pairs.append((name.strip(), value.strip()))
    return pairs


def accent_variables(stylesheet: str) -> Palette:
    """Read the accent tokens from the stylesheet's ``:root`` blocks, splitting ``light-dark`` pairs."""
    declared: dict[str, list[str]] = {}
    for name, value in _root_declarations(stylesheet):
        if name in ACCENT_TOKENS:
            declared.setdefault(name, []).append(value)
    light: dict[str, str] = {}
    dark: dict[str, str] = {}
    for token in ACCENT_TOKENS:
        values = declared.get(token, [])
        if len(values) != 1:
            raise PaletteSourceError(f"{token} must be declared exactly once on :root, found {len(values)}")
        value = values[0]
        if pair := _LIGHT_DARK.fullmatch(value):
            light[token], dark[token] = pair.group(1), pair.group(2)
        elif _PLAIN_COLOUR.fullmatch(value):
            light[token] = value
        else:
            raise PaletteSourceError(f"{token} is neither a hex colour nor a light-dark() pair of hex colours")
    return Palette(light=light, dark=dark)


def desktop_palette(conf_source: str, stylesheet: str) -> Palette:
    """Combine the Furo theme variables with the Cadrumo accent tokens."""
    theme = theme_variables(conf_source)
    accents = accent_variables(stylesheet)
    light = {f"--{name}": value for name, value in theme.light.items()}
    dark = {f"--{name}": value for name, value in theme.dark.items()}
    clashes = sorted(set(light) & set(accents.light))
    if clashes:
        raise PaletteSourceError(f"accent tokens shadow theme variables: {clashes}")
    return Palette(light={**light, **accents.light}, dark={**dark, **accents.dark})


def render_palette(palette: Palette) -> str:
    """Render the light block on ``:root`` and the dark block on ``[data-scheme="dark"]``."""

    def block(selector: str, values: Mapping[str, str]) -> str:
        lines = "".join(f"  {name}: {value};\n" for name, value in values.items())
        return f"{selector} {{\n{lines}}}\n"

    header = (
        "/* Generated by dev/docs/desktop_palette.py from docs/conf.py and\n"
        "   docs/_static/cadrumo-docs.css. Do not edit; regenerate instead. */\n"
    )
    return f"{header}\n{block(LIGHT_SELECTOR, palette.light)}\n{block(DARK_SELECTOR, palette.dark)}"


def main(argv: Sequence[str] | None = None) -> int:
    """Write the desktop shell's palette stylesheet."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--conf", type=Path, default=CONF_PATH)
    parser.add_argument("--stylesheet", type=Path, default=STYLESHEET_PATH)
    # The build names where its generated inputs go; nothing is written into the source tree by default.
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        palette = desktop_palette(
            arguments.conf.read_text(encoding=UTF_8), arguments.stylesheet.read_text(encoding=UTF_8)
        )
    except (OSError, SyntaxError, PaletteSourceError) as exc:
        parser.exit(1, f"refused: {exc}\n")
    output = Path(arguments.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(output, render_palette(palette), encoding=UTF_8)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
