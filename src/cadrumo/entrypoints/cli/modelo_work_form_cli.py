"""Behavior for the command that prints a declaration's saved repeating records.

A repeating record (a let property, a descendant, an operator of a summary
declaration) is stored per row, so the calculation's casilla values cannot show
it. This command reads the declaration's form through the same registered read
the workbench and the window use and prints each saved record the form serves,
with its row index, the casilla each value fills and the typed value. Nothing
is assembled here: the blocks, rows, columns and values are the served form's.

Text output, one line per item:

- ``record<TAB><block id><TAB><row index><TAB><casilla id><TAB><value>`` for a value in a casilla column;
- ``record_column<TAB><block id><TAB><row index><TAB><column key><TAB><value>`` for a column no casilla owns;
- ``block<TAB><block id><TAB>known<TAB><record count>`` before a block whose records the form reads;
- ``block<TAB><block id><TAB>unknown<TAB><words>`` for a block whose records the form cannot read, never shown
  as empty.

A cell the form serves empty prints no line. The value is the typed wire value, as ``casilla`` lines print it.
"""

from __future__ import annotations

from uuid import UUID

import typer

from cadrumo_client.commands.output import activate_subcommand_output_language
from cadrumo_client.commands.profile_binding import require_profile_client

from ...application.modelo.workbench_projection import (
    ModeloWorkbenchFormProjectionV1,
    PublicModeloFormRepeatingBlock,
    PublicModeloFormRepeatingRow,
)
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import output_language as active_output_language
from ...core.i18n.render import tr
from .common import emit_envelope
from .modelo_cli_support import resolve_explicit_or_active_bucket_id
from .modelo_work_form_payloads import (
    WorkFormRecord,
    WorkFormRecordBlock,
    WorkFormRecordColumn,
    WorkFormRecordValue,
    WorkFormResult,
)
from .operation_modelo_carry_attestation import read_modelo_work_form_for_cli

_COMMAND = "modelo.work.form"
#: The words the workbench and the window show for a block whose records are not known.
_ROWS_UNKNOWN_LOCALE_KEY = "workspace.modelo.grid.records_unknown"


def _values(block: PublicModeloFormRepeatingBlock, row: PublicModeloFormRepeatingRow) -> list[WorkFormRecordValue]:
    texts = row.value_texts or (None,) * len(row.values)
    return [
        WorkFormRecordValue(
            column_key=column.key, casilla_id=casilla_id, kind=value.kind, value=value.text, value_text=text
        )
        for column, casilla_id, value, text in zip(
            block.columns, block.column_casilla_ids, row.values, texts, strict=True
        )
        if value is not None and value.kind != "null"
    ]


def _record_block(page_id: str, section_id: str, block: PublicModeloFormRepeatingBlock) -> WorkFormRecordBlock:
    return WorkFormRecordBlock(
        block_id=block.id,
        page_id=page_id,
        section_id=section_id,
        columns=[
            WorkFormRecordColumn(key=column.key, heading=column.heading.text, casilla_id=casilla_id, data_type=kind)
            for column, casilla_id, kind in zip(
                block.columns, block.column_casilla_ids, block.column_data_types, strict=True
            )
        ],
        min_rows=block.min_rows,
        max_rows=block.max_rows,
        rows_known=block.rows_known,
        rows_unknown_words=None if block.rows_known else tr(_ROWS_UNKNOWN_LOCALE_KEY),
        records=[WorkFormRecord(index=row.index, values=_values(block, row)) for row in block.rows],
    )


def work_form_result(bucket_id: str, projection: ModeloWorkbenchFormProjectionV1) -> WorkFormResult:
    """The served form's repeating blocks, in the form's page and section order, with their saved records."""
    form = projection.form.form
    return WorkFormResult(
        bucket_id=bucket_id,
        work_unit_id=form.work_unit_id,
        modelo=form.modelo,
        filing_year=form.filing_year,
        period=form.period.code,
        registry_revision_id=form.registry_revision_id,
        calculation_revision_id=form.calculation_revision_id,
        blocks=[
            _record_block(page.id, section.id, block)
            for page in form.pages
            for section in page.sections
            for block in section.blocks
            if isinstance(block, PublicModeloFormRepeatingBlock)
        ],
    )


def work_form_lines(result: WorkFormResult) -> list[str]:
    """The text lines: the declaration, then each block and one line per value of each of its records."""
    lines = [
        f"operation\t{_COMMAND}",
        f"work_unit_id\t{result.work_unit_id}",
        f"modelo\t{result.modelo}",
        f"filing_year\t{result.filing_year}",
        f"period\t{result.period}",
        f"registry_revision_id\t{result.registry_revision_id}",
        f"calculation_revision_id\t{result.calculation_revision_id or ''}",
    ]
    for block in result.blocks:
        if not block.rows_known:
            lines.append(f"block\t{block.block_id}\tunknown\t{block.rows_unknown_words}")
            continue
        lines.append(f"block\t{block.block_id}\tknown\t{len(block.records)}")
        for record in block.records:
            lines.extend(
                f"record\t{block.block_id}\t{record.index}\t{value.casilla_id}\t{value.value}"
                if value.casilla_id is not None
                else f"record_column\t{block.block_id}\t{record.index}\t{value.column_key}\t{value.value}"
                for value in record.values
            )
    return lines


def work_form(
    ctx: typer.Context,
    work_unit_id: str,
    output_language: OutputLanguage | None = None,
) -> None:
    """Print the saved repeating records of a declaration's form, with row index, casilla and typed value."""
    activate_subcommand_output_language(ctx, output_language)
    bucket_id = resolve_explicit_or_active_bucket_id(None)
    client = require_profile_client(ctx, expected_profile_id=UUID(bucket_id))
    language = OutputLanguage(active_output_language())
    projection = read_modelo_work_form_for_cli(client, work_unit_id=work_unit_id.strip(), language=language)
    result = work_form_result(bucket_id, projection)
    emit_envelope(ctx, command=_COMMAND, result=result, lines=work_form_lines(result))


__all__ = ["work_form", "work_form_lines", "work_form_result"]
