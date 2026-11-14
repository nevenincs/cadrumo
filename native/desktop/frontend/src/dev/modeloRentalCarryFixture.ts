import type {
  ModeloEditApplyPublicResultV1,
  ModeloEditOperatorInputV2,
  ModeloEditPreflightProjectionV1,
} from "../shell/modeloContract/modeloEdit";
import type {
  ModeloFormCarryAttestation,
  ModeloWorkbenchFormProjectionV1,
} from "../shell/modeloContract/modeloWorkForm";

// What the rental-carry statement scenario and story need that no stored read
// holds yet: a form serving the statement of a family stated row by row, one
// entry per property, after its form-wide entries. The application serves
// these entries from a calculation of a Modelo 100 over let properties, which
// no stored envelope was read from; the entries here are made, with
// placeholder words in the shape the application serves, and their checks are
// answered as checked. Design and test evidence only: nothing here is a
// taxpayer's, and the window renders only what an entry says.

/** One property's entry as the application serves it. */
export type RentalRow = {
  identity: string;
  words: string;
  bindings: readonly string[];
};

export const RENTAL_ROWS: readonly RentalRow[] = [
  {
    identity: "‹row identity A›",
    words: "‹row words A›",
    bindings: ["‹carry column 1›", "‹carry column 2›"],
  },
  {
    identity: "‹row identity B›",
    words: "‹row words B›",
    bindings: ["‹carry column 1›"],
  },
];

/** The family a row entry is made for, and the words its entries share. */
const FAMILY = "renta_capital_inmobiliario_gastos_pendientes";
const ACTION = "‹row statement action›";
const STATEMENT = "‹row statement›";
const EFFECT = "‹row statement effect›";

const entryOf = (row: RentalRow): ModeloFormCarryAttestation => ({
  family: FAMILY,
  binding_ids: [...row.bindings],
  row_identity: row.identity,
  row_words: row.words,
  action_words: ACTION,
  statement_words: STATEMENT,
  effect_words: EFFECT,
});

/** `envelope` with one entry per row added after the entries it serves. */
export function withRentalRows(
  envelope: ModeloWorkbenchFormProjectionV1,
  rows: readonly RentalRow[] = RENTAL_ROWS,
): void {
  const form = envelope.form.form;
  form.carry_attestations = [...form.carry_attestations, ...rows.map(entryOf)];
}

/** The binding intents a body carries, as one line a scenario reads back. */
export function intentsLine(
  definition: string,
  input: ModeloEditOperatorInputV2,
): string {
  const intents = (input.submission.binding_intents ?? []).map((intent) => ({
    kind: intent.kind,
    address: intent.address,
  }));
  return `modelo edit body ${definition} ${JSON.stringify(intents)}`;
}

/** The answer to a check or an apply of staged statements: checked with
 * nothing found, or applied. */
export function answeredRentalCarry(
  definition: string,
  input: ModeloEditOperatorInputV2,
): ModeloEditPreflightProjectionV1 | ModeloEditApplyPublicResultV1 {
  const baseline = input.submission.baseline;
  if (definition !== "modelo.edit.preflight")
    return {
      result_version: 1,
      receipt_id: "rental-carry-receipt",
      calculation_revision_id: baseline.current_calculation_revision_id,
    };
  return {
    result_version: 1,
    profile_id: "rental-carry",
    work_unit_id: baseline.work_unit_id,
    outcome: {
      outcome: "evaluated",
      baseline_id: baseline.baseline_id,
      findings: [],
    },
    parsed: [],
    findings: [],
    operator_entries_unknown: false,
    refusal_words: null,
    rebase: [],
  };
}
