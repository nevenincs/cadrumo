"""The compile's renderers against the writers they imitate.

A mark's strings are recorded before any writer sees them, so the compile has
to write each string the way the writer that owns its position would have: the
docutils HTML writer for a text node and an attribute value, Jinja and
``markupsafe`` for the theme's ``<title>``, BeautifulSoup for the navigation
tree Furo re-serialises, and the docutils smart-quotes transform for the
typography of each language. :mod:`dev.docs.compile_slots` holds a small
renderer per writer, by hand.

The gates that state each position's expected bytes state them by hand, which
is what makes them readable and is also their limit: they say what the writers
do today and nothing about what the writers do. These gates close that: each
renderer is run beside the REAL writer over the same hostile strings, so an
upstream change to any of the four escaping rules fails here rather than
reaching the published roots as a one-character difference inside an attribute.

The typography is the one renderer whose answer depends on the language, so it
is compared against one real Sphinx build carrying the same sentence once per
language, each paragraph declaring its own language the way docutils reads it.
"""

from __future__ import annotations

import re
from io import StringIO
from typing import Final

import pytest
from bs4 import BeautifulSoup, NavigableString
from bs4.formatter import HTMLFormatter
from docutils.frontend import get_default_settings
from docutils.utils import new_document
from docutils.writers.html5_polyglot import HTMLTranslator, Writer
from jinja2.filters import do_striptags
from markupsafe import escape
from sphinx.application import Sphinx

from cadrumo.core.external_constants import OutputLanguage

