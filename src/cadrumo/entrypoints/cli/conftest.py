from collections.abc import Iterator
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.tests.published_authority_support import (
    release_published_authority_operation,
)

from ...core.config import reset_settings_cache
from ...core.external_constants import OUTPUT_LANGUAGE_ENV_VAR
from ...core.i18n.render import clear_output_language_cache
from ...tests.env import temporary_env


@pytest.fixture(scope="session", autouse=True)
def _published_authority_lease() -> Iterator[None]:
    """Release the per-worker published authority lease that seeded CLI fixtures take."""
    yield
    release_published_authority_operation()


@pytest.fixture(autouse=True)
def force_english_output() -> Iterator[None]:
    """Pin CLI output to English so test assertions stay readable.

    The production default is ``es``; this fixture only affects test
    output, not runtime behaviour.

    Writing the variable is not a pin on its own.
    :class:`~cadrumo.core.config.Settings` is built once per active-profile
    pointer state and then held, so an instance constructed before this
    fixture ran carries no explicit ``cadrumo_output_language``; the
    resolver finds the field absent from ``model_fields_set`` and falls
    through to whatever language the machine's active profile happens to
    carry. Dropping the held instances at both boundaries is what turns the
    write into a pin, and it leaves the language resolution independent of
    whether anything else in the test happens to force a rebuild.

    :func:`~cadrumo.core.config.override_settings` is the usual door for a
    settings value, but it is the wrong one at package-wide autouse scope:
    it snapshots EVERY field for the whole block, so a test that creates a
    profile or logs in would keep reading the route captured before that
    happened. The variable plus an invalidation keeps the pointer-keyed
    rebuild intact, and it reaches the console subprocesses a number of
    these tests spawn, which an in-process override cannot.
    """
    with temporary_env(**{OUTPUT_LANGUAGE_ENV_VAR: "en"}):
        reset_settings_cache()
        clear_output_language_cache()
        try:
            yield
        finally:
            reset_settings_cache()
            clear_output_language_cache()


@pytest.fixture(autouse=True)
def isolated_cadrumo_root(tmp_path: Path) -> Iterator[None]:
    """Point `Settings.cadrumo_local_storage_root` at the test's `tmp_path`."""
    with temporary_env(CADRUMO_LOCAL_STORAGE_ROOT=str(tmp_path)):
        yield
