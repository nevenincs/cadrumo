"""CLI surface tests for ``aeat app modelo review-package build/verify``."""

from __future__ import annotations

import json
import zipfile
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....application.workflow.persistence import workflow_state_repository
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.modelos.calculation_repository import upsert_calculation_revision
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.repository import upsert_work_unit
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.user_profile.values import UserProfileFact
from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from ....tests.cli_runner import invoke_cached_cli
from ....tests.profile_capsule import set_active_test_profile_facts
from ....tests.registry_revision import active_registry_revision_id
from ._modelo_review_package_support import build_review_package_via_cli, seed_exportable_modelo_revision
from ._strict_cli_fixture_support import binding_isolated_backend

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

__all__ = ["binding_isolated_backend"]


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


def _set_export_profile_name() -> None:
    set_active_test_profile_facts(
        (
            UserProfileFact(path="identity.name", value="Ana"),
            UserProfileFact(path="identity.surnames", value="Review Package Test"),
            UserProfileFact(path="activities.description", value="Consulting"),
            # Modelo 111 declares whether the withholder is a colegio
            # concertado in its own header field, and the producer refuses an
            # undeclared value rather than assume one.
            UserProfileFact(path="withholding.colegio_concertado", value=False),
        ),
    )


_M111_CASILLA_03: CasillaId = validated_casilla_id("03", surface="modelo 111 review-package test casilla")
_M111_CASILLA_06: CasillaId = validated_casilla_id("06", surface="modelo 111 review-package test casilla")
_M111_CASILLA_09: CasillaId = validated_casilla_id("09", surface="modelo 111 review-package test casilla")
_M111_CASILLA_12: CasillaId = validated_casilla_id("12", surface="modelo 111 review-package test casilla")
_M111_CASILLA_15: CasillaId = validated_casilla_id("15", surface="modelo 111 review-package test casilla")
_M111_CASILLA_18: CasillaId = validated_casilla_id("18", surface="modelo 111 review-package test casilla")
_M111_CASILLA_21: CasillaId = validated_casilla_id("21", surface="modelo 111 review-package test casilla")
_M111_CASILLA_24: CasillaId = validated_casilla_id("24", surface="modelo 111 review-package test casilla")
_M111_CASILLA_27: CasillaId = validated_casilla_id("27", surface="modelo 111 review-package test casilla")
_M111_CASILLA_29: CasillaId = validated_casilla_id("29", surface="modelo 111 review-package test casilla")

_MODELO_111_INPUTS: dict[CasillaId, str] = {
    _M111_CASILLA_03: "180.25",
    _M111_CASILLA_06: "12.10",
    _M111_CASILLA_09: "300.00",
    _M111_CASILLA_12: "14.40",
    _M111_CASILLA_15: "25.00",
    _M111_CASILLA_18: "0.50",
    _M111_CASILLA_21: "7.00",
    _M111_CASILLA_24: "8.00",
    _M111_CASILLA_27: "9.00",
    _M111_CASILLA_29: "40.00",
}


def test_review_package_build_then_verify_end_to_end(tmp_path: Path) -> None:
    _set_export_profile_name()
    work_unit_id, calculation_revision_id = seed_exportable_modelo_revision(
        input_values_by_casilla_id=_MODELO_111_INPUTS,
    )
    package_path = tmp_path / "review-package.zip"

    build_result = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "review-package",
            "build",
            work_unit_id,
            "--output",
            str(package_path),
            "--by",
            "Ana",
            "--notes",
            "for accountant review",
        ],
    )

    assert build_result.exit_code == 0, build_result.output
    build_payload = _payload(build_result.output)
    assert build_payload["calculation_revision_id"] == calculation_revision_id
    assert build_payload["modelo"] == "111"
    assert build_payload["filing_year"] == 2026
    assert build_payload["member_count"] == 4
    assert build_payload["has_ledger_evidence"] is False
    assert build_payload["built_by"] == "Ana"
    assert package_path.exists()

    with zipfile.ZipFile(package_path, "r") as archive:
        names = set(archive.namelist())
    assert names == {
        "corpus.manifest.json",
        "draft.fichero-boe",
        "revision.json",
        "evidence.json",
        "package-info.json",
    }

    verify_result = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "review-package",
            "verify",
            str(package_path),
        ],
    )

    assert verify_result.exit_code == 0, verify_result.output
    verify_payload = _payload(verify_result.output)
    assert verify_payload["is_clean"] is True
    assert verify_payload["missing"] == []
    assert verify_payload["unexpected"] == []
    assert verify_payload["mismatched"] == []
    assert verify_payload["calculation_revision_id"] == calculation_revision_id
    assert verify_payload["modelo"] == "111"
    assert verify_payload["built_by"] == "Ana"


