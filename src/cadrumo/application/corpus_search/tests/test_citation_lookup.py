"""Real-behavior tests for the structured citation lookup."""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

from ....domain.calculations.registry import authority as authority_module
from ..citation_lookup import CitationLookup, bundled_citation_lookup
from ..errors import CorpusSearchInputError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(scope="session", autouse=True)
def compose_runtime_ports() -> Iterator[None]:
    """Keep this published-artifact test independent of application port setup."""
    yield


@pytest.fixture(scope="module")
def _published_authority(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Stage the committed authority artifact behind the runtime loader."""
    root = tmp_path_factory.mktemp("citation-authority")
    artifact_path = root / "registry" / "authority" / "authority.json"
    artifact_path.parent.mkdir(parents=True)
    shutil.copy2(authority_module.bundled_authority_artifact_path(), artifact_path)
    return root


@pytest.fixture
def lookup(_published_authority: Path, monkeypatch: pytest.MonkeyPatch) -> CitationLookup:
    """Read the staged publication through the same runtime authority boundary."""
    monkeypatch.setattr(authority_module, "_bundled_path", lambda *parts: _published_authority.joinpath(*parts))
    return bundled_citation_lookup()


def test_resolve_returns_verbatim_text_and_metadata(lookup: CitationLookup) -> None:
    resolution = lookup.resolve("ley-58-2003:art-27.2")
    assert resolution.document_id == "BOE-A-2003-23186"
    assert resolution.kind == "ley"
    assert resolution.permalink.startswith("https://www.boe.es/")
    assert resolution.anchor == "a27-2"
    assert "extempor" in resolution.verbatim_text.lower()


def test_resolve_slices_consolidated_document_by_anchor(lookup: CitationLookup) -> None:
    resolution = lookup.resolve("ley-35-2006:art-11")
    assert resolution.anchor == "a11"
    assert resolution.verbatim_text.strip()
    # The anchor slice must be a fragment of the consolidated file, not the
    # whole multi-hundred-article document.
    full_text_length = 700_000
    assert len(resolution.verbatim_text) < full_text_length


def test_unknown_citation_is_refused(lookup: CitationLookup) -> None:
    with pytest.raises(CorpusSearchInputError):
        lookup.resolve("no-such-law:art-999")


def test_citation_authority_is_the_registry_catalogue(lookup: CitationLookup) -> None:
    # The lookup must key on the registry legal catalogue, not a parallel
    # citation parser: its id set equals the catalogue's.
    assert lookup.citation_ids == tuple(sorted(authority_module.bundled_authority().catalogues.legal))


def test_every_catalogue_citation_resolves_to_text(lookup: CitationLookup) -> None:
    unresolved: list[str] = []
    for citation_id in lookup.citation_ids:
        resolution = lookup.resolve(citation_id)
        if not resolution.verbatim_text.strip():
            unresolved.append(citation_id)
    assert not unresolved, f"citations resolved to empty text: {unresolved[:10]}"


def test_resolve_corpus_text_accepts_a_citation_id(lookup: CitationLookup) -> None:
    text = lookup.resolve_corpus_text("ley-58-2003:art-27.2")
    assert "extempor" in text.lower()


def test_resolve_corpus_text_accepts_a_corpus_ref(lookup: CitationLookup) -> None:
    text = lookup.resolve_corpus_text("corpus/normatives/html/ley-58-2003-art-27.html#a27-2")
    assert "extempor" in text.lower()


def test_resolve_corpus_text_refuses_unknown_reference(lookup: CitationLookup) -> None:
    with pytest.raises(CorpusSearchInputError):
        lookup.resolve_corpus_text("corpus/normatives/html/does-not-exist.html#a1")
