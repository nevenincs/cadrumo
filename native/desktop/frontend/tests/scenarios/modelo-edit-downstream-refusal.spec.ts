import { expect, type Page, test } from "@playwright/test";
import { label } from "../support/strings";
import { boxRow, openDeclaration, tab } from "../support/scenarioModelo";
import {
  applyButton,
  calls,
  review,
  stage,
  TYPED_06,
} from "../support/scenarioModeloWrites";

// A refused edit whose values were admitted and a later stage refused, and the
// check's profile findings, as the backend serves them. Every sentence and
// door word below is fixture text standing in for what the backend serves;
// the window composes none of it.

declare global {
  interface Window {
    __downstreamPreflight?: boolean;
    __calculateCalls?: number;
  }
}

/** A refused apply's error detail: the sentence, and the door the worker
 * served on its verdict. */
function refusedApply(words: string, verdict: Record<string, unknown>) {
  return {
    kind: "refused",
    operation_id: "fixture-downstream-apply",
    revision: 2,
    reason: "REFUSED_FIXTURE_DOWNSTREAM",
    detail: {
      detail_version: 1,
      kind: "registered",
      error_code: "REFUSED_FIXTURE_DOWNSTREAM",
      message_key: null,
      context: [],
      context_entries_omitted: 0,
      refusal_words: words,
      refusal_words_language: "en",
      precondition_verdict_json: JSON.stringify({
        failed_condition_id: "fixture.downstream.condition",
        evidence: [
          {
            condition_id: "fixture.downstream.condition",
            evidence_id: "modelo.work.edit.downstream_refusal",
            provenance: "application_state",
            values: { edit_values_admitted: true },
          },
        ],
        alternative_actions: [],
        ...verdict,
      }),
    },
  };
}

/** Answers every apply with `outcome`; every other edit call goes through. */
async function refuseApplies(target: Page, outcome: unknown) {
  await target.evaluate((outcome) => {
    const port = window.__fixtureModelo!;
    const edit = port.edit.bind(port);
    port.edit = (async (
      definition: Parameters<typeof port.edit>[0],
      body: Parameters<typeof port.edit>[1],
    ) =>
      definition === "modelo.edit.apply"
        ? outcome
        : edit(definition, body)) as typeof port.edit;
  }, outcome);
}

test("an apply a later stage refused routes its served door, which names the arguments it still needs", async ({
  page: target,
}) => {
  const words = "Fixture: the recalculation refused this declaration.";
  const door = "Fixture: correct the recorded declaration";
  await openDeclaration(target, "130", { shape: "edit" });
  await refuseApplies(
    target,
    refusedApply(words, {
      action: { action_id: "fixture.downstream.amend" },
      argument_bindings: [{ argument_name: "reason", status: "missing" }],
      missing_argument_names: ["reason"],
      conditionality: "requires_arguments",
      target_operation_ids: ["modelo.work.amend"],
      action_words: door,
      action_words_language: "en",
      no_recovery_outcome: null,
      no_recovery_words: null,
    }),
  );
  await stage(target, "06", TYPED_06);
  const dialog = await review(target);
  await applyButton(dialog).click();
  const notice = dialog.getByRole("alert").filter({ hasText: words });
  await expect(notice).toBeVisible();
  const way = notice.getByRole("button", { name: door });
  await expect(way).toBeEnabled();
  await expect(way).not.toHaveAttribute("aria-disabled", "true");
  await expect(way).toHaveAttribute("data-conditional", "true");
  // The door opens the correction of the recorded filing, over the history.
  await way.click();
  await expect(
    target.getByRole("dialog", {
      name: label("workspace.modelo.correction.title"),
    }),
  ).toBeVisible();
});

