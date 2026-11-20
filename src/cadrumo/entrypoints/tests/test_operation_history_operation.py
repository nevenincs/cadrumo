"""The registered operation history read, over the real journal and a real encrypted profile."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.operations.secure_references import (
    OperationSecureReferenceRepository,
    operation_secure_reference_repository,
)
from cadrumo.adapters.persistence.operations.tests.profile_operation_supervisor import (
    SupervisedProfile,
    supervised_profile,
)
from cadrumo.adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from cadrumo.application.operation_history.list_operation import (
    OPERATIONS_HISTORY_LIMIT_MAX,
    OPERATIONS_HISTORY_LIST_DEFINITION_ID,
    OperationHistoryCursorV1,
    OperationHistoryListRequest,
    OperationHistoryResultV1,
    OperationHistoryRowV1,
    build_operation_history_list_definition,
    build_operation_history_list_registration,
    read_operation_history,
)
from cadrumo.application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from cadrumo.application.operations.capabilities import OperationRequestStoragePolicy
from cadrumo.application.operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from cadrumo.application.operations.operation_definition import OperationDefinition
from cadrumo.application.operations.persistence.events import OperationPhaseEvent, OperationTerminalEvent
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot
from cadrumo.application.operations.persistence.leases import OperationOwnerLease, operation_conflict_scope_reference
from cadrumo.application.operations.provenance import OperationAdmissionProvenance
from cadrumo.application.operations.registry import OperationPublicDefinitionRegistrationV1
from cadrumo.application.persistence_errors import PersistenceDegradationError
from cadrumo.application.user_profile.access_contracts import ProfileAccessBinding
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.hashing import content_hash_hex
from cadrumo.core.operations import (
    OperationDurability,
    OperationEffect,
    OperationFrontendProjection,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.core.paths import effective_storage_root
from cadrumo.core.storage_taxonomy import StorageCategory
from cadrumo.core.storage_taxonomy_locations import storage_location
from cadrumo.entrypoints.operation_history_composition import compose_operation_history_ports
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import (
    AccessAction,
    AccessScope,
    Availability,
    DisclosureCategory,
    OperationAccessRequest,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_T0 = datetime(2026, 11, 1, 9, tzinfo=UTC)
_NOW = datetime(2026, 11, 20, 12, tzinfo=UTC)
_MARKER = "history-private-marker-never-in-a-row"
_LEDGER_READS = ("list", "view", "status", "check", "history", "track", "preflight", "review")


def _composed() -> tuple[tuple[OperationDefinition, OperationPublicDefinitionRegistrationV1], ...]:
    definition = build_operation_history_list_definition(compose_operation_history_ports)
    return ((definition, build_operation_history_list_registration(definition)),)


@dataclass(frozen=True, slots=True)
class _Journal:
    """The shared journal and the exact profile's admission custody a test writes into."""

    profile_id: UUID
    operands: OperationSecureReferenceRepository

    @property
    def directory(self) -> Path:
        return effective_storage_root() / storage_location(StorageCategory.OPERATION_JOURNAL).subpath

    def provenance(
        self, identity: OperationIdentity, *, profile_id: UUID | None = None
    ) -> OperationAdmissionProvenance:
        owner = self.profile_id if profile_id is None else profile_id
        return OperationAdmissionProvenance(
            identity=identity,
            profile_binding=ProfileAccessBinding(
                profile_id=owner,
                installation_id=uuid4(),
                os_owner_id=_MARKER,
                custody_generation=1,
                dek_epoch=uuid4(),
            ),
            approved_scope=AccessScope(
                operations=frozenset({identity.definition_id}),
                actions=frozenset({AccessAction.SUBMIT}),
                disclosures=frozenset(),
                periods=None,
                allow_period_independent=True,
                allow_delegation=False,
            ),
            admitted_request=OperationAccessRequest(
                profile_id=owner,
                definition_id=identity.definition_id,
                action=AccessAction.SUBMIT,
                frontend=OperationFrontendProjection.CLI,
                periods=frozenset(),
                period_independent=True,
                destination_id=uuid4(),
            ),
            authority_generation=content_hash_hex({"publication": "history-test"}),
            request_fingerprint=content_hash_hex({"request": _MARKER}),
        )

    def admit(self, identity: OperationIdentity, *, profile_id: UUID | None = None) -> str:
        """Store this invocation's admission record in the profile's custody and name it."""
        return asyncio.run(self.operands.put(self.provenance(identity, profile_id=profile_id), written_at=_NOW))

    def identity(
        self, number: int, *, definition_id: str | None = None, subject_ref: str | None = None
    ) -> OperationIdentity:
        """The invocation identity of the ``number``-th record; it names this profile unless told otherwise.

        Each record defaults to a definition of its own: records of one definition and subject share one lease scope.
        """
        return OperationIdentity(
            operation_id=f"{number:x}".rjust(64, "0"),
            definition_id=definition_id or f"ledger.{_LEDGER_READS[number % len(_LEDGER_READS)]}",
            subject_ref=subject_ref or profile_operation_subject(str(self.profile_id)),
        )

    def write(
        self, identity: OperationIdentity, *, started_at: datetime, reference: str | None, state: str = "running"
    ) -> None:
        """Create one real journal record at its initial revision, as a profile worker would have."""
        snapshot = _snapshot(identity, started_at=started_at, reference=reference, state=state)
        lease = OperationOwnerLease(
            operation_id=identity.operation_id,
            scope_ref=operation_conflict_scope_reference(
                definition_id=identity.definition_id, subject_ref=identity.subject_ref
            ),
            owner_id="b" * 64,
            token="c" * 64,
            acquired_at=started_at,
            expires_at=started_at + timedelta(hours=1),
        )
        root = effective_storage_root()
        asyncio.run(OperationLeaseFilesystemRepository(storage_root=root).acquire(lease, observed_at=started_at))
        asyncio.run(OperationJournalRepository(storage_root=root).create(snapshot, lease=lease))

    def admitted(
        self, number: int, *, started_at: datetime, state: str = "running", definition_id: str | None = None
    ) -> None:
        """Write a record whose admission record this profile's custody holds and names."""
        identity = self.identity(number, definition_id=definition_id)
        self.write(identity, started_at=started_at, reference=self.admit(identity), state=state)


