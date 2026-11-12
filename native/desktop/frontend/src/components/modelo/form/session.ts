import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ledgerFailure, type LedgerFailureCode } from "../../../shell/ledger";
import { modeloEditBody, type ModeloPort } from "../../../shell/modelo";
import type { OutputLanguage } from "../../../shell/modeloContract/modelo";
import type {
  ModeloEditNormalisation,
  ModeloEditOperatorInputV2,
  ModeloEditTypedEntryV1,
  ModeloEditHeldAddressV1,
  ModeloEditHeldChangeV1,
  ModeloEditHeldKind,
  ModeloFormRebaseEntryV1,
} from "../../../shell/modeloContract/modeloEdit";
import type {
  ModeloEditApplyBaselineV1,
  ModeloEditBindingIntentKind,
  ModeloEditValueAddressV1,
  ModeloEditValueGrammarV1,
  ModeloEditWireScalar,
  ModeloFormAddressV1,
} from "../../../shell/modeloContract/modeloEditWork";
import type {
  AbsenceAttestationFamily,
  ModeloWorkbenchFormProjectionV1,
  PublicModeloFormField,
  ModeloFormBindingStatement,
  ModeloFormCarryAttestation,
  ModeloFormPriorValueWithdrawal,
  PublicModeloFormPriorValueAttestation,
} from "../../../shell/modeloContract/modeloWorkForm";
import type { PublicModeloWorkForm } from "../../../shell/modeloContract/modeloWorkFormPart2";
import { takesEntry } from "./entryField";

// The form's working state: the edits staged on it and the box chosen. It
// lives in memory only, for one declaration, and is handed to the review and
// the details panel. A staged edit carries the contract intent for the box's
// edit address and, for a typed value, the value the application read from
// what the filer typed; nothing here reads an amount, a date or a NIF.

/** A form address as one string: `c:<casilla>` or `b:<binding>`. */
export const addressKey = (address: ModeloFormAddressV1) =>
  address.kind === "casilla"
    ? `c:${address.casilla_id}`
    : `b:${address.binding_id}`;

/** The key a box is chosen by: its own address. */
export const fieldKey = (field: PublicModeloFormField) =>
  addressKey(field.address);

/** The key an edit of a box is staged under: the address the application
 * says the edit takes, which for a value fed by a source is its binding. */
export const editKey = (field: PublicModeloFormField) =>
  addressKey(field.edit_address);

/** The edit contract's spelling of a box's edit address. */
export function editAddress(
  field: PublicModeloFormField,
): ModeloEditValueAddressV1 {
  const address = field.edit_address;
  return address.kind === "casilla"
    ? { kind: "scalar", casilla_id: address.casilla_id }
    : {
        kind: "binding",
        binding_id: address.binding_id,
        row_identity: null,
      };
}

/** A value set on a box, and the same value as the application compares
 * entries of it (for a value read from what the filer typed, or an assumed
 * value confirmed); null when it gave none. */
type SetValue = {
  value: ModeloEditWireScalar;
  change: "set";
  comparable: ModeloEditWireScalar;
};

/** One staged edit as the edit contract names it: a box takes a typed
 * value, a clear, a restore, or the removal of the filer's own entry or
 * clear on a box no source feeds; a binding that feeds a box takes an override
 * or its removal, or, for a carry from an earlier filing, the filer's
 * statement that it holds no amount, said in the words the form served for
 * that statement. `change` is the kind of change the filer made, as a
 * preflight is told it: removing an override clears a value the filer gave,
 * or gives the box back to its source. A statement and its withdrawal name
 * the statement's family, which keeps every box of it together: a family is
 * staged whole or not at all. A carry the application holds no earlier return
 * for can take the figure the filer states for that return, in the words the
 * form served; the figures stated for one family of earlier returns are
 * withdrawn together, so their withdrawal names that family. */
export type StagedIntent =
  | ({ kind: "set_typed_value" } & SetValue)
  | { kind: "clear_declared_value"; change: "clear" }
  | { kind: "restore_source_value"; change: "restore" | "remove" }
  | ({ kind: "set_override_value" } & SetValue)
  | {
      kind: "remove_override";
      change: Exclude<ModeloEditHeldKind, "set">;
      /** The family whose statement this removal withdraws, when it does. */
      withdraws?: AbsenceAttestationFamily;
      /** The served withdrawal of the figures stated for one family of
       * earlier returns that this removal is part of, when it is. */
      withdrawsPrior?: PriorStatement;
    }
  | {
      kind: "attest_no_amount";
      change: "set";
      family: AbsenceAttestationFamily;
      words: string;
      effect: string;
    }
  | {
      kind: "attest_prior_value";
      change: "set";
      value: ModeloEditWireScalar;
      comparable: ModeloEditWireScalar;
      /** The family of earlier returns the figure stands in for. */
      family: string;
      words: string;
      effect: string;
    };

export type StagedEdit = {
  /** `editKey` of the box. */
  key: string;
  address: ModeloEditValueAddressV1;
  /** The box as the edit was last staged on it: as the form read it when
   * the filer staged it, or as a renewal's read restaged it. */
  field: PublicModeloFormField;
  intent: StagedIntent;
  /** What the filer typed, which the editor opens on again. */
  entry: string | null;
  /** The value the application read the entry as, as its box shows a value;
   * null where it said nothing or nothing was typed. */
  read: string | null;
  /** What the application did to read the entry. */
  normalisations: ModeloEditNormalisation[];
  /** The box changed under the edit when the baseline was renewed; the
   * filer looks at it again before applying. */
  beforeChanged: boolean;
};

/** What the last renewal did to the staged edits, until the filer
 * acknowledges it. */
export type Rebased = { changed: number; dropped: number };

/** What reports moved or dropped, by the address of each box (its own,
 * which a restage never changes), until the filer acknowledges it. */
export type Moved = ReadonlyMap<string, "changed" | "dropped">;

/** `moved` with what one report did added: a box counts once, and a box
 * first changed and then dropped counts as dropped. */
export function noteMoved(
  moved: Moved,
  found: Iterable<[string, "changed" | "dropped"]>,
): Moved {
  const next = new Map(moved);
  for (const [key, outcome] of found)
    if (outcome === "dropped" || next.get(key) !== "dropped")
      next.set(key, outcome);
  return next;
}

