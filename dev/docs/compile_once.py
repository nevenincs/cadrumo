"""Compile the user documentation once for every language, store it, and measure it.

One Sphinx build, with the multilingual compile active, writes a site whose
pages carry a mark wherever a string depends on the language
(:mod:`dev.docs.compile_slots`). This module runs that build, factors its output
into the stored form :mod:`dev.docs.language_roots` writes, composes every
language's site back from it, and measures ONE composed site against the one
that language's own build produced: the WITNESS (:data:`WITNESS_LANGUAGE`).

The measurement is the point of the module as much as the compile is. A
mechanism that has not been moved leaves the language it could not speak
reading English, so a composed site differs from the witness build in exactly
the places the unmoved mechanisms own. Reporting those differences by the kind
of markup they sit in turns the remaining work into a count that falls as each
mechanism moves, instead of one gate that is red until the last of them does.

One witness rather than one build per language, because a build per language is
exactly the cost the compile exists to retire, and because the languages are not
independent evidence: a composed root is the one structure plus one language's
strings, so what a second translated language's build could show that the first
did not is a defect in that language's own strings, which the catalogue gates
own. What a translated witness shows and an English one cannot is a mechanism
that silently follows the Sphinx ``language`` or was never marked at all: those
read correctly in English by accident.

A difference kept on purpose is declared in :data:`INTENDED_DIFFERENCES` with
its reason and is reported apart from the rest, never folded into the count. A
change made to every build at once moves both sides of the comparison together
and so leaves no difference to declare: those are named in
:data:`UNWITNESSED_CHANGES`, which every measuring run prints beside the counts,
because a reader of the report would otherwise read silence as evidence.

There are two entries, and they differ only in what they keep.
:func:`compile_language_roots` is the one every caller that wants the language
roots uses -- the package build, the ``docs-langs`` recipe, the live preview --
and it writes each language's root where a per-language build used to write it.
:func:`compile_once` is the measuring one: it keeps the compiled site, the
stored form and the composed roots side by side so :func:`compare` can read all
three.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import zlib
from collections import Counter
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Final
from urllib.parse import urlsplit

_ROOT_FOR_DIRECT_INVOCATION = Path(__file__).resolve().parents[2]
if str(_ROOT_FOR_DIRECT_INVOCATION) not in sys.path:
    sys.path.insert(0, str(_ROOT_FOR_DIRECT_INVOCATION))
if not __package__:
    __package__ = "dev.docs"


from cadrumo.core.external_constants import OutputLanguage
from dev.packaging.command_execution import run_command

from .build import DOCS_FLAVOR_ENV, write_deployment_sitemap
from .build import main as build_documentation
from .build_paths import DOCS_BASE_URL_ENV, DOCS_BUILD_ROOT_ENV, DOCS_SITE_PREFIX_ENV, docs_site_prefixes
from .compile_slots import SLOTS_FILE, CompileSlots, context_at, markup_contexts, read_slots
from .language_roots import (
    STRUCTURE_DIRECTORY,
    Layout,
    compose_root,
    read_text,
    refuse_uneven_language_files,
    store_compiled_root,
)
from .language_switcher import carries_switcher, unresolved_cross_root_links
from .message_marks import FRAGMENT_PREFIX
from .sequence_build_gate import SEQUENCE_CHECK_SKIP_ENV
from .shared_page_assets import CHROME_STRINGS_SCRIPT, language_chrome_strings
from .shared_structure import compare_page, slot_numbers
from .translations_js import TRANSLATIONS_SCRIPT, language_translations_js

#: The environment key ``docs/conf.py`` reads to carry every language.
MULTILINGUAL_ENV: Final[str] = "CADRUMO_DOCS_MULTILINGUAL"

#: The documentation settings a compile does not own, and therefore keeps from
#: the environment it is run in: whether the network may be reached, where the
#: repository stands, whether the CLI tree the live command surface writes is
#: emitted, and how wide the read may run. A caller builds hermetically by
#: setting these; everything else a ``CADRUMO_DOCS_`` key could say about the
#: site is the compile's own (:func:`_pin_build_environment`).
#:
#: Read parallelism is here because it is a property of the host and not of the
#: site: it changes how long a build takes and nothing it writes, and a host
#: that has to bound it -- a gate sharing its cores with the rest of a lane --
#: says so once for every build it runs.
HOST_SELECTORS: Final[tuple[str, ...]] = (
    "CADRUMO_DOCS_OFFLINE",
    "CADRUMO_DOCS_PROJECT_ROOT",
    "CADRUMO_DOCS_SKIP_CLI_TREE",
    "CADRUMO_DOCS_JOBS",
    SEQUENCE_CHECK_SKIP_ENV,
)

#: The language whose own build is the proof that a composed root is faithful.
#:
#: It is a TRANSLATED language on purpose. The compile builds in
#: English, so anything that silently follows the Sphinx
#: ``language``, or that was never marked at all, is correct in English by
#: accident: every defect of that kind in this mechanism's history showed in a
#: translated root and in no English one.
#:
#: Catalan among the three: it is not the compile's own language, it sits in the
#: middle of the carried order rather than at either end -- so a mechanism that
#: always reads the first language's string, or the last one's, is wrong here
#: too -- Sphinx ships both a message catalogue and compiled interface strings
#: for it, and its prose is apostrophe-dense, which exercises the typographic
#: education hundreds of times on one page set.
WITNESS_LANGUAGE: Final[str] = "ca"

#: Where each language's own object inventory is written out of the compiled
#: one, inside the compiled site and taken out of the files it is read as.
_INVENTORY_STAGING: Final[str] = ".compile-inventories"

#: Build state inside the compiled site that no reader is served.
_BUILD_STATE: Final[frozenset[str]] = frozenset({".doctrees", ".buildinfo", "_sources", SLOTS_FILE, _INVENTORY_STAGING})

#: Sphinx's own inventory of every page and label, which names each by the
#: title of the page it is on.
INVENTORY_FILE: Final[str] = "objects.inv"

#: The last line of an inventory's header, after which the entries are
#: zlib-compressed (``sphinx.util.inventory.InventoryFile.dump``).
_INVENTORY_BODY: Final[bytes] = b"# The remainder of this file is compressed using zlib.\n"

#: The compression Sphinx writes an inventory's entries with, fed one entry at
#: a time as it feeds them: the deflate stream depends on both, so a language's
#: inventory is only the bytes its own build wrote if it is written the same way.
_INVENTORY_COMPRESSION: Final[int] = 9

#: The deployment sitemap, which ``dev.docs.build`` writes for a build served
#: from an address of its own. It is the one reader-facing file of a compiled
#: site that belongs to one root rather than to all of them.
SITEMAP_FILE: Final[str] = "sitemap.xml"

#: Where a measuring run keeps the one build it measures a composed root
#: against, inside the directory it was given.
_WITNESS_DIRECTORY: Final[str] = "witness"

#: The files one language legitimately holds none of, and which therefore do
#: not make its root uneven (:func:`dev.docs.language_roots.refuse_uneven_language_files`).
#: Sphinx ships compiled interface strings for every language it has a
#: catalogue for, and English is the language its own strings are written in: an
#: English build writes neither the file nor the tag that loads it, so the
#: composed English root holds neither either.
_DECLARED_ABSENCES: Final[Mapping[str, tuple[str, ...]]] = {
    OutputLanguage.EN.value: (f"_static/{TRANSLATIONS_SCRIPT}",)
}

#: Where :func:`compile_language_roots` keeps the stored form while it composes
#: the roots from it, for a caller that did not ask to keep it. Inside the
#: build root, and removed with the compiled site once the roots are written.
_STORED_SCRATCH: Final[str] = ".compiled-text"

_UTF_8: Final[str] = "utf-8"


@dataclass(frozen=True)
class IntendedDifference:
    """One difference from a language's own build that is kept, and why.

    A declaration names the page and what the built page has there as well as
    the markup it sits in, because a markup context covers a whole site: a
    declaration keyed on the context alone would excuse every later difference
    of that kind, which is the one way a proof stops proving anything.

    Attributes:
        context: The markup context (:func:`markup_contexts`) the difference
            sits in.
        page: The page it is on, as a path inside the site root.
        built: What the built page has there, which the composed page does not.
        reason: Why the composed page is right and the built page is not.
    """

    context: str
    page: str
    built: str
    reason: str

    @property
    def key(self) -> str:
        """Return how a comparison counts and reports this difference."""
        return f"{self.page} {self.context}"


#: Differences from the per-language builds that are deliberate. A difference
#: nobody has decided to keep is a defect, so each one here names its page, its
#: markup and the exact bytes it covers.
INTENDED_DIFFERENCES: Final[tuple[IntendedDifference, ...]] = (
    IntendedDifference(
        context="attr:a.href",
        page="how-to/filing-calendar.html",
        built="profile-setup.html",
        reason=(
            "the translated link carries an anchor into the page it names "
            "(profile-setup.md#what-the-active-profile-means) and the one compile resolves it, where a "
            "translated build of that language resolves the same link to the page alone and drops the "
            "anchor: the composed page lands the reader on the section, as the English page does"
        ),
    ),
    IntendedDifference(
        context="attr:span.class",
        page="how-to/filing-calendar.html",
        built="std std-doc",
        reason=(
            "the same link: a reference resolved to an anchor inside a page carries std-ref, where the "
            "page-alone reference a translated build fell back to carries std-doc"
        ),
    ),
)


@dataclass(frozen=True)
class UnwitnessedChange:
    """One deliberate change to what EVERY build of the documentation writes.

    A mechanism moved for the composed roots alone shows up as a difference
    from the per-language build, which is what the comparison counts. A
    mechanism that changed both forms of the site at once moves both sides
    together, so the comparison stays silent about it by construction and the
    silence is not evidence of anything. Each such change is named here and
    printed beside the counts, so a reader of the report is told what the
    report cannot witness.

    Attributes:
        mechanism: The module that owns the change.
        change: What every build now writes that it did not write before.
        reason: Why the change belongs to every build rather than to the
            composed roots alone.
    """

    mechanism: str
    change: str
    reason: str


#: Changes to what every build writes, which the comparison cannot witness. A
#: change here is not excused by the comparison: it is kept out of its reach,
#: and its own gates are the ones that prove it.
UNWITNESSED_CHANGES: Final[tuple[UnwitnessedChange, ...]] = (
    UnwitnessedChange(
        mechanism="myst_parser task lists",
        change=(
            "the English release-notes template loses the checkbox each of its task list items "
            "carried, so it reads as the other three languages' copies of it already did"
        ),
        reason=(
            "Sphinx translates a paragraph by replacing its children, which drops the checkbox, and the "
            "one compile reads the source language through a catalogue like every other language. The "
            "witness is a translated language, whose own build loses the checkbox as well, so there is no "
            "longer a build of the one language this was visible in for the comparison to report it"
        ),
    ),
    UnwitnessedChange(
        mechanism="dev.docs.message_marks",
        change=(
            "a source-language string is the stretch of the page's own source its message was folded "
            "from, line breaks and all, rather than the folded message the catalogue holds"
        ),
        reason=(
            "a build of the language the pages are authored in consults no catalogue, so its pages keep "
            "the line breaks the source wraps at, while the one compile reaches every language through a "
            "catalogue. The recovery (``_SourceText.unfolded``) is what keeps the composed English root "
            "equal to that build, and the witness is a translated language whose own build folds the "
            "breaks exactly as the compile does: nothing in the comparison reads English prose any more"
        ),
    ),
    UnwitnessedChange(
        mechanism="dev.docs.untranslated_typesetting",
        change=(
            "a generated page that nobody translates is typeset in the language it is authored in, "
            "so its quotation marks, dashes and ellipses are the English ones in every root"
        ),
        reason=(
            "educating English prose with another language's quotation marks is not a translation, and a "
            "page read identically in four languages would otherwise cost a stored string per language "
            "for each of them: the per-language builds were changed with the compile so that the one "
            "typesetting both produce is the authored one"
        ),
    ),
    UnwitnessedChange(
        mechanism="dev.docs.section_anchors",
        change=(
            "a generated heading's own anchor is the English one in every language, declared by the "
            "page's generator rather than slugged from the translated heading"
        ),
        reason=(
            "one structure cannot hold four spellings of one id, and an anchor that moved with the "
            "language was already a permalink whose target depended on which root the reader stood in: "
            "the per-language builds publish the same declared anchor, which is the one they shipped "
            "in English"
        ),
    ),
)


def unwitnessed_report() -> str:
    """Return the lines a measuring run prints for :data:`UNWITNESSED_CHANGES`."""
    lines = [f"{len(UNWITNESSED_CHANGES)} change(s) to every build, which the comparison cannot witness:"]
    for entry in UNWITNESSED_CHANGES:
        lines.append(f"  {entry.mechanism}: {entry.change}")
        lines.append(f"    because {entry.reason}")
    return "\n".join(lines)


#: The context a difference in a file that is not a page is counted under.
#: Such a file holds no markup, so the whole file is what differs.
_WHOLE_FILE: Final[str] = "file"

#: The context a file neither side can be read as text in is counted under. A
#: page is compared by the markup it is written in, so one whose bytes are not
#: the text it claims to be has no context of its own to be filed under.
_UNDECODABLE: Final[str] = "undecodable"


@dataclass
class Comparison:
    """What one composed site still differs from its own build in.

    Attributes:
        language: The language compared.
        pages: Pages compared in both. Every other file of the site is
            compared as well, whole, and counted under :data:`_WHOLE_FILE`.
        equal: Pages whose bytes already match.
        missing: Paths the built site has and the composed site does not.
        extra: Paths the composed site has and the built site does not.
        by_context: Differing stretches by the markup context they sit in.
        intended: Differing stretches a declared intended difference covers,
            by that declaration's own key.
        samples: Up to three examples per context.
    """

    language: str
    pages: int = 0
    equal: int = 0
    missing: list[str] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)
    by_context: Counter[str] = field(default_factory=Counter)
    intended: Counter[str] = field(default_factory=Counter)
    samples: dict[str, list[tuple[str, str, str]]] = field(default_factory=dict)

    @property
    def differences(self) -> int:
        """How many stretches still differ, intended ones excluded."""
        return sum(self.by_context.values())

    @property
    def absent(self) -> int:
        """How many files one of the two sites has and the other does not.

        Reported and judged apart from :attr:`differences`, which counts
        stretches inside the files both sites have: a composed root missing a
        page is not a page that differs, and folding the two together would
        let one hide in the other's count. Both have to be nothing for a
        measuring run to pass.
        """
        return len(self.missing) + len(self.extra)

    def report(self, *, contexts: int = 25) -> str:
        """Return the comparison as the lines a run prints."""
        lines = [
            f"{self.language}: {self.equal} of {self.pages} page(s) already equal, "
            f"{self.differences} differing stretch(es), {sum(self.intended.values())} intended, "
            f"{len(self.missing)} missing, {len(self.extra)} extra"
        ]
        for path in self.missing[:5]:
            lines.append(f"  missing: {path}")
        for path in self.extra[:5]:
            lines.append(f"  extra: {path}")
        for key, count in self.intended.most_common():
            reason = next(entry.reason for entry in INTENDED_DIFFERENCES if entry.key == key)
            lines.append(f"  {count:8d}  {key}  (intended: {reason})")
        for context, count in self.by_context.most_common(contexts):
            lines.append(f"  {count:8d}  {context}")
            for path, built, composed in self.samples.get(context, []):
                lines.append(f"            {path}: built {built!r} -> composed {composed!r}")
        return "\n".join(lines)


@dataclass(frozen=True)
class CompileOnceResult:
    """What one compile produced.

    Attributes:
        compiled: The site the one Sphinx build wrote.
        stored: The structure and each language's text.
        roots: Each language's site composed from the stored form.
        languages: The languages the compile carried.
        marks: Distinct marks the compile recorded.
        seconds: Wall time of the Sphinx build alone.
    """

    compiled: Path
    stored: Path
    roots: Mapping[str, Path]
    languages: tuple[str, ...]
    marks: int
    seconds: float


@dataclass(frozen=True)
class CompiledLanguageRoots:
    """The language roots one compile wrote.

    Attributes:
        html_root: The directory the roots sit under.
        roots: Each language's own root, by language tag.
        stored: The structure and each language's text the roots were composed
            from, which is what a caller ships instead of the roots where it
            can compose them later; None when the caller asked for the roots
            alone and the stored form was removed with the rest of the
            compile's scaffolding.
        languages: The languages the compile carried, in the stored order.
        seconds: Wall time of the Sphinx compile alone.
    """

    html_root: Path
    roots: Mapping[str, Path]
    stored: Path | None
    languages: tuple[str, ...]
    seconds: float


def _site_files(root: Path) -> dict[str, Path]:
    """Return a built or composed site's reader-facing files by path inside it."""
    files: dict[str, Path] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative in _BUILD_STATE or relative.split("/")[0] in _BUILD_STATE:
            continue
        files[relative] = path
    return files


