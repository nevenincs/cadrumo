"""Native documentation build selectors remain owned by the packaging driver."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from dev.docs.build import DOCS_FLAVOR_ENV, docs_build_flavor

from .. import docs_build
from ..docs_build import _owner_environment

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_owner_builds_pin_the_desktop_flavor_over_an_ambient_web_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DOCS_FLAVOR_ENV, "web")
    environment = _owner_environment(tmp_path / "build", tmp_path / "storage", check_sequences=True, jobs=1)
    assert docs_build_flavor(environment) == "desktop"


@pytest.mark.parametrize("english_exit", [0, 1])
def test_strict_english_gate_finishes_before_localized_owners(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, english_exit: int
) -> None:
    runs = []
    english_finished = False
    monkeypatch.setattr(docs_build.os, "cpu_count", lambda: 16)

    def owner(language: str, root: Path, storage: Path, **settings: object):
        assert settings["check_sequences"] is (language == "en")
        assert settings["jobs"] == (2 if language == "en" else 5)
        return [language], {}

    def execute(command: list[str], **settings: object):
        nonlocal english_finished
        language = command[0]
        if language != "en":
            assert english_finished
        runs.append(language)
        if language == "en":
            english_finished = True
        return SimpleNamespace(
            returncode=english_exit if language == "en" else 0,
            stdout="",
            stderr="",
            duration_seconds=0,
        )

    monkeypatch.setattr(docs_build, "owner_build", owner)
    monkeypatch.setattr(docs_build, "run_command", execute)
    if english_exit:
        with pytest.raises(SystemExit, match="User documentation build failed: en"):
            docs_build._run_owner_builds(tmp_path / "build", tmp_path / "work", ("en", "es", "ca", "hu"))
        assert runs == ["en"]
    else:
        docs_build._run_owner_builds(tmp_path / "build", tmp_path / "work", ("en", "es", "ca", "hu"))
        assert runs[0] == "en"
        assert set(runs) == {"en", "es", "ca", "hu"}
