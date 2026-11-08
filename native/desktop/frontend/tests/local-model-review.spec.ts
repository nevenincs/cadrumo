import { expect, test } from "@playwright/test";
import { build } from "esbuild";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import type { SetupRun } from "../src/ipc/componentSetup";
import { FIXTURE_CATALOG } from "../src/dev/fixtures/agentCatalog";
import { catalogLanes, type CatalogLane } from "../src/shell/localModelLanes";
import { planIsFor } from "../src/shell/localModels";

// Where the local AI's plan is answered while it awaits the person: on the
// asked model's row, on the program's row, or, in a model section that stands
// alone with no program row near it, on the section. Whether a plan is a
// lane's is checked in itself, then through the real components drawn to
// markup with the window's own provisioning store, because the test runner
// replaces JSX in the files it loads: they are compiled here with the
// project's JSX setting. No page is opened.

const LANE = catalogLanes(FIXTURE_CATALOG).find(
  (lane) => lane.id === "local_api",
)!;
const VISION = "synthetic-vision:1";
/** A second keyless lane of the same catalog, which lists other models. */
const SECOND: CatalogLane = {
  ...LANE,
  id: "second_cli",
  name: "Second",
  models: LANE.models.map((model) => ({
    ...model,
    id: `second-${model.id}`,
    name: `second-${model.name}`,
  })),
  recommended: LANE.recommended.map((id) => `second-${id}`),
};
const SECOND_VISION = `second-${VISION}`;

const planning =
  (...models: string[]) =>
  (model: string) =>
    models.includes(model);

test("a plan is a lane's when the model asked for belongs to it", () => {
  expect(
    planIsFor({
      lane: SECOND,
      models: SECOND.models,
      reviewed: { lane: SECOND.id, model: SECOND_VISION },
      planned: planning(SECOND_VISION),
    }),
  ).toBe(true);
  expect(
    planIsFor({
      lane: SECOND,
      models: SECOND.models,
      reviewed: { lane: LANE.id, model: VISION },
      planned: planning(VISION),
    }),
  ).toBe(false);
});

test("with nothing asked, as after a reload, a plan is the lane's that lists a model the plan holds a part for", () => {
  expect(
    planIsFor({
      lane: SECOND,
      models: SECOND.models,
      reviewed: null,
      planned: planning(SECOND_VISION),
    }),
  ).toBe(true);
  for (const planned of [planning(VISION), () => false])
    expect(
      planIsFor({
        lane: SECOND,
        models: SECOND.models,
        reviewed: null,
        planned,
      }),
    ).toBe(false);
});

test("a plan is no lane's while the lane is not known", () => {
  expect(
    planIsFor({
      lane: null,
      models: [],
      reviewed: null,
      planned: planning(SECOND_VISION),
    }),
  ).toBe(false);
});

type Draw = (scene: {
  what: "section" | "local_ai";
  lane: CatalogLane;
  stage: SetupRun["stage"];
  /** The model the plan holds a part for. */
  planned: string;
}) => string;