/** The notice `moved` gives: how many boxes changed and how many were
 * dropped, or null when none. */
export function rebasedOf(moved: Moved): Rebased | null {
  if (moved.size === 0) return null;
  let changed = 0;
  let dropped = 0;
  for (const outcome of moved.values())
    if (outcome === "changed") changed += 1;
    else dropped += 1;
  return { changed, dropped };
}

const atBinding = (field: PublicModeloFormField) =>
  field.edit_address.kind === "binding";

/** The intent that sets a box to `value` at its edit address. */
export const valueIntent = (
  field: PublicModeloFormField,
  value: ModeloEditWireScalar,
  comparable: ModeloEditWireScalar = null,
): StagedIntent =>
  atBinding(field)
    ? { kind: "set_override_value", value, change: "set", comparable }
    : { kind: "set_typed_value", value, change: "set", comparable };

/** The intent that takes the filer's value out of a box. */
export const clearIntent = (field: PublicModeloFormField): StagedIntent =>
  atBinding(field)
    ? { kind: "remove_override", change: "clear" }
    : { kind: "clear_declared_value", change: "clear" };

/** The intent that gives a box back to its source, or null where the box
 * offers none. */
export function restoreIntent(
  field: PublicModeloFormField,
): StagedIntent | null {
  if (!field.restorable) return null;
  return atBinding(field)
    ? { kind: "remove_override", change: "restore" }
    : { kind: "restore_source_value", change: "restore" };
}

/** The intent that takes the filer's own entry or clear out of a box no
 * source feeds, so it holds what the declaration gives without it, or null
 * where the box offers none. */
export function removeIntent(
  field: PublicModeloFormField,
): StagedIntent | null {
  return field.removable
    ? { kind: "restore_source_value", change: "remove" }
    : null;
}

/** The intent that confirms an assumed value as the filer's own, or null
 * where the application does not offer it. */
export function confirmIntent(
  field: PublicModeloFormField,
): StagedIntent | null {
  if (!field.confirmable || field.confirm_value === null) return null;
  return valueIntent(field, field.confirm_value, field.confirm_comparable);
}

/** The intent that withdraws the statement a box was stated by: its value
 * taken out at its binding, or the box given back to its source; null where
 * no statement stands on the box or neither is offered. */
export function withdrawIntent(
  field: PublicModeloFormField,
): StagedIntent | null {
  const family = field.stated_absent;
  if (family === null || !atBinding(field)) return null;
  if (field.clearable)
    return { kind: "remove_override", change: "clear", withdraws: family };
  if (field.restorable)
    return { kind: "remove_override", change: "restore", withdraws: family };
  return null;
}

/** The statement a staged intent belongs to, as one key: its family stated
 * or withdrawn; null for an edit of one box alone. Edits sharing it are
 * staged, kept and taken back together. */
export function statementOf(intent: StagedIntent): string | null {
  if (intent.kind === "attest_no_amount") return `state:${intent.family}`;
  if (intent.kind === "remove_override" && intent.withdraws !== undefined)
    return `withdraw:${intent.withdraws}`;
  if (intent.kind === "remove_override" && intent.withdrawsPrior !== undefined)
    return `withdraw-prior:${intent.withdrawsPrior.family}`;
  return null;
}

/** The intent that withdraws the figure stated on a box for the earlier
 * returns of `withdrawal`'s family: its value taken out at its binding, or the
 * box given back to its source; null where the box holds no figure stated for
 * that family or neither is offered. */
export function priorWithdrawIntent(
  field: PublicModeloFormField,
  withdrawal: PriorStatement,
): StagedIntent | null {
  if (
    !atBinding(field) ||
    field.stated_prior_value?.family_id !== withdrawal.family
  )
    return null;
  if (field.clearable)
    return {
      kind: "remove_override",
      change: "clear",
      withdrawsPrior: withdrawal,
    };
  if (field.restorable)
    return {
      kind: "remove_override",
      change: "restore",
      withdrawsPrior: withdrawal,
    };
  return null;
}

/** A served withdrawal as the intents of its carries name it. */
const priorStatementOf = (
  withdrawal: ModeloFormPriorValueWithdrawal,
): PriorStatement => ({
  family: withdrawal.family_id,
  words: withdrawal.action_words,
  effect: withdrawal.effect_words,
});

/** The box the form draws at a binding, where it draws one. */
function boxAtBinding(
  placed: readonly PlacedField[],
  bindingId: string,
): PublicModeloFormField | null {
  return (
    placed.find(
      (p) =>
        p.field.edit_address.kind === "binding" &&
        p.field.edit_address.binding_id === bindingId,
    )?.field ?? null
  );
}

/** What withdrawing a family's stated figures comes to: the withdrawal of
 * every carry the form serves it for, or, when one of them is drawn nowhere
 * or cannot be taken out here, that carry's binding, and nothing is staged. */
export type PriorWithdrawal =
  | { kind: "offered"; edits: StatementEdit[] }
  | { kind: "refused"; bindingId: string; field: PublicModeloFormField | null };

/** The withdrawal of every figure stated for one family, on each binding the
 * served `withdrawal` names, each as the baseline admits removing its value
 * (`admits`) and as the box allows. */
export function priorWithdrawal(
  placed: readonly PlacedField[],
  withdrawal: ModeloFormPriorValueWithdrawal,
  admits: (field: PublicModeloFormField) => boolean,
): PriorWithdrawal {
  const edits: StatementEdit[] = [];
  for (const bindingId of withdrawal.binding_ids) {
    const field = boxAtBinding(placed, bindingId);
    const intent =
      field && admits(field)
        ? priorWithdrawIntent(field, priorStatementOf(withdrawal))
        : null;
    if (!field || !intent) return { kind: "refused", bindingId, field };
    edits.push({ field, intent });
  }
  return { kind: "offered", edits };
}

/** The served withdrawal of `family`'s stated figures, or null where the
 * form serves none. */
export function servedPriorWithdrawal(
  served: readonly PublicModeloFormPriorValueAttestation[],
  family: string,
): ModeloFormPriorValueWithdrawal | null {
  for (const entry of served)
    if (entry.withdrawal?.family_id === family) return entry.withdrawal;
  return null;
}