from ..compile_slots import (
    _docutils_attribute,
    _docutils_text,
    _educated,
    _jinja,
    _minimal,
    _resouped,
    _template_title,
    plain_text,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

#: Strings chosen for what each writer treats differently: the five characters
#: docutils replaces, the two Jinja writes as numeric references and docutils
#: does not, the at-sign only docutils touches, text that already looks escaped,
#: whitespace runs an attribute value folds, and non-ASCII that none of them
#: may touch at all.
_HOSTILE: Final[tuple[str, ...]] = (
    "",
    "Ley 37/1992",
    "& < > \" ' @",
    "A & B < C > D",
    'say "yes", or don\'t',
    "soporte@example.test",
    "&amp; &#64; &lt; &quot;",
    "a\nb\tc\r\nd  e   f",
    "  leading and trailing  ",
    "«Façana» — àáéíóú ñ ő ű",
    "<script>alert('x')</script>",
)

#: Rendered stretches for the two renderers that read markup rather than text:
#: plain text, text that was escaped by the writer whose output they are handed,
#: and a message carrying inline markup.
_RENDERED: Final[tuple[str, ...]] = (
    "Ley 37/1992",
    "A &amp; B &lt; C &gt; D",
    "write to soporte&#64;example.test",
    '<em>Ley 37/1992</em> and <code class="docutils literal">&quot;aeat&quot;</code>',
    "a  run   of &amp; spaces",
)


@pytest.fixture(scope="module")
def writer() -> HTMLTranslator:
    """The real docutils HTML writer, over an empty document.

    Its escaping methods read the writer's own substitution table and its
    settings, so they are asked of a real instance rather than of a table
    copied out of it.
    """
    return HTMLTranslator(new_document("renderer-writers", get_default_settings(Writer)))


@pytest.mark.parametrize("value", _HOSTILE)
def test_the_text_renderer_escapes_as_the_docutils_writer_does(value: str, writer: HTMLTranslator) -> None:
    """A string recorded for a text node is written as the writer would have written it."""
    assert _docutils_text(value) == writer.encode(value)


@pytest.mark.parametrize("value", _HOSTILE)
def test_the_attribute_renderer_escapes_and_folds_as_the_docutils_writer_does(
    value: str, writer: HTMLTranslator
) -> None:
    """An attribute value folds its whitespace as well as escaping, which the writer owns."""
    assert _docutils_attribute(value) == writer.attval(value)


@pytest.mark.parametrize("value", _HOSTILE)
def test_the_template_renderer_escapes_as_markupsafe_does(value: str) -> None:
    """A string a Jinja template escapes is written as ``markupsafe`` escapes it.

    This is the renderer the apostrophe distinguishes: docutils leaves it,
    ``markupsafe`` writes ``&#39;``, and nothing in the surrounding markup says
    which of the two wrote the string.
    """
    assert _jinja(value) == str(escape(value))


@pytest.mark.parametrize("markup", _RENDERED)
def test_the_title_renderer_strips_and_escapes_as_the_template_does(markup: str) -> None:
    """The theme is handed the title as markup and writes ``striptags`` then ``escape``.

    Both halves run here: the module derives the plain form from the rendering
    (:func:`~dev.docs.compile_slots.plain_text`) and writes it for the
    ``<title>``, and the two filters the template composes do the same.
    """
    assert _template_title(plain_text(markup)) == str(escape(do_striptags(markup)))


@pytest.mark.parametrize("value", _HOSTILE)
def test_the_minimal_renderer_substitutes_as_beautiful_soup_does(value: str) -> None:
    """The navigation's strings are escaped by the formatter ``str(soup)`` uses.

    Asked of the formatter BeautifulSoup looks up for a minimally escaped
    serialisation, not of a reading of what that formatter does.
    """
    minimal = HTMLFormatter.REGISTRY["minimal"]
    assert _minimal(value) == minimal.substitute(NavigableString(value))


@pytest.mark.parametrize("markup", _RENDERED)
def test_the_navigation_renderer_is_beautiful_soup_re_serialising_the_markup(markup: str) -> None:
    """Furo hands the writer's toctree to BeautifulSoup and writes ``str(soup)`` back."""
    assert _resouped(markup) == str(BeautifulSoup(markup, "html.parser"))


@pytest.mark.parametrize("value", _HOSTILE)
def test_re_serialising_the_writers_escaping_leaves_the_minimal_escaping(value: str, writer: HTMLTranslator) -> None:
    """The navigation carries the writer's own output, parsed and escaped again.

    This is the claim that makes the navigation position answerable at all: what
    the theme publishes for a plain string is the minimally escaped string,
    whatever the writer escaped on the way in. The three renderers are composed
    here as the compile composes them, over the real writer's output.
    """
    assert _resouped(writer.encode(value)) == _minimal(value)


#: One sentence carrying what the smart-quotes transform educates -- single and
#: double quotation marks, an apostrophe, a dash pair and an ellipsis -- and
#: nothing the HTML writer escapes, so a built paragraph's own markup is the
#: educated string and nothing else.
_TYPESET: Final[str] = "L'IVA d'enguany -- 'aixo' i \"allo\" ... fi"

#: One educated paragraph of the built page. The ``language-<tag>`` class a
#: block declares its language with reaches the written page as the ``lang``
#: attribute, which is how the writer publishes it.
_PARAGRAPH: Final[re.Pattern[str]] = re.compile(r'<p lang="([a-z]+)">(.*?)</p>', re.DOTALL)


@pytest.fixture(scope="module")
def typeset(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    """Return what one real Sphinx build typeset the same sentence to, per language.

    One build carrying one paragraph per language, each declaring its own
    language through the ``language-<tag>`` class docutils reads a text block's
    language from. That is the mechanism a generator-owned page is pinned with
    (:mod:`dev.docs.untranslated_typesetting`), used here to put four languages'
    education in one build rather than four.
    """
    root = tmp_path_factory.mktemp("typesetting")
    # ``rst-class`` and not ``class``: Sphinx gives the name ``class`` to the
    # Python domain's own directive, which would declare a class named
    # ``language-ca`` instead of classing the paragraph below it.
    blocks = "\n".join(f".. rst-class:: language-{member.value}\n\n{_TYPESET}\n" for member in OutputLanguage)
    (root / "conf.py").write_text('html_theme = "basic"\nsmartquotes = True\n', encoding="utf-8")
    (root / "index.rst").write_text(f"=====\nTitle\n=====\n\n{blocks}", encoding="utf-8")
    application = Sphinx(
        srcdir=str(root),
        confdir=str(root),
        outdir=str(root / "_out"),
        doctreedir=str(root / "_doctrees"),
        buildername="html",
        warning=StringIO(),
        freshenv=True,
    )
    application.build()
    page = (root / "_out" / "index.html").read_text(encoding="utf-8")
    return {language: educated for language, educated in _PARAGRAPH.findall(page)}


@pytest.mark.parametrize("language", [member.value for member in OutputLanguage])
def test_the_typography_renderer_educates_as_a_build_of_that_language_does(
    language: str, typeset: dict[str, str]
) -> None:
    """Each language's own quotation marks, dashes and ellipsis, from the real transform.

    A mark holds no quotation mark for the transform to find, so every recorded
    string is educated here instead -- in its own language, which is what a
    build of that language would have done to the same text block.
    """
    assert language in typeset, f"the build typeset no paragraph for {language}: {sorted(typeset)}"
    assert _educated(_TYPESET, language) == typeset[language]


def test_the_languages_are_not_all_typeset_alike(typeset: dict[str, str]) -> None:
    """Detector teeth: the comparison above says nothing if every language reads the same.

    The quotation marks are what differ: Catalan and Spanish open a quoted
    phrase with a guillemet where English opens it with a curly quote, which is
    the difference that cost the first measured compile 1,847 of its reported
    differences in one language alone.
    """
    assert len(set(typeset.values())) > 1, f"every language typeset the sentence identically: {typeset}"
