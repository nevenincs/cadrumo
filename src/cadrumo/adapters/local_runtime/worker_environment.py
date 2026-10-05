"""Explicit path controls retained across an installed worker's clean environment."""

from __future__ import annotations

from ...core.config import Settings


def worker_path_environment_names() -> frozenset[str]:
    """Keep configured storage and published authority locations without ambient credentials.

    Published authority is separate from taxpayer storage. Its configured root
    must reach the isolated worker that composes the same installed operation graph.
    """
    return Settings.storage_env_var_names() | {"CADRUMO_AUTHORITY_ROOT", "TEMP", "TMP", "TMPDIR"}