def _per_language_assets(files: dict[str, Path], languages: Sequence[str]) -> dict[str, dict[str, Path]]:
    """Return each language's own copy of the assets the compile wrote per language.

    The variants are build output of the compile, so they are taken out of the
    site's shared files: what the site holds is the canonical path, stored once
    per language from these. A language the compile wrote no variant for is
    stored none, which is what a language whose own build writes no such file
    needs: English has no Sphinx interface strings and therefore no
    ``translations.js``.
    """
    per_language: dict[str, dict[str, Path]] = {language: {} for language in languages}
    variants = {
        CHROME_STRINGS_SCRIPT: language_chrome_strings,
        TRANSLATIONS_SCRIPT: language_translations_js,
    }
    for canonical, named in variants.items():
        for language in languages:
            source = files.pop(f"_static/{named(language)}", None)
            if source is not None:
                per_language[language][f"_static/{canonical}"] = source
    return per_language


def _names_a_fragment(entry: str) -> bool:
    """Return whether one inventory entry points into a fragment document.

    An entry is its name, its domain and type, its priority, the page it is on
    and its display name, in that order and separated by single spaces; only
    the display name can hold one, so the page is the fourth field.
    """
    fields = entry.split(" ", 4)
    page = fields[3].partition("#")[0] if len(fields) > 3 else ""
    return PurePosixPath(page).name.startswith(FRAGMENT_PREFIX)


