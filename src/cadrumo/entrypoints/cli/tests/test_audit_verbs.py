"""Native-worker coverage for ``aeat app modelo audit {view,check,export}``.

Each behavioral route uses an authenticated worker backed by a real encrypted
profile. The canonical evidence service seeds the manifest and supplies an
independent check oracle; these tests do not add a record loader.
"""

from __future__ import annotations

import json
import sys
import zipfile
from collections.abc import Sequence
from pathlib import Path
from typing import cast

import pytest
from click.testing import Result

from ....adapters.persistence.profile.evidence_bundles import (
    EvidenceBundleRepository,
    EvidenceBundleWorkUnitRepository,
)
from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ....application.evidence.models import EvidenceBundle
from ....application.evidence.payloads import EvidenceRecordRefPayload
from ....application.evidence.ports import EvidenceBundlePorts
from ....application.evidence.service import EvidenceBundleService
from ....application.user_profile.login_session import resolve_login_target
from ....core.output_rendering import jsonable_output_payload
from ....core.redaction.rules import redact_structured_for_cli_output
from ....tests.cli_envelope import require_error_document, unwrap_cli_result
from .cli_runner import invoke_cached_cli
from .runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORK_UNIT_ID = "a" * 64
_REVISION_ID = "b" * 64
_FILING_ID = "c" * 64


def _invoke(args: Sequence[str]) -> Result:
    """Invoke a public command without opening a profile worker."""
    return invoke_cached_cli(args)


def _invoke_native(profile: NativeCliProfileFixture, args: Sequence[str], *, json_output: bool = True) -> Result:
    """Invoke one CLI audit request through its authenticated native worker."""
    if profile.label is None:
        raise AssertionError("native audit profile was not registered")
    close_active_bucket_session()
    result = invoke_cached_cli(
        (
            "--language",
            "en",
            "--format",
            "json" if json_output else "text",
            "--profile",
            profile.label,
            "--profile-secrets-stdin",
            *args,
        ),
        input=json.dumps({"profile_passphrase": profile.passphrase}),
    )
    assert profile.passphrase not in result.output
    return result


def _service_for(profile: NativeCliProfileFixture) -> tuple[str, EvidenceBundleService]:
    """Return the canonical evidence service bound to this profile's records."""
    if profile.label is None:
        raise AssertionError("native audit profile was not registered")
    bucket_id = resolve_login_target(profile.label).bucket_id
    objects = secure_object_repository_for_bucket(bucket_id)
    service = EvidenceBundleService(
        ports=EvidenceBundlePorts(
            repository=EvidenceBundleRepository(objects=objects),
            work_units=EvidenceBundleWorkUnitRepository(bucket_id=bucket_id, objects=objects),
        ),
    )
    return bucket_id, service


def _seed_bundle(profile: NativeCliProfileFixture) -> tuple[EvidenceBundleService, EvidenceBundle]:
    """Build one real encrypted manifest through the existing evidence service."""
    bucket_id, service = _service_for(profile)
    bundle = service.build(
        bucket_id=bucket_id,
        work_unit_id=_WORK_UNIT_ID,
        record_payloads={
            ("calculation_revision", _REVISION_ID): b"casilla-01=1000.00\ncasilla-02=210.00\n",
            ("filing_record", _FILING_ID): b"justificante: CSV12345\n",
        },
        calculation_revision_id=_REVISION_ID,
        filing_record_id=_FILING_ID,
    )
    return service, bundle


def _expected_view(bundle: EvidenceBundle) -> dict[str, object]:
    from ..modelo_aux_payloads import ModeloAuditViewResult

    result = ModeloAuditViewResult(
        bundle_id=bundle.bundle_id,
        manifest_version=bundle.manifest_version,
        bucket_id=bundle.bucket_id,
        work_unit_id=bundle.work_unit_id,
        calculation_revision_id=bundle.calculation_revision_id,
        filing_record_id=bundle.filing_record_id,
        verification_state=bundle.verification_state,
        completeness_ratio=bundle.completeness_ratio,
        records=[
            EvidenceRecordRefPayload(
                object_type=record.object_type,
                object_id=record.object_id,
                content_sha256=record.content_sha256,
                payload_size_bytes=record.payload_size_bytes,
            )
            for record in bundle.records
        ],
        created_at=bundle.created_at,
        notes=bundle.notes,
    )
    return cast("dict[str, object]", redact_structured_for_cli_output(jsonable_output_payload(result)))


