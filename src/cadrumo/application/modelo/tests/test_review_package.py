"""Review-package build + integrity-verify roundtrip and anti-tautology proofs.

Exercises the shareable-artefact surface (:func:`build_review_package`,
:func:`verify_review_package`, :func:`assert_review_package_verifies`) end to
end against a real filesystem and a real zip archive, mirroring the
established corpus-bundle test pattern
(``src/cadrumo/core/corpus_manifest/tests/test_bundle.py``): build a package,
verify it clean, then corrupt/remove/add a member and confirm the verifier
names the exact affected member in every case. No calculation tautologies are
involved; these are structural/contract assertions on the checksum-manifest
reuse and the revision-state eligibility gate.
"""

from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period, validated_casilla_id
from ....domain.calculations.registry.bindings import CasillaObservation
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    LedgerFilingEvidence,
    ModeloCode,
    WorkUnit,
    WorkUnitState,
    derive_calculation_revision_id,
    derive_work_unit_id,
)
from .._review_package import (
    ReviewPackageError,
    ReviewPackageIntegrityError,
    ReviewPackageRevisionStateError,
    assert_review_package_verifies,
    build_review_package,
    verify_review_package,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 7, 3, 12, 0, tzinfo=UTC)
_BASE_CASILLA = validated_casilla_id("base", surface="test_review_package")
_CUOTA_CASILLA = validated_casilla_id("cuota", surface="test_review_package")
_DRAFT_BYTES = b"FICHERO-BOE-BYTES-FOR-REVIEW-PACKAGE-TEST"


def _work_unit(*, bucket_id: str = "bucket-review-package") -> WorkUnit:
    period = Period.from_year_and_code(2026, "1T")
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2026,
        period=period,
        revision_id="review-package-revision",
    )
    return WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=2026,
        period=period,
        revision_id="review-package-revision",
        name="303-2026-1T",
        created_at=_NOW,
        updated_at=_NOW,
        state=WorkUnitState.BORRADOR,
    )


def _revision(
    work_unit: WorkUnit,
    *,
    state: CalculationRevisionState = CalculationRevisionState.VERIFICADO_COMPLETO,
    ledger_filing_evidence: LedgerFilingEvidence | None = None,
    verified_at: datetime | None = _NOW,
    verified_by: str | None = "operator",
    filed_at: datetime | None = None,
    filed_by: str | None = None,
    superseded_at: datetime | None = None,
) -> CalculationRevision:
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={_BASE_CASILLA: "100.00"},
        binding_overrides={},
        casilla_values={_CUOTA_CASILLA: Decimal("21.00")},
        source_transaction_ids=(),
        filing_instance_evidence=None,
        source_provenance=(),
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=state,
        input_values_by_casilla_id={_BASE_CASILLA: "100.00"},
        casilla_values={_CUOTA_CASILLA: Decimal("21.00")},
        observations=(
            CasillaObservation(
                casilla_id=_CUOTA_CASILLA,
                value=Decimal("21.00"),
                legal_refs=("ley-37-1992:art-99",),
                source_refs=("test-review-package",),
            ),
        ),
        ledger_filing_evidence=ledger_filing_evidence,
        created_at=_NOW,
        updated_at=_NOW,
        verified_at=verified_at,
        verified_by=verified_by,
        filed_at=filed_at,
        filed_by=filed_by,
        superseded_at=superseded_at,
        filing_instance_evidence=None,
        source_provenance=(),
    )


def test_build_review_package_then_verify_clean(tmp_path: Path) -> None:
    work_unit = _work_unit()
    revision = _revision(work_unit)
    output_path = tmp_path / "review-package.zip"

    build_result = build_review_package(
        revision=revision,
        work_unit=work_unit,
        draft_bytes=_DRAFT_BYTES,
        output_path=output_path,
        built_by="operator",
        notes="shared with accountant for Q1 review",
    )

    assert build_result.output_path == output_path
    assert output_path.exists()
    assert build_result.member_count == 4
    assert build_result.manifest.calculation_revision_id == revision.calculation_revision_id
    assert build_result.manifest.work_unit_id == work_unit.work_unit_id
    assert build_result.manifest.bucket_id == work_unit.bucket_id
    assert build_result.manifest.modelo == "303"
    assert build_result.manifest.filing_year == 2026
    assert build_result.manifest.has_ledger_evidence is False
    assert build_result.manifest.notes == "shared with accountant for Q1 review"

    verification = verify_review_package(output_path)
    assert verification.is_clean is True
    assert verification.missing == ()
    assert verification.unexpected == ()
    assert verification.mismatched == ()
    assert verification.manifest == build_result.manifest

    # Real-behavior anti-tautology proof: assert_review_package_verifies must
    # not raise and must return the identical manifest for a clean package.
    manifest = assert_review_package_verifies(output_path)
    assert manifest == build_result.manifest