def _per_language_inventory(
    files: dict[str, Path],
    slots: CompileSlots,
    staging: Path,
) -> dict[str, dict[str, Path]]:
    """Return each language's own object inventory, read out of the compiled one.

    The inventory names every page and label by the title of its page, and a
    title is a mark. Its entries are compressed, so no mark is visible in the
    file and the ordinary rule -- a file carrying no mark is the same bytes in
    every language -- would store the compile's own marks once and give them to
    every language. It is therefore read back here, each language's titles put
    in as the page's own text reads them, and written as Sphinx writes it.

    The compiled inventory is taken out of *files*, because what the site holds
    is one inventory per language and not a fifth. What the compile read and no
    language's build does is taken out of the entries: a fragment document is
    build scaffolding whose written page is deleted once its translations have
    been read, so the inventory must not go on naming it
    (:mod:`dev.docs.message_marks`).

    Args:
        files: The compiled site's files, which the inventory is taken out of.
        slots: The marks the compile recorded.
        staging: A directory to write each language's inventory into.

    Returns:
        For each language, its own inventory by its path inside the root; empty
        for every language when the compile wrote none.

    Raises:
        SystemExit: If the compiled inventory is not in the format whose
            entries can be read back.
    """
    source = files.pop(INVENTORY_FILE, None)
    if source is None:
        return {language: {} for language in slots.languages}
    header, marker, body = source.read_bytes().partition(_INVENTORY_BODY)
    if not marker:
        raise SystemExit(
            f"{source} does not carry the compressed-entry header a Sphinx inventory has, "
            "so the titles its entries name cannot be read in each language"
        )
    entries = [entry for entry in zlib.decompress(body).decode(_UTF_8).splitlines() if not _names_a_fragment(entry)]
    written: dict[str, dict[str, Path]] = {}
    for index, language in enumerate(slots.languages):
        compressor = zlib.compressobj(_INVENTORY_COMPRESSION)
        compressed = b"".join(
            compressor.compress(f"{slots.plain_resolved(entry, index)}\n".encode(_UTF_8)) for entry in entries
        )
        target = staging / language / INVENTORY_FILE
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(
            slots.plain_resolved(header.decode(_UTF_8), index).encode(_UTF_8) + marker + compressed + compressor.flush()
        )
        written[language] = {INVENTORY_FILE: target}
    return written


