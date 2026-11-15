// The Export and record view and the header rest on a small part of the whole
// form read: the header's result, latest file and export hold, the recorded
// filing, the filed flag, the edit closure, the journey, the rules-incomplete
// flag and the next step, the calculation and verification the offer names,
// the export offer and the receipt. After an export, a local filing or a
// receipt the application serves exactly those fields as one read of their
// own, a fraction of the whole form's time. This puts them into the form the
// window already shows, field for field under the same names, and leaves
// every other part of that form as the last whole read stated it. Nothing is
// derived here.

import type { ModeloResult } from "../../../shell/modelo";
import type { ModeloWorkbenchFormProjectionV1 } from "../../../shell/modeloContract/modeloWorkForm";

export type FilingState = ModeloResult<"modelo.work.filing_state">;

/** Whether `state` answers for the declaration `envelope` shows. */
export function answersFor(
  envelope: ModeloWorkbenchFormProjectionV1,
  state: FilingState,
): boolean {
  return (
    state.work_unit_id === envelope.work_unit_id &&
    state.profile_id === envelope.profile_id
  );
}

/** `envelope` with the parts the filing state serves taken from it. */
export function withFilingState(
  envelope: ModeloWorkbenchFormProjectionV1,
  state: FilingState,
): ModeloWorkbenchFormProjectionV1 {
  return {
    ...envelope,
    form: {
      ...envelope.form,
      filed: state.filed,
      journey: state.journey,
      form: {
        ...envelope.form.form,
        filing: state.filing,
        edit_closure: state.edit_closure,
      },
    },
    rules_incomplete: state.rules_incomplete,
    next_step: state.next_step,
    header: {
      ...envelope.header,
      result: state.header.result,
      file: state.header.file,
      export_hold: state.header.export_hold,
    },
    calculation_revision_id: state.calculation_revision_id,
    verification_report_id: state.verification_report_id,
    export_offer: state.export_offer,
    receipt: state.receipt,
  };
}
