"""Write the canonical filing export for public and secure proof channels."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from cadrumo.application.filing.export import export_draft
from cadrumo.application.filing.export_verification import (
    DeclaracionExportResult,
)
from cadrumo.application.filing.runtime import (
    RegistrySchemaAccessor,
)

from .filing_export_proof_contracts import (
    FilingExportConformanceRenderInputs,
    FilingExportDictionaryValue,
    FilingExportSecureReplayEvidence,
)


def _export(
    proof_input: FilingExportConformanceRenderInputs | FilingExportSecureReplayEvidence,
    *,
    output_path: Path,
    schema_provider: RegistrySchemaAccessor,
) -> DeclaracionExportResult:
    return export_draft(
        proof_input.draft,
        output_path=output_path,
        producer_snapshot=proof_input.producer_snapshot,
        dictionary_values=_dictionary_mapping(proof_input.dictionary_values),
        prior_domiciliation_election=proof_input.prior_domiciliation_election,
        product_software_identity=proof_input.product_software_identity,
        schema_provider=schema_provider,
    )


def _dictionary_mapping(values: tuple[FilingExportDictionaryValue, ...]) -> Mapping[str, object] | None:
    return {item.field_id: item.value for item in values} or None
