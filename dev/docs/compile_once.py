"""Compile the user documentation once for every language, store it, and measure it.

One Sphinx build, with the multilingual compile active, writes a site whose
pages carry a mark wherever a string depends on the language
(:mod:`dev.docs.compile_slots`). This module runs that build, factors its output
into the stored form :mod:`dev.docs.language_roots` writes, composes every
language's site back from it, and -- while per-language builds still exist --
measures each composed site against the one that language's own build produced.

The measurement is the point of the module as much as the compile is. A
mechanism that has not yet been moved leaves the language it could not speak
reading English, so a composed site differs from its oracle in exactly the
places the unmoved mechanisms own. Reporting those differences by the kind of
markup they sit in turns the remaining work into a count that falls as each
mechanism moves, instead of one gate that is red until the last of them does.

A difference kept on purpose is declared in :data:`INTENDED_DIFFERENCES` with
its reason and is reported apart from the rest, never folded into the count.

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
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

_ROOT_FOR_DIRECT_INVOCATION = Path(__file__).resolve().parents[2]
if str(_ROOT_FOR_DIRECT_INVOCATION) not in sys.path:
    sys.path.insert(0, str(_ROOT_FOR_DIRECT_INVOCATION))
if not __package__:
    __package__ = "dev.docs"


from .build import DOCS_FLAVOR_ENV
from .build import main as build_documentation
from .build_paths import DOCS_BASE_URL_ENV, DOCS_BUILD_ROOT_ENV, DOCS_SITE_PREFIX_ENV
from .compile_slots import SLOTS_FILE, context_at, markup_contexts, read_slots
from .i18n import DEFAULT_SOURCE_LANGUAGE
from .language_roots import compose_root, store_compiled_root
from .sequence_build_gate import SEQUENCE_CHECK_SKIP_ENV
from .shared_page_assets import CHROME_STRINGS_SCRIPT, language_chrome_strings
from .shared_structure import compare_page
from .translations_js import TRANSLATIONS_SCRIPT, language_translations_js

#: The environment key ``docs/conf.py`` reads to carry every language.
MULTILINGUAL_ENV: Final[str] = "CADRUMO_DOCS_MULTILINGUAL"

#: The Sphinx ``language`` the one compile builds in: the language the pages
#: are authored in, whose messages every catalogue translates. It selects the
#: scope and the catalogues, not the text the pages carry.
COMPILE_LANGUAGE: Final[str] = DEFAULT_SOURCE_LANGUAGE

#: The documentation settings a compile does not own, and therefore keeps from
#: the environment it is run in: whether the network may be reached, where the
#: repository stands, and whether the CLI tree the live command surface writes
#: is emitted. A caller builds hermetically by setting these; everything else a
#: ``CADRUMO_DOCS_`` key could say about the site is the compile's own
#: (:func:`_pin_build_environment`).
HOST_SELECTORS: Final[tuple[str, ...]] = (
    "CADRUMO_DOCS_OFFLINE",
    "CADRUMO_DOCS_PROJECT_ROOT",
    "CADRUMO_DOCS_SKIP_CLI_TREE",
    SEQUENCE_CHECK_SKIP_ENV,
)

#: Build state inside the compiled site that no reader is served.
_BUILD_STATE: Final[frozenset[str]] = frozenset({".doctrees", ".buildinfo", "_sources", SLOTS_FILE})

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
        context="markup:p",
        page="_release_notes_template.html",
        built='<input class="task-list-item-checkbox" disabled="disabled" type="checkbox">',
        reason=(
            "Sphinx translates a paragraph by replacing its children, which drops the checkbox a "
            "task list item carries: every language whose build translates this page already loses "
            "it, and the one compile reads the source language through a catalogue as well, so the "
            "English page now reads as the other three do"
        ),
    ),
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


@dataclass
class Comparison:
    """What one composed site still differs from its own build in.

    Attributes:
        language: The language compared.
        pages: Pages compared in both.
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
            can compose them later.
        languages: The languages the compile carried, in the stored order.
        seconds: Wall time of the Sphinx compile alone.
    """

    html_root: Path
    roots: Mapping[str, Path]
    stored: Path
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
        # code, English included, so no language is at the apex of this layout:
        # the compile says so by carrying a prefix itself, which is what
        # :func:`dev.docs.build_paths.docs_site_prefixes` reads
        # (the desktop package is the other layout, and carries none).
        os.environ[DOCS_SITE_PREFIX_ENV] = f"{COMPILE_LANGUAGE}/"
    if check_sequences is not None:
        if check_sequences:
            os.environ.pop(SEQUENCE_CHECK_SKIP_ENV, None)
        else:
            os.environ[SEQUENCE_CHECK_SKIP_ENV] = "1"


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
) -> CompileOnceResult:
    """Run the one compile, store what it wrote, and compose every language from the store.

    Every directory written is cleared first. The compile's own doctree cache
    lives inside the compiled site, which Sphinx puts it in for a build given
    no cache of its own, so clearing that directory is what keeps a compile
    from reading an earlier one's environment back: the marks are numbered per
    compile, and a cached doctree would carry another compile's numbers into
    this one's pages.

    Raises:
        SystemExit: If the Sphinx build fails, or wrote no record of its marks.
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
            COMPILE_LANGUAGE,
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
    store_compiled_root(files, slots, stored, language_files=language_files)
    roots: dict[str, Path] = {}
    for language in slots.languages:
        roots[language] = roots_in / language
        if roots[language].exists():
            shutil.rmtree(roots[language])
        compose_root(stored, language, roots[language])
    return CompileOnceResult(
        compiled=compiled,
        stored=stored,
        roots=roots,
        languages=slots.languages,
        marks=len(slots.values),
        seconds=seconds,
    )


