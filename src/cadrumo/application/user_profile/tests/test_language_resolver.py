"""Integration tests for profile-owned output-language resolution.

Tests exercise the full application stack: language preference is stored
in the active profile via the workflow state repository and read back
through core.i18n._render.output_language. Requires an isolated storage
runtime for each test (no shared global state).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....core.config import override_settings
from ....core.i18n import output_language
from ....core.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from cadrumo.application.user_profile.login_session import login_profile
from cadrumo.application.user_profile.registration import register_profile_with_credentials

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture
def isolated_language_state(tmp_path: Path) -> Iterator[str]:
    """Pin unset language state while bootstrapping a real storage span.

    Empty-string ``cadrumo_output_language`` shadows any ambient environment
    value; storage isolation plus the profile-create span gives the locale
    resolver a real backing store to read from.
    """

    test_value = f"output-language-resolver-{tmp_path.name}"
    with (
        override_settings(cadrumo_output_language="", cadrumo_secret_passphrase=test_value),
        isolated_profile_storage_root(tmp_path=tmp_path),
    ):
        outcome = register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label="Output language resolver",
            passphrase=test_value,
        )
        login_profile(name=outcome.label, passphrase_callback=test_value.__str__)
        yield outcome.profile_id


def _seed_profile_language(language: str, *, profile_id: str) -> None:
    register_minimal_profile(
        profile_id=profile_id,
        overrides={PROFILE_OUTPUT_LANGUAGE_PATH: language},
    )


def test_output_language_reads_active_profile_without_emitting_bucket_events(
    isolated_language_state: str,
) -> None:
    from cadrumo.application.workflow.persistence import workflow_state_repository

    _seed_profile_language("ca", profile_id=isolated_language_state)
    repository = workflow_state_repository()
    before = len(repository.load().bucket_events)

    assert output_language() == "ca"

    assert len(repository.load().bucket_events) == before


def test_environment_output_language_override_wins_over_profile(
    isolated_language_state: str,
) -> None:
    _seed_profile_language("ca", profile_id=isolated_language_state)

    with override_settings(cadrumo_output_language="en"):
        assert output_language() == "en"


def test_environment_output_language_override_is_canonical(
    isolated_language_state: str,
) -> None:
    _seed_profile_language("ca", profile_id=isolated_language_state)

    with override_settings(cadrumo_output_language="es"):
        assert output_language() == "es"


def test_clean_install_defaults_to_spanish(isolated_language_state: str) -> None:
    del isolated_language_state
    assert output_language() == "es"
