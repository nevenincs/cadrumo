"""Strict roundtrip across the encrypted browser-session boundary.

The :mod:`cadrumo.adapters.outbound.aeat.auth._session_store` module
persists Playwright ``storage_state`` payloads encrypted at
``SensitivityClass.SESSION`` through :class:`SecureObjectRepository`.
This test asserts the save / load cycle preserves every key inside
``storage_state`` and ``metadata`` and that the SHA-256 fingerprint
on the loaded session matches the one computed at save time.

No mocks: the test enters the active profile-bucket runtime with a real
bucket session so regressions in runtime routing, column encryption,
envelope schema, or session-store JSON dumping surface as strict
equality failures.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from ......core.auth_session_keys import aeat_auth_session_storage_state_path
from ......core.config import AEAT_CERTIFICATE_PROTECTED_URL
from ......core.time import now
from ......tests.aeat_literal_fixtures import AEAT_HOST_SUFFIX_EXPECTED, aeat_url
from ......tests.secure_sql import isolated_runtime_profile
from .....persistence.storage import AEAT_BROWSER_SESSION_NAMESPACE
from .....persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from .. import _session_store

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]
_BUCKET_ID = "1f6b0000-0000-4000-8000-00000000f0f0"
_NON_JSON_CAPTURED_AT = datetime(2026, 5, 28, 13, 55, 0, tzinfo=UTC)


def _playwright_shaped_storage_state() -> dict[str, object]:
    """Build a Playwright-shape storage_state with cookies + origins.

    Mirrors the shape ``BrowserContext.storage_state()`` actually
    emits so the roundtrip exercises real heterogeneous content:
    nested lists of dicts with mixed value types (str, int, bool).
    """

    return {
        "cookies": [
            {
                "name": "PRESTACIONES_SESSION",
                "value": "abc123",
                "domain": f".{AEAT_HOST_SUFFIX_EXPECTED}",
                "path": "/",
                "expires": 1893456000,
                "httpOnly": True,
                "secure": True,
                "sameSite": "Lax",
            },
        ],
        "origins": [
            {
                "origin": aeat_url("sede", "/").rstrip("/"),
                "localStorage": [
                    {"name": "consent.banner", "value": "dismissed"},
                ],
            },
        ],
    }


def test_persisted_browser_session_roundtrips_under_real_encryption(
    tmp_path: Path,
) -> None:
    """A saved browser session loads back with every key + SHA preserved."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        logical_path = Path("/profile/active/aeat-session")
        storage_state = _playwright_shaped_storage_state()
        metadata = {
            "certificate_thumbprint": "AA:BB:CC:DD:EE:FF:00:11:22:33",
            "certificate_subject": "CN=AEAT Test User",
            "protected_resource_url": AEAT_CERTIFICATE_PROTECTED_URL,
            "renewal_count": 0,
        }
        sha_at_save = _session_store.storage_state_sha256(storage_state)

        _session_store.save(
            logical_path,
            storage_state=storage_state,
            metadata=metadata,
        )
        loaded = _session_store.load(logical_path)
        repo = secure_object_repository_for_active_bucket()
        raw_records = tuple(
            record
            for record in repo.iter_all_records_raw()
            if record.namespace == AEAT_BROWSER_SESSION_NAMESPACE.namespace
        )

        assert loaded is not None
        assert _session_store.exists(logical_path) is True
        # Strict equality on the typed envelope: schema_version,
        # storage_state, metadata, written_at must all survive.
        assert loaded.schema_version == AEAT_BROWSER_SESSION_NAMESPACE.schema_version
        assert loaded.storage_state == storage_state
        assert loaded.metadata == metadata
        assert len(raw_records) == 1
        raw_record = raw_records[0]
        assert raw_record.classification == AEAT_BROWSER_SESSION_NAMESPACE.sensitivity.value
        assert raw_record.schema_version == AEAT_BROWSER_SESSION_NAMESPACE.schema_version
        assert raw_record.object_key != logical_path.as_posix().encode("utf-8")
        assert len(raw_record.object_key) == 32
        # Cookie list preserves its inner shape: lists round-trip
        # through JSON as lists (not tuples), so the assertion
        # checks list identity rather than tuple.
        assert isinstance(loaded.storage_state["cookies"], list)
        cookies = loaded.storage_state["cookies"]
        assert isinstance(cookies, list)
        assert isinstance(cookies[0], Mapping)
        # Playwright storage_state cookies are documented string-keyed
        # dicts; the persisted payload exposes them only as ``object``.
        first_cookie = cast("Mapping[str, object]", cookies[0])
        assert first_cookie["name"] == "PRESTACIONES_SESSION"
        assert first_cookie["httpOnly"] is True
        assert first_cookie["expires"] == 1893456000
        # The SHA computed on the loaded payload must match the
        # SHA computed at save time. If column-encryption mangled
        # any byte, this assertion fails before any field check.
        assert loaded.storage_state_sha256 == sha_at_save


