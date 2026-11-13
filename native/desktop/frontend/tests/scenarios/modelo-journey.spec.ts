import { expect, test, type Page } from "@playwright/test";
import type {
  ModeloFormExportHold,
  ModeloFormJourney,
  ModeloFormNextStep,
  ModeloFormStepState,
  ModeloFormVerdict,
  ModeloWorkbenchFormProjectionV1,
} from "../../src/shell/modeloContract/modeloWorkForm";
import type { ModeloPort } from "../../src/shell/modelo";
import { label } from "../support/strings";
import {
  boxRow,
  fields,
  form,
  openDeclaration,
  tab,
} from "../support/scenarioModelo";
import { stage, TYPED_06 } from "../support/scenarioModeloWrites";

// Where a declaration stands on the filing journey is the read model's: the
// steps and their status (one set while the window holds changes, another
// otherwise), the box the filer starts at, the action that lifts the export
// hold and what a finished check concluded. The window draws what it is
// served, so each test serves a value the declaration's own state would not
// produce and expects to see exactly that.

type Served = {
  next_step?: ModeloFormNextStep | null;
  journey?: ModeloFormJourney;
  export_hold?: ModeloFormExportHold | null;
  verdict?: ModeloFormVerdict;
};
type JourneyTest = { verified: boolean; submits: string[] };
declare global {
  interface Window {
    __journeyTest?: JourneyTest;
  }
}

const A_STEP: ModeloFormNextStep = {
  action: "fill",
  count: 1,
  findings_lead: false,
  recorded_at: null,
  file_created_at: null,
  receipt_to_add: false,
};
const NOT_CHECKED: ModeloFormVerdict = {
  status: null,
  words: "Synthetic verdict: not checked.",
  unapplied_words: null,
  checked_words: null,
  checked_resolves: false,
};
const states = (
  ...pairs: [ModeloFormStepState["step"], ModeloFormStepState["status"]][]
): ModeloFormStepState[] => pairs.map(([step, status]) => ({ step, status }));
const journey = (
  parts: Partial<ModeloFormJourney> & Pick<ModeloFormJourney, "steps">,
): ModeloFormJourney => ({
  steps_while_changes_held: parts.steps,
  next_step: A_STEP,
  held_prerequisite_next_step: { ...A_STEP, action: "resolve" },
  first_attention: null,
  verdict: NOT_CHECKED,
  ...parts,
});

/** Serves the declaration the scenario reads with `served` laid over it, and
 * with `afterVerify` once a verification has settled. The host answers no
 * verification itself, so one is recorded and answered as settled. */
async function serve(target: Page, served: Served, afterVerify?: Served) {
  await target.addInitScript(
    ({ now, after }) => {
      const test: JourneyTest = (window.__journeyTest = {
        verified: false,
        submits: [],
      });
      const lay = (
        read: ModeloWorkbenchFormProjectionV1,
        over: Served,
      ): ModeloWorkbenchFormProjectionV1 => ({
        ...read,
        ...(over.next_step !== undefined ? { next_step: over.next_step } : {}),
        ...(over.verdict ? { verdict: over.verdict } : {}),
        form: {
          ...read.form,
          ...(over.journey ? { journey: over.journey } : {}),
        },
        header: {
          ...read.header,
          ...(over.export_hold !== undefined
            ? { export_hold: over.export_hold }
            : {}),
        },
      });
      let port: ModeloPort | undefined;
      Object.defineProperty(window, "__fixtureModelo", {
        configurable: true,
        get: () => port,
        set(value: ModeloPort) {
          port = value;
          const read = value.form.bind(value);
          const submit = value.submit.bind(value) as (
            ...args: unknown[]
          ) => Promise<unknown>;
          value.form = async (...args) =>
            lay(await read(...args), test.verified && after ? after : now);
          value.submit = (async (...args: unknown[]) => {
            test.submits.push(String(args[0]));
            if (args[0] !== "modelo.work.verify") return submit(...args);
            test.verified = true;
            return { kind: "settled", operation_id: "verify-1", result: {} };
          }) as ModeloPort["submit"];
        },
      });
    },
    { now: served, after: afterVerify },
  );
}

const steps = (target: Page) =>
  target.locator(".declarations-workspace [data-journey] > li");
const shown = (target: Page) =>
  steps(target).evaluateAll((items) =>
    items.map((item) => [
      item.getAttribute("data-step"),
      item.getAttribute("data-status"),
      item.getAttribute("aria-current"),
    ]),
  );

