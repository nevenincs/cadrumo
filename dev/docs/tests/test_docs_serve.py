"""Unit gate for the live-reloading documentation server command builder.

Asserts that :func:`dev.docs.serve.serve_command` watches both documentation
surfaces (the narrative corpus and the ``src/aeat`` docstring source) and that
the self-regenerated trees are excluded from the watch set so a rebuild cannot
loop on its own output.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from dev.docs.serve import serve_command

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_REPO_ROOT = Path(__file__).resolve().parents[3]


def test_serve_command_watches_docs_and_autodoc_source() -> None:
    """The command serves docs/ and watches the src/aeat docstring surface."""
    command = serve_command(_REPO_ROOT, host="127.0.0.1", port=8000, open_browser=False)
    assert command[1:3] == ["-m", "sphinx_autobuild"]
    assert str(_REPO_ROOT / "docs") in command
    assert str(_REPO_ROOT / "docs" / "_build" / "html") in command
    watch_index = command.index("--watch")
    assert command[watch_index + 1] == str(_REPO_ROOT / "src" / "aeat")


def test_serve_command_excludes_self_regenerated_trees() -> None:
    """The generated CLI tree and build output are ignored to prevent a loop."""
    command = serve_command(_REPO_ROOT, host="127.0.0.1", port=8000, open_browser=False)
    ignores = [command[index + 1] for index, flag in enumerate(command) if flag == "--ignore"]
    sep = os.sep
    assert f"*{sep}docs{sep}cli{sep}*" in ignores
    assert any("_build" in pattern for pattern in ignores)
    # The docs/cli ignore must be anchored so it does not also swallow changes
    # to the unrelated src/aeat/entrypoints/cli source tree.
    assert f"*{sep}cli{sep}*" not in ignores


def test_serve_command_open_browser_flag_is_optional() -> None:
    """The browser-open flag and port are threaded through to the command."""
    with_browser = serve_command(_REPO_ROOT, host="127.0.0.1", port=9001, open_browser=True)
    without_browser = serve_command(_REPO_ROOT, host="127.0.0.1", port=9001, open_browser=False)
    assert "--open-browser" in with_browser
    assert "--open-browser" not in without_browser
    assert "9001" in with_browser
