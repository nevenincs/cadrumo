"""Where the bulk filed pull reports that it wrote nothing.

``--dry-run`` promises the operator that a sweep left no trace. That promise is
primary result data the command exists to produce, not an incidental diagnostic,
so it rides ``result`` and never the notices channel -- the same shape the
telemetry flush surface already uses for its own preview flag.

The single-modelo branch has no dry-run path at all. It is therefore refused
rather than ignored: silently accepting the flag and performing a real write is
the one failure this surface cannot afford, because the operator's only evidence
that nothing happened is the flag they passed.
"""

from __future__ import annotations

import pytest

from ....application.live import BulkFiledDataCaptureReport
from .._app_live_filed_payloads import FiledCaptureResult
from .._app_live_rendering import _filed_capture_lines

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_dry_run_is_a_result_field_not_a_notice() -> None:
    """The flag is primary output, so it must be addressable on the result schema."""
    assert "dry_run" in FiledCaptureResult.model_fields

    result = FiledCaptureResult(
        mode="bulk",
        dry_run=True,
        output_root="filed-declarations",
        captured_count=0,
        observation_paths=[],
        artefact_refs=[],
        casilla_count=0,
        calculation_observation_count=0,
        calculation_observation_keys=[],
    )

    assert result.dry_run is True
    dumped = result.model_dump(mode="json")
    assert dumped["dry_run"] is True
    # The envelope's notices channel is assembled separately; a preview flag that
    # lived there would be an incidental diagnostic, which is what the CLI
    # contract reserves that channel for.
    assert "notices" not in dumped


def test_dry_run_defaults_false_so_a_silent_omission_never_reads_as_a_preview() -> None:
    """Absence must mean a real write, never an unstated dry run."""
    result = FiledCaptureResult(
        mode="single",
        output_root="filed-declarations",
        captured_count=0,
        observation_paths=[],
        artefact_refs=[],
        casilla_count=0,
        calculation_observation_count=0,
        calculation_observation_keys=[],
    )

    assert result.dry_run is False


@pytest.mark.parametrize("dry_run", [True, False])
def test_text_mode_agrees_with_the_result_field(dry_run: bool) -> None:
    """Text and JSON must not disagree about whether anything was written."""
    report = BulkFiledDataCaptureReport(
        output_root="filed-declarations",
        modelos=("303",),
        year_from=2025,
        year_to=2025,
        captured_count=0,
        reached_count=0,
        failed_count=0,
        observation_paths=(),
        artefact_refs=(),
        justificante_metadata_count=0,
        justificante_csvs=(),
        filing_evidence_stamped_count=0,
        filing_record_ids=(),
        filing_evidence_conflict_count=0,
        filing_evidence_conflict_record_ids=(),
        casilla_count=0,
        calculation_observation_count=0,
        calculation_observation_keys=(),
        evidence_notices=(),
        failures=(),
        skipped_casillas=(),
        recapture_notices=(),
        dry_run=dry_run,
    )
    lines = _filed_capture_lines(report, mode="bulk")

    emitted = any(line.startswith("dry_run") for line in lines)
    assert emitted is dry_run
