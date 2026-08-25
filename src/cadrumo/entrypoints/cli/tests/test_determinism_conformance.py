"""Determinism-conformance axis over the ``--format json`` command surface.

An opt-in axis: for each command explicitly ENROLLED as replayable, this gate
captures the command's emitted ``SchemaEnvelope`` twice under a frozen clock with
injected identity against REAL repositories, canonicalises and masks via the
shared substrate primitive, and asserts byte-identical full-envelope equality. An
un-enrolled command-spec result identity is REPORTED as a visible coverage gap (a
pytest warning enumerating the uncovered set) rather than silently passing, so the
axis grows deliberately. The enrolled set only ratchets up: a stale enrolment (a
command that no longer registers) fails loudly.

Two commands are enrolled. The ledger-add retried-no-op is the state-transition
case: its envelope replays byte-identical, and the bucket's committed-state
fingerprint (the substrate's ``compute_db_sha256`` over a committed-files snapshot
— the main ``.db`` plus committed ``-wal``, excluding the volatile ``-shm``
read-index) is identical after the idempotent second add against a hermetic
synthetic ``var/`` root — the concrete proof the clock-free idempotency id is a
true no-op. The ledger-evidence
add is the D1 golden case: its ``--format json`` envelope is byte-identical across
two fresh-bucket runs, with zero residual differing fields, proving the
content-addressed ``evidence_id`` needs no mask. The axis owns only
payload-and-post-state determinism; the harness operator golden gate layers
AEAT-oracle expected-value and trajectory assertions on top.
"""

from __future__ import annotations

import io
import shutil
import warnings
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....application.ledger.models import ManualLedgerTransactionCommand
from ....application.ledger.evidence import PurchaseInvoiceEvidenceService
from ....application.ledger.actions_manual import create_manual_transaction, ledger_transaction_payload
from ....application.ledger.review_projection import ledger_transaction_review_status
from ....core.directory_scan import scan_directory
from ....core.json_contract import Notice, NoticeSeverity, emit_json_success
from ....core.observability import (
    canonicalise,
    capture_envelopes,
    compute_db_sha256,
    differing_field_names,
    differing_paths,
    mask_document,
)
from ....core.time import frozen_clock
from ....domain.transactions import TransactionDirection
from ....tests.env_scope import scoped_cwd
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .._command_schema import command_schema_types
from .._ledger_payloads import EvidenceAddResult, LedgerAddResult

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_INSTANT = datetime(2026, 4, 14, 9, 30, 0, tzinfo=UTC)
_BUCKET = "28282828-2828-4828-8828-282828282828"

#: Opt-in enrolment of replayable ``--format json`` commands. Grows deliberately;
#: every entry MUST be a registered command (enforced below) and MUST have a
#: determinism proof in this module.
ENROLLED_REPLAYABLE_COMMANDS: frozenset[str] = frozenset({"ledger.add", "ledger.evidence.add"})


def uncovered_replayable_commands() -> frozenset[str]:
    """Return registered ``--format json`` commands not yet enrolled as replayable."""
    return frozenset(command_schema_types()) - ENROLLED_REPLAYABLE_COMMANDS


def _committed_db_fingerprint(profile: TestRuntimeProfile, snapshot_dir: Path) -> str:
    """Return the substrate ``compute_db_sha256`` over the bucket's committed state.

    Snapshots the committed database files — the main ``.db`` plus its committed
    ``-wal`` frames — into ``snapshot_dir``, excluding the volatile ``-shm``
    shared-memory WAL index, then fingerprints that snapshot with the substrate's
    :func:`compute_db_sha256` (the named db_sha256 tier). ``-shm`` carries no
    committed row payload and its reader-marks flap on every read (not a state
    change), and it cannot be removed in-session on Windows (its mmap handle
    outlives ``engine.dispose()``), so the live var tree cannot be hashed directly
    in-process; the snapshot lets the substrate fingerprint run over the committed
    bytes exactly as it would at a between-process replay boundary where no
    connection is open.
    """
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    for source in scan_directory(profile.paths.db_dir):
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


