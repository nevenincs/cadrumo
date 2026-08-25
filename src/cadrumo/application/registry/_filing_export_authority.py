"""Verified generation and emission proof for filing-export closure.

The registry loader deliberately ignores generator provenance.  Filing closure
therefore consumes a separate authority result: the development generator must
have verified its canonical manifest against the current semantic map and render
profile, and the production filing writer must have emitted and checked bytes.
This module carries that result without importing development tooling into the
application package or treating a layout declaration as emission evidence.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Annotated, ClassVar, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG
from ...domain.calculations.registry.ids import (
    ExportLayoutId,
    ModeloId,
    RevisionId,
)

__all__ = [
    "FilingExportEmissionProof",
    "FilingExportGenerationProof",
    "FilingExportProof",
    "FilingExportProofAuthority",
    "FilingExportProofConflictError",
    "GeneratedExportFileDigest",
]

_Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
_Locator = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1_500)]


class _ProofModel(BaseModel):
    """Strict immutable base for export proof records."""

    model_config = STRICT_FROZEN_CONFIG


class GeneratedExportFileDigest(_ProofModel):
    """One generated fragment rehashed by the canonical manifest verifier."""

    relative_path: str = Field(min_length=1, max_length=255)
    sha256: _Sha256

    @field_validator("relative_path")
    @classmethod
    def _require_safe_relative_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if (
            "\\" in value
            or path.is_absolute()
            or value.startswith("/")
            or any(part in {"", ".", ".."} for part in value.split("/"))
        ):
            raise ValueError("generated export proof paths must be safe relative POSIX paths")
        return value


class FilingExportGenerationProof(_ProofModel):
    """Canonical generator-verifier result for one exact revision layout set."""

    authority: Literal["dev.registry.pipeline.verify_export_fragment_provenance_manifest"]
    manifest_locator: _Locator
    manifest_sha256: _Sha256
    semantic_map_sha256: _Sha256
    render_profile_sha256: _Sha256
    loader_semantic_sha256: _Sha256
    output_files: tuple[GeneratedExportFileDigest, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _require_exact_output_digest_set(self) -> FilingExportGenerationProof:
        paths = tuple(item.relative_path for item in self.output_files)
        if paths != tuple(sorted(paths)):
            raise ValueError("generated export proof files must be sorted by relative path")
        if len(paths) != len(set(paths)):
            raise ValueError("generated export proof files must be unique")
        if not any(path.endswith(".toml") for path in paths):
            raise ValueError("generated export proof requires at least one emitted TOML fragment")
        return self


class FilingExportEmissionProof(_ProofModel):
    """Successful production-writer result checked at official byte offsets."""

    authority: Literal["cadrumo.application.filing.export_draft"]
    evidence_locator: _Locator
    payload_sha256: _Sha256
    emitted_bytes: int = Field(gt=0)
    checked_official_offsets: int = Field(gt=0)


class FilingExportProof(_ProofModel):
    """Complete generation-and-emission proof for one registry revision."""

    modelo: ModeloId
    revision: RevisionId
    layout_ids: tuple[ExportLayoutId, ...] = Field(min_length=1)
    generation: FilingExportGenerationProof
    emission: FilingExportEmissionProof

    @model_validator(mode="after")
    def _require_unique_layouts(self) -> FilingExportProof:
        if len(self.layout_ids) != len(set(self.layout_ids)):
            raise ValueError("filing export proof layout identities must be unique")
        return self


class FilingExportProofConflictError(ValueError):
    """Live proof coordinate conflicts with the composing registry snapshot."""

    __bare_base_rationale__: ClassVar[str] = (
        "internal-filing-export-proof-conflict-carrier: coverage catches this by name and converts it "
        "into a typed _LayoutEvidenceFailure value rather than raising to an operator"
    )


@runtime_checkable
class FilingExportProofAuthority(Protocol):
    """Port supplying independently verified generation and emitted-byte proof."""

    def proof_for(
        self,
        *,
        modelo: ModeloId,
        revision: RevisionId,
        layout_ids: tuple[ExportLayoutId, ...],
    ) -> FilingExportProof | None:
        """Return exact proof only when both canonical verification stages passed."""
