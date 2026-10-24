import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
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
  restaged,
  restoreIntent,
  UNPLACED_PAGE,
  valueIntent,
  WORKING_FIGURES_PAGE,
  type StagedEdit,
} from "../src/components/modelo/form/session";
import type {
  ModeloWorkbenchFormProjectionV1,
  PublicModeloFormField,
} from "../src/shell/modeloContract";

// The form's working state over the envelopes the application read for a
// synthetic taxpayer: where each box is drawn, the address an edit of it
// takes, and the submission the staged edits make. No page is opened.

const envelope = (name: string) =>
  JSON.parse(
    readFileSync(
      resolve(import.meta.dirname, `../src/dev/fixtures/modelo/${name}.json`),
      "utf8",
    ),
  ) as ModeloWorkbenchFormProjectionV1;

const m130 = envelope("modelo-130-1T-en");
const m303 = envelope("modelo-303-1T-en");
const m390 = envelope("modelo-390-0A-en");

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
  expect(m390.admitted_baseline).toBeNull();
  expect(editsAdmitted(m390)).toBe(false);
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