def _snapshot(
    identity: OperationIdentity, *, started_at: datetime, reference: str | None, state: str
) -> OperationPersistedSnapshot:
    terminal = {
        "succeeded": (OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE),
        "refused": (OperationTerminalCondition.REFUSED, OperationEffect.NONE),
        "interrupted": (OperationTerminalCondition.INTERRUPTED, OperationEffect.UNKNOWN),
    }.get(state)
    updated_at = started_at + timedelta(minutes=1)
    receipt: OperationTerminalReceipt | None = None
    events: tuple[OperationPhaseEvent | OperationTerminalEvent, ...]
    if terminal is None:
        settling = state == "settling"
        lifecycle = OperationLifecycle.SETTLING if settling else OperationLifecycle.RUNNING
        effect = OperationEffect.UNKNOWN if settling else OperationEffect.NONE
        phase_code: str | None = "phase.read"
        events = (
            OperationPhaseEvent(
                identity=identity,
                revision=0,
                sequence=1,
                timestamp=updated_at,
                code="phase.read",
                phase_code="phase.read",
            ),
        )
    else:
        condition, effect = terminal
        lifecycle = OperationLifecycle.TERMINAL
        phase_code = None
        receipt = OperationTerminalReceipt(
            identity=identity,
            revision=0,
            condition=condition,
            effect=effect,
            settled_at=updated_at,
            result_ref="result:private-reference" if condition is OperationTerminalCondition.SUCCEEDED else None,
            refusal_ref="REFUSED_PROFILE_ACCESS" if condition is OperationTerminalCondition.REFUSED else None,
        )
        events = (
            OperationTerminalEvent(
                identity=identity,
                revision=0,
                sequence=1,
                timestamp=updated_at,
                code="operation.terminal",
                receipt=receipt,
            ),
        )
    return OperationPersistedSnapshot(
        identity=identity,
        definition_contract_digest="c" * 64,
        request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
        request_reference="d" * 64,
        credential_free_request_json='{"request":"' + _MARKER + '"}',
        admission_provenance_reference=reference,
        revision=0,
        lifecycle=lifecycle,
        terminal_condition=None if receipt is None else receipt.condition,
        effect=effect,
        phase_code=phase_code,
        started_at=started_at,
        updated_at=updated_at,
        execution_deadline=None,
        cleanup_deadline=None,
        cancellation_requested_at=None,
        cancellation_acknowledged_at=None,
        cancellation_deferred=False,
        event_cursor=1,
        terminal_receipt=receipt,
        events=events,
    )


def _journal(profile: SupervisedProfile) -> _Journal:
    return _Journal(
        profile_id=profile.profile_id,
        operands=operation_secure_reference_repository(
            objects=secure_object_repository_for_bucket(str(profile.profile_id))
        ),
    )


