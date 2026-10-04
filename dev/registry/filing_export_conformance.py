"""Run a public conformance vector through the canonical filing writer."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Protocol, runtime_checkable

from dev._paths import prepare_temporary_directory

from pydantic import BaseModel

from cadrumo.application.filing.export_verification import (
    DeclaracionExportResult,
)
from cadrumo.application.filing.runtime import (
    RegistrySchemaAccessor,
)
from cadrumo.core.models import STRICT_FROZEN_CONFIG
from cadrumo.core.storage_environment import prepare_temporary_directory

from .filing_export_proof_contracts import (
    FilingExportConformanceReceipt,
    FilingExportConformanceRenderInputs,
    FilingExportConformanceVectorEvidence,
    FilingExportProofCoordinate,
)
from .filing_export_writer import _export


class FilingExportConformanceRequest(BaseModel):
    """Public development request carrying no filing values or producer identity."""

    model_config = STRICT_FROZEN_CONFIG

    coordinate: FilingExportProofCoordinate


@runtime_checkable
class FilingExportConformanceAuthority(Protocol):
    """Official-layout authority that adjudicates one non-sensitive render."""

    @property
    def authority_id(self) -> str:
        """Return the conformance authority's stable identity."""
        ...

    def resolve_conformance_vector(
        self, request: FilingExportConformanceRequest
    ) -> FilingExportConformanceVectorEvidence | None:
        """Resolve the public vector evidence for one requested coordinate."""
        ...

    def schema_provider_for_conformance(
        self, evidence: FilingExportConformanceVectorEvidence
    ) -> RegistrySchemaAccessor:
        """Provide canonical registry schema access for the vector."""
        ...

    def materialize_conformance_inputs(
        self, evidence: FilingExportConformanceVectorEvidence
    ) -> FilingExportConformanceRenderInputs:
        """Build transient writer inputs from public vector evidence."""
        ...

    def verify_conformance(
        self,
        *,
        request: FilingExportConformanceRequest,
        evidence: FilingExportConformanceVectorEvidence,
        export_result: DeclaracionExportResult,
        payload: bytes,
    ) -> FilingExportConformanceReceipt:
        """Verify emitted bytes and return an authority-bound receipt."""
        ...


_CONFORMANCE_AUTHORITY_ID = "dev.registry.filing-export-conformance"


def prove_export_conformance(
    request: FilingExportConformanceRequest,
    *,
    authority: FilingExportConformanceAuthority,
) -> FilingExportConformanceReceipt:
    """Resolve and run a development conformance vector through the canonical writer."""
    evidence = authority.resolve_conformance_vector(request)
    if evidence is None:
        raise ValueError("conformance authority has no mechanism vector for the requested coordinate")
    if evidence.coordinate != request.coordinate or evidence.authority_id != authority.authority_id:
        raise ValueError("conformance authority returned evidence for another request")
    schema_provider = authority.schema_provider_for_conformance(evidence)
    render_inputs = authority.materialize_conformance_inputs(evidence)
    if (
        render_inputs.coordinate != evidence.coordinate
        or render_inputs.filing_year != evidence.filing_year
        or render_inputs.period != evidence.period
    ):
        raise ValueError("conformance vector builder returned inputs for another coordinate")
    with TemporaryDirectory(prefix="cadrumo-export-conformance-", dir=prepare_temporary_directory()) as temporary:
        output_path = Path(temporary) / "proof-output"
        result = _export(render_inputs, output_path=output_path, schema_provider=schema_provider)
        payload = output_path.read_bytes()
        receipt = authority.verify_conformance(
            request=request,
            evidence=evidence,
            export_result=result,
            payload=payload,
        )
        _require_conformance_receipt(request, evidence, result, receipt, authority_id=authority.authority_id)
    return receipt


def _require_conformance_receipt(
    request: FilingExportConformanceRequest,
    evidence: FilingExportConformanceVectorEvidence,
    result: DeclaracionExportResult,
    receipt: FilingExportConformanceReceipt,
    *,
    authority_id: str,
) -> None:
    if (
        receipt.coordinate != request.coordinate
        or receipt.provenance != evidence.provenance
        or receipt.authority_id != authority_id
    ):
        raise ValueError("conformance authority receipt conflicts with the requested official identity")
    if result.modelo != request.coordinate.modelo or result.period != evidence.period:
        raise ValueError("canonical export receipt conflicts with the conformance coordinate")
    if receipt.emitted_bytes != result.byte_size:
        raise ValueError("conformance extent must match the canonical export receipt")
