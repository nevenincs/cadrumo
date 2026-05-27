"""Regression coverage for operator-safe auth diagnostic listing."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ...adapters.outbound.aeat.auth import CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE
from ...adapters.persistence.storage import SensitivityClass
from ...core.external_constants import load_external_constants
from ...tests.secure_sql import isolated_runtime_profile
from ._diagnostics import list_auth_diagnostics, load_auth_diagnostic, record_auth_diagnostic_phone_state

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_auth_diagnostics_list_and_show_redact_page_bodies(
    tmp_path: Path,
) -> None:
    external = load_external_constants().aeat
    selector_url = external.clave_movil.selector_access_url_template.format(
        target=f"{external.domains.sede}{external.sede_paths.expedientes_resumen}"
    )
    contrast_url = (
        f"{external.domains.www12}{external.clave_movil.autentica_dni_nie_contraste_path}"
        "?qAA=2&ref=%2Fprivate-target&storksp=secret&from=aeat&ts=20260521081409392278"
    )
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repo = profile.repository
        older = datetime(2026, 5, 19, 8, 0, tzinfo=UTC)
        newer = datetime(2026, 5, 19, 9, 0, tzinfo=UTC)
        repo.save(
            namespace=CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE,
            object_key="diag-old",
            classification=SensitivityClass.SESSION,
            schema_version=1,
            written_at=older,
            payload=json.dumps(
                {
                    "diagnostic_id": "diag-old",
                    "reason": "post-auth-landing-timeout",
                    "url": selector_url,
                    "captured_at": older.isoformat(),
                    "html": "<html><body>older captured page</body></html>",
                    "screenshot_png_base64": "aW1hZ2U=",
                }
            ).encode("utf-8"),
        )
        repo.save(
            namespace=CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE,
            object_key="diag-new",
            classification=SensitivityClass.SESSION,
            schema_version=1,
            written_at=newer,
            payload=json.dumps(
                {
                    "diagnostic_id": "diag-new",
                    "reason": "push-wait-state-not-reached",
                    "url": contrast_url,
                    "captured_at": newer.isoformat(),
                    "auth_attempt": {
                        "auth_mode": "non_qr",
                        "auth_route": "clave_movil_non_qr_request",
                        "identity_kind": "NIE",
                        "headless": True,
                        "prefer_non_qr": True,
                        "timeout_ms": 120000,
                        "active_profile_ref": "sha256:profile123",
                        "active_profile_label_present": True,
                        "active_profile_registered": True,
                        "profile_record_present": True,
                        "profile_tax_id_present": True,
                        "profile_tax_id_fingerprint": "sha256:profiletax",
                        "clave_identity_configured": True,
                        "clave_identity_fingerprint": "sha256:clavetax",
                        "identity_alignment": "mismatch",
                        "dni_fecha_configured": False,
                        "dni_fecha_fingerprint": "",
                        "nie_soporte_configured": True,
                        "nie_soporte_fingerprint": "sha256:support",
                        "certificate_path_configured": True,
                        "certificate_password_configured": False,
                        "certificate_file_present": False,
                        "certificate_backend": "playwright_context",
                        "certificate_path_fingerprint": "sha256:certpath",
                    },
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
        assert listed.rows[0].auth_mode == "non_qr"
        assert listed.rows[0].auth_route == "clave_movil_non_qr_request"
        assert listed.rows[0].identity_kind == "NIE"
        assert listed.rows[0].headless is True
        assert listed.rows[0].prefer_non_qr is True
        assert listed.rows[0].timeout_ms == 120000
        assert listed.rows[0].route_label == "clave_movil_contrast"
        assert listed.rows[0].active_profile_id == ""
        assert listed.rows[0].active_profile_ref == "sha256:profile123"
        assert listed.rows[0].active_profile_label == ""
        assert listed.rows[0].active_profile_label_present is True
        assert listed.rows[0].profile_tax_id_present is True
        assert listed.rows[0].clave_identity_configured is True
        assert listed.rows[0].identity_alignment == "mismatch"
        assert listed.rows[0].nie_soporte_configured is True
        assert listed.rows[0].certificate_path_configured is True
        assert listed.rows[0].certificate_backend == "playwright_context"
        assert listed.rows[0].url.startswith(
            f"{external.domains.www12.removeprefix('https://')}"
            f"{external.clave_movil.autentica_dni_nie_contraste_path}"
        )
        assert listed.rows[0].url.endswith("?keys=qAA,ref,storksp,from,ts")
        assert "%2Fprivate-target" not in listed.rows[0].url
        assert "secret" not in listed.rows[0].url
        assert listed.rows[1].screenshot_captured is True
        assert listed.rows[1].route_label == "selector_access"
        assert detail is not None
        assert detail.diagnostic_id == "diag-new"
        assert detail.url == listed.rows[0].url
        assert detail.auth_mode == "non_qr"
        assert detail.auth_route == "clave_movil_non_qr_request"
        assert detail.identity_kind == "NIE"
        assert detail.profile_tax_id_fingerprint == "sha256:profiletax"
        assert detail.clave_identity_fingerprint == "sha256:clavetax"
        assert detail.nie_soporte_fingerprint == "sha256:support"
        assert detail.certificate_path_fingerprint == "sha256:certpath"
        assert detail.html_excerpt == "[redacted html captured: 72 chars]"
        assert "sensitive form fields" not in detail.html_excerpt
        report = record_auth_diagnostic_phone_state("diag-new", "app_did_not_prompt")
        reported_detail = load_auth_diagnostic("diag-new")
        relisted = list_auth_diagnostics()
        assert report is not None
        assert report.phone_state == "app_did_not_prompt"
        assert reported_detail is not None
        assert reported_detail.phone_state == "app_did_not_prompt"
        assert reported_detail.phone_state_reported_at == report.reported_at
        assert relisted.rows[0].phone_state == "app_did_not_prompt"
        assert relisted.rows[0].phone_state_reported_at == report.reported_at
        assert record_auth_diagnostic_phone_state("missing", "app_did_not_prompt") is None
        with pytest.raises(ValueError):
            record_auth_diagnostic_phone_state("diag-new", "guessed")
