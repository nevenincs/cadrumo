"""Legal-citation queries answered from the published authority generation."""

from __future__ import annotations

import pytest

from ....calculations.registry.authority import bundled_indexed_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CITED_PROVISION = "ley-35-2006:art-30"


def test_legal_reference_ids_enumerate_every_published_legal_declaration() -> None:
    with bundled_indexed_authority().operation() as operation:
        identities = operation.legal_reference_ids()

        assert identities, "the published generation enumerates no legal declarations"
        assert len(identities) == len(set(identities))
        assert _CITED_PROVISION in identities
        assert operation.legal_reference(_CITED_PROVISION).id == _CITED_PROVISION


def test_legal_reference_ids_exclude_public_source_declarations() -> None:
    with bundled_indexed_authority().operation() as operation:
        identities = set(operation.legal_reference_ids())
        snapshot = operation.snapshot("130", filing_year=2026, period="1T")

    assert snapshot.sources, "the fixture snapshot names no public source to compare against"
    assert identities.isdisjoint(snapshot.sources)


def test_a_verbatim_excerpt_of_the_published_evidence_is_grounded() -> None:
    with bundled_indexed_authority().operation() as operation:
        text = operation.legal_evidence(_CITED_PROVISION).anchored_text
        excerpt = text.strip()[:80]

        assert excerpt
        assert operation.legal_quotation_is_grounded(_CITED_PROVISION, excerpt) is True


def test_a_fabricated_or_empty_quotation_is_not_grounded() -> None:
    with bundled_indexed_authority().operation() as operation:
        assert operation.legal_quotation_is_grounded(_CITED_PROVISION, "texto que ninguna ley contiene jamás") is False
        assert operation.legal_quotation_is_grounded(_CITED_PROVISION, "   ") is False


def test_an_unpublished_citation_is_refused_rather_than_judged() -> None:
    with bundled_indexed_authority().operation() as operation, pytest.raises(LookupError):
        operation.legal_quotation_is_grounded("ley-0-0000:art-0", "cualquier texto")
