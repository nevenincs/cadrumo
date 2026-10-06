"""Carry every language's Sphinx interface strings through one compile.

Sphinx ships its own interface strings -- the search page's words, the
navigation's labels -- compiled to JavaScript, one file per language.
``StandaloneHTMLBuilder`` copies the build language's file to
``_static/translations.js`` and adds the script tag that loads it only for a
language whose file it finds. English has none, so an English build has neither
the file nor the tag, and each other language has both.

The one compile has no one language, so both become per-language here:

- The file is written once per language beside the canonical path, for the
  driver to store as that language's copy of it
  (:func:`dev.docs.compile_once.compile_once`). English, having no file, is
  stored none, exactly as its own build has none.
- The TAG is a mark. It cannot be left to Sphinx, because a tag Sphinx writes
  stands in the page every language shares and English needs no tag at all. So
  the mark carries the line break in front of it as well: a language with the
  file reads a line, and English reads nothing and composes to no line. That is
  the shape :func:`dev.docs._locale_chrome.docs_line` uses, for the same
  reason -- an element some languages have and others do not cannot be a line
  of its own.

The cache key inside the tag is each language's own, computed here from the
bytes written for that language. The usual substitution of a key the compile
wrote (:func:`dev.docs.compile_slots.cache_key_slots`) has nothing to work
from, because the compile writes no canonical file to take a key of.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

from .compile_slots import Rendering, active
from .language_roots import asset_cache_key

if TYPE_CHECKING:
    from sphinx.application import Sphinx

__all__ = ["TRANSLATIONS_SCRIPT", "language_translations_js", "register", "translations_js_tag"]

#: The canonical path, inside ``_static``, that every page links.
TRANSLATIONS_SCRIPT: Final[str] = "translations.js"

#: Before any extension's own handler, because the scripts Sphinx's
#: ``init_js_files`` left are what :func:`_anchor` reads and an extension that
#: registers one at this event adds it to the same record.
_WRITE_PRIORITY: Final[int] = 1

#: The priority ``StandaloneHTMLBuilder.add_js_file`` gives a script by default,
#: and therefore the priority it gives ``translations.js``.
_DEFAULT_PRIORITY: Final[int] = 500

#: The priority ``init_js_files`` gives a script named in ``html_js_files``.
_CONFIGURED_PRIORITY: Final[int] = 800

#: The scripts Sphinx adds before it reaches the registered and configured ones.
_SPHINX_SCRIPTS: Final[tuple[str, ...]] = (
    "documentation_options.js",
    "doctools.js",
    "sphinx_highlight.js",
)


def language_translations_js(language: str) -> str:
    """Return the name the compile writes one language's interface strings under.

    The canonical :data:`TRANSLATIONS_SCRIPT` is what every page links, and the
    one compile writes no bytes for it. Each language's real file is written
    beside it under this name, for the driver to store as that language's copy
    of the canonical path. A variant is build output of the compile and is never
    served.
    """
    return f"translations.{language}.js"


def _candidates(app: Sphinx, language: str) -> Iterator[Path]:
    """Yield where Sphinx looks for one language's compiled interface strings.

    The same places, in the same order, as
    ``StandaloneHTMLBuilder._get_translations_js``: each configured locale
    directory, then the Sphinx package's own, then the prefix's share tree.
    """
    from sphinx import package_dir

    for directory in app.config.locale_dirs:
        yield Path(directory, language, "LC_MESSAGES", "sphinx.js")
    yield Path(package_dir, "locale", language, "LC_MESSAGES", "sphinx.js")
    yield Path(sys.prefix, "share", "sphinx", "locale", language, "sphinx.js")


def _shipped(app: Sphinx, language: str) -> Path | None:
    """Return one language's compiled interface strings, or None if Sphinx ships none."""
    return next((path for path in _candidates(app, language) if path.is_file()), None)


