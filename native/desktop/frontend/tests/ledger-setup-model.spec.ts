import { expect, test } from "@playwright/test";
import type { LedgerRuleRow } from "../src/shell/ledgerSetup";
import { planApply, ruleApplyClashes } from "../src/shell/ledgerPlan";
import {
  actionRows,
  EMPTY_STAGE,
  reduceStage,
  type StagedAction,
} from "../src/shell/ledgerStage";
import {
  callFailure,
  callOutcome,
  commonWords,
  correctionOf,
  ibanProblem,
  parseObject,
  parsePoints,
  patternMatcher,
  patternMatches,
  patternWords,
  priorityAt,
  reorderWrites,
  ruleOrder,
  rulePrefill,
  wholeYear,
  wordsPattern,
} from "../src/components/ledger/setup/setupModel";
import { hexId, movement } from "./support/ledger";

// The Setup sections' pure decisions and the staged rule run. No page is
// opened.

const rule = (
  name: string,
  priority: number,
  created: string,
  pattern = name.toUpperCase(),
): LedgerRuleRow => ({
  rule_id: hexId(name),
  description_pattern: pattern,
  classification: "BUSINESS",
  category_id: null,
  priority,
  actor: "person",
  created_at: created,
});

test("plain words become a pattern that finds them and nothing else, and back", () => {
  const pattern = wordsPattern("  Papelería  (Trazo) 1.5+ ");
  expect(pattern).toBe("Papelería\\s+\\(Trazo\\)\\s+1\\.5\\+");
  expect(patternWords(pattern)).toBe("Papelería (Trazo) 1.5+");
  const matcher = patternMatcher(pattern)!;
  expect(matcher.test("COMPRA PAPELERÍA   (TRAZO) 1.5+ CENTRO")).toBe(true);
  // The dot is a dot, not any character.
  expect(matcher.test("PAPELERÍA (TRAZO) 1x5+")).toBe(false);
  // A rule typed by hand with plain spaces is plain words too.
  expect(patternWords("CUOTA AUTONOMOS")).toBe("CUOTA AUTONOMOS");
  // One written in the expression grammar is not.
  expect(patternWords("^CUOTA.*TGSS$")).toBeNull();
  expect(patternWords("A\\dB")).toBeNull();
  // Grammar this window reads differently is not tried here.
  expect(patternMatcher("(?P<name>X)")).toBeNull();
  expect(patternMatcher("(?i)x")).toBeNull();
  expect(patternMatcher("[unclosed")).toBeNull();
});

test("a pattern matches the loaded active movements still to classify", () => {
  const rows = [
    movement("a", { description: "RECIBO ALBOR MOVIL" }),
    movement("b", {
      description: "FIBRA ALBOR",
      business_classification: "BUSINESS",
    }),
    movement("c", { description: "ALBOR", lifecycle_state: "ARCHIVED" }),
    movement("d", { description: "OTRA COSA" }),
  ];
  expect(patternMatches(wordsPattern("albor"), rows)).toEqual(["a"]);
  expect(patternMatches("(?P<x>albor)", rows)).toBeNull();
});

test("a rule from a selection starts from what the movements share", () => {
  expect(
    commonWords([
      "TRANSFERENCIA COOPERATIVA OLIVAR DEL SUR FRA 2026-058",
      "TRANSFERENCIA COOPERATIVA OLIVAR DEL SUR FRA 2026-055",
    ]),
  ).toBe("TRANSFERENCIA COOPERATIVA OLIVAR DEL SUR FRA");
  // The longest run of whole words both hold, in order.
  expect(commonWords(["PAGO RECIBO LUZ CASA", "RECIBO LUZ OFICINA PAGO"])).toBe(
    "RECIBO LUZ",
  );
  expect(commonWords(["ALFA", "BETA"])).toBe("");
  expect(commonWords([])).toBe("");

  const rows = new Map(
    [
      movement("a", {
        description: "SOFTNUBE SUSCRIPCION 01",
        business_classification: "BUSINESS",
        category_id: "software_suscripcion",
      }),
      movement("b", {
        description: "SOFTNUBE SUSCRIPCION 02",
        business_classification: "BUSINESS",
        category_id: "software_suscripcion",
      }),
      movement("c", { description: "SOFTNUBE SUSCRIPCION 03" }),
    ].map((row) => [row.transaction.transaction_id, row]),
  );
  expect(rulePrefill({ ids: ["a", "b"] }, rows)).toEqual({
    words: "SOFTNUBE SUSCRIPCION",
    classification: "BUSINESS",
    categoryId: "software_suscripcion",
  });
  // Where they disagree, nothing is chosen for the person.
  expect(rulePrefill({ ids: ["a", "c"] }, rows)).toEqual({
    words: "SOFTNUBE SUSCRIPCION",
    classification: null,
    categoryId: null,
  });
});

test("the rule order follows priority, then age, and a place takes the number that holds it", () => {
  const first = rule("first", 10, "2026-01-01T00:00:00Z");
  const tie = rule("tie", 10, "2026-01-02T00:00:00Z");
  const last = rule("last", 50, "2026-01-01T00:00:00Z");
  const ordered = ruleOrder([last, tie, first]);
  expect(ordered.map((found) => found.rule_id)).toEqual(
    [first, tie, last].map((found) => found.rule_id),
  );
  // A new rule is the newest: at the priority of the rule before it, it runs
  // after it.
  expect(priorityAt(ordered, 3)).toBe(60);
  expect(priorityAt([], 0)).toBe(100);
  expect(priorityAt(ordered, 2)).toBe(20);
  expect(priorityAt(ordered, 0)).toBe(1);
  // Between two rules of the same priority no number fits.
  expect(priorityAt(ordered, 1)).toBeNull();
});

