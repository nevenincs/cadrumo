"""The text values of a return's saved repeating records, read from the live work form of the backend run.

The calculation's public result holds numbers, while a casilla a repeating-row group stores per row can hold text (a
descendant's NIF, a payee's NIF). The CLI prints such a value redacted, so the surface comparison has to know whether
the backend holds a value for that casilla. The backend reads the same ``modelo.work.form`` operation the CLI prints,
takes the same single-value rule as the CLI column (:func:`.cli_column.row_form.text_figures`), and keeps the plain
text apart from the numeric figures, which every surface is held to show.
"""

from __future__ import annotations

from cadrumo.application.modelo.workbench_operations import (
    MODELO_WORK_FORM_OPERATION_DEFINITION_ID,
    ModeloWorkbenchFormRequest,
)
from cadrumo.application.modelo.workbench_projection import ModeloWorkbenchFormProjectionV1
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.entrypoints.cli.modelo_work_form_cli import work_form_result
from cadrumo.entrypoints.cli.modelo_work_form_payloads import WorkFormResult
from cadrumo.entrypoints.tests.persona_operations import run_operation
from cadrumo.entrypoints.tests.persona_world import PersonaMaterialisationError, PersonaWorld

from .cli_column.row_form import FormValue, text_figures


def form_values(result: WorkFormResult) -> tuple[FormValue, ...]:
    """Every value of every saved record of the blocks whose rows are known, as the CLI column reads them."""
    return tuple(
        FormValue(f"{block.block_id}:{record.index}", block.block_id, record.index, value.casilla_id, value.value)
        for block in result.blocks
        if block.rows_known
        for record in block.records
        for value in record.values
        if value.casilla_id is not None
    )


def read_text_figures(world: PersonaWorld, work_unit_id: str) -> tuple[tuple[str, str], ...]:
    """The return's text figures by casilla id, sorted; none when the form cannot be read."""
    try:
        projection = run_operation(
            world,
            MODELO_WORK_FORM_OPERATION_DEFINITION_ID,
            ModeloWorkbenchFormRequest(
                profile_id=world.profile_id, work_unit_id=work_unit_id, output_language=OutputLanguage.EN
            ),
            ModeloWorkbenchFormProjectionV1,
            subject=work_unit_id,
        )
    except PersonaMaterialisationError:
        return ()
    result = work_form_result(str(world.profile_id), projection)
    return tuple(
        sorted((casilla, value) for casilla, value in text_figures(form_values(result)).items() if value.strip())
    )
