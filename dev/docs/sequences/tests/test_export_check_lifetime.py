"""Public refresh and check validate real artifacts before temporary cleanup."""

from pathlib import Path

import pytest

from cadrumo.core.config import load_settings, override_settings
from cadrumo.tests.env_scope import derived_storage_settings

from ..checks import check_sequences, refresh_sequences

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]


@pytest.mark.parametrize("sequence_id", ["quickstart-export", "verification-reports-export-check"])
def test_public_refresh_and_check_keep_real_fichero_artifact_alive(
    sequence_id: str,
    tmp_path: Path,
) -> None:
    authority_root = load_settings().cadrumo_authority_root
    goldens_root = tmp_path / "goldens"
    with (
        derived_storage_settings(tmp_path / "storage"),
        override_settings(cadrumo_authority_root=authority_root),
    ):
        written, problems, _ = refresh_sequences(sequence_id=sequence_id, goldens_root=goldens_root)
        assert not problems and len(written) == 1
        # Both calls intentionally use the public owner's default temporary
        # sandbox; no retained sandbox or substituted executor can hide cleanup.
        problems, _ = check_sequences(sequence_id=sequence_id, goldens_root=goldens_root)
        assert not problems