def _pin_build_environment(
    build_root: Path,
    *,
    flavor: str,
    jobs: int | None,
    base_url: str | None = None,
    check_sequences: bool | None = None,
) -> None:
    """Pin the one compile's selectors so an ambient setting cannot reshape it.

    Set in this process rather than handed to a child, because the build driver
    is called here and spawns the Sphinx child itself: one authority for how a
    documentation build is run, which is also the only place the marks could be
    recorded from.

    Args:
        build_root: The documentation build root the compile works under.
        flavor: Who the pages are for, as ``dev.docs.build`` means it.
        jobs: Sphinx read parallelism, or None for the build's own default.
        base_url: The site's address above the language directories, or None
            for a site served from no address of its own.
        check_sequences: Whether the CLI sequence gate runs, or None to leave
            an ambient decision alone.
    """
    # Everything the compile does not decide is kept: whether the host may be
    # reached and which optional generator runs are a caller's hermetic
    # arrangement, not a selector that could reshape the site.
    kept = {key: os.environ[key] for key in HOST_SELECTORS if key in os.environ}
    for key in [key for key in os.environ if key.startswith("CADRUMO_DOCS_")]:
        del os.environ[key]
    os.environ.update(kept)
    os.environ.update(
        {
            MULTILINGUAL_ENV: "1",
            DOCS_BUILD_ROOT_ENV: str(build_root),
            DOCS_FLAVOR_ENV: flavor,
            # The site has one search index, built over the composed roots once
            # they exist. A compiled site carrying marks is not a site a reader
            # opens, so indexing it would index the marks.
            "CADRUMO_DOCS_PAGEFIND_MODE": "none",
            "PYTHONIOENCODING": _UTF_8,
        }
    )
    if jobs is not None:
        os.environ["CADRUMO_DOCS_JOBS"] = str(jobs)
    if base_url is not None:
        os.environ[DOCS_BASE_URL_ENV] = base_url
        # A site with an address of its own serves every language under its own
        # code, English included, so no language is at the apex of this layout.
        # The address and this root's own directory are what say so, and
        # :func:`dev.docs.build_paths.docs_site_prefixes` reads both: the
        # desktop package is the other layout, with neither.
        os.environ[DOCS_SITE_PREFIX_ENV] = f"{OutputLanguage.EN.value}/"
    if check_sequences is not None:
        if check_sequences:
            os.environ.pop(SEQUENCE_CHECK_SKIP_ENV, None)
        else:
            os.environ[SEQUENCE_CHECK_SKIP_ENV] = "1"


def witness_root(destination: Path, language: str) -> Path:
    """Return where a measuring run under *destination* keeps one language's own build."""
    return destination / _WITNESS_DIRECTORY / language