def translations_js_tag(href: str, key: str, *, newline: str) -> str:
    """Return the script tag that loads the interface strings, and the line it starts.

    Args:
        href: The path from the page being written to the canonical file.
        key: The cache key of the bytes that path holds for this language.
        newline: The line terminator the page being written uses.

    Returns:
        The line break, the indentation the theme's own tags carry, and the tag.
    """
    return f'{newline}    <script src="{href}?v={key}"></script>'


def _anchor(app: Sphinx) -> str:
    """Return the script ``translations.js`` is written after, as the page links it.

    Sphinx adds ``translations.js`` last of all the scripts its own
    ``init_js_files`` adds, at the default priority, and the page's tags are
    sorted by priority with ties left in the order they were added. So the tag
    follows the last of those scripts that sorts at or below that priority: a
    script of the same priority added later -- one an extension adds once the
    builder is initialised -- sorts after it and must stay after it. The order
    the scripts are declared in is not the order they are written in, because a
    registered script carries its own priority: the theme registers its own
    script at 200 after an extension has registered one at 500.
    """
    declared: list[tuple[str, int]] = [(name, 200) for name in _SPHINX_SCRIPTS]
    declared += [
        (str(filename), int(attributes.get("priority", _DEFAULT_PRIORITY)))
        for filename, attributes in app.registry.js_files
        if filename
    ]
    declared += [
        (str(filename), int(attributes.get("priority", _CONFIGURED_PRIORITY)))
        for filename, attributes in app.builder.config.html_js_files
        if filename
    ]
    written = sorted(declared, key=lambda declaration: declaration[1])
    last = [name for name, priority in written if priority <= _DEFAULT_PRIORITY][-1]
    return f"_static/{last}"


@dataclass(frozen=True)
class _Written:
    """What one compile wrote for the interface strings.

    Attributes:
        keys: Each language's cache key, in the stored order, empty for a
            language Sphinx ships no interface strings for.
        anchor: The script, as a page links it, the tag is written after.
    """

    keys: tuple[str, ...]
    anchor: str


# ── The compile's one record of what was written ─────────────────────────────
# The tag is built while a page is written, from facts settled when the builder
# was initialised. The page context carries no argument of ours, so the facts
# wait here, as the mark record itself does.
_WRITTEN: _Written | None = None


def _write_language_scripts(app: Sphinx) -> None:
    """Write each language's interface strings beside the canonical path."""
    global _WRITTEN
    slots = active()
    if slots is None:
        return
    static = Path(app.builder.outdir) / "_static"
    static.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    for language in slots.languages:
        shipped = _shipped(app, language)
        if shipped is None:
            keys.append("")
            continue
        content = shipped.read_bytes()
        (static / language_translations_js(language)).write_bytes(content)
        keys.append(asset_cache_key(content))
    _WRITTEN = _Written(keys=tuple(keys), anchor=_anchor(app))


def _supply_tag(
    app: Sphinx,
    pagename: str,
    templatename: str,
    context: dict[str, object],
    doctree: object,
) -> None:
    """Give one page the function its script loop asks for the tag with."""
    slots, written = active(), _WRITTEN
    if slots is None or written is None:
        context["cadrumo_translations_js_tag"] = lambda _script: ""
        return
    pathto = context["pathto"]
    if not callable(pathto):
        raise TypeError("the page context carries no pathto resolver")
    href = str(pathto(f"_static/{TRANSLATIONS_SCRIPT}", resource=True))
    # A recorded string is put straight into a finished page, so the line break
    # it carries has to be the terminator that page already uses.
    tag = slots.mark(
        Rendering.VERBATIM,
        [translations_js_tag(href, key, newline=os.linesep) if key else "" for key in written.keys],
    )
    context["cadrumo_translations_js_tag"] = lambda script: tag if str(script) == written.anchor else ""


def register(app: Sphinx) -> None:
    """Write each language's interface strings and give every page its tag.

    Outside the one compile the tag is Sphinx's own and this adds nothing: the
    function the template calls returns the empty string for every script, so a
    single-language build writes exactly the bytes it writes today.
    """
    app.connect("builder-inited", _write_language_scripts, priority=_WRITE_PRIORITY)
    app.connect("html-page-context", _supply_tag)
