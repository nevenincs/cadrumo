"""Regression coverage for operator-safe auth diagnostic listing."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from cadrumo.adapters.outbound.aeat.auth.clave_movil_support import mint_diagnostic_id
from cadrumo.adapters.persistence.profile.auth_diagnostics import build_auth_diagnostic_persistence
from cadrumo.adapters.persistence.storage.secure_object_namespaces import CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.auth.diagnostics import (
    AuthDiagnosticPhoneState,
    list_auth_diagnostics,
    load_auth_diagnostic,
    record_auth_diagnostic_phone_state,
)
from cadrumo.application.auth.errors import AuthDiagnosticPayloadError, AuthDiagnosticPhoneStateError
from cadrumo.core.classification.policies import SensitivityClass
from cadrumo.core.external_constants import UTF_8_ENCODING, load_external_constants
from cadrumo.core.operator_action_enums import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from cadrumo.tests.aeat_literal_fixtures import aeat_url

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]


def _list_auth_diagnostics():
    """Call the application projection through the composed persistence adapter."""
    return list_auth_diagnostics(persistence=build_auth_diagnostic_persistence())


def _load_auth_diagnostic(diagnostic_id: str):
    """Load one application diagnostic through the composed persistence adapter."""
    return load_auth_diagnostic(diagnostic_id, persistence=build_auth_diagnostic_persistence())


def _record_auth_diagnostic_phone_state(diagnostic_id: str, phone_state: str):
    """Update one application diagnostic through the composed persistence adapter."""
    return record_auth_diagnostic_phone_state(
        diagnostic_id,
        phone_state,
        persistence=build_auth_diagnostic_persistence(),
    )


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
            namespace=CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE.namespace,
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
            namespace=CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE.namespace,
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
                        "certificate_path_fingerprint": "sha256:certpath",
                    },
                    "html": "<html><body>newer captured page with sensitive form fields</body></html>",
                },
            ).encode(UTF_8_ENCODING),
        )

        listed = _list_auth_diagnostics()
        detail = _load_auth_diagnostic("diag-new")

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
        assert "certificate_backend" not in listed.rows[0].model_dump()
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
        assert "certificate_backend" not in detail.model_dump()
        verdict = detail.operator_report_verdict
        assert verdict is not None
        assert verdict.failed_condition_id == "auth.diagnostics.phone_state_recorded"
        assert verdict.action is None
        assert verdict.argument_bindings == ()
        assert verdict.conditionality is ActionConditionality.NOT_APPLICABLE
        assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
        assert len(verdict.evidence) == 1
        evidence = verdict.evidence[0]
        assert evidence.condition_id == "auth.diagnostics.phone_state_recorded"
        assert evidence.evidence_id == "auth.diagnostics.phone_state_recorded.observation"
        assert evidence.provenance is ActionEvidenceProvenance.APPLICATION_STATE
        assert evidence.values == {"diagnostic_available": True, "phone_state_observed": False}
        assert detail.html_excerpt == "[redacted html captured: 72 chars]"
        assert "sensitive form fields" not in detail.html_excerpt
        report = _record_auth_diagnostic_phone_state("diag-new", "app_did_not_prompt")
        reported_detail = _load_auth_diagnostic("diag-new")
        relisted = _list_auth_diagnostics()
        assert report is not None
        assert report.phone_state == "app_did_not_prompt"
        assert reported_detail is not None
        assert reported_detail.phone_state == "app_did_not_prompt"
        assert reported_detail.operator_report_verdict is None
        assert reported_detail.phone_state_reported_at == report.reported_at
        assert relisted.rows[0].phone_state == "app_did_not_prompt"
        assert relisted.rows[0].phone_state_reported_at == report.reported_at
        assert _record_auth_diagnostic_phone_state("missing", "app_did_not_prompt") is None
        with pytest.raises(AuthDiagnosticPhoneStateError) as exc_info:
            _record_auth_diagnostic_phone_state("diag-new", "guessed")
        assert exc_info.value.context == {"phone_state": "guessed"}


def test_rapid_encrypted_diagnostic_captures_list_and_load_individually(tmp_path: Path) -> None:
    """Same-moment captures remain independently addressable after encrypted persistence."""

    captured_at = datetime(2026, 8, 2, 9, 0, tzinfo=UTC)
    diagnostic_ids = tuple(mint_diagnostic_id(captured_at) for _ in range(8))
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        for sequence, diagnostic_id in enumerate(diagnostic_ids):
            _store_diagnostic(
                profile.repository,
                key=diagnostic_id,
                payload=_diagnostic_payload(
                    diagnostic_id=diagnostic_id,
                    reason=f"rapid-capture-{sequence}",
                    captured_at=captured_at.isoformat(),
                    html=f"<main>local diagnostic capture {sequence}</main>",
                ),
            )
        listed = _list_auth_diagnostics()
        details = tuple(_load_auth_diagnostic(diagnostic_id) for diagnostic_id in diagnostic_ids)

    assert len(set(diagnostic_ids)) == len(diagnostic_ids)
    assert listed.row_count == len(diagnostic_ids)
    assert {row.diagnostic_id for row in listed.rows} == set(diagnostic_ids)
    assert all(detail is not None for detail in details)
    assert {detail.diagnostic_id for detail in details if detail is not None} == set(diagnostic_ids)


def _store_diagnostic(repo: SecureObjectRepository, *, key: str, payload: dict[str, object]) -> None:
    """Persist one genuine encrypted diagnostic row through the real repository."""
    repo.save(
        namespace=CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE.namespace,
        object_key=key,
        classification=SensitivityClass.SESSION,
        schema_version=1,
        written_at=datetime(2026, 5, 19, 8, 0, tzinfo=UTC),
        payload=json.dumps(payload).encode(UTF_8_ENCODING),
    )


def _diagnostic_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "diagnostic_id": "diag",
        "reason": "post-auth-landing-timeout",
        "url": aeat_url("sede", "/"),
        "captured_at": datetime(2026, 5, 19, 8, 0, tzinfo=UTC).isoformat(),
    }
    payload.update(overrides)
    return payload


class TestPersistedInstantContract:
    """A persisted diagnostic instant is held to the canonical UTC contract.

    ``captured_at`` and the operator report's ``reported_at`` were parsed with a
    bare ``datetime.fromisoformat``, so a row written without an offset, or with
    a local one, came back naive or non-UTC while ``validate_utc_aware`` — the
    contract every other persisted instant carries — rejects both. The listing
    sorts by capture time, which is not a comparison a mixed naive/aware set
    supports.
    """

    def test_naive_captured_at_is_refused(self, tmp_path: Path) -> None:
        with isolated_runtime_profile(tmp_path=tmp_path) as profile:
            _store_diagnostic(
                profile.repository,
                key="diag",
                payload=_diagnostic_payload(captured_at="2026-05-19T08:00:00"),
            )

            with pytest.raises(AuthDiagnosticPayloadError):
                _list_auth_diagnostics()

    def test_non_utc_captured_at_is_refused(self, tmp_path: Path) -> None:
        with isolated_runtime_profile(tmp_path=tmp_path) as profile:
            _store_diagnostic(
                profile.repository,
                key="diag",
                payload=_diagnostic_payload(captured_at="2026-05-19T08:00:00+02:00"),
            )

            with pytest.raises(AuthDiagnosticPayloadError):
                _list_auth_diagnostics()

    def test_non_utc_reported_at_is_refused(self, tmp_path: Path) -> None:
        with isolated_runtime_profile(tmp_path=tmp_path) as profile:
            _store_diagnostic(
                profile.repository,
                key="diag",
                payload=_diagnostic_payload(
                    operator_report={
                        "phone_state": "app_did_not_prompt",
                        "reported_at": "2026-05-19T09:00:00+02:00",
                    },
                ),
            )

            with pytest.raises(AuthDiagnosticPayloadError):
                _list_auth_diagnostics()

    def test_utc_instants_round_trip(self, tmp_path: Path) -> None:
        """Anti-tautology: the refusals discriminate rather than always-refusing."""
        with isolated_runtime_profile(tmp_path=tmp_path) as profile:
            _store_diagnostic(
                profile.repository,
                key="diag",
                payload=_diagnostic_payload(
                    operator_report={
                        "phone_state": "app_did_not_prompt",
                        "reported_at": "2026-05-19T09:00:00+00:00",
                    },
                ),
            )

            report = _list_auth_diagnostics()

            assert report.row_count == 1
            row = report.rows[0]
            assert row.captured_at == datetime(2026, 5, 19, 8, 0, tzinfo=UTC)
            assert row.phone_state_reported_at == datetime(2026, 5, 19, 9, 0, tzinfo=UTC)


class TestPersistedPhoneStateTaxonomy:
    """A persisted phone state is held to the same closed vocabulary as the mutation.

    The taxonomy was enforced only by ``record_auth_diagnostic_phone_state``:
    the read path pushed whatever the row held through ``str()``, so a payload
    carrying an unrecognised state was listed verbatim while the mutation API
    refused the identical value for the same diagnostic.
    """

    def test_unknown_persisted_state_is_refused(self, tmp_path: Path) -> None:
        with isolated_runtime_profile(tmp_path=tmp_path) as profile:
            _store_diagnostic(
                profile.repository,
                key="diag",
                payload=_diagnostic_payload(operator_report={"phone_state": "guessed"}),
            )

            with pytest.raises(AuthDiagnosticPayloadError):
                _list_auth_diagnostics()

            with pytest.raises(AuthDiagnosticPhoneStateError):
                _record_auth_diagnostic_phone_state("diag", "guessed")

    def test_unknown_top_level_state_is_refused(self, tmp_path: Path) -> None:
        """The legacy top-level field carries the same vocabulary as the report."""
        with isolated_runtime_profile(tmp_path=tmp_path) as profile:
            _store_diagnostic(
                profile.repository,
                key="diag",
                payload=_diagnostic_payload(phone_state="guessed"),
            )

            with pytest.raises(AuthDiagnosticPayloadError):
                _list_auth_diagnostics()

    def test_absent_state_is_not_a_violation(self, tmp_path: Path) -> None:
        """A diagnostic captured before any operator report simply has no state."""
        with isolated_runtime_profile(tmp_path=tmp_path) as profile:
            _store_diagnostic(profile.repository, key="diag", payload=_diagnostic_payload())

            row = _list_auth_diagnostics().rows[0]

            assert row.phone_state is None

    def test_every_declared_state_round_trips(self, tmp_path: Path) -> None:
        """Anti-tautology: the refusal discriminates rather than always-refusing."""
        for state in AuthDiagnosticPhoneState:
            with isolated_runtime_profile(tmp_path=tmp_path / state.value) as profile:
                _store_diagnostic(
                    profile.repository,
                    key="diag",
                    payload=_diagnostic_payload(operator_report={"phone_state": state.value}),
                )

                assert _list_auth_diagnostics().rows[0].phone_state is state