def _read(
    profile: SupervisedProfile, *, limit: int = 100, after: OperationHistoryCursorV1 | None = None
) -> OperationHistoryResultV1:
    return asyncio.run(
        read_operation_history(
            compose_operation_history_ports(str(profile.profile_id)),
            profile_id=profile.profile_id,
            limit=limit,
            after=after,
            observed_at=_NOW,
        )
    )


def test_an_installation_with_no_journal_has_a_genuinely_empty_history(tmp_path: Path) -> None:
    with supervised_profile(tmp_path / "profile", _composed()) as profile:
        empty = _read(profile)

    assert (empty.runs, empty.run_count, empty.next_cursor) == ((), 0, None)
    assert (empty.unreadable_records, empty.unverifiable_records) == (0, 0)


def test_the_profile_runs_are_listed_newest_first_with_their_state_kept_verbatim(tmp_path: Path) -> None:
    with supervised_profile(tmp_path / "profile", _composed()) as profile:
        journal = _journal(profile)
        journal.admitted(1, started_at=_T0, state="running")
        journal.admitted(
            2, definition_id="live.notifications.latest", started_at=_T0 + timedelta(hours=1), state="settling"
        )
        journal.admitted(3, definition_id="ledger.add", started_at=_T0 + timedelta(hours=2), state="succeeded")
        journal.admitted(
            4, definition_id="auth.session.acquire", started_at=_T0 + timedelta(hours=3), state="interrupted"
        )
        journal.admitted(5, definition_id="modelo.work.verify", started_at=_T0 + timedelta(hours=4), state="refused")
        listed = _read(profile)

    assert [row.operation_id[-1] for row in listed.runs] == ["5", "4", "3", "2", "1"]
    assert listed.run_count == 5
    assert (listed.unreadable_records, listed.unverifiable_records) == (0, 0)
    by_number = {row.operation_id[-1]: row for row in listed.runs}
    assert by_number["1"].lifecycle is OperationLifecycle.RUNNING
    assert by_number["1"].phase_code == "phase.read"
    assert by_number["1"].receipt is None
    assert by_number["2"].lifecycle is OperationLifecycle.SETTLING
    assert by_number["2"].effect is OperationEffect.UNKNOWN
    assert by_number["2"].register_page == "aeat-sync"
    assert by_number["3"].register_page == "ledger"
    assert by_number["3"].receipt is not None
    assert by_number["3"].receipt.condition is OperationTerminalCondition.SUCCEEDED
    assert by_number["3"].receipt.result_stored
    assert by_number["4"].effect is OperationEffect.UNKNOWN
    assert by_number["4"].receipt is not None
    assert by_number["4"].receipt.condition is OperationTerminalCondition.INTERRUPTED
    assert by_number["4"].receipt.effect is OperationEffect.UNKNOWN
    assert by_number["5"].receipt is not None
    assert by_number["5"].receipt.refusal_ref == "REFUSED_PROFILE_ACCESS"
    assert by_number["5"].receipt.result_stored is False


def test_a_row_carries_no_request_result_or_private_reference(tmp_path: Path) -> None:
    with supervised_profile(tmp_path / "profile", _composed()) as profile:
        journal = _journal(profile)
        journal.admitted(1, started_at=_T0, state="succeeded")
        listed = _read(profile)

    serialized = listed.model_dump_json()
    assert _MARKER not in serialized
    assert "private-reference" not in serialized
    assert str(profile.profile_id) not in serialized.replace(f'"profile_id":"{profile.profile_id}"', "")
    private_fields = {
        "subject_ref",
        "request_reference",
        "credential_free_request_json",
        "result_ref",
        "diagnostic_ref",
    }
    assert private_fields.isdisjoint(OperationHistoryRowV1.model_fields)
    assert private_fields.isdisjoint(OperationHistoryResultV1.model_fields)


def test_another_profiles_runs_are_neither_listed_nor_counted(tmp_path: Path) -> None:
    other = uuid4()
    with supervised_profile(tmp_path / "profile", _composed()) as profile:
        journal = _journal(profile)
        journal.admitted(1, started_at=_T0, state="succeeded")
        # Admitted by another profile's worker: its admission record lives in that profile's own custody.
        foreign = journal.identity(2, subject_ref=profile_operation_subject(str(other)))
        journal.write(
            foreign,
            started_at=_T0 + timedelta(hours=1),
            reference=content_hash_hex(journal.provenance(foreign, profile_id=other).model_dump(mode="json")),
        )
        # A run keyed by something other than a profile, admitted by a profile this custody does not know.
        elsewhere = journal.identity(3, definition_id="workflow.run.read", subject_ref="0123456789abcdef")
        journal.write(
            elsewhere,
            started_at=_T0 + timedelta(hours=2),
            reference=content_hash_hex(journal.provenance(elsewhere, profile_id=other).model_dump(mode="json")),
        )
        listed = _read(profile)

    assert [row.operation_id[-1] for row in listed.runs] == ["1"]
    assert listed.run_count == 1
    assert (listed.unreadable_records, listed.unverifiable_records) == (0, 0)


