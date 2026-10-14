"""Explicit path controls retained across an installed worker's clean environment."""

from __future__ import annotations

from ...core.storage_environment import TEMPORARY_VARIABLES, relayed_setting_names


def worker_path_environment_names() -> frozenset[str]:
    """Keep configured storage and published authority locations without ambient credentials.

    These are the settings a profile worker takes from the runtime that starts
    it, plus the temporary variables pinned beneath its root. Published
    authority is separate from taxpayer storage; its configured root must reach
    the isolated worker that composes the same installed operation graph.
    """
    return relayed_setting_names() | frozenset(TEMPORARY_VARIABLES)