def witness_build(
    language: str,
    out_dir: Path,
    *,
    flavor: str,
    base_url: str | None,
    build_root: Path,
    base: Mapping[str, str] | None = None,
) -> tuple[list[str], dict[str, str]]:
    """Return the command and environment of one language's OWN documentation root.

    The witness is a real strict build of one language at the user scope, which
    is what the composed root of that language is measured against. Its
    selectors are the ones the website publisher gives a per-root build
    (:mod:`dev.deploy.docs_site_languages`), because a root is only comparable
    to a compile that was told the same things about where it is served: the
    address of its own directory, that directory's name, and that the site's one
    search index is built over every root afterwards rather than by this build.

    It is declared here, beside :func:`_pin_build_environment`, so the compile
    and the build it is proven against take their selectors from one authority.
    A difference between the two that neither the compile nor the build owns is
    a difference the measurement would report as a defect of the compile.

    Args:
        language: The language to build, which is the language measured.
        out_dir: Where the built root goes.
        flavor: Who the pages are for, as ``dev.docs.build`` means it, and as
            the compile being measured was given.
        base_url: The site's address above the language directories, or None for
            a site served from no address of its own.
        build_root: A documentation build root of this build's own. Pinned
            rather than left to the host because a strict build reads the
            inventory of whatever root stands there and resolves its own
            references against it: two builds given different build roots are
            not the same build.
        base: The environment to build on; the process environment by default.

    Returns:
        The command line, and the whole environment to run it under.
    """
    carried = base if base is not None else os.environ
    # Every documentation selector is dropped and then pinned, exactly as
    # :func:`_pin_build_environment` does it for the compile, so an ambient key
    # cannot reshape one of the two builds and not the other. What is not a
    # documentation selector is kept: where product storage goes is the
    # caller's, and both builds need it.
    environment = {key: value for key, value in carried.items() if not key.startswith("CADRUMO_DOCS_")}
    environment.update({key: carried[key] for key in HOST_SELECTORS if key in carried})
    environment.update(
        {
            DOCS_FLAVOR_ENV: flavor,
            DOCS_BUILD_ROOT_ENV: str(build_root),
            DOCS_SITE_PREFIX_ENV: language,
            "CADRUMO_DOCS_PAGEFIND_MODE": "none",
            "PYTHONIOENCODING": _UTF_8,
        }
    )
    if base_url is not None:
        environment[DOCS_BASE_URL_ENV] = f"{base_url.rstrip('/')}/{language}"
    command = [
        sys.executable,
        "-m",
        "dev.docs.build",
        "--strict",
        "--isolated-source",
        "--scope",
        "user",
        "--language",
        language,
        "--out-dir",
        str(out_dir),
    ]
    return command, environment


def _refuse_unresolved_cross_root_links(
    stored: Path,
    layout: Layout,
    prefixes: Mapping[str, str],
    site_path: str,
) -> None:
    """Refuse a stored form whose language switcher addresses a page no root holds.

    Read off the stored form rather than off the composed roots: the switcher is
    one recorded string per language, so each page's structure is scanned once
    and then only the few strings that carry the element are looked at, instead
    of every page being read again in every language.

    The pages stored whole carry none: the element names the language of the
    root it stands in, so a page every language reads the same bytes of has no
    switcher on it at all.

    Raises:
        SystemExit: If any page's switcher names an address its target root does
            not hold (:func:`dev.docs.language_switcher.unresolved_cross_root_links`).
    """
    files = {
        language: {*layout.pages, *layout.shared, *layout.language_files[language]} for language in layout.languages
    }
    strings = {language: read_text(stored, language) for language in layout.languages}
    # The slots whose string carries a switcher, found once per language rather
    # than page by page: a page then only has to say which slots it uses.
    carrying = {
        language: {number for number, value in enumerate(text) if carries_switcher(value)}
        for language, text in strings.items()
    }
    found: list[str] = []
    for path in layout.pages:
        numbers = slot_numbers((stored / STRUCTURE_DIRECTORY / path).read_text(encoding=_UTF_8))
        for language in layout.languages:
            for number in dict.fromkeys(numbers):
                if number not in carrying[language]:
                    continue
                found.extend(
                    unresolved_cross_root_links(
                        strings[language][number],
                        language=language,
                        page=path,
                        prefixes=prefixes,
                        files=files,
                        site_path=site_path,
                    )
                )
    if found:
        raise SystemExit(
            f"{len(found)} language-switcher link(s) address a page the root they name does not hold:\n  "
            + "\n  ".join(found[:20])
        )