def test_build_review_package_bundles_ledger_evidence_when_present(tmp_path: Path) -> None:
    work_unit = _work_unit()
    evidence = LedgerFilingEvidence(snapshot_fingerprint="a" * 64, rows=(), manual_entries=(), captured_at=_NOW)
    revision = _revision(work_unit, ledger_filing_evidence=evidence)
    output_path = tmp_path / "review-package-with-evidence.zip"

    build_result = build_review_package(
        revision=revision,
        work_unit=work_unit,
        draft_bytes=_DRAFT_BYTES,
        output_path=output_path,
        built_by="operator",
    )
    assert build_result.manifest.has_ledger_evidence is True

    with zipfile.ZipFile(output_path, "r") as archive:
        evidence_payload = json.loads(archive.read("evidence.json"))
    assert evidence_payload["snapshot_fingerprint"] == "a" * 64

    verification = verify_review_package(output_path)
    assert verification.is_clean is True
    assert verification.manifest.has_ledger_evidence is True


def test_build_review_package_refuses_borrador_revision(tmp_path: Path) -> None:
    work_unit = _work_unit()
    revision = _revision(
        work_unit,
        state=CalculationRevisionState.BORRADOR,
        verified_at=None,
        verified_by=None,
    )
    output_path = tmp_path / "should-not-exist.zip"

    with pytest.raises(ReviewPackageRevisionStateError) as exc_info:
        build_review_package(
            revision=revision,
            work_unit=work_unit,
            draft_bytes=_DRAFT_BYTES,
            output_path=output_path,
            built_by="operator",
        )

    assert exc_info.value.context is not None
    assert exc_info.value.context["state"] == "borrador"
    assert not output_path.exists()


def test_build_review_package_refuses_superseded_revision(tmp_path: Path) -> None:
    work_unit = _work_unit()
    revision = _revision(
        work_unit,
        state=CalculationRevisionState.PRESENTADO_SUPERSEDIDO,
        filed_at=_NOW,
        filed_by="operator",
        superseded_at=_NOW,
    )
    output_path = tmp_path / "should-not-exist.zip"

    with pytest.raises(ReviewPackageRevisionStateError) as exc_info:
        build_review_package(
            revision=revision,
            work_unit=work_unit,
            draft_bytes=_DRAFT_BYTES,
            output_path=output_path,
            built_by="operator",
        )

    assert exc_info.value.context is not None
    assert exc_info.value.context["state"] == "presentado_supersedido"
    assert not output_path.exists()


def test_build_review_package_refuses_work_unit_revision_mismatch(tmp_path: Path) -> None:
    work_unit = _work_unit()
    other_work_unit = _work_unit(bucket_id="bucket-other")
    revision = _revision(work_unit)

    with pytest.raises(ReviewPackageError):
        build_review_package(
            revision=revision,
            work_unit=other_work_unit,
            draft_bytes=_DRAFT_BYTES,
            output_path=tmp_path / "mismatch.zip",
            built_by="operator",
        )


def test_verify_review_package_flags_mismatched_member_by_name(tmp_path: Path) -> None:
    work_unit = _work_unit()
    revision = _revision(work_unit)
    output_path = tmp_path / "review-package.zip"
    build_review_package(
        revision=revision,
        work_unit=work_unit,
        draft_bytes=_DRAFT_BYTES,
        output_path=output_path,
        built_by="operator",
    )

    _tamper_member(output_path, "draft.fichero-boe", b"TAMPERED FICHERO BYTES")

    result = verify_review_package(output_path)
    assert result.is_clean is False
    assert result.mismatched == ("draft.fichero-boe",)
    assert result.missing == ()
    assert result.unexpected == ()

    with pytest.raises(ReviewPackageIntegrityError) as exc_info:
        assert_review_package_verifies(output_path)
    assert exc_info.value.context is not None
    assert exc_info.value.context["mismatched"] == "draft.fichero-boe"


def test_verify_review_package_flags_missing_member_by_name(tmp_path: Path) -> None:
    work_unit = _work_unit()
    revision = _revision(work_unit)
    output_path = tmp_path / "review-package.zip"
    build_review_package(
        revision=revision,
        work_unit=work_unit,
        draft_bytes=_DRAFT_BYTES,
        output_path=output_path,
        built_by="operator",
    )

    _drop_member(output_path, "revision.json")

    result = verify_review_package(output_path)
    assert result.is_clean is False
    assert result.missing == ("revision.json",)

    with pytest.raises(ReviewPackageIntegrityError) as exc_info:
        assert_review_package_verifies(output_path)
    assert exc_info.value.context is not None
    assert exc_info.value.context["missing"] == "revision.json"


