"""Real encrypted-session metadata parsing tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from ....adapters.outbound.aeat.auth import session_store
from ....core import AuthProviderKind
from ....core.external_constants import load_external_constants
from ....tests.secure_sql import isolated_runtime_profile
from ..sessions import load_persisted_session, storage_state_paths

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "30303030-3030-4303-8303-303030303030"
_AUTHENTICATED_AT = datetime(2026, 5, 26, 9, 30, 0, tzinfo=UTC)


def test_load_persisted_session_accepts_provider_specific_clave_metadata(tmp_path: Path) -> None:
    """Application session reuse must accept the real Cl@ve metadata envelope.

    Cl@ve Móvil persists adapter-owned fields such as schema_version,
    storage_state_sha256, landing_url, and verification_code. The
    application layer narrows that metadata to the common provider-neutral
    fields instead of rejecting a valid encrypted session as corrupt.
    """

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as runtime:
        settings = runtime.settings.model_copy(update={"cadrumo_auth_provider": AuthProviderKind.CLAVE_MOVIL})
        external = load_external_constants().aeat
        sede_domain = urlsplit(external.domains.sede).netloc
        landing_url = f"{external.domains.www6}{external.sede_paths.expedientes_resumen}"
        authenticated_at = _AUTHENTICATED_AT
        storage_state = {
            "cookies": [
                {
                    "name": "AEAT_SESSION",
                    "value": "encrypted-store-boundary",
                    "domain": f".{sede_domain}",
                    "path": "/",
                    "expires": 1893456000,
                    "httpOnly": True,
                    "secure": True,
                    "sameSite": "Lax",
                },
            ],
            "origins": [],
        }
        path = storage_state_paths(AuthProviderKind.CLAVE_MOVIL).storage_state
        session_store.save(
            path,
            storage_state=storage_state,
            metadata={
                "schema_version": 2,
                "provider_kind": "clave_movil",
                "identity_nif": "TEST-IDENTITY",
                "authenticated_at": authenticated_at.isoformat().replace("+00:00", "Z"),
                "idle_deadline": (authenticated_at + timedelta(minutes=18)).isoformat().replace("+00:00", "Z"),
                "storage_state_sha256": session_store.storage_state_sha256(storage_state),
                "used_non_qr_fallback": True,
                "verification_code": "SUB",
                "landing_url": landing_url,
            },
        )

        persisted = load_persisted_session(settings)

    assert persisted is not None
    assert persisted.provider_kind is AuthProviderKind.CLAVE_MOVIL
    assert persisted.identity_nif == "TEST-IDENTITY"
    assert persisted.authenticated_at == authenticated_at
    assert persisted.idle_deadline == authenticated_at + timedelta(minutes=18)
