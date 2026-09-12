"""Integration tests for profile-owned output-language resolution.

Tests exercise the full application stack: language preference is stored
in the active profile via the workflow state repository and read back
through core.i18n.render.output_language. Requires an isolated storage
runtime for each test (no shared global state).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.user_profile.login_session import login_profile
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.core.config import override_settings
from cadrumo.core.i18n.render import output_language
from cadrumo.core.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from cadrumo.tests.user_profile import register_minimal_profile

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


def test_a_language_fact_write_mirrors_the_bucket_hint(isolated_language_state: str) -> None:
    """The preference must survive a lock, which only the non-secret hint can do.

    ``resolve_active_profile_output_language`` falls back to the bucket hint
    whenever no session is bound. Nothing wrote that hint, so the fallback
    always found nothing and a chosen language silently reverted to the
    settings default on every pre-login surface.
    """
    from cadrumo.application.user_profile.fact_write import ProfileFactWriteDoor, apply_profile_fact_changes
    from cadrumo.application.user_profile.language_resolver import resolve_profile_output_language_hint
    from cadrumo.core.bucket_pointer import resolve_active_bucket_id
    from cadrumo.core.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH as _LANGUAGE_PATH
    from cadrumo.domain.user_profile.values import UserProfileFact

    _seed_profile_language("es", profile_id=isolated_language_state)
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None, "the seeded profile must bind an active bucket"

    apply_profile_fact_changes(
        profile_id=isolated_language_state,
        changes=(UserProfileFact(path=_LANGUAGE_PATH, value="ca"),),
        door=ProfileFactWriteDoor.MANAGER_FIELD,
    )

    assert resolve_profile_output_language_hint(bucket_id) == "ca"


def test_clearing_the_language_fact_clears_the_hint(isolated_language_state: str) -> None:
    """The control: the two must not disagree about an absence."""
    from cadrumo.application.user_profile.fact_write import ProfileFactWriteDoor, apply_profile_fact_changes
    from cadrumo.application.user_profile.language_resolver import resolve_profile_output_language_hint
    from cadrumo.core.bucket_pointer import resolve_active_bucket_id
    from cadrumo.core.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH as _LANGUAGE_PATH
    from cadrumo.domain.user_profile.values import UserProfileFact

    _seed_profile_language("es", profile_id=isolated_language_state)
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None

    apply_profile_fact_changes(
        profile_id=isolated_language_state,
        changes=(UserProfileFact(path=_LANGUAGE_PATH, value="ca"),),
        door=ProfileFactWriteDoor.MANAGER_FIELD,
    )
    assert resolve_profile_output_language_hint(bucket_id) == "ca"

    apply_profile_fact_changes(
        profile_id=isolated_language_state,
        changes=(UserProfileFact(path=_LANGUAGE_PATH, value=None),),
        door=ProfileFactWriteDoor.MANAGER_FIELD,
    )

    assert resolve_profile_output_language_hint(bucket_id) is None