/** The statement of a figure for its earlier returns that a box offers, as
 * the form served it on the box, or null where it offers none. A read that
 * offers no statement leaves the list out. */
export function priorValueStatement(
  field: PublicModeloFormField,
): ModeloFormBindingStatement | null {
  return (
    field.statements?.find(
      (statement) => statement.intent === "attest_prior_value",
    ) ?? null
  );
}

/** One box of a statement and the intent it takes. */
export type StatementEdit = {
  field: PublicModeloFormField;
  intent: StagedIntent;
};

/** The box at each binding `statement` names, in its order, each taking the
 * statement; null when the form draws one of them nowhere, so a statement
 * is never staged on part of what it names. */
export function statementEdits(
  placed: readonly PlacedField[],
  statement: ModeloFormCarryAttestation,
): StatementEdit[] | null {
  const edits: StatementEdit[] = [];
  for (const bindingId of statement.binding_ids) {
    const found = placed.find(
      (p) =>
        p.field.edit_address.kind === "binding" &&
        p.field.edit_address.binding_id === bindingId,
    );
    if (!found) return null;
    edits.push({
      field: found.field,
      intent: {
        kind: "attest_no_amount",
        change: "set",
        family: statement.family,
        words: statement.action_words,
        effect: statement.effect_words,
      },
    });
  }
  return edits;
}

/** What withdrawing a box's statement comes to: the withdrawal of every box
 * the same statement stands on, or, when one of them cannot be taken out
 * here, that box, and nothing is staged. */
export type Withdrawal =
  | { kind: "offered"; edits: StatementEdit[] }
  | { kind: "refused"; field: PublicModeloFormField };

/** The boxes a statement stands on, once each, in reading order. */
function statedBoxes(
  placed: readonly PlacedField[],
  family: AbsenceAttestationFamily,
): PublicModeloFormField[] {
  const seen = new Set<string>();
  const boxes: PublicModeloFormField[] = [];
  for (const { field } of placed) {
    const key = editKey(field);
    if (field.stated_absent !== family || seen.has(key)) continue;
    seen.add(key);
    boxes.push(field);
  }
  return boxes;
}

/** The withdrawal a stated box offers, or null where it offers none: a
 * statement is withdrawn from every box it stands on at once, each as the
 * baseline admits removing its value (`admits`) and as the box allows. */
export function withdrawal(
  placed: readonly PlacedField[],
  field: PublicModeloFormField,
  admits: (field: PublicModeloFormField) => boolean,
): Withdrawal | null {
  const family = field.stated_absent;
  if (family === null || !admits(field) || !withdrawIntent(field)) return null;
  const edits: StatementEdit[] = [];
  for (const box of statedBoxes(placed, family)) {
    const intent = admits(box) ? withdrawIntent(box) : null;
    if (!intent) return { kind: "refused", field: box };
    edits.push({ field: box, intent });
  }
  return { kind: "offered", edits };
}

/** The binding intents the baseline admits, by `addressKey`. */
export function bindingIntents(
  baseline: ModeloEditApplyBaselineV1 | null,
): ReadonlyMap<string, readonly ModeloEditBindingIntentKind[]> {
  const intents = new Map<string, readonly ModeloEditBindingIntentKind[]>();
  for (const entry of baseline?.permitted_surface ?? [])
    if (entry.kind === "writable_binding_override")
      intents.set(`b:${entry.binding_id}`, entry.allowed_intents);
  return intents;
}

/** The boxes a staged statement or withdrawal must cover to stand, by
 * `editKey`: every box the form serves the statement for, or every box it
 * shows stated; none when it serves or shows none. */
function coveredBy(
  intent: StagedIntent,
  placed: readonly PlacedField[],
  served: readonly ModeloFormCarryAttestation[],
  priorValues: readonly PublicModeloFormPriorValueAttestation[],
): string[] {
  if (
    intent.kind === "remove_override" &&
    intent.withdrawsPrior !== undefined
  ) {
    const withdrawal = servedPriorWithdrawal(
      priorValues,
      intent.withdrawsPrior.family,
    );
    return withdrawal ? withdrawal.binding_ids.map((id) => `b:${id}`) : [];
  }
  if (intent.kind === "attest_no_amount") {
    const statement = served.find((each) => each.family === intent.family);
    const edits = statement ? statementEdits(placed, statement) : null;
    return edits?.map((edit) => editKey(edit.field)) ?? [];
  }
  if (intent.kind === "remove_override" && intent.withdraws !== undefined)
    return statedBoxes(placed, intent.withdraws).map(editKey);
  return [];
}

/** `staged` with every statement whole: a statement or a withdrawal whose
 * boxes are not all staged, as the form now serves the statement (`served`)
 * or shows it stated, is dropped with every box of it. */
export function wholeStatements(
  staged: ReadonlyMap<string, StagedEdit>,
  placed: readonly PlacedField[],
  served: readonly ModeloFormCarryAttestation[],
  priorValues: readonly PublicModeloFormPriorValueAttestation[] = [],
): { next: Map<string, StagedEdit>; dropped: StagedEdit[] } {
  const groups = new Map<string, StagedEdit[]>();
  for (const edit of staged.values()) {
    const group = statementOf(edit.intent);
    if (group) groups.set(group, [...(groups.get(group) ?? []), edit]);
  }
  const next = new Map(staged);
  const dropped: StagedEdit[] = [];
  for (const edits of groups.values()) {
    const first = edits[0];
    if (!first) continue;
    const wanted = coveredBy(first.intent, placed, served, priorValues);
    const keys = new Set(edits.map((edit) => edit.key));
    if (
      wanted.length > 0 &&
      wanted.length === keys.size &&
      wanted.every((key) => keys.has(key))
    )
      continue;
    for (const edit of edits) {
      next.delete(edit.key);
      dropped.push(edit);
    }
  }
  return { next, dropped };
}

/** An edit address as one string, as a preflight's report names it. */
const heldKey = (address: ModeloEditHeldAddressV1) =>
  address.kind === "scalar"
    ? `s:${address.casilla_id}`
    : `b:${address.binding_id}`;

