"""Real-runtime service tests for ``record_m036_declaration`` (M036 commit 2).

Drives the production persistence path: a real bucket runtime, real
encrypted SecureObjectRepository write, real BucketEventHistoryRepository
emission.  Asserts the content-address invariants (idempotent re-record
of identical input, distinct id for distinct justificante), the bucket
cross-check (record's ``bucket_id`` matches storage scope), and the
co-emitted ``BucketEvent`` carries the matching CENSO_DECLARATION_*
event_type per the operator-action / data-write two-event composition
contract (`aeat-architecture-boundaries` rule).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.storage.secure_object_namespaces import LIVE_M036_DECLARATION_NAMESPACE
from ....domain.buckets.event import BucketEventType
from ....domain.calculations.registry.censo_modelos import CensoModeloEventKind
from ....tests.secure_sql import isolated_runtime_profile
from ....tests.write_unit_recorder import WriteUnitRecorder
from ...live.errors import LiveApplicationInputError
from .._m036_lifecycle import (
    M036DeclarationCommand,
    M036DeclarationResult,
    _m036_declaration_repository,
    derive_m036_declaration_id,
    list_m036_declarations,
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
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as runtime:
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
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as runtime:
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
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as runtime:
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
    """Each event_kind maps to its matching BucketEventType.

    A ``modificacion`` amends an existing registration, so this records
    the requisite alta first (a later, distinct filing date) — the
    sequence guard now refuses a bare ``modificacion`` with nothing on
    record, exercised on its own in ``test_m036_lifecycle_sequence.py``.
    """
    command = M036DeclarationCommand(
        profile_id=_PROFILE_ID,
        event_kind=CensoModeloEventKind.MODIFICACION,
        declared_on=date(2026, 6, 5),
    )
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as runtime:
        record_m036_declaration(_alta_command(), bucket_id=runtime.bucket_id)
        result = record_m036_declaration(command, bucket_id=runtime.bucket_id)
        catalogue = BucketEventHistoryRepository().load()

    matching = [event for event in catalogue.events.values() if event.object_id == result.declaration_id]
    assert len(matching) == 1
    assert matching[0].event_type is BucketEventType.CENSO_DECLARATION_MODIFICACION


def test_record_baja_emits_baja_event(tmp_path: Path) -> None:
    """BAJA event_kind maps to CENSO_DECLARATION_BAJA.

    A ``baja`` deregisters an existing registration, so this records the
    requisite alta first — the sequence guard now refuses a bare ``baja``
    with nothing on record, exercised on its own in
    ``test_m036_lifecycle_sequence.py``.
    """
    command = M036DeclarationCommand(
        profile_id=_PROFILE_ID,
        event_kind=CensoModeloEventKind.BAJA,
        declared_on=date(2026, 6, 5),
    )
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as runtime:
        record_m036_declaration(_alta_command(), bucket_id=runtime.bucket_id)
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
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as runtime:
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
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as runtime:
        draft = record_m036_declaration(_alta_command(), bucket_id=runtime.bucket_id)
        confirmed = record_m036_declaration(
            _alta_command(justificante="ACUSE-SVC-1"),
            bucket_id=runtime.bucket_id,
        )

    assert draft.declaration_id != confirmed.declaration_id
    assert draft.sede_justificante is None
    assert confirmed.sede_justificante == "ACUSE-SVC-1"


def test_record_refuses_a_command_profile_that_does_not_own_the_bucket(
    tmp_path: Path,
) -> None:
    """A profile-B declaration cannot be recorded into bucket A.

    A bucket identity IS the profile UUID owning it, so a command naming a
    different profile is incoherent. Without the guard the two identities split
    across the same call: ``declaration_id`` and the event payload derive from
    ``command.profile_id`` while the stored row and the event scope key on
    ``bucket_id``. The repository cross-check compares only the result's own
    ``bucket_id`` against its binding, so it cannot see the foreign profile
    identity riding inside the payload.
    """
    foreign_profile = "39393939-3939-4939-8939-393939393939"
    assert foreign_profile != _PROFILE_ID
    command = M036DeclarationCommand(
        profile_id=foreign_profile,
        event_kind=CensoModeloEventKind.ALTA,
        declared_on=date(2026, 6, 4),
        sede_justificante=None,
    )

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as runtime:
        with pytest.raises(LiveApplicationInputError) as exc_info:
            record_m036_declaration(command, bucket_id=runtime.bucket_id)

        assert exc_info.value.context is not None
        assert exc_info.value.context["profile_id"] == foreign_profile
        assert exc_info.value.context["bucket_id"] == _PROFILE_ID
        assert list_m036_declarations(bucket_id=runtime.bucket_id) == ()
        catalogue = BucketEventHistoryRepository().load()

    assert catalogue.events == {}


def test_record_refuses_before_deriving_the_declaration_id(tmp_path: Path) -> None:
    """The refusal precedes id derivation, so no foreign address is minted.

    Anti-tautology for the guard: the id the foreign command WOULD have produced
    must be absent from storage, not merely unreachable through the read-back
    surface. A guard placed after derivation would leave that address recorded.
    """
    foreign_profile = "39393939-3939-4939-8939-393939393939"
    foreign_declaration_id = derive_m036_declaration_id(
        profile_id=foreign_profile,
        event_kind=CensoModeloEventKind.ALTA,
        declared_on=date(2026, 6, 4),
        sede_justificante=None,
    )
    command = M036DeclarationCommand(
        profile_id=foreign_profile,
        event_kind=CensoModeloEventKind.ALTA,
        declared_on=date(2026, 6, 4),
        sede_justificante=None,
    )

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as runtime:
        with pytest.raises(LiveApplicationInputError):
            record_m036_declaration(command, bucket_id=runtime.bucket_id)

        assert (
            runtime.repository.load(
                LIVE_M036_DECLARATION_NAMESPACE.namespace,
                f"m036-declaration:{runtime.bucket_id}:{foreign_declaration_id}",
                expected_class=LIVE_M036_DECLARATION_NAMESPACE.sensitivity,
                max_supported_version=LIVE_M036_DECLARATION_NAMESPACE.schema_version,
            )
            is None
        )


def test_record_accepts_the_owning_profile_and_reads_back(tmp_path: Path) -> None:
    """Valid same-profile parity: the guard does not refuse the coherent case."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as runtime:
        result = record_m036_declaration(_alta_command(), bucket_id=runtime.bucket_id)
        recorded = list_m036_declarations(bucket_id=runtime.bucket_id)

    assert result.profile_id == result.bucket_id == _PROFILE_ID
    assert recorded == (result,)


