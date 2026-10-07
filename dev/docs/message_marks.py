"""Carry every language's translation of an authored page through one compile.

The authored pages are translated through gettext: one catalogue per source
page under ``docs/locales/<language>/LC_MESSAGES``. A build selects one
language, and Sphinx's own ``Locale`` transform substitutes that language's
translation for each translatable message. That is one build per language,
which is exactly what the one compile exists to stop.

So this module puts a mark where the translation goes and records every
language's translation beside it, using the same transform rather than
replacing it:

1. A catalogue is generated for the language the compile builds in, whose
   translation of each message is that message's mark. Sphinx substitutes it
   like any other translation, so the mark reaches the page title, the
   navigation, the ``<title>`` element, the breadcrumbs and the body through
   the mechanisms the pages already use, and nothing in Sphinx is patched.
2. A translation is not a string but markup: it carries inline markup, links
   and roles, and a role resolves against the page it stands on. So each
   authored page gets a *fragment document* beside it -- same directory, same
   file type, so every relative reference resolves exactly as it does on the
   page -- holding every language's translation of each of that page's
   messages as its own paragraph between markers. The one compile renders
   those documents with the pages, and what each paragraph rendered to is read
   back as that language's string for the message's mark. English is a
   language like the others: its string is the rendered source message.

A fragment document is build scaffolding, so its output is deleted once it has
been read: nothing a reader is served, no navigation entry, no search record.

A generated page has no catalogue, and its chrome is markup for the same
reason a translation is: a chrome string carries inline markup, links and
roles that resolve against the page it stands on. Such a string reaches the
same fragment documents from the other side -- the generator reserves its mark
while writing the page and leaves the strings for :func:`prepare`
(:func:`rendered_markup`) -- so one mechanism renders both, and a generated
page's chrome is rendered where it stands rather than reaching a reader as raw
RST.

What this costs per added language is the rendering of its text: one more
catalogue read, one more paragraph per message in the fragment documents, and
one more string per mark. The pages themselves are read and written once no
matter how many languages the compile carries.
"""

from __future__ import annotations

import bisect
import re
from collections.abc import Callable, Collection, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, cast, override

from sphinx.transforms import SphinxTransform
from sphinx.transforms.post_transforms import SphinxPostTransform

from .compile_slots import (
    BLOCK_CLOSE,
    BLOCK_MID,
    BLOCK_OPEN,
    MARK,
    MARK_CLOSE,
    MARK_OPEN,
    CompileSlots,
    Rendering,
    mark_number,
    plain_text,
)

#: The delimiters of one rendered translation inside a fragment document, in
#: the order a block writes them. The characters themselves are declared in
#: :mod:`dev.docs.compile_slots`, beside the mark's own, so one registry names
#: every private-use character the compile reserves and a composed root can be
#: refused for carrying any of them.
_BLOCK: Final[tuple[str, str, str]] = (BLOCK_OPEN, BLOCK_MID, BLOCK_CLOSE)

#: One rendered translation inside a fragment document's written page: the
#: block's number, then what the paragraph rendered its translation to.
_RENDERED: Final[re.Pattern[str]] = re.compile(f"{BLOCK_OPEN}([0-9a-f]+){BLOCK_MID}(.*?){BLOCK_CLOSE}", re.DOTALL)
#: One block's own number, read from the source paragraph a transform is given.
_DECLARED: Final[re.Pattern[str]] = re.compile(f"^{BLOCK_OPEN}([0-9a-f]+){BLOCK_MID}")

#: Where a generated pseudo-catalogue is written inside the source tree being
#: compiled, kept out of ``locales`` so an authored catalogue and a generated
#: one are never in the same place.
PSEUDO_LOCALE_DIR: Final[str] = "_compile_locales"

#: What a fragment document's filename starts with, inside the directory of
#: the page it carries the translations of.
FRAGMENT_PREFIX: Final[str] = "_compile_messages."

#: Sphinx's own declaration that a translation drops references its source
#: had. Every reference a message carries moves into the recorded strings, so
#: the mark that replaces it genuinely carries none and says so the way Sphinx
#: provides for, rather than by silencing the warning for every message.
_NOQA: Final[str] = "#noqa"

_UTF_8: Final[str] = "utf-8"


class MessageMarksError(RuntimeError):
    """A page's messages cannot be marked, or a rendering cannot be read back."""


@dataclass(frozen=True)
class _Block:
    """One language's translation of one message, as the fragment carries it.

    Attributes:
        mark: The reserved mark the translation is a string of.
        language: The language's index in the compile's language order.
        source: The translation as the fragment document's paragraph holds it.
    """

    mark: str
    language: int
    source: str


# ── What the read phase notes, where a forked worker's note survives ─────────
# Sphinx reads documents in forked worker processes on Linux, pickles each
# worker's environment back and merges it. A note a transform leaves anywhere
# else is lost there, silently: the compile would simply not know that a
# heading's translation is dropped in Hungarian. So the read phase's notes are
# attributes of the environment, merged with the environment they were made in
# and dropped with the document they are about.
_NOTES: Final[str] = "cadrumo_message_mark_notes"


