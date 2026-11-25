import assert from "node:assert/strict";
import test from "node:test";
import { LEDGER_DEFINITIONS } from "../../src/shell/ledger.ts";
import { MODELO_DEFINITIONS } from "../../src/shell/modeloContract/contracts.ts";
import {
  placeIn,
  refusalControls,
  refusalWays,
  servedVerdictFromJson,
  type ServedAlternativeAction,
  type ServedVerdict,
  type WindowPlace,
} from "../../src/shell/refusal.ts";

const admitted = {
  ledger: LEDGER_DEFINITIONS,
  declarations: MODELO_DEFINITIONS,
};
const route = (ids: readonly string[]): WindowPlace | null =>
  placeIn(ids, admitted);

function verdict(fields: Partial<ServedVerdict>): ServedVerdict {
  return {
    failed_condition_id: "fixture.condition",
    evidence: [],
    action_id: null,
    argument_bindings: [],
    missing_argument_names: [],
    conditionality: "not_applicable",
    no_recovery_outcome: null,
    no_recovery_words: null,
    no_recovery_words_language: null,
    action_words: null,
    action_words_language: null,
    target_operation_ids: [],
    ...fields,
  };
}

const way = (
  action_id: string,
  target_operation: string,
  action_words: string | null,
): ServedAlternativeAction => ({
  action_id,
  target_operation_ids: [target_operation],
  argument_bindings: [],
  missing_argument_names: [],
  conditionality: "immediate",
  action_words,
  action_words_language: action_words === null ? null : "en",
});

test("an admitted definition routes to the page that hosts it, by exact id only", () => {
  assert.deepEqual(route(["ledger.review"]), {
    page: "ledger",
    definition: "ledger.review",
  });
  assert.deepEqual(route(["modelo.work.verify"]), {
    page: "declarations",
    definition: "modelo.work.verify",
  });
  assert.equal(route(["config.auth.login"]), null);
  assert.equal(route(["modelo.work"]), null);
  assert.equal(route([""]), null);
  assert.equal(route([]), null);
});

test("the first served operation the window admits routes the action, in served order", () => {
  assert.deepEqual(route(["live.notifications.list", "modelo.work.amend"]), {
    page: "declarations",
    definition: "modelo.work.amend",
  });
  assert.deepEqual(route(["modelo.edit.apply", "modelo.work.form"]), {
    page: "declarations",
    definition: "modelo.edit.apply",
  });
});

test("the primary way comes first and the alternatives keep their served order, repeats included", () => {
  const ways = refusalWays(
    verdict({
      action_id: "primary",
      target_operation_ids: ["modelo.work.create"],
      conditionality: "immediate",
      action_words: "First",
      alternative_actions: [
        way("zeta", "ledger.review", "Second"),
        way("alpha", "ledger.review", "Third"),
        way("zeta", "ledger.review", "Fourth"),
      ],
    }),
  );
  assert.deepEqual(
    ways.map((w) => [w.role, w.action_id, w.action_words]),
    [
      ["primary", "primary", "First"],
      ["alternative", "zeta", "Second"],
      ["alternative", "alpha", "Third"],
      ["alternative", "zeta", "Fourth"],
    ],
  );
});

test("a no-recovery verdict offers no way out, whatever else it carries", () => {
  assert.deepEqual(
    refusalWays(
      verdict({
        no_recovery_outcome: "terminal",
        no_recovery_words: "None",
        alternative_actions: [way("a", "ledger.review", "Words")],
      }),
    ),
    [],
  );
  assert.deepEqual(refusalWays(null), []);
});

test("a way without served words draws no control; an unroutable one draws one without an intent", () => {
  const controls = refusalControls(
    verdict({
      action_id: "primary",
      target_operation_ids: ["modelo.work.create"],
      conditionality: "immediate",
      action_words: "   ",
      alternative_actions: [
        way("routed", "ledger.review", "Routed"),
        way("elsewhere", "config.auth.login", "Elsewhere"),
      ],
    }),
    route,
  );
  assert.deepEqual(
    controls.map((c) => [c.role, c.words, c.intent?.place.page ?? null]),
    [
      ["alternative", "Routed", "ledger"],
      ["alternative", "Elsewhere", null],
    ],
  );
});

