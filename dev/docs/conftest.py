"""Pytest harness for the resident vaultspec-rag service tests.

The resident service's pytest isolation guard requires a per-process root and
explicit status and Qdrant locations.  Keep those values scoped to tests that
actually query the service so ordinary docs tests retain the ambient
environment and child ``uv run vaultspec-rag`` processes inherit the same
isolated settings through ``os.environ``.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol, runtime_checkable

import pytest

from cadrumo.tests import temporary_env


@runtime_checkable
class _MarkerNode(Protocol):
    def get_closest_marker(self, name: str) -> object | None: ...


@pytest.fixture(scope="session")
def _resident_service_environment(  # pyright: ignore[reportUnusedFunction]  # pytest discovers this fixture by decorator.
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[None]:
    """Give resident-service child processes one isolated root for this pytest process."""
    root = tmp_path_factory.mktemp("vaultspec-rag-pytest")
    status_dir = root / "status"
    qdrant_dir = root / "qdrant"
    status_dir.mkdir()
    qdrant_dir.mkdir()

    with temporary_env(
        _VAULTSPEC_RAG_PYTEST_SINGLETON_ROOT=str(root),
        _VAULTSPEC_RAG_PYTEST_SINGLETON_ACTIVE="1",
        VAULTSPEC_RAG_STATUS_DIR=str(status_dir),
        VAULTSPEC_RAG_QDRANT_STORAGE_DIR=str(qdrant_dir),
    ):
        yield


@pytest.fixture(autouse=True)
def _inherit_resident_service_environment(  # pyright: ignore[reportUnusedFunction]  # pytest discovers this fixture by decorator.
    request: pytest.FixtureRequest,
) -> None:
    """Activate the session environment only for resident-service test items."""
    request_node: object = getattr(request, "node", None)
    if not isinstance(request_node, _MarkerNode):
        raise TypeError("pytest request node does not expose marker lookup")
    if request_node.get_closest_marker("resident_service") is not None:
        request.getfixturevalue("_resident_service_environment")