@dataclass
class DocumentNotes:
    """What reading one document told the compile about its marks.

    Attributes:
        titles: The marks the document carries as a toctree entry title or a
            toctree caption.
        dropped: For each marked heading, the languages whose own build keeps
            the source message because Sphinx drops their translation.
    """

    titles: set[str] = field(default_factory=set)
    dropped: dict[str, set[int]] = field(default_factory=dict)


def _notes(env: object) -> dict[str, DocumentNotes]:
    """Return one environment's notes by document, starting them if it carries none."""
    found = getattr(env, _NOTES, None)
    if isinstance(found, dict):
        return cast(dict[str, DocumentNotes], found)
    started: dict[str, DocumentNotes] = {}
    setattr(env, _NOTES, started)
    return started


def notes_for(env: object, docname: str) -> DocumentNotes:
    """Return one document's notes on this build's environment, starting them if new."""
    return _notes(env).setdefault(docname, DocumentNotes())


def purge_notes(app: object, env: object, docname: str) -> None:
    """Drop one document's notes, because the document is about to be read again.

    Args:
        app: The Sphinx application (unused).
        env: The build environment.
        docname: The document being re-read.
    """
    _notes(env).pop(docname, None)


def merge_notes(app: object, env: object, docnames: Iterable[str], other: object) -> None:
    """Take the notes a worker process made while reading its own documents.

    Args:
        app: The Sphinx application (unused).
        env: This process's build environment.
        docnames: The documents the other environment read.
        other: The environment the worker pickled back.
    """
    theirs = _notes(other)
    if not theirs:
        return
    notes = _notes(env)
    for docname in docnames:
        found = theirs.get(docname)
        if found is not None:
            notes[docname] = found


def collect_notes(env: object, plan: MessagePlan) -> None:
    """Fold every read document's notes into the plan, which spans the whole compile.

    The notes are per document because that is the unit a read is parallel in
    and the unit a re-read invalidates. What they say is about a mark, and a
    mark is one string wherever the pages carry it, so they are folded here --
    once, in the process that reads the renderings back.

    Args:
        env: The build environment the read phase left its notes on.
        plan: The plan to fold them into.
    """
    for notes in _notes(env).values():
        plan.titles.update(notes.titles)
        for mark, languages in notes.dropped.items():
            plan.dropped.setdefault(mark, set()).update(languages)


@dataclass
class _Pending:
    """What a generator asked to have rendered on one of its pages.

    Attributes:
        blocks: Each reserved mark and the string it stands for in every
            language, in the order the generator asked for them.
        marks: The mark already reserved for one set of strings, so a string a
            page carries many times is rendered once.
    """

    blocks: list[tuple[str, tuple[str, ...]]] = field(default_factory=list)
    marks: dict[tuple[str, ...], str] = field(default_factory=dict)


# ── What the generators asked for, between their hook and this one ───────────
# A generated page has no catalogue, so a chrome string that is markup cannot
# reach a mark through Sphinx's own Locale transform. The generator reserves the
# mark where it writes the page and leaves the strings here; :func:`prepare`
# runs later in the same hook and renders them through the same fragment
# documents the authored pages use. Both run in the main process before the read
# phase, which is why a module-level record is enough to carry them.
_PENDING: dict[str, _Pending] = {}


def rendered_markup(slots: CompileSlots, docname: str, sources: Sequence[str]) -> str:
    """Reserve a mark standing for *sources* rendered on the page *docname*.

    Args:
        slots: The compile's mark record, which the mark is reserved in.
        docname: The page the strings stand on, whose directory the fragment
            document is written into so every relative reference resolves as
            it does on the page itself.
        sources: One language's markup per language, in the stored order.

    Returns:
        The mark to write in place of the language's markup.

    Raises:
        MessageMarksError: If a string is given for the wrong number of
            languages.
    """
    if len(sources) != len(slots.languages):
        raise MessageMarksError(
            f"markup on {docname} needs one string per language; got {len(sources)} for {len(slots.languages)}"
        )
    strings = tuple(sources)
    pending = _PENDING.setdefault(docname, _Pending())
    mark = pending.marks.get(strings)
    if mark is None:
        mark = pending.marks[strings] = slots.reserve(Rendering.MESSAGE)
        pending.blocks.append((mark, strings))
    return mark


