import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import {
  clearIntent,
  confirmIntent,
  editAddress,
  editKey,
  editSubmission,
  editsAdmitted,
  entrySubmission,
  fieldKey,
  placedFields,
  noteMoved,
  priorWithdrawal,
  rebasedEdits,
  rebasedOf,
  removeIntent,
  restaged,
  restoreIntent,
  servedPriorWithdrawal,
  statementEdits,
  statementOf,
  wholeStatements,
  withdrawal,
  UNPLACED_PAGE,
  valueIntent,
  WORKING_FIGURES_PAGE,
  type StagedEdit,
} from "../src/components/modelo/form/session";
import { mayRenew } from "../src/components/modelo/dialogs/operationRun";
import { stagedText } from "../src/components/modelo/form/stagedWords";
import type { Translate } from "../src/shell/strings";
import { MODELO_FIXTURES } from "./support/windowFixtures";
import type {
  ModeloFormCarryAttestation,
  ModeloWorkbenchFormProjectionV1,
  PublicModeloFormField,
} from "../src/shell/modeloContract/modeloWorkForm";
import type { PublicModeloFormPriorValueAttestation } from "../src/shell/modeloContract/modeloWorkFormPart2";

// The form's working state over the envelopes the application read for a
// synthetic taxpayer: where each box is drawn, the address an edit of it
// takes, and the submission the staged edits make. No page is opened.

const envelope = <Read = ModeloWorkbenchFormProjectionV1>(name: string) =>
  JSON.parse(
    readFileSync(new URL(`${name}.json`, MODELO_FIXTURES), "utf8"),
  ) as Read;

const m130 = envelope("modelo-130-1T-en");
const m303 = envelope("modelo-303-1T-en");
const rulesIncomplete = envelope<{ modelo: string; period_code: string }>(
  "scenario-rules-incomplete",
);
const incomplete = envelope(
  `modelo-${rulesIncomplete.modelo}-${rulesIncomplete.period_code}-en`,
);

const box = (e: ModeloWorkbenchFormProjectionV1, number: string) => {
  const found = placedFields(e.form.form).find(
    (placed) => placed.field.box === number,
  );
  if (!found) throw new Error(`box ${number} is not on the form`);
  return found.field;
};

const staged = (
  field: PublicModeloFormField,
  intent: StagedEdit["intent"],
): StagedEdit => ({
  key: editKey(field),
  address: editAddress(field),
  field,
  intent,
  entry: null,
  read: null,
  normalisations: [],
  beforeChanged: false,
});

test("every box of every page is placed once, in reading order", () => {
  const form = m303.form.form;
  const placed = placedFields(form);
  const pages = [
    ...form.pages.map((page) => page.id),
    UNPLACED_PAGE,
    WORKING_FIGURES_PAGE,
  ];
  const order = placed.map((p) => pages.indexOf(p.pageId));
  expect(
    order.every((at, i) => at >= 0 && (i === 0 || at >= order[i - 1]!)),
  ).toBe(true);
  expect(placed.filter((p) => p.pageId === UNPLACED_PAGE)).toHaveLength(
    form.unplaced.length,
  );
  expect(placed.filter((p) => p.pageId === WORKING_FIGURES_PAGE)).toHaveLength(
    form.working_figures.length,
  );
  const grids = form.pages
    .flatMap((page) => page.sections)
    .flatMap((section) => section.blocks)
    .flatMap((block) =>
      block.kind === "grid"
        ? block.rows.flatMap((row) => row.cells.filter((cell) => cell.field))
        : [],
    );
  expect(grids.length).toBeGreaterThan(0);
  for (const cell of grids)
    expect(placed.some((p) => p.field === cell.field)).toBe(true);
});

test("a box fed by a source is staged at the binding the read names", () => {
  const fed = box(m130, "05");
  expect(fed.edit_address.kind).toBe("binding");
  expect(fieldKey(fed)).toBe("c:05");
  expect(editKey(fed)).toBe(
    `b:${fed.edit_address.kind === "binding" ? fed.edit_address.binding_id : ""}`,
  );
  expect(editAddress(fed).kind).toBe("binding");
  expect(valueIntent(fed, "12.00").kind).toBe("set_override_value");
  expect(clearIntent(fed).kind).toBe("remove_override");

  const own = box(m130, "06");
  expect(editAddress(own)).toEqual({ kind: "scalar", casilla_id: "06" });
  expect(valueIntent(own, "12.00").kind).toBe("set_typed_value");
  expect(clearIntent(own).kind).toBe("clear_declared_value");
});

