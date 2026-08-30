"""Real encrypted-store validation for certificate-session resume."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import SecretStr

from ......application.auth_credentials import unnamed_certificate_credentials
from ......core.config import Settings
from ......core.errors.hierarchy import AeatLoginAssertionError
from ......tests.secure_sql import isolated_runtime_profile
from .. import session_store as session_store
from ..authenticator import AeatAuthenticator
from ..authenticator_persistence import PersistedSessionMetadata
from ..certificate import extract_nif_from_subject
from ._authenticator_support import SECRET_PASSPHRASE, _build_bundle

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case", "expected_reason"),
    [
        ("missing-storage", "storage_state_missing"),
        ("missing-cookies", "storage_state_cookies_missing"),
        ("missing-origins", "storage_state_origins_missing"),
        ("malformed-metadata", "metadata_malformed"),
        ("schema-mismatch", "metadata_malformed"),
        ("hash-mismatch", "storage_hash_mismatch"),
        ("expired-idle-deadline", "idle_deadline_expired"),
        ("thumbprint-mismatch", "certificate_thumbprint_mismatch"),
        ("subject-mismatch", "certificate_subject_mismatch"),
        ("nif-mismatch", "certificate_nif_mismatch"),
    ],
)
async def test_resume_rejects_invalid_encrypted_session_before_browser_resolution(
    tmp_path: Path,
    case: str,
    expected_reason: str,
) -> None:
    """Every local refusal runs before any browser session is required."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="1f6b0000-0000-4000-8000-00000000aaa0"):
        bundle_path = _build_bundle(tmp_path)
        settings = Settings(
            cadrumo_certificate_path=bundle_path,
            cadrumo_certificate_password_secret=SecretStr(SECRET_PASSPHRASE),
            cadrumo_token_dir=tmp_path / ".tokens",
        )
        authenticator = AeatAuthenticator(
            settings,
            credentials=unnamed_certificate_credentials(settings),
        )
        certificate = authenticator.load_certificate()
        storage_state: dict[str, object] = {"cookies": [], "origins": []}
        current = datetime.now(UTC)
        metadata = PersistedSessionMetadata(
            certificate_thumbprint=certificate.sha256_thumbprint,
            certificate_subject=certificate.subject,
            certificate_nif=extract_nif_from_subject(certificate),
            authenticated_at=current,
            idle_deadline=current + timedelta(hours=1),
            storage_state_sha256=session_store.storage_state_sha256(storage_state),
        ).model_dump(mode="json")
        storage_state_path = tmp_path / f"{case}-storage.json"

        if case == "missing-cookies":
            storage_state.pop("cookies")
        elif case == "missing-origins":
            storage_state.pop("origins")
        elif case == "malformed-metadata":
            metadata = {}
        elif case == "schema-mismatch":
            metadata["schema_version"] = 999
        elif case == "hash-mismatch":
            metadata["storage_state_sha256"] = "0" * 64
        elif case == "expired-idle-deadline":
            metadata["idle_deadline"] = (current - timedelta(seconds=1)).isoformat()
        elif case == "thumbprint-mismatch":
            metadata["certificate_thumbprint"] = "f" * 64
        elif case == "subject-mismatch":
            metadata["certificate_subject"] = "CN=DIFFERENT"
        elif case == "nif-mismatch":
            metadata["certificate_nif"] = "87654321X"

        if case != "missing-storage":
            session_store.save(
                storage_state_path,
                storage_state=storage_state,
                metadata=metadata,
            )

        with pytest.raises(AeatLoginAssertionError) as excinfo:
            await authenticator.resume_from_storage_state(storage_state_path)

        assert excinfo.value.context is not None
        assert excinfo.value.context["reason"] == expected_reason
        assert not session_store.exists(storage_state_path)
