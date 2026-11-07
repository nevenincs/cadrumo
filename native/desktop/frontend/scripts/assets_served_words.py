"""Record what the activity-asset register says, for the browser fixtures that look its words up.

The window words nothing of the register's: its fixtures look each reason, remedy,
handoff interval and left-out reason up in a recording keyed by exactly what was
asked. This answers every question committed in
``dev/fixtures/assets-served-words-questions/questions.jsonl`` through the register's
own words, in every language, and writes the recording. Append a question the
fixtures could not answer to that file and run ``just fixtures-seed assets-served-words``:

    uv run --no-sync python native/desktop/frontend/scripts/assets_served_words.py [--check | --output DIR]
"""

from __future__ import annotations

from dev.fixture_projections.location import family_directory
from dev.fixture_projections.producer_output import emit, producer_arguments
from dev.prettier_json import dump_json

from cadrumo.application.actividad_asset.tests.served_words_recording_support import committed_questions, recording


def main() -> None:
    """Write, check or redirect the register-words recording."""
    arguments = producer_arguments(__doc__)
    emit(
        {
            family_directory("assets-served-words") / "assetsServedWords.json": dump_json(
                recording(committed_questions())
            )
        },
        arguments,
        remedy="just fixtures-seed assets-served-words",
    )


if __name__ == "__main__":
    main()
