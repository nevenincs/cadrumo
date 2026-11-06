"""Record what ``ledger.staged.check`` answers, for the browser fixtures that look its answers up.

The window's fixtures hold no rule: they look each staged check up in a recording
keyed by exactly what was asked. This answers every question committed in
``dev/fixtures/ledger-staged-check-questions/questions.jsonl`` through the real check
and writes the recording. A question the fixtures could not answer is captured by
the frontend tests under ``CADRUMO_STAGED_CHECK_UNRECORDED``; append the captured
lines to the questions file and run ``just fixtures-seed ledger-staged-check``:

    uv run --no-sync python native/desktop/frontend/scripts/ledger_staged_check.py [--check | --output DIR]
"""

from __future__ import annotations

from dev.fixture_projections.location import family_directory
from dev.fixture_projections.producer_output import emit, producer_arguments
from dev.prettier_json import dump_json

from cadrumo.application.ledger.tests.staged_check_recording_support import committed_questions, recording
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority


def main() -> None:
    """Write, check or redirect the staged-check recording."""
    arguments = producer_arguments(__doc__)
    with bundled_indexed_authority().operation():
        rendered = dump_json(recording(committed_questions()))
    emit(
        {family_directory("ledger-staged-check") / "ledgerStagedCheck.json": rendered},
        arguments,
        remedy="just fixtures-seed ledger-staged-check",
    )


if __name__ == "__main__":
    main()
