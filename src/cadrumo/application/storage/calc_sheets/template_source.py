"""Strict presentation inputs for fictional workbook templates, never filing snapshots."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import BaseModel, model_validator

from ....core.errors.hierarchy import pydantic_validation_boundary
from ....core.frozen_mapping import FROZEN_MAPPING
from ....core.hashing import sha256_hex
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.period import Period
from ....domain.calculations.registry.ids import LegalRefId, ModeloId, SourceRefId
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.schema_references import LegalReference, SourceReference
from .records import SheetAdministrativeFrame


class WorkbookTemplateSource(BaseModel):
    """An exact revision and evidence slice selected by development tooling.

    The illustrative frame describes the example only. This record carries no
    taxpayer data, filing authority, publication identity, or snapshot reference.
    """

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal["fictional_template"] = "fictional_template"
    modelo_id: ModeloId
    revision: ModeloRevision
    preview_frame: Period | SheetAdministrativeFrame
    source_ref: SourceRefId
    legal: Annotated[Mapping[LegalRefId, LegalReference], FROZEN_MAPPING]
    sources: Annotated[Mapping[SourceRefId, SourceReference], FROZEN_MAPPING]

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _evidence_identity(self) -> WorkbookTemplateSource:
        if self.source_ref not in self.sources:
            raise ValueError("template design source is absent from its evidence slice")
        if any(key != value.id for key, value in self.legal.items()):
            raise ValueError("template legal evidence key does not match its identity")
        if any(key != value.id for key, value in self.sources.items()):
            raise ValueError("template source evidence key does not match its identity")
        return self

    @property
    def template_digest(self) -> str:
        """Bind the preview frame, revision content, and selected evidence."""
        return sha256_hex(self.model_dump_json().encode("utf-8"))
