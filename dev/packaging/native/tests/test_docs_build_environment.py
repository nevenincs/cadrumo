"""Native documentation build selectors remain owned by the packaging driver."""

from pathlib import Path

import pytest

from dev.docs.build import DOCS_FLAVOR_ENV, docs_build_flavor

from ..docs_build import _owner_environment

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_owner_builds_pin_the_desktop_flavor_over_an_ambient_web_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DOCS_FLAVOR_ENV, "web")
    environment = _owner_environment(tmp_path / "build", tmp_path / "storage", check_sequences=True, jobs=1)
    assert docs_build_flavor(environment) == "desktop"
