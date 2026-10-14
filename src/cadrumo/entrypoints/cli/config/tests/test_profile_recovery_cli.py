"""Tax profile-archive CLI behavior adjacent to the moved recovery commands."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from click.testing import Result

from ...verb_input_schema import build_verb_input_schemas

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_archive_import_no_longer_takes_a_recovery_artifact(run_cadrumo_cli: Callable[..., Result]) -> None:
    """The portable artifact is gone; restore proves the passphrase and nothing else."""
    schema = build_verb_input_schemas(("config.profile.archive.import",))["config.profile.archive.import"]
    assert [parameter.name for parameter in schema.parameters] == [
        "label",
        "file",
        "secrets_stdin",
        "secrets_fd",
        "output_language",
    ]
    help_result = run_cadrumo_cli(("config", "profile", "archive", "import", "--help"))
    assert help_result.exit_code == 0, help_result.output
    assert "--artifact" not in help_result.output