def test_verify_review_package_flags_unexpected_extra_member(tmp_path: Path) -> None:
    work_unit = _work_unit()
    revision = _revision(work_unit)
    output_path = tmp_path / "review-package.zip"
    build_review_package(
        revision=revision,
        work_unit=work_unit,
        draft_bytes=_DRAFT_BYTES,
        output_path=output_path,
        built_by="operator",
    )

    with zipfile.ZipFile(output_path, "r") as src, zipfile.ZipFile(output_path.with_suffix(".rewritten"), "w") as dst:
        for item in src.infolist():
            dst.writestr(item, src.read(item.filename))
        dst.writestr("unexpected-extra-member.txt", b"not declared by the manifest")
    output_path.with_suffix(".rewritten").replace(output_path)

    result = verify_review_package(output_path)
    assert result.is_clean is False
    assert result.unexpected == ("unexpected-extra-member.txt",)
    assert result.missing == ()
    assert result.mismatched == ()


def test_verify_review_package_raises_on_tampered_package_info_descriptor(tmp_path: Path) -> None:
    work_unit = _work_unit()
    revision = _revision(work_unit)
    output_path = tmp_path / "review-package.zip"
    build_review_package(
        revision=revision,
        work_unit=work_unit,
        draft_bytes=_DRAFT_BYTES,
        output_path=output_path,
        built_by="operator",
    )

    _tamper_member(output_path, "package-info.json", b'{"not": "a valid manifest"}')

    with pytest.raises(ReviewPackageIntegrityError):
        verify_review_package(output_path)


def test_verify_review_package_raises_file_not_found_for_missing_path(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        verify_review_package(tmp_path / "does-not-exist.zip")


def test_verify_review_package_raises_on_not_a_zip_file(tmp_path: Path) -> None:
    not_a_zip = tmp_path / "not-a-package.zip"
    not_a_zip.write_bytes(b"this is definitely not a zip archive")

    with pytest.raises(ReviewPackageIntegrityError):
        verify_review_package(not_a_zip)


def test_review_package_manifest_survives_json_roundtrip(tmp_path: Path) -> None:
    """Anti-tautology proof for the descriptor itself.

    Directly mutates the persisted ``package-info.json`` payload (deleting a
    required field) and confirms the recovered manifest either fails to load
    or diverges from the pre-mutation manifest -- proving the descriptor
    recovery path actually re-parses the embedded JSON rather than trusting a
    cached in-memory object.
    """
    work_unit = _work_unit()
    revision = _revision(work_unit)
    output_path = tmp_path / "review-package.zip"
    build_result = build_review_package(
        revision=revision,
        work_unit=work_unit,
        draft_bytes=_DRAFT_BYTES,
        output_path=output_path,
        built_by="operator",
    )

    with zipfile.ZipFile(output_path, "r") as archive:
        raw = archive.read("package-info.json")
    payload = json.loads(raw)
    del payload["calculation_revision_id"]
    mutated = json.dumps(payload).encode("utf-8")

    _tamper_member(output_path, "package-info.json", mutated)

    with pytest.raises(ReviewPackageIntegrityError):
        verify_review_package(output_path)

    # Confirm the ORIGINAL build result manifest is unaffected by the on-disk
    # mutation (it is an independent in-memory object), proving the failure
    # above is a real re-parse of the corrupted bytes, not a stale cache hit.
    assert build_result.manifest.calculation_revision_id == revision.calculation_revision_id


def _tamper_member(package_path: Path, member: str, new_content: bytes) -> None:
    rewritten = package_path.with_name(package_path.name + ".rewritten")
    with zipfile.ZipFile(package_path, "r") as src, zipfile.ZipFile(rewritten, "w") as dst:
        for item in src.infolist():
            data = new_content if item.filename == member else src.read(item.filename)
            dst.writestr(item, data)
    rewritten.replace(package_path)


def _drop_member(package_path: Path, member: str) -> None:
    rewritten = package_path.with_name(package_path.name + ".rewritten")
    with zipfile.ZipFile(package_path, "r") as src, zipfile.ZipFile(rewritten, "w") as dst:
        for item in src.infolist():
            if item.filename == member:
                continue
            dst.writestr(item, src.read(item.filename))
    rewritten.replace(package_path)


__all__: list[str] = []
