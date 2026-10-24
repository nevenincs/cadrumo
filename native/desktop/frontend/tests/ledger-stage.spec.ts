import { expect, test } from "@playwright/test";
import {
  changesIdentity,
  EMPTY_STAGE,
  effectiveFacts,
  newDraft,
  newIdempotencyKey,
  reduceStage,
  stagedCount,
  storedFieldValue,
  type StageCell,
  type StageEvent,
  type StageField,
  type StageState,
  type StagedAction,
} from "../src/shell/ledgerStage";
import { hexId, movement } from "./support/ledger";

// The staged-changes store. No page is opened.

const A = hexId("a");
const B = hexId("b");
const rowA = movement(A, {
  business_classification: "BUSINESS",
  category_id: "material_oficina",
  taxable_base: "30.00",
  iva_rate: "0.21",
});
const rowB = movement(B);
const stored = { [A]: rowA, [B]: rowB };

const set = (id: string, field: StageField, value: string): StageCell => ({
  id,
  field,
  value: { kind: "set", value },
  stored: storedFieldValue(stored[id]!, field),
});
const clear = (id: string, field: StageField): StageCell => ({
  id,
  field,
  value: { kind: "clear" },
  stored: storedFieldValue(stored[id]!, field),
});
const run = (...events: StageEvent[]) =>
  events.reduce<StageState>(reduceStage, EMPTY_STAGE);

test("a set and a clear are kept apart, and staging the stored value stages nothing", () => {
  const state = run(
    { type: "stage", label: "set", cells: [set(A, "category_id", "telefono")] },
    { type: "stage", label: "clear", cells: [clear(A, "iva_rate")] },
  );
  expect(state.content.rows[A]).toEqual({
    category_id: { kind: "set", value: "telefono" },
    iva_rate: { kind: "clear" },
  });
  // The stored value spelled another way is the same value.
  const same = run({
    type: "stage",
    label: "set",
    cells: [set(A, "taxable_base", "30")],
  });
  expect(same).toBe(EMPTY_STAGE);
  // Clearing an empty field changes nothing either.
  expect(
    run({ type: "stage", label: "clear", cells: [clear(B, "category_id")] }),
  ).toBe(EMPTY_STAGE);
  // Setting a staged field back to its stored value drops the change.
  const back = reduceStage(state, {
    type: "stage",
    label: "set",
    cells: [set(A, "category_id", "material_oficina")],
  });
  expect(back.content.rows[A]).toEqual({ iva_rate: { kind: "clear" } });
  expect(stagedCount(back.content)).toBe(1);
});

test("undo and redo step per change and per batch", () => {
  const batch: StageCell[] = [
    set(A, "notes", "Factura pedida"),
    set(B, "business_classification", "BUSINESS"),
    set(B, "category_id", "material_oficina"),
  ];
  let state = run(
    { type: "stage", label: "set", cells: [set(A, "category_id", "telefono")] },
    { type: "stage", label: "paste", cells: batch },
  );
  expect(stagedCount(state.content)).toBe(4);
  state = reduceStage(state, { type: "undo" });
  expect(stagedCount(state.content)).toBe(1);
  expect(state.redo.map((entry) => entry.label)).toEqual(["paste"]);
  state = reduceStage(state, { type: "undo" });
  expect(stagedCount(state.content)).toBe(0);
  state = reduceStage(state, { type: "undo" });
  expect(stagedCount(state.content)).toBe(0);
  state = reduceStage(state, { type: "redo" });
  state = reduceStage(state, { type: "redo" });
  expect(stagedCount(state.content)).toBe(4);
  // A new change after an undo drops what could be redone.
  state = reduceStage(state, { type: "undo" });
  state = reduceStage(state, {
    type: "stage",
    label: "set",
    cells: [set(B, "notes", "Otra")],
  });
  expect(state.redo).toEqual([]);
  expect(state.content.rows[B]).toEqual({
    notes: { kind: "set", value: "Otra" },
  });
});

test("revert a cell, revert a movement, and discard everything undoably", () => {
  const archive: StagedAction = {
    id: "act-1",
    kind: "archive",
    transactionId: A,
    reason: "",
  };
  let state = run(
    {
      type: "stage",
      label: "paste",
      cells: [set(A, "category_id", "telefono"), set(A, "notes", "Nota")],
    },
    { type: "stage_action", action: archive },
    { type: "stage", label: "set", cells: [set(B, "notes", "B")] },
  );
  state = reduceStage(state, { type: "revert_cell", id: A, field: "notes" });
  expect(state.content.rows[A]).toEqual({
    category_id: { kind: "set", value: "telefono" },
  });
  expect(state.undo.at(-1)?.label).toBe("revert_cell");
  state = reduceStage(state, { type: "revert_movement", id: A });
  expect(state.content.rows[A]).toBeUndefined();
  expect(state.content.actions).toEqual([]);
  state = reduceStage(state, { type: "undo" });
  expect(state.content.actions).toEqual([archive]);
  state = reduceStage(state, { type: "discard" });
  expect(stagedCount(state.content)).toBe(0);
  state = reduceStage(state, { type: "undo" });
  expect(stagedCount(state.content)).toBe(3);
});

