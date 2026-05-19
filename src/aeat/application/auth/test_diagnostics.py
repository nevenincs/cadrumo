"""Regression coverage for operator-safe auth diagnostic listing."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ...adapters.outbound.aeat.auth._clave_movil import _DIAGNOSTIC_NAMESPACE
from ...adapters.persistence.storage import EphemeralMasterKeyProvider, SensitivityClass
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...adapters.persistence.storage.sql._orm import Base
from ...adapters.persistence.storage.sql.engine import create_engine_from_settings
from ...core.config import Settings
from ._diagnostics import list_auth_diagnostics, load_auth_diagnostic

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_auth_diagnostics_list_and_show_redact_page_bodies(
    tmp_path: Path,
    monkeypatch,
) -> None:
    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "auth-diagnostics.db"
        monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        try:
            repo = SecureObjectRepository(engine=engine)
            older = datetime(2026, 5, 19, 8, 0, tzinfo=UTC)
            newer = datetime(2026, 5, 19, 9, 0, tzinfo=UTC)
            repo.save(
                namespace=_DIAGNOSTIC_NAMESPACE,
                object_key="diag-old",
                classification=SensitivityClass.SESSION,
                schema_version=1,
                written_at=older,
                payload=json.dumps(
                    {
                        "diagnostic_id": "diag-old",
                        "reason": "post-auth-landing-timeout",
                        "url": "https://sede.agenciatributaria.gob.es/static_files/common/html/selector_acceso/SelectorAccesos.html",
                        "captured_at": older.isoformat(),
                        "html": "<html><body>older captured page</body></html>",
                        "screenshot_png_base64": "aW1hZ2U=",
                    }
                ).encode("utf-8"),
            )
            repo.save(
                namespace=_DIAGNOSTIC_NAMESPACE,
                object_key="diag-new",
                classification=SensitivityClass.SESSION,
                schema_version=1,
                written_at=newer,
                payload=json.dumps(
                    {
                        "diagnostic_id": "diag-new",
                        "reason": "push-wait-state-not-reached",
                        "url": "https://www12.agenciatributaria.gob.es/wlpl/MOVI-P24H/AutenticaDniNieContrasteh",
                        "captured_at": newer.isoformat(),
                        "html": "<html><body>newer captured page with sensitive form fields</body></html>",
                    }
                ).encode("utf-8"),
            )

            listed = list_auth_diagnostics()
            detail = load_auth_diagnostic("diag-new")

            assert listed.row_count == 2
            assert [row.diagnostic_id for row in listed.rows] == ["diag-new", "diag-old"]
            assert listed.rows[0].html_captured is True
            assert listed.rows[0].screenshot_captured is False
            assert listed.rows[1].screenshot_captured is True
            assert detail is not None
            assert detail.diagnostic_id == "diag-new"
            assert detail.html_excerpt == "[redacted html captured: 72 chars]"
            assert "sensitive form fields" not in detail.html_excerpt
        finally:
            engine.dispose()