def test_storage_state_hash_rejects_non_json_values() -> None:
    storage_state = _playwright_shaped_storage_state()
    storage_state["captured_at"] = _NON_JSON_CAPTURED_AT

    with pytest.raises(ValidationError, match="invalid-json-value"):
        _session_store.storage_state_sha256(storage_state)


def test_session_store_rejects_non_json_metadata_before_write(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        logical_path = Path("/profile/active/aeat-session")

        with pytest.raises(ValidationError, match="invalid-json-value"):
            _session_store.save(
                logical_path,
                storage_state=_playwright_shaped_storage_state(),
                metadata={"captured_at": _NON_JSON_CAPTURED_AT},
            )

        assert _session_store.exists(logical_path) is False


def test_cadrumo_session_custody_refuses_former_product_state_without_mutation(tmp_path: Path) -> None:
    """A former logical session blocks new custody without being read or changed."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        current_path = aeat_auth_session_storage_state_path(_BUCKET_ID, "storage")
        former_path = Path(".aeat/auth/sessions") / current_path.name
        repo = secure_object_repository_for_active_bucket()
        opaque_payload = b"former-encrypted-session-envelope"
        repo.save(
            namespace=AEAT_BROWSER_SESSION_NAMESPACE.namespace,
            object_key=former_path.as_posix(),
            classification=AEAT_BROWSER_SESSION_NAMESPACE.sensitivity,
            schema_version=AEAT_BROWSER_SESSION_NAMESPACE.schema_version,
            written_at=now(),
            payload=opaque_payload,
        )

        with pytest.raises(
            _session_store.FormerProductAuthSessionStateError,
            match="will not read, move, re-key, delete, or adopt",
        ):
            _session_store.save(
                current_path,
                storage_state=_playwright_shaped_storage_state(),
                metadata={"provider_kind": "certificate"},
            )

        former_record = repo.load(
            AEAT_BROWSER_SESSION_NAMESPACE.namespace,
            former_path.as_posix(),
            expected_class=AEAT_BROWSER_SESSION_NAMESPACE.sensitivity,
            max_supported_version=AEAT_BROWSER_SESSION_NAMESPACE.schema_version,
        )
        assert former_record is not None
        assert former_record.payload == opaque_payload
        assert repo.exists(AEAT_BROWSER_SESSION_NAMESPACE.namespace, current_path.as_posix()) is False


def test_session_store_rejects_direct_former_product_paths_before_repository_access(tmp_path: Path) -> None:
    """Former logical keys cannot be explicitly read, written, or deleted."""
    former_path = Path(".aeat/auth/sessions/operator-storage.json")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        for operation in (
            lambda: _session_store.exists(former_path),
            lambda: _session_store.save(
                former_path,
                storage_state=_playwright_shaped_storage_state(),
                metadata={"provider_kind": "certificate"},
            ),
            lambda: _session_store.load(former_path),
            lambda: _session_store.delete(former_path),
        ):
            with pytest.raises(_session_store.FormerProductAuthSessionStateError):
                operation()