def _emit_evidence_add(storage_root: Path, pdf: Path) -> dict[str, object]:
    """Drive one real ``ledger evidence add`` in a fresh bucket and capture its envelope.

    Builds the ``EvidenceAddResult`` exactly as the CLI leaf does (record dump plus
    the ``bucket_event_ids`` appended at the emit site) and emits it through the
    real success-envelope path under a capture sink. All storage ops stay inside one
    ``frozen_clock`` block.
    """
    with isolated_runtime_profile(tmp_path=storage_root, bucket_id=_BUCKET) as profile, frozen_clock(_INSTANT):
        service = PurchaseInvoiceEvidenceService(
            settings=profile.settings,
            bucket_event_repository=BucketEventHistoryRepository(objects=profile.repository),
        )
        result = service.add(
            bucket_id=profile.bucket_id,
            source_path=pdf,
            supplier="Acme S.L.",
            invoice_number="INV-001",
            invoice_date="2026-01-15",
            taxable_base=Decimal("100.00"),
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("21.00"),
            notes="office supplies",
        )
        payload = result.record.model_dump(mode="json")
        payload["bucket_event_ids"] = list(result.bucket_event_ids)
        with capture_envelopes() as sink:
            emit_json_success("ledger.evidence.add", EvidenceAddResult.model_validate(payload), stream=io.StringIO())
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

    def test_ledger_evidence_add_envelope_replays_byte_identical(self, tmp_path: Path) -> None:
        """D1 golden case: the evidence-add envelope is deterministic across runs.

        One synthetic PDF reused across both runs so ``source_path`` is identical;
        each run is a fresh bucket, so the content-addressed ``evidence_id`` derives
        with disambiguator 0 in both and matches. The content-addressed evidence id,
        the content-addressed bucket-event id and the frozen-clock timestamps make
        the whole ``--format json`` envelope deterministic — zero residual differing
        fields, so no ``GOLDEN_MASK_FIELDS`` entry is warranted.
        """
        pdf = tmp_path / "receipt.pdf"
        pdf.write_bytes(b"%PDF-1.4 determinism")

        first = _emit_evidence_add(tmp_path / "run-a", pdf)
        second = _emit_evidence_add(tmp_path / "run-b", pdf)

        assert differing_paths(first, second) == frozenset()
        assert differing_field_names(first, second) == frozenset()
        assert canonicalise(first) == canonicalise(second)

    def test_ledger_evidence_add_identity_is_cwd_independent(
        self,
        tmp_path: Path,
    ) -> None:
        """Regression: identical bytes added from DIFFERENT working dirs share one identity.

        The golden case above reused one absolute pdf path, so ``source_path`` was
        only incidentally identical. This drives the real defect: the same bytes
        added via the same relative path from two different working directories.
        The content-addressed ``evidence_id`` and the bucket-event id must match
        (identity derives from the source digest and stable metadata, never the
        machine-absolutized path), and the persisted ``source_path`` echoes the
        argv-faithful relative path in both runs, not the resolved absolute form.
        """
        pdf_bytes = b"%PDF-1.4 cwd-independent"
        cwd_a = tmp_path / "cwd-a"
        cwd_b = tmp_path / "cwd-b"
        for cwd in (cwd_a, cwd_b):
            cwd.mkdir()
            (cwd / "receipt.pdf").write_bytes(pdf_bytes)

        def _add_from(cwd: Path, storage_root: Path) -> tuple[str, tuple[str, ...], str]:
            with (
                scoped_cwd(cwd),
                isolated_runtime_profile(tmp_path=storage_root, bucket_id=_BUCKET) as profile,
                frozen_clock(_INSTANT),
            ):
                service = PurchaseInvoiceEvidenceService(
                    settings=profile.settings,
                    bucket_event_repository=BucketEventHistoryRepository(objects=profile.repository),
                )
                result = service.add(
                    bucket_id=profile.bucket_id,
                    source_path=Path("receipt.pdf"),
                    supplier="Acme S.L.",
                    invoice_number="INV-001",
                )
            return result.record.evidence_id, result.bucket_event_ids, result.record.source_path

        first_id, first_events, first_path = _add_from(cwd_a, tmp_path / "run-a")
        second_id, second_events, second_path = _add_from(cwd_b, tmp_path / "run-b")

        # Identity is content-derived, independent of cwd / absolute path.
        assert first_id == second_id
        assert first_events == second_events
        assert first_events != ()
        # The persisted breadcrumb echoes the argv-faithful path, not the resolved form.
        assert first_path == "receipt.pdf"
        assert second_path == "receipt.pdf"
        assert not Path(first_path).is_absolute()


class TestCoverageDiscipline:
    def test_enrolled_commands_are_all_registered(self) -> None:
        """No stale enrolment: every enrolled command still resolves in the registry."""
        stale = ENROLLED_REPLAYABLE_COMMANDS - frozenset(command_schema_types())
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
                f"{len(command_schema_types())} authored --format json commands enrolled; "
                f"{len(uncovered)} uncovered (opt-in). First uncovered: {sorted(uncovered)[:10]}",
                stacklevel=2,
            )
