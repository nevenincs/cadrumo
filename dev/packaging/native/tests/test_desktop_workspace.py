"""The desktop takes its locations from the package's declaration, never from a Python query."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ..application_environment import load
from ..generate import generate

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DESKTOP = REPO_ROOT / "native/desktop/src-tauri/src"


def test_the_contract_carries_every_location_the_desktop_projects(tmp_path: Path) -> None:
    generate(REPO_ROOT, tmp_path, target="windows-x86-64")
    defaults = json.loads((tmp_path / "contract.json").read_text(encoding="utf-8"))["desktop_defaults"]
    components = load(REPO_ROOT).components
    assert {key: defaults[key] for key in ("console_workspace", "webview", "manager_log_file", "logs")} == {
        key: components[key] for key in ("console_workspace", "webview", "manager_log_file", "logs")
    }
    # Only the command line's log directory may be relocated, by the one declared location name.
    assert defaults["log_variable"] in load(REPO_ROOT).groups["locations"]
    assert defaults["output_language_variable"] == components["language_variable"]


def test_the_desktop_embeds_no_location_query_for_python() -> None:
    environment = (_DESKTOP / "environment.rs").read_text(encoding="utf-8")
    assert 'include_str!("python/environment.py")' not in environment
    assert not (_DESKTOP / "python/environment.py").exists()
    for source in _DESKTOP.rglob("*.py"):
        text = source.read_text(encoding="utf-8")
        for member in ("DESKTOP_WEBVIEW", "CONSOLE_WORKSPACE", "MANAGER_LOG_FILE"):
            assert member not in text, (source, member)