def _compile_and_compose(
    compiled: Path,
    stored: Path,
    roots_in: Path,
    *,
    build_root: Path,
    flavor: str,
    jobs: int | None,
    strict: bool,
    check_sequences: bool | None,
    base_url: str | None,
    only: Sequence[str] | None = None,
) -> CompileOnceResult:
    """Run the one compile, store what it wrote, and compose every language from the store.

    *only* names the languages whose roots are written; the compile still
    carries every language, because that is what it stores.

    Every directory written is cleared first. The compile's own doctree cache
    lives inside the compiled site, which Sphinx puts it in for a build given
    no cache of its own, so clearing that directory is what keeps a compile
    from reading an earlier one's environment back: the marks are numbered per
    compile, and a cached doctree would carry another compile's numbers into
    this one's pages.

    Raises:
        SystemExit: If the Sphinx build fails, wrote no record of its marks, or
            was asked for the root of a language it does not carry.
    """
    for directory in (compiled, stored):
        if directory.exists():
            shutil.rmtree(directory)
    _pin_build_environment(build_root, flavor=flavor, jobs=jobs, base_url=base_url, check_sequences=check_sequences)
    started = time.monotonic()
    code = build_documentation(
        [
            # One language is still named, because the compile is one build and
            # a build has one Sphinx ``language``. It selects the user scope and
            # the catalogues; what it no longer selects is the text on the pages.
            "--language",
            OutputLanguage.EN.value,
            "--isolated-source",
            *(["--strict"] if strict else []),
            "--out-dir",
            str(compiled),
        ]
    )
    seconds = time.monotonic() - started
    if code != 0:
        raise SystemExit(f"the one documentation compile failed: exit {code}")
    record = compiled / SLOTS_FILE
    if not record.is_file():
        raise SystemExit(
            f"the compile wrote no record of its marks at {record}; "
            f"it was not run with {MULTILINGUAL_ENV}=1, or docs/conf.py did not start recording"
        )
    slots = read_slots(record)
    files = _site_files(compiled)
    language_files = _per_language_assets(files, slots.languages)
    for language, inventory in _per_language_inventory(files, slots, compiled / _INVENTORY_STAGING).items():
        language_files[language].update(inventory)
    # The sitemap names every page by its absolute address, and the driver that
    # wrote it was given the address above the language directories, because
    # that is what one compile of all of them is served from. So the compiled
    # site's own sitemap belongs to no root: each is written from its own
    # composed root below, where the language is known.
    files.pop(SITEMAP_FILE, None)
    layout = store_compiled_root(files, slots, stored, language_files=language_files)
    # The stored form is checked here rather than in each root, because these
    # three refusals are about the SITE and not about one language's copy of it:
    # every root of every flavour comes through this function, and what each
    # refusal names is invisible in a single composed root.
    refuse_uneven_language_files(layout, absent=_DECLARED_ABSENCES)
    _refuse_unresolved_cross_root_links(
        stored,
        layout,
        docs_site_prefixes(
            layout.languages,
            build_language=OutputLanguage.EN.value,
            source_language=OutputLanguage.EN.value,
        ),
        # The error page's own links are absolute, because it is served for an
        # address that does not exist: what they are absolute to is the path the
        # site is served under, which only the address above the roots says.
        urlsplit(base_url).path.rstrip("/") if base_url is not None else "",
    )
    roots: dict[str, Path] = {}
    for language in roots_to_write(slots.languages, only):
        roots[language] = roots_in / language
        if roots[language].exists():
            shutil.rmtree(roots[language])
        compose_root(stored, language, roots[language])
        if base_url is not None and flavor == "web":
            write_deployment_sitemap(roots[language], f"{base_url.rstrip('/')}/{language}")
    return CompileOnceResult(
        compiled=compiled,
        stored=stored,
        roots=roots,
        languages=slots.languages,
        marks=len(slots.values),
        seconds=seconds,
    )


def roots_to_write(carried: Sequence[str], only: Sequence[str] | None) -> tuple[str, ...]:
    """Return the languages whose roots a compile writes, in the order it carries them.

    Args:
        carried: The languages the compile carries.
        only: The languages a caller asked for, or None for all of them.

    Raises:
        SystemExit: If *only* names a language the compile does not carry. Such
            a language has no text to compose a root from, and writing the
            others would leave a site missing a root its caller counts on.
    """
    if only is None:
        return tuple(carried)
    uncarried = sorted(set(only) - set(carried))
    if uncarried:
        raise SystemExit(
            f"the compile carries {', '.join(carried)} and was asked for the root of {', '.join(uncarried)}; "
            "a language the documentation is not translated into has no root to write"
        )
    return tuple(language for language in carried if language in only)


def compile_once(
    destination: Path,
    *,
    flavor: str = "desktop",
    jobs: int | None = None,
    base_url: str | None = None,
    strict: bool = False,
) -> CompileOnceResult:
    """Compile the documentation once, store it, and compose every language back.

    This is the measuring entry: it keeps the compiled site, the stored form and
    the composed roots side by side under one directory so a comparison can read
    all three. A caller that wants the roots themselves calls
    :func:`compile_language_roots`.

    Args:
        destination: A directory to write the compiled site, the stored form
            and the composed roots into.
        flavor: Who the pages are for, as ``dev.docs.build`` means it.
        jobs: Sphinx read parallelism, or None for the build's own default.
        base_url: The site's address above the language directories, as
            :func:`compile_language_roots` means it. The measurement needs it
            too: a root the publisher builds from its own address differs from
            one built from none wherever a page states where it is served, so
            a witness built that way is only comparable to a compile given the
            same address.
        strict: Whether the compile refuses a warning (Sphinx ``-n -W``). The
            witness build always does, so a measurement of a compile that does
            not is measuring two builds that were not held to one standard.

    Returns:
        What the compile produced.

    Raises:
        SystemExit: If the Sphinx build fails, or wrote no record of its marks.
    """
    return _compile_and_compose(
        destination / "compiled",
        destination / "stored",
        destination / "roots",
        build_root=destination / "build",
        flavor=flavor,
        jobs=jobs,
        strict=strict,
        check_sequences=None,
        base_url=base_url,
    )


def compile_language_roots(
    html_root: Path,
    *,
    build_root: Path,
    flavor: str = "desktop",
    jobs: int | None = None,
    strict: bool = True,
    check_sequences: bool = True,
    base_url: str | None = None,
    stored: Path | None = None,
    languages: Sequence[str] | None = None,
) -> CompiledLanguageRoots:
    """Write every language's documentation root from ONE compile.

    This is the entry every caller uses to produce the language roots: the
    package build, the ``docs-langs`` recipe and the live preview. It replaces
    one Sphinx build per language, which is what the whole mechanism exists to
    stop: the pages are read and written once no matter how many languages the
    site publishes, and each root is composed from the structure plus that
    language's own strings (:mod:`dev.docs.language_roots`).

    Args:
        html_root: The directory the language roots are written under, each at
            ``<html_root>/<language>``. An existing root is replaced.
        build_root: The documentation build root the compile works under. The
            compiled site and the stored form are written beneath it, and
            neither is a root a reader is served.
        flavor: Who the pages are for, as ``dev.docs.build`` means it: ``web``
            for the published site, ``desktop`` for the packaged copy.
        jobs: Sphinx read parallelism, or None for the build's own default.
        strict: Whether the compile refuses a warning (Sphinx ``-n -W``).
        check_sequences: Whether the CLI sequence gate runs. One compile is one
            build, so the gate runs once rather than on a chosen root.
        base_url: The site's address above the language directories, such as
            ``https://example.test/docs``; None for a site served from no
            address of its own, which is what the packaged copy is.
        stored: Where to keep the structure and each language's text, or None
            to compose the roots from it and remove it again. A caller that
            stages or ships the stored form rather than the composed roots
            names a directory; one that wants the roots gets no second copy of
            the site in its build directory.
        languages: The languages whose roots are written, or None for every
            language the compile carries. A caller whose site already has a
            root from another build -- the published site's English root, which
            alone carries the API reference -- names the rest, so the compile
            leaves that root alone. The compile reads and stores every language
            either way.

    Returns:
        The roots written, and what the compile cost.

    Raises:
        SystemExit: If the Sphinx build fails, wrote no record of its marks, or
            was asked for the root of a language it does not carry.
    """
    result = _compile_and_compose(
        build_root / "compiled",
        stored if stored is not None else build_root / _STORED_SCRATCH,
        html_root,
        build_root=build_root,
        flavor=flavor,
        jobs=jobs,
        strict=strict,
        check_sequences=check_sequences,
        base_url=base_url,
        only=languages,
    )
    # The compiled site is scaffolding here: it carries the marks, no reader is
    # served it, and what the roots were composed from is the stored form beside
    # them. It is removed so a caller that inventories its own build directory
    # sees the roots and the text, not a third copy of the site and its doctree
    # cache. The measuring entry keeps it, which is what it exists for.
    shutil.rmtree(result.compiled)
    # The stored form is the roots' own intermediate unless a caller asked to
    # keep it: a caller that wanted the roots composed is handed the roots, and
    # a second copy of the whole site left beside them would be inventoried,
    # cached and shipped by every build directory that holds one.
    if stored is None:
        shutil.rmtree(result.stored)
    return CompiledLanguageRoots(
        html_root=html_root,
        roots=result.roots,
        stored=stored,
        languages=result.languages,
        seconds=result.seconds,
    )