def test_a_worker_bound_to_another_profile_refuses_to_read_the_history(tmp_path: Path) -> None:
    with supervised_profile(tmp_path / "profile", _composed()) as profile:
        ports = compose_operation_history_ports(str(profile.profile_id))
        with pytest.raises(ProfileAccessRefusedError) as refused:
            asyncio.run(read_operation_history(ports, profile_id=uuid4(), limit=10, after=None, observed_at=_NOW))
        settled = profile.run(
            definition_id=OPERATIONS_HISTORY_LIST_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(uuid4())),
            payload=OperationHistoryListRequest(profile_id=uuid4()),
        )

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
    assert settled.receipt.condition is OperationTerminalCondition.REFUSED
    assert settled.receipt.result_ref is None


def test_pages_continue_from_the_cursor_without_repeating_or_skipping_a_run(tmp_path: Path) -> None:
    with supervised_profile(tmp_path / "profile", _composed()) as profile:
        journal = _journal(profile)
        for number in range(1, 6):
            journal.admitted(number, started_at=_T0 + timedelta(hours=number), state="succeeded")
        # Two runs begun in the same instant keep one stable order by identity.
        journal.admitted(6, started_at=_T0 + timedelta(hours=5), state="succeeded")
        first = _read(profile, limit=2)
        second = _read(profile, limit=2, after=first.next_cursor)
        third = _read(profile, limit=2, after=second.next_cursor)
        past_the_oldest = _read(profile, limit=2, after=third.runs[-1].cursor)

    pages = (first, second, third)
    assert [len(page.runs) for page in pages] == [2, 2, 2]
    assert [page.next_cursor is not None for page in pages] == [True, True, False]
    assert past_the_oldest.runs == ()
    assert past_the_oldest.next_cursor is None
    assert all(page.run_count == 6 for page in pages)
    listed = [row.operation_id[-1] for page in pages for row in page.runs]
    assert listed == ["6", "5", "4", "3", "2", "1"]
    assert first.next_cursor == first.runs[-1].cursor


def test_an_unreadable_record_is_counted_and_never_makes_the_history_look_empty(tmp_path: Path) -> None:
    with supervised_profile(tmp_path / "profile", _composed()) as profile:
        journal = _journal(profile)
        journal.directory.mkdir(parents=True, exist_ok=True)
        (journal.directory / f"{'9' * 64}.json").write_text("{not a journal record", encoding="utf-8")
        only_damage = _read(profile)
        journal.admitted(1, started_at=_T0, state="succeeded")
        both = _read(profile)

    assert only_damage.runs == ()
    assert only_damage.run_count == 0
    assert only_damage.unreadable_records == 1
    assert [row.operation_id[-1] for row in both.runs] == ["1"]
    assert both.unreadable_records == 1


def test_a_run_that_names_this_profile_without_proof_is_counted_as_unverifiable(tmp_path: Path) -> None:
    with supervised_profile(tmp_path / "profile", _composed()) as profile:
        journal = _journal(profile)
        journal.admitted(1, started_at=_T0, state="succeeded")
        # Names this profile and holds no admission reference at all.
        journal.write(journal.identity(2), started_at=_T0 + timedelta(hours=1), reference=None)
        # Names this profile; its admission record is not in this profile's custody.
        journal.write(journal.identity(3), started_at=_T0 + timedelta(hours=2), reference="e" * 64)
        # Its admission record is held but names another invocation.
        journal.write(
            journal.identity(4),
            started_at=_T0 + timedelta(hours=3),
            reference=journal.admit(journal.identity(0xF)),
        )
        # Its admission record is held and names a different profile.
        journal.write(
            journal.identity(5),
            started_at=_T0 + timedelta(hours=4),
            reference=journal.admit(journal.identity(5), profile_id=uuid4()),
        )
        listed = _read(profile)

    assert [row.operation_id[-1] for row in listed.runs] == ["1"]
    assert listed.unverifiable_records == 4
    assert listed.unreadable_records == 0


def test_a_journal_that_cannot_be_scanned_refuses_instead_of_reading_as_empty(tmp_path: Path) -> None:
    with supervised_profile(tmp_path / "profile", _composed()) as profile:
        journal = _journal(profile)
        journal.directory.parent.mkdir(parents=True, exist_ok=True)
        journal.directory.write_text("not a directory", encoding="utf-8")
        with pytest.raises(PersistenceDegradationError):
            _read(profile)