test("an apply a later stage refused with no way out says so and offers no door", async ({
  page: target,
}) => {
  const words = "Fixture: the recalculation refused this declaration.";
  const none = "Fixture: nothing the window offers clears this refusal.";
  await openDeclaration(target, "130", { shape: "edit" });
  await refuseApplies(
    target,
    refusedApply(words, {
      action: null,
      argument_bindings: [],
      missing_argument_names: [],
      conditionality: "not_applicable",
      target_operation_ids: [],
      action_words: null,
      action_words_language: null,
      no_recovery_outcome: "operator_decision",
      no_recovery_words: none,
      no_recovery_words_language: "en",
    }),
  );
  await stage(target, "06", TYPED_06);
  const dialog = await review(target);
  await applyButton(dialog).click();
  const notice = dialog.getByRole("alert").filter({ hasText: words });
  await expect(notice).toBeVisible();
  await expect(notice).toContainText(none);
  await expect(notice).toHaveAttribute("data-no-recovery", "operator_decision");
  await expect(notice.getByRole("button")).toHaveCount(0);
  // Nothing was applied: the edit stays staged.
  await dialog
    .getByRole("button", { name: label("workspace.modelo.review.back") })
    .click();
  await expect(boxRow(target, "06")).toContainText(
    label("workspace.modelo.attention.staged"),
  );
});

test("a check a later stage refused says the served downstream sentence and applies nothing", async ({
  page: target,
}) => {
  const words = "Fixture: the recalculation would refuse this declaration.";
  await openDeclaration(target, "130", { shape: "edit" });
  await target.evaluate((words) => {
    const port = window.__fixtureModelo!;
    const edit = port.edit.bind(port);
    port.edit = (async (
      definition: Parameters<typeof port.edit>[0],
      body: Parameters<typeof port.edit>[1],
    ) => {
      const answer = await edit(definition, body);
      if (
        definition !== "modelo.edit.preflight" ||
        !window.__downstreamPreflight ||
        answer.kind !== "settled"
      )
        return answer;
      // The values were admitted; the recalculation refused under its own
      // registered code, carried as the refusal's downstream.
      return {
        ...answer,
        result: {
          ...answer.result,
          outcome: {
            outcome: "refused",
            refusal: {
              kind: "domain",
              edit_contract_version: 1,
              code: "downstream_refused",
              address: null,
              facts: [],
              evidence: [],
              responsible_owner: "fixture",
              reconsideration_condition: "fixture",
              recovery_action: null,
              downstream: {
                error_code: "REFUSED_FIXTURE_DOWNSTREAM",
                message_key: null,
                context: [],
                failed_condition_id: "fixture.downstream.condition",
                recovery_action: { action_id: "fixture.downstream.amend" },
                argument_names: ["reason"],
                no_recovery_outcome: null,
              },
            },
          },
          findings: [],
          rebase: [],
          refusal_words: words,
        },
      };
    }) as typeof port.edit;
  }, words);
  await stage(target, "06", TYPED_06);
  await target.evaluate(() => {
    window.__downstreamPreflight = true;
  });
  const dialog = await review(target);
  await expect(dialog.getByText(words, { exact: true })).toBeVisible();
  await expect(applyButton(dialog)).toBeDisabled();
  expect(await calls(target, "modelo edit modelo.edit.apply")).toHaveLength(0);
});

// -- the check's profile findings --------------------------------------------

/** One issue line, as the read model words it, with fixture words. */
const line = (fields: {
  level: string;
  message: string;
  action: string;
  recalculates: boolean;
}) => ({
  box: null,
  where: null,
  detail: null,
  technical: "Fixture technical details",
  address: null,
  in_records: false,
  surface: null,
  compared_surface: null,
  from_calculation: false,
  finding_id: null,
  resolution_answer: null,
  answer_lead_words: null,
  answer_lead_words_language: null,
  invoice_id: null,
  ...fields,
});

/** One issue of the form, as the backend derives it from its finding. */
const issue = (fields: {
  severity: string;
  attention: string;
  message_locale_key: string;
  action_locale_key: string;
  door_action_id: string | null;
}) => ({
  finding: {
    kind: "stale_calculation",
    severity: fields.severity,
    casilla_id: null,
    expectation_id: null,
    message_locale_key: fields.message_locale_key,
    message_facts: [],
    legal_refs: [],
    source_refs: [],
  },
  box: null,
  attention: fields.attention,
  action_locale_key: fields.action_locale_key,
  open_invoice_id: null,
  door_action_id: fields.door_action_id,
});

/** Serves `added` lines and issues on every read of the form from the first
 * on, and counts the calculations the window asks for. */
