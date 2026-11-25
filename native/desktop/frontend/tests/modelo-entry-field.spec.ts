import { expect, test } from "@playwright/test";
import {
  entryField,
  readOnlyReason,
  takesEntry,
} from "../src/components/modelo/form/entryField";
import type {
  ModeloEditValueGrammarV1,
  ModeloEditWritableScalarSurfaceEntryV1,
} from "../src/shell/modeloContract/modeloEditWork";
import type { PublicModeloFormField } from "../src/shell/modeloContract/modeloWorkForm";
import type { Translate } from "../src/shell/strings";

// Which editor an address takes, from the grammar the application serves. The
// grammars are the shapes its projections produce: a box's own, a binding's,
// and a corrected box's, which is read as a figure whatever the box prints.
// That the `1` and `0` here are what the application reads is proved against
// its parser in its own tests. No page is opened.

const t = ((key: string) => `<${key}>`) as Translate;

const grammar = (
  data_type: string,
  over: Partial<ModeloEditValueGrammarV1> = {},
): ModeloEditValueGrammarV1 => ({
  data_type,
  family: "text",
  channel: "text",
  max_fraction_digits: null,
  sign: "any",
  minimum: null,
  maximum: null,
  choices: null,
  min_length: null,
  max_length: null,
  pattern: null,
  ratio_unit: null,
  money_operand_bound: false,
  required: false,
  constraints_declared: false,
  ...over,
});
const figure = (
  data_type: string,
  over: Partial<ModeloEditValueGrammarV1> = {},
) => grammar(data_type, { family: "decimal", channel: "decimal", ...over });

const YES_NO = {
  kind: "choice",
  choices: [
    { value: "", label: "—" },
    { value: "1", label: "<desktop.ledger.form.yes>" },
    { value: "0", label: "<desktop.ledger.form.no>" },
  ],
};

/** A box's own grammar by its registry data type, keyed by the generated type
 * so a type the registry gains has to be added here. */
const BY_TYPE: Record<
  ModeloEditWritableScalarSurfaceEntryV1["data_type"],
  [ModeloEditValueGrammarV1, unknown]
> = {
  decimal: [figure("decimal"), { kind: "decimal" }],
  money: [figure("money"), { kind: "money" }],
  integer: [
    grammar("integer", { family: "integer", channel: "decimal" }),
    { kind: "integer" },
  ],
  ratio: [figure("ratio", { ratio_unit: "undeclared" }), { kind: "decimal" }],
  year: [figure("year"), { kind: "year" }],
  boolean: [
    grammar("boolean", { family: "boolean", channel: "decimal" }),
    YES_NO,
  ],
  date: [grammar("date"), { kind: "date" }],
  text: [grammar("text"), { kind: "text" }],
  nif: [grammar("nif"), { kind: "taxId" }],
  period_code: [grammar("period_code"), { kind: "text", mono: true }],
  country_code: [grammar("country_code"), { kind: "country" }],
  iban: [grammar("iban"), { kind: "iban" }],
  name: [grammar("name"), { kind: "text" }],
  nif_iva: [grammar("nif_iva"), { kind: "taxId" }],
  ccaa_code: [grammar("ccaa_code"), { kind: "text", mono: true }],
  province_code: [grammar("province_code"), { kind: "text", mono: true }],
  postal_code: [grammar("postal_code"), { kind: "text", mono: true }],
  municipality_code: [
    grammar("municipality_code"),
    { kind: "text", mono: true },
  ],
  bic: [grammar("bic"), { kind: "bic" }],
};

for (const [type, [served, editor]] of Object.entries(BY_TYPE))
  test(`a ${type} box takes its own editor`, () => {
    expect(takesEntry(served)).toBe(true);
    expect(entryField(t, served)).toEqual(editor);
  });