@dataclass
class MessagePlan:
    """What one compile marks, renders and reads back.

    Attributes:
        languages: The languages the compile carries, in the stored order.
        blocks: Every block written into a fragment document, by its number.
        fragments: The fragment documents written, as docnames.
        pages: The authored pages whose messages were marked.
        titles: The marks a read document carries as a toctree title, which
            :class:`NoteToctreeTitleMarks` fills and :func:`harvest` records
            uneducated.
        source_language: The language the messages are authored in, whose
            string a language reads where its own translation is dropped.
        dropped: For each marked heading, the languages whose own build keeps
            the source message because Sphinx drops their translation of it,
            which :class:`NoteDroppedHeadingTranslations` fills.
        anchors: For each page, the identifiers its own links to its own
            headings reach, which :class:`ResolveOwnPageAnchors` fills and
            :func:`harvest` unwraps.
        messages: Marks reserved, one per marked message.
    """

    languages: tuple[str, ...]
    source_language: str = ""
    blocks: list[_Block] = field(default_factory=list)
    fragments: list[str] = field(default_factory=list)
    pages: list[str] = field(default_factory=list)
    titles: set[str] = field(default_factory=set)
    dropped: dict[str, set[int]] = field(default_factory=dict)
    anchors: dict[str, set[str]] = field(default_factory=dict)

    @property
    def messages(self) -> int:
        """How many messages the plan reserved a mark for."""
        return len(self.blocks) // len(self.languages) if self.languages else 0

    def language_of(self, number: str) -> str | None:
        """Return the language tag one block's number declares, if it is a block of this plan."""
        index = int(number, 16)
        if index >= len(self.blocks):
            return None
        return self.languages[self.blocks[index].language]

    def owner_of(self, docname: str) -> str | None:
        """Return the page whose translations one fragment document carries, if it is one."""
        try:
            return self.pages[self.fragments.index(docname)]
        except ValueError:
            return None

    def sources_of(self, mark: str) -> list[str]:
        """Return one mark's translation in every language as its catalogue holds it.

        This is the string itself rather than what rendering it produced, which
        is what a toctree title reaches the page as: the title is an attribute
        of the toctree node, so nothing parsed it as markup and nothing
        educated it.
        """
        strings = [""] * len(self.languages)
        for block in self.blocks:
            if block.mark == mark:
                strings[block.language] = _one_line(block.source)
        return strings


# ── The compile's one active plan ────────────────────────────────────────────
# The transform that tells each fragment paragraph which language it holds runs
# inside Sphinx's read phase, where no argument of ours reaches it. One active
# plan, set for the compile and cleared after it, is how it gets there.
_ACTIVE: MessagePlan | None = None


def active() -> MessagePlan | None:
    """Return this compile's message plan, or None outside a multilingual compile."""
    return _ACTIVE


def _read_catalogue(path: Path) -> tuple[dict[str, str], dict[str, tuple[tuple[str, int], ...]]]:
    """Return one gettext catalogue's usable translations and where each was extracted.

    The locations are the catalogue's own ``#:`` references, which is how the
    source language's string is recovered from the right occurrence of a message
    in the page's own source (:meth:`_SourceText.unfolded`).
    """
    from babel.messages.pofile import read_po

    with path.open("rb") as stream:
        catalogue = read_po(stream)
    translations: dict[str, str] = {}
    locations: dict[str, tuple[tuple[str, int], ...]] = {}
    for message in catalogue:
        if not isinstance(message.id, str) or not message.id:
            continue
        if message.fuzzy:
            # A build compiles its catalogues without the fuzzy entries, so a
            # fuzzy translation reaches no page of that language's own build and
            # must reach no recorded string either. Left out, the message is
            # untranslated here exactly as it is there.
            continue
        string = message.string
        if isinstance(string, str) and string:
            translations[message.id] = string
            # A reference with no line of its own says nothing about where the
            # message stands, so it is not kept: ``line`` is zero or absent for
            # an entry an extractor could not place.
            locations[message.id] = tuple((str(filename), line) for filename, line in message.locations if line)
    return translations, locations


def _one_line(value: str) -> str:
    """Return one translation as a single paragraph line.

    A build of the language substitutes the translation as the catalogue holds
    it, one line, so the fragment holds one line too: a line break the
    catalogue happens to carry would reach the page where that build's page has
    a space.
    """
    return " ".join(value.split())


#: A link to a heading of the page the translation stands on, as resolving it
#: from another document writes it: the title wrapped in the classes a
#: cross-document reference carries. The page's own link to its own heading
#: carries the text as it was written and no wrapper, so the wrapper the move
#: added comes back off -- for those anchors and no others, because the same
#: markup is what a translation's own cross-reference legitimately produces.
#: Dotted, because a link's text wraps across lines exactly as its page does.
_OWN_PAGE_TITLE: Final[re.Pattern[str]] = re.compile(
    r'(<a\b[^>]*href="#([^"]*)"[^>]*>)<span class="std std-ref">(.*?)</span>(</a>)', re.DOTALL
)


def _unwrapped(markup: str, anchors: Collection[str]) -> str:
    """Return one rendering with the wrapper a link to one of *anchors* gained taken off."""

    def unwrap(found: re.Match[str]) -> str:
        if found.group(2) not in anchors:
            return found.group()
        return f"{found.group(1)}{found.group(3)}{found.group(4)}"

    return _OWN_PAGE_TITLE.sub(unwrap, markup)


#: One run of whitespace, which is what a message and its own source differ by.
_WHITESPACE: Final[re.Pattern[str]] = re.compile(r"\s+")


def _folded(value: str) -> str:
    """Return one stretch of source with every run of whitespace folded to a space."""
    return _WHITESPACE.sub(" ", value).strip()