async function serveFindings(
  target: Page,
  added: { lines: unknown[]; issues: unknown[] },
) {
  await target.addInitScript((added) => {
    const wrap = (port: NonNullable<Window["__fixtureModelo"]>) => {
      const form = port.form;
      port.form = async (...args) => {
        const read = await form(...args);
        return {
          ...read,
          issue_lines: [
            ...(added.lines as typeof read.issue_lines),
            ...read.issue_lines,
          ],
          form: {
            ...read.form,
            form: {
              ...read.form.form,
              issues: [
                ...(added.issues as typeof read.form.form.issues),
                ...read.form.form.issues,
              ],
            },
          },
        };
      };
      const submit = port.submit;
      port.submit = async (...args) => {
        if (args[0] === "modelo.work.calculate")
          window.__calculateCalls = (window.__calculateCalls ?? 0) + 1;
        return submit(...args);
      };
    };
    let current: Window["__fixtureModelo"];
    Object.defineProperty(window, "__fixtureModelo", {
      configurable: true,
      get: () => current,
      set: (port: Window["__fixtureModelo"]) => {
        if (port && port !== current) wrap(port);
        current = port;
      },
    });
  }, added);
}

test("a draft whose read profile facts were edited says so and calculates again from its line", async ({
  page: target,
}) => {
  const message = "Fixture: profile facts this draft read were edited since.";
  const action = "Fixture: calculate the declaration again.";
  await serveFindings(target, {
    lines: [line({ level: "blocks", message, action, recalculates: true })],
    issues: [
      issue({
        severity: "blocking",
        attention: "blocks",
        message_locale_key: "application.modelo.findings.profile_read_drift",
        action_locale_key:
          "application.modelo.work_form.finding_action.calculate_again",
        door_action_id: null,
      }),
    ],
  });
  await openDeclaration(target, "130", { shape: "checked" });
  await tab(target, "workspace.modelo.step.review").click();
  const item = target
    .getByRole("region", { name: label("workspace.modelo.level.blocks") })
    .getByRole("listitem")
    .filter({ hasText: message });
  await expect(item).toContainText(action);
  await expect(item).not.toContainText("Fixture technical details");
  const calculate = item.getByRole("button", {
    name: label("workspace.modelo.next_button.recalculate"),
  });
  await expect(calculate).toBeEnabled();
  await calculate.click();
  await expect
    .poll(() => target.evaluate(() => window.__calculateCalls ?? 0))
    .toBe(1);
});

test("a filed declaration whose profile facts were edited since says so and opens its amendment", async ({
  page: target,
}) => {
  const message =
    "Fixture: profile facts this filed declaration read were edited since.";
  const action = "Fixture: correct the filed declaration.";
  await serveFindings(target, {
    // The backend serves the line as one that calculates again, as every
    // stale calculation is; a filed declaration takes no calculation.
    lines: [line({ level: "check", message, action, recalculates: true })],
    issues: [
      issue({
        severity: "warning",
        attention: "check",
        message_locale_key:
          "application.modelo.findings.profile_read_superseded_filed",
        action_locale_key:
          "application.modelo.work_form.finding_action.amend_filed_declaration",
        door_action_id: "operator.modelo.work.amend",
      }),
    ],
  });
  await openDeclaration(target, "130", { shape: "filed" });
  await tab(target, "workspace.modelo.step.review").click();
  const level = target.getByRole("region", {
    name: label("workspace.modelo.level.check"),
  });
  const item = level.getByRole("listitem").filter({ hasText: message });
  await expect(item).toContainText(action);
  await expect(
    item.getByRole("button", {
      name: label("workspace.modelo.next_button.recalculate"),
    }),
  ).toHaveCount(0);
  const amend = target
    .locator("[data-issue-door]")
    .getByRole("button", { name: label("workspace.modelo.correction.title") });
  await expect(amend).toBeEnabled();
  await amend.click();
  await expect(
    target.getByRole("dialog", {
      name: label("workspace.modelo.correction.title"),
    }),
  ).toBeVisible();
  expect(await target.evaluate(() => window.__calculateCalls ?? 0)).toBe(0);
});