/** A staged edit as a preflight is told it was held: its edit address, the
 * kind of change and the box's state when it was staged, so the preflight
 * says what became of it. */
function held(edit: StagedEdit): ModeloEditHeldChangeV1 | null {
  const { address } = edit;
  if (address.kind !== "scalar" && address.kind !== "binding") return null;
  return {
    address,
    kind: edit.intent.change,
    held_state: edit.field.state_digest,
  };
}

/** The staged edits as one submission, valid for a preflight and for an
 * apply: typed values only, never entries as typed. Findings and refusals
 * come back said in `language`. A preflight is also told the changes held,
 * `heldChanges`, and reports what became of each. */
export function editSubmission(
  baseline: ModeloEditApplyBaselineV1,
  edits: Iterable<StagedEdit>,
  language: OutputLanguage,
  heldChanges = false,
): ModeloEditOperatorInputV2 {
  const all = [...edits];
  const scalar: NonNullable<
    ModeloEditOperatorInputV2["submission"]["scalar_intents"]
  > = [];
  const binding: NonNullable<
    ModeloEditOperatorInputV2["submission"]["binding_intents"]
  > = [];
  for (const edit of all) {
    const { address, intent } = edit;
    const value = "value" in intent ? { value: intent.value } : {};
    if (address.kind === "scalar") {
      if (
        intent.kind === "set_typed_value" ||
        intent.kind === "clear_declared_value" ||
        intent.kind === "restore_source_value"
      )
        scalar.push({ address, kind: intent.kind, ...value });
    } else if (
      address.kind === "binding" &&
      (intent.kind === "set_override_value" ||
        intent.kind === "remove_override" ||
        intent.kind === "attest_no_amount" ||
        intent.kind === "attest_prior_value")
    )
      binding.push({ address, kind: intent.kind, ...value });
  }
  return {
    input_version: 2,
    output_language: language,
    submission: {
      baseline,
      mutation_family: baseline.mutation_family,
      scalar_intents: scalar,
      binding_intents: binding,
      ...(heldChanges
        ? {
            held: all.flatMap((edit) => {
              const change = held(edit);
              return change ? [change] : [];
            }),
          }
        : {}),
    },
  };
}

/** A preflight that only reads one entry as the filer typed it. */
export function entrySubmission(
  baseline: ModeloEditApplyBaselineV1,
  field: PublicModeloFormField,
  lexeme: string,
  language: OutputLanguage,
): ModeloEditOperatorInputV2 {
  return {
    input_version: 2,
    output_language: language,
    submission: {
      baseline,
      mutation_family: baseline.mutation_family,
      lexemes: [
        { address: editAddress(field), entry_locale: language, lexeme },
      ],
    },
  };
}

/** What renewing an edit baseline came to: the renewed baseline; refused
 * because the declaration moved under it, in the words the application
 * served; or not answered. */
export type BaselineRenewal =
  | { kind: "renewed"; baseline: ModeloEditApplyBaselineV1 }
  | { kind: "moved"; words: string | null }
  | { kind: "failed"; code: LedgerFailureCode | "refused" };

/** Renews `baseline` through the application, which re-admits it only when
 * nothing but its lifetime changed. An editor renews before it reads an
 * entry again and just before it applies, so a baseline that only ran out
 * never reaches the filer as a declaration that changed. */
export async function renewBaseline(
  port: ModeloPort,
  baseline: ModeloEditApplyBaselineV1,
  language: OutputLanguage,
): Promise<BaselineRenewal> {
  try {
    const outcome = await port.submit("modelo.edit.renew", {
      baseline,
      output_language: language,
    });
    // A renewal that settles as anything but an answer was refused.
    if (outcome.kind !== "settled") return { kind: "failed", code: "refused" };
    const renewed = outcome.result.renewed_baseline;
    return renewed
      ? { kind: "renewed", baseline: renewed }
      : { kind: "moved", words: outcome.result.refusal_words };
  } catch (error) {
    return { kind: "failed", code: ledgerFailure(error).code };
  }
}

/** Where a box is drawn: the page and section holding it. Boxes not yet
 * placed, working figures and the answers no page takes have pages of their
 * own. */
export type PlacedField = {
  field: PublicModeloFormField;
  key: string;
  pageId: string;
  sectionId: string;
};

export const UNPLACED_PAGE = "unplaced";
export const WORKING_FIGURES_PAGE = "working-figures";
export const ANSWERS_PAGE = "answers";

/** Every box of the form in reading order. */
export function placedFields(form: PublicModeloWorkForm): PlacedField[] {
  const out: PlacedField[] = [];
  const add = (
    field: PublicModeloFormField,
    pageId: string,
    sectionId: string,
  ) => out.push({ field, key: fieldKey(field), pageId, sectionId });
  for (const page of form.pages)
    for (const section of page.sections)
      for (const block of section.blocks) {
        if (block.kind === "field") add(block.field, page.id, section.id);
        else if (block.kind === "binding_inputs")
          for (const field of block.fields) add(field, page.id, section.id);
        else if (block.kind === "grid")
          for (const row of block.rows)
            for (const cell of row.cells)
              if (cell.field) add(cell.field, page.id, section.id);
      }
  for (const unplaced of form.unplaced)
    add(unplaced.field, UNPLACED_PAGE, UNPLACED_PAGE);
  for (const field of form.working_figures)
    add(field, WORKING_FIGURES_PAGE, WORKING_FIGURES_PAGE);
  for (const field of form.answers) add(field, ANSWERS_PAGE, ANSWERS_PAGE);
  return out;
}

/** The intent an edit takes when it is staged again on `field`, as the
 * box now stands, or null when the box no longer takes it: a value the box
 * already holds as the filer's own changes nothing, a clear needs a value
 * of the filer's to remove, and a restore needs a source to go back to. */