class _SourceText:
    """One authored page's source, searchable by a message extracted from it.

    Sphinx extracts a message with the line breaks of its own source folded
    into spaces, and a build of the language the messages are authored in never
    consults a catalogue, so that language's page keeps those line breaks. The
    one compile reaches the page through the catalogue like every other
    language, so the source language's string has to carry the line breaks
    back, or every wrapped paragraph of the authored pages differs from its own
    build by whitespace alone.

    They are recovered rather than remembered: the message is looked up in the
    source with the whitespace of both folded, and the stretch it was folded
    from is read back out. A message not found whole is left folded, which is
    what happens to one whose source a directive or a role rewrote.
    """

    def __init__(self, text: str) -> None:
        """Index one source file by where each character of its folded form came from."""
        self._folded: list[str] = []
        self._offsets: list[int] = []
        self._line_starts: list[int] = [0]
        previous_space = True
        for offset, character in enumerate(text):
            if character == "\n":
                self._line_starts.append(offset + 1)
            space = character.isspace()
            if space and previous_space:
                continue
            self._folded.append(" " if space else character)
            self._offsets.append(offset)
            previous_space = space
        self._text = text
        self._joined = "".join(self._folded)

    def unfolded(self, message: str, line: int) -> str:
        """Return the source *message* was folded from, its lines left undented.

        A continuation line's indentation is not part of the text the parser
        builds -- the page carries the line break and nothing else -- so the
        recovered stretch carries the same.

        ``line`` is the source line the catalogue says the message was
        extracted from, and it is what tells one occurrence of the same words
        from another. A link written as a list item of its own is also written
        inside a paragraph a few lines above it, and the paragraph wraps where
        the list item does not: looking the shorter message up from the top of
        the file recovers the line break of the longer one's occurrence and
        publishes a break the list item's own build has nowhere. So the search
        starts at the message's own line.

        A catalogue does not place every message: a table cell is referenced by
        its file alone. There the stretch stands only where every occurrence in
        the file was folded from the same one, because nothing says which of
        them this message is and one recorded string cannot be two.

        Args:
            message: The message, as the catalogue holds it.
            line: The 1-based source line it was extracted from, or 1 where the
                catalogue does not place it.

        Returns:
            The stretch of source it was folded from, or the message itself
            where that stretch cannot be identified.
        """
        folded = _folded(message)
        if not folded:
            return message
        if line > 1:
            at = self._joined.find(folded, self._folded_index(line))
            if at >= 0 and _folded(stretch := self._stretch(folded, at)) == folded:
                return stretch
        agreed = {stretch for stretch in self._occurrences(folded) if _folded(stretch) == folded}
        return agreed.pop() if len(agreed) == 1 else message

    def _occurrences(self, folded: str) -> Iterator[str]:
        """Yield the stretch of source behind every occurrence of *folded*."""
        at = self._joined.find(folded)
        while at >= 0:
            yield self._stretch(folded, at)
            at = self._joined.find(folded, at + 1)

    def _stretch(self, folded: str, at: int) -> str:
        """Return the source behind the occurrence of *folded* at *at*, its lines undented."""
        span = self._text[self._offsets[at] : self._offsets[at + len(folded) - 1] + 1]
        return "\n".join(piece.strip() for piece in span.splitlines())

    def _folded_index(self, line: int) -> int:
        """Return where in the folded form the 1-based source *line* begins."""
        if line <= 1:
            return 0
        return bisect.bisect_left(self._offsets, self._line_starts[min(line, len(self._line_starts)) - 1])


def _fragment_source(suffix: str, blocks: Iterable[tuple[int, _Block]]) -> str:
    """Return a fragment document's source, declared an orphan in its own file type.

    The document is never linked from anything, so it says so itself: without
    that, every fragment is a page Sphinx reports as missing from every
    toctree, and the report would be right.
    """
    orphan = "---\norphan: true\n---\n" if suffix == ".md" else ":orphan:\n"
    paragraphs = [
        # The spaces are not decoration. A translation beginning or ending in
        # inline markup needs whitespace outside it for the markup to be
        # recognised, and a private-use character is not whitespace.
        f"{BLOCK_OPEN}{index:x}{BLOCK_MID} {block.source} {BLOCK_CLOSE}"
        for index, block in blocks
    ]
    return orphan + "\n" + "\n\n".join(paragraphs) + "\n"


def fragment_docname(docname: str) -> str:
    """Return the docname of the fragment document carrying one page's translations."""
    page = docname.rpartition("/")
    return f"{page[0]}/{FRAGMENT_PREFIX}{page[2]}" if page[0] else f"{FRAGMENT_PREFIX}{docname}"


@dataclass(frozen=True)
class _Catalogues:
    """One page's catalogues, and where the messages they share were extracted.

    Attributes:
        by_language: Each language's translations, the language the messages are
            authored in excepted: it carries no catalogue, so its translation of
            a message is the message.
        locations: For each message, the source references the first catalogue
            read carries for it.
    """

    by_language: dict[str, dict[str, str]]
    locations: dict[str, tuple[tuple[str, int], ...]]