def test_review_package_verify_detects_tampered_member(tmp_path: Path) -> None:
    _set_export_profile_name()
    work_unit_id, _ = seed_exportable_modelo_revision(input_values_by_casilla_id=_MODELO_111_INPUTS)
    package_path = tmp_path / "review-package.zip"

    build_result = _invoke(
        ["app", "modelo", "review-package", "build", work_unit_id, "--output", str(package_path)],
    )
    assert build_result.exit_code == 0, build_result.output

    rewritten = package_path.with_suffix(".rewritten")
    with zipfile.ZipFile(package_path, "r") as src, zipfile.ZipFile(rewritten, "w") as dst:
        for item in src.infolist():
            data = b"TAMPERED" if item.filename == "draft.fichero-boe" else src.read(item.filename)
            dst.writestr(item, data)
    rewritten.replace(package_path)

    verify_result = _invoke(
        ["--format", "json", "app", "modelo", "review-package", "verify", str(package_path)],
    )

    assert verify_result.exit_code == 0, verify_result.output
    verify_payload = _payload(verify_result.output)
    assert verify_payload["is_clean"] is False
    assert verify_payload["mismatched"] == ["draft.fichero-boe"]


def test_review_package_verify_refuses_missing_package(tmp_path: Path) -> None:
    result = _invoke(
        ["app", "modelo", "review-package", "verify", str(tmp_path / "does-not-exist.zip")],
    )
    assert result.exit_code != 0, result.output


def test_review_package_build_requires_output_flag() -> None:
    _set_export_profile_name()
    work_unit_id, _ = seed_exportable_modelo_revision(input_values_by_casilla_id=_MODELO_111_INPUTS)

    result = _invoke(["app", "modelo", "review-package", "build", work_unit_id])
    assert result.exit_code != 0, result.output


def test_review_package_keeps_raw_revision_and_selector_refusals_distinct(tmp_path: Path) -> None:
    """The review builder preserves the shared resolver's address-versus-selector errors."""
    _set_export_profile_name()
    raw_revision = _invoke(
        [
            "app",
            "modelo",
            "review-package",
            "build",
            "--output",
            str(tmp_path / "raw.zip"),
            "--revision",
            "not-a-revision-id",
        ]
    )
    selector = _invoke(
        [
            "app",
            "modelo",
            "review-package",
            "build",
            "--output",
            str(tmp_path / "selector.zip"),
            "--select",
            "not-a-selector",
        ]
    )

    assert raw_revision.exit_code != 0, raw_revision.output
    assert selector.exit_code != 0, selector.output
    assert "not-a-revision-id" in raw_revision.output
    assert "not-a-selector" in selector.output


def test_review_package_invalid_period_names_the_selected_modelo_tokens(tmp_path: Path) -> None:
    """An annual modelo rejects a quarterly token with its declared annual token."""
    _set_export_profile_name()

    result = _invoke(
        [
            "app",
            "modelo",
            "review-package",
            "build",
            "--modelo",
            "100",
            "--year",
            "2024",
            "--period",
            "1T",
            "--output",
            str(tmp_path / "invalid-period.zip"),
        ]
    )

    assert result.exit_code != 0, result.output
    assert "0A" in result.output


def test_review_package_help_advertises_local_only() -> None:
    result = _invoke(["app", "modelo", "review-package", "build", "--help"])
    assert result.exit_code == 0, result.output
    assert any(token in result.output.lower() for token in ("local-only", "local;", "local.", "nunca")), result.output
    assert "--refund-election" in result.output
    assert "--payment-election" in result.output
    assert "--disposition" not in result.output


def test_review_package_build_refuses_draft_revision(tmp_path: Path) -> None:
    """A BORRADOR-state (never verified) revision cannot be packaged for review."""
    state = workflow_state_repository().load()
    bucket_id = state.active_profile_bucket_id()
    assert bucket_id is not None
    revision_id = active_registry_revision_id(modelo="111", filing_year=2026, period="1T")
    filing_period = Period.from_year_and_code(2026, "1T")
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo="111",
        filing_year=2026,
        period=filing_period,
        revision_id=revision_id,
    )
    now = datetime.now(UTC)
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode("111"),
        filing_year=2026,
        period=filing_period,
        revision_id=revision_id,
        name="111-2026-1T",
        created_at=now,
        updated_at=now,
    )
    WorkUnitCatalogueRepository().save(upsert_work_unit(WorkUnitCatalogueRepository().load(), work_unit))
    calculation_revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    revision = CalculationRevision(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        created_at=now,
        updated_at=now,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    cr_repo = CalculationRevisionCatalogueRepository()
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), revision))

    package_path = tmp_path / "should-not-exist.zip"
    result = _invoke(
        [
            "app",
            "modelo",
            "review-package",
            "build",
            work_unit_id,
            "--output",
            str(package_path),
        ],
    )
    assert result.exit_code != 0, result.output
    assert not package_path.exists()


