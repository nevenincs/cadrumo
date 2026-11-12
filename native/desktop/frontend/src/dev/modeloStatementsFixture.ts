import type { LedgerOutcome } from "../shell/ledger";
import type { ModeloPort, ModeloResult } from "../shell/modelo";
import type {
  ModeloEditOperatorInputV2,
  ModeloEditPreflightProjectionV1,
} from "../shell/modeloContract/modeloEdit";
import type {
  ModeloFormCarryAttestation,
  ModeloWorkbenchFormProjectionV1,
} from "../shell/modeloContract/modeloWorkForm";
import { placedFields } from "../components/modelo/form/session";

// What the Modelo statement stories need that no seeded envelope holds yet,
// made from the seeded Renta reads and said here as made: a form serving
// more than one statement at once, boxes a statement was applied to, a box
// whose removal the baseline does not admit, and a check of the staged
// statements answered as checked or as refused. Each Renta read serves one
// statement; none was read after a statement was applied, and no check of a
// statement was read. The words are the reads' own; a refusal's words are
// the story's, given to it, never written here. Design and test evidence
// only: nothing here is a taxpayer's.

/** Adds to `envelope` every statement `other` serves that it does not, in
 * the order `other` serves them, after its own: both are reads of the same
 * declaration for the same synthetic filer, so the boxes are the same. */
export function withStatementsOf(
  envelope: ModeloWorkbenchFormProjectionV1,
  other: ModeloWorkbenchFormProjectionV1,
): void {
  const form = envelope.form.form;
  const families = new Set(form.carry_attestations.map((each) => each.family));
  form.carry_attestations = [
    ...form.carry_attestations,
    ...other.form.form.carry_attestations.filter(
      (each) => !families.has(each.family),
    ),
  ];
}

/** `envelope` as if `statement` had been applied: every box it names reads
 * as the filer's, stated by it and offering its value to be taken out, and
 * the form serves it no more. No read serves the words of a stated box yet,
 * so the statement's served effect words stand in for them. */
export function withStated(
  envelope: ModeloWorkbenchFormProjectionV1,
  statement: ModeloFormCarryAttestation,
): void {
  const form = envelope.form.form;
  const bindings = new Set<string>(statement.binding_ids);
  for (const { field } of placedFields(form)) {
    const address = field.edit_address;
    if (address.kind !== "binding" || !bindings.has(address.binding_id))
      continue;
    field.stated_absent = statement.family;
    field.origin = "entered";
    field.origin_words = statement.effect_words;
    field.filers_own = true;
    field.clearable = true;
    field.standing = "done";
  }
  form.carry_attestations = form.carry_attestations.filter(
    (each) => each.family !== statement.family,
  );
}

/** `envelope` with the baseline admitting no removal of the value at
 * `bindingId`. */
export function withoutRemoval(
  envelope: ModeloWorkbenchFormProjectionV1,
  bindingId: string,
): void {
  for (const entry of envelope.admitted_baseline?.permitted_surface ?? [])
    if (
      entry.kind === "writable_binding_override" &&
      entry.binding_id === bindingId
    )
      entry.allowed_intents = entry.allowed_intents.filter(
        (intent) => intent !== "remove_override",
      );
}

/** How the stories' check of the staged edits is answered: checked with
 * nothing found, or refused in `words`. */
export type StatementCheck =
  { kind: "checked" } | { kind: "refused"; words: string };

/** `port` with every check of staged edits answered as `check` says, on the
 * baseline the check was sent on; every other call goes to `port`. */
export function checkingStatements(
  port: ModeloPort,
  check: StatementCheck,
): ModeloPort {
  let operations = 0;
  return {
    ...port,
    async edit(definition, body) {
      if (definition !== "modelo.edit.preflight")
        return port.edit(definition, body);
      const input = JSON.parse(
        new TextDecoder().decode(body),
      ) as ModeloEditOperatorInputV2;
      body.fill(0);
      const baseline = input.submission.baseline;
      operations += 1;
      const result: ModeloEditPreflightProjectionV1 = {
        result_version: 1,
        profile_id: "statement-story",
        work_unit_id: baseline.work_unit_id,
        outcome:
          check.kind === "checked"
            ? {
                outcome: "evaluated",
                baseline_id: baseline.baseline_id,
                findings: [],
              }
            : {
                outcome: "refused",
                refusal: {
                  kind: "domain",
                  edit_contract_version: 1,
                  code: "disallowed_intent",
                  address: null,
                  facts: [],
                  evidence: [],
                  responsible_owner: "modelo.edit",
                  reconsideration_condition: "",
                  recovery_action: null,
                },
              },
        parsed: [],
        findings: [],
        operator_entries_unknown: false,
        refusal_words: check.kind === "refused" ? check.words : null,
        rebase: [],
      };
      return {
        kind: "settled",
        operation_id: `statement-check-${operations}`,
        revision: 1,
        result,
      } as LedgerOutcome<ModeloResult<typeof definition>>;
    },
  };
}
