"""One bundled file has one origin, and every source row citing it must say so.

A ``SourceReference`` mixes two kinds of claim. Some fields describe the
ARTIFACT -- the digest and length of the bytes, the day they were retrieved,
the address they were retrieved from. Those are observations about one file,
so every row pointing at that file must carry the same values, and two rows
that disagree mean at least one of them reports an origin nobody observed.
The other fields describe the USE -- which evidence tier this citation leans
on, which kind of document it is being read as, the applicability window the
citing declaration needs, the review the row itself has had. Those
legitimately differ between rows, because one BOE order really can carry both
the procedure an ``instructions`` row cites and the annex a ``layout_authority``
row cites, and each row's window belongs to the modelo citing it. Collapsing
them would overclaim, so this gate separates the two and binds only the first.

The second comparison goes outside the catalogue entirely. A BOE capture
carries its own identity: a ``rel="canonical"`` link naming the address the
document is served at, and, for the Spanish edition of the diary, an ELI
``date_publication``. Those are the publisher's statements, embedded in bytes
the registry already hash-pins, so they settle ``source_url`` and
``published_at`` without a network call and without trusting whichever row was
typed most recently.

NO COUNT IS PINNED and no allowlist exists. Both comparisons walk whatever is
registered now against whatever is bundled now.
"""

from __future__ import annotations

import html as html_entities
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import pytest

from cadrumo.core.resources.bundled_data import bundled_path

from .catalogue_verification_support import authored_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_NORMATIVES_HTML = "corpus/normatives/html/"
_CANONICAL_LINK = re.compile(r'<link[^>]+rel="canonical"[^>]+href="(?P<href>[^"]+)"')
_ELI_PUBLICATION = re.compile(
    r'<meta\s+about="(?P<about>[^"]*)"\s+'
    r'property="http://data\.europa\.eu/eli/ontology#date_publication"\s+'
    r'content="(?P<content>[^"]*)"'
)
"""The BOE serves one ELI resource per language edition of a diary issue.

Only the Spanish one (``/spa``) is the Boletin Oficial del Estado itself; the
Catalan and Galician supplements are published on their own later days, so a
comparison that took any ``date_publication`` would read a translation's date
as the norm's publication date.
"""


def _artifact_facts(source: Any) -> Mapping[str, object]:
    """Return the fields that describe the file rather than the citation.

    ``source_url`` is compared without its fragment: the fragment addresses a
    provision inside one document, so two rows citing different articles of one
    law are naming the same retrieval, not disagreeing about it.
    """
    return {
        "bytes": source.bytes,
        "retrieved_at": str(source.retrieved_at),
        "sha256": source.sha256,
        "source_url": str(source.source_url).split("#")[0],
    }


def _sources() -> tuple[Any, ...]:
    return tuple(authored_catalogues().sources.values())


def _shared_paths(sources: Iterable[Any]) -> Mapping[str, list[Any]]:
    grouped: dict[str, list[Any]] = defaultdict(list)
    for source in sources:
        grouped[source.corpus_path].append(source)
    return {path: rows for path, rows in grouped.items() if len(rows) > 1}


def _origin_disagreements(sources: Iterable[Any]) -> list[str]:
    """Report every field on which two rows citing one file disagree."""
    disagreements: list[str] = []
    for path, rows in sorted(_shared_paths(sources).items()):
        facts = {source.id: _artifact_facts(source) for source in rows}
        for field in sorted(next(iter(facts.values()))):
            declared = {source_id: values[field] for source_id, values in facts.items()}
            if len(set(declared.values())) > 1:
                rendered = ", ".join(f"{source_id}={value!r}" for source_id, value in sorted(declared.items()))
                disagreements.append(f"{path} {field}: {rendered}")
    return disagreements


def test_the_comparison_reaches_files_cited_by_more_than_one_source() -> None:
    """Anti-vacuity: a catalogue with no shared file would pass without comparing anything."""
    shared = _shared_paths(_sources())
    assert len(shared) > 10, f"only {len(shared)} bundled file(s) are cited by more than one source row"


def test_every_source_citing_one_bundled_file_declares_one_origin() -> None:
    """Digest, length, retrieval day and address belong to the file, not to the citation."""
    disagreements = _origin_disagreements(_sources())
    assert not disagreements, (
        f"{len(disagreements)} bundled file(s) carry source rows that disagree about the origin "
        "of the same bytes:\n  " + "\n  ".join(disagreements)
    )


class _DoctoredRow:
    """One source row whose retrieval date is restated, for the detector only."""

    def __init__(self, source: Any) -> None:
        self.id = source.id
        self.corpus_path = source.corpus_path
        self.sha256 = source.sha256
        self.bytes = source.bytes
        self.retrieved_at = "1970-01-01"
        self.source_url = str(source.source_url)


