"""Real exact-profile worker acceptance for the maritime preview CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....core.config import override_settings
from ....core.errors.error_codes import ErrorCategory, get_error_exit_code
from ....tests.cli_envelope import require_error_document, unwrap_cli_result
from .._modelo_payloads import WorkPreviewMaritimeExemptionResult
from .cli_runner import invoke_cached_cli
from .runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]


def _invoke(profile: NativeCliProfileFixture, *arguments: str, text: bool = False) -> Result:
    if profile.label is None:
        raise AssertionError("native maritime profile was not registered")
    close_active_bucket_session()
    with override_settings(cadrumo_cli_reveal_identifiers=True):
        result = invoke_cached_cli(
            (
                "--language",
                "es",
                "--format",
                "text" if text else "json",
                "--profile",
                profile.label,
                "--profile-secrets-stdin",
                "app",
                "modelo",
                "work",
                "preview-maritime-exemption",
                *arguments,
            ),
            input=json.dumps({"profile_passphrase": profile.passphrase}),
        )
    assert profile.passphrase not in result.output
    return result


def _result(result: Result) -> WorkPreviewMaritimeExemptionResult:
    assert result.exit_code == 0, result.output
    return WorkPreviewMaritimeExemptionResult.model_validate_json(
        json.dumps(unwrap_cli_result(result), ensure_ascii=False),
    )


def test_native_preview_preserves_complete_grounding_warning_and_text(tmp_path: Path) -> None:
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(
            label="native-maritime-complete-preview",
            facts={
                "maritime_worker.worker_class": "trabajador_del_mar",
                "maritime_worker.vessel_flag": "foreign",
                "maritime_worker.waters_type": "international",
                "maritime_worker.vessel_registry": "REBECA",
                "maritime_worker.retmar_registered": "true",
            },
        )

        result = _invoke(
            profile,
            "--annual-salary",
            "36500.00",
            "--qualifying-days",
            "100",
            "--gross-navigation-income",
            "30000",
        )
        payload = _result(result)
        assert payload.worker_class == "trabajador_del_mar"
        assert payload.vessel_flag == "foreign"
        assert payload.waters_type == "international"
        assert payload.vessel_registry == "REBECA"
        assert payload.retmar_registered is True
        assert payload.retmar_mandatory_filing is True
        assert payload.retmar_warning is not None
        assert "RETMAR" in payload.retmar_warning
        assert "BOE-A-2006-20764" in payload.retmar_warning
        assert len(payload.observations) == 2
        assert {reference for row in payload.observations for reference in row.legal_refs} == {
            "ley-35-2006:art-7",
            "ley-19-1994:art-75",
        }
        assert all(row.source_refs for row in payload.observations)
        assert payload.casilla_values["0525"] == payload.observations[-1].value

        text_result = _invoke(
            profile,
            "--annual-salary",
            "36500.00",
            "--qualifying-days",
            "100",
            "--gross-navigation-income",
            "30000",
            text=True,
        )
        assert text_result.exit_code == 0, text_result.output
        assert "operation\tmodelo.work.preview_maritime_exemption" in text_result.output
        assert "observation\tcasilla=0525" in text_result.output
        assert "retmar_warning\t" in text_result.output


def test_native_profile_without_maritime_selector_returns_empty_preview(tmp_path: Path) -> None:
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-maritime-no-selector", facts={})

        payload = _result(_invoke(profile))

        assert payload.worker_class is None
        assert payload.observations == []
        assert payload.casilla_values == {}
        assert payload.retmar_registered is False
        assert payload.retmar_mandatory_filing is False
        assert payload.retmar_warning is None


def test_native_da41_refusal_keeps_the_registered_error_code_and_translation(tmp_path: Path) -> None:
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(
            label="native-maritime-da41-refusal",
            facts={
                "maritime_worker.worker_class": "trabajador_del_mar",
                "maritime_worker.tuna_fleet": "true",
                "maritime_worker.pending_eu_clearance": "true",
            },
        )

        refused = _invoke(
            profile,
            "--annual-salary",
            "36500",
            "--qualifying-days",
            "100",
        )

        assert refused.exit_code == get_error_exit_code(ErrorCategory.REFUSED), refused.output
        error = require_error_document(refused.output)["error"]
        assert error["code"] == "REFUSED_RENTA_MARITIME_EXEMPTION_INACTIVE"
        assert "DA 41" in error["message"]
        assert "BOE-A-2006-20764" in error["message"]


def test_native_worker_accepts_each_existing_canonical_salary_form(tmp_path: Path) -> None:
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(
            label="native-maritime-canonical-amounts",
            facts={
                "maritime_worker.worker_class": "trabajador_del_mar",
                "maritime_worker.vessel_flag": "foreign",
            },
        )

        for raw_amount in ("36500", "36500.00", "36500.5", "0.99"):
            payload = _result(
                _invoke(profile, "--annual-salary", raw_amount, "--qualifying-days", "100"),
            )
            assert len(payload.observations) == 1
