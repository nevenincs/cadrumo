"""The output-language cache must survive resolving the language.

Resolving the active profile's language scopes its own read with
``override_settings(cadrumo_active_profile=...)``, and ``override_settings``
invalidates the language cache at both of its boundaries. The resolution
therefore invalidated the entry it was about to store, and because the
invalidation counter is part of the cache key, every subsequent call was keyed
to a dead version: a cache that could never serve a hit while a bucket session
was bound.

The cost was not marginal. Each miss is a full encrypted profile read and three
``Settings`` constructions, and every ``tr()`` goes through this resolution, so
one manager repaint paid it a few hundred times -- around thirteen seconds to
re-word the page after a language change, on a surface whose whole purpose is
to answer in the language just chosen.

These tests drive the real resolver against real encrypted storage. The first
pins the reuse; the rest are the controls that keep it honest, because a cache
that never invalidates would satisfy the first test and serve a stale language
forever.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....core.config import override_settings
from ....core.i18n import _render, clear_output_language_cache, output_language
from ....domain.user_profile import UserProfileFact
from ....tests.secure_sql import isolated_profile_storage_root
from .. import register_profile_with_credentials, set_active_field

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_LABEL = "Language Cache Subject"
_PASSPHRASE = "output-language-cache-operator-secret"  # noqa: S105 - synthetic test fixture
_LANGUAGE_PATH = "preferences.output_language"


def _register_in(language: str) -> None:
    register_profile_with_credentials(
        label=_LABEL,
        passphrase=_PASSPHRASE,
        facts=(UserProfileFact(path=_LANGUAGE_PATH, value=language),),
    )


def _cache_generation() -> int:
    """Read the invalidation counter folded into the cache key.

    Observed directly on the real module rather than through an interception,
    so what the test watches is what production increments.
    """
    return _render._OUTPUT_LANGUAGE_CACHE_VERSION


def _write_language(language: str) -> None:
    """Persist a new language through the ordinary profile-write door."""
    from ...workflow import workflow_state_repository

    workflow_state_repository().update(
        lambda state: set_active_field(state, UserProfileFact(path=_LANGUAGE_PATH, value=language))
    )


def test_resolving_the_language_does_not_invalidate_its_own_cache(tmp_path: Path) -> None:
    """A second resolution is served from the cache the first one filled.

    The counter is read across the pair rather than timing the calls: a
    duration is a property of the machine, while the counter moving is the
    defect itself. A resolution that bumps it has invalidated the entry it
    just stored, and the next caller is guaranteed a miss.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _register_in("en")
        clear_output_language_cache()

        assert output_language() == "en"
        settled = _cache_generation()
        hits = _render._cached_output_language.cache_info().hits

        assert output_language() == "en"

        assert _cache_generation() == settled, (
            "resolving the language invalidated its own cache, so every tr() pays a full encrypted profile read"
        )
        assert _render._cached_output_language.cache_info().hits == hits + 1, (
            "the second resolution was recomputed rather than served from the cache"
        )


def test_a_profile_write_that_moves_the_language_is_still_seen(tmp_path: Path) -> None:
    """The control for the test above: reuse must not outlive a real write.

    Suppression is scoped to the resolver's own scoping block, so the
    profile-write invalidation path is untouched. Without this the first test
    would pass just as well against a cache that never invalidated at all.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _register_in("en")
        clear_output_language_cache()
        assert output_language() == "en"

        _write_language("ca")

        assert output_language() == "ca", "a persisted language change was served from a stale cache"


def test_an_explicit_settings_override_still_takes_effect(tmp_path: Path) -> None:
    """The registration screen's door: an override must be seen immediately.

    Registration has no profile behind it, so a settings-level override is the
    only way its page can answer in the language just chosen. That block is
    opened by the screen rather than by a resolution, so it is never
    suppressed, and the language must move at both of its boundaries.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _register_in("en")
        clear_output_language_cache()
        assert output_language() == "en"

        with override_settings(cadrumo_output_language="hu"):
            assert output_language() == "hu", "an explicit override was not observed inside its block"

        assert output_language() == "en", "the override outlived its own block"
