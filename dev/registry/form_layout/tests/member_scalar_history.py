"""Reconstruct the prior scalar presentation for publication-boundary tests."""

from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_form_layouts import FormFieldBlock, FormRepeatingGroupBlock


def scalar_member_history(revision: ModeloRevision) -> ModeloRevision:
    """Use current authored cells/headings while removing only record repetition."""
    form = revision.form_layouts[0]
    pages = []
    for page in form.pages:
        sections = []
        for section in page.sections:
            blocks = []
            for block in section.blocks:
                if not isinstance(block, FormRepeatingGroupBlock) or not block.grids:
                    blocks.append(block)
                    continue
                gridded = {cell.casilla_id for grid in block.grids for row in grid.rows for cell in row.cells}
                blocks.extend(
                    FormFieldBlock(id=column.key, casilla_id=column.casilla_id)
                    for column in block.columns
                    if column.casilla_id not in gridded
                )
                blocks.extend(block.grids)
            sections.append(section.model_copy(update={"blocks": tuple(blocks)}))
        pages.append(page.model_copy(update={"sections": tuple(sections)}))
    return revision.model_copy(update={"form_layouts": (form.model_copy(update={"pages": tuple(pages)}),)})