def test_the_registered_read_settles_with_no_effect_and_projects_the_page(tmp_path: Path) -> None:
    with supervised_profile(tmp_path / "profile", _composed()) as profile:
        journal = _journal(profile)
        journal.admitted(1, started_at=_T0, state="settling")
        journal.admitted(2, started_at=_T0 + timedelta(hours=1), state="succeeded")
        settled = profile.run(
            definition_id=OPERATIONS_HISTORY_LIST_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(profile.profile_id)),
            payload=OperationHistoryListRequest(profile_id=profile.profile_id, limit=1),
        )
        page = profile.result(settled, OperationHistoryResultV1)

    assert settled.receipt.condition is OperationTerminalCondition.SUCCEEDED
    assert settled.receipt.effect is OperationEffect.NONE
    assert page.profile_id == profile.profile_id
    assert [row.operation_id[-1] for row in page.runs] == ["2"]
    assert page.run_count == 2
    assert page.next_cursor == page.runs[0].cursor


def test_the_history_read_is_ephemeral_so_listing_adds_no_run_to_the_journal() -> None:
    contract = build_operation_history_list_registration(
        build_operation_history_list_definition(compose_operation_history_ports)
    ).contract

    assert contract.durability is OperationDurability.EPHEMERAL
    assert contract.permitted_effects == frozenset({OperationEffect.NONE})


def test_access_is_the_signed_in_profile_own_period_independent_read(tmp_path: Path) -> None:
    with supervised_profile(tmp_path / "profile", _composed()) as profile:
        request = OperationRequest(
            definition_id=OPERATIONS_HISTORY_LIST_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(profile.profile_id)),
            payload=OperationHistoryListRequest(profile_id=profile.profile_id),
        )
        context = OperationAccessContext(
            profile_id=profile.profile_id,
            destination_id=uuid4(),
            action=AccessAction.RESULT,
            frontend=OperationFrontendProjection.CLI,
            contract=profile.registry.lookup_public_contract(OPERATIONS_HISTORY_LIST_DEFINITION_ID),
            published_authority=Availability.AVAILABLE,
        )
        resolved = resolve_operation_access(registry=profile.registry, request=request, context=context)
        with pytest.raises(ProfileAccessRefusedError) as foreign:
            resolve_operation_access(
                registry=profile.registry, request=request, context=replace(context, profile_id=uuid4())
            )

    assert resolved.request.period_independent
    assert not resolved.policy.requires_all_periods
    assert {item.category for item in resolved.policy.disclosures} == {DisclosureCategory.PROFILE_VALUES}
    assert foreign.value.reason is AccessDenialCode.PROFILE_MISMATCH


@pytest.mark.parametrize(
    "fields",
    (
        {"limit": 0},
        {"limit": OPERATIONS_HISTORY_LIMIT_MAX + 1},
        {"limit": "5"},
        {"after": {"started_at": "2026-11-01T09:00:00", "operation_id": "a" * 64}},
        {"after": {"started_at": "2026-11-01T09:00:00Z", "operation_id": "short"}},
        {"include": "payloads"},
    ),
)
def test_the_request_is_strict_and_bounded(fields: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        OperationHistoryListRequest.model_validate({"profile_id": uuid4(), **fields})


def test_the_result_refuses_a_page_that_is_out_of_order_or_larger_than_the_profile_history() -> None:
    row = OperationHistoryRowV1(
        operation_id="a" * 64,
        definition_id="ledger.list",
        register_page="ledger",
        started_at=_T0,
        updated_at=_T0,
        lifecycle=OperationLifecycle.RUNNING,
        effect=OperationEffect.NONE,
        phase_code=None,
        cancellation_requested=False,
        receipt=None,
    )
    older = row.model_copy(update={"operation_id": "b" * 64, "started_at": _T0 - timedelta(hours=1)})
    fields = {
        "profile_id": uuid4(),
        "observed_at": _NOW,
        "next_cursor": None,
        "unreadable_records": 0,
        "unverifiable_records": 0,
    }

    OperationHistoryResultV1.model_validate({**fields, "runs": (row, older), "run_count": 2})
    with pytest.raises(ValidationError):
        OperationHistoryResultV1.model_validate({**fields, "runs": (older, row), "run_count": 2})
    with pytest.raises(ValidationError):
        OperationHistoryResultV1.model_validate({**fields, "runs": (row, older), "run_count": 1})
    with pytest.raises(ValidationError):
        OperationHistoryResultV1.model_validate({**fields, "runs": (row,), "run_count": 2, "next_cursor": older.cursor})