export function restaged(
  edit: StagedEdit,
  field: PublicModeloFormField,
): StagedIntent | null {
  const { intent } = edit;
  // A statement stands only while the carry still holds no value: one an
  // earlier return now supplies is dropped, never staged over it.
  if (intent.kind === "attest_no_amount")
    return field.takes_typed_value && field.origin !== "imported"
      ? intent
      : null;
  // A withdrawal stands only while the box still holds its statement.
  if (intent.kind === "remove_override" && intent.withdraws !== undefined)
    return field.stated_absent === intent.withdraws
      ? withdrawIntent(field)
      : null;
  if (intent.kind === "remove_override" && intent.withdrawsPrior !== undefined)
    return priorWithdrawIntent(field, intent.withdrawsPrior);
  // A stated figure stands only while the box still offers the statement:
  // a carry an earlier return now supplies drops it, never staged over it.
  if (intent.kind === "attest_prior_value")
    return field.takes_typed_value && priorValueStatement(field) !== null
      ? intent
      : null;
  if (intent.change === "set") {
    if (!field.takes_typed_value) return null;
    if (
      field.own_value !== null &&
      intent.comparable !== null &&
      intent.comparable === field.own_value
    )
      return null;
    return valueIntent(field, intent.value, intent.comparable);
  }
  if (intent.change === "clear")
    return field.clearable ? clearIntent(field) : null;
  if (intent.change === "remove") return removeIntent(field);
  return restoreIntent(field);
}

/** The staged edits as a preflight's `report` leaves them on the boxes
 * `placed` as they now stand: each kept or changed edit staged again on its
 * box, the others dropped, and a statement or withdrawal left with only some
 * of its boxes dropped whole, against the statements the form now serves
 * (`served`); and what the report moved or dropped, by the box's own
 * address. */
export function rebasedEdits(
  staged: ReadonlyMap<string, StagedEdit>,
  report: ModeloFormRebaseEntryV1[],
  placed: readonly PlacedField[],
  served: readonly ModeloFormCarryAttestation[] = [],
  priorValues: readonly PublicModeloFormPriorValueAttestation[] = [],
): {
  next: Map<string, StagedEdit>;
  found: [string, "changed" | "dropped"][];
} {
  const outcomes = new Map(
    report.map((entry) => [heldKey(entry.address), entry.outcome]),
  );
  const now = new Map(placed.map((p) => [p.key, p.field]));
  const next = new Map<string, StagedEdit>();
  const found: [string, "changed" | "dropped"][] = [];
  for (const edit of staged.values()) {
    const change = held(edit);
    const outcome = (change && outcomes.get(heldKey(change.address))) ?? "kept";
    const where = addressKey(edit.field.address);
    const field = now.get(where);
    const intent = field && outcome !== "dropped" && restaged(edit, field);
    if (!field || !intent) {
      found.push([where, "dropped"]);
      continue;
    }
    if (outcome === "changed") found.push([where, "changed"]);
    const key = editKey(field);
    next.set(key, {
      ...edit,
      key,
      address: editAddress(field),
      field,
      intent,
      beforeChanged: outcome === "changed" || edit.beforeChanged,
    });
  }
  const whole = wholeStatements(next, placed, served, priorValues);
  for (const edit of whole.dropped)
    found.push([addressKey(edit.field.address), "dropped"]);
  return { next: whole.next, found };
}

/** What each writable address takes as the baseline admits it, by
 * `addressKey`. An address the baseline does not make writable has none. */
export function entryGrammars(
  baseline: ModeloEditApplyBaselineV1 | null,
): ReadonlyMap<string, ModeloEditValueGrammarV1> {
  const grammars = new Map<string, ModeloEditValueGrammarV1>();
  for (const entry of baseline?.permitted_surface ?? []) {
    if (entry.kind === "writable_scalar")
      grammars.set(`c:${entry.casilla_id}`, entry.grammar);
    else if (entry.kind === "writable_binding_override")
      grammars.set(`b:${entry.binding_id}`, entry.grammar);
  }
  return grammars;
}

/** Whether the declaration takes edits at all. */
export const editsAdmitted = (envelope: ModeloWorkbenchFormProjectionV1) =>
  envelope.admitted_baseline !== null &&
  envelope.form.form.edit_closure === null;

/** What reading one typed entry came to. */
export type EntryOutcome =
  | { kind: "staged" }
  | { kind: "unchanged" }
  | { kind: "refused"; entry: ModeloEditTypedEntryV1 }
  /** Not read: the check was refused, in its own words where it gave
   * them, or never reached the application. */
  | { kind: "failed"; code: string; words: string | null };

const NO_PRIOR_VALUES: readonly PublicModeloFormPriorValueAttestation[] = [];

/** The carries a form serves for stating a figure of earlier returns. The
 * read leaves the list out when it is empty. */
export const priorValuesOf = (
  form: PublicModeloWorkForm,
): readonly PublicModeloFormPriorValueAttestation[] =>
  (form.prior_value_attestations as
    PublicModeloFormPriorValueAttestation[] | undefined) ?? NO_PRIOR_VALUES;

/** A figure stated for a carry's earlier returns, as the form served the
 * statement: the family of those returns, the action and what it does. */
export type PriorStatement = { family: string; words: string; effect: string };

/** A request to bring a box or a section into view; `seq` repeats it. */
export type Reveal = { key: string | null; sectionId: string; seq: number };

