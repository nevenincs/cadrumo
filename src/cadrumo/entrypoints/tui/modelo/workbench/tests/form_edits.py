"""Change named boxes of a synthetic form wherever its layout holds them.

Tests of the workbench's views build the states they need (an assumed value, a
source that found nothing, a value fixed by the form) from the shared fixture
by updating the boxes in place, so pages, grids and working figures keep their
shape.
"""

from __future__ import annotations

from collections.abc import Mapping

from ......application.modelo.work_form_models import (
    ModeloFormBlock,
    ModeloFormField,
    ModeloFormFieldBlock,
    ModeloFormGridBlock,
    ModeloWorkForm,
)


def replace_fields(form: ModeloWorkForm, changes: Mapping[str, Mapping[str, object]]) -> ModeloWorkForm:
    """Return ``form`` with each named box's field updated by its mapping of changes."""

    def changed(field: ModeloFormField) -> ModeloFormField:
        update = changes.get(field.box or "")
        return field if update is None else field.model_copy(update=dict(update))

    def block_changed(block: ModeloFormBlock) -> ModeloFormBlock:
        if isinstance(block, ModeloFormFieldBlock):
            return block.model_copy(update={"field": changed(block.field)})
        if isinstance(block, ModeloFormGridBlock):
            rows = tuple(
                row.model_copy(
                    update={
                        "cells": tuple(
                            cell if cell.field is None else cell.model_copy(update={"field": changed(cell.field)})
                            for cell in row.cells
                        )
                    }
                )
                for row in block.rows
            )
            return block.model_copy(update={"rows": rows})
        return block

    pages = tuple(
        page.model_copy(
            update={
                "sections": tuple(
                    section.model_copy(update={"blocks": tuple(block_changed(block) for block in section.blocks)})
                    for section in page.sections
                )
            }
        )
        for page in form.pages
    )
    working = tuple(changed(field) for field in form.working_figures)
    return form.model_copy(update={"pages": pages, "working_figures": working})


__all__ = ["replace_fields"]
