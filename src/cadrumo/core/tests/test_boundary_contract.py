"""Regression check for a retired core error symbol.

Dependency direction belongs exclusively to ``just check-import-boundaries``.
This module keeps only the independent source-removal regression for the
historical ``WorkspaceLockedError`` symbol.

See Also:
    :func:`~tests._inventory.production_python_files`
        Production source inventory used by the removed-symbol regression
        guard.
"""

from __future__ import annotations

import pytest

from ...tests.inventory import production_python_files, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_workspace_locked_error_is_not_present_in_production_sources() -> None:
    """The removed ``WorkspaceLockedError`` symbol must not reappear."""
    removed_error_name = "Workspace" + "LockedError"
    offenders: list[str] = []
    for path in production_python_files():
        if removed_error_name in path.read_text(encoding="utf-8"):
            offenders.append(repo_relative(path))

    assert offenders == []
