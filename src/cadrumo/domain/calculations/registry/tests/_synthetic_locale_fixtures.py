"""Shared synthetic-locale lifecycle for registry tests."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from .....tests.locales_root_fixture import locales_root_scope


class SyntheticLocaleState:
    root: Path | None = None


synthetic_locale_state = SyntheticLocaleState()


@pytest.fixture(autouse=True)
def _synthetic_locale_scope(tmp_path: Path, request: pytest.FixtureRequest) -> Iterator[None]:
    if "committed" in request.node.nodeid:
        yield
        return
    (tmp_path / "es.yml").write_text("", encoding="utf-8")
    with locales_root_scope(tmp_path):
        synthetic_locale_state.root = tmp_path
        try:
            yield
        finally:
            synthetic_locale_state.root = None


__all__ = ["_synthetic_locale_scope", "synthetic_locale_state"]
