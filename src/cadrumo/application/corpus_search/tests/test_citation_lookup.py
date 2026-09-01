"""Real-behavior tests for the structured citation lookup."""

from __future__ import annotations

from pathlib import Path

import pytest

from ....domain.calculations.registry.authority import bundled_authority
from ..citation_lookup import CitationLookup, bundled_citation_lookup
from ..errors import CorpusSearchInputError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_resolve_returns_verbatim_text_and_metadata() -> None:
    lookup = bundled_citation_lookup()
    resolution = lookup.resolve("ley-58-2003:art-27.2")
    assert resolution.document_id == "BOE-A-2003-23186"
    assert resolution.kind == "ley"
    assert resolution.permalink.startswith("https://www.boe.es/")
    assert resolution.anchor == "a27-2"
    assert "extempor" in resolution.verbatim_text.lower()


def test_resolve_refuses_a_sidecar_less_source(tmp_path: Path) -> None:
    """An anchor cannot widen to raw BOE text when its unit sidecar is absent."""
    reference = bundled_authority().catalogues.legal["ley-35-2006:art-1"]
    source_path = bundled_authority().source_root / reference.corpus_ref.partition("#")[0]
    copied_path = tmp_path / reference.corpus_ref.partition("#")[0]
    copied_path.parent.mkdir(parents=True)
    copied_path.write_bytes(source_path.read_bytes())

    lookup = CitationLookup({reference.id: reference}, source_root=tmp_path)
    with pytest.raises(CorpusSearchInputError) as raised:
        lookup.resolve("ley-35-2006:art-1")

    assert raised.value.reason == "citation_extracted_text_absent"


def test_resolve_slices_consolidated_document_by_anchor() -> None:
    lookup = bundled_citation_lookup()
    resolution = lookup.resolve("ley-35-2006:art-11")
    assert resolution.anchor == "a11"
    assert resolution.verbatim_text.strip()
    # The anchor slice must be a fragment of the consolidated file, not the
    # whole multi-hundred-article document.
    full_text_length = 700_000
    assert len(resolution.verbatim_text) < full_text_length


def test_unknown_citation_is_refused() -> None:
    lookup = bundled_citation_lookup()
    with pytest.raises(CorpusSearchInputError):
        lookup.resolve("no-such-law:art-999")


def test_citation_authority_is_the_registry_catalogue() -> None:
    # The lookup must key on the registry legal catalogue, not a parallel
    # citation parser: its id set equals the catalogue's.
    lookup = bundled_citation_lookup()
    catalogue_ids = tuple(sorted(bundled_authority().catalogues.legal))
    assert lookup.citation_ids == catalogue_ids


def test_every_catalogue_citation_resolves_to_text() -> None:
    lookup = bundled_citation_lookup()
    unresolved: list[str] = []
    for citation_id in lookup.citation_ids:
        resolution = lookup.resolve(citation_id)
        if not resolution.verbatim_text.strip():
            unresolved.append(citation_id)
    assert not unresolved, f"citations resolved to empty text: {unresolved[:10]}"


def test_resolve_corpus_text_accepts_a_citation_id() -> None:
    lookup = bundled_citation_lookup()
    text = lookup.resolve_corpus_text("ley-58-2003:art-27.2")
    assert "extempor" in text.lower()


def test_resolve_corpus_text_accepts_a_corpus_ref() -> None:
    lookup = bundled_citation_lookup()
    text = lookup.resolve_corpus_text("corpus/normatives/html/ley-58-2003-art-27.html#a27-2")
    assert "extempor" in text.lower()


def test_resolve_corpus_text_refuses_unknown_reference() -> None:
    lookup = bundled_citation_lookup()
    with pytest.raises(CorpusSearchInputError):
        lookup.resolve_corpus_text("corpus/normatives/html/does-not-exist.html#a1")