test("a ratio has a percent box only where its grammar says percent", () => {
  expect(
    entryField(t, figure("ratio", { ratio_unit: "percent", maximum: "100" })),
  ).toEqual({ kind: "percent", unit: "points" });
  for (const unit of ["fraction", "undeclared"] as const)
    expect(entryField(t, figure("ratio", { ratio_unit: unit }))).toEqual({
      kind: "decimal",
    });
});

test("a served word stands beside its code, whatever the box holds", () => {
  const offered = grammar("text", {
    choices: [
      { code: "28", word: "application.modelo.edit_choice.province_code.28" },
      { code: "1T", word: "some.other.family.1T" },
      { code: "99", word: null },
    ],
  });
  expect(entryField(t, offered)).toEqual({
    kind: "choice",
    choices: [
      { value: "", label: "—" },
      {
        value: "28",
        label: "28 · <application.modelo.edit_choice.province_code.28>",
      },
      { value: "1T", label: "1T · <some.other.family.1T>" },
      { value: "99", label: "99" },
    ],
  });
});

test("a blank the design declares is the one empty row, not a second", () => {
  const offered = grammar("text", {
    choices: [
      { code: "X", word: null },
      { code: "", word: null },
    ],
  });
  expect(entryField(t, offered)).toEqual({
    kind: "choice",
    choices: [
      { value: "", label: "—" },
      { value: "X", label: "X" },
    ],
  });
});

test("a box with declared choices offers exactly those codes, untranslated", () => {
  const offered = grammar("province_code", {
    choices: [
      { code: "08", word: null },
      { code: "17", word: null },
    ],
  });
  expect(entryField(t, offered)).toEqual({
    kind: "choice",
    choices: [
      { value: "", label: "—" },
      { value: "08", label: "08" },
      { value: "17", label: "17" },
    ],
  });
});

test("a binding's token is typed as declared", () => {
  expect(takesEntry(grammar("enum"))).toBe(true);
  expect(entryField(t, grammar("enum"))).toEqual({ kind: "text", mono: true });
});

test("a corrected yes or no is a choice with its answers, not an empty list", () => {
  const corrected = figure("boolean", { max_fraction_digits: 6 });
  expect(takesEntry(corrected)).toBe(true);
  expect(entryField(t, corrected)).toEqual(YES_NO);
});

test("a corrected box is read as a figure, so it never takes a box whose text is not one", () => {
  for (const type of ["date", "text", "nif", "iban", "bic", "country_code"])
    expect(entryField(t, figure(type)), type).toEqual({ kind: "decimal" });
  expect(entryField(t, figure("period_code"))).toEqual({ kind: "decimal" });
  expect(entryField(t, figure("year"))).toEqual({ kind: "year" });
});

test("no channel carries a value, whatever its data type", () => {
  for (const [type, family] of [
    ["date", "date"],
    ["year", "integer"],
    ["boolean", "boolean"],
    ["money", "decimal"],
  ] as const)
    expect(
      takesEntry(grammar(type, { family, channel: "unavailable" })),
      type,
    ).toBe(false);
});

test("a type no editor is known for is read-only, never free text", () => {
  expect(takesEntry(grammar("row_set"))).toBe(false);
  expect(takesEntry(figure("row_set"))).toBe(false);
  expect(takesEntry(grammar("constructor"))).toBe(false);
});

test("a yes or no on a text channel takes nothing: neither word nor figure is read there", () => {
  expect(takesEntry(grammar("boolean"))).toBe(false);
});

test("only a box that cannot be typed into says why here", () => {
  const box = (over: Partial<PublicModeloFormField>) =>
    ({ editability_words: "because", ...over }) as PublicModeloFormField;
  expect(readOnlyReason(box({ editability: "not_writable" }))).toBe("because");
  for (const editability of [
    "editable_value",
    "calculated",
    "informational",
    "locked_source",
    "no_admission",
  ] as const)
    expect(readOnlyReason(box({ editability })), editability).toBeNull();
  expect(
    readOnlyReason(
      box({ editability: "not_writable", editability_words: null }),
    ),
  ).toBeNull();
});