def compile_once(
    destination: Path,
    *,
    flavor: str = "desktop",
    jobs: int | None = None,
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
        strict=False,
        check_sequences=None,
        base_url=None,
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
            to keep it beneath *build_root*. A caller that stages or ships the
            stored form rather than the composed roots names it.

    Returns:
        The roots written, and what the compile cost.

    Raises:
        SystemExit: If the Sphinx build fails, or wrote no record of its marks.
    """
    result = _compile_and_compose(
        build_root / "compiled",
        stored if stored is not None else build_root / "compiled-text",
        html_root,
        build_root=build_root,
        flavor=flavor,
        jobs=jobs,
        strict=strict,
        check_sequences=check_sequences,
        base_url=base_url,
    )
    # The compiled site is scaffolding here: it carries the marks, no reader is
    # served it, and what the roots were composed from is the stored form beside
    # them. It is removed so a caller that inventories its own build directory
    # sees the roots and the text, not a third copy of the site and its doctree
    # cache. The measuring entry keeps it, which is what it exists for.
    shutil.rmtree(result.compiled)
    return CompiledLanguageRoots(
        html_root=html_root,
        roots=result.roots,
        stored=result.stored,
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
        The comparison, differing stretches counted by markup context.
    """
    found = Comparison(language=language)
    composed_files, built_files = _site_files(composed), _site_files(built)
    found.missing = sorted(set(built_files) - set(composed_files))
    found.extra = sorted(set(composed_files) - set(built_files))
    for path in sorted(set(composed_files) & set(built_files)):
        built_bytes = built_files[path].read_bytes()
        composed_bytes = composed_files[path].read_bytes()
        if not path.endswith(".html"):
            continue
        found.pages += 1
        if built_bytes == composed_bytes:
            found.equal += 1
            continue
        built_page = built_bytes.decode(_UTF_8, errors="replace")
        contexts = markup_contexts(built_page)
        starts = [start for start, _ in contexts]
        for difference in compare_page(built_page, composed_bytes.decode(_UTF_8, errors="replace")):
            context = context_at(starts, contexts, difference.offset)
            declared = next(
                (
                    entry
                    for entry in INTENDED_DIFFERENCES
                    if entry.context == context and entry.page == path and entry.built in difference.base
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


def _oracle_roots(oracle: Path, languages: Sequence[str]) -> dict[str, Path]:
    """Return each language's own built root under *oracle*, refusing an absent one."""
    roots = {language: oracle / language for language in languages}
    absent = sorted(language for language, root in roots.items() if not root.is_dir())
    if absent:
        raise SystemExit(f"the oracle holds no built root for {', '.join(absent)} under {oracle}")
    return roots


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
    parser.add_argument(
        "--strict", action="store_true", help="Refuse a warning in the compile (Sphinx -n -W); --html-root only."
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="The address the site is served from, above the language directories; --html-root only.",
    )
    parser.add_argument(
        "--oracle",
        type=Path,
        default=None,
        help="Directory holding one built root per language, named by its language tag, to measure against.",
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
        )
        print(
            f"One compile of {len(written.languages)} language(s) in {written.seconds:.0f} s: "
            f"{', '.join(written.languages)} under {written.html_root}",
            flush=True,
        )
        return 0

    destination = arguments.out
    if arguments.compare_only:
        stored = destination / "stored"
        languages = json.loads((stored / "layout.json").read_text(encoding=_UTF_8))["languages"]
        roots = {language: destination / "roots" / language for language in languages}
        print(f"Measuring the roots already composed under {destination}")
    else:
        destination.mkdir(parents=True, exist_ok=True)
        for leftover in ("compiled", "stored", "roots"):
            if (destination / leftover).exists():
                raise SystemExit(f"{destination / leftover} exists; give an empty --out or pass --compare-only")
        result = compile_once(destination, flavor=arguments.flavor, jobs=arguments.jobs)
        languages, roots = list(result.languages), dict(result.roots)
        stored_size = sum(path.stat().st_size for path in result.stored.rglob("*") if path.is_file())
        print(
            f"One compile of {len(languages)} language(s) in {result.seconds:.0f} s: "
            f"{result.marks} distinct mark(s), stored as {stored_size / 1_000_000:.1f} MB in {result.stored}",
            flush=True,
        )

    if arguments.oracle is None:
        print("No oracle given; nothing was measured.")
        return 0
    oracle = _oracle_roots(arguments.oracle, languages)
    comparisons = [compare(roots[language], oracle[language], language) for language in languages]
    for comparison in comparisons:
        print(comparison.report(), flush=True)
    total = sum(comparison.differences for comparison in comparisons)
    print(f"\n{total} differing stretch(es) over {len(languages)} language(s)", flush=True)
    if arguments.json is not None:
        arguments.json.write_text(
            json.dumps(
                {
                    comparison.language: {
                        "pages": comparison.pages,
                        "equal": comparison.equal,
                        "differences": comparison.differences,
                        "missing": comparison.missing,
                        "extra": comparison.extra,
                        "by_context": dict(comparison.by_context.most_common()),
                        "intended": dict(comparison.intended.most_common()),
                    }
                    for comparison in comparisons
                },
                indent=1,
            )
            + "\n",
            encoding=_UTF_8,
        )
    return 0 if total == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