test("missing arguments make the control open the destination's form, never submit", () => {
  const [control] = refusalControls(
    verdict({
      action_id: "primary",
      target_operation_ids: ["modelo.work.create"],
      conditionality: "requires_arguments",
      missing_argument_names: ["value"],
      action_words: "Open",
    }),
    route,
  );
  assert.equal(control?.conditional, true);
  assert.equal(control?.intent?.kind, "form");
  assert.deepEqual(control?.intent?.missing, ["value"]);
});

// A stored verdict as the worker's error detail serializes it: the domain
// record, whose actions nest their identity and whose unserved word and
// routing fields are left out.
const stored = (fields: Record<string, unknown>) =>
  JSON.stringify({
    failed_condition_id: "fixture.condition",
    evidence: [
      {
        condition_id: "fixture.condition",
        evidence_id: "fixture.evidence",
        provenance: "persisted_state",
        values: { held: true, count: "2" },
      },
    ],
    action: null,
    argument_bindings: [],
    missing_argument_names: [],
    conditionality: "not_applicable",
    no_recovery_outcome: null,
    ...fields,
  });

test("a stored verdict reads into the served snapshot, with its served words and routing", () => {
  const read = servedVerdictFromJson(
    stored({
      action: { action_id: "operator.fixture.primary" },
      conditionality: "immediate",
      action_words: "Primary words",
      action_words_language: "en",
      target_operation_ids: ["modelo.work.amend", "modelo.work.filing_record"],
      alternative_actions: [
        {
          action: { action_id: "operator.fixture.second" },
          argument_bindings: [
            {
              argument_name: "value",
              status: "missing",
              value: null,
              source: null,
              source_key: null,
              source_evidence_id: null,
            },
          ],
          missing_argument_names: ["value"],
          conditionality: "requires_arguments",
          action_words: "Second words",
          action_words_language: "en",
          target_operation_ids: ["modelo.edit.apply"],
        },
      ],
    }),
  );
  assert.ok(read);
  assert.equal(read.action_id, "operator.fixture.primary");
  assert.deepEqual(read.evidence[0]?.values, [
    { key: "held", value: true },
    { key: "count", value: "2" },
  ]);
  assert.deepEqual(
    refusalControls(read, route).map((c) => [
      c.role,
      c.words,
      c.intent?.kind,
      c.intent?.place.definition,
    ]),
    [
      ["primary", "Primary words", "follow", "modelo.work.amend"],
      ["alternative", "Second words", "form", "modelo.edit.apply"],
    ],
  );
});

test("a stored no-way-out verdict keeps its served sentence; unserved fields read as absent", () => {
  const read = servedVerdictFromJson(
    stored({
      no_recovery_outcome: "terminal",
      no_recovery_words: "None words",
      no_recovery_words_language: "en",
    }),
  );
  assert.equal(read?.no_recovery_words, "None words");
  assert.deepEqual(read?.target_operation_ids, []);
  assert.equal(read?.action_words, null);
  assert.deepEqual(refusalWays(read ?? null), []);
});

test("a missing, malformed or unknown-token verdict reads as none", () => {
  assert.equal(servedVerdictFromJson(null), null);
  assert.equal(servedVerdictFromJson("{"), null);
  assert.equal(servedVerdictFromJson("[]"), null);
  assert.equal(
    servedVerdictFromJson(stored({ conditionality: "sometimes" })),
    null,
  );
  assert.equal(
    servedVerdictFromJson(stored({ no_recovery_outcome: "never" })),
    null,
  );
  assert.equal(
    servedVerdictFromJson(stored({ action_words_language: "fr" })),
    null,
  );
});
