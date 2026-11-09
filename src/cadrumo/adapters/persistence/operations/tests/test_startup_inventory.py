"""Startup inventory over canonical credential-free operation journals."""

from __future__ import annotations

import asyncio
import json
from datetime import timedelta
from pathlib import Path
from typing import Any, override
from uuid import UUID

import pytest
from pydantic import ValidationError

import cadrumo.adapters.persistence.operations.journal as journal_module
from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.operations.secure_references import operation_secure_reference_repository
from cadrumo.adapters.persistence.storage.errors import RepositoryError
from cadrumo.application.operations.composition import compose_operation_services
from cadrumo.application.operations.models import OperationId, OperationIdentity, OperationTerminalReceipt
from cadrumo.application.operations.persistence.events import OperationTerminalEvent
from cadrumo.application.operations.persistence.journal import (
    OperationPersistedSnapshot,
    OperationRecoveryInventoryDisposition,
)
from cadrumo.application.operations.persistence.leases import (
    OperationLeaseDisposition,
    OperationOwnerLease,
    operation_conflict_scope_reference,
)
from cadrumo.application.operations.tests.authority_test_support import unread_authority_operation
from cadrumo.application.user_profile.censal_operation import CENSAL_OPERATION_DEFINITION_ID
from cadrumo.application.user_profile.censal_readback import read_latest_censal_observation
from cadrumo.core.errors.hierarchy import InternalInvariantError
from cadrumo.core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition

from .supervisor_test_support import WaitingExecutor, supervisor_registry
from .test_journal import STARTED, journal_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _journal_path(root: Path, operation_id: str) -> Path:
    return root / "operation-journals" / f"{operation_id}.json"


async def _create(
    root: Path, operation_id: str, *, terminal: bool = False, definition_id: str = "test.operation"
) -> None:
    """Create one real journal and owner lease through their canonical adapters."""
    journal = OperationJournalRepository(storage_root=root)
    initial_template = journal_snapshot(revision=0, sequence=1)
    identity = OperationIdentity(
        operation_id=operation_id, definition_id=definition_id, subject_ref=f"subject:{operation_id[0]}"
    )
    event = initial_template.events[0].model_copy(update={"identity": identity})
    initial = OperationPersistedSnapshot.model_validate(
        initial_template.model_copy(update={"identity": identity, "events": (event,)}).model_dump(mode="python")
    )
    lease = OperationOwnerLease(
        operation_id=operation_id,
        scope_ref=operation_conflict_scope_reference(
            definition_id=identity.definition_id, subject_ref=identity.subject_ref
        ),
        owner_id="e" * 64,
        token="f" * 64,
        acquired_at=STARTED,
        expires_at=STARTED + timedelta(hours=1),
    )
    acquired = await OperationLeaseFilesystemRepository(storage_root=root).acquire(lease, observed_at=STARTED)
    assert acquired.disposition is OperationLeaseDisposition.ACQUIRED
    await journal.create(initial, lease=lease)
    if terminal:
        settled_at = STARTED + timedelta(minutes=1)
        receipt = OperationTerminalReceipt(
            identity=identity,
            revision=1,
            condition=OperationTerminalCondition.INTERRUPTED,
            effect=OperationEffect.NONE,
            settled_at=settled_at,
        )
        terminal_event = OperationTerminalEvent(
            identity=identity,
            revision=1,
            sequence=2,
            timestamp=settled_at,
            code="operation.terminal",
            receipt=receipt,
        )
        successor = OperationPersistedSnapshot.model_validate(
            initial.model_copy(
                update={
                    "revision": 1,
                    "lifecycle": OperationLifecycle.TERMINAL,
                    "terminal_condition": receipt.condition,
                    "effect": receipt.effect,
                    "updated_at": settled_at,
                    "event_cursor": 2,
                    "events": (terminal_event,),
                    "terminal_receipt": receipt,
                }
            ).model_dump(mode="python")
        )
        await journal.commit_settlement(successor, expected_revision=0, lease=lease)