def compare(composed: Path, built: Path, language: str, *, samples: int = 3) -> Comparison:
    """Return what one composed site still differs from that language's own build in.

    Args:
        composed: The site composed from the stored form.
        built: The site that language's own build produced.
        language: The language, for the report.
        samples: Examples to keep per markup context.

    Returns:
        The comparison: every page's differing stretches counted by the markup
        context they sit in, and every other file counted whole.
    """
    found = Comparison(language=language)
    composed_files, built_files = _site_files(composed), _site_files(built)
    found.missing = sorted(set(built_files) - set(composed_files))
    found.extra = sorted(set(composed_files) - set(built_files))
    for path in sorted(set(composed_files) & set(built_files)):
        built_bytes = built_files[path].read_bytes()
        composed_bytes = composed_files[path].read_bytes()
        if not path.endswith(".html"):
            # A file that is not a page is stored whole, so it is compared
            # whole: there is no markup in it for a difference to sit in, and
            # one that differs at all differs in what a reader is served. The
            # search index, the inventory and the sitemap are each a language's
            # own, and a proof that only read the pages would not say so.
            if built_bytes != composed_bytes:
                found.by_context[_WHOLE_FILE] += 1
                kept = found.samples.setdefault(_WHOLE_FILE, [])
                if len(kept) < samples:
                    kept.append((path, f"{len(built_bytes)} byte(s)", f"{len(composed_bytes)} byte(s)"))
            continue
        found.pages += 1
        if built_bytes == composed_bytes:
            found.equal += 1
            continue
        # Decoded strictly, because a page read with replacement characters is
        # not the page: two different invalid byte sequences both read as the
        # replacement character and would compare equal, which is the one way a
        # byte-for-byte proof could call two different pages the same.
        pages = _decoded_pair(built_bytes, composed_bytes)
        if pages is None:
            found.by_context[_UNDECODABLE] += 1
            kept = found.samples.setdefault(_UNDECODABLE, [])
            if len(kept) < samples:
                kept.append((path, f"{len(built_bytes)} byte(s)", f"{len(composed_bytes)} byte(s)"))
            continue
        built_page, composed_page = pages
        contexts = markup_contexts(built_page)
        starts = [start for start, _ in contexts]
        for difference in compare_page(built_page, composed_page):
            context = context_at(starts, contexts, difference.offset)
            declared = next(
                (
                    entry
                    for entry in INTENDED_DIFFERENCES
                    # The whole differing stretch, not a part of it: a
                    # declaration matched on a substring would excuse every
                    # other stretch of that context on that page that happens
                    # to contain the bytes it names -- a wrong anchor, or
                    # another language's root -- which is a standing permission
                    # rather than one difference kept on purpose.
                    if entry.context == context and entry.page == path and entry.built == difference.base
                ),
                None,
            )
            if declared is not None:
                found.intended[declared.key] += 1
                continue
            found.by_context[context] += 1
            kept = found.samples.setdefault(context, [])
            if len(kept) < samples:
                kept.append((path, difference.base[:90], difference.other[:90]))
    return found


def _decoded_pair(built: bytes, composed: bytes) -> tuple[str, str] | None:
    """Return both pages as text, or None when either one's bytes are not UTF-8.

    A page the compile wrote and a page composed from the stored form are both
    UTF-8 by construction, so neither can be read any other way: a page that
    cannot be decoded is a difference the comparison reports, and never a page
    silently read with replacement characters in it.
    """
    try:
        return built.decode(_UTF_8), composed.decode(_UTF_8)
    except UnicodeDecodeError:
        return None


