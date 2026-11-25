"""Record what ``ledger.entry-options`` serves into the browser's entry-options fixture.

The window holds no vocabulary, classification rule, text limit or period of its own: it shows
what the operation serves. This reads the served families, classification rules and limits
through the operation's own projection, and answers the questions committed in
``dev/fixtures/ledger-entry-option-questions/periods.json`` through the ledger's own period read:

    uv run --no-sync python native/desktop/frontend/scripts/ledger_entry_options.py [--check | --output DIR]
"""

from __future__ import annotations

from dev.fixture_projections.location import family_directory
from dev.fixture_projections.producer_output import emit, producer_arguments
from dev.prettier_json import dump_json

from cadrumo.application.ledger.tests.entry_option_periods_recording_support import committed_questions, recording
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority


def main() -> None:
    """Write, check or redirect the entry-options recording."""
    arguments = producer_arguments(__doc__)
    with bundled_indexed_authority().operation() as operation:
        rendered = dump_json(recording(committed_questions(), operation))
    emit(
        {family_directory("ledger-entry-options") / "ledgerEntryOptions.json": rendered},
        arguments,
        remedy="just fixtures-seed ledger-entry-options",
    )


if __name__ == "__main__":
    main()