def _build_package(tmp_path: Path, *, name: str = "review-package.zip") -> Path:
    _set_export_profile_name()
    package_path, _, _ = build_review_package_via_cli(
        tmp_path, invoke=_invoke, input_values_by_casilla_id=_MODELO_111_INPUTS, name=name
    )
    return package_path


def test_review_package_sign_then_verify_signature_end_to_end(tmp_path: Path) -> None:
    package_path = _build_package(tmp_path)
    signature_path = tmp_path / "signature.json"

    sign_result = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "review-package",
            "sign",
            str(package_path),
            "--output",
            str(signature_path),
        ],
    )
    assert sign_result.exit_code == 0, sign_result.output
    sign_payload = _payload(sign_result.output)
    assert signature_path.exists()
    public_key_hex = sign_payload["signer_public_key_hex"]
    assert len(public_key_hex) == 64
    bytes.fromhex(public_key_hex)  # is valid hex

    # The private key must never appear anywhere in the CLI output.
    signature_envelope = signature_path.read_text(encoding="utf-8")
    assert "private_key" not in sign_result.output
    assert public_key_hex in signature_envelope

    verify_signature_result = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "review-package",
            "verify-signature",
            str(package_path),
            str(signature_path),
            "--public-key",
            public_key_hex,
        ],
    )
    assert verify_signature_result.exit_code == 0, verify_signature_result.output
    verify_payload = _payload(verify_signature_result.output)
    assert verify_payload["is_valid"] is True


def test_review_package_verify_signature_fails_on_tampered_package(tmp_path: Path) -> None:
    package_path = _build_package(tmp_path)
    signature_path = tmp_path / "signature.json"

    sign_result = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "review-package",
            "sign",
            str(package_path),
            "--output",
            str(signature_path),
        ],
    )
    assert sign_result.exit_code == 0, sign_result.output
    public_key_hex = _payload(sign_result.output)["signer_public_key_hex"]

    rewritten = package_path.with_suffix(".rewritten")
    with zipfile.ZipFile(package_path, "r") as src, zipfile.ZipFile(rewritten, "w") as dst:
        for item in src.infolist():
            data = b"TAMPERED" if item.filename == "draft.fichero-boe" else src.read(item.filename)
            dst.writestr(item, data)
    rewritten.replace(package_path)

    verify_result = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "review-package",
            "verify-signature",
            str(package_path),
            str(signature_path),
            "--public-key",
            public_key_hex,
        ],
    )
    assert verify_result.exit_code == 0, verify_result.output
    assert _payload(verify_result.output)["is_valid"] is False


def test_review_package_verify_signature_fails_on_wrong_public_key(tmp_path: Path) -> None:
    package_path = _build_package(tmp_path)
    signature_path = tmp_path / "signature.json"
    _invoke(
        ["app", "modelo", "review-package", "sign", str(package_path), "--output", str(signature_path)],
    )

    wrong_public_key = "0" * 64
    verify_result = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "review-package",
            "verify-signature",
            str(package_path),
            str(signature_path),
            "--public-key",
            wrong_public_key,
        ],
    )
    assert verify_result.exit_code == 0, verify_result.output
    assert _payload(verify_result.output)["is_valid"] is False