def main(argv: list[str] | None = None) -> int:
    """Compile once, store, compose, and report what still differs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=None, help="Directory for the compile, the stored form and the roots."
    )
    parser.add_argument(
        "--html-root",
        type=Path,
        default=None,
        help=(
            "Write one documentation root per language under this directory, each at <html-root>/<language>, "
            "and report nothing else. This is the publishing mode: --out is the measuring one."
        ),
    )
    parser.add_argument(
        "--build-root",
        type=Path,
        default=None,
        help="Documentation build root for --html-root; the parent of the HTML root by default.",
    )
    parser.add_argument("--strict", action="store_true", help="Refuse a warning in the compile (Sphinx -n -W).")
    parser.add_argument(
        "--stored",
        type=Path,
        default=None,
        help=(
            "Keep the structure and each language's text here; --html-root only. It is the roots' own "
            "intermediate by default, removed once they are composed from it."
        ),
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="The address the site is served from, above the language directories.",
    )
    parser.add_argument(
        "--languages",
        nargs="+",
        default=None,
        help="Write only these languages' roots; --html-root only. Every language is written by default.",
    )
    parser.add_argument(
        "--witness",
        default=None,
        metavar="LANG",
        help=(
            "Measure the composed root of this language against a build of that language's own, which this "
            f"run makes under <out>/{_WITNESS_DIRECTORY}/<LANG>; --out only. {WITNESS_LANGUAGE} is the one "
            "the gate witnesses."
        ),
    )
    parser.add_argument("--flavor", default="desktop", help="Who the pages are for (web or desktop).")
    parser.add_argument("--jobs", type=int, default=None, help="Sphinx read parallelism.")
    parser.add_argument(
        "--compare-only",
        action="store_true",
        help="Skip the compile and measure the roots a previous run left under --out.",
    )
    parser.add_argument("--json", type=Path, default=None, help="Write the comparison counts here as well.")
    arguments = parser.parse_args(argv)

    if (arguments.html_root is None) == (arguments.out is None):
        parser.error("give exactly one of --html-root (publish the roots) and --out (compile and measure)")
    if arguments.html_root is not None:
        html_root = arguments.html_root
        written = compile_language_roots(
            html_root,
            build_root=arguments.build_root if arguments.build_root is not None else html_root.parent,
            flavor=arguments.flavor,
            jobs=arguments.jobs,
            strict=arguments.strict,
            # The gate the environment already decides about: a caller that
            # cannot run the live CLI sequences says so there, and this mode
            # does not overrule it.
            check_sequences=os.environ.get(SEQUENCE_CHECK_SKIP_ENV) != "1",
            base_url=arguments.base_url,
            stored=arguments.stored,
            languages=arguments.languages,
        )
        kept = f", stored in {arguments.stored}" if arguments.stored is not None else ""
        print(
            f"One compile of {len(written.languages)} language(s) in {written.seconds:.0f} s: "
            f"wrote {', '.join(written.roots)} under {written.html_root}{kept}",
            flush=True,
        )
        return 0

    destination = arguments.out
    witness = arguments.witness
    if arguments.compare_only:
        stored = destination / "stored"
        languages = json.loads((stored / "layout.json").read_text(encoding=_UTF_8))["languages"]
        roots = {language: destination / "roots" / language for language in languages}
        print(f"Measuring the roots already composed under {destination}")
    else:
        destination.mkdir(parents=True, exist_ok=True)
        for leftover in ("compiled", "stored", "roots", _WITNESS_DIRECTORY):
            if (destination / leftover).exists():
                raise SystemExit(f"{destination / leftover} exists; give an empty --out or pass --compare-only")
        # The witness is started beside the compile rather than after it, so
        # the one build the measurement needs costs the longer of the two
        # rather than their sum. The compile runs here, in this process, which
        # is where the marks are recorded, so it is the witness that goes to a
        # thread and a child.
        with ThreadPoolExecutor(max_workers=1) as pool:
            building = None
            if witness is not None:
                command, environment = witness_build(
                    witness,
                    witness_root(destination, witness),
                    flavor=arguments.flavor,
                    base_url=arguments.base_url,
                    build_root=destination / _WITNESS_DIRECTORY / "build",
                )
                print(f"Building the {witness} root of its own, beside the compile", flush=True)
                building = pool.submit(
                    run_command, command, cwd=_ROOT_FOR_DIRECT_INVOCATION, environment=environment, errors="replace"
                )
            result = compile_once(
                destination,
                flavor=arguments.flavor,
                jobs=arguments.jobs,
                base_url=arguments.base_url,
                strict=arguments.strict,
            )
            languages, roots = list(result.languages), dict(result.roots)
            stored_size = sum(path.stat().st_size for path in result.stored.rglob("*") if path.is_file())
            print(
                f"One compile of {len(languages)} language(s) in {result.seconds:.0f} s: "
                f"{result.marks} distinct mark(s), stored as {stored_size / 1_000_000:.1f} MB in {result.stored}",
                flush=True,
            )
            if building is not None:
                built_witness = building.result()
                print(f"The {witness} build of its own took {built_witness.duration_seconds:.0f} s", flush=True)
                if built_witness.returncode != 0:
                    print(built_witness.stdout[-4000:] + built_witness.stderr[-4000:], flush=True)
                    raise SystemExit(
                        f"the {witness} build the measurement is against failed: exit {built_witness.returncode}"
                    )

    if witness is None:
        print("No witness language given; nothing was measured.")
        return 0
    if witness not in languages:
        raise SystemExit(f"the compile carries {', '.join(languages)}, and was asked to witness {witness}")
    built = witness_root(destination, witness)
    if not built.is_dir():
        raise SystemExit(f"no {witness} build to measure the composed {witness} root against at {built}")
    comparison = compare(roots[witness], built, witness)
    print(comparison.report(), flush=True)
    print(
        f"\n{comparison.differences} differing stretch(es) and "
        f"{comparison.absent} missing or extra file(s) in the {witness} root",
        flush=True,
    )
    print(unwitnessed_report(), flush=True)
    if arguments.json is not None:
        arguments.json.write_text(
            json.dumps(
                {
                    comparison.language: {
                        "pages": comparison.pages,
                        "equal": comparison.equal,
                        "differences": comparison.differences,
                        "absent": comparison.absent,
                        "missing": comparison.missing,
                        "extra": comparison.extra,
                        "by_context": dict(comparison.by_context.most_common()),
                        "intended": dict(comparison.intended.most_common()),
                    }
                },
                indent=1,
            )
            + "\n",
            encoding=_UTF_8,
        )
    # A composed root missing a page, or carrying one no build wrote, fails the
    # run as a differing stretch does: a site that is not the same set of files
    # is not the same site, whatever the files it does share read like.
    return 0 if comparison.differences == 0 and comparison.absent == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