test("the steps are the read model's, in its order and with its statuses", async ({
  page: target,
}) => {
  const served = states(
    ["review", "blocked"],
    ["fill", "done"],
    ["file", "current"],
    ["calculate", "pending"],
  );
  await serve(target, { journey: journey({ steps: served }) });
  await openDeclaration(target, "130");
  expect(await shown(target)).toEqual([
    ["review", "blocked", null],
    ["fill", "done", null],
    ["file", "current", "step"],
    ["calculate", "pending", null],
  ]);
  for (const { step } of served)
    await expect(
      steps(target).filter({
        hasText: label(`workspace.modelo.step.${step}`),
      }),
    ).toHaveCount(1);
});

test("changes the window holds show the steps served for that case", async ({
  page: target,
}) => {
  await serve(target, {
    journey: journey({
      steps: states(
        ["fill", "done"],
        ["calculate", "done"],
        ["review", "current"],
        ["file", "pending"],
      ),
      steps_while_changes_held: states(
        ["fill", "current"],
        ["calculate", "pending"],
        ["review", "pending"],
        ["file", "pending"],
      ),
    }),
  });
  await openDeclaration(target, "130", { shape: "edit" });
  expect((await shown(target)).map(([, status]) => status)).toEqual([
    "done",
    "done",
    "current",
    "pending",
  ]);
  await stage(target, "06", TYPED_06);
  expect((await shown(target)).map(([, status]) => status)).toEqual([
    "current",
    "pending",
    "pending",
    "pending",
  ]);
});

test("the next action starts at the box the read model serves as first", async ({
  page: target,
}) => {
  // Not the first box that needs the filer, so the window cannot have found
  // it by looking.
  const served = fields(form("130-1T").form.form).find(
    (field) => field.standing !== "needs_you" && field.box !== null,
  );
  if (!served?.box) throw new Error("the 130 has a box that needs nobody");
  const box = served.box;
  await serve(target, {
    next_step: A_STEP,
    journey: journey({
      steps: states(
        ["fill", "current"],
        ["calculate", "pending"],
        ["review", "pending"],
        ["file", "pending"],
      ),
      first_attention: { address: served.address, page_id: null },
    }),
  });
  await openDeclaration(target, "130");
  await target
    .locator(".declarations-workspace header")
    .getByRole("button", { name: label("workspace.modelo.next_button.fill") })
    .click();
  await expect(boxRow(target, box).first()).toHaveAttribute(
    "aria-selected",
    "true",
  );
});

test("a hold's door takes the action the read model names for it", async ({
  page: target,
}) => {
  await serve(target, {
    journey: journey({
      steps: states(
        ["fill", "done"],
        ["calculate", "done"],
        ["review", "current"],
        ["file", "pending"],
      ),
    }),
    export_hold: {
      reason: "verify",
      count: 0,
      words: "Synthetic hold: check the declaration first.",
      action: "verify",
    },
  });
  await openDeclaration(target, "130", { shape: "stale" });
  await tab(target, "workspace.modelo.filing.title").click();
  const door = target.getByRole("tabpanel").getByRole("button", {
    name: label("workspace.modelo.next_button.verify"),
    exact: true,
  });
  await expect(door).toHaveAttribute("data-hold-action", "verify");
  await door.click();
  await expect
    .poll(() => target.evaluate(() => window.__journeyTest!.submits))
    .toContain("modelo.work.verify");
});

for (const resolves of [false, true]) {
  test(`a finished check says what the read model served (${resolves ? "something to resolve" : "nothing to resolve"})`, async ({
    page: target,
  }) => {
    const words = `Synthetic finished check, resolves ${resolves}.`;
    const verifying: ModeloFormNextStep = {
      ...A_STEP,
      action: "verify",
      count: 0,
    };
    const base = journey({
      steps: states(
        ["fill", "done"],
        ["calculate", "done"],
        ["review", "current"],
        ["file", "pending"],
      ),
    });
    await serve(
      target,
      { next_step: verifying, journey: base },
      {
        next_step: verifying,
        journey: base,
        verdict: {
          status: resolves ? "blocked" : "complete",
          words: "Synthetic verdict.",
          unapplied_words: null,
          checked_words: words,
          checked_resolves: resolves,
        },
      },
    );
    await openDeclaration(target, "130", { shape: "checked" });
    await target
      .locator(".declarations-workspace header")
      .getByRole("button", {
        name: label("workspace.modelo.next_button.verify"),
      })
      .click();
    const said = target
      .locator(".declarations-workspace [role=status]")
      .filter({ hasText: words });
    await expect(said).toBeVisible();
    await expect(said).toHaveAttribute(
      "data-tone",
      resolves ? "warning" : "success",
    );
  });
}
