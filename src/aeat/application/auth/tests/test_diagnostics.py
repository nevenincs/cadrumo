"""Regression coverage for operator-safe auth diagnostic listing."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.storage import SensitivityClass
from ....core.errors import ERROR_REGISTRY, build_error_envelope
from ....core.external_constants import CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE, UTF_8_ENCODING, load_external_constants
from ....tests.aeat_literal_fixtures import aeat_url, configured_path
from ....tests.secure_sql import isolated_runtime_profile
from .._diagnostics import (
    _DiagnosticPayload,
    list_auth_diagnostics,
    load_auth_diagnostic,
    record_auth_diagnostic_phone_state,
)
from .._errors import AuthDiagnosticPhoneStateError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_auth_diagnostics_list_and_show_redact_page_bodies(
    tmp_path: Path,
) -> None:
    external = load_external_constants().aeat
    selector_url = external.clave_movil.selector_access_url_template.format(
        target=f"{external.domains.sede}{external.sede_paths.expedientes_resumen}",
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
                },
            ).encode(UTF_8_ENCODING),
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
                },
            ).encode(UTF_8_ENCODING),
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
            f"{external.domains.www12.removeprefix('https://')}{external.clave_movil.autentica_dni_nie_contraste_path}",
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
        assert detail.operator_report_commands == (
            "aeat config auth diagnostics report diag-new --phone-state app_prompted_and_accepted",
            "aeat config auth diagnostics report diag-new --phone-state app_prompted_not_accepted",
            "aeat config auth diagnostics report diag-new --phone-state app_did_not_prompt",
            "aeat config auth diagnostics report diag-new --phone-state operator_did_not_check",
        )
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
        with pytest.raises(AuthDiagnosticPhoneStateError) as exc_info:
            record_auth_diagnostic_phone_state("diag-new", "guessed")
        assert exc_info.value.context == {"phone_state": "guessed"}


def test_auth_diagnostic_phone_state_error_is_in_error_registry() -> None:
    assert "REFUSED_AUTH_DIAGNOSTIC_PHONE_STATE" in ERROR_REGISTRY


def test_auth_diagnostic_phone_state_error_round_trips_through_build_error_envelope() -> None:
    err = AuthDiagnosticPhoneStateError("not_a_valid_state", context={"phone_state": "not_a_valid_state"})
    envelope = build_error_envelope(err)
    assert envelope.code == "REFUSED_AUTH_DIAGNOSTIC_PHONE_STATE"
    assert envelope.category == "REFUSED"
    assert envelope.message


def test_diagnostic_payload_round_trips_through_json() -> None:
    """_DiagnosticPayload validates from JSON and serialises back to an equivalent dict."""
    raw = {
        "diagnostic_id": "diag-rt-001",
        "reason": "push-wait-state-not-reached",
        "url": aeat_url("www2", configured_path("sede_paths", "clave_movil_login")),
        "captured_at": "2026-05-28T10:00:00+00:00",
        "html": "<html><body>page</body></html>",
        "screenshot_png_base64": "aW1hZ2U=",
        "auth_attempt": {
            "auth_mode": "non_qr",
            "headless": True,
            "timeout_ms": 120000,
        },
        "operator_report": {
            "phone_state": "app_did_not_prompt",
            "reported_at": "2026-05-28T11:00:00+00:00",
        },
        "phone_state": "",
        # Extra field unknown to the current schema — must survive round-trip
        "future_extension": "value",
    }

    payload_a = _DiagnosticPayload.model_validate(raw)
    serialised = payload_a.model_dump(mode="json")
    payload_b = _DiagnosticPayload.model_validate(serialised)

    assert payload_a == payload_b
    assert payload_a.diagnostic_id == "diag-rt-001"
    assert payload_a.reason == "push-wait-state-not-reached"
    assert payload_a.html == "<html><body>page</body></html>"
    assert payload_a.auth_attempt["auth_mode"] == "non_qr"
    assert payload_a.operator_report["phone_state"] == "app_did_not_prompt"

    # Anti-tautology: mutate the serialised blob and confirm inequality is detected
    serialised["diagnostic_id"] = "diag-rt-MUTATED"
    payload_mutated = _DiagnosticPayload.model_validate(serialised)
    assert payload_mutated != payload_a


def test_diagnostic_payload_rejects_non_object_json() -> None:
    """_payload() raises ValueError when the JSON root is not an object."""
    import json as _json

    from .._diagnostics import _payload

    with pytest.raises(ValueError, match="not a JSON object"):
        _payload(_json.dumps([1, 2, 3]).encode(UTF_8_ENCODING))