def _expected_check(service: EvidenceBundleService, bundle: EvidenceBundle) -> dict[str, object]:
    from ..modelo_aux_payloads import EvidenceBundleCheckFindingPayload, ModeloAuditCheckResult

    report = service.check(bucket_id=bundle.bucket_id, bundle_id=bundle.bundle_id)
    result = ModeloAuditCheckResult(
        bundle_id=report.bundle_id,
        verification_state=report.verification_state,
        completeness_ratio=report.completeness_ratio,
        findings=[
            EvidenceBundleCheckFindingPayload(
                check=finding.check.value,
                passed=finding.passed,
                detail=finding.detail,
            )
            for finding in report.findings
        ],
    )
    return cast("dict[str, object]", redact_structured_for_cli_output(result.model_dump(mode="json")))


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_audit_view_renders_the_complete_canonical_bundle_manifest(tmp_path: Path) -> None:
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-audit-view", facts={})
        _service, bundle = _seed_bundle(profile)

        result = _invoke_native(profile, ["app", "modelo", "audit", "view", bundle.bundle_id])

        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["command"] == "modelo.audit.show"
        assert unwrap_cli_result(result) == _expected_view(bundle)
        text_result = _invoke_native(
            profile,
            ["app", "modelo", "audit", "view", bundle.bundle_id],
            json_output=False,
        )
        assert text_result.exit_code == 0, text_result.output
        assert f"bundle_id\t{bundle.bundle_id}" in text_result.output
        assert f"work_unit_id\t{_WORK_UNIT_ID}" in text_result.output
        assert "manifest_version\t" in text_result.output
        assert "records\t2" in text_result.output


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_audit_view_preserves_the_canonical_unknown_bundle_refusal(tmp_path: Path) -> None:
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-audit-not-found", facts={})
        _seed_bundle(profile)

        result = _invoke_native(profile, ["app", "modelo", "audit", "view", "0" * 64])

        assert result.exit_code != 0, result.output
        assert "Traceback" not in result.output
        assert require_error_document(result.output)["error"]["code"] == "REFUSED_EVIDENCE_BUNDLE_NOT_FOUND"


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_audit_check_returns_the_complete_canonical_verification_report(tmp_path: Path) -> None:
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-audit-check", facts={})
        service, bundle = _seed_bundle(profile)
        expected = _expected_check(service, bundle)

        result = _invoke_native(profile, ["app", "modelo", "audit", "check", bundle.bundle_id])

        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["command"] == "modelo.audit.check"
        assert unwrap_cli_result(result) == expected
        text_result = _invoke_native(
            profile,
            ["app", "modelo", "audit", "check", bundle.bundle_id],
            json_output=False,
        )
        assert text_result.exit_code == 0, text_result.output
        assert f"bundle_id\t{bundle.bundle_id}" in text_result.output
        assert "verification_state\tincomplete" in text_result.output
        assert "completeness_ratio\t0.0" in text_result.output
        assert "findings\t5" in text_result.output


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_audit_export_writes_the_canonical_incomplete_bundle_when_forced(tmp_path: Path) -> None:
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-audit-export", facts={})
        _service, bundle = _seed_bundle(profile)
        output = tmp_path / "bundle.zip"

        result = _invoke_native(
            profile,
            ["app", "modelo", "audit", "export", bundle.bundle_id, "--output", str(output), "--force-incomplete"],
        )

        assert result.exit_code == 0, result.output
        assert output.is_file()
        with zipfile.ZipFile(output) as archive:
            names = archive.namelist()
        assert names == ["manifest.json"]
        assert names[-1] == "manifest.json"
        assert unwrap_cli_result(result) == redact_structured_for_cli_output(
            {
                "operation": "modelo.audit.export",
                "bucket_id": bundle.bucket_id,
                "bundle_id": bundle.bundle_id,
                "output": str(output),
                "verification_state": bundle.verification_state.value,
                "records": len(bundle.records),
            },
        )
        text_output = tmp_path / "bundle-text.zip"
        text_result = _invoke_native(
            profile,
            [
                "app",
                "modelo",
                "audit",
                "export",
                bundle.bundle_id,
                "--output",
                str(text_output),
                "--force-incomplete",
            ],
            json_output=False,
        )
        assert text_result.exit_code == 0, text_result.output
        assert text_output.is_file()
        assert f"bundle_id\t{bundle.bundle_id}" in text_result.output
        assert f"output\t{text_output}" in text_result.output


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_audit_export_refuses_incomplete_without_force_and_preserves_the_file(tmp_path: Path) -> None:
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-audit-export-refusal", facts={})
        _service, bundle = _seed_bundle(profile)
        output = tmp_path / "bundle.zip"

        result = _invoke_native(
            profile, ["app", "modelo", "audit", "export", bundle.bundle_id, "--output", str(output)]
        )

        assert result.exit_code != 0, result.output
        assert not output.exists()
        assert "Traceback" not in result.output
        assert require_error_document(result.output)["error"]["code"] == "REFUSED_EVIDENCE_BUNDLE_VERIFICATION"


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_audit_export_still_requires_its_output_path(tmp_path: Path) -> None:
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-audit-output-required", facts={})
        _service, bundle = _seed_bundle(profile)

        result = _invoke_native(profile, ["app", "modelo", "audit", "export", bundle.bundle_id])

        assert result.exit_code != 0, result.output


