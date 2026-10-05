"""Live-gated proof that Cadrumo works under the three non-sensitive scopes alone.

Deselected unless ``CADRUMO_LIVE_TESTS_ENABLED=1`` and
``CADRUMO_LIVE_TESTS_GOOGLE=1`` are set and an AEAT profile is active. The
tests run against the operator's own Google account with the client the
application ships:

1. Sign-in runs the real loopback consent flow in the OS-default browser,
   requires that Google granted exactly ``openid``, ``userinfo.email`` and
   ``drive.file``, creates the profile's Drive folder and stores the sign-in.
2. Export, preview and readback then exercise every Sheets and Drive method
   the calculation export uses, against a workbook this application created,
   with nothing wider than ``drive.file`` granted.
3. Sign-out clears the stored sign-in and leaves the Drive folder recorded.

Nothing is submitted to AEAT. The tests create one folder and one workbook in
the signed-in account's My Drive and leave them there for inspection.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import date

import pytest

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import open_test_profile_session

from .....application.storage.calc_sheets.engine import build_export_plan
from .....core.bucket_pointer import resolve_active_bucket_id
from .....core.resources.bundled_data import packaged_data
from .....domain.calculations.registry.tests.published_authority import published_snapshot
from .....tests.live_gate import requires_live_enabled, requires_live_google_enabled
from ...storage.factory import (
    build_google_credentials,
    google_credentials_for,
    require_application_drive_root,
    resolve_required_drive_root_folder_id,
)
from ..calc_sheets_apply import apply_export_plan, preview_export_plan
from ..calc_sheets_pull import pull_operator_edits
from ..errors import GoogleAuthClientMetadataUnavailableError
from ..installation_client import INSTALLATION_CLIENT_DATA_PARTS, load_installation_client
from ..oauth_flow import run_login_flow
from ..records import REQUIRED_SCOPES, DriveConfig, OAuthClient
from ..root_folder import ensure_profile_root_folder
from ..session_store import (
    delete_session,
    load_drive_config,
    load_metadata,
    load_token,
    save_drive_config,
    save_metadata,
    save_token,
)

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_outbound_adapter]


def _require_live_and_shipped_client(monkeypatch: pytest.MonkeyPatch) -> OAuthClient:
    """Read the client the application ships, which every other test is kept away from."""
    requires_live_enabled()
    requires_live_google_enabled()
    monkeypatch.setattr(
        "cadrumo.adapters.outbound.google.installation_client.installation_client_source",
        lambda: packaged_data(*INSTALLATION_CLIENT_DATA_PARTS),
    )
    try:
        return load_installation_client()
    except GoogleAuthClientMetadataUnavailableError:
        pytest.fail("this checkout holds no usable Google OAuth client file at its installation location")


@contextmanager
def _active_profile() -> Generator[str]:
    """Open the active profile's storage session and yield its ID."""
    active = resolve_active_bucket_id()
    if active is None:
        pytest.fail("live Google tests require an active AEAT profile pointer")
    with open_test_profile_session(active):
        yield active


def test_sign_in_grants_exactly_the_three_scopes_and_creates_the_profile_folder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real consent, then the folder, then the stored sign-in, in the order the product uses.

    The first run opens Google's consent page and waits for the operator.
    """
    client = _require_live_and_shipped_client(monkeypatch)
    with _active_profile() as profile:
        token, metadata = run_login_flow(client, profile)

        assert sorted(metadata.granted_scopes) == sorted(REQUIRED_SCOPES), (
            "Google granted a different scope set than the three the application requests"
        )
        assert token.client_id == client.client_id

        root_folder_id = ensure_profile_root_folder(google_credentials_for(client, token), profile=profile)
        save_token(profile, token)
        save_metadata(profile, metadata)
        save_drive_config(profile, DriveConfig(root_folder_id=root_folder_id))

        # Signing in again finds the same folder instead of creating a second one.
        assert ensure_profile_root_folder(build_google_credentials(profile=profile), profile=profile) == root_folder_id


def test_export_preview_and_readback_succeed_under_drive_file_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every Sheets and Drive call of the calculation export, against an application-created workbook."""
    _require_live_and_shipped_client(monkeypatch)
    with _active_profile() as profile:
        metadata = load_metadata(profile)
        if metadata is None:
            pytest.fail("no stored sign-in; run the sign-in test first, or `aeat config google login`")
        # Nothing wider than the three scopes was granted, so every call below
        # succeeds on `drive.file` alone or not at all.
        assert sorted(metadata.granted_scopes) == sorted(REQUIRED_SCOPES)

        credentials = build_google_credentials(profile=profile)
        root_folder_id = resolve_required_drive_root_folder_id(profile=profile)
        require_application_drive_root(credentials, root_folder_id=root_folder_id)

        snapshot = published_snapshot("130", filing_year=2025, period="1T", on=date(2025, 4, 1))
        plan = build_export_plan(snapshot)

        created = apply_export_plan(plan, credentials=credentials, root_folder_id=root_folder_id)
        rewritten = apply_export_plan(plan, credentials=credentials, root_folder_id=root_folder_id)
        assert rewritten.spreadsheet_id == created.spreadsheet_id, "a second export created a second workbook"

        preview = preview_export_plan(plan, credentials=credentials, root_folder_id=root_folder_id)
        assert preview.spreadsheet_exists and preview.spreadsheet_id == created.spreadsheet_id

        pulled = pull_operator_edits(snapshot, spreadsheet_id=created.spreadsheet_id, credentials=credentials)
        assert pulled.spreadsheet_id == created.spreadsheet_id
        assert pulled.cells_read > 0


def test_sign_out_clears_the_stored_sign_in_and_keeps_the_folder(monkeypatch: pytest.MonkeyPatch) -> None:
    _require_live_and_shipped_client(monkeypatch)
    with _active_profile() as profile:
        folder_before = load_drive_config(profile)

        delete_session(profile)

        assert load_token(profile) is None, "refresh token must be cleared by sign-out"
        assert load_metadata(profile) is None, "sign-in record must be cleared by sign-out"
        assert load_drive_config(profile) == folder_before
