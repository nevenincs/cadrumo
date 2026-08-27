"""Typed direct materialisation of one source row into one casilla row."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from ...core import STRICT_FROZEN_HIDDEN_INPUT_CONFIG, CasillaId
from ._row_source_identity import RowSourceIdentity
from .registry.ids import BindingId, RevisionId

RowCasillaKey = tuple[CasillaId, int]


class DirectRowMaterializationProvenance(BaseModel):
    """Registry-owned proof that one binding row directly supplied a casilla row."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    source_binding_id: BindingId
    source_row_index: int = Field(ge=1)
    source_identity: RowSourceIdentity = Field(repr=False)
    materialization_rule_id: BindingId
    materialization_rule_version: RevisionId

    @model_validator(mode="after")
    def _rule_is_the_source_binding(self) -> DirectRowMaterializationProvenance:
        if self.materialization_rule_id != self.source_binding_id:
            raise ValueError("direct row materialization rule must equal its source binding")
        return self


__all__ = ["DirectRowMaterializationProvenance", "RowCasillaKey"]