def test_a_row_that_restates_one_origin_differently_is_detected() -> None:
    """Detector teeth: one shared-path row is doctored in a local copy of the catalogue."""
    sources = _sources()
    shared = _shared_paths(sources)
    assert shared, "no shared bundled path was available to doctor"
    target = shared[sorted(shared)[0]][0]
    doctored = tuple(_DoctoredRow(source) if source.id == target.id else source for source in sources)

    disagreements = _origin_disagreements(doctored)

    assert len(disagreements) == 1, f"the doctored retrieval date was not isolated: {disagreements}"
    assert disagreements[0].startswith(f"{target.corpus_path} retrieved_at:")


def _capture_identity(path: Path) -> tuple[str | None, str | None]:
    """Return the canonical address and Spanish publication date the capture states."""
    markup = path.read_text(encoding="utf-8", errors="replace")
    link = _CANONICAL_LINK.search(markup)
    published: list[str] = sorted(
        {
            str(match.group("content"))
            for match in _ELI_PUBLICATION.finditer(markup)
            if str(match.group("about")).endswith("/spa")
        }
    )
    return (
        html_entities.unescape(link.group("href")).strip() if link else None,
        published[0] if len(published) == 1 else None,
    )


def _publisher_disagreements(sources: Iterable[Any], *, base: Path) -> list[str]:
    """Compare each captured normative's declared origin with what the bytes state."""
    disagreements: list[str] = []
    for source in sources:
        if not source.corpus_path.startswith(_NORMATIVES_HTML):
            continue
        canonical, published = _capture_identity(base / source.corpus_path)
        declared_url = str(source.source_url).split("#")[0]
        if canonical is not None and declared_url != canonical:
            disagreements.append(f"{source.id} source_url: catalogue {declared_url!r} vs capture {canonical!r}")
        if published is not None and source.published_at is not None and str(source.published_at) != published:
            disagreements.append(
                f"{source.id} published_at: catalogue {str(source.published_at)!r} vs capture {published!r}"
            )
    return sorted(disagreements)


def test_the_publisher_comparison_reaches_the_captured_normatives() -> None:
    """Anti-vacuity: captures that state neither fact would make the gate silent."""
    base = bundled_path()
    stated = [
        source
        for source in _sources()
        if source.corpus_path.startswith(_NORMATIVES_HTML)
        and any(fact is not None for fact in _capture_identity(base / source.corpus_path))
    ]
    assert len(stated) > 50, f"only {len(stated)} captured normative(s) state their own identity"


def test_declared_origin_matches_what_the_capture_states_about_itself() -> None:
    """The publisher's own canonical link and ELI date settle both fields."""
    disagreements = _publisher_disagreements(_sources(), base=bundled_path())
    assert not disagreements, (
        f"{len(disagreements)} source row(s) disagree with the BOE capture they pin:\n  " + "\n  ".join(disagreements)
    )


def _falsify_publication_date(match: re.Match[str]) -> str:
    if not match.group("about").endswith("/spa"):
        return match.group(0)
    return match.group(0).replace(f'content="{match.group("content")}"', 'content="1970-01-01"')


@pytest.mark.parametrize("field", ("published_at", "source_url"))
def test_a_capture_that_contradicts_its_row_is_detected(field: str, tmp_path: Path) -> None:
    """Detector teeth: a doctored capture is written to a temporary tree, never the corpus."""
    base = bundled_path()
    target = next(
        source
        for source in _sources()
        if source.corpus_path.startswith(_NORMATIVES_HTML)
        and source.published_at is not None
        and all(fact is not None for fact in _capture_identity(base / source.corpus_path))
    )
    original = (base / target.corpus_path).read_text(encoding="utf-8", errors="replace")
    if field == "source_url":
        doctored = _CANONICAL_LINK.sub('<link rel="canonical" href="https://x.invalid/"/>', original, count=1)
        expected_declared = str(target.source_url).split("#")[0]
        expected_capture = "https://x.invalid/"
    else:
        doctored = _ELI_PUBLICATION.sub(_falsify_publication_date, original)
        expected_declared = str(target.published_at)
        expected_capture = "1970-01-01"
    assert doctored != original, f"the capture's {field} evidence was not altered"
    staged = tmp_path / target.corpus_path
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_text(doctored, encoding="utf-8")

    disagreements = _publisher_disagreements((target,), base=tmp_path)

    assert disagreements == [f"{target.id} {field}: catalogue {expected_declared!r} vs capture {expected_capture!r}"], (
        disagreements
    )