async function compiled(): Promise<Draw> {
  const root = fileURLToPath(new URL("..", import.meta.url));
  const source = (path: string) =>
    JSON.stringify(fileURLToPath(new URL(`../src/${path}`, import.meta.url)));
  const built = await build({
    stdin: {
      contents: `
        import { createElement } from "react";
        import { renderToStaticMarkup } from "react-dom/server";
        import { ProvisioningContext, useProvisioningStore } from ${source("shell/provisioning.ts")};
        import { LocalModels } from ${source("components/settings/LocalModels.tsx")};
        import { LocalAi } from ${source("components/setup/LocalAi.tsx")};

        const part = (model) => ({
          part: "download", model, step: null, completed: null, total: null,
          result: null,
        });
        const snapshot = (item, stage, model) => ({
          rows: [{
            item, kind: "local_ai", mode: "quick", state: "ready",
            stale_reason: null, blocked_reason: null, failure: null,
            recovery: null, recovery_action_id: null, version: "1.0",
            size_bytes: null,
          }],
          rows_mode: "quick", complete: true, hardware_limited: false,
          check: null,
          runs: [{
            item, operation_id: "setup-1", stage,
            review: stage === "review" ? {
              plan_digest: "plan-1",
              entries: [{
                item, download_bytes: 1024, source_hosts: ["example.test"],
                destination: null, installs_outside_program: false,
                shares_download_with: null,
                parts: [{ part: "download", model, download_bytes: 1024,
                  destination: "models" }],
              }],
              known_download_bytes: 1024, has_unknown_size: false,
              installs_outside_program: false, required_bytes: 1024,
              free_bytes: 1048576, space_sufficient: true,
            } : null,
            items: [{
              item, step: null, completed: null, total: null, retry: null,
              result: null, parts: [part(model)],
            }],
            cancellable: true, cancel_requested: false, outcome: null,
            failure: null,
          }],
          google: { state: "signed_in", email: null, drive_folder_id: null,
            stage: "idle", failure: null },
          details: "",
        });
        const quiet = () => undefined;
        const control = (snap) => ({
          offered: true,
          read: { kind: "ready", value: { revision: 1, state: "ready", snapshot: snap } },
          snapshot: snap, pending: false, busy: () => false,
          startingOf: () => false, refusal: null, check: quiet, verify: quiet,
          start: quiet, answer: quiet, cancel: quiet,
          removeModel: () => Promise.resolve(null),
          remove: () => Promise.resolve(null),
          signInGoogle: quiet, signOutGoogle: quiet, clearRefusal: quiet,
        });
        // The lists are read in an effect, which never runs here: they stay
        // loading, so no model row is listed and no model has been asked for.
        const host = {
          read: () => new Promise(() => undefined),
          add: () => Promise.reject(new Error("unused")),
          remove: () => Promise.reject(new Error("unused")),
          reset: () => Promise.reject(new Error("unused")),
        };
        function Stage({ scene }) {
          const store = useProvisioningStore(
            control(snapshot("local_ai", scene.stage, scene.planned)),
            "owner",
          );
          return createElement(
            ProvisioningContext.Provider,
            { value: store },
            scene.what === "section"
              ? createElement(LocalModels, { lane: scene.lane, host, locale: "en" })
              : createElement(LocalAi, {
                  lanes: [scene.lane], host, locale: "en",
                }),
          );
        }
        export const draw = (scene) =>
          renderToStaticMarkup(createElement(Stage, { scene }));
      `,
      resolveDir: root,
      loader: "js",
    },
    bundle: true,
    write: false,
    platform: "node",
    format: "cjs",
    jsx: "automatic",
    logLevel: "silent",
    plugins: [
      {
        name: "desktop-strings",
        setup(plugin) {
          plugin.onResolve({ filter: /^virtual:desktop-strings$/ }, () => ({
            path: "desktop-strings",
            namespace: "stub",
          }));
          plugin.onLoad({ filter: /.*/, namespace: "stub" }, () => ({
            contents: "export default { en: {} };",
            loader: "js",
          }));
        },
      },
    ],
  });
  const module = { exports: {} as { draw: Draw } };
  new Function(
    "module",
    "exports",
    "require",
    built.outputFiles.map((file) => file.text).join(""),
  )(module, module.exports, createRequire(import.meta.url));
  return module.exports.draw;
}

const reviews = (markup: string) =>
  markup.split("data-setup-review").length - 1;

test("a model section that stands alone shows the plan it finds waiting, once, at section level", async () => {
  const markup = (await compiled())({
    what: "section",
    lane: SECOND,
    stage: "review",
    planned: SECOND_VISION,
  });
  expect(markup).toContain('data-slot="local-models-review"');
  expect(reviews(markup)).toBe(1);
  expect(markup).toContain(SECOND_VISION);
});

test("a model section that stands alone shows no plan once the setup runs, or for another lane's model", async () => {
  const draw = await compiled();
  expect(
    draw({
      what: "section",
      lane: SECOND,
      stage: "running",
      planned: SECOND_VISION,
    }),
  ).not.toContain("data-setup-review");
  expect(
    draw({ what: "section", lane: SECOND, stage: "review", planned: VISION }),
  ).not.toContain("data-setup-review");
});

test("under the local AI the plan found waiting is answered on the program's row alone", async () => {
  const markup = (await compiled())({
    what: "local_ai",
    lane: LANE,
    stage: "review",
    planned: VISION,
  });
  expect(reviews(markup)).toBe(1);
  expect(markup).not.toContain('data-slot="local-models-review"');
  const program = markup.indexOf('data-setup-row="local_ai"');
  expect(program).toBeGreaterThanOrEqual(0);
  expect(markup.indexOf("data-setup-review")).toBeGreaterThan(program);
});
