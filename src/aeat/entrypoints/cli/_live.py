"""Shared fixtures and skip helpers for ``@pytest.mark.live_read`` tests.

Live tests run against real Google APIs and must satisfy two
preconditions:

- ``AEAT_LIVE_TESTS_ENABLED`` is true in ``env/.env`` (or the
  environment), and
- The relevant scratch resource ID is set (folder, sheet, doc, or
  project as appropriate).

Tests that need a precondition the workstation does not satisfy are
skipped with a clear message — they never silently pass and never hit
the API blindly. The module exposes per-precondition guards
(``requires_*``) and per-service factory helpers
(``drive_service``, ``sheets_service``, ``docs_service``,
``storage_client``, ``cloudfunctions_client``, ``cloudrun_client``)
that re-read :class:`aeat.core.config.Settings` so env edits are
picked up between tests.
"""

from __future__ import annotations

import contextlib
import uuid
from collections.abc import Iterable
from typing import Any

import pytest

from ...core.config import Settings


def _settings() -> Settings:
    """Re-read :class:`aeat.core.config.Settings` so env edits are picked up."""
    return Settings()


def requires_live_enabled() -> None:
    """Skip the calling test when ``AEAT_LIVE_TESTS_ENABLED`` is false."""
    if not _settings().aeat_live_tests_enabled:
        pytest.skip("AEAT_LIVE_TESTS_ENABLED is false; opt in via env/.env")


def requires_scratch_folder() -> str:
    """Return the configured scratch-folder ID, skipping the test if unset.

    Returns:
        The Drive folder ID stored in ``AEAT_SCRATCH_FOLDER_ID``.
    """
    settings = _settings()
    if not settings.aeat_scratch_folder_id:
        pytest.skip("AEAT_SCRATCH_FOLDER_ID is unset; run `aeat bootstrap`")
    return settings.aeat_scratch_folder_id


def requires_scratch_sheet() -> str:
    """Return the configured scratch-sheet ID, skipping the test if unset.

    Returns:
        The Sheets ID stored in ``AEAT_SCRATCH_SHEET_ID``.
    """
    settings = _settings()
    if not settings.aeat_scratch_sheet_id:
        pytest.skip("AEAT_SCRATCH_SHEET_ID is unset; run `aeat bootstrap`")
    return settings.aeat_scratch_sheet_id


def requires_scratch_doc() -> str:
    """Return the configured scratch-doc ID, skipping the test if unset.

    Returns:
        The Docs ID stored in ``AEAT_SCRATCH_DOC_ID``.
    """
    settings = _settings()
    if not settings.aeat_scratch_doc_id:
        pytest.skip("AEAT_SCRATCH_DOC_ID is unset; run `aeat bootstrap`")
    return settings.aeat_scratch_doc_id


def requires_project() -> str:
    """Return ``GOOGLE_CLOUD_PROJECT``, skipping the test if unset.

    Returns:
        The configured Google Cloud project identifier.
    """
    settings = _settings()
    if not settings.google_cloud_project:
        pytest.skip("GOOGLE_CLOUD_PROJECT is unset")
    return settings.google_cloud_project


def unique_prefix() -> str:
    """Return a UUID prefix for live-test resource names.

    Used so two parallel test runs do not collide on Drive file names
    or Sheets/Docs ranges. The prefix is short (12 hex chars) and
    URL-safe.

    Returns:
        A ``"aeat-live-<hex>"`` prefix string.
    """
    return f"aeat-live-{uuid.uuid4().hex[:12]}"


def drive_service() -> Any:
    """Build a Drive v3 service from the current ADC.

    Returns:
        The Drive ``v3`` service object.
    """
    from ...adapters.outbound.google import DRIVE_SCOPE, build_drive_service, get_credentials_for_scopes

    return build_drive_service(get_credentials_for_scopes([DRIVE_SCOPE]))


def sheets_service() -> Any:
    """Build a Sheets v4 service from the current ADC.

    Returns:
        The Sheets ``v4`` service object.
    """
    from ...adapters.outbound.google import SHEETS_SCOPE, build_sheets_service, get_credentials_for_scopes

    return build_sheets_service(get_credentials_for_scopes([SHEETS_SCOPE]))


def docs_service() -> Any:
    """Build a Docs v1 service from the current ADC.

    Returns:
        The Docs ``v1`` service object.
    """
    from ...adapters.outbound.google import DOCS_SCOPE, build_docs_service, get_credentials_for_scopes

    return build_docs_service(get_credentials_for_scopes([DOCS_SCOPE]))


def storage_client(project: str) -> Any:
    """Build a Cloud Storage client scoped to ``project``.

    Args:
        project: Google Cloud project ID for the Storage client.

    Returns:
        A Cloud Storage client.
    """
    from ...adapters.outbound.google import CLOUD_PLATFORM_SCOPE, build_storage_client, get_credentials_for_scopes

    return build_storage_client(get_credentials_for_scopes([CLOUD_PLATFORM_SCOPE]), project)


def cloudfunctions_client() -> Any:
    """Build a Cloud Functions v2 client from the current ADC.

    Returns:
        A Cloud Functions ``v2`` client.
    """
    from ...adapters.outbound.google import (
        CLOUD_PLATFORM_SCOPE,
        build_cloudfunctions_client,
        get_credentials_for_scopes,
    )

    return build_cloudfunctions_client(get_credentials_for_scopes([CLOUD_PLATFORM_SCOPE]))


def cloudrun_client() -> Any:
    """Build a Cloud Run v2 services client from the current ADC.

    Returns:
        A Cloud Run ``v2`` services client.
    """
    from ...adapters.outbound.google import CLOUD_PLATFORM_SCOPE, build_cloudrun_client, get_credentials_for_scopes

    return build_cloudrun_client(get_credentials_for_scopes([CLOUD_PLATFORM_SCOPE]))


def skip_if_drive_quota(exc: Exception) -> None:
    """Skip the calling test when ``exc`` looks like a Drive quota block.

    Service accounts on consumer (non-Workspace) Google accounts have
    zero Drive storage quota. Their API calls return
    ``storageQuotaExceeded`` for any operation that would create or own
    a Drive file. Live tests skip cleanly under that condition so the
    suite stays green for the autonomous SA path.

    Args:
        exc: Exception raised by the Drive client.

    Raises:
        Exception: Re-raises ``exc`` when it does not match a known
            quota / authorisation signature.
    """
    text = repr(exc).lower()
    if "storagequotaexceeded" in text or "storage quota" in text or "user's drive" in text or "invalid_grant" in text:
        pytest.skip(f"Drive unavailable for the active credentials: {exc.__class__.__name__}")
    raise exc


def cleanup_files(drive: Any, file_ids: Iterable[str]) -> None:
    """Best-effort permanent delete of a list of Drive file IDs.

    Cleanup never raises — a half-cleaned scratch folder is preferable
    to a test failure that masks the real assertion failure earlier in
    the test body.

    Args:
        drive: Drive service object built via :func:`drive_service`.
        file_ids: Iterable of Drive file IDs to delete.
    """
    for ident in file_ids:
        with contextlib.suppress(Exception):
            drive.files().delete(fileId=ident).execute()
