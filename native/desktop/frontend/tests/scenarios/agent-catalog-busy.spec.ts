import { expect, test, type Page } from "@playwright/test";
import {
  agentColumn as column,
  offeredModels,
  openHistory,
  openModelPicker,
  pickWay,
  scenarioOnly,
} from "../support/agent";
import { label } from "../support/strings";

// A service still starting the agent can be too busy to answer its catalog.
// The column says the agent is still starting, and reads the catalog again
// on a cue: when the service publishes the agent's status, or the person
// comes back to the window. Nothing asks again on a timer.

test.beforeEach(() => {
  scenarioOnly("The scenario host decides when the service is busy.");
});

test("an unsupported platform reports its capability without catalog or model reads", async ({
  page,
}) => {
  await page.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&catalog=unsupported",
  );
  await expect(column(page).getByRole("status")).toContainText(
    label("desktop.agent.platform_unsupported"),
  );
  await expect(
    column(page).getByRole("button", {
      name: label("desktop.agent.retry"),
      exact: true,
    }),
  ).toHaveCount(0);
  await page.waitForTimeout(1200);
  const calls = await page.evaluate(() => window.__scenarioHostCalls ?? []);
  expect(
    calls.filter(
      (call) => call === "agentProviderCatalog" || call === "agentLocalModels",
    ),
  ).toEqual([]);
});

test("history waits for the agent and refreshes after service recovery", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  await expect
    .poll(() =>
      page.evaluate(() =>
        (window.__scenarioHostCalls ?? []).includes(
          "agentProviderCatalogResolved",
        ),
      ),
    )
    .toBe(true);
  await page.evaluate(() =>
    window.__scenarioAgentPublishStatus?.({ state: "starting" }),
  );
  await expect(
    column(page).getByText(label("desktop.agent.service_starting")),
  ).toBeVisible();
  await openHistory(page);
  const reads = () =>
    page.evaluate(
      () =>
        (window.__scenarioHostCalls ?? []).filter(
          (call) => call === "agentConversations",
        ).length,
    );
  expect(await reads()).toBe(0);
  await page.evaluate(() => window.__scenarioAgentPublishStatus?.());
  await expect.poll(reads).toBe(1);
  await expect(
    column(page).getByText(label("desktop.agent.service_signed_out")),
  ).toHaveCount(0);
  await page.evaluate(() =>
    window.__scenarioAgentPublishStatus?.({
      state: "refused",
      code: "agent_service_failed",
    }),
  );
  await expect(
    column(page)
      .locator(".agent-body")
      .getByText(label("desktop.agent.unavailable"), { exact: true }),
  ).toBeVisible();
  expect(await reads()).toBe(1);
  await page.evaluate(() => window.__scenarioAgentPublishStatus?.());
  await expect.poll(reads).toBe(2);
});

test("a catalog the busy service cannot answer yet is read again once the agent's status is published", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&catalog=busy",
  );
  const starting = column(target).getByText(
    label("desktop.agent.service_starting"),
  );
  await expect(starting).toBeVisible();
  // Nothing can be chosen while the catalog is unread.
  await expect(
    column(target).getByRole("button", {
      name: label("desktop.agent.choose_model"),
      exact: false,
    }),
  ).toHaveAccessibleName(new RegExp(label("desktop.agent.unavailable")));

  // The signal: the service publishes the agent's status.
  await target.evaluate(() => window.__scenarioAgentPublishStatus?.());
  await expect(starting).toHaveCount(0);
  await expect(
    column(target).getByRole("button", {
      name: label("desktop.agent.choose_model"),
      exact: false,
    }),
  ).toHaveCount(0);
  const calls = await target.evaluate(() => window.__scenarioHostCalls ?? []);
  expect(
    calls.filter((call) => call === "agentProviderCatalogResolved").length,
  ).toBeGreaterThanOrEqual(1);
});

test("the stored model lists are not asked for while the agent starts, and are read and applied once it runs", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&setup=ready&catalog=declared",
  );
  await expect(
    column(target).getByText(label("desktop.agent.service_starting")),
  ).toBeVisible();
  const localModelReads = () =>
    target.evaluate(
      () =>
        (window.__scenarioHostCalls ?? []).filter(
          (call) => call === "agentLocalModels",
        ).length,
    );
  // The catalog is asked for while starting, with its own retry; the lists
  // have none, and the host refuses them until the service has a connection.
  await expect
    .poll(() =>
      target.evaluate(() =>
        (window.__scenarioHostCalls ?? []).includes("agentProviderCatalog"),
      ),
    )
    .toBe(true);
  await target.waitForTimeout(600);
  expect(await localModelReads()).toBe(0);
  await target.evaluate(() => window.__scenarioAgentPublishStatus?.());
  await expect.poll(localModelReads).toBeGreaterThanOrEqual(1);
  // The lists read at ready are applied: the local lane serves a model nobody
  // put on its list, and the picker leaves it out. Lists left unread would
  // offer it.
  const picker = await openModelPicker(target);
  await pickWay(target, picker, "zai/api");
  expect(await offeredModels(picker)).toEqual([
    "synthetic-text:1",
    "synthetic-vision:1",
  ]);
});

