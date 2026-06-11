"""Real-behavior tests for SedeNavigationError translated_message threading.

Coverage (contract):
- contract-A: storage_state_for_session raises SedeNavigationError with
  translated_message populated when storage_state_path is None.
- contract-B: storage_state_for_session raises SedeNavigationError with
  translated_message populated when the persisted session cannot be loaded
  (path points to a non-existent file).
- contract-C: translated_message resolves to a non-placeholder string in the
  catalogue (i.e. the locale key exists and is bound to real copy).
- contract-D: fetch_notifications_summary raises SedeNavigationError with
  translated_message when storage_state_path is None.
- contract-E: fetch_iva_compensation_wallet raises SedeNavigationError with
  translated_message when storage_state_path is None.
- contract-F: walk_expedientes_tree raises SedeNavigationError with
  translated_message when storage_state_path is None.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ......core.i18n import tr
from ...auth._authenticator import AeatSession, CertificateSessionDetail, HandshakeResult
from ...auth._providers import AuthProviderKind
from .._auth_state import storage_state_for_session
from .._errors import SedeNavigationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime.now(UTC)
_DEADLINE = _NOW + timedelta(hours=8)


def _minimal_session(*, storage_state_path: Path | None, identity_nif: str = "12345678Z") -> AeatSession:
    """Build the smallest valid AeatSession for offline raises."""
    return AeatSession(
        provider_kind=AuthProviderKind.CERTIFICATE,
        authenticated_at=_NOW,
        idle_deadline=_DEADLINE,
        storage_state_path=storage_state_path,
        identity_nif=identity_nif,
        provider_detail=CertificateSessionDetail(
            certificate_thumbprint="aabbcc",
            certificate_subject="CN=test",
            handshake=HandshakeResult(
                success=True,
                status_code=200,
                server_cert_chain=(),
                elapsed_ms=10,
                attempted_at=_NOW,
                error_message=None,
            ),
        ),
    )


# ---------------------------------------------------------------------------
# contract-A: None path triggers translated_message in storage_state_for_session
# ---------------------------------------------------------------------------


def test_storage_state_for_session_no_path_carries_translated_message() -> None:
    session = _minimal_session(storage_state_path=None)
    with pytest.raises(SedeNavigationError) as exc_info:
        storage_state_for_session(session)
    assert exc_info.value.translated_message is not None
    assert len(exc_info.value.translated_message) > 0


# ---------------------------------------------------------------------------
# contract-B: load returns None triggers translated_message (with profile isolation)
# ---------------------------------------------------------------------------


def test_storage_state_for_session_unloaded_state_carries_translated_message(
    tmp_path: Path,
) -> None:
    """When session_store.load cannot find a matching record it returns None,
    which must raise SedeNavigationError with translated_message set.

    The test creates a synthetic path that passes the None-path guard but
    causes load() to return None under an isolated profile bucket."""
    from ......tests.secure_sql import isolated_runtime_profile

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="auth-state-test"):
        session = _minimal_session(storage_state_path=tmp_path / "nonexistent.json")
        with pytest.raises(SedeNavigationError) as exc_info:
            storage_state_for_session(session)
        assert exc_info.value.translated_message is not None
        assert len(exc_info.value.translated_message) > 0


# ---------------------------------------------------------------------------
# contract-C: locale key resolves to non-placeholder string
# ---------------------------------------------------------------------------


def test_no_auth_session_locale_key_resolves_to_real_copy() -> None:
    resolved = tr("adapters.sede.errors.no_auth_session")
    assert "adapters.sede.errors.no_auth_session" not in resolved
    assert len(resolved) > 10


# ---------------------------------------------------------------------------
# contract-D: fetch_notifications_summary carries translated_message on None path
# ---------------------------------------------------------------------------


def test_fetch_notifications_summary_carries_translated_message_on_none_path() -> None:
    from .._notifications import fetch_notifications_summary

    session = _minimal_session(storage_state_path=None)

    with pytest.raises(SedeNavigationError) as exc_info:
        asyncio.run(fetch_notifications_summary(session))

    assert exc_info.value.translated_message is not None
    assert "adapters.sede.errors.no_auth_session" not in exc_info.value.translated_message


# ---------------------------------------------------------------------------
# contract-E: fetch_iva_compensation_wallet carries translated_message on None path
# ---------------------------------------------------------------------------


def test_fetch_iva_compensation_wallet_carries_translated_message_on_none_path() -> None:
    from .._iva_compensation_wallet import fetch_iva_compensation_wallet

    session = _minimal_session(storage_state_path=None)

    with pytest.raises(SedeNavigationError) as exc_info:
        asyncio.run(
            fetch_iva_compensation_wallet(
                session,
                taxpayer_nif="12345678Z",
                target_year=2025,
                target_period="4T",
            ),
        )

    assert exc_info.value.translated_message is not None
    assert "adapters.sede.errors.no_auth_session" not in exc_info.value.translated_message


# ---------------------------------------------------------------------------
# contract-F: walk_expedientes_tree carries translated_message on None path
# ---------------------------------------------------------------------------


def test_walk_expedientes_tree_carries_translated_message_on_none_path() -> None:
    from .._walker import walk_expedientes_tree

    session = _minimal_session(storage_state_path=None)

    with pytest.raises(SedeNavigationError) as exc_info:
        asyncio.run(walk_expedientes_tree(session))

    assert exc_info.value.translated_message is not None
    assert "adapters.sede.errors.no_auth_session" not in exc_info.value.translated_message