test("restore and confirm are offered only where the read offers them", () => {
  for (const { field } of placedFields(m303.form.form)) {
    const restore = restoreIntent(field);
    expect(restore !== null).toBe(field.restorable);
    const confirm = confirmIntent(field);
    expect(confirm !== null).toBe(
      field.confirmable && field.confirm_value !== null,
    );
    if (confirm && "value" in confirm)
      expect(confirm.value).toEqual(field.confirm_value);
  }
});

test("the staged edits make one submission of typed values only", () => {
  const baseline = m130.admitted_baseline!;
  const own = box(m130, "06");
  const fed = box(m130, "05");
  const input = editSubmission(
    baseline,
    [
      staged(own, valueIntent(own, "1234.56")),
      staged(fed, { kind: "remove_override", change: "restore" }),
    ],
    "es",
  );
  expect(input.output_language).toBe("es");
  expect(input.submission.baseline).toBe(baseline);
  expect(input.submission.mutation_family).toBe(baseline.mutation_family);
  expect(input.submission.scalar_intents).toEqual([
    {
      address: { kind: "scalar", casilla_id: "06" },
      kind: "set_typed_value",
      value: "1234.56",
    },
  ]);
  expect(input.submission.binding_intents).toEqual([
    { address: editAddress(fed), kind: "remove_override" },
  ]);
  expect(input.submission.lexemes).toBeUndefined();
});

test("a carry stated to hold nothing is sent as the statement, with no value", () => {
  const fed = box(m130, "05");
  const statement = {
    kind: "attest_no_amount",
    change: "set",
    family: "renta_negative_general_bases_pending",
    words: "served action",
    effect: "served effect",
  } as const;
  const edit = staged(fed, statement);
  expect(
    editSubmission(m130.admitted_baseline!, [edit], "en").submission
      .binding_intents,
  ).toEqual([{ address: editAddress(fed), kind: "attest_no_amount" }]);
  // The staged edit says what the form served, never words of its own.
  expect(stagedText(((key: string) => key) as Translate, edit)).toBe(
    "served action",
  );
  const open = {
    ...fed,
    takes_typed_value: true,
    origin: "not_imported_yet",
  } as const;
  expect(restaged(edit, open)).toEqual(statement);
  expect(restaged(edit, { ...open, takes_typed_value: false })).toBeNull();
  // An earlier return stored meanwhile supplies the carry: the statement goes.
  expect(restaged(edit, { ...open, origin: "imported" })).toBeNull();
});

// The Renta read places the four carries of earlier negative bases at their
// bindings; the statement over them is shaped as the form serves one.
const m100 = envelope("modelo-100-0A-en");
const carries = placedFields(m100.form.form).filter(
  (placed) =>
    placed.field.edit_address.kind === "binding" &&
    placed.field.edit_address.binding_id.startsWith(
      "renta-base-liquidable-negativa-general-",
    ),
);
const served: ModeloFormCarryAttestation = {
  family: "renta_negative_general_bases_pending",
  binding_ids: carries.map((placed) =>
    placed.field.edit_address.kind === "binding"
      ? placed.field.edit_address.binding_id
      : "",
  ),
  action_words: "served action",
  statement_words: "served statement",
  effect_words: "served effect",
};

test("a statement is staged on every box it names, or on none", () => {
  const placed = placedFields(m100.form.form);
  expect(carries.length).toBeGreaterThan(1);
  const edits = statementEdits(placed, served);
  expect(edits?.map((edit) => editKey(edit.field))).toEqual(
    served.binding_ids.map((id) => `b:${id}`),
  );
  expect(new Set(edits?.map((edit) => statementOf(edit.intent))).size).toBe(1);
  // A binding the form draws nowhere stages none of the statement.
  expect(
    statementEdits(placed, {
      ...served,
      binding_ids: [...served.binding_ids, "not-on-the-form"],
    }),
  ).toBeNull();
});