def _catalogues(locales: Path, domain: str, languages: Sequence[str], source: str) -> _Catalogues | None:
    """Return the catalogues for one page, or None if no language carries one."""
    found: dict[str, dict[str, str]] = {}
    locations: dict[str, tuple[tuple[str, int], ...]] = {}
    for language in languages:
        if language == source:
            continue
        path = locales / language / "LC_MESSAGES" / f"{domain}.po"
        if path.is_file():
            found[language], read = _read_catalogue(path)
            locations = locations or read
    return _Catalogues(by_language=found, locations=locations) if found else None


def _extracted_from(locations: Sequence[tuple[str, int]], source: Path) -> int:
    """Return the line of *source* a message was extracted from, or its first line.

    A catalogue reference names the file it was extracted from as well as the
    line, and a message a page includes from elsewhere is extracted from that
    other file: its line says nothing about this source, so the whole file is
    searched instead.
    """
    for filename, line in locations:
        if Path(filename).name == source.name:
            return line
    return 1


def prepare(
    srcdir: Path,
    *,
    slots: CompileSlots,
    docnames: Iterable[str],
    doc2path: Callable[[str], Path],
    source_language: str,
    compact: bool | str,
) -> MessagePlan:
    """Mark every authored page's messages and write what renders their translations.

    A page the generators asked to have markup rendered on
    (:func:`rendered_markup`) gets a fragment document too, carrying their
    strings beside any its catalogues supplied.

    Args:
        srcdir: The source tree this compile reads, which the generated
            catalogue and the fragment documents are written into.
        slots: The compile's mark record, which the marks are reserved in.
        docnames: The documents this compile will read.
        doc2path: One document's source path, for its file type and directory.
        source_language: The language the messages are authored in, which
            carries no catalogue.
        compact: Sphinx's ``gettext_compact``, which decides a page's domain.

    Returns:
        The plan, which :func:`harvest` reads the renderings back with.

    Raises:
        MessageMarksError: If a translation contains a character reserved for
            a mark or a block delimiter, or if markup was asked to be rendered
            on a page this build does not read.
    """
    from sphinx.util.i18n import docname_to_domain

    global _ACTIVE
    plan = MessagePlan(languages=slots.languages, source_language=source_language)
    locales = srcdir / "locales"
    pseudo = srcdir / PSEUDO_LOCALE_DIR / source_language / "LC_MESSAGES"
    pending = dict(_PENDING)
    _PENDING.clear()
    for docname in sorted(docnames):
        domain = docname_to_domain(docname, compact)
        catalogues = _catalogues(locales, domain, plan.languages, source_language)
        asked = pending.pop(docname, None)
        if catalogues is None and asked is None:
            continue
        marked: dict[str, str] = {}
        blocks: list[tuple[int, _Block]] = []
        source = doc2path(docname)
        if catalogues is not None:
            authored = _SourceText(source.read_text(encoding=_UTF_8))
            for message in next(iter(catalogues.by_language.values())):
                line = _extracted_from(catalogues.locations.get(message, ()), source)
                authored_source = authored.unfolded(message, line)
                # A message a language has not translated reaches that language's
                # own page as the message itself, line breaks and all -- and that
                # build still typesets it in its own language, educating its
                # quotation marks, dashes and ellipses the way it educates every
                # other text block. So the string recorded for such a language is
                # the recovered source rather than nothing: left out, the message
                # would reach the composed page as the compile's own language
                # typeset it, which is a different page for every language whose
                # quotation marks differ.
                translations = [
                    authored_source
                    if language == source_language
                    else _one_line(catalogues.by_language[language].get(message, "")) or authored_source
                    for language in plan.languages
                ]
                _refuse_reserved(docname, translations)
                mark = slots.reserve(Rendering.MESSAGE)
                marked[message] = f"{mark}{_NOQA}"
                _add_blocks(plan, blocks, mark, translations)
        if asked is not None:
            for mark, strings in asked.blocks:
                _refuse_reserved(docname, strings)
                _add_blocks(plan, blocks, mark, [_one_line(string) for string in strings])
        if not blocks:
            continue
        if marked:
            _write_pseudo_catalogue(pseudo / f"{domain}.mo", marked)
        fragment = source.with_name(f"{FRAGMENT_PREFIX}{source.name}")
        fragment.write_text(_fragment_source(source.suffix, blocks), encoding=_UTF_8)
        plan.fragments.append(fragment_docname(docname))
        plan.pages.append(docname)
    if pending:
        raise MessageMarksError(
            f"markup was asked to be rendered on {len(pending)} page(s) this build does not read, "
            f"first {sorted(pending)[0]!r}; nothing would render their marks"
        )
    _ACTIVE = plan
    return plan


#: The characters a recorded string may not contain, and what each delimits.
_RESERVED: Final[tuple[tuple[str, str], ...]] = (
    (MARK_OPEN, "a mark"),
    (MARK_CLOSE, "a mark"),
    *((character, "a block") for character in _BLOCK),
)


