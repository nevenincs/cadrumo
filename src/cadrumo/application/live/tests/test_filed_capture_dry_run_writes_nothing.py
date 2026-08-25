"""A dry-run filed-declaration capture writes nothing to the real encrypted store.

The decision record's binding requirement: a preview leaves the store and the
remote plan byte-identical across a run. This proves the store half with the
real production write path -- :meth:`_CaptureAccumulator.absorb`, the exact
method both :func:`capture_filed_data_bulk` and :func:`capture_filed_data`
call per observation -- against a genuine encrypted bucket database, never a
mock or an in-memory substitute.

The bootstrap confound: opening a secure-object repository for the first time
in a fresh bucket can itself write schema DDL to the database file, regardless
of whether any row is ever inserted. Snapshotting BEFORE that first touch would
make an untouched-vs-bootstrapped diff masquerade as a dry-run write. The fix
is ordering: warm the exact read path :meth:`absorb` exercises before taking
the baseline snapshot, so only the absorb call under test can move the needle.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....tests.secure_sql import isolated_runtime_profile, read_db_at_rest_bytes
from ...calculations import CalculationObservationRepository
from ..filed_data_capture import _CaptureAccumulator, recapture_divergence_notices
from ._filed_capture_history_support import _prior_303_observation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_dry_run_absorb_leaves_the_bucket_database_byte_identical(tmp_path: Path) -> None:
    from ....adapters.outbound.aeat.sede import FiledDeclaracionObservationStore

    observation = _prior_303_observation(pending_compensation=Decimal("0.00"))

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="0981a5d8-4224-4246-b73c-4fe7b1d3ff51") as profile:
        store = FiledDeclaracionObservationStore(tmp_path, objects=profile.repository)
        accumulator = _CaptureAccumulator()

        # Warm-up: exercise the exact read path `absorb` runs (the recapture
        # divergence lookup) BEFORE the baseline snapshot, so any first-touch
        # schema bootstrap lands ahead of the measurement rather than inside it.
        recapture_divergence_notices((observation,), repository=CalculationObservationRepository())

        baseline = read_db_at_rest_bytes(profile.paths.database_file)

        accumulator.absorb(
            observation,
            store=store,
            bucket_id=profile.bucket_id,
            output_root=tmp_path,
            dry_run=True,
        )

        after_dry_run = read_db_at_rest_bytes(profile.paths.database_file)

        assert after_dry_run == baseline, "a dry-run absorb wrote to the encrypted bucket database"
        assert accumulator.absorbed_count == 1, "the reached tally must still count a dry-run unit"
        assert accumulator.observation_paths == [], "dry-run must persist no observation manifest"
        assert accumulator.filing_record_ids == [], "dry-run must stamp no filing record"

        # Positive control: a real absorb against the SAME store DOES move the
        # bytes. Without this, a broken read_db_at_rest_bytes could report
        # "identical" no matter what happened, and the assertion above would be
        # vacuous.
        accumulator.absorb(
            observation,
            store=store,
            bucket_id=profile.bucket_id,
            output_root=tmp_path,
            dry_run=False,
        )

        after_real_write = read_db_at_rest_bytes(profile.paths.database_file)

        assert after_real_write != baseline, "a real absorb must change the encrypted bucket database"
        assert accumulator.absorbed_count == 2
        assert len(accumulator.observation_paths) == 1, "the real absorb must persist exactly one manifest"