test("a statement or withdrawal left with some of its boxes is dropped whole", () => {
  const placed = placedFields(m100.form.form);
  const all = new Map(
    (statementEdits(placed, served) ?? []).map((edit) => {
      const made = staged(edit.field, edit.intent);
      return [made.key, made] as const;
    }),
  );
  expect(wholeStatements(all, placed, [served]).dropped).toEqual([]);
  // Served no more, the statement goes from every box.
  expect(wholeStatements(all, placed, []).next.size).toBe(0);
  const part = new Map([...all].slice(1));
  const whole = wholeStatements(part, placed, [served]);
  expect(whole.next.size).toBe(0);
  expect(whole.dropped).toHaveLength(part.size);
});

test("a stated box withdraws its statement from every box it stands on, or from none", () => {
  const stated = (field: PublicModeloFormField): PublicModeloFormField =>
    carries.some((placed) => placed.field === field)
      ? {
          ...field,
          stated_absent: "renta_negative_general_bases_pending",
          clearable: true,
        }
      : field;
  const placed = placedFields(m100.form.form).map((each) => ({
    ...each,
    field: stated(each.field),
  }));
  const boxes = placed.filter((each) => each.field.stated_absent !== null);
  const first = boxes[0]!.field;
  const offer = withdrawal(placed, first, () => true);
  expect(offer?.kind).toBe("offered");
  if (offer?.kind !== "offered") return;
  expect(offer.edits.map((edit) => editKey(edit.field))).toEqual(
    boxes.map((each) => editKey(each.field)),
  );
  for (const edit of offer.edits)
    expect(edit.intent).toEqual({
      kind: "remove_override",
      change: "clear",
      withdraws: "renta_negative_general_bases_pending",
    });
  // One box the baseline does not let be taken out keeps the whole family.
  const last = boxes.at(-1)!.field;
  expect(withdrawal(placed, first, (field) => field !== last)).toEqual({
    kind: "refused",
    field: last,
  });
  // A box whose own removal is not admitted offers no withdrawal.
  expect(withdrawal(placed, first, (field) => field !== first)).toBeNull();
  // A box no statement stands on offers none.
  expect(withdrawal(placed, box(m130, "05"), () => true)).toBeNull();
  // A withdrawal is kept only while the box still holds its statement.
  const held = staged(first, offer.edits[0]!.intent);
  expect(restaged(held, first)).toEqual(offer.edits[0]!.intent);
  expect(restaged(held, { ...first, stated_absent: null })).toBeNull();
});

// The same carries, as one family of earlier returns the application holds
// none of, in placeholder words shaped as the form serves them.
const PRIOR = {
  family: "synthetic-earlier-returns",
  words: "served withdrawal",
  effect: "served withdrawal effect",
};
const carryIds = served.binding_ids;
const priorServed = (
  stated: boolean,
): PublicModeloFormPriorValueAttestation[] =>
  carryIds.map((bindingId) => ({
    binding_id: bindingId,
    edit_address: { kind: "binding", binding_id: bindingId },
    intent: "attest_prior_value",
    family_id: PRIOR.family,
    earlier_filings: [],
    source_words: "served earlier returns",
    action_words: "served action",
    statement_words: "served statement",
    effect_words: "served effect",
    stated,
    admitted: true,
    refusal_reason: null,
    refusal_words: null,
    refusal: null,
    withdrawal: stated
      ? {
          family_id: PRIOR.family,
          binding_ids: [...carryIds].sort(),
          intent: "remove_override",
          action_words: PRIOR.words,
          effect_words: PRIOR.effect,
        }
      : null,
  }));
const statedPrior = (field: PublicModeloFormField): PublicModeloFormField =>
  carries.some((placed) => placed.field === field)
    ? {
        ...field,
        stated_prior_value: {
          source_words: "served earlier returns",
          origin_words: "served origin",
          family_id: PRIOR.family,
        },
        clearable: true,
      }
    : field;