export type FormSession = {
  /** The baseline every check and apply is sent on: the one the form's read
   * admitted, or a renewal of it adopted since, whichever was issued later. */
  baseline: ModeloEditApplyBaselineV1 | null;
  /** Adopts a renewal of the baseline for every check and apply after it. */
  adoptBaseline(baseline: ModeloEditApplyBaselineV1): void;
  staged: ReadonlyMap<string, StagedEdit>;
  stagedCount: number;
  /** Stages one edit on its box; an edit staged over one box of a statement
   * or withdrawal takes the rest of it back, so none is left in part. */
  stage(field: PublicModeloFormField, intent: StagedIntent): void;
  /** Takes back the edit staged under `editKey`, and with it every other box
   * of the statement or withdrawal it belongs to. */
  unstage(editKey: string): void;
  /** Every statement the form serves, in its order and words; none where
   * the declaration takes no edit. */
  statements: readonly ModeloFormCarryAttestation[];
  /** Whether `statement` is staged on every box it names. */
  stagesStatement(statement: ModeloFormCarryAttestation): boolean;
  /** Stages each of `chosen` on every box it names and takes back every
   * served statement not chosen; answers the chosen statements that name a
   * box the form draws nowhere, which are not staged. */
  stageStatements(
    chosen: readonly ModeloFormCarryAttestation[],
  ): ModeloFormCarryAttestation[];
  /** The withdrawal a box stated by a statement offers, or null. */
  withdrawal(field: PublicModeloFormField): Withdrawal | null;
  /** Stages the withdrawal a box offers on every box of its statement, and
   * answers it; nothing is staged when it is refused. */
  withdraw(field: PublicModeloFormField): Withdrawal | null;
  discardAll(): void;
  /** Keeps the staged edits a preflight's `report` keeps, staged again
   * against the declaration as it stands, and drops the others. */
  rebase(report: ModeloFormRebaseEntryV1[]): void;
  /** What the last report moved or dropped, until acknowledged; null when
   * nothing. */
  rebased: Rebased | null;
  /** A report not yet applied: until it is, the staged edits do not carry
   * what it says. */
  rebasePending: boolean;
  /** Takes the renewal's marks off the edits the filer has looked at. */
  acknowledge(): void;
  /** Reads what the filer typed into a box through the application and
   * stages the value it reads. An empty entry takes back a value typed here,
   * or else takes the filer's value out of the box. With `prior`, the value
   * read is staged as the figure the filer states for the box's earlier
   * returns, and an empty entry only takes back such a figure typed here. */
  enter(
    field: PublicModeloFormField,
    text: string,
    prior?: PriorStatement,
  ): Promise<EntryOutcome>;
  /** The carries the filer can state a figure of for earlier returns the
   * application does not hold, as the form serves them; none where the
   * declaration takes no edit. */
  priorValues: readonly PublicModeloFormPriorValueAttestation[];
  /** What withdrawing a family's stated figures would stage. */
  priorWithdrawal(withdrawal: ModeloFormPriorValueWithdrawal): PriorWithdrawal;
  /** Stages the withdrawal of every figure stated for a family, and answers
   * it; nothing is staged when it is refused. */
  withdrawPriorValues(
    withdrawal: ModeloFormPriorValueWithdrawal,
  ): PriorWithdrawal;
  /** Whether the withdrawal of `family`'s stated figures is staged. */
  stagesPriorWithdrawal(family: string): boolean;
  /** What a box's edit address takes, or null where it takes nothing. */
  grammarOf(field: PublicModeloFormField): ModeloEditValueGrammarV1 | null;
  /** Whether a box can be typed into here: the form admits edits, the
   * application says the box takes a typed value, and its grammar takes one. */
  editable(field: PublicModeloFormField): boolean;
  selectedKey: string | null;
  selected: PublicModeloFormField | null;
  select(key: string | null): void;
  /** Chooses the box printed with `box` and brings it into view. */
  selectBox(box: string): boolean;
  /** Chooses the box of a casilla and brings it into view. */
  selectCasilla(casillaId: string): boolean;
  /** Chooses the box at a form address and brings it into view. */
  selectAddress(address: ModeloFormAddressV1): boolean;
  /** The box at a form address, where the form draws one. */
  fieldAt(address: ModeloFormAddressV1): PublicModeloFormField | null;
  /** Chooses the next box after the chosen one that needs the filer, or
   * whose calculation failed, and brings it into view. */
  jumpToNext(kind: "todo" | "failed"): boolean;
  goSection(sectionId: string): void;
  pageId: string | null;
  setPageId(id: string): void;
  reveal: Reveal | null;
  placed: readonly PlacedField[];
};

