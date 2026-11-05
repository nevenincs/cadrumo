"""Record the periods the ledger's period read answers into the browser's entry-options fixture.

The window does no period arithmetic: it shows the periods ``ledger.entry-options``
serves, from the ``periods`` section of the entry-options fixture. This answers the
questions committed in ``dev/fixtures/ledger-entry-option-questions/periods.json``
through the ledger's own period read and writes that section, keeping every other
section of the fixture as it stands:

    uv run --no-sync python native/desktop/frontend/scripts/ledger_entry_options.py [--check | --output DIR]
"""

from __future__ import annotations

import json

from dev.fixture_projections.producer_output import emit, producer_arguments
from dev.prettier_json import dump_json

from cadrumo.application.ledger.tests.entry_option_periods_recording_support import (
    RECORDING,
    committed_questions,
    recording,
)


def main() -> None:
    """Write, check or redirect the entry-options recording."""
    arguments = producer_arguments(__doc__)
    rendered = dump_json(recording(json.loads(RECORDING.read_text(encoding="utf-8")), committed_questions()))
    emit({RECORDING: rendered}, arguments, remedy="just fixtures-seed ledger-entry-options")


if __name__ == "__main__":
    main()
