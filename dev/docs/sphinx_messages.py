"""Carry Sphinx's own translated words through one compile.

Sphinx and the theme put words of their own on every page: the permalink's
title, the relation links' names, the index page's heading, the navigation's
labels. They come from Sphinx's ``sphinx`` message catalogue, through one
translator object the build language settles, and they reach a page by two
different routes:

- the HTML writer puts some into a finished page itself
  (``add_permalink_ref(node, _('Link to this heading'))``), long after the
  transforms that educate typography have run, so they are plain uneducated
  text (:attr:`~dev.docs.compile_slots.Rendering.PLAIN`);
- the theme's Jinja templates write the rest, unescaped and uneducated like
  every other string a template interpolates
  (:attr:`~dev.docs.compile_slots.Rendering.TEMPLATE`).

One mark cannot serve both, so the two routes are answered by two objects. That
is possible because they reach the translator differently: the Python side
looks it up in ``sphinx.locale.translators`` at every call, and the Jinja
environment captures ``app.translator`` once, while the builder initialises its
templates. Replacing both from ``setup(app)`` -- which runs before that -- gives
each route its own.

A word every language reads the same is not marked. It is one string, which is
what every build writes, and leaving it alone keeps the record to the words
that genuinely differ.

A word with a placeholder is the one case the mark cannot simply stand in for:
its caller fills it, and filling a mark would throw the mark away. So a marked
word remembers each language's string, and the operators that fill one build a
fresh mark from each language's own string filled with the same argument.
"""

from __future__ import annotations

from collections.abc import Sequence
from gettext import NullTranslations, translation
from pathlib import Path
from typing import TYPE_CHECKING, Final, override

from .compile_slots import Rendering, active

if TYPE_CHECKING:
    from sphinx.application import Sphinx

__all__ = ["register"]

#: Sphinx's own message catalogue, and the namespace its page words come from.
_CATALOGUE: Final[str] = "sphinx"
_NAMESPACE: Final[str] = "general"


def _resolved(value: object, language: int) -> object:
    """Return one interpolation argument with every mark inside it read in one language.

    An argument can itself be a mark: the navigation's label takes the title of
    the page it opens, and that title is marked. Such a mark cannot stay inside
    a recorded string while it still names the other languages.
    """
    slots = active()
    if slots is None:
        return value
    if isinstance(value, tuple):
        return tuple(_resolved(item, language) for item in value)
    if isinstance(value, str):
        return slots.resolved(value, language)
    return value


def _marked(strings: Sequence[str], rendering: Rendering) -> str:
    """Return the mark standing for one word in every language, or the word itself."""
    slots = active()
    if slots is None or len(set(strings)) == 1:
        return strings[0]
    return _MarkedMessage(slots.mark(rendering, strings), tuple(strings), rendering)


class _MarkedMessage(str):
    """One word of Sphinx's own as the mark standing for every language's.

    The value is the mark, so wherever a translated word is written as text the
    mark is written and the finishing pass reads it like any other.

    Attributes:
        _strings: What the word reads in every language, in the stored order.
        _rendering: Which writer owns the strings, for a mark built from them.
    """

    _strings: tuple[str, ...]
    _rendering: Rendering

    def __new__(cls, mark: str, strings: tuple[str, ...], rendering: Rendering) -> _MarkedMessage:
        """Return the mark, remembering what it reads in each language."""
        marked = super().__new__(cls, mark)
        marked._strings = strings
        marked._rendering = rendering
        return marked

    @override
    def __reduce__(self) -> tuple[type[_MarkedMessage], tuple[str, tuple[str, ...], Rendering]]:
        """Return what rebuilds this word when the build environment is unpickled.

        Sphinx keeps some of its own words on the environment, and a reader
        process hands its environment back pickled. A string is otherwise
        rebuilt from its value alone, which this word's strings do not survive.
        """
        return (_MarkedMessage, (str(self), self._strings, self._rendering))

    @override
    def __mod__(self, value: object) -> str:
        """Return the mark for each language's word filled with *value*."""
        return _marked(
            [string % _resolved(value, language) for language, string in enumerate(self._strings)],
            self._rendering,
        )

    @override
    def format(self, *args: object, **kwargs: object) -> str:
        """Return the mark for each language's word formatted with the same arguments."""
        return _marked(
            [
                string.format(
                    *(_resolved(value, language) for value in args),
                    **{name: _resolved(value, language) for name, value in kwargs.items()},
                )
                for language, string in enumerate(self._strings)
            ],
            self._rendering,
        )


