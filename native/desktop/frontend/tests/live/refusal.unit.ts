import assert from "node:assert/strict";
import test from "node:test";
import { LEDGER_DEFINITIONS } from "../../src/shell/ledger.ts";
import { MODELO_DEFINITIONS } from "../../src/shell/modeloContract/contracts.ts";
import {
  placeIn,
  refusalControls,
  refusalWays,
  type ServedAlternativeAction,
  type ServedVerdict,
  type WindowPlace,
} from "../../src/shell/refusal.ts";

const admitted = {
  ledger: LEDGER_DEFINITIONS,
  declarations: MODELO_DEFINITIONS,
};
const route = (key: string | null): WindowPlace | null =>
  placeIn(key, admitted);

function verdict(fields: Partial<ServedVerdict>): ServedVerdict {
  return {
    failed_condition_id: "fixture.condition",
    evidence: [],
    action_id: null,
    argument_bindings: [],
    missing_argument_names: [],
    conditionality: "not_applicable",
    no_recovery_outcome: null,
    ...fields,
  };
}

const way = (
  action_id: string,
  target_command_key: string,
  action_words: string | null,
): ServedAlternativeAction => ({
  action_id,
  target_command_key,
  argument_bindings: [],
  missing_argument_names: [],
  conditionality: "immediate",
  action_words,
});

test("an admitted definition routes to the page that hosts it, by exact key only", () => {
  assert.deepEqual(route("ledger.review"), {
    page: "ledger",
    definition: "ledger.review",
  });
  assert.deepEqual(route("modelo.work.verify"), {
    page: "declarations",
    definition: "modelo.work.verify",
  });
  assert.equal(route("config.auth.login"), null);
  assert.equal(route("modelo.work"), null);
  assert.equal(route(""), null);
  assert.equal(route(null), null);
});

test("the primary way comes first and the alternatives keep their served order, repeats included", () => {
  const ways = refusalWays(
    verdict({
      action_id: "primary",
      target_command_key: "modelo.work.create",
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
      target_command_key: "modelo.work.create",
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
      target_command_key: "modelo.work.create",
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