test("a figure stated for earlier returns is sent as the statement with its value", () => {
  const carry = carries[0]!.field;
  const offered: PublicModeloFormField = {
    ...carry,
    takes_typed_value: true,
    statements: [
      {
        intent: "attest_prior_value",
        binding_id: carryIds[0]!,
        action_words: "served action",
        statement_words: "served statement",
        effect_words: "served effect",
        source_words: "served earlier returns",
      },
    ],
  };
  const intent = {
    kind: "attest_prior_value",
    change: "set",
    value: "1234.00",
    comparable: "1234.00",
    family: PRIOR.family,
    words: "served action",
    effect: "served effect",
  } as const;
  const edit = staged(offered, intent);
  expect(
    editSubmission(m100.admitted_baseline!, [edit], "en").submission
      .binding_intents,
  ).toEqual([
    {
      address: editAddress(offered),
      kind: "attest_prior_value",
      value: "1234.00",
    },
  ]);
  // A figure stands alone: it is no statement staged with other boxes.
  expect(statementOf(intent)).toBeNull();
  expect(restaged(edit, offered)).toEqual(intent);
  // A carry that offers the statement no more, as when its earlier return is
  // now held, drops the figure.
  expect(restaged(edit, { ...offered, statements: [] })).toBeNull();
});

test("the figures stated for one family are withdrawn together, or not at all", () => {
  const placed = placedFields(m100.form.form).map((each) => ({
    ...each,
    field: statedPrior(each.field),
  }));
  const withdrawalServed = servedPriorWithdrawal(
    priorServed(true),
    PRIOR.family,
  );
  expect(withdrawalServed).not.toBeNull();
  expect(servedPriorWithdrawal(priorServed(false), PRIOR.family)).toBeNull();
  const offer = priorWithdrawal(placed, withdrawalServed!, () => true);
  expect(offer.kind).toBe("offered");
  if (offer.kind !== "offered") return;
  expect(offer.edits.map((edit) => editKey(edit.field))).toEqual(
    [...carryIds].sort().map((id) => `b:${id}`),
  );
  for (const edit of offer.edits) {
    expect(edit.intent).toEqual({
      kind: "remove_override",
      change: "clear",
      withdrawsPrior: PRIOR,
    });
    expect(statementOf(edit.intent)).toBe(`withdraw-prior:${PRIOR.family}`);
  }
  // One carry the baseline does not let be taken out keeps the whole family.
  const kept = offer.edits.at(-1)!.field;
  expect(
    priorWithdrawal(placed, withdrawalServed!, (field) => field !== kept),
  ).toEqual({
    kind: "refused",
    bindingId: [...carryIds].sort().at(-1),
    field: kept,
  });
  // A carry the form draws nowhere keeps it too.
  expect(
    priorWithdrawal(
      placed,
      { ...withdrawalServed!, binding_ids: ["not-on-the-form"] },
      () => true,
    ),
  ).toEqual({ kind: "refused", bindingId: "not-on-the-form", field: null });
  // Staged on only some of its carries, or served no more, it goes whole.
  const all = new Map(
    offer.edits.map((edit) => {
      const made = staged(edit.field, edit.intent);
      return [made.key, made] as const;
    }),
  );
  expect(wholeStatements(all, placed, [], priorServed(true)).dropped).toEqual(
    [],
  );
  expect(wholeStatements(all, placed, [], []).next.size).toBe(0);
  const part = new Map([...all].slice(1));
  expect(wholeStatements(part, placed, [], priorServed(true)).next.size).toBe(
    0,
  );
  // A withdrawal is kept only while the carry still holds the figure.
  const held = staged(kept, offer.edits.at(-1)!.intent);
  expect(restaged(held, kept)).toEqual(offer.edits.at(-1)!.intent);
  expect(restaged(held, { ...kept, stated_prior_value: null })).toBeNull();
  // The staged withdrawal is said as one.
  expect(stagedText(((key: string) => key) as Translate, held)).toBe(
    "desktop.modelo.statements.withdrawn",
  );
});

test("an entry is read by a preflight carrying only what was typed", () => {
  const baseline = m130.admitted_baseline!;
  const input = entrySubmission(baseline, box(m130, "06"), "1.234,56", "es");
  expect(input.output_language).toBe("es");
  expect(input.submission.scalar_intents).toBeUndefined();
  expect(input.submission.lexemes).toEqual([
    {
      address: { kind: "scalar", casilla_id: "06" },
      entry_locale: "es",
      lexeme: "1.234,56",
    },
  ]);
});

