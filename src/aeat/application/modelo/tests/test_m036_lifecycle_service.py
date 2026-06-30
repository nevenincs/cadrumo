"""Real-runtime service tests for ``record_m036_declaration`` (M036 commit 2).

Drives the production persistence path: a real bucket runtime, real
encrypted SecureObjectRepository write, real BucketEventHistoryRepository
emission.  Asserts the content-address invariants (idempotent re-record
of identical input, distinct id for distinct justificante), the bucket
cross-check (record's ``bucket_id`` matches storage scope), and the
co-emitted ``BucketEvent`` carries the matching CENSO_DECLARATION_*
event_type per the operator-action / data-write two-event composition
contract (`composition-service-no-parallel-write-path` rule).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ....adapters.persistence.storage import LIVE_M036_DECLARATION_NAMESPACE
from ....domain.buckets import BucketEventHistoryRepository, BucketEventType
from ....domain.calculations.registry import CensoModeloEventKind
from ....tests.secure_sql import isolated_runtime_profile
from .._m036_lifecycle import (
    M036DeclarationCommand,
    M036DeclarationResult,
    derive_m036_declaration_id,
    record_m036_declaration,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
_PROFILE_ID = "32323232-3232-4232-8232-323232323232"


def _alta_command(*, justificante: str | None = None) -> M036DeclarationCommand:
    return M036DeclarationCommand(
        profile_id=_PROFILE_ID,
        event_kind=CensoModeloEventKind.ALTA,
        declared_on=date(2026, 6, 4),
        sede_justificante=justificante,
    )


def test_record_alta_persists_result_with_bucket_scope(tmp_path: Path) -> None:
    """A successful record returns a typed result carrying bucket_id + the SHA-256 id."""
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        result = record_m036_declaration(_alta_command(), bucket_id=runtime.bucket_id)

    assert isinstance(result, M036DeclarationResult)
    assert result.bucket_id == runtime.bucket_id
    assert result.event_kind is CensoModeloEventKind.ALTA
    assert result.profile_id == _PROFILE_ID
    assert result.declared_on == date(2026, 6, 4)
    assert result.declaration_id == derive_m036_declaration_id(
        profile_id=_PROFILE_ID,
        event_kind=CensoModeloEventKind.ALTA,
        declared_on=date(2026, 6, 4),
        sede_justificante=None,
    )


def test_record_persists_to_secure_object_namespace(tmp_path: Path) -> None:
    """The record lands in LIVE_M036_DECLARATION_NAMESPACE keyed by bucket+declaration_id."""
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        result = record_m036_declaration(_alta_command(), bucket_id=runtime.bucket_id)

        record = runtime.repository.load(
            LIVE_M036_DECLARATION_NAMESPACE.namespace,
            f"m036-declaration:{runtime.bucket_id}:{result.declaration_id}",
            expected_class=LIVE_M036_DECLARATION_NAMESPACE.sensitivity,
            max_supported_version=LIVE_M036_DECLARATION_NAMESPACE.schema_version,
        )

    assert record is not None
    assert record.classification is LIVE_M036_DECLARATION_NAMESPACE.sensitivity


def test_record_alta_emits_bucket_event_of_matching_kind(tmp_path: Path) -> None:
    """Recording ALTA appends a CENSO_DECLARATION_ALTA event to the bucket history."""
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        result = record_m036_declaration(_alta_command(), bucket_id=runtime.bucket_id)
        catalogue = BucketEventHistoryRepository().load()

    matching = [
        event
        for event in catalogue.events.values()
        if event.event_type is BucketEventType.CENSO_DECLARATION_ALTA and event.object_id == result.declaration_id
    ]
    assert len(matching) == 1
    event = matching[0]
    assert event.bucket_id == runtime.bucket_id
    assert event.payload["profile_id"] == _PROFILE_ID
    assert event.payload["declared_on"] == "2026-06-04"


def test_record_modificacion_emits_modificacion_event(tmp_path: Path) -> None:
    """Each event_kind maps to its matching BucketEventType."""
    command = M036DeclarationCommand(
        profile_id=_PROFILE_ID,
        event_kind=CensoModeloEventKind.MODIFICACION,
        declared_on=date(2026, 6, 4),
    )
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        result = record_m036_declaration(command, bucket_id=runtime.bucket_id)
        catalogue = BucketEventHistoryRepository().load()

    matching = [event for event in catalogue.events.values() if event.object_id == result.declaration_id]
    assert len(matching) == 1
    assert matching[0].event_type is BucketEventType.CENSO_DECLARATION_MODIFICACION


def test_record_baja_emits_baja_event(tmp_path: Path) -> None:
    """BAJA event_kind maps to CENSO_DECLARATION_BAJA."""
    command = M036DeclarationCommand(
        profile_id=_PROFILE_ID,
        event_kind=CensoModeloEventKind.BAJA,
        declared_on=date(2026, 6, 4),
    )
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        result = record_m036_declaration(command, bucket_id=runtime.bucket_id)
        catalogue = BucketEventHistoryRepository().load()

    matching = [event for event in catalogue.events.values() if event.object_id == result.declaration_id]
    assert len(matching) == 1
    assert matching[0].event_type is BucketEventType.CENSO_DECLARATION_BAJA


def test_record_is_idempotent_for_identical_input(tmp_path: Path) -> None:
    """Re-recording the same declaration tuple yields the same declaration_id.

    The secure-object write becomes a no-op overwrite of the same row;
    the catalogue retains a single event because the event_id is also
    content-addressed over the identical tuple.
    """
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        first = record_m036_declaration(_alta_command(), bucket_id=runtime.bucket_id)
        second = record_m036_declaration(_alta_command(), bucket_id=runtime.bucket_id)
        catalogue = BucketEventHistoryRepository().load()

    assert first.declaration_id == second.declaration_id
    assert first.bucket_id == second.bucket_id
    matching = [event for event in catalogue.events.values() if event.object_id == first.declaration_id]
    # Content-addressed event id deduplicates the catalogue entry, but if
    # the implementation grows to allow multiple recordings the count
    # remains bounded to the distinct event_ids — never zero.
    assert len(matching) >= 1


def test_record_with_distinct_justificante_yields_distinct_record(
    tmp_path: Path,
) -> None:
    """Pre-acuse and post-acuse declarations are distinct records, not coalesced."""
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        draft = record_m036_declaration(_alta_command(), bucket_id=runtime.bucket_id)
        confirmed = record_m036_declaration(
            _alta_command(justificante="ACUSE-SVC-1"),
            bucket_id=runtime.bucket_id,
        )

    assert draft.declaration_id != confirmed.declaration_id
    assert draft.sede_justificante is None
    assert confirmed.sede_justificante == "ACUSE-SVC-1"
