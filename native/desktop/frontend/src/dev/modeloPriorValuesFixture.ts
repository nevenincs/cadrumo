import type { LedgerOutcome } from "../shell/ledger";
import type { ModeloPort, ModeloResult } from "../shell/modelo";
import type {
  ModeloEditOperatorInputV2,
  ModeloEditPreflightProjectionV1,
} from "../shell/modeloContract/modeloEdit";
import type {
  ModeloFormPriorValueWithdrawal,
  ModeloWorkbenchFormProjectionV1,
  PublicModeloFormField,
} from "../shell/modeloContract/modeloWorkForm";
import type { PublicModeloFormPriorValueAttestation } from "../shell/modeloContract/modeloWorkFormPart2";
import { placedFields } from "../components/modelo/form/session";

// What the stories of figures stated for earlier returns need that no seeded
// envelope holds yet: two carries of one family of earlier returns served
// for a statement, stated, or refused because the application holds the
// earlier return, and a check of a typed figure answered as read. The words
// are placeholders in the served shape, never the backend's own; the carries
// are two boxes of a seeded read the baseline already makes writable at a
// binding. Design and test evidence only: nothing here is a taxpayer's.

/** The family the stories' two carries stand in for. */
export const PRIOR_FAMILY = "synthetic-earlier-return";

/** The placeholder words the stories serve. */
export const PRIOR_WORDS = {
  source: "Synthetic earlier return",
  action: "Synthetic: state the earlier figure",
  statement: "Synthetic: you state the figure the earlier return carries.",
  effect: "Synthetic: the box takes the figure you state.",
  origin: "Synthetic: stated by you for the earlier return",
  withdrawAction: "Synthetic: withdraw the stated figures",
  withdrawEffect: "Synthetic: each box holds no stated figure again.",
  refusal: "Synthetic: the earlier return is held, so the box follows it.",
  door: "Synthetic: open the declarations",
} as const;

/** The first two boxes the form draws at a binding the baseline makes
 * writable, once each; the stories' carries. */
function carries(
  envelope: ModeloWorkbenchFormProjectionV1,
): PublicModeloFormField[] {
  const writable = new Set(
    (envelope.admitted_baseline?.permitted_surface ?? []).flatMap((entry) =>
      entry.kind === "writable_binding_override" ? [entry.binding_id] : [],
    ),
  );
  const seen = new Set<string>();
  const found: PublicModeloFormField[] = [];
  for (const { field } of placedFields(envelope.form.form)) {
    const address = field.edit_address;
    if (address.kind !== "binding" || !writable.has(address.binding_id))
      continue;
    if (seen.has(address.binding_id)) continue;
    seen.add(address.binding_id);
    found.push(field);
    if (found.length === 2) return found;
  }
  throw new Error("the read draws fewer than two writable carries");
}

const bindingOf = (field: PublicModeloFormField) =>
  field.edit_address.kind === "binding" ? field.edit_address.binding_id : "";

/** `envelope` with the baseline admitting a stated figure at `bindingId`. */
function admitStatement(
  envelope: ModeloWorkbenchFormProjectionV1,
  bindingId: string,
): void {
  for (const entry of envelope.admitted_baseline?.permitted_surface ?? [])
    if (
      entry.kind === "writable_binding_override" &&
      entry.binding_id === bindingId &&
      !entry.allowed_intents.includes("attest_prior_value")
    )
      entry.allowed_intents = [...entry.allowed_intents, "attest_prior_value"];
}

/** How the stories' carries stand: offered for a statement, stated, or the
 * second refused because its earlier return is held. */
export type PriorShape = "offered" | "stated" | "refused";

/** `envelope` serving its first two writable carries as one family of
 * earlier returns, as `shape` says. */
export function withPriorValues(
  envelope: ModeloWorkbenchFormProjectionV1,
  shape: PriorShape,
): void {
  const boxes = carries(envelope);
  const ids = boxes.map(bindingOf);
  const withdrawal: ModeloFormPriorValueWithdrawal | null =
    shape === "stated"
      ? {
          family_id: PRIOR_FAMILY,
          binding_ids: [...ids].sort(),
          intent: "remove_override",
          action_words: PRIOR_WORDS.withdrawAction,
          effect_words: PRIOR_WORDS.withdrawEffect,
        }
      : null;
  const entries = boxes.map(
    (field, at): PublicModeloFormPriorValueAttestation => {
      const bindingId = ids[at] ?? "";
      const admitted = !(shape === "refused" && at === 1);
      if (admitted) admitStatement(envelope, bindingId);
      if (shape === "stated") {
        field.stated_prior_value = {
          source_words: PRIOR_WORDS.source,
          origin_words: PRIOR_WORDS.origin,
          family_id: PRIOR_FAMILY,
        };
        field.origin = "entered";
        field.origin_words = PRIOR_WORDS.origin;
        field.filers_own = true;
        field.clearable = true;
        field.standing = "done";
      } else if (admitted)
        field.statements = [
          {
            intent: "attest_prior_value",
            binding_id: bindingId,
            action_words: PRIOR_WORDS.action,
            statement_words: PRIOR_WORDS.statement,
            effect_words: PRIOR_WORDS.effect,
            source_words: PRIOR_WORDS.source,
          },
        ];
      return {
        binding_id: bindingId,
        edit_address: { kind: "binding", binding_id: bindingId },
        intent: "attest_prior_value",
        family_id: PRIOR_FAMILY,
        earlier_filings: [],
        source_words: PRIOR_WORDS.source,
        action_words: PRIOR_WORDS.action,
        statement_words: PRIOR_WORDS.statement,
        effect_words: PRIOR_WORDS.effect,
        stated: shape === "stated",
        admitted,
        refusal_reason: admitted ? null : "source_held",
        refusal_words: admitted ? null : PRIOR_WORDS.refusal,
        refusal: admitted
          ? null
          : {
              no_recovery_words: null,
              no_recovery_words_language: null,
              action_words: PRIOR_WORDS.door,
              action_words_language: null,
              target_operation_ids: ["modelo.work.list"],
              failed_condition_id: "synthetic.prior_value.admitted",
              evidence: [],
              action_id: "synthetic.open_declarations",
              argument_bindings: [],
              missing_argument_names: [],
              conditionality: "immediate",
              no_recovery_outcome: null,
              alternative_actions: [],
            },
        withdrawal,
      };
    },
  );
  envelope.form.form.prior_value_attestations = entries;
}

/** `port` with every check that reads a typed entry answered as read: the
 * entry as its own value, with nothing done to it. Every other call goes to
 * `port`. */
export function readingEntries(port: ModeloPort): ModeloPort {
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
      const { baseline, lexemes = [] } = input.submission;
      operations += 1;
      const result: ModeloEditPreflightProjectionV1 = {
        result_version: 1,
        profile_id: "prior-value-story",
        work_unit_id: baseline.work_unit_id,
        outcome: {
          outcome: "evaluated",
          baseline_id: baseline.baseline_id,
          findings: [],
        },
        parsed: lexemes.map((entry) => ({
          address: entry.address,
          value: entry.lexeme,
          normalisations: [],
          refusal: null,
          value_text: entry.lexeme,
          refusal_words: null,
          comparable_value: entry.lexeme,
        })),
        findings: [],
        operator_entries_unknown: false,
        refusal_words: null,
        rebase: [],
      };
      return {
        kind: "settled",
        operation_id: `prior-value-check-${operations}`,
        revision: 1,
        result,
      } as LedgerOutcome<ModeloResult<typeof definition>>;
    },
  };
}
