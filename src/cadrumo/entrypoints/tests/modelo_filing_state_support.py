"""The filing state a declaration's full form read states, for comparison with the filing-state read.

Shared test-support module: the filing-state read must state exactly what the
form read states under the same names, so a test selects those fields from a
form read and compares the two results whole.
"""

from __future__ import annotations

from cadrumo.application.modelo.work_form_header import ModeloFormFilingHeader
from cadrumo.application.modelo.workbench_projection import (
    ModeloWorkbenchFormProjectionV1,
    ModeloWorkFilingStateProjectionV1,
)


def filing_state_of_form(form: ModeloWorkbenchFormProjectionV1) -> ModeloWorkFilingStateProjectionV1:
    """The filing state the form read ``form`` states: its own fields, taken under their names."""
    offer = form.export_offer
    if offer is None:
        raise AssertionError("a form read states what exporting offers")
    loaded = form.form.form
    header = form.header
    return ModeloWorkFilingStateProjectionV1(
        result_version=1,
        profile_id=form.profile_id,
        work_unit_id=form.work_unit_id,
        modelo=loaded.modelo,
        period=loaded.period,
        filing=loaded.filing,
        filed=form.form.filed,
        edit_closure=loaded.edit_closure,
        journey=form.form.journey,
        rules_incomplete=form.rules_incomplete,
        next_step=form.next_step,
        header=ModeloFormFilingHeader(result=header.result, file=header.file, export_hold=header.export_hold),
        calculation_revision_id=form.calculation_revision_id,
        verification_report_id=form.verification_report_id,
        export_offer=offer,
        receipt=form.receipt,
    )


__all__ = ["filing_state_of_form"]
