"""Gates for the typesetting language of a generator-owned page.

A build educates quotation marks with the characters of the language it builds,
so one English sentence reaches a reader as ``'Mis expedientes'`` typeset four
ways. :mod:`dev.docs.untranslated_typesetting` stops that where the page is
nobody's translation: a committed page that declares itself generated, which
reaches every language's build as the same English prose.

The expected characters are docutils' own documented quote sets rather than a
reading of the transform: English educates a single-quoted phrase to ``‘ ’``
and Spanish educates it to ``“ ”``, which is exactly the difference the one
compile measured against each language's own build before this transform
existed.
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Final

import pytest
from sphinx.application import Sphinx

from ..i18n import _GENERATED_MARKER
from ..untranslated_typesetting import PAGES_SETTING

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

#: The phrase both pages carry, single-quoted in the source.
_SOURCE: Final[str] = "Open 'Mis expedientes' now."
#: What English education makes of it.
_ENGLISH: Final[str] = "Open ‘Mis expedientes’ now."
#: What Spanish education makes of it.
_SPANISH: Final[str] = "Open “Mis expedientes” now."

#: The banner a generator stamps into a page it owns, which is what puts a page
#: in the set the transforms read. Taken from the production constant, so a
#: changed banner cannot leave this gate testing a page nothing selects.
_BANNER: Final[str] = f"<!-- {_GENERATED_MARKER}: regenerate it, do not edit it -->"


def _write_site(root: Path, *, register: bool) -> None:
    """Write a two-page Spanish site, one page generator-owned and one authored."""
    setup = (
        "\ndef setup(app):\n    from dev.docs.untranslated_typesetting import register\n    register(app)\n"
        if register
        else ""
    )
    (root / "conf.py").write_text(
        'extensions = ["myst_parser"]\n'
        'language = "es"\n'
        "smartquotes = True\n"
        "from pathlib import Path\n"
        "from dev.docs.untranslated_typesetting import source_language_pages\n"
        f"{PAGES_SETTING} = source_language_pages(Path(__file__).resolve().parent)\n" + setup,
        encoding="utf-8",
    )
    (root / "index.md").write_text(
        f"# Index\n\n{_SOURCE}\n\n```{{toctree}}\nauthored\ngenerated\n```\n", encoding="utf-8"
    )
    (root / "authored.md").write_text(f"# Authored\n\n{_SOURCE}\n", encoding="utf-8")
    (root / "generated.md").write_text(f"{_BANNER}\n\n# Generated\n\n{_SOURCE}\n", encoding="utf-8")


def _build(root: Path) -> dict[str, str]:
    """Build the site in-process and return each page's HTML by name."""
    out = root / "_out"
    app = Sphinx(
        srcdir=str(root),
        confdir=str(root),
        outdir=str(out),
        doctreedir=str(root / "_doctrees"),
        buildername="html",
        warning=StringIO(),
        freshenv=True,
    )
    app.build()
    return {page.stem: page.read_text(encoding="utf-8") for page in out.glob("*.html")}


def test_a_generator_owned_page_is_typeset_in_the_source_language(tmp_path: Path) -> None:
    """The generator-owned page educates in English; its authored sibling in Spanish."""
    _write_site(tmp_path, register=True)
    pages = _build(tmp_path)
    assert _ENGLISH in pages["generated"], (
        f"the generator-owned page was not typeset in the source language; expected {_ENGLISH!r} in generated.html"
    )
    assert _SPANISH in pages["authored"], (
        f"an authored page must stay typeset in the build's own language; expected {_SPANISH!r}"
    )


def test_without_the_transforms_both_pages_are_typeset_in_the_build_language(tmp_path: Path) -> None:
    """Detector teeth: the same site, unregistered, educates both pages in Spanish."""
    _write_site(tmp_path, register=False)
    pages = _build(tmp_path)
    assert _SPANISH in pages["generated"], (
        "the fixture no longer reproduces the defect the transforms exist for; "
        "an unregistered build must typeset the generator-owned page in the build's language"
    )


def test_the_declared_language_does_not_reach_the_published_markup(tmp_path: Path) -> None:
    """The class the pin adds is taken off again, so the page's markup is unchanged."""
    _write_site(tmp_path, register=True)
    pages = _build(tmp_path)
    assert "language-en" not in pages["generated"], (
        "the class the transform declares the typesetting language with reached the written page"
    )