def test_inventory_pages_include_terminal_and_refused_entries_without_changing_files(tmp_path: Path) -> None:
    ids = tuple(character * 64 for character in "abcd")

    async def exercise() -> None:
        for operation_id in ids:
            await _create(tmp_path, operation_id, terminal=operation_id == ids[1])
        corrupt = _journal_path(tmp_path, ids[2])
        current_document = json.loads(corrupt.read_text(encoding="utf-8"))
        current_document["history"] = []
        corrupt.write_text(json.dumps(current_document), encoding="utf-8")
        old_format = _journal_path(tmp_path, ids[3])
        old_document = json.loads(old_format.read_text(encoding="utf-8"))
        old_document["snapshot"]["schema_version"] = 6
        old_format.write_text(json.dumps(old_document), encoding="utf-8")
        original_bytes = {operation_id: _journal_path(tmp_path, operation_id).read_bytes() for operation_id in ids}

        journal = OperationJournalRepository(storage_root=tmp_path)
        first = await journal.inventory_page(after=None, limit=2)
        second = await journal.inventory_page(after=first.next_cursor, limit=2)
        assert tuple(entry.operation_id for entry in first.entries) == ids[:2]
        assert tuple(entry.disposition for entry in first.entries) == (
            OperationRecoveryInventoryDisposition.NONTERMINAL,
            OperationRecoveryInventoryDisposition.TERMINAL,
        )
        assert tuple(entry.definition_id for entry in first.entries) == ("test.operation", "test.operation")
        assert first.next_cursor == ids[1] and first.has_more
        terminal_page = await journal.inventory_page(after=ids[0], limit=1)
        assert tuple(entry.operation_id for entry in terminal_page.entries) == (ids[1],)
        assert terminal_page.next_cursor == ids[1] and terminal_page.has_more
        assert tuple(entry.operation_id for entry in second.entries) == ids[2:]
        assert tuple(entry.disposition for entry in second.entries) == (
            OperationRecoveryInventoryDisposition.REFUSED,
            OperationRecoveryInventoryDisposition.REFUSED,
        )
        assert tuple(entry.definition_id for entry in second.entries) == (None, None), "an unread record names nothing"
        assert second.next_cursor == ids[3] and not second.has_more
        assert (await journal.inventory_page(after=second.next_cursor, limit=2)).entries == ()
        assert {
            operation_id: _journal_path(tmp_path, operation_id).read_bytes() for operation_id in ids
        } == original_bytes

        services = compose_operation_services(
            registry=supervisor_registry(
                executor_type=WaitingExecutor,
                build=lambda: WaitingExecutor(started=asyncio.Event(), release=asyncio.Event()),
            ),
            authority_operation=unread_authority_operation(),
            journal=journal,
            reader=journal,
            event_stream=journal,
            leases=OperationLeaseFilesystemRepository(storage_root=tmp_path),
            operands=operation_secure_reference_repository(),
            owner_id="1" * 64,
            lease_token_factory=lambda: "2" * 64,
            clock=lambda: STARTED,
            lease_duration=timedelta(minutes=10),
            execution_timeout=timedelta(minutes=1),
            cleanup_timeout=timedelta(minutes=1),
        )
        assert await services.recovery_inventory(after=None, limit=2) == first

    asyncio.run(exercise())


@pytest.mark.parametrize("filename", ("malformed.json", "malformed.lease.json"))
def test_inventory_refuses_malformed_name_even_beyond_the_first_page(tmp_path: Path, filename: str) -> None:
    async def exercise() -> None:
        await _create(tmp_path, "a" * 64)
        journal = OperationJournalRepository(storage_root=tmp_path)
        malformed = tmp_path / "operation-journals" / filename
        malformed.write_text("{}", encoding="utf-8")
        original = malformed.read_bytes()
        with pytest.raises(RepositoryError, match="invalid operation journal inventory filename"):
            await journal.inventory_page(after=None, limit=1)
        assert malformed.read_bytes() == original

    asyncio.run(exercise())


def test_inventory_absence_is_empty_but_scan_failure_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "absent"
    journal = OperationJournalRepository(storage_root=root)
    empty = asyncio.run(journal.inventory_page(after=None, limit=1))
    assert empty.entries == () and empty.next_cursor is None and not empty.has_more
    assert not root.exists()

    async def exercise() -> None:
        await _create(tmp_path, "a" * 64)
        existing = OperationJournalRepository(storage_root=tmp_path)
        original_scan = journal_module.scan_directory

        def refuse_scan(path: Path, **kwargs: Any) -> tuple[Path, ...]:
            if path == tmp_path / "operation-journals":
                raise PermissionError("synthetic directory refusal")
            return original_scan(path, **kwargs)

        monkeypatch.setattr(journal_module, "scan_directory", refuse_scan)
        with pytest.raises(RepositoryError, match="cannot scan operation journal inventory"):
            await existing.inventory_page(after=None, limit=1)
        assert _journal_path(tmp_path, "a" * 64).exists()

    asyncio.run(exercise())


@pytest.mark.parametrize("limit", (0, 129))
def test_inventory_rejects_unbounded_page_limits_without_creating_storage(tmp_path: Path, limit: int) -> None:
    repository = OperationJournalRepository(storage_root=tmp_path)
    with pytest.raises(ValidationError):
        asyncio.run(repository.inventory_page(after=None, limit=limit))
    assert not (tmp_path / "operation-journals").exists()