export function useFormSession({
  envelope,
  port,
  language,
}: {
  envelope: ModeloWorkbenchFormProjectionV1;
  port: ModeloPort;
  language: OutputLanguage;
}): FormSession {
  const form = envelope.form.form;
  const placed = useMemo(() => placedFields(form), [form]);
  const byKey = useMemo(() => new Map(placed.map((p) => [p.key, p])), [placed]);
  const [staged, setStaged] = useState<ReadonlyMap<string, StagedEdit>>(
    () => new Map(),
  );
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [pageId, setPageId] = useState<string | null>(
    form.pages[0]?.id ?? null,
  );
  const [reveal, setReveal] = useState<Reveal | null>(null);
  const seq = useRef(0);
  const [renewed, setRenewed] = useState<ModeloEditApplyBaselineV1 | null>(
    null,
  );

  // Staged edits belong to one declaration; another one starts clean.
  const unit = envelope.work_unit_id;
  const [heldUnit, setHeldUnit] = useState(unit);
  if (heldUnit !== unit) {
    setHeldUnit(unit);
    setStaged(new Map());
    setSelectedKey(null);
    setPageId(form.pages[0]?.id ?? null);
    setReveal(null);
    setRenewed(null);
  }
  useEffect(() => {
    if (pageId === null && form.pages[0]) setPageId(form.pages[0].id);
  }, [pageId, form.pages]);

  const stage = useCallback(
    (
      field: PublicModeloFormField,
      intent: StagedIntent,
      entry: string | null = null,
      read: string | null = null,
      normalisations: ModeloEditNormalisation[] = [],
    ) => {
      const key = editKey(field);
      setStaged((now) => {
        const next = new Map(now);
        // A statement or withdrawal stands whole or not at all: an edit
        // staged over one of its boxes takes the rest of it back.
        const before = now.get(key);
        const group = before ? statementOf(before.intent) : null;
        if (group && group !== statementOf(intent))
          for (const [other, edit] of now)
            if (statementOf(edit.intent) === group) next.delete(other);
        next.set(key, {
          key,
          address: editAddress(field),
          field: now.get(key)?.field ?? field,
          intent,
          entry,
          read,
          normalisations,
          beforeChanged: now.get(key)?.beforeChanged ?? false,
        });
        return next;
      });
    },
    [],
  );
  const unstage = useCallback((key: string) => {
    setStaged((now) => {
      const held = now.get(key);
      if (!held) return now;
      const next = new Map(now);
      next.delete(key);
      const group = statementOf(held.intent);
      if (group)
        for (const [other, edit] of now)
          if (statementOf(edit.intent) === group) next.delete(other);
      return next;
    });
  }, []);
  const [moved, setMoved] = useState<Moved>(() => new Map());
  const rebased = useMemo(() => rebasedOf(moved), [moved]);
  const discardAll = useCallback(() => {
    setStaged(new Map());
    setMoved(new Map());
  }, []);

  // A renewal's report is applied once the declaration is read again: each
  // kept edit is staged again against its box as it now stands, as the
  // TUI's rebase does, and a box that changed under its edit is marked.
  const [pendingRebase, setPendingRebase] = useState<
    ModeloFormRebaseEntryV1[] | null
  >(null);
  const rebase = useCallback(
    (report: ModeloFormRebaseEntryV1[]) => setPendingRebase(report),
    [],
  );
  useEffect(() => {
    if (!pendingRebase) return;
    setPendingRebase(null);
    const { next, found } = rebasedEdits(
      staged,
      pendingRebase,
      placed,
      form.carry_attestations,
      priorValuesOf(form),
    );
    setStaged(next);
    // What a report moved or dropped is said until the filer acknowledges
    // it: a later check is told only the changes still held, so it adds what
    // it finds, by box, and never takes back what an earlier report dropped.
    if (found.length) setMoved((shown) => noteMoved(shown, found));
  }, [pendingRebase, placed, staged, form]);
  const acknowledge = useCallback(() => {
    setMoved(new Map());
    setStaged((held) => {
      if (![...held.values()].some((edit) => edit.beforeChanged)) return held;
      return new Map(
        [...held].map(([key, edit]) => [
          key,
          { ...edit, beforeChanged: false },
        ]),
      );
    });
  }, []);

  const admittedBaseline = envelope.admitted_baseline;
  // A baseline a later read admitted supersedes a renewal of an earlier one.
  const baseline =
    renewed &&
    renewed.work_unit_id === unit &&
    (!admittedBaseline || renewed.issued_at >= admittedBaseline.issued_at)
      ? renewed
      : admittedBaseline;
  const adoptBaseline = useCallback(
    (next: ModeloEditApplyBaselineV1) => setRenewed(next),
    [],
  );
  const grammars = useMemo(() => entryGrammars(baseline), [baseline]);
  const grammarOf = useCallback(
    (field: PublicModeloFormField) => grammars.get(editKey(field)) ?? null,
    [grammars],
  );
  const admitted = editsAdmitted(envelope);
  const editable = useCallback(
    (field: PublicModeloFormField) => {
      const grammar = grammarOf(field);
      return (
        admitted &&
        field.takes_typed_value &&
        grammar !== null &&
        takesEntry(grammar)
      );
    },
    [admitted, grammarOf],
  );
  // What the baseline admits at each binding, for the statements' boxes.
  const intents = useMemo(() => bindingIntents(baseline), [baseline]);
  const admitsRemoval = useCallback(
    (field: PublicModeloFormField) =>
      admitted &&
      (intents.get(editKey(field))?.includes("remove_override") ?? false),
    [admitted, intents],
  );
  const withdrawalOf = useCallback(
    (field: PublicModeloFormField) => withdrawal(placed, field, admitsRemoval),
    [placed, admitsRemoval],
  );
  const stageAll = useCallback(
    (edits: readonly StatementEdit[]) => {
      for (const edit of edits) stage(edit.field, edit.intent);
    },
    [stage],
  );
  const withdraw = useCallback(
    (field: PublicModeloFormField) => {
      const offer = withdrawalOf(field);
      if (offer?.kind === "offered") stageAll(offer.edits);
      return offer;
    },
    [withdrawalOf, stageAll],
  );
  const statements = useMemo(
    () => (admitted ? form.carry_attestations : []),
    [admitted, form.carry_attestations],
  );
  const servedPriorValues = priorValuesOf(form);
  const priorValues = useMemo(
    () => (admitted ? servedPriorValues : []),
    [admitted, servedPriorValues],
  );
  const priorWithdrawalOf = useCallback(
    (served: ModeloFormPriorValueWithdrawal) =>
      priorWithdrawal(placed, served, admitsRemoval),
    [placed, admitsRemoval],
  );
  const withdrawPriorValues = useCallback(
    (served: ModeloFormPriorValueWithdrawal) => {
      const offer = priorWithdrawalOf(served);
      if (offer.kind === "offered") stageAll(offer.edits);
      return offer;
    },
    [priorWithdrawalOf, stageAll],
  );
  const stagesPriorWithdrawal = useCallback(
    (family: string) =>
      [...staged.values()].some(
        (edit) =>
          edit.intent.kind === "remove_override" &&
          edit.intent.withdrawsPrior?.family === family,
      ),
    [staged],
  );
  const stagesStatement = useCallback(
    (statement: ModeloFormCarryAttestation) =>
      statement.binding_ids.length > 0 &&
      statement.binding_ids.every((bindingId) => {
        const intent = staged.get(`b:${bindingId}`)?.intent;
        return (
          intent?.kind === "attest_no_amount" &&
          intent.family === statement.family
        );
      }),
    [staged],
  );
  const stageStatements = useCallback(
    (chosen: readonly ModeloFormCarryAttestation[]) => {
      const unplaced: ModeloFormCarryAttestation[] = [];
      for (const statement of statements) {
        if (!chosen.includes(statement)) {
          const held = [...staged.values()].find(
            (edit) =>
              edit.intent.kind === "attest_no_amount" &&
              edit.intent.family === statement.family,
          );
          if (held) unstage(held.key);
          continue;
        }
        if (stagesStatement(statement)) continue;
        const edits = statementEdits(placed, statement);
        if (edits) stageAll(edits);
        else unplaced.push(statement);
      }
      return unplaced;
    },
    [statements, staged, unstage, stagesStatement, placed, stageAll],
  );
  const enter = useCallback(
    async (
      field: PublicModeloFormField,
      text: string,
      prior?: PriorStatement,
    ) => {
      const lexeme = text.trim();
      const key = editKey(field);
      const held = staged.get(key);
      if (!lexeme && prior) {
        // Emptying a figure stated here takes it back, and nothing else.
        if (held?.intent.kind !== "attest_prior_value")
          return { kind: "unchanged" } as const;
        unstage(key);
        return { kind: "staged" } as const;
      }
      if (!lexeme) {
        // Emptying a value typed here takes it back; emptying a value the
        // box holds takes the filer's value out of it.
        if (held && "value" in held.intent) {
          unstage(key);
          return { kind: "staged" } as const;
        }
        if (held) return { kind: "unchanged" } as const;
        // Emptying a stated box withdraws its statement from every box of it.
        if (field.stated_absent !== null)
          return withdraw(field)?.kind === "offered"
            ? ({ kind: "staged" } as const)
            : ({ kind: "unchanged" } as const);
        // Emptying a figure stated for earlier returns withdraws every figure
        // stated for the same returns, as the form serves that withdrawal.
        const family = field.stated_prior_value?.family_id;
        if (family) {
          const served = servedPriorWithdrawal(priorValues, family);
          return served && withdrawPriorValues(served).kind === "offered"
            ? ({ kind: "staged" } as const)
            : ({ kind: "unchanged" } as const);
        }
        if (!field.clearable) return { kind: "unchanged" } as const;
        stage(field, clearIntent(field));
        return { kind: "staged" } as const;
      }
      if (held?.entry === lexeme) return { kind: "unchanged" } as const;
      if (!baseline)
        return { kind: "failed", code: "not_admitted", words: null } as const;
      const check = (on: ModeloEditApplyBaselineV1) =>
        port.edit(
          "modelo.edit.preflight",
          modeloEditBody(entrySubmission(on, field, lexeme, language)),
        );
      try {
        let outcome = await check(baseline);
        // A stale baseline is renewed once and the entry read again on the
        // renewal: time passing alone never refuses an entry. When the
        // declaration did move, the renewal is refused and says so.
        if (
          outcome.kind === "settled" &&
          outcome.result.outcome.outcome === "refused" &&
          outcome.result.outcome.refusal.kind === "stale_edit_baseline"
        ) {
          const renewal = await renewBaseline(port, baseline, language);
          if (renewal.kind === "moved")
            return {
              kind: "failed",
              code: "stale_edit_baseline",
              words: renewal.words ?? outcome.result.refusal_words,
            } as const;
          if (renewal.kind === "renewed") {
            adoptBaseline(renewal.baseline);
            outcome = await check(renewal.baseline);
          }
        }
        if (outcome.kind !== "settled")
          return { kind: "failed", code: outcome.kind, words: null } as const;
        const read = outcome.result;
        if (read.outcome.outcome === "refused")
          return {
            kind: "failed",
            code: read.outcome.refusal.kind,
            words: read.refusal_words,
          } as const;
        const entry = read.parsed[0];
        if (!entry)
          return { kind: "failed", code: "unknown", words: null } as const;
        if (entry.refusal) return { kind: "refused", entry } as const;
        if (prior) {
          stage(
            field,
            {
              kind: "attest_prior_value",
              change: "set",
              value: entry.value,
              comparable: entry.comparable_value,
              family: prior.family,
              words: prior.words,
              effect: prior.effect,
            },
            lexeme,
            entry.value_text,
            entry.normalisations,
          );
          return { kind: "staged" } as const;
        }
        // Typing the filer's own value again changes nothing; an assumed value
        // typed unchanged is staged, as keeping it is how it is confirmed.
        if (
          field.own_value !== null &&
          entry.comparable_value === field.own_value
        ) {
          if (held) unstage(key);
          return { kind: "unchanged" } as const;
        }
        stage(
          field,
          valueIntent(field, entry.value, entry.comparable_value),
          lexeme,
          entry.value_text,
          entry.normalisations,
        );
        return { kind: "staged" } as const;
      } catch (error) {
        return {
          kind: "failed",
          code: ledgerFailure(error).code,
          words: null,
        } as const;
      }
    },
    [
      adoptBaseline,
      baseline,
      language,
      port,
      priorValues,
      stage,
      staged,
      unstage,
      withdraw,
      withdrawPriorValues,
    ],
  );

  const bring = useCallback((target: PlacedField | undefined) => {
    if (!target) return false;
    setPageId(target.pageId);
    setSelectedKey(target.key);
    seq.current += 1;
    setReveal({
      key: target.key,
      sectionId: target.sectionId,
      seq: seq.current,
    });
    return true;
  }, []);
  const selectBox = useCallback(
    (box: string) => bring(placed.find((p) => p.field.box === box)),
    [bring, placed],
  );
  const selectCasilla = useCallback(
    (casillaId: string) => bring(byKey.get(`c:${casillaId}`)),
    [bring, byKey],
  );
  const selectAddress = useCallback(
    (address: ModeloFormAddressV1) => bring(byKey.get(addressKey(address))),
    [bring, byKey],
  );
  const fieldAt = useCallback(
    (address: ModeloFormAddressV1) =>
      byKey.get(addressKey(address))?.field ?? null,
    [byKey],
  );
  const jumpToNext = useCallback(
    (kind: "todo" | "failed") => {
      const wanted = placed.filter((p) =>
        kind === "todo"
          ? p.field.standing === "needs_you" && !staged.has(editKey(p.field))
          : p.field.origin === "calculation_failed",
      );
      const at = wanted.findIndex((p) => p.key === selectedKey);
      return bring(wanted[(at + 1) % Math.max(wanted.length, 1)]);
    },
    [bring, placed, selectedKey, staged],
  );
  const goSection = useCallback(
    (sectionId: string) => {
      const page =
        form.pages.find((p) => p.sections.some((s) => s.id === sectionId))
          ?.id ?? sectionId;
      setPageId(page);
      seq.current += 1;
      setReveal({ key: null, sectionId, seq: seq.current });
    },
    [form.pages],
  );

  return {
    baseline,
    adoptBaseline,
    staged,
    stagedCount: staged.size,
    stage,
    unstage,
    statements,
    stagesStatement,
    stageStatements,
    withdrawal: withdrawalOf,
    withdraw,
    priorValues,
    priorWithdrawal: priorWithdrawalOf,
    withdrawPriorValues,
    stagesPriorWithdrawal,
    discardAll,
    rebase,
    rebased,
    rebasePending: pendingRebase !== null,
    acknowledge,
    enter,
    grammarOf,
    editable,
    selectedKey,
    selected: selectedKey ? (byKey.get(selectedKey)?.field ?? null) : null,
    select: setSelectedKey,
    selectBox,
    selectCasilla,
    selectAddress,
    fieldAt,
    jumpToNext,
    goSection,
    pageId,
    setPageId,
    reveal,
    placed,
  };
}
