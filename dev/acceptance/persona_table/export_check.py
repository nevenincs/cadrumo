"""The table's checks of a written fichero: its character rules and its stated casilla values read back.

The collector (``sweep``) and the CLI column run these on the file an export wrote, so both report the same export
stage. This module has no side effect at import: it reads no authority until a function of it is called.
"""

from __future__ import annotations

from pathlib import Path

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.errors import RegistryError
from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition
from cadrumo.domain.filing.errors import ModeloBuilderError
from cadrumo.tests.personas import ExpectedValue

from .export_readback import read_fields, readback_mismatches, readback_reason, unreadable_reason
from .export_text import check_export_text, violation_reason
from .roles import edition_identities
from .rows import PlannedRow


def export_layout(operation: PinnedAuthorityOperation, plan: PlannedRow) -> ExportLayoutDefinition:
    """The fixed-width layout of the revision the law selects for the planned return."""
    revision = operation.revision_for_context(plan.modelo, filing_year=plan.year, period=plan.period)
    return operation.revision_with_export_layouts(plan.modelo, revision.id).export_layouts[0]


def export_readback_reason(plan: PlannedRow, values: list[ExpectedValue], output: Path) -> str:
    """The stated casilla values the written fichero carries with another value, or empty when it agrees.

    A file the registry parser cannot read is itself an export defect, reported as the reason.
    """
    casillas = edition_identities(plan.modelo, plan.year, plan.period)
    with bundled_indexed_authority().operation() as operation:
        layout = export_layout(operation, plan)
        try:
            parsed = read_fields(
                layout,
                output.read_bytes(),
                modelo=plan.modelo,
                year=plan.year,
                period=plan.period,
                operation=operation,
            )
        except (RegistryError, ModeloBuilderError) as error:
            return unreadable_reason(error)
    return readback_reason(readback_mismatches(values, casillas, plan.unchecked, parsed))


def export_text_reason(plan: PlannedRow, output: Path) -> str:
    """The first character-rule violation of the written fichero against its design, or empty when clean."""
    with bundled_indexed_authority().operation() as operation:
        layout = export_layout(operation, plan)
        return violation_reason(check_export_text(layout, output.read_bytes()))


def export_reason(plan: PlannedRow, values: list[ExpectedValue], output: Path) -> str:
    """The first defect of the written fichero, the text check before the readback, or empty when both are clean."""
    return export_text_reason(plan, output) or export_readback_reason(plan, values, output)
