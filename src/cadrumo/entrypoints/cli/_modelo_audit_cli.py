"""Modelo evidence-bundle audit CLI command surface."""

from __future__ import annotations

from pathlib import Path

import typer

from ._common import active_bucket_id_or_refuse, emit_envelope


def _evidence_bundle_service():
    from ...application.evidence.service import EvidenceBundleService

    return EvidenceBundleService()


def audit_view(
    ctx: typer.Context,
    bundle_id: str,
) -> None:
    """Render an evidence bundle's manifest and referenced record list."""
    bucket_id = active_bucket_id_or_refuse()
    bundle = _evidence_bundle_service().show(bucket_id=bucket_id, bundle_id=bundle_id)
    from ._modelo_payloads import EvidenceRecordRefPayload, ModeloAuditViewResult

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
                object_type=rec.object_type,
                object_id=rec.object_id,
                content_sha256=rec.content_sha256,
                payload_size_bytes=rec.payload_size_bytes,
            )
            for rec in bundle.records
        ],
        created_at=bundle.created_at,
        notes=bundle.notes,
    )
    lines = [
        f"bucket\t{bucket_id}",
        f"bundle_id\t{bundle.bundle_id}",
        f"work_unit_id\t{bundle.work_unit_id}",
        f"manifest_version\t{bundle.manifest_version}",
        f"verification_state\t{bundle.verification_state.value}",
        f"records\t{len(bundle.records)}",
    ]
    emit_envelope(ctx, command="modelo.audit.show", result=result, lines=lines)


def audit_check(
    ctx: typer.Context,
    bundle_id: str,
) -> None:
    """Re-verify the evidence bundle's integrity without mutating state."""
    bucket_id = active_bucket_id_or_refuse()
    report = _evidence_bundle_service().check(bucket_id=bucket_id, bundle_id=bundle_id)
    from ._modelo_payloads import EvidenceBundleCheckFindingPayload, ModeloAuditCheckResult

    result = ModeloAuditCheckResult(
        bundle_id=report.bundle_id,
        verification_state=report.verification_state,
        completeness_ratio=report.completeness_ratio,
        findings=[
            EvidenceBundleCheckFindingPayload(
                check=f.check.value,
                passed=f.passed,
                detail=f.detail,
            )
            for f in report.findings
        ],
    )
    lines = [
        f"bucket\t{bucket_id}",
        f"bundle_id\t{report.bundle_id}",
        f"verification_state\t{report.verification_state.value}",
        f"completeness_ratio\t{report.completeness_ratio}",
        f"findings\t{len(report.findings)}",
    ]
    emit_envelope(ctx, command="modelo.audit.check", result=result, lines=lines)


def audit_export(
    ctx: typer.Context,
    bundle_id: str,
    output: Path,
    force_incomplete: bool = False,
) -> None:
    """Write the evidence bundle as a ZIP archive to ``--output``."""
    bucket_id = active_bucket_id_or_refuse()
    service = _evidence_bundle_service()
    output_path = service.export(
        bucket_id=bucket_id,
        bundle_id=bundle_id,
        output_path=output,
        force_incomplete=force_incomplete,
    )
    bundle = service.show(bucket_id=bucket_id, bundle_id=bundle_id)
    from ._modelo_payloads import ModeloAuditExportResult

    result = ModeloAuditExportResult(
        bucket_id=bucket_id,
        bundle_id=bundle.bundle_id,
        output=str(output_path),
        verification_state=bundle.verification_state,
        records=len(bundle.records),
    )
    lines = [
        f"bucket\t{bucket_id}",
        f"bundle_id\t{bundle.bundle_id}",
        f"output\t{output_path}",
        f"verification_state\t{bundle.verification_state.value}",
    ]
    emit_envelope(ctx, command="modelo.audit.export", result=result, lines=lines)


__all__ = ["audit_check", "audit_export", "audit_view"]
