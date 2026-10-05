"""Contract tests for IVA's translation of canonical mapping failures."""

from __future__ import annotations

from collections.abc import MutableMapping
from datetime import date
from decimal import Decimal
from typing import cast

import pytest

from cadrumo.core.revision_review import RevisionReviewStatus
from cadrumo.domain.calculations.registry.facts.payloads import MappingFactEntry, MappingFactPayload
from cadrumo.domain.calculations.registry.facts.resolution import ResolvedMappingFact
from cadrumo.domain.calculations.registry.facts.variants import FactOwnership
from cadrumo.domain.calculations.registry.schema_base import DateAxis
from cadrumo.domain.iva._fact_mapping_entries import IvaMappingSubject, mapping_entries
from cadrumo.domain.iva.errors import IvaValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SUBJECTS: tuple[IvaMappingSubject, ...] = (
    "IVA classification mapping",
    "IVA component mapping",
    "IVA statutory citation mapping",
)


def _resolved_mapping(entries: tuple[MappingFactEntry, ...]) -> ResolvedMappingFact:
    """Build an isolated typed resolution solely to exercise the map boundary."""
    return _resolved_payload(MappingFactPayload(entries=entries))


def _resolved_payload(payload: MappingFactPayload) -> ResolvedMappingFact:
    """Attach typed test payloads to valid non-legal resolution metadata."""
    return ResolvedMappingFact(
        fact_id="iva-test-mapping",
        variant_id="iva.test.variant",
        date_axis=DateAxis.FILING_PERIOD,
        effective_date=date(2025, 1, 1),
        valid_from=date(2025, 1, 1),
        review_status=RevisionReviewStatus.PENDING_REVIEW,
        ownership=FactOwnership.AUTHORED,
        authority_digest="a" * 64,
        source_variant_id="iva.test.variant",
        source_revision_ids=("iva.test.revision",),
        source_refs=("iva-test-source",),
        payload=payload,
    )


@pytest.mark.parametrize("subject", _SUBJECTS)
def test_mapping_entries_preserves_text_and_is_read_only(subject: IvaMappingSubject) -> None:
    resolved = _resolved_mapping((MappingFactEntry(key=" Mixed Key ", value="  Mixed Value  "),))

    entries = mapping_entries(resolved, subject=subject)

    assert entries == {" Mixed Key ": "  Mixed Value  "}
    mutable_entries = cast(MutableMapping[str, str], entries)
    with pytest.raises(TypeError):
        mutable_entries["new"] = "value"


@pytest.mark.parametrize(
    ("subject", "expected"),
    tuple((subject, f"{subject} entries must be string-to-string") for subject in _SUBJECTS),
)
def test_non_string_mapping_atoms_keep_iva_error_without_chaining(subject: IvaMappingSubject, expected: str) -> None:
    resolved = _resolved_mapping((MappingFactEntry(key=12, value=Decimal("1.25")),))

    with pytest.raises(IvaValidationError) as caught:
        mapping_entries(resolved, subject=subject)

    assert str(caught.value) == expected
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


@pytest.mark.parametrize(
    ("subject", "expected"),
    tuple((subject, f"duplicate {subject} key 'repeated'") for subject in _SUBJECTS),
)
def test_duplicate_mapping_keys_keep_subject_specific_iva_error(subject: IvaMappingSubject, expected: str) -> None:
    entries = (
        MappingFactEntry(key="repeated", value="first"),
        MappingFactEntry(key="repeated", value="second"),
    )
    # The validated payload model normally rejects this earlier. Construct only
    # this malformed internal payload so the mapper's duplicate refusal remains
    # covered at its own boundary.
    payload = MappingFactPayload.model_construct(entries=entries)
    resolved = _resolved_mapping((entries[0],)).model_copy(update={"payload": payload})

    with pytest.raises(IvaValidationError) as caught:
        mapping_entries(resolved, subject=subject)

    assert str(caught.value) == expected
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