/** How many times the window has asked for the catalog. */
const catalogReads = (target: Page) =>
  target.evaluate(
    () =>
      (window.__scenarioHostCalls ?? []).filter(
        (call) => call === "agentProviderCatalog",
      ).length,
  );

/** Two minutes on the page's clock, in steps, so anything the window had
 * scheduled would have run. */
const pass = async (target: Page) => {
  for (let step = 0; step < 12; step++) {
    await target.clock.fastForward("00:10");
    await target.waitForTimeout(50);
  }
};

/** The person comes back to the window. */
const comeBack = (target: Page) =>
  target.evaluate(() => window.dispatchEvent(new Event("focus")));

test("a catalog still busy just after the agent is ready says it is starting and is read again when the person comes back, not on a timer", async ({
  page: target,
}) => {
  await target.clock.install();
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&catalog=busy-past-ready",
  );
  const starting = column(target).getByText(
    label("desktop.agent.service_starting"),
  );
  await expect(starting).toBeVisible();
  // A long start: the busy answer is said, and nothing asks again by itself.
  await expect.poll(() => catalogReads(target)).toBe(1);
  await pass(target);
  expect(await catalogReads(target)).toBe(1);

  // The agent is ready, and the service stays busy for a moment longer: the
  // published status is the cue for one read.
  await target.evaluate(() => window.__scenarioAgentPublishStatus?.());
  await expect.poll(() => catalogReads(target)).toBe(2);
  await pass(target);
  expect(await catalogReads(target)).toBe(2);
  await expect(starting).toBeVisible();

  // The person comes back to the window: the service answers now, and the
  // choices appear.
  await comeBack(target);
  await expect.poll(() => catalogReads(target)).toBe(3);
  await expect(starting).toHaveCount(0);
  await expect(
    column(target).getByRole("button", {
      name: label("desktop.agent.choose_model"),
      exact: false,
    }),
  ).toHaveCount(0);
  const calls = await target.evaluate(() => window.__scenarioHostCalls ?? []);
  expect(calls).toContain("agentProviderCatalogResolved");
});

test("while the service stays busy the settings say the agent is starting in the local AI's place, offering no retry that cannot help", async ({
  page: target,
}) => {
  await target.clock.install();
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&catalog=busy",
  );
  await expect(
    column(target).getByText(label("desktop.agent.service_starting")),
  ).toBeVisible();
  await pass(target);
  const asked = await catalogReads(target);
  await column(target)
    .getByRole("button", { name: label("desktop.agent.settings") })
    .click();
  const providers = column(target).getByRole("region", {
    name: label("desktop.providers.title"),
  });
  await providers
    .locator('li[data-provider="zai"] > details')
    .evaluate((node) => ((node as HTMLDetailsElement).open = true));
  const said = providers
    .locator('li[data-provider="zai"] [data-model-list-state="starting"]')
    .first();
  await expect(said).toContainText(label("desktop.agent.service_starting"));
  await expect(
    said.getByRole("button", { name: label("desktop.agent.retry") }),
  ).toHaveCount(0);
  // Opening the settings is a cue; the time that passes after it is not.
  const opened = await catalogReads(target);
  expect(opened).toBeGreaterThanOrEqual(asked);
  await pass(target);
  expect(await catalogReads(target)).toBe(opened);
});

/** The agent column's catalog hook, mounted alone over a service that
 * answers busy until the probe lets it answer. */
type CatalogProbe = {
  reads: number;
  busy: boolean;
  kind: string;
  /** Timers the hook left scheduled. */
  pending: Set<number>;
  publish(state: "ready" | "stopped" | "refused"): void;
};

const probe = (target: Page) =>
  target.evaluate(() => {
    const held = (window as unknown as { __catalogProbe: CatalogProbe })
      .__catalogProbe;
    return { reads: held.reads, kind: held.kind, pending: held.pending.size };
  });

