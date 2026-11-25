"""Record what the activity-asset register answers for the Assets fixtures' scenario register.

The window holds no register figure of its own: its fixtures read each element's list
row, plan, limits, advisories, history, revisions, forecasts and baja figures from
this recording. It replays the scenario committed under
``dev/fixtures/assets-register-scenario`` through the real register over the published
authority and writes what it answers. Change the scenario there and run
``just fixtures-seed assets-register``:

    uv run --no-sync python native/desktop/frontend/scripts/assets_register.py [--check | --output DIR]
"""

from __future__ import annotations

from dev.fixture_projections.location import family_directory
from dev.fixture_projections.producer_output import emit, producer_arguments
from dev.prettier_json import dump_json

from cadrumo.application.actividad_asset.tests.register_recording_support import committed_scenario, recording

RECORDING = family_directory("assets-register") / "assetsRegister.json"


def main() -> None:
    """Write, check or redirect the scenario register's recording."""
    arguments = producer_arguments(__doc__)
    emit(
        {RECORDING: dump_json(recording(*committed_scenario()))},
        arguments,
        remedy="just fixtures-seed assets-register",
    )


if __name__ == "__main__":
    main()
