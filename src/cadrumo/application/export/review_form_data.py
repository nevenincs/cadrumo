"""Frozen form values and geometry projected solely from a saved calculation."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, model_validator

from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.calculations.registry.form_context import resolve_form_context_field
from ...domain.calculations.registry.schema_form_layouts import FormContextFieldBlock, FormRepeatingGroupBlock
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.calculation_revision_rendering import CalculationRenderingSnapshot
from ..modelo.work_form_context_values import form_context_value
from ..modelo.work_form_models import ModeloFormRepeatingRow, ModeloFormScalar
from ..modelo.work_form_records import saved_form_records


class ReviewFormValue(BaseModel):
    """One exact saved scalar, binding or context value; unknown remains None."""

    model_config = STRICT_FROZEN_CONFIG
    id: str
    value: ModeloFormScalar


class ReviewFormRecords(BaseModel):
    """Captured closed repeating records for one declared form block."""

    model_config = STRICT_FROZEN_CONFIG
    block_id: str
    known: bool
    rows: tuple[ModeloFormRepeatingRow, ...]


class ReviewSavedForm(BaseModel):
    """All inputs required for a saved-value form; no renderer reads repositories."""

    model_config = STRICT_FROZEN_CONFIG
    rendering: CalculationRenderingSnapshot
    scalars: tuple[ReviewFormValue, ...]
    bindings: tuple[ReviewFormValue, ...]
    contexts: tuple[ReviewFormValue, ...]
    records: tuple[ReviewFormRecords, ...]

    @model_validator(mode="after")
    def _unique_channels(self) -> Self:
        for channel in (self.scalars, self.bindings, self.contexts):
            if len({item.id for item in channel}) != len(channel):
                raise ValueError("saved form channel contains duplicate identities")
        if len({item.block_id for item in self.records}) != len(self.records):
            raise ValueError("saved form contains duplicate record blocks")
        return self


def capture_review_form(revision: CalculationRevision) -> ReviewSavedForm | None:
    """Project the original saved registry and channels without current-source resolution."""
    rendering = revision.rendering_snapshot
    if rendering is None or len(rendering.registry_snapshot.revision.form_layouts) != 1:
        return None
    snapshot = rendering.registry_snapshot
    blocks = tuple(
        block
        for page in snapshot.revision.form_layouts[0].pages
        for section in page.sections
        for block in section.blocks
    )
    values = {
        **revision.input_values_by_casilla_id,
        **{observation.casilla_id: observation.value for observation in revision.observations},
        **revision.casilla_values,
    }

    def context_value(block: FormContextFieldBlock) -> ModeloFormScalar:
        field = resolve_form_context_field(snapshot.revision, block)
        if field.binding is not None:
            saved = revision.binding_overrides.get(field.binding)
            if saved is not None:
                return saved
            owners = tuple(casilla.id for casilla in snapshot.revision.casillas if casilla.binding == field.binding)
            return values.get(owners[0]) if len(owners) == 1 else None
        return form_context_value(snapshot, block, revision=revision)

    contexts = tuple(
        ReviewFormValue(id=block.id, value=context_value(block))
        for block in blocks
        if isinstance(block, FormContextFieldBlock)
    )
    records = tuple(
        ReviewFormRecords(block_id=block.id, known=known, rows=rows)
        for block in blocks
        if isinstance(block, FormRepeatingGroupBlock)
        for known, rows in (
            saved_form_records(
                snapshot=snapshot,
                revision=revision,
                block=block,
                column_casillas=tuple(column.casilla_id for column in block.columns),
            ),
        )
    )
    return ReviewSavedForm(
        rendering=rendering,
        scalars=tuple(ReviewFormValue(id=key, value=value) for key, value in sorted(values.items())),
        bindings=tuple(
            ReviewFormValue(id=key, value=value) for key, value in sorted(revision.binding_overrides.items())
        ),
        contexts=contexts,
        records=records,
    )