def _refuse_reserved(docname: str, strings: Iterable[str]) -> None:
    """Refuse a string carrying a character this module's own artefacts are delimited by.

    Raises:
        MessageMarksError: If one of *strings* contains such a character.
    """
    for string in strings:
        for character, kind in _RESERVED:
            if character in string:
                raise MessageMarksError(
                    f"the string {string[:60]!r} of {docname} contains a character reserved for {kind} delimiter"
                )


def _add_blocks(plan: MessagePlan, blocks: list[tuple[int, _Block]], mark: str, strings: Sequence[str]) -> None:
    """Record one mark's string in every language as a block of its page's fragment."""
    for index, string in enumerate(strings):
        blocks.append((len(plan.blocks), _Block(mark, index, string)))
        plan.blocks.append(blocks[-1][1])


def _write_pseudo_catalogue(path: Path, translations: Mapping[str, str]) -> None:
    """Write the catalogue whose translation of each message is that message's mark."""
    from babel.messages.catalog import Catalog
    from babel.messages.mofile import write_mo

    catalogue = Catalog(charset=_UTF_8)
    for message, mark in translations.items():
        catalogue.add(message, mark)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as stream:
        write_mo(stream, catalogue)


def _without_marks(
    owner: str,
    markup: str,
    language: int,
    rendered: Mapping[str, Sequence[str | None]],
    slots: CompileSlots,
    seen: frozenset[str] = frozenset(),
) -> str:
    """Return one rendered translation with every mark inside it read in one language.

    A rendered translation can carry marks of its own: a reference to another
    page with no explicit title renders that page's title, and a glossary
    reference renders the term, and both of those are themselves marked. Such a
    mark cannot be stored inside a language's string while it still names the
    other languages, so it is read here -- against the other messages of this
    same compile where it is one of them, and against the marks already
    recorded where it is not.

    Raises:
        MessageMarksError: If a translation's marks refer back to it, which no
            composition could resolve.
    """
    if MARK_OPEN not in markup:
        return markup
    if owner in seen:
        raise MessageMarksError(f"a rendered translation refers to itself through {len(seen)} other(s)")

    def read(found: re.Match[str]) -> str:
        mark = found.group()
        nested = rendered.get(mark)
        if nested is None:
            return slots.strings(mark_number(mark))[1][language]
        return _without_marks(mark, nested[language] or "", language, rendered, slots, seen | {owner})

    return MARK.sub(read, markup)


def harvest(plan: MessagePlan, slots: CompileSlots, page_path: Callable[[str], Path]) -> int:
    """Read every rendered translation back and record it, then drop the fragments.

    Args:
        plan: What :func:`prepare` wrote.
        slots: The compile's mark record, whose reserved marks are supplied.
        page_path: One docname's written page.

    Returns:
        How many messages were supplied.

    Raises:
        MessageMarksError: If a fragment document was not written, or a block
            it declared did not render.
    """
    global _ACTIVE
    rendered: dict[str, list[str | None]] = {}
    for docname, owner in zip(plan.fragments, plan.pages, strict=True):
        page = page_path(docname)
        if not page.is_file():
            raise MessageMarksError(f"the compile wrote no fragment document for {docname} at {page}")
        # A reference to the owning page's own targets resolves from the
        # fragment as a reference to another document, because that is what the
        # fragment is; on the page it is a reference within one. The fragment
        # stands in the page's own directory, so the one difference the move
        # makes to a resolved link is the page's own filename in front of the
        # anchor, which is taken back off here, and -- for a link to one of the
        # page's own headings -- the title wrapper a cross-document reference
        # carries (:class:`ResolveOwnPageAnchors`).
        own = f'href="{page_path(owner).name}#'
        anchors = plan.anchors.get(owner, frozenset())
        for found in _RENDERED.finditer(page.read_text(encoding=_UTF_8)):
            block = plan.blocks[int(found.group(1), 16)]
            # The paragraph's own spaces around the translation are the ones
            # that let its outermost inline markup be recognised; exactly one
            # of each is given back.
            # A recorded string stands in a page stored without the terminators
            # of the platform that wrote it, which is the form reading the
            # fragment back through universal newlines already leaves.
            markup = _unwrapped(
                found.group(2).removeprefix(" ").removesuffix(" ").replace(own, 'href="#'),
                anchors,
            )
            strings = rendered.setdefault(block.mark, [None] * len(plan.languages))
            strings[block.language] = markup
        page.unlink()
    incomplete = [(mark, plan.languages[strings.index(None)]) for mark, strings in rendered.items() if None in strings]
    absent = sorted({block.mark for block in plan.blocks} - set(rendered))
    if incomplete or absent:
        raise MessageMarksError(
            f"{len(incomplete)} marked message(s) did not render in every language "
            f"(first {incomplete[:2]}) and {len(absent)} did not render at all "
            f"(first {absent[:2]}); the fragment documents did not carry what was marked"
        )
    # A heading whose translation Sphinx drops reaches that language's own page
    # in the source language, so that is what the mark reads there: the source
    # language's own rendering, which the same fragment already produced.
    source = plan.languages.index(plan.source_language) if plan.source_language in plan.languages else -1
    if source >= 0:
        for mark, languages in plan.dropped.items():
            strings = rendered.get(mark)
            if strings is None:
                continue
            for language in languages:
                strings[language] = strings[source]
    # A toctree title is the catalogue's own string, so the rendering the
    # fragment produced for it is not what any page carries. They are recorded
    # first, so a translation that names one reads the recorded string rather
    # than the rendering that stands for nothing.
    supplied = len(rendered)
    for mark in sorted(plan.titles & set(rendered)):
        titles = plan.sources_of(mark)
        slots.supply(mark, titles, titles, rendering=Rendering.PLAIN)
        del rendered[mark]
    for mark, strings in rendered.items():
        markup = [
            _without_marks(mark, string or "", language, rendered, slots) for language, string in enumerate(strings)
        ]
        slots.supply(mark, markup, [plain_text(string) for string in markup])
    _ACTIVE = None
    return supplied


