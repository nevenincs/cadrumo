"""Compare composed documentation roots to their language-specific builds."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from .compile_slots import SLOTS_FILE, context_at, markup_contexts
from .shared_structure import compare_page

_BUILD_STATE: Final[frozenset[str]] = frozenset(
    {".doctrees", ".buildinfo", "_sources", SLOTS_FILE, ".compile-inventories"}
)
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


def site_files(root: Path) -> dict[str, Path]:
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
    composed_files, built_files = site_files(composed), site_files(built)
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
        _compare_pages(found, path, pages, samples)
    return found


def _compare_pages(found: Comparison, path: str, pages: tuple[str, str], samples: int) -> None:
    """Count page differences by markup context."""
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
