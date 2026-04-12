"""Live smoke tests for the Cloud sub-app.

Read-only round-trips against Cloud Functions, Cloud Run, and Cloud
Storage. An empty list is success — these tests verify that the API
call returns 2xx, not that any specific resource exists in the project.
"""

from __future__ import annotations

import pytest

from aeat.cli._live import (
    cloudfunctions_client,
    cloudrun_client,
    requires_live_enabled,
    requires_project,
    storage_client,
)


@pytest.mark.live
class TestCloudLive:
    """Read-only Cloud surface smoke tests."""

    def test_storage_list_buckets(self) -> None:
        requires_live_enabled()
        project = requires_project()
        client = storage_client(project)
        # Iterate at most a few buckets so the test stays fast in
        # projects with many buckets. The point is the call shape.
        result = list(client.list_buckets(max_results=5))
        assert isinstance(result, list)

    def test_functions_list(self) -> None:
        requires_live_enabled()
        project = requires_project()
        client = cloudfunctions_client()
        parent = f"projects/{project}/locations/-"
        result = list(client.list_functions(parent=parent))
        assert isinstance(result, list)

    def test_run_list_services(self) -> None:
        requires_live_enabled()
        project = requires_project()
        client = cloudrun_client()
        parent = f"projects/{project}/locations/-"
        result = list(client.list_services(parent=parent))
        assert isinstance(result, list)
