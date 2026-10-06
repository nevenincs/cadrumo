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

What this costs per added language is the rendering of its text: one more
catalogue read, one more paragraph per message in the fragment documents, and
one more string per mark. The pages themselves are read and written once no
matter how many languages the compile carries.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, override

from sphinx.transforms import SphinxTransform
from sphinx.transforms.post_transforms import SphinxPostTransform

from .compile_slots import MARK, MARK_CLOSE, MARK_OPEN, CompileSlots, Rendering, mark_number, plain_text

#: Private-use characters delimiting one rendered translation inside a
#: fragment document. Deliberately distinct from the mark and the slot
#: delimiters, so the three artefacts can never be read as one another.
BLOCK_OPEN: Final[str] = ""
BLOCK_MID: Final[str] = ""
BLOCK_CLOSE: Final[str] = ""

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
        messages: Marks reserved, one per marked message.
    """

    languages: tuple[str, ...]
    blocks: list[_Block] = field(default_factory=list)
    fragments: list[str] = field(default_factory=list)
    pages: list[str] = field(default_factory=list)
    titles: set[str] = field(default_factory=set)

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


def _read_catalogue(path: Path) -> dict[str, str]:
    """Return one gettext catalogue as its usable singular translations, in file order."""
    from babel.messages.pofile import read_po

    with path.open("rb") as stream:
        catalogue = read_po(stream)
    translations: dict[str, str] = {}
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
    return translations


def _one_line(value: str) -> str:
    """Return one translation as a single paragraph line.

    A build of the language substitutes the translation as the catalogue holds
    it, one line, so the fragment holds one line too: a line break the
    catalogue happens to carry would reach the page where that build's page has
    a space.
    """
    return " ".join(value.split())


#: A reference to the owning page's own heading, as resolving it from another
#: document writes it. A reference inside one document takes the heading's own
#: text; the same reference from outside takes the heading's title and says so
#: with a class. The move the fragment makes is what turns the first into the
#: second, so the wrapper it adds comes back off with the filename.
_SAME_PAGE_TITLE: Final[re.Pattern[str]] = re.compile(
    r'(<a\b[^>]*href="#[^"]*"[^>]*>)<span class="std std-ref">(.*?)</span>(</a>)'
)

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
        previous_space = True
        for offset, character in enumerate(text):
            space = character.isspace()
            if space and previous_space:
                continue
            self._folded.append(" " if space else character)
            self._offsets.append(offset)
            previous_space = space
        self._text = text
        self._joined = "".join(self._folded)

    def unfolded(self, message: str) -> str:
        """Return the source *message* was folded from, its lines left undented.

        A continuation line's indentation is not part of the text the parser
        builds -- the page carries the line break and nothing else -- so the
        recovered stretch carries the same.
        """
        found = self._joined.find(_folded(message))
        if found < 0:
            return message
        span = self._text[self._offsets[found] : self._offsets[found + len(_folded(message)) - 1] + 1]
        recovered = "\n".join(line.strip() for line in span.splitlines())
        # The recovery is only trustworthy where it folds back to the message
        # it was looked up by; where it does not, the folded message stands.
        return recovered if _folded(recovered) == _folded(message) else message


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


def _catalogues(locales: Path, domain: str, languages: Sequence[str], source: str) -> dict[str, dict[str, str]] | None:
    """Return each language's catalogue for one page, or None if no language carries one.

    The language the messages are authored in carries no catalogue, so its
    translation of a message is the message.
    """
    found: dict[str, dict[str, str]] = {}
    for language in languages:
        if language == source:
            continue
        path = locales / language / "LC_MESSAGES" / f"{domain}.po"
        if path.is_file():
            found[language] = _read_catalogue(path)
    return found or None


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
            a mark or a block delimiter.
    """
    from sphinx.util.i18n import docname_to_domain

    global _ACTIVE
    plan = MessagePlan(languages=slots.languages)
    locales = srcdir / "locales"
    pseudo = srcdir / PSEUDO_LOCALE_DIR / source_language / "LC_MESSAGES"
    reserved = ((MARK_OPEN, "a mark"), (MARK_CLOSE, "a mark"), *((character, "a block") for character in _BLOCK))
    for docname in sorted(docnames):
        domain = docname_to_domain(docname, compact)
        catalogues = _catalogues(locales, domain, plan.languages, source_language)
        if catalogues is None:
            continue
        marked: dict[str, str] = {}
        blocks: list[tuple[int, _Block]] = []
        source = doc2path(docname)
        authored = _SourceText(source.read_text(encoding=_UTF_8))
        for message in next(iter(catalogues.values())):
            translations = [
                authored.unfolded(message)
                if language == source_language
                else _one_line(catalogues[language].get(message, ""))
                for language in plan.languages
            ]
            # A message no language has translated yet is left English, which
            # is what a single-language build of that language does with it.
            if not all(translations):
                continue
            for translation in translations:
                for character, kind in reserved:
                    if character in translation:
                        raise MessageMarksError(
                            f"the translation {translation[:60]!r} of a message of {docname} "
                            f"contains a character reserved for {kind} delimiter"
                        )
            mark = slots.reserve(Rendering.MESSAGE)
            marked[message] = f"{mark}{_NOQA}"
            for index, translation in enumerate(translations):
                blocks.append((len(plan.blocks), _Block(mark, index, translation)))
                plan.blocks.append(blocks[-1][1])
        if not marked:
            continue
        _write_pseudo_catalogue(pseudo / f"{domain}.mo", marked)
        fragment = source.with_name(f"{FRAGMENT_PREFIX}{source.name}")
        fragment.write_text(_fragment_source(source.suffix, blocks), encoding=_UTF_8)
        plan.fragments.append(fragment_docname(docname))
        plan.pages.append(docname)
    _ACTIVE = plan
    return plan


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
        # A reference to the owning page's own labels resolves from the
        # fragment as a reference to another document, because that is what the
        # fragment is; on the page it is a reference within one. The fragment
        # stands in the page's own directory, so the one difference the move
        # makes to a resolved link is the page's own filename in front of the
        # anchor, which is taken back off here.
        own = f'href="{page_path(owner).name}#'
        for found in _RENDERED.finditer(page.read_text(encoding=_UTF_8)):
            block = plan.blocks[int(found.group(1), 16)]
            # The paragraph's own spaces around the translation are the ones
            # that let its outermost inline markup be recognised; exactly one
            # of each is given back.
            # A recorded string is put straight into a finished page, so a line
            # break inside it has to be the terminator that page already uses:
            # the one the writer that wrote it used, not the one reading the
            # fragment back through universal newlines left.
            markup = _SAME_PAGE_TITLE.sub(
                r"\1\2\3",
                found.group(2).removeprefix(" ").removesuffix(" ").replace(own, 'href="#'),
            ).replace("\n", os.linesep)
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
    carries, both of which :func:`harvest` already takes back off.

    The page's own order of precedence is kept rather than guessed at: a page
    resolves such a link against its declared targets first and its heading
    slugs second, and a declared target is a label of the whole project that
    the ordinary resolver already reaches from the fragment. So only a slug
    that is not also a label is rewritten here. Without that, a heading
    carrying both -- a declared target whose name is the heading's own slug --
    would be reached through its section instead of through the target, and the
    section's own identifier is not the target's.
    """

    #: Ahead of MyST's own reference resolver, which runs at 9.
    default_priority = 8

    @override
    def run(self, **kwargs: object) -> None:
        """Rewrite every link to one of the owning page's headings that nothing else resolves."""
        from sphinx import addnodes

        plan = _ACTIVE
        owner = plan.owner_of(self.env.docname) if plan is not None else None
        if owner is None:
            return
        slugs = self.env.metadata.get(owner, {}).get("myst_slugs", {})
        standard = self.env.domains.standard_domain
        for node in self.document.findall(addnodes.pending_xref):
            if node.get("reftype") != "myst" or node.get("refdomain"):
                continue
            target = node["reftarget"]
            if target not in slugs or target.lower() in standard.labels or target.lower() in standard.anonlabels:
                continue
            node["refdomain"] = "doc"
            node["reftargetid"] = target
            node["reftarget"] = owner


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

        plan = _ACTIVE
        if plan is None:
            return
        for toctree in self.document.findall(addnodes.toctree):
            titles = [title for title, _docname in toctree["entries"] if title]
            caption = toctree.get("caption")
            if caption:
                titles.append(caption)
            for title in titles:
                plan.titles.update(found.group() for found in MARK.finditer(title))


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
