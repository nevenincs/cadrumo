"""Packaged documentation owner builds: the command and environment each language root is built with."""

from __future__ import annotations

from pathlib import Path

import pytest

from dev.docs.build import DOCS_FLAVOR_ENV, docs_build_flavor
from dev.docs.build_paths import DOCS_BUILD_ROOT_ENV
from dev.docs.sequence_build_gate import SEQUENCE_CHECK_SKIP_ENV

from ..native.docs_build import owner_build

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _effective_flavor(command: list[str], environment: dict[str, str]) -> str:
    # The owner lets an explicit --flavor argument override the environment selection.
    if "--flavor" in command:
        return command[command.index("--flavor") + 1]
    return docs_build_flavor(environment)


@pytest.mark.parametrize("check_sequences", [True, False])
def test_owner_builds_pin_the_desktop_flavor_over_an_ambient_web_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, check_sequences: bool
) -> None:
    monkeypatch.setenv(DOCS_FLAVOR_ENV, "web")
    monkeypatch.setenv(SEQUENCE_CHECK_SKIP_ENV, "1")
    root = tmp_path / "build/html/es"
    command, environment = owner_build(
        "es", root, tmp_path / "storage", build_root=tmp_path / "build", check_sequences=check_sequences, jobs=2
    )
    assert _effective_flavor(command, environment) == "desktop"
    assert command[command.index("--language") + 1] == "es"
    assert command[command.index("--out-dir") + 1] == str(root)
    assert environment[DOCS_BUILD_ROOT_ENV] == str(tmp_path / "build")
    # The ambient skip is dropped, so only the declared first root runs the sequence gate.
    assert (SEQUENCE_CHECK_SKIP_ENV not in environment) is check_sequences