test("moving a rule writes it once where a number fits, and numbers all again where none does", () => {
  const a = rule("a", 10, "2026-01-01T00:00:00Z");
  const b = rule("b", 20, "2026-01-02T00:00:00Z");
  const c = rule("c", 30, "2026-01-03T00:00:00Z");
  expect(reorderWrites([a, b, c], 2, 1)).toEqual([{ rule: c, priority: 19 }]);
  expect(reorderWrites([a, b, c], 0, 2)).toEqual([{ rule: a, priority: 40 }]);
  expect(reorderWrites([a, b, c], 1, 1)).toEqual([]);
  const x = rule("x", 1, "2026-01-01T00:00:00Z");
  const y = rule("y", 1, "2026-01-02T00:00:00Z");
  // Nothing goes below 1: everything is numbered again, the moved rule
  // first, and a rule already on its number is not written.
  expect(reorderWrites([x, y], 1, 0)).toEqual([
    { rule: y, priority: 10 },
    { rule: x, priority: 20 },
  ]);
});

test("an account number's shape and control digits are checked before it is sent", () => {
  expect(ibanProblem("ES91 2100 0418 4502 0005 1332")).toBeNull();
  expect(ibanProblem("ES9221000418450200051332")).toBe("check");
  expect(ibanProblem("ES91")).toBe("shape");
  expect(ibanProblem("not an iban")).toBe("shape");
  expect(ibanProblem("GB82WEST12345698765432")).toBeNull();
});

test("register numbers and documents keep the product's grammar", () => {
  expect(parsePoints("92")).toEqual({ kind: "value", value: "92" });
  expect(parsePoints("92.50%")).toEqual({ kind: "value", value: "92.5" });
  expect(parsePoints("100.5").kind).toBe("refused");
  expect(parsePoints("92,5").kind).toBe("refused");
  expect(parsePoints("")).toEqual({ kind: "empty" });
  expect(wholeYear("2024")).toBe(2024);
  expect(wholeYear("24")).toBeNull();
  expect(parseObject('{"a":1}')).toEqual({ kind: "value", value: { a: 1 } });
  expect(parseObject("[1]")).toEqual({ kind: "refused" });
  expect(parseObject("{")).toEqual({ kind: "refused" });
  expect(parseObject("  ")).toEqual({ kind: "empty" });
  expect(
    correctionOf({ asset_id: "A-1", revision_number: 2 }, hexId("rev")),
  ).toEqual({
    asset_id: "A-1",
    revision_number: 3,
    supersedes_revision_id: hexId("rev"),
  });
});

test("a call reads as done, refused, unknown or failed, and an unknown write is never a failure", () => {
  expect(
    callOutcome(
      { kind: "settled", operation_id: "o", revision: 3, result: { a: 1 } },
      true,
    ),
  ).toEqual({ kind: "done", result: { a: 1 } });
  expect(
    callOutcome(
      {
        kind: "refused",
        operation_id: "o",
        revision: 3,
        reason: "REFUSED_X",
        detail: null,
      },
      true,
    ),
  ).toEqual({ kind: "refused", reason: "REFUSED_X", detail: null });
  const running = {
    kind: "running" as const,
    operation_id: "o",
    revision: 2,
    cancellable: false,
  };
  expect(callOutcome(running, true)).toEqual({ kind: "unknown" });
  expect(callOutcome(running, false).kind).toBe("failed");
  expect(callFailure({ code: "unknown", operation_id: "o" })).toEqual({
    kind: "unknown",
  });
  expect(callFailure(new Error("boom"))).toEqual({
    kind: "failed",
    code: "unavailable",
    reason: null,
  });
});

test("a staged rule run names no row, follows a new id, and is held while a listed movement has a staged classification", () => {
  const run: StagedAction = {
    id: "run",
    kind: "rule_apply",
    reaffirm: true,
    transactionIds: ["a", "b"],
  };
  expect(actionRows(run)).toEqual([]);
  let state = reduceStage(EMPTY_STAGE, { type: "stage_action", action: run });
  state = reduceStage(state, { type: "rekey", from: "a", to: "a2" });
  const rekeyed = state.content.actions[0]!;
  expect(rekeyed.kind === "rule_apply" && rekeyed.transactionIds).toEqual([
    "a2",
    "b",
  ]);

  const rows = new Map([
    ["a2", movement("a2")],
    ["b", movement("b")],
  ]);
  const plan = planApply(state.content, { rows });
  expect(plan.steps).toEqual([
    {
      kind: "action",
      action: rekeyed,
      definition: "ledger.rule.apply",
      request: { reaffirm: true, dry_run: false },
    },
  ]);
  expect(ruleApplyClashes(run, state.content)).toBe(false);

  // A classification the person staged on a listed movement holds it back;
  // a correction does not.
  const classified = reduceStage(state, {
    type: "stage",
    label: "set",
    cells: [
      {
        id: "b",
        field: "business_classification",
        value: { kind: "set", value: "PERSONAL" },
        stored: "NOT_YET_PROCESSED",
      },
    ],
  });
  const held = planApply(classified.content, { rows });
  expect(held.held.actions).toEqual(["run"]);
  expect(
    held.steps.some(
      (step) =>
        step.kind === "action" && step.definition === "ledger.rule.apply",
    ),
  ).toBe(false);
  const noted = reduceStage(state, {
    type: "stage",
    label: "set",
    cells: [
      {
        id: "b",
        field: "notes",
        value: { kind: "set", value: "revisar" },
        stored: null,
      },
    ],
  });
  expect(planApply(noted.content, { rows }).held.actions).toEqual([]);
});
