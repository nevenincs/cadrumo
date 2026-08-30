"""Registry-definition binding proof for the Google session secure-object writes.

Each Google OAuth/session record family (client, token, metadata, drive config,
credential-source selection) persists an encrypted secure object whose
``classification`` and envelope ``schema_version`` MUST be single-sourced from
the owning
:class:`~adapters.persistence.storage.SecureObjectNamespaceDefinition`
(``GOOGLE_OAUTH_CLIENT_NAMESPACE`` and siblings) rather than restated as
``SensitivityClass`` literals in the session store.

This is a write-path proof: it drives each production save function and reads
the raw :class:`SecureObjectRow` back from the encrypted SQL backend, asserting
the persisted classification and schema_version equal what the registry def
declares. The two SECRET namespaces (client, token) and the three FINANCIAL
namespaces (metadata, drive config, credential source) are each checked against
their own def, so a cross-namespace metadata swap would fail here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from .....core import GoogleCredentialSourceKind
from .....tests.secure_sql import isolated_runtime_profile
from ....persistence.storage import (
    GOOGLE_CREDENTIAL_SOURCE_NAMESPACE,
    GOOGLE_DRIVE_CONFIG_NAMESPACE,
    GOOGLE_OAUTH_CLIENT_NAMESPACE,
    GOOGLE_OAUTH_METADATA_NAMESPACE,
    GOOGLE_OAUTH_TOKEN_NAMESPACE,
    SecureObjectNamespaceDefinition,
)
from ....persistence.storage.sql import SecureObjectRow
from ....persistence.storage.sql.session import session_scope
from .. import session_store
from ..impersonation import GoogleCredentialSourceSelection
from ..records import REQUIRED_SCOPES, DriveConfig, OAuthClient, OAuthMetadata, OAuthToken

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_BUCKET_ID = "c638b552-05ee-427e-82e4-21e5f4936157"  # was 'google-session-namespace-binding'
_PROFILE = "operator-google"
_ISSUED_AT = datetime(2026, 5, 26, 9, 0, 0, tzinfo=UTC)


def test_session_store_rows_carry_registry_declared_metadata(tmp_path: Path) -> None:
    """Every Google session save persists the metadata its registry def declares."""

    client = OAuthClient(
        client_id="desktop-client.apps.googleusercontent.com",
        client_secret="gcp-client-secret",
        project_id="cadrumo-vault",
        auth_uri="https://accounts.google.com/o/oauth2/auth",
        token_uri="https://oauth2.googleapis.com/token",
        auth_provider_x509_cert_url="https://www.googleapis.com/oauth2/v1/certs",
        redirect_uris=("http://127.0.0.1:8765/callback",),
    )
    token = OAuthToken(
        refresh_token="1//refresh-token",
        token_uri="https://oauth2.googleapis.com/token",
    )
    metadata = OAuthMetadata(
        account_email="operator@example.com",
        granted_scopes=REQUIRED_SCOPES,
        issued_at=_ISSUED_AT,
        last_refresh_at=_ISSUED_AT,
    )
    drive_config = DriveConfig(root_folder_id="drive-folder-id")
    selection = GoogleCredentialSourceSelection(kind=GoogleCredentialSourceKind.OAUTH_DESKTOP)

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        session_store.save_client(_PROFILE, client)
        session_store.save_token(_PROFILE, token)
        session_store.save_metadata(_PROFILE, metadata)
        session_store.save_drive_config(_PROFILE, drive_config)
        session_store.save_credential_source_selection(_PROFILE, selection)

        with session_scope(profile.repository._engine) as session:
            rows = {row.namespace: row for row in session.execute(select(SecureObjectRow)).scalars().all()}

    expected: dict[str, SecureObjectNamespaceDefinition] = {
        GOOGLE_OAUTH_CLIENT_NAMESPACE.namespace: GOOGLE_OAUTH_CLIENT_NAMESPACE,
        GOOGLE_OAUTH_TOKEN_NAMESPACE.namespace: GOOGLE_OAUTH_TOKEN_NAMESPACE,
        GOOGLE_OAUTH_METADATA_NAMESPACE.namespace: GOOGLE_OAUTH_METADATA_NAMESPACE,
        GOOGLE_DRIVE_CONFIG_NAMESPACE.namespace: GOOGLE_DRIVE_CONFIG_NAMESPACE,
        GOOGLE_CREDENTIAL_SOURCE_NAMESPACE.namespace: GOOGLE_CREDENTIAL_SOURCE_NAMESPACE,
    }
    for namespace, definition in expected.items():
        assert namespace in rows, f"expected a persisted row under {namespace!r}"
        row = rows[namespace]
        assert row.classification == definition.sensitivity.value, (
            f"persisted classification {row.classification!r} for {namespace!r} diverges from "
            f"registry def {definition.sensitivity.value!r}"
        )
        assert row.schema_version == definition.schema_version, (
            f"persisted schema_version {row.schema_version} for {namespace!r} diverges from "
            f"registry def {definition.schema_version}"
        )
