import { expect, test } from "@playwright/test";
import schemas from "@fixtures/ledger-result-schemas/ledgerResultSchemas.json" with { type: "json" };
import type { JsonObject, LedgerDefinitionId } from "../src/shell/ledger";

// The scenario ledger answers in the shape its operations serve. Each answer
// the host gives is held to the JSON Schema of the result model the operation
// registers, recorded from the backend beside the other window projections:
// a field the operation now serves that the host does not answer, or an
// answer with a field the operation does not serve, fails here and names the
// path, so the next contract addition cannot reach the captures unnoticed.
// The scenario ledger needs a window; a bare one stands in for it here. No
// page is opened.

const stand = globalThis as unknown as { window?: unknown };
stand.window = {
  location: { search: "" },
  setTimeout: globalThis.setTimeout,
};
const { ledgerFixture } = await import("../src/dev/ledgerFixture");

type Schema = {
  $ref?: string;
  anyOf?: Schema[];
  type?: string | string[];
  properties?: Record<string, Schema>;
  required?: string[];
  additionalProperties?: boolean | Schema;
  items?: Schema;
  prefixItems?: Schema[];
  enum?: unknown[];
  const?: unknown;
  $defs?: Record<string, Schema>;
};

const kindOf = (value: unknown) =>
  value === null
    ? "null"
    : Array.isArray(value)
      ? "array"
      : Number.isInteger(value)
        ? "integer"
        : typeof value;

/** What an answer lacks of, or adds to, a schema, as `path: reason` lines. */
function violations(
  value: unknown,
  schema: Schema,
  root: Schema,
  path: string,
): string[] {
  if (schema.$ref) {
    const name = schema.$ref.replace("#/$defs/", "");
    const target = root.$defs?.[name];
    return target
      ? violations(value, target, root, path)
      : [`${path}: unresolved ${schema.$ref}`];
  }
  if (schema.anyOf) {
    const attempts = schema.anyOf.map((option) =>
      violations(value, option, root, path),
    );
    return attempts.some((found) => found.length === 0)
      ? []
      : [
          `${path}: matches none of its options (${attempts.flat().join("; ")})`,
        ];
  }
  if (schema.const !== undefined)
    return value === schema.const ? [] : [`${path}: not ${schema.const}`];
  if (schema.enum)
    return schema.enum.includes(value) ? [] : [`${path}: not in its set`];
  const kind = kindOf(value);
  const types = schema.type === undefined ? [] : [schema.type].flat();
  const fits =
    types.length === 0 ||
    types.includes(kind) ||
    (kind === "integer" && types.includes("number"));
  if (!fits) return [`${path}: is ${kind}, not ${types.join(" or ")}`];
  if (kind === "array") {
    const items = value as unknown[];
    return items.flatMap((item, index) => {
      const at = schema.prefixItems?.[index] ?? schema.items;
      return at ? violations(item, at, root, `${path}[${index}]`) : [];
    });
  }
  if (kind !== "object" || !schema.properties) return [];
  const object = value as Record<string, unknown>;
  const found: string[] = [];
  for (const name of schema.required ?? [])
    if (!(name in object)) found.push(`${path}.${name}: not answered`);
  for (const [name, member] of Object.entries(object)) {
    const known = schema.properties[name];
    if (known)
      found.push(...violations(member, known, root, `${path}.${name}`));
    else if (schema.additionalProperties === false)
      found.push(`${path}.${name}: not served`);
  }
  return found;
}

const served = schemas as unknown as Record<string, Schema>;
const answerViolations = (definition: string, answer: unknown) =>
  violations(answer, served[definition]!, served[definition]!, definition);

test("a missing field and an unserved field both fail the check", () => {
  const complete = {
    profile_id: "00000000-0000-4000-8000-000000000000",
    action: "view",
    tax_identifier: "X",
    country_code: null,
    evidenced_scope: null,
    facts: null,
    resolution: null,
    recorded: null,
    withdrawn: null,
    changed: false,
    conflict_context: null,
    provincia_code: null,
    provincia_choices: [],
    filing_name: null,
    findings: [],
    filing_name_slots: [],
    filing_name_part_limits: [],
  };
  expect(answerViolations("ledger.counterparty", complete)).toEqual([]);
  const short: Record<string, unknown> = { ...complete };
  delete short.provincia_choices;
  expect(answerViolations("ledger.counterparty", short)).toEqual([
    "ledger.counterparty.provincia_choices: not answered",
  ]);
  expect(
    answerViolations("ledger.counterparty", { ...complete, extra: 1 }),
  ).toEqual(["ledger.counterparty.extra: not served"]);
});

