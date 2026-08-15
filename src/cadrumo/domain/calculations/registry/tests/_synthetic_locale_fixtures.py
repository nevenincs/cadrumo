"""Shared synthetic-locale lifecycle for registry tests."""

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from .....tests.locales_root_fixture import locales_root_scope


class SyntheticLocaleState:
    root: Path | None = None


synthetic_locale_state = SyntheticLocaleState()

#: Node-id substrings whose tests exercise the real bundled/committed
#: registry corpus rather than a synthetic one and so must keep the
#: packaged locale catalogue untouched. Extend this set (never hand-roll a
#: parallel scope) when a new bundled-data test needs the same escape.
BUNDLED_DATA_MARKERS: tuple[str, ...] = (
    "committed",
    "m100_2024_2025",
    "reviewed_singleton_markers",
    "quarterly_contraparte",
)


@pytest.fixture(autouse=True)
def _synthetic_locale_scope(tmp_path: Path, request: pytest.FixtureRequest) -> Iterator[None]:
    if any(marker in request.node.nodeid for marker in BUNDLED_DATA_MARKERS):
        yield
        return
    (tmp_path / "es.yml").write_text("", encoding="utf-8")
    with locales_root_scope(tmp_path):
        synthetic_locale_state.root = tmp_path
        try:
            yield
        finally:
            synthetic_locale_state.root = None


def _write_test_label(label: str) -> str:
    """Enroll one synthetic Spanish value in the test-only catalogue.

    Appends the key/value pair to the active
    :data:`synthetic_locale_state` root's ``es.yml`` (a no-op outside the
    ``_synthetic_locale_scope`` fixture's scope) and returns the derived
    localization key.
    """
    key = f"test.schema.casilla.{hashlib.sha256(label.encode('utf-8')).hexdigest()}.label"
    if synthetic_locale_state.root is not None:
        with (synthetic_locale_state.root / "es.yml").open("a", encoding="utf-8") as handle:
            handle.write(f"{json.dumps(key)}: {json.dumps(label, ensure_ascii=False)}\n")
    return key


__all__ = ["_synthetic_locale_scope", "_write_test_label", "synthetic_locale_state"]
