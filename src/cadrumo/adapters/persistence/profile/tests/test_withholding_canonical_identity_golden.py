"""Stored withholding identities and digests keep the exact bytes they were hashed from.

The expected bytes and digests here are written out by hand and were produced
apart from the code under test, so a change of JSON spelling fails them.
"""

from __future__ import annotations

import hashlib
import json
import math
from decimal import Decimal

import pytest

from cadrumo.adapters.persistence.profile.withholding_observation_workflow import _entries_digest
from cadrumo.application.aggregation.withholding_observation_service import (
    EconomicAllocation,
    SourceLiabilitySnapshot,
    WithholdingProjectionIdentity,
    WithholdingProjectionRole,
    withholding_canonical_json,
)

from .test_withholding_observation_workflow import _entry

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def test_the_spelling_sorts_compacts_escapes_and_admits_nan() -> None:
    value = {"z": "Ca\u00f1\u00f3n", "a": [1, 2.5, math.nan, None, True], "m": {"b": "\u20ac", "a": ""}}

    assert withholding_canonical_json(value) == (
        '{"a":[1,2.5,NaN,null,true],"m":{"a":"","b":"\\u20ac"},"z":"Ca\\u00f1\\u00f3n"}'
    )


def test_the_liability_identity_token_hashes_its_settlement_free_spelling() -> None:
    identity = WithholdingProjectionIdentity(
        source_kind="manual",
        source_object_id="fuente-\u00f1",
        source_revision_id="revision-1",
        recognition_event_id="recognition-1",
        settlement_event_id="payment-1",
        allocation_id="allocation-1",
        projection_role=WithholdingProjectionRole.RETENCION,
    )

    assert identity.token == _sha(
        '{"allocation_id":"allocation-1","projection_role":"retencion","recognition_event_id":"recognition-1",'
        '"source_kind":"manual","source_object_id":"fuente-\\u00f1","source_revision_id":"revision-1"}'
    )


def _liability() -> SourceLiabilitySnapshot:
    return SourceLiabilitySnapshot(
        source_kind="manual",
        source_object_id="fuente-\u00f1",
        source_revision_id="revision-1",
        liability_base=Decimal("100"),
        liability_withholding=Decimal("19"),
        liability_settlement=Decimal("81"),
    )


def test_the_source_guard_token_hashes_only_the_source_coordinates() -> None:
    assert _liability().source_token == _sha('{"source_kind":"manual","source_object_id":"fuente-\\u00f1"}')


def test_the_allocation_guard_identity_hashes_its_four_coordinates() -> None:
    allocation = EconomicAllocation(
        liability=_liability(),
        recognition_event_id="recognition-1",
        allocation_id="allocation-1",
        allocated_base=Decimal("100"),
        allocated_withholding=Decimal("19"),
        allocated_settlement=Decimal("81"),
    )

    assert allocation.guard_identity == _sha(
        '{"allocation_id":"allocation-1","recognition_event_id":"recognition-1",'
        '"source_kind":"manual","source_object_id":"fuente-\\u00f1"}'
    )


def test_the_entries_digest_sorts_rows_by_their_spelled_identity_and_is_order_free() -> None:
    first = _entry(suffix="a", retencion=True)
    second = _entry(suffix="b", retencion=False)

    digest = _entries_digest((second, first))

    assert digest == _entries_digest((first, second))
    rows = sorted(
        (entry.model_dump(mode="json") for entry in (first, second)),
        key=lambda row: json.dumps(row["identity"], sort_keys=True, separators=(",", ":"), ensure_ascii=True),
    )
    assert digest == _sha(json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