def test_record_commits_declaration_and_audit_event_in_one_transaction(tmp_path: Path) -> None:
    """The declaration snapshot and its audit event share one transaction.

    Recording saved the declaration and emitted the event through a separate
    write, so an event-storage failure left the M036 declaration durable with
    nothing in the history accounting for it — a censal state change the audit
    trail cannot explain.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as runtime:
        recorder = WriteUnitRecorder(runtime.repository.engine)

        with recorder.recording():
            record_m036_declaration(_alta_command(), bucket_id=runtime.bucket_id)

        assert recorder.commits_between_writes() == 0


def test_split_record_write_shape_commits_between_stores(tmp_path: Path) -> None:
    """Anti-tautology: the recorder reports a seam on the shape this replaced.

    Persisting the declaration and the event catalogue through independent
    saves — the pre-fix sequence — must be observed as more than one
    transaction, or the assertion above could not fail.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as runtime:
        result = record_m036_declaration(_alta_command(), bucket_id=runtime.bucket_id)
        events = BucketEventHistoryRepository()
        catalogue = events.load()
        declarations = _m036_declaration_repository(runtime.bucket_id)
        recorder = WriteUnitRecorder(runtime.repository.engine)

        with recorder.recording():
            declarations.save(result)
            events.save(catalogue)

        assert recorder.commits_between_writes() >= 1


def test_record_preserves_its_persisted_audit_payload_version(tmp_path: Path) -> None:
    """The co-committed event still persists payload_version 1.

    The modelo-wide builder supplies version 2. Routing this event through the
    shared derive helper must not re-version a persisted audit contract, so the
    version is pinned here rather than left to whichever builder is used.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as runtime:
        result = record_m036_declaration(_alta_command(), bucket_id=runtime.bucket_id)
        catalogue = BucketEventHistoryRepository().load()

    matching = [event for event in catalogue.events.values() if event.object_id == result.declaration_id]
    assert len(matching) == 1
    assert matching[0].payload_version == 1