test("a new movement keeps one random idempotency key through every edit", () => {
  const first = newIdempotencyKey();
  const second = newIdempotencyKey();
  expect(first).toMatch(/^desktop-add-[0-9a-f]{32}$/);
  expect(first).not.toBe(second);
  const fixed = newDraft((bytes) => bytes.fill(171));
  expect(fixed.idempotencyKey).toBe(`desktop-add-${"ab".repeat(16)}`);
  // Nothing is assumed: no direction, no account, no classification.
  expect(fixed.fields).toEqual({});
  let state = run({ type: "add_draft", draft: fixed });
  state = reduceStage(state, {
    type: "edit_draft",
    key: fixed.key,
    field: "amount",
    value: "12.5",
  });
  state = reduceStage(state, {
    type: "edit_draft",
    key: fixed.key,
    field: "description",
    value: "Taxi",
  });
  expect(state.content.drafts[0]).toEqual({
    ...fixed,
    fields: { amount: "12.5", description: "Taxi" },
  });
  state = reduceStage(state, { type: "undo" });
  expect(state.content.drafts[0]?.fields).toEqual({ amount: "12.5" });
  expect(state.content.drafts[0]?.idempotencyKey).toBe(fixed.idempotencyKey);
});

test("an apply clears undo; the rebase keeps only what did not save", () => {
  const link: StagedAction = {
    id: "link-1",
    kind: "link",
    transactionId: B,
    invoiceId: "inv-1",
  };
  const draft = newDraft();
  let state = run(
    {
      type: "stage",
      label: "paste",
      cells: [
        set(A, "category_id", "telefono"),
        set(A, "notes", "Nota"),
        set(B, "description", "TAXI"),
      ],
    },
    { type: "stage_action", action: link },
    { type: "add_draft", draft },
  );
  state = reduceStage(state, { type: "apply_started" });
  expect(state.undo).toEqual([]);
  expect(state.redo).toEqual([]);
  expect(state.applied).toBe(true);
  state = reduceStage(state, {
    type: "rebase",
    keep: { rows: { [A]: ["notes"] }, drafts: [draft.key], actions: [] },
  });
  expect(state.content).toEqual({
    rows: { [A]: { notes: { kind: "set", value: "Nota" } } },
    drafts: [draft],
    actions: [],
  });
  // Nothing saved comes back on undo.
  expect(reduceStage(state, { type: "undo" })).toBe(state);
  // A change staged afterwards is undoable again.
  state = reduceStage(state, {
    type: "stage",
    label: "set",
    cells: [set(B, "notes", "Luego")],
  });
  expect(state.applied).toBe(false);
  expect(reduceStage(state, { type: "undo" }).content.rows[B]).toBeUndefined();
});

test("a new id is followed everywhere the movement is named", () => {
  const NEW = hexId("new");
  const merge: StagedAction = {
    id: "merge-1",
    kind: "merge",
    childIds: [A, B],
    reason: "",
  };
  const link: StagedAction = {
    id: "link-1",
    kind: "link",
    transactionId: A,
    invoiceId: "inv-1",
  };
  let state = run(
    { type: "stage", label: "set", cells: [set(A, "notes", "Nota")] },
    { type: "stage_action", action: link },
    { type: "stage_action", action: merge },
  );
  state = reduceStage(state, { type: "rekey", from: A, to: NEW });
  expect(state.content.rows[A]).toBeUndefined();
  expect(state.content.rows[NEW]).toEqual({
    notes: { kind: "set", value: "Nota" },
  });
  expect(state.content.actions).toEqual([
    { ...link, transactionId: NEW },
    { ...merge, childIds: [NEW, B] },
  ]);
});

test("the effective row is the stored row plus its changes; identity fields are named", () => {
  const changes = {
    taxable_base: { kind: "clear" as const },
    category_id: { kind: "set" as const, value: "telefono" },
  };
  const facts = effectiveFacts(rowA, changes);
  expect(facts.taxable_base).toBeNull();
  expect(facts.category_id).toBe("telefono");
  expect(facts.iva_rate).toBe("0.21");
  // Not in the read: unknown, not empty.
  expect(facts.own_account_id).toBeUndefined();
  // The stored row is untouched.
  expect(rowA.transaction.taxable_base).toBe("30.00");

  expect(
    changesIdentity(rowA, { amount: { kind: "set", value: "36.3" } }),
  ).toEqual([]);
  expect(
    changesIdentity(rowA, { amount: { kind: "set", value: "40" } }),
  ).toEqual(["amount"]);
  expect(
    changesIdentity(rowA, { description: { kind: "set", value: "OTRA" } }),
  ).toEqual(["description"]);
  // A booked date behind a value date is not the effective date.
  const valued = movement(A, { value_date: "2026-10-06" });
  expect(
    changesIdentity(valued, {
      booked_date: { kind: "set", value: "2026-10-01" },
    }),
  ).toEqual([]);
  expect(
    changesIdentity(rowA, {
      booked_date: { kind: "set", value: "2026-10-01" },
    }),
  ).toEqual(["booked_date"]);
  expect(
    changesIdentity(rowA, { own_account_id: { kind: "set", value: "acc-02" } }),
  ).toEqual(["own_account_id"]);
});