class _MarkingTranslations(NullTranslations):
    """Answer every lookup with what the word reads in every language at once.

    Each language's own catalogue is consulted, so a word no catalogue
    translates stays the message, exactly as a build of that language leaves it.
    """

    def __init__(self, catalogues: Sequence[NullTranslations], rendering: Rendering) -> None:
        """Answer from one catalogue per language, in the compile's stored order."""
        super().__init__()
        self._catalogues = tuple(catalogues)
        self._rendering = rendering

    @override
    def gettext(self, message: str) -> str:
        """Return the mark for one word in every language."""
        return _marked([catalogue.gettext(message) for catalogue in self._catalogues], self._rendering)

    @override
    def ngettext(self, msgid1: str, msgid2: str, n: int) -> str:
        """Return the mark for one word in every language, in the number's own form."""
        return _marked(
            [catalogue.ngettext(msgid1, msgid2, n) for catalogue in self._catalogues],
            self._rendering,
        )

    @override
    def pgettext(self, context: str, message: str) -> str:
        """Return the mark for one word of one context in every language."""
        return _marked(
            [catalogue.pgettext(context, message) for catalogue in self._catalogues],
            self._rendering,
        )

    @override
    def npgettext(self, context: str, msgid1: str, msgid2: str, n: int) -> str:
        """Return the mark for one word of one context, in the number's own form."""
        return _marked(
            [catalogue.npgettext(context, msgid1, msgid2, n) for catalogue in self._catalogues],
            self._rendering,
        )


def _directories(app: Sphinx) -> list[Path]:
    """Return where Sphinx looks for its own catalogue, in its own order.

    The configured locale directories first, as ``Sphinx._init_i18n`` searches
    them, and the Sphinx package's own last. The system default directory
    Sphinx also consults is left out: a catalogue of Sphinx's own messages
    installed outside the environment would make one compile read what a
    per-language build of the same tree does not.
    """
    from sphinx import package_dir

    return [Path(app.srcdir, directory) for directory in app.config.locale_dirs] + [Path(package_dir, "locale")]


def _catalogue(language: str, directories: Sequence[Path]) -> NullTranslations:
    """Return one language's catalogue of Sphinx's own messages, or an empty one."""
    found: NullTranslations | None = None
    for directory in directories:
        try:
            read = translation(_CATALOGUE, localedir=str(directory), languages=[language])
        except OSError:
            continue
        if found is None:
            found = read
        else:
            found.add_fallback(read)
    return found or NullTranslations()


#: Words of Sphinx's own that are resolved before this module can answer them,
#: by the attribute they are kept on. Sphinx initialises its own translator
#: while the application is constructed, which is BEFORE ``setup(app)`` runs, so
#: a word a module resolves while it is imported is already one language's
#: plain string by the time the translators are replaced. Such a word is
#: therefore marked here, from its own message.
#:
#: The module index's name is the one in this tree: it is not on a page of the
#: user scope at all, and it reaches a root through Sphinx's object inventory,
#: which names every label by its display name.
_FROZEN: Final[tuple[tuple[str, str, str], ...]] = (
    ("sphinx.domains.python", "PythonModuleIndex.localname", "Python Module Index"),
)


def _mark_frozen_words(catalogues: Sequence[NullTranslations]) -> None:
    """Replace each word resolved before this compile could answer it with its mark."""
    from importlib import import_module

    for module_name, attribute, message in _FROZEN:
        owner: object = import_module(module_name)
        *path, name = attribute.split(".")
        for step in path:
            owner = getattr(owner, step)
        setattr(owner, name, _marked([catalogue.gettext(message) for catalogue in catalogues], Rendering.PLAIN))


def register(app: Sphinx) -> None:
    """Answer Sphinx's own words with every language's, for this compile only.

    Called from ``setup(app)``, which runs before the builder initialises its
    templates: that is what lets the words the templates write and the words
    the HTML writer writes be answered by two objects with two renderings.
    Outside the one compile this does nothing and Sphinx keeps its own
    translator untouched.
    """
    from sphinx import locale

    slots = active()
    if slots is None:
        return
    directories = _directories(app)
    catalogues = [_catalogue(language, directories) for language in slots.languages]
    locale.translators[_NAMESPACE, _CATALOGUE] = _MarkingTranslations(catalogues, Rendering.PLAIN)
    app.translator = _MarkingTranslations(catalogues, Rendering.TEMPLATE)
    _mark_frozen_words(catalogues)
