"""Scale benchmark: the startup inventory a profile worker reads before its first operation.

The first operation a profile worker admits after a sign-in waits for the
recovery inventory: every record in the credential-free operation journal is
named, read and validated, so an unreadable record refuses all hosted work.
A profile that has been used for months holds thousands of records. This
module seeds a REAL journal through the canonical adapter (one record settled
by the journal itself, then copied under new identities) and measures the
whole inventory through the composed operation services the worker calls.

The gate is process CPU-time, which counts the capture threads too; wall-clock
is an advisory. Reading the inventory page by page re-scanned the directory
for every 128-record page, which made the cost quadratic in the record count.
At this scale that cost alone exceeds the budget, so a return to it fails here.
"""

from __future__ import annotations

import asyncio
import statistics
import tempfile
import time
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.operations.secure_references import operation_secure_reference_repository
from cadrumo.adapters.persistence.operations.tests.supervisor_test_support import WaitingExecutor, supervisor_registry
from cadrumo.adapters.persistence.operations.tests.test_journal import STARTED, journal_snapshot
from cadrumo.application.operations.composition import OperationComposedServices, compose_operation_services
from cadrumo.application.operations.models import OperationIdentity, OperationTerminalReceipt
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
from cadrumo.core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition

from ..perf_measurement import wall_advisory_message

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_RECORDS = 6_000
_TEMPLATE_ID = "0" * 64
_SAMPLES = 3

#: Measured 2.7-3.0 CPU-s (about 2.0 s wall) for the full pass on a quiet
#: workstation, against 6.6-6.8 CPU-s for the page-by-page reading it replaced.
#: The ceiling carries the measured ~1.64x co-residency inflation of CPU-time on
#: that machine and stays below the replaced reading's quiet cost.
_BUDGET_CPU_SECONDS = 4.8
_WALL_ADVISORY_SECONDS = 5.0
_WEDGE_WALL_TO_CPU_RATIO = 4.0


async def _settle_template(root: Path) -> None:
    """Create and settle one record through the real journal and lease adapters."""
    journal = OperationJournalRepository(storage_root=root)
    template = journal_snapshot(revision=0, sequence=1)
    identity = OperationIdentity(operation_id=_TEMPLATE_ID, definition_id="test.operation", subject_ref="subject")
    event = template.events[0].model_copy(update={"identity": identity})
    initial = OperationPersistedSnapshot.model_validate(
        template.model_copy(update={"identity": identity, "events": (event,)}).model_dump(mode="python")
    )
    lease = OperationOwnerLease(
        operation_id=_TEMPLATE_ID,
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
    settled_at = STARTED + timedelta(minutes=1)
    receipt = OperationTerminalReceipt(
        identity=identity,
        revision=1,
        condition=OperationTerminalCondition.INTERRUPTED,
        effect=OperationEffect.NONE,
        settled_at=settled_at,
    )
    terminal = OperationPersistedSnapshot.model_validate(
        initial.model_copy(
            update={
                "revision": 1,
                "lifecycle": OperationLifecycle.TERMINAL,
                "terminal_condition": receipt.condition,
                "effect": receipt.effect,
                "updated_at": settled_at,
                "event_cursor": 2,
                "events": (
                    OperationTerminalEvent(
                        identity=identity,
                        revision=1,
                        sequence=2,
                        timestamp=settled_at,
                        code="operation.terminal",
                        receipt=receipt,
                    ),
                ),
                "terminal_receipt": receipt,
            }
        ).model_dump(mode="python")
    )
    await journal.commit_settlement(terminal, expected_revision=0, lease=lease)


def _services(root: Path) -> OperationComposedServices:
    journal = OperationJournalRepository(storage_root=root)
    return compose_operation_services(
        registry=supervisor_registry(
            executor_type=WaitingExecutor,
            build=lambda: WaitingExecutor(started=asyncio.Event(), release=asyncio.Event()),
        ),
        authority_operation=unread_authority_operation(),
        journal=journal,
        reader=journal,
        event_stream=journal,
        leases=OperationLeaseFilesystemRepository(storage_root=root),
        operands=operation_secure_reference_repository(),
        owner_id="1" * 64,
        lease_token_factory=lambda: "2" * 64,
        clock=lambda: STARTED,
        lease_duration=timedelta(minutes=10),
        execution_timeout=timedelta(minutes=1),
        cleanup_timeout=timedelta(minutes=1),
    )


@pytest.fixture(scope="module")
def scale_journal() -> Iterator[Path]:
    """A storage root whose journal holds ``_RECORDS`` settled records."""
    with tempfile.TemporaryDirectory(prefix="cadrumo-journal-inventory-") as directory:
        root = Path(directory)
        asyncio.run(_settle_template(root))
        journal_root = root / "operation-journals"
        template = (journal_root / f"{_TEMPLATE_ID}.json").read_text(encoding="utf-8")
        for index in range(1, _RECORDS):
            operation_id = f"{index:064x}"
            (journal_root / f"{operation_id}.json").write_text(
                template.replace(_TEMPLATE_ID, operation_id), encoding="utf-8"
            )
        yield root


@pytest.mark.perf
@pytest.mark.serial
def test_startup_inventory_cpu_within_budget_at_scale(scale_journal: Path) -> None:
    """The whole inventory of a long-used profile stays inside its CPU budget."""
    services = _services(scale_journal)
    cpu: list[float] = []
    wall: list[float] = []
    for _ in range(_SAMPLES):
        wall_started = time.perf_counter()
        cpu_started = time.process_time()
        inventory = asyncio.run(services.recovery_inventory())
        cpu.append(time.process_time() - cpu_started)
        wall.append(time.perf_counter() - wall_started)
        assert len(inventory.entries) == _RECORDS
        assert all(entry.disposition is OperationRecoveryInventoryDisposition.TERMINAL for entry in inventory.entries)

    cpu_median = statistics.median(cpu)
    wall_median = statistics.median(wall)
    print(
        f"\n[bench] operation_journal_startup_inventory: records={_RECORDS} cpu_median={cpu_median:.3f}s "
        f"gate=cpu<{_BUDGET_CPU_SECONDS:.1f}s wall_median={wall_median:.3f}s (wall advisory)"
    )
    wall_advisory_message(
        "operation_journal_startup_inventory median",
        wall_seconds=wall_median,
        cpu_seconds=cpu_median,
        wall_advisory_seconds=_WALL_ADVISORY_SECONDS,
        hang_wall_to_cpu_ratio=_WEDGE_WALL_TO_CPU_RATIO,
    )
    assert cpu_median < _BUDGET_CPU_SECONDS, (
        f"startup inventory of {_RECORDS} journal records took {cpu_median:.3f} CPU-s, over the "
        f"{_BUDGET_CPU_SECONDS:.1f} CPU-s budget (cpu samples={cpu!r})"
    )
