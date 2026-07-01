"""Determinism-conformance axis over the ``--format json`` command surface (ADR D4).

An opt-in axis: for each command a campaign ENROLS as replayable, this gate
captures the command's emitted ``SchemaEnvelope`` twice under a frozen clock with
injected identity against REAL repositories, canonicalises and masks via the
shared substrate primitive, and asserts byte-identical full-envelope equality. An
un-enrolled ``register_schema`` command is REPORTED as a visible coverage gap (a
pytest warning enumerating the uncovered set) rather than silently passing, so the
axis grows deliberately. The enrolled set only ratchets up: a stale enrolment (a
command that no longer registers) fails loudly.

The ledger-add retried-no-op is the first enrolled state-transition case: its
envelope replays byte-identical, and the substrate optional ``db_sha256``
post-state tier is identical after the idempotent second add against a hermetic
synthetic ``var/`` root — the concrete proof that the clock-free idempotency id is
a true no-op. The axis owns only payload-and-post-state determinism; the harness
operator golden gate layers AEAT-oracle expected-value and trajectory assertions
on top.
"""

from __future__ import annotations

import io
import shutil
import warnings
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....application.ledger import (
    ManualLedgerTransactionCommand,
    create_manual_transaction,
    ledger_transaction_payload,
    ledger_transaction_review_status,
)
from ....core.json_contract import SCHEMA_REGISTRY, Notice, NoticeSeverity, emit_json_success
from ....core.observability import (
    canonicalise,
    capture_envelopes,
    compute_db_sha256,
    differing_paths,
    mask_document,
)
from ....core.time import frozen_clock
from ....domain.buckets import BucketEventHistoryRepository
from ....domain.transactions import TransactionCatalogueRepository, TransactionDirection
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .._ledger_payloads import LedgerAddResult

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_INSTANT = datetime(2026, 4, 14, 9, 30, 0, tzinfo=UTC)
_BUCKET = "28282828-2828-4828-8828-282828282828"

#: Opt-in enrolment of replayable ``--format json`` commands. Grows deliberately;
#: every entry MUST be a registered command (enforced below) and MUST have a
#: determinism proof in this module.
ENROLLED_REPLAYABLE_COMMANDS: frozenset[str] = frozenset({"ledger.add"})


def uncovered_replayable_commands() -> frozenset[str]:
    """Return registered ``--format json`` commands not yet enrolled as replayable."""
    return frozenset(SCHEMA_REGISTRY) - ENROLLED_REPLAYABLE_COMMANDS


def _committed_db_fingerprint(profile: TestRuntimeProfile, snapshot_dir: Path) -> str:
    """Return the substrate ``compute_db_sha256`` over the bucket's committed state.

    Snapshots the committed database files — the main ``.db`` plus its committed
    ``-wal`` frames — into ``snapshot_dir``, excluding the volatile ``-shm``
    shared-memory WAL index, then fingerprints that snapshot with the substrate's
    :func:`compute_db_sha256`. ``-shm`` carries no committed row payload and its
    reader-marks flap on every read (not a state change), and it cannot be removed
    in-session on Windows (its mmap handle outlives ``engine.dispose()``), so the
    live var tree cannot be hashed directly in-process; the snapshot lets the
    substrate fingerprint run over the committed bytes exactly as it would at a
    between-process replay boundary where no connection is open.
    """
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    for source in sorted(profile.paths.db_dir.iterdir()):
        if source.is_file() and not source.name.endswith("-shm"):
            shutil.copy2(source, snapshot_dir / source.name)
    return compute_db_sha256(snapshot_dir)


def _idempotent_command() -> ManualLedgerTransactionCommand:
    return ManualLedgerTransactionCommand(
        bucket_id=_BUCKET,
        booked_date=date(2026, 5, 2),
        amount=Decimal("25.00"),
        direction=TransactionDirection.OUTGOING,
        description="cash sale",
        idempotency_key="det-conformance-1",
    )