const TAX = "B12345674";
/** Requests that carry no year, edition or tax fact of their own. */
const ASKS: [LedgerDefinitionId, JsonObject][] = [
  ["ledger.counterparty", { action: "view", tax_identifier: TAX }],
  [
    "ledger.counterparty",
    {
      action: "confirm",
      tax_identifier: TAX,
      territorial_scope: "es_mainland",
      asserted_by: "Test",
    },
  ],
  ["ledger.counterparty", { action: "view", tax_identifier: TAX }],
  [
    "ledger.counterparty",
    {
      action: "filing_name",
      tax_identifier: TAX,
      party_kind: "entity",
      razon_social: "Synthetic SL",
      asserted_by: "Test",
    },
  ],
  ["ledger.counterparty", { action: "view", tax_identifier: TAX }],
  ["ledger.list", { output_language: "en" }],
  ["ledger.list", { output_language: "hu", limit: 5 }],
  ["ledger.rule.list", {}],
  ["ledger.ratios.validate", {}],
  ["ledger.participation.rebuild", {}],
  ["ledger.llm-diagnostics", { low_confidence_threshold: { decimal: "0.5" } }],
];

test("every answer the scenario ledger gives is what its operation serves", async () => {
  const port = ledgerFixture({
    say: () => undefined,
    wait: async () => undefined,
    signedIn: () => true,
    shape: "fixture",
  });
  for (const [definition, request] of ASKS) {
    const outcome = await port
      .submit(definition, request)
      .catch((error: unknown) => {
        throw new Error(
          `${definition} ${JSON.stringify(request)} was refused: ${JSON.stringify(error)}`,
        );
      });
    expect(outcome.kind, `${definition} ${JSON.stringify(request)}`).toBe(
      "settled",
    );
    if (outcome.kind !== "settled") continue;
    expect(answerViolations(definition, outcome.result), definition).toEqual(
      [],
    );
  }
});

test("a counterparty's provincia is stated from the served choices and refused otherwise", async () => {
  const port = ledgerFixture({
    say: () => undefined,
    wait: async () => undefined,
    signedIn: () => true,
    shape: "fixture",
  });
  const view = await port.submit("ledger.counterparty", {
    action: "view",
    tax_identifier: TAX,
  });
  if (view.kind !== "settled") throw new Error("the view did not settle");
  const choices = view.result.provincia_choices as { code: string }[];
  expect(choices.length).toBeGreaterThan(0);
  const stated = await port.submit("ledger.counterparty", {
    action: "provincia",
    tax_identifier: TAX,
    provincia_code: choices[0]!.code,
    asserted_by: "Test",
  });
  if (stated.kind !== "settled")
    throw new Error("the statement did not settle");
  expect(stated.result.provincia_code).toBe(choices[0]!.code);
  expect(answerViolations("ledger.counterparty", stated.result)).toEqual([]);
  await expect(
    port.submit("ledger.counterparty", {
      action: "provincia",
      tax_identifier: TAX,
      provincia_code: "ZZ",
      asserted_by: "Test",
    }),
  ).rejects.toMatchObject({ reason: "invalid" });
});

test("every listed movement answers as the list serves it, a served retención included", async () => {
  for (const shape of ["fixture", "withholding"] as const) {
    const port = ledgerFixture({
      say: () => undefined,
      wait: async () => undefined,
      signedIn: () => true,
      shape,
    });
    const outcome = await port.submit("ledger.list", { limit: 500 });
    if (outcome.kind !== "settled") throw new Error("the list did not settle");
    expect(answerViolations("ledger.list", outcome.result), shape).toEqual([]);
    const practised = outcome.result.rows.filter(
      (row) => row.withholding.length > 0,
    );
    expect(practised.length > 0, shape).toBe(shape === "withholding");
  }
});
