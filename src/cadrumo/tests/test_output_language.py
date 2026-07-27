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

from ..application.user_profile import profile_create_storage_span
from ..core.config import override_settings
from ..core.i18n import output_language
from .secure_sql import isolated_profile_storage_root
from .user_profile import register_minimal_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture
def isolated_language_state(tmp_path: Path) -> Iterator[None]:
    """Pin the unset-language state via ContextVar and bootstrap a
    real profile storage span.

    Empty-string ``cadrumo_output_language`` shadows any ambient env
    value; the storage-isolation + profile-create span gives the
    locale resolver a real backing store to read from.
    """

    with (
        override_settings(cadrumo_output_language=""),
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("00000000-0000-4000-8000-000000000000"),
    ):
        yield


def _seed_profile_language(language: str) -> None:
    from ..application.user_profile import set_active_field
    from ..application.workflow import workflow_state_repository
    from ..domain.user_profile import UserProfileFact

    repository = workflow_state_repository()
    repository.update(lambda state: register_minimal_profile(state, profile_id="00000000-0000-4000-8000-000000000000"))
    repository.update(
        lambda state: set_active_field(state, UserProfileFact(path="preferences.output_language", value=language)),
    )


def test_output_language_reads_active_profile_without_emitting_bucket_events(
    isolated_language_state: None,
) -> None:
    del isolated_language_state
    from ..application.workflow import workflow_state_repository

    _seed_profile_language("ca")
    repository = workflow_state_repository()
    before = len(repository.load().bucket_events)

    assert output_language() == "ca"

    assert len(repository.load().bucket_events) == before


def test_environment_output_language_override_wins_over_profile(
    isolated_language_state: None,
) -> None:
    del isolated_language_state
    _seed_profile_language("ca")

    with override_settings(cadrumo_output_language="en"):
        assert output_language() == "en"


def test_environment_output_language_override_is_canonical(
    isolated_language_state: None,
) -> None:
    del isolated_language_state
    _seed_profile_language("ca")

    with override_settings(cadrumo_output_language="es"):
        assert output_language() == "es"


def test_clean_install_defaults_to_spanish(isolated_language_state: None) -> None:
    del isolated_language_state
    assert output_language() == "es"


def test_unsupported_profile_output_language_is_refused_at_the_edit_door(
    isolated_language_state: None,
) -> None:
    """The profile can never come to hold an unsupported language code.

    ``preferences.output_language`` is a schema enum, and the edit door
    validates against the schema, so the only writer refuses ``"zz"`` rather
    than storing it for the resolver to cope with later. Resolution is
    unaffected and still answers the settings default.

    This asserts the enforcement POINT, which the resolver-level fallback it
    replaced could not: that test seeded an unsupported value and watched the
    resolver shrug, which stopped being reachable once the field became an
    enum. The resolver's own tolerance of an unsupported code is still covered
    where it belongs, against the registered resolver seam in
    ``core.i18n.tests.test_render_override``.
    """
    del isolated_language_state
    from ..domain.user_profile import ProfileSchemaValidationError

    with pytest.raises(ProfileSchemaValidationError):
        _seed_profile_language("zz")

    assert output_language() == "es"