class ResolveOwnPageAnchors(SphinxPostTransform):
    """Point a fragment's links to its own page's headings at that page.

    A translation can link to a heading of the page it stands on, written as
    ``[text](#the-heading)``. MyST resolves that form against the slugs of the
    document it was parsed in, and a fragment document is not that document, so
    the link reaches the reference resolver unresolved, is reported missing and
    renders as plain text -- which a strict build refuses.

    The owning page is known from the fragment's own docname, and its heading
    slugs are in the environment by the time references are resolved. So the
    link is rewritten here into the form MyST resolves against another
    document: the owning page, with the heading as the target inside it. What
    that resolves to differs from the page's own link by the page's filename in
    front of the anchor and the title wrapper a cross-document reference
    carries, both of which :func:`harvest` takes back off -- the wrapper only
    for the anchors noted here, because a reference the translation wrote as a
    cross-reference carries that wrapper on the page itself.

    The page's own order of precedence is kept rather than guessed at: a page
    resolves such a link against its declared targets first and its heading
    slugs second. A declared target is a label of the whole project, which the
    ordinary resolver already reaches from the fragment and resolves correctly
    apart from that same wrapper -- so a link to one of the owning page's
    labels is left alone and only noted. Rewriting it instead would ask the
    cross-document resolver for an identifier it has no slug for, which it
    reports as missing. A label of another page is neither rewritten nor
    noted: from the fragment it is the same link it is on the page.
    """

    #: Ahead of MyST's own reference resolver, which runs at 9.
    default_priority = 8

    @override
    def run(self, **kwargs: object) -> None:
        """Rewrite every link to one of the owning page's headings that nothing else resolves."""
        from sphinx import addnodes

        plan = _ACTIVE
        owner = plan.owner_of(self.env.docname) if plan is not None else None
        if owner is None or plan is None:
            return
        slugs = self.env.metadata.get(owner, {}).get("myst_slugs", {})
        standard = self.env.domains.standard_domain
        # The identifiers noted are how :func:`harvest` tells a link the page
        # writes plain from a cross-reference the page writes wrapped: the
        # markup the two reach the fragment as is the same.
        noted = plan.anchors.setdefault(owner, set())
        for node in self.document.findall(addnodes.pending_xref):
            if node.get("reftype") != "myst" or node.get("refdomain"):
                continue
            target = node["reftarget"]
            declared = standard.labels.get(target.lower()) or standard.anonlabels.get(target.lower())
            if declared is not None:
                if declared[0] == owner:
                    noted.add(declared[1])
                continue
            if target not in slugs:
                continue
            node["refdomain"] = "doc"
            node["reftargetid"] = target
            node["reftarget"] = owner
            noted.add(slugs[target][1])


class NoteToctreeTitleMarks(SphinxTransform):
    """Note which marked messages a read document carries as a toctree title.

    An explicit toctree entry title and a toctree caption are attributes of the
    toctree node, which is why Sphinx's own translation of them replaces a
    string rather than patching a tree. Nothing parses that string as markup,
    and the smart-quotes transform educates text blocks, so the title reaches
    the navigation, a body toctree and the relation links exactly as the
    catalogue holds it -- where a title the page's own heading supplied reaches
    the same places educated. The two cannot be told apart by where they land,
    so they are told apart here, by the mark.
    """

    #: After Sphinx's own ``Locale`` transform, which is what puts a mark in a
    #: toctree's titles, and long before the smart quotes this is about.
    default_priority = 25

    @override
    def apply(self, **kwargs: object) -> None:
        """Record every mark this document's toctrees carry as a title."""
        from sphinx import addnodes

        if _ACTIVE is None:
            return
        notes = notes_for(self.env, self.env.docname)
        for toctree in self.document.findall(addnodes.toctree):
            titles = [title for title, _docname in toctree["entries"] if title]
            caption = toctree.get("caption")
            if caption:
                titles.append(caption)
            for title in titles:
                notes.titles.update(found.group() for found in MARK.finditer(title))