const mountProbe = (target: Page) =>
  target.evaluate(async () => {
    const { react, dom, client } =
      await window.__scenarioModules!.profileViews();
    const hook = await window.__scenarioModules!.agentCatalog();
    const { agent } = await window.__scenarioModules!.localAiReads();
    const fixture = agent.fixtureAgent({
      say: () => {},
      wait: async () => {},
      signedIn: () => true,
      readable: () => true,
      empty: true,
      stream: "steady",
      asks: null,
      refused: () => new Error("refused"),
    });
    const answer = await fixture.session.providerCatalog();
    const held: CatalogProbe = {
      reads: 0,
      busy: true,
      kind: "unavailable",
      pending: new Set(),
      publish: () => {},
    };
    (window as unknown as { __catalogProbe: CatalogProbe }).__catalogProbe =
      held;
    // Any timer of a second or more the page schedules from here on.
    const setTimer = window.setTimeout.bind(window);
    const clearTimer = window.clearTimeout.bind(window);
    window.setTimeout = ((
      callback: TimerHandler,
      delay?: number,
      ...args: unknown[]
    ) => {
      if (typeof callback !== "function" || (delay ?? 0) < 1_000)
        return setTimer(callback, delay, ...args);
      const id = setTimer(() => {
        held.pending.delete(id);
        callback(...args);
      }, delay);
      held.pending.add(id);
      return id;
    }) as typeof window.setTimeout;
    window.clearTimeout = (id) => {
      if (typeof id === "number") held.pending.delete(id);
      clearTimer(id);
    };
    const session = {
      ...fixture.session,
      providerCatalog: async () => {
        held.reads += 1;
        if (held.busy) throw { code: "agent_service_busy" };
        return answer;
      },
    };
    type Status = import("../../src/shell/agentSession").AgentServiceStatus;
    const statuses = {
      ready: (): Status => ({ state: "ready", agent_version: "fixture" }),
      stopped: (): Status => ({ state: "stopped" }),
      refused: (): Status => ({
        state: "refused",
        code: "agent_service_failed",
      }),
    };
    const t = ((key: string) =>
      key) as unknown as import("../../src/shell/strings").Translate;
    function Probe() {
      const [status, setStatus] = react.useState<Status>(statuses.ready);
      const view = hook.useAgentCatalog({
        t,
        reader: "A",
        session,
        status,
        readingHost: null,
        setupSettled: null,
        settingsChanges: 0,
        settings: null,
        opened: 0,
        listChanges: 0,
        pickerOpened: 0,
        chosen: null,
        ranWith: undefined,
        fixedWay: null,
      });
      react.useLayoutEffect(() => {
        held.kind = view.catalog.kind;
        held.publish = (state) => setStatus(statuses[state]());
      });
      return null;
    }
    const container = document.createElement("div");
    document.body.append(container);
    dom.flushSync(() =>
      client.createRoot(container).render(react.createElement(Probe)),
    );
  });

const publish = (target: Page, state: "ready" | "stopped" | "refused") =>
  target.evaluate((state) => {
    (
      window as unknown as { __catalogProbe: CatalogProbe }
    ).__catalogProbe.publish(state);
  }, state);

test("a busy catalog schedules nothing and is read again once per published status until it loads", async ({
  page: target,
}) => {
  await target.clock.install();
  await target.goto("/scenarios.html?scenario=signed-out&bar=off");
  await target.waitForFunction(() => Boolean(window.__scenarioModules));
  await mountProbe(target);
  await expect.poll(async () => (await probe(target)).kind).toBe("failed");
  await pass(target);
  expect(await probe(target)).toMatchObject({ reads: 1, pending: 0 });

  // Each publication is one read.
  await publish(target, "ready");
  await expect.poll(async () => (await probe(target)).reads).toBe(2);
  await pass(target);
  expect(await probe(target)).toMatchObject({ reads: 2, pending: 0 });

  // A service that stopped or refused is not asked at all.
  for (const state of ["stopped", "refused"] as const) {
    await publish(target, state);
    await expect
      .poll(async () => (await probe(target)).kind)
      .toBe("unavailable");
    await pass(target);
    expect(await probe(target)).toMatchObject({ reads: 2, pending: 0 });
  }

  // Ready again, and the service answers.
  await target.evaluate(() => {
    (
      window as unknown as { __catalogProbe: CatalogProbe }
    ).__catalogProbe.busy = false;
  });
  await publish(target, "ready");
  await expect.poll(async () => (await probe(target)).kind).toBe("ready");
  expect(await probe(target)).toMatchObject({ reads: 3, pending: 0 });
});