def test_inventory_refuses_invalid_cursor_before_filesystem_access(tmp_path: Path) -> None:
    repository = OperationJournalRepository(storage_root=tmp_path)
    with pytest.raises(ValidationError):
        asyncio.run(repository.inventory_page(after="NOT_A_LOWERCASE_OPERATION_ID", limit=1))
    assert not (tmp_path / "operation-journals").exists()


class _CountedLoads(OperationJournalRepository):
    """The real journal, counting the snapshots read one by one after the inventory."""

    def __init__(self, *, storage_root: Path) -> None:
        super().__init__(storage_root=storage_root)
        self.loads = 0

    @override
    async def load(self, operation_id: OperationId) -> OperationPersistedSnapshot:
        self.loads += 1
        return await super().load(operation_id)


def test_the_census_readback_reads_again_only_records_opened_for_a_census_definition(tmp_path: Path) -> None:
    """Every other journaled operation is passed over on its inventory classification alone."""
    others = tuple(character * 64 for character in "abcde")

    async def exercise() -> int:
        for operation_id in others:
            await _create(tmp_path, operation_id, terminal=operation_id != others[0])
        await _create(tmp_path, "f" * 64, terminal=True, definition_id=CENSAL_OPERATION_DEFINITION_ID)
        journal = _CountedLoads(storage_root=tmp_path)
        observed = await read_latest_censal_observation(
            UUID(int=1), journal=journal, operands=operation_secure_reference_repository()
        )
        assert observed is None, "an interrupted census capture never replaces the absent one"
        return journal.loads

    assert asyncio.run(exercise()) == 1


def test_the_census_readback_still_refuses_a_history_holding_an_unreadable_record(tmp_path: Path) -> None:
    """An unread record might be a census capture, so passing over records never passes over this one."""

    async def exercise() -> None:
        await _create(tmp_path, "a" * 64, terminal=True)
        corrupt = _journal_path(tmp_path, "a" * 64)
        document = json.loads(corrupt.read_text(encoding="utf-8"))
        document["history"] = []
        corrupt.write_text(json.dumps(document), encoding="utf-8")
        with pytest.raises(InternalInvariantError, match="cannot be verified"):
            await read_latest_censal_observation(
                UUID(int=1),
                journal=OperationJournalRepository(storage_root=tmp_path),
                operands=operation_secure_reference_repository(),
            )

    asyncio.run(exercise())


def test_an_inventory_delta_names_every_record_and_classifies_only_the_unknown_ones(tmp_path: Path) -> None:
    """Known records are named without being read; unknown ones are classified as a page would."""
    ids = tuple(character * 64 for character in "abcd")

    async def exercise() -> None:
        for operation_id in ids:
            await _create(tmp_path, operation_id, terminal=operation_id == ids[1])
        corrupt = _journal_path(tmp_path, ids[3])
        document = json.loads(corrupt.read_text(encoding="utf-8"))
        document["history"] = []
        corrupt.write_text(json.dumps(document), encoding="utf-8")
        journal = _CountedLoads(storage_root=tmp_path)
        everything = await journal.inventory_page(after=None, limit=4)

        delta = await journal.inventory_delta(known=frozenset({ids[0], ids[2]}))

        assert delta.present == frozenset(ids)
        assert delta.entries == tuple(entry for entry in everything.entries if entry.operation_id in {ids[1], ids[3]})
        assert [entry.disposition for entry in delta.entries] == [
            OperationRecoveryInventoryDisposition.TERMINAL,
            OperationRecoveryInventoryDisposition.REFUSED,
        ]
        assert (await journal.inventory_delta(known=frozenset(ids))).entries == ()
        assert journal.loads == 0

    asyncio.run(exercise())


def test_an_inventory_delta_of_an_absent_journal_is_empty_and_a_malformed_name_is_refused(tmp_path: Path) -> None:
    absent = OperationJournalRepository(storage_root=tmp_path / "absent")
    empty = asyncio.run(absent.inventory_delta(known=frozenset()))
    assert empty.present == frozenset() and empty.entries == ()
    assert not (tmp_path / "absent").exists()

    async def exercise() -> None:
        await _create(tmp_path, "a" * 64)
        (tmp_path / "operation-journals" / "malformed.json").write_text("{}", encoding="utf-8")
        with pytest.raises(RepositoryError, match="invalid operation journal inventory filename"):
            await OperationJournalRepository(storage_root=tmp_path).inventory_delta(known=frozenset({"a" * 64}))

    asyncio.run(exercise())
