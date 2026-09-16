"""Rendering reads the profile language from memory, never from storage.

The language is snapshotted when a host composes and when a session or the
preference changes; ``tr()`` on an interface event loop must then render
without opening a file, even right after its cache was invalidated.
"""

from __future__ import annotations

import threading
from collections.abc import Generator
from pathlib import Path

import pytest

from ....core.config import override_settings
from ....core.i18n.render import (
    clear_output_language_cache,
    output_language,
    register_profile_language_resolver,
    tr,
)
from ....tests.thread_file_io_probe import recording_file_io
from ..language_resolver import (
    refresh_active_profile_output_language,
    register_language_resolver,
    resolve_active_profile_output_language,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_KEY = "tui.local_reader.title"


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
