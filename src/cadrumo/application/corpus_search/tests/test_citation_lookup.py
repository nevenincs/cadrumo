"""Real-behavior tests for the structured citation lookup."""

from __future__ import annotations

from collections.abc import Iterator
from typing import cast

import pytest

from ....core.hashing import sha256_hex
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.authority_artifact import (
    AuthorityComponentKind,
    EvidenceComponentQuery,
    PublishedLegalEvidence,
    ReferenceComponentQuery,
)
from ....domain.calculations.registry.authority_store import SQLiteAuthorityReader
from ....domain.calculations.registry.tests.authority_fakes import FakeAuthorityComponentReader
from ..citation_lookup import CitationLookup, bundled_citation_lookup
from ..errors import CorpusSearchInputError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(scope="session", autouse=True)
def compose_runtime_ports() -> Iterator[None]:
    """Keep this published-artifact test independent of application port setup."""
    yield


@pytest.fixture(scope="module")
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    """Hold one real published generation for every lookup in this module."""
    with bundled_indexed_authority().operation() as operation:
        yield operation


@pytest.fixture(scope="module")
def lookup(authority_operation: PinnedAuthorityOperation) -> CitationLookup:
    """Build a point-addressed lookup over the selected citation ids."""
    return bundled_citation_lookup(
        ("ley-58-2003:art-27.2", "ley-35-2006:art-11"),
        operation=authority_operation,
    )


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


def test_citation_authority_is_the_caller_selected_registry_set(lookup: CitationLookup) -> None:
    assert lookup.citation_ids == ("ley-35-2006:art-11", "ley-58-2003:art-27.2")


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


def test_component_reader_loads_only_the_requested_legal_evidence(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    reference = authority_operation.legal_reference("ley-58-2003:art-27.2")
    anchored_text = authority_operation.legal_evidence("ley-58-2003:art-27.2").anchored_text
    evidence = PublishedLegalEvidence(
        legal_reference_id=str(reference.id),
        anchored_text=anchored_text,
        text_sha256=sha256_hex(anchored_text.encode("utf-8")),
    )
    query = EvidenceComponentQuery(
        reference_id=str(reference.id),
        kind=AuthorityComponentKind.LEGAL_EVIDENCE,
    )
    reader = FakeAuthorityComponentReader({query: evidence})
    lookup = CitationLookup.from_component_reader(
        {str(reference.id): reference},
        reader=reader,
        pin=reader.pin(),
    )

    assert lookup.resolve(str(reference.id)).verbatim_text == anchored_text
    assert reader.loads == [query]


def test_operation_loads_selected_reference_then_its_evidence_pointwise(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    reference = authority_operation.legal_reference("ley-58-2003:art-27.2")
    anchored_text = authority_operation.legal_evidence("ley-58-2003:art-27.2").anchored_text
    reference_query = ReferenceComponentQuery(
        reference_id=str(reference.id),
        kind=AuthorityComponentKind.LEGAL_REFERENCE,
    )
    evidence_query = EvidenceComponentQuery(
        reference_id=str(reference.id),
        kind=AuthorityComponentKind.LEGAL_EVIDENCE,
    )
    evidence = PublishedLegalEvidence(
        legal_reference_id=str(reference.id),
        anchored_text=anchored_text,
        text_sha256=sha256_hex(anchored_text.encode("utf-8")),
    )
    reader = FakeAuthorityComponentReader({reference_query: reference, evidence_query: evidence})
    pin = reader.pin()
    operation = PinnedAuthorityOperation(cast(SQLiteAuthorityReader, reader), pin)
    lookup = CitationLookup.from_operation((str(reference.id),), operation=operation)

    assert lookup.resolve(str(reference.id)).verbatim_text == anchored_text
    assert reader.loads == [reference_query, evidence_query]
