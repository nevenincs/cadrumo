"""Rendering reads the profile language from memory, never from storage.

The language is snapshotted when a host composes and when a session or the
preference changes; ``tr()`` on an interface event loop must then render
without opening a file, even right after its cache was invalidated.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Generator
from pathlib import Path

import pytest

from ....core.config import override_settings
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import (
    clear_output_language_cache,
    output_language,
    profile_output_language_precedence,
    register_profile_language_resolver,
    tr,
)
from ....tests.thread_file_io_probe import recording_file_io
from ..language_resolver import (
    adopt_profile_output_language,
    refresh_active_profile_output_language,
    register_language_resolver,
    resolve_active_profile_output_language,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_KEY = "tui.home.title"


@pytest.fixture
def composed_language_host(tmp_path: Path) -> Generator[None]:
    """A host with no explicit language setting and the production resolver registered."""
    with override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_output_language=""):
        register_language_resolver()
        tr(_KEY)  # the locale catalogue itself is loaded once, at first use
        try:
            yield
        finally:
            register_language_resolver()


def _render_after_invalidation() -> list[str]:
    clear_output_language_cache()
    with recording_file_io(threading.get_ident()) as accesses:
        tr(_KEY)
    return list(accesses)


def test_rendering_after_an_invalidation_opens_no_file(composed_language_host: None) -> None:
    del composed_language_host
    assert _render_after_invalidation() == []


def test_the_gate_detects_a_resolver_that_reads_storage(composed_language_host: None, tmp_path: Path) -> None:
    """Detector teeth: a resolver that reads a file on every resolution is caught."""
    del composed_language_host
    preference = tmp_path / "language-preference"
    preference.write_text("ca", encoding="utf-8")
    register_profile_language_resolver(lambda: preference.read_text(encoding="utf-8"))

    accesses = _render_after_invalidation()

    assert any(access.startswith("open:") and access.endswith("language-preference") for access in accesses)
    assert output_language() == "ca"


def test_a_host_with_no_selected_profile_snapshots_no_profile_language(composed_language_host: None) -> None:
    del composed_language_host
    # No profile is selected in this host, so storage holds no preference.
    assert refresh_active_profile_output_language() is None
    assert resolve_active_profile_output_language() is None
    assert output_language() == "es"


def test_canonical_preference_adoption_changes_rendering_without_file_io(composed_language_host: None) -> None:
    del composed_language_host
    # Catalogues are lazy; measure resolver invalidation after loading the
    # target locale, just as the composed host fixture loads its initial one.
    with override_settings(cadrumo_output_language=OutputLanguage.HU):
        tr(_KEY)
    assert adopt_profile_output_language(OutputLanguage.HU)
    assert resolve_active_profile_output_language() == "hu"
    assert output_language() == "hu"
    assert _render_after_invalidation() == []
    assert not adopt_profile_output_language(OutputLanguage.HU)
    assert adopt_profile_output_language(None)
    assert output_language() == "es"


def test_interactive_profile_choice_precedes_inherited_setting_without_changing_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The TUI's live preference agrees with the canonical desktop value; CLI stays transient."""
    monkeypatch.setenv("CADRUMO_OUTPUT_LANGUAGE", "es")
    with override_settings(cadrumo_local_storage_root=tmp_path):
        register_language_resolver()
        try:
            adopt_profile_output_language(OutputLanguage.CA)
            assert output_language() == "es"
            with profile_output_language_precedence():
                assert output_language() == "ca"
                tr(_KEY)  # Load the target catalogue before observing resolver I/O.
                assert _render_after_invalidation() == []

                async def read_worker_language() -> str:
                    return await asyncio.to_thread(output_language)

                assert asyncio.run(read_worker_language()) == "ca"
                adopt_profile_output_language(OutputLanguage.HU)
                assert output_language() == "hu"
                adopt_profile_output_language(None)
                assert output_language() == "es"
                adopt_profile_output_language(OutputLanguage.CA)
            assert output_language() == "es"
            with override_settings(cadrumo_output_language=OutputLanguage.EN):
                assert output_language() == "en"
            assert output_language() == "es"
        finally:
            register_language_resolver()


def test_interactive_language_scope_restores_cli_precedence_after_failure(composed_language_host: None) -> None:
    del composed_language_host
    adopt_profile_output_language(OutputLanguage.CA)
    with override_settings(cadrumo_output_language=OutputLanguage.ES):
        with pytest.raises(RuntimeError, match="host closed"), profile_output_language_precedence():
            assert output_language() == "ca"
            raise RuntimeError("host closed")
        assert output_language() == "es"