def test_audit_replay_command_is_removed() -> None:
    result = _invoke(["app", "modelo", "audit", "replay", "0" * 64])
    assert result.exit_code != 0, result.output


def test_audit_replay_result_schema_is_not_registered() -> None:
    from ..command_schema import command_schema_types

    assert "modelo.audit.replay" not in command_schema_types()


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_audit_workflow_runs_view_check_and_export_on_one_encrypted_profile(tmp_path: Path) -> None:
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-audit-workflow", facts={})
        _service, bundle = _seed_bundle(profile)
        output = tmp_path / "bundle-e2e.zip"

        view = _invoke_native(profile, ["app", "modelo", "audit", "view", bundle.bundle_id])
        check = _invoke_native(profile, ["app", "modelo", "audit", "check", bundle.bundle_id])
        export = _invoke_native(
            profile,
            ["app", "modelo", "audit", "export", bundle.bundle_id, "--output", str(output), "--force-incomplete"],
        )

        assert view.exit_code == 0, view.output
        assert check.exit_code == 0, check.output
        assert export.exit_code == 0, export.output
        assert output.is_file()
        with zipfile.ZipFile(output) as archive:
            assert archive.namelist() == ["manifest.json"]


def test_audit_help_text_uses_accepted_vocabulary() -> None:
    """Help stays public and never implies AEAT filing or remote contact."""
    forbidden_en = ("submit ", "submission", "send to aeat", "upload to aeat", "live filing", "telematic")
    forbidden_es = ("enviar a aeat", "subir a aeat", "presentar telemáticamente")
    accepted_per_verb = {
        "view": (("evidence", "evidencia"), ("bundle", "paquete"), ("manifest", "manifiesto", "manifest")),
        "check": (("verify", "verificar", "reverificar"), ("bundle", "paquete")),
        "export": (("bundle", "paquete"), ("manifest", "manifiesto")),
    }
    negations = ("never", "not ", "no ", "without ", "nunca", "ni ", "sin ")

    for verb, required_groups in accepted_per_verb.items():
        result = _invoke(["app", "modelo", "audit", verb, "--help"])
        assert result.exit_code == 0, (verb, result.output)
        lower = result.output.lower()
        for group in required_groups:
            assert any(term in lower for term in group), (verb, group, result.output)
        normalised = " ".join(lower.split())
        for bad in forbidden_en + forbidden_es:
            idx = normalised.find(bad)
            while idx != -1:
                preceding = normalised[max(0, idx - 28) : idx]
                assert any(neg in preceding for neg in negations), (verb, bad, result.output)
                idx = normalised.find(bad, idx + 1)


def test_audit_verbs_refuse_without_an_active_profile(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        for command in (
            ["view", "0" * 64],
            ["check", "0" * 64],
            ["export", "0" * 64, "--output", str(tmp_path / "no-profile.zip")],
        ):
            result = _invoke(["app", "modelo", "audit", *command])
            assert result.exit_code != 0, (command, result.output)
