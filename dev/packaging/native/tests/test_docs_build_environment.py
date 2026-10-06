"""Native documentation build selectors remain owned by the packaging driver."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from dev.docs.build import DOCS_FLAVOR_ENV, docs_build_flavor, pagefind_index_mode
from dev.docs.build_paths import docs_site_prefix

from .. import docs_build
from ..docs_build import _owner_environment

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_owner_builds_pin_the_desktop_flavor_over_an_ambient_web_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DOCS_FLAVOR_ENV, "web")
    environment = _owner_environment(
        tmp_path / "build", tmp_path / "storage", language="en", check_sequences=True, jobs=1
    )
    assert docs_build_flavor(environment) == "desktop"


@pytest.mark.parametrize(("language", "prefix"), [("en", ""), ("es", "es/"), ("hu", "hu/")])
def test_owner_builds_index_nothing_and_carry_their_place_in_the_staged_site(
    tmp_path: Path, language: str, prefix: str
) -> None:
    """A root build writes no index and declares where the staged site serves it.

    The packaged site has ONE index, built over every root once they are all
    built, so a root that indexed itself would write one addressed to its build
    directory instead of to the staged layout. The prefix is the other half: the
    apex language is served at the top and the others under their own directory,
    and a page resolves the one index and a shared result's destination against
    it. Both are read back through the owners that consume them rather than by
    comparing raw strings, so a renamed key cannot pass this.
    """
    environment = _owner_environment(
        tmp_path / "build", tmp_path / "storage", language=language, check_sequences=True, jobs=1
    )

    assert pagefind_index_mode(environment) == "none"
    assert docs_site_prefix(environment) == prefix


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