test("a declaration whose edits were refused takes none", () => {
  expect(editsAdmitted(m130)).toBe(true);
  expect(incomplete.admitted_baseline).toBeNull();
  expect(editsAdmitted(incomplete)).toBe(false);
});

test("a preflight's report keeps a set value only where the box still takes it as a change", () => {
  const own = box(m130, "06");
  const typed = staged(own, valueIntent(own, "150.00", "150"));
  // The box still takes a typed value: the edit is staged on it as it is now.
  expect(restaged(typed, { ...own, takes_typed_value: true })).toEqual(
    valueIntent(own, "150.00", "150"),
  );
  // The box no longer takes typing: the edit is dropped.
  expect(restaged(typed, { ...own, takes_typed_value: false })).toBeNull();
  // The box already holds the same figure as the filer's own: nothing to change.
  expect(
    restaged(typed, { ...own, takes_typed_value: true, own_value: "150" }),
  ).toBeNull();
  // A figure the application did not compare is never assumed equal.
  expect(
    restaged(staged(own, valueIntent(own, "150")), {
      ...own,
      takes_typed_value: true,
      own_value: "150",
    }),
  ).not.toBeNull();
});

test("a confirmed value is dropped once the box holds it as the filer's own", () => {
  const own = box(m130, "06");
  const assumed = {
    ...own,
    confirmable: true,
    confirm_value: "80",
    confirm_comparable: "80",
  };
  const confirm = confirmIntent(assumed);
  if (!confirm) throw new Error("the assumed box offers no confirmation");
  expect(confirm).toEqual(valueIntent(assumed, "80", "80"));
  const held = staged(assumed, confirm);
  expect(
    restaged(held, { ...own, takes_typed_value: true, own_value: "80" }),
  ).toBeNull();
  expect(
    restaged(held, { ...own, takes_typed_value: true, own_value: null }),
  ).not.toBeNull();
});

test("a preflight is told each held change at its edit address, an apply none", () => {
  const baseline = m130.admitted_baseline!;
  const own = box(m130, "06");
  const fed = box(m130, "05");
  const edits = [
    staged(own, valueIntent(own, "1")),
    staged(fed, { kind: "remove_override", change: "restore" }),
  ];
  const checked = editSubmission(baseline, edits, "en", true).submission;
  expect(checked.held).toEqual([
    {
      address: editAddress(own),
      kind: "set",
      held_state: own.state_digest,
    },
    {
      address: editAddress(fed),
      kind: "restore",
      held_state: fed.state_digest,
    },
  ]);
  expect(editSubmission(baseline, edits, "en").submission.held).toBeUndefined();
});

test("a renewal keeps a clear or a restore only where the box still offers it", () => {
  const own = box(m130, "06");
  const clear = staged(own, clearIntent(own));
  expect(restaged(clear, { ...own, clearable: true })).toEqual(
    clearIntent(own),
  );
  expect(restaged(clear, { ...own, clearable: false })).toBeNull();
  const fed = box(m130, "05");
  const restore = staged(fed, { kind: "remove_override", change: "restore" });
  expect(restaged(restore, { ...fed, restorable: false })).toBeNull();
  expect(restaged(restore, { ...fed, restorable: true })).toEqual(
    restoreIntent({ ...fed, restorable: true }),
  );
});

test("a staged intent says the kind of change a renewal is told", () => {
  const own = box(m130, "06");
  const fed = box(m130, "05");
  expect(valueIntent(own, "1").change).toBe("set");
  expect(clearIntent(own).change).toBe("clear");
  expect(clearIntent(fed).change).toBe("clear");
  expect(restoreIntent({ ...fed, restorable: true })?.change).toBe("restore");
});

test("the filer's own entry or clear is taken out only where the read offers it, and said as a removal", () => {
  const own = box(m130, "06");
  expect(removeIntent({ ...own, removable: false })).toBeNull();
  const remove = removeIntent({ ...own, removable: true });
  expect(remove).toEqual({ kind: "restore_source_value", change: "remove" });
  if (!remove) throw new Error("the box offers removal");
  const held = staged({ ...own, removable: true }, remove);
  expect(restaged(held, { ...own, removable: true })).toEqual(remove);
  expect(restaged(held, { ...own, removable: false })).toBeNull();
  const words: Translate = (key) => key;
  expect(stagedText(words, held)).toBe("workspace.modelo.staged.remove");
  expect(
    stagedText(
      words,
      staged(own, { kind: "restore_source_value", change: "restore" }),
    ),
  ).toBe("workspace.modelo.staged.restore");
});

