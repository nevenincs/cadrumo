"""The recapture divergence is read before the upsert, and reaches the operator.

A re-capture of filed history is an unconditional upsert keyed on modelo,
ejercicio, period and expediente, so a corrected filing replaces values the
operator may already have calculated against. The advisory that reports this
was built, exported and unit-tested at the leaf — and never called from any
production path, so the sweep changed history in silence.

Two properties are gated here, and the ordering one is the load-bearing half:
the divergence MUST be read while the prior values still exist. Computed after
the write it can only ever report nothing, which is indistinguishable from a
clean sweep.
"""

from __future__ import annotations

import importlib
import inspect

import pytest

from ..filed_data_capture import _CaptureAccumulator

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class TestTheDivergenceIsReadBeforeThePersist:
    """Ordering inside the single persistence funnel."""

    def test_the_divergence_read_precedes_the_upsert_in_the_one_funnel(self) -> None:
        """``absorb`` reads the prior values before it overwrites them.

        Asserted on source order inside the funnel rather than by driving a
        live capture, because the alternative — reaching the real
        ``persist_observation`` — needs an authenticated AEAT sweep, which is
        a forbidden live remote interaction in a test.

        Source order is a weak instrument in general and an adequate one here
        for exactly one reason: these two statements are adjacent in a single
        function whose whole contract is their order, so there is no control
        flow between them for the assertion to miss.
        """
        source = inspect.getsource(_CaptureAccumulator.absorb)
        read_at = source.index("recapture_divergence_notices")
        write_at = source.index("store.persist_observation")
        assert read_at < write_at, (
            "the recapture divergence must be read BEFORE persist_observation; "
            "afterwards the prior values are gone and the advisory can only "
            "ever report nothing, which looks exactly like a clean sweep"
        )

    def test_every_capture_path_shares_that_one_funnel(self) -> None:
        """Single-shot, bulk and source capture all persist through ``absorb``.

        If a path persisted directly, it would upsert without the divergence
        read and this gate would still be green. Counting the call sites is
        what makes the ordering guarantee cover the whole surface rather than
        one path.
        """
        from pathlib import Path

        module = importlib.import_module("..filed_data_capture", package=__package__)
        assert module.__file__ is not None
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert source.count("store.persist_observation(") == 1, (
            "persist_observation is called outside the accumulator funnel; that "
            "path upserts without reading the divergence first"
        )
        assert source.count("accumulator.absorb(") >= 3


class TestTheAdvisoryReachesTheOperator:
    """A notice nothing forwards is the defect this closes."""

    def test_the_accumulator_carries_the_notices_it_reads(self) -> None:
        accumulator = _CaptureAccumulator()
        assert accumulator.recapture_notices == []

    def test_the_run_model_exposes_the_notices(self) -> None:
        from ..filed_data_capture import FiledHistoryOnboardingRun

        assert "recapture_notices" in FiledHistoryOnboardingRun.model_fields

    def test_the_bulk_report_exposes_the_notices(self) -> None:
        from ..remote_state_models import BulkFiledDataCaptureReport

        assert "recapture_notices" in BulkFiledDataCaptureReport.model_fields

    def test_the_cli_forwards_them_onto_the_envelope(self) -> None:
        """The envelope builder must extend from the run's own notices.

        Without this the notices exist on the model and stop there — which is
        the exact shape of the original defect, one layer further out.
        """
        from pathlib import Path

        from ....entrypoints.cli import _app_live

        assert _app_live.__file__ is not None
        source = Path(_app_live.__file__).read_text(encoding="utf-8")
        assert "notices.extend(run.recapture_notices)" in source
