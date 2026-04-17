"""Live smoke tests for the Cloud sub-app.

Read-only round-trips against Cloud Functions, Cloud Run, and Cloud
Storage. An empty list is success — these tests verify that the API
call returns 2xx, not that any specific resource exists in the project.

These three APIs all require an active billing account on the project.
On a project without billing the calls fail with ``PermissionDenied``
and the tests skip cleanly so the live suite stays green for projects
that opt out of billing-gated features.
"""

from __future__ import annotations

import pytest

from ._live import (
    cloudfunctions_client,
    cloudrun_client,
    requires_live_enabled,
    requires_project,
    storage_client,
)

pytestmark = [pytest.mark.live_read, pytest.mark.domain_infra]


def _skip_if_no_billing(exc: Exception) -> None:
    """Skip the calling test if the exception looks like a billing block."""
    text = repr(exc).lower()
    if "billing" in text or "permission" in text or "403" in text or "consumer" in text:
        pytest.skip(f"cloud API requires billing on the project: {exc.__class__.__name__}")
    raise exc


class TestCloudLive:
    """Read-only Cloud surface smoke tests."""

    def test_storage_list_buckets(self) -> None:
        requires_live_enabled()
        project = requires_project()
        try:
            client = storage_client(project)
            result = list(client.list_buckets(max_results=5))
        except Exception as exc:
            _skip_if_no_billing(exc)
            return
        assert isinstance(result, list)

    def test_functions_list(self) -> None:
        requires_live_enabled()
        project = requires_project()
        try:
            client = cloudfunctions_client()
            parent = f"projects/{project}/locations/-"
            result = list(client.list_functions(parent=parent))
        except Exception as exc:
            _skip_if_no_billing(exc)
            return
        assert isinstance(result, list)

    def test_run_list_services(self) -> None:
        requires_live_enabled()
        project = requires_project()
        try:
            client = cloudrun_client()
            parent = f"projects/{project}/locations/-"
            result = list(client.list_services(parent=parent))
        except Exception as exc:
            _skip_if_no_billing(exc)
            return
        assert isinstance(result, list)