def _emit_ledger_add(profile: TestRuntimeProfile) -> dict[str, object]:
    """Drive one real ``ledger add`` and capture its emitted envelope document.

    Builds the ``LedgerAddResult`` exactly as the CLI leaf does (same application
    service, same payload helpers, same registered schema, same emit path), so the
    capture is a real ``--format json`` envelope, not a hand-shaped stand-in.
    """
    repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id, objects=profile.repository)
    events = BucketEventHistoryRepository(objects=profile.repository)
    result = create_manual_transaction(
        _idempotent_command(),
        transaction_repository=repo,
        bucket_event_repository=events,
        occurred_at=_INSTANT,
    )
    payload = LedgerAddResult.model_validate(
        {
            "bucket_id": result.ref.bucket_id,
            "transaction_id": result.ref.transaction_id,
            "bucket_event_ids": list(result.bucket_event_ids),
            "review_status": ledger_transaction_review_status(result.transaction),
            "transaction": ledger_transaction_payload(result.transaction).model_dump(mode="json"),
        },
    )
    notices: list[Notice] = []
    if not result.bucket_event_ids:
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="ledger.add.idempotent_noop",
                message=f"Idempotent no-op ({result.ref.transaction_id}).",
                context={"transaction_id": result.ref.transaction_id},
            ),
        )
    with capture_envelopes() as sink:
        emit_json_success("ledger.add", payload, notices=notices, stream=io.StringIO())
    return sink[-1]


class TestEnrolledCommandDeterminism:
    def test_ledger_add_retried_noop_envelope_replays_byte_identical(self, tmp_path: Path) -> None:
        with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile, frozen_clock(_INSTANT):
            _emit_ledger_add(profile)  # first add: creates the row
            first_noop = _emit_ledger_add(profile)  # guarded no-op retry
            second_noop = _emit_ledger_add(profile)  # a second guarded no-op retry

        # Two no-op retries of the same clock-free-keyed add emit an identical
        # envelope (same content-addressed transaction_id, empty bucket_event_ids,
        # pinned created_at) — byte-identical after canonicalise+mask.
        assert differing_paths(mask_document(first_noop), mask_document(second_noop)) == frozenset()
        assert canonicalise(mask_document(first_noop)) == canonicalise(mask_document(second_noop))

    def test_ledger_add_retried_noop_leaves_db_state_unchanged(self, tmp_path: Path) -> None:
        with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile, frozen_clock(_INSTANT):
            repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id, objects=profile.repository)
            events = BucketEventHistoryRepository(objects=profile.repository)
            command = _idempotent_command()
            create_manual_transaction(
                command,
                transaction_repository=repo,
                bucket_event_repository=events,
                occurred_at=_INSTANT,
            )
            db_after_create = _committed_db_fingerprint(profile, tmp_path / "db-snap-create")

            second = create_manual_transaction(
                command,
                transaction_repository=repo,
                bucket_event_repository=events,
                occurred_at=_INSTANT,
            )
            assert second.bucket_event_ids == ()  # the guarded-idempotent no-op signal
            db_after_retry = _committed_db_fingerprint(profile, tmp_path / "db-snap-retry")

        # The idempotent second add wrote nothing: the hermetic var-root committed
        # fingerprint is identical, proving the clock-free identity is a true
        # post-state no-op.
        assert db_after_retry == db_after_create


class TestCoverageDiscipline:
    def test_enrolled_commands_are_all_registered(self) -> None:
        """No stale enrolment: every enrolled command still resolves in the registry."""
        stale = ENROLLED_REPLAYABLE_COMMANDS - frozenset(SCHEMA_REGISTRY)
        assert not stale, f"enrolled replayable commands no longer registered: {sorted(stale)}"

    def test_uncovered_commands_are_reported_not_silently_passed(self) -> None:
        """Surface the un-enrolled registered commands as a visible coverage gap.

        Enrolment is opt-in, so an uncovered command does not fail the axis — but it
        is reported (a warning enumerating the count), never a silent pass, so the
        coverage gap stays visible and the axis grows deliberately.
        """
        assert ENROLLED_REPLAYABLE_COMMANDS, "the determinism axis must enrol at least one command"
        uncovered = uncovered_replayable_commands()
        if uncovered:
            warnings.warn(
                f"determinism-conformance coverage: {len(ENROLLED_REPLAYABLE_COMMANDS)} of "
                f"{len(SCHEMA_REGISTRY)} registered --format json commands enrolled; "
                f"{len(uncovered)} uncovered (opt-in). First uncovered: {sorted(uncovered)[:10]}",
                stacklevel=2,
            )