test("the notice counts each box a report moved once, until acknowledged", () => {
  const empty = new Map<string, "changed" | "dropped">();
  expect(rebasedOf(empty)).toBeNull();
  // Two checks in a row report box 08 changed: it is one box that changed.
  const twice = noteMoved(noteMoved(empty, [["s:08", "changed"]]), [
    ["s:08", "changed"],
  ]);
  expect(rebasedOf(twice)).toEqual({ changed: 1, dropped: 0 });
  // A box first changed and then dropped counts as dropped, once.
  const thenDropped = noteMoved(twice, [
    ["s:08", "dropped"],
    ["s:06", "dropped"],
  ]);
  expect(rebasedOf(thenDropped)).toEqual({ changed: 0, dropped: 2 });
  // A dropped box reported changed later stays dropped.
  expect(rebasedOf(noteMoved(thenDropped, [["s:08", "changed"]]))).toEqual({
    changed: 0,
    dropped: 2,
  });
});

test("what a report moved is kept by the box's own address, which a restage never changes", () => {
  const own = box(m130, "08");
  const edit = staged(own, valueIntent(own, "250"));
  const sent = editAddress(own);
  if (sent.kind !== "scalar" && sent.kind !== "binding")
    throw new Error("box 08 has no held edit address");
  // On the read the report applies to, the box is edited at a binding.
  const now = {
    ...own,
    takes_typed_value: true,
    edit_address: { kind: "binding" as const, binding_id: "synthetic.08" },
  };
  const placed = placedFields(m130.form.form).map((p) =>
    p.field.box === "08" ? { ...p, field: now } : p,
  );
  const first = rebasedEdits(
    new Map([[edit.key, edit]]),
    [{ address: sent, kind: "set", outcome: "changed" }],
    placed,
  );
  const [restagedEdit] = [...first.next.values()];
  expect(restagedEdit?.address).toEqual({
    kind: "binding",
    binding_id: "synthetic.08",
    row_identity: null,
  });
  expect(first.found).toEqual([[fieldKey(own), "changed"]]);
  // A second report names the edit at its new address; the box is the same.
  const second = rebasedEdits(
    first.next,
    [
      {
        address: {
          kind: "binding",
          binding_id: "synthetic.08",
          row_identity: null,
        },
        kind: "set",
        outcome: "changed",
      },
    ],
    placed,
  );
  expect(second.found).toEqual([[fieldKey(own), "changed"]]);
  expect(
    rebasedOf(noteMoved(noteMoved(new Map(), first.found), second.found)),
  ).toEqual({ changed: 1, dropped: 0 });
});

test("only the latest check, on the baseline held now, may renew it", () => {
  const held = m130.admitted_baseline!;
  const other = { ...held, baseline_id: `${held.baseline_id}-other` };
  expect(mayRenew({ ticket: 3, latest: 3, stale: held, current: held })).toBe(
    true,
  );
  // A check overtaken by a later one leaves the renewal to it.
  expect(mayRenew({ ticket: 2, latest: 3, stale: held, current: held })).toBe(
    false,
  );
  // A check made on a baseline the review no longer holds renews nothing.
  expect(mayRenew({ ticket: 3, latest: 3, stale: held, current: other })).toBe(
    false,
  );
  expect(mayRenew({ ticket: 3, latest: 3, stale: held, current: null })).toBe(
    false,
  );
});

test("a typed value is said as the application read it, or as typed where it said nothing", () => {
  const field = box(m130, "06");
  const typed = {
    ...staged(field, valueIntent(field, "1234.56")),
    entry: "1234,56",
  };
  const t = ((key: string) => key) as Translate;
  expect(stagedText(t, typed)).toBe("1234,56");
  expect(stagedText(t, { ...typed, read: "1,234.56 €" })).toBe("1,234.56 €");
});
