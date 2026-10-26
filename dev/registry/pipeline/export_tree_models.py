"""Canonical immutable models for generated export trees and their transport profile."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cadrumo.core.external_constants import LATIN_1_ENCODING
from cadrumo.domain.calculations.registry.fixed_width_codec import (
    ExportEncoding,
)
from cadrumo.domain.calculations.registry.ids import (
    ExportLayoutId,
    ModeloId,
    SourceRefId,
)
from cadrumo.domain.calculations.registry.schema_exports import (
    ExportLayoutDefinition,
)

from .export_fragment_provenance import (
    ExportFieldDerivation,
    ExportFragmentProvenanceManifest,
)
from .export_tree_serialization import require_safe_identifier

_ENCODING_ALIAS_MAP: Final[Mapping[str, str]] = {
    LATIN_1_ENCODING: "iso-8859-1",
    "latin_1": "iso-8859-1",
    "iso-8859-1": "iso-8859-1",
    "iso_8859_1": "iso-8859-1",
    "cp1252": "cp1252",
    "windows-1252": "cp1252",
    "iso-8859-15": "iso-8859-15",
    "iso_8859_15": "iso-8859-15",
    "latin-9": "iso-8859-15",
}


class _StrictModel(BaseModel):
    """Frozen development-tool boundary with no untyped extras."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ExportTreeTransportProfile(_StrictModel):
    """Transport-only settings for one generated export tree."""

    modelo: ModeloId
    design_epoch: str = Field(min_length=1)
    source_ref: SourceRefId
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    layout_id: ExportLayoutId
    format: Literal["fixed_width"]
    encoding: ExportEncoding
    line_ending: Literal["crlf", "lf", "none"]
    serializer_convention: Literal["rtoml-pretty-v1"]

    @model_validator(mode="after")
    def _require_supported_encoding_and_safe_ids(self) -> ExportTreeTransportProfile:
        if self.encoding.casefold() not in _ENCODING_ALIAS_MAP:
            raise ValueError(f"export tree transport profile declares unsupported encoding {self.encoding!r}")
        require_safe_identifier(str(self.layout_id), subject="export layout id")
        return self


class RenderedExportTree(_StrictModel):
    """The complete in-memory layout and materialised output members."""

    layout: ExportLayoutDefinition
    field_derivations: tuple[ExportFieldDerivation, ...] = Field(min_length=1)
    output_files: tuple[str, ...] = Field(min_length=1)
    provenance_manifest: ExportFragmentProvenanceManifest

    @model_validator(mode="after")
    def _require_complete_or_exact_inherited_delta(self) -> RenderedExportTree:
        if len(self.output_files) == 1 and (
            self.output_files != ("0000-export-layout.toml",)
            or self.provenance_manifest.generated_export_inheritance is None
        ):
            raise ValueError("one-file generated export requires the exact attested inheritance delta")
        if len(self.output_files) > 1 and self.provenance_manifest.generated_export_inheritance is not None:
            raise ValueError("inherited export attestation requires one canonical delta fragment")
        return self