class NoteDroppedHeadingTranslations(SphinxTransform):
    """Note each language whose translation of a marked heading Sphinx drops.

    Sphinx translates a heading by giving the translation an RST underline,
    parsing that again with the page's own parser, and keeping the result only
    where the first node is one of the few it expects. A translation opening
    with what the parser reads as a list marker -- a Markdown heading numbered
    ``1.`` is the case in this tree -- parses as a list, is dropped, and that
    language's own build keeps the heading in the source language.

    One compile carries every language, so the drop has to be carried too. It
    is decided here, by running the check Sphinx runs rather than by guessing
    the shapes it refuses, because this is where the node is known to be a
    heading and the build's own parser, configuration and settings are at
    hand. :func:`harvest` then records the source language's rendering for the
    languages noted, which is what their own build publishes.

    Sphinx's earlier pass can also translate a heading, from the translation
    parsed with no underline, but it cannot save one this check refuses: a
    string that pass accepts is a lone paragraph, and a lone paragraph given an
    underline is a section title, which this check accepts.
    """

    #: After Sphinx's own ``Locale`` transform, which is what puts a mark in a
    #: heading, and beside the note the toctree titles take.
    default_priority = 26

    @override
    def apply(self, **kwargs: object) -> None:
        """Note, for every marked heading of this document, the languages that lose it."""
        from docutils import nodes

        plan = _ACTIVE
        if plan is None or self.env.docname in plan.fragments:
            return
        source = plan.languages.index(plan.source_language) if plan.source_language in plan.languages else -1
        notes = notes_for(self.env, self.env.docname)
        # Parsing with the page's own parser is what makes the check faithful,
        # and a Markdown parse records the document's heading anchors in this
        # document's metadata. A probe's parse would record its own one-line
        # document's instead, so what this document recorded is put back.
        metadata = dict(self.env.metadata.get(self.env.docname, {}))
        try:
            for heading in self.document.findall(nodes.title):
                # The line the heading was read from, which the probe reports a
                # translation's own diagnostics against, as Sphinx does.
                line = int(getattr(heading, "line", None) or 0)
                for mark in {found.group() for found in MARK.finditer(heading.astext())}:
                    translations = plan.sources_of(mark)
                    dropped = {
                        index
                        for index, translation in enumerate(translations)
                        if index != source and translation and not self._kept(translation, line)
                    }
                    if dropped:
                        notes.dropped.setdefault(mark, set()).update(dropped)
        finally:
            self.env.metadata[self.env.docname] = metadata

    def _kept(self, msgstr: str, line: int) -> bool:
        """Return whether Sphinx's heading substitution keeps *msgstr*.

        The three steps are Sphinx's own (``sphinx.transforms.i18n.Locale``):
        a translation ending in a literal-block marker is given the dummy
        block that keeps the parser quiet, the translation is underlined and
        published with the page's parser, and the node that comes back is
        compared against the types the substitution accepts.
        """
        from docutils import nodes
        from sphinx.transforms.i18n import publish_msgstr
        from sphinx.util.nodes import IMAGE_TYPE_NODES, LITERAL_TYPE_NODES

        if msgstr.strip().endswith("::"):
            msgstr += "\n\n   dummy literal"
        # The build's own settings, with this probe's diagnostics silenced: the
        # page is parsed by the build itself, and a report from a probe of a
        # translation no page of this compile carries is not this build's.
        settings = self.document.settings.copy()
        settings.report_level = _SILENT
        published = publish_msgstr(
            self.app,
            msgstr + "\n" + "=" * len(msgstr) * 2,
            self.document["source"],
            line,
            self.config,
            settings,
        )
        accepted: tuple[type[nodes.Element], ...] = (
            nodes.paragraph,
            nodes.title,
            *LITERAL_TYPE_NODES,
            *IMAGE_TYPE_NODES,
        )
        return isinstance(published.next_node(), accepted)


#: The docutils report level above its own highest, which reports nothing.
_SILENT: Final[int] = 5


class DeclareBlockLanguage(SphinxTransform):
    """Tell each fragment paragraph which language's translation it holds.

    Smart quotation marks are the language's own, and docutils takes the
    language of a text block from the block's own ``language-<tag>`` class and
    from nowhere else -- it does not consult the block's ancestors. So the
    paragraph a translation stands in has to carry the class itself. It is set
    here, from the block's own number, rather than written into the fragment
    source, because neither file type puts a class on a paragraph the same way
    and a directive that did would change what the paragraph renders to.
    """

    #: Before Sphinx educates quotation marks, dashes and ellipses, which is
    #: the transform the class exists for, and after the document is parsed.
    default_priority = 700

    @override
    def apply(self, **kwargs: object) -> None:
        """Class every paragraph of a fragment document with its own language."""
        from docutils import nodes

        plan = _ACTIVE
        if plan is None or self.env.docname not in plan.fragments:
            return
        for paragraph in self.document.findall(nodes.paragraph):
            declared = _DECLARED.match(paragraph.astext())
            if declared is None:
                continue
            language = plan.language_of(declared.group(1))
            if language is not None:
                paragraph["classes"].append(f"language-{language}")