def test_review_package_counter_sign_then_verify_receipt_end_to_end(tmp_path: Path) -> None:
    package_path = _build_package(tmp_path)
    signature_path = tmp_path / "signature.json"

    sign_result = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "review-package",
            "sign",
            str(package_path),
            "--output",
            str(signature_path),
        ],
    )
    assert sign_result.exit_code == 0, sign_result.output
    operator_public_key_hex = _payload(sign_result.output)["signer_public_key_hex"]

    receipt_path = tmp_path / "receipt.json"
    counter_sign_result = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "review-package",
            "counter-sign",
            str(package_path),
            str(signature_path),
            "--output",
            str(receipt_path),
            "--note",
            "reviewed, no changes",
        ],
    )
    assert counter_sign_result.exit_code == 0, counter_sign_result.output
    counter_sign_payload = _payload(counter_sign_result.output)
    assert receipt_path.exists()
    counter_signer_public_key_hex = counter_sign_payload["counter_signer_public_key_hex"]
    assert len(counter_signer_public_key_hex) == 64
    assert counter_sign_payload["note"] == "reviewed, no changes"

    # The counter-signer's own bucket is the same active bucket in this single-profile
    # test harness, so the operator and the counter-signer public keys are identical
    # here; verify-receipt still exercises both signature layers independently.
    receipt_envelope = receipt_path.read_text(encoding="utf-8")
    assert "private_key" not in counter_sign_result.output
    assert counter_signer_public_key_hex in receipt_envelope

    verify_receipt_result = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "review-package",
            "verify-receipt",
            str(package_path),
            str(receipt_path),
            "--operator-public-key",
            operator_public_key_hex,
            "--counter-signer-public-key",
            counter_signer_public_key_hex,
        ],
    )
    assert verify_receipt_result.exit_code == 0, verify_receipt_result.output
    assert _payload(verify_receipt_result.output)["is_valid"] is True


def test_review_package_verify_receipt_fails_when_note_edited(tmp_path: Path) -> None:
    package_path = _build_package(tmp_path)
    signature_path = tmp_path / "signature.json"
    sign_result = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "review-package",
            "sign",
            str(package_path),
            "--output",
            str(signature_path),
        ],
    )
    operator_public_key_hex = _payload(sign_result.output)["signer_public_key_hex"]

    receipt_path = tmp_path / "receipt.json"
    counter_sign_result = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "review-package",
            "counter-sign",
            str(package_path),
            str(signature_path),
            "--output",
            str(receipt_path),
            "--note",
            "approved as filed",
        ],
    )
    counter_signer_public_key_hex = _payload(counter_sign_result.output)["counter_signer_public_key_hex"]

    receipt_json = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt_json["note"] = "approved WITH CHANGES"
    receipt_path.write_text(json.dumps(receipt_json), encoding="utf-8")

    verify_receipt_result = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "review-package",
            "verify-receipt",
            str(package_path),
            str(receipt_path),
            "--operator-public-key",
            operator_public_key_hex,
            "--counter-signer-public-key",
            counter_signer_public_key_hex,
        ],
    )
    assert verify_receipt_result.exit_code == 0, verify_receipt_result.output
    assert _payload(verify_receipt_result.output)["is_valid"] is False


def test_review_package_sign_refuses_missing_package(tmp_path: Path) -> None:
    _set_export_profile_name()
    result = _invoke(
        [
            "app",
            "modelo",
            "review-package",
            "sign",
            str(tmp_path / "does-not-exist.zip"),
            "--output",
            str(tmp_path / "signature.json"),
        ],
    )
    assert result.exit_code != 0, result.output


def test_review_package_verify_signature_refuses_missing_signature_file(tmp_path: Path) -> None:
    package_path = _build_package(tmp_path)
    result = _invoke(
        [
            "app",
            "modelo",
            "review-package",
            "verify-signature",
            str(package_path),
            str(tmp_path / "does-not-exist-signature.json"),
            "--public-key",
            "0" * 64,
        ],
    )
    assert result.exit_code != 0, result.output


def test_review_package_verify_signature_refuses_malformed_signature_file(tmp_path: Path) -> None:
    package_path = _build_package(tmp_path)
    signature_path = tmp_path / "signature.json"
    signature_path.write_text("not valid json at all", encoding="utf-8")

    result = _invoke(
        [
            "app",
            "modelo",
            "review-package",
            "verify-signature",
            str(package_path),
            str(signature_path),
            "--public-key",
            "0" * 64,
        ],
    )
    assert result.exit_code != 0, result.output


def test_review_package_counter_sign_refuses_missing_signature_file(tmp_path: Path) -> None:
    package_path = _build_package(tmp_path)
    result = _invoke(
        [
            "app",
            "modelo",
            "review-package",
            "counter-sign",
            str(package_path),
            str(tmp_path / "does-not-exist-signature.json"),
            "--output",
            str(tmp_path / "receipt.json"),
        ],
    )
    assert result.exit_code != 0, result.output


def test_review_package_verify_receipt_refuses_missing_receipt_file(tmp_path: Path) -> None:
    package_path = _build_package(tmp_path)
    result = _invoke(
        [
            "app",
            "modelo",
            "review-package",
            "verify-receipt",
            str(package_path),
            str(tmp_path / "does-not-exist-receipt.json"),
            "--operator-public-key",
            "0" * 64,
            "--counter-signer-public-key",
            "1" * 64,
        ],
    )
    assert result.exit_code != 0, result.output


__all__: list[str] = []
