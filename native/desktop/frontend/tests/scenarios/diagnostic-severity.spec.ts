import { expect, test } from "@playwright/test";

// A refusal the window answers by asking again, within the wait the caller
// expects, is a debug note; one asked again past that wait is a warning; the
// refusal that ends the asking, and any refusal that does not pass by
// waiting, is an error. The real Tauri adapter runs against a recording
// invoke boundary.

type Report = { level: string; command: string | null; code: string | null };

for (const [name, code, scheduled, expected, level] of [
  [
    "a busy refusal that will be asked again within the expected wait",
    "agent_service_busy",
    true,
    true,
    "DEBUG",
  ],
  [
    "a busy refusal that will be asked again past the expected wait",
    "agent_service_busy",
    true,
    false,
    "WARNING",
  ],
  [
    "a busy refusal asked again by a caller that names no expected wait",
    "agent_service_busy",
    true,
    null,
    "WARNING",
  ],
  [
    "a reconnecting refusal that will be asked again within the expected wait",
    "agent_reconnecting",
    true,
    true,
    "DEBUG",
  ],
  [
    "a busy refusal with no further ask",
    "agent_service_busy",
    false,
    true,
    "ERROR",
  ],
  [
    "a failure that waiting does not cure",
    "agent_service_failed",
    true,
    true,
    "ERROR",
  ],
] as const)
  test(`${name} is reported at ${level}`, async ({ page }) => {
    await page.goto("/scenarios.html");
    const reports = await page.evaluate(
      async ({ code, scheduled, expected }) => {
        const reports: Report[] = [];
        Object.assign(window, {
          __CADRUMO_SHELL__: { token: "c".repeat(64) },
          __TAURI_INTERNALS__: {
            async invoke(command: string, args: unknown) {
              if (command === "desktop_frontend_diagnostic") {
                reports.push((args as { report: Report }).report as Report);
                return null;
              }
              throw { code };
            },
          },
        });
        const { catalogReadRetry } =
          await window.__scenarioModules!.catalogReadPolicy();
        const { tauriHost } = await window.__scenarioModules!.tauriHost();
        const session = tauriHost().agentSession!;
        await session
          .providerCatalog(
            catalogReadRetry(
              () => scheduled,
              expected === null ? undefined : () => expected,
            ),
          )
          .catch(() => undefined);
        return reports;
      },
      { code, scheduled, expected },
    );
    expect(reports).toMatchObject([
      { level, command: "agent_provider_catalog", code },
    ]);
  });

for (const busyReads of [1, 4])
  test(`Local AI catalog reads busy ${busyReads} time(s): debug notes while it retries, an error only when it gives up`, async ({
    page,
  }) => {
    await page.goto("/scenarios.html?scenario=signed-out&bar=off");
    await page.waitForFunction(() => Boolean(window.__scenarioModules));
    const result = await page.evaluate(async (busyReads) => {
      const { react, dom, client } =
        await window.__scenarioModules!.profileViews();
      const { lanes, agent, providers } =
        await window.__scenarioModules!.localAiReads();
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
      const provider = providers.providerSettingsFixture({
        say: () => {},
        wait: async () => {},
        readable: () => true,
      }).settings;
      const answer = await fixture.session.providerCatalog();
      const reports: Report[] = [];
      let reads = 0;
      Object.assign(window, {
        __CADRUMO_SHELL__: { token: "d".repeat(64) },
        __TAURI_INTERNALS__: {
          async invoke(command: string, args: unknown) {
            if (command === "desktop_frontend_diagnostic") {
              reports.push((args as { report: Report }).report);
              return null;
            }
            if (command === "agent_status")
              return { state: "ready", agent_version: "fixture" };
            if (command === "agent_provider_catalog") {
              reads += 1;
              if (reads <= busyReads) throw { code: "agent_service_busy" };
              return answer;
            }
            return null;
          },
        },
      });
      const { tauriHost } = await window.__scenarioModules!.tauriHost();
      const real = tauriHost().agentSession!;
      const session = {
        ...real,
        status: async () => ({
          state: "ready" as const,
          agent_version: "fixture",
        }),
        observeStatus: async () => () => {},
      };
      // The recovery pauses are shortened; React scheduling stays real.
      const realTimeout = window.setTimeout.bind(window);
      window.setTimeout = ((
        callback: TimerHandler,
        delay?: number,
        ...args: unknown[]
      ) =>
        realTimeout(
          callback,
          delay !== undefined && delay >= 2_000 ? delay / 200 : delay,
          ...args,
        )) as typeof window.setTimeout;
      let view!: import("../../src/shell/localAiLanes").LocalAiLanes;
      function Probe() {
        const current = lanes.useLocalAiLanes(
          { reader: "A", session, providerSettings: provider },
          true,
          0,
        );
        react.useLayoutEffect(() => {
          view = current;
        });
        return null;
      }
      const container = document.createElement("div");
      document.body.append(container);
      const root = client.createRoot(container);
      try {
        dom.flushSync(() => root.render(react.createElement(Probe)));
        // Before the status is known the lanes read as failed, so wait for the
        // reads the case makes, then let the last one settle.
        const expected = Math.min(busyReads + 1, 4);
        for (let at = 0; at < 200 && reads < expected; at++)
          await new Promise((resolve) => realTimeout(resolve, 20));
        await new Promise((resolve) => realTimeout(resolve, 150));
        return {
          status: view.status,
          reads,
          levels: reports
            .filter((report) => report.command === "agent_provider_catalog")
            .map((report) => report.level),
        };
      } finally {
        dom.flushSync(() => root.unmount());
        container.remove();
        window.setTimeout = realTimeout;
      }
    }, busyReads);
    expect(result).toEqual(
      busyReads === 1
        ? { status: "ready", reads: 2, levels: ["DEBUG"] }
        : {
            status: "failed",
            reads: 4,
            levels: ["DEBUG", "DEBUG", "DEBUG", "ERROR"],
          },
    );
  });

/** What the agent column's catalog hook, mounted alone over the real Tauri
 * adapter whose service answers every catalog read busy, has asked and had
 * recorded. */
type BusyColumn = { reads: number; levels: string[] };

test("an agent column whose service stays busy past the quiet bound records one warning, and none before", async ({
  page,
}) => {
  await page.clock.install();
  await page.goto("/scenarios.html?scenario=signed-out&bar=off");
  await page.waitForFunction(() => Boolean(window.__scenarioModules));
  const bound = await page.evaluate(async () => {
    const { react, dom, client } =
      await window.__scenarioModules!.profileViews();
    const hook = await window.__scenarioModules!.agentCatalog();
    const { CATALOG_BUSY_QUIET_MS } =
      await window.__scenarioModules!.catalogReadPolicy();
    const held: BusyColumn = { reads: 0, levels: [] };
    (window as unknown as { __busyColumn: BusyColumn }).__busyColumn = held;
    Object.assign(window, {
      __CADRUMO_SHELL__: { token: "f".repeat(64) },
      __TAURI_INTERNALS__: {
        async invoke(command: string, args: unknown) {
          if (command === "desktop_frontend_diagnostic") {
            const report = (args as { report: Report }).report;
            if (report.command === "agent_provider_catalog")
              held.levels.push(report.level);
            return null;
          }
          if (command === "agent_provider_catalog") {
            held.reads += 1;
            throw { code: "agent_service_busy" };
          }
          return null;
        },
      },
    });
    const { tauriHost } = await window.__scenarioModules!.tauriHost();
    const session = tauriHost().agentSession!;
    type Status = import("../../src/shell/agentSession").AgentServiceStatus;
    const status: Status = { state: "ready", agent_version: "fixture" };
    const t = ((key: string) =>
      key) as unknown as import("../../src/shell/strings").Translate;
    function Probe() {
      hook.useAgentCatalog({
        t,
        reader: "A",
        session,
        status,
        readingHost: null,
        setupSettled: null,
        settingsChanges: 0,
        opened: 0,
        listChanges: 0,
        chosen: null,
        ranWith: undefined,
      });
      return null;
    }
    const container = document.createElement("div");
    document.body.append(container);
    dom.flushSync(() =>
      client.createRoot(container).render(react.createElement(Probe)),
    );
    return CATALOG_BUSY_QUIET_MS;
  });
  const column = () =>
    page.evaluate(
      () => (window as unknown as { __busyColumn: BusyColumn }).__busyColumn,
    );
  // Steps longer than the column's longest pause: each pause is scheduled
  // only once the read before it has been shown.
  const step = 5_000;
  const advance = async (steps: number) => {
    for (let at = 0; at < steps; at++) {
      await page.clock.fastForward(step);
      await page.waitForTimeout(50);
    }
  };
  await expect
    .poll(async () => (await column()).levels.length)
    .toBeGreaterThanOrEqual(1);
  // Up to a step short of the bound every busy read is the wait expected.
  await advance(Math.floor(bound / step) - 1);
  const within = await column();
  expect(within.reads).toBeGreaterThan(10);
  expect(within.levels).toEqual(Array(within.reads).fill("DEBUG"));
  // Past the bound the first busy read is one warning, and the reads that
  // follow it are noted below a warning again.
  await advance(6);
  const past = await column();
  expect(past.reads).toBeGreaterThan(within.reads + 2);
  expect(past.levels.filter((level) => level === "WARNING")).toHaveLength(1);
  expect(past.levels.filter((level) => level !== "WARNING")).toEqual(
    Array(past.levels.length - 1).fill("DEBUG"),
  );
  expect(past.levels.at(-1)).toBe("DEBUG");
});

// A send the agent refuses for a model this computer does not hold is said
// to the person with its next step: it is noted as a warning with its code.
// A send refusal the column has no next step for stays an error.
for (const [code, level] of [
  ["agent_gateway_model_not_installed", "WARNING"],
  ["agent_gateway_422", "ERROR"],
] as const)
  test(`a send refused with ${code} is reported at ${level}`, async ({
    page,
  }) => {
    await page.goto("/scenarios.html");
    const reports = await page.evaluate(async (code) => {
      const reports: Report[] = [];
      Object.assign(window, {
        __CADRUMO_SHELL__: { token: "e".repeat(64) },
        __TAURI_INTERNALS__: {
          async invoke(command: string, args: unknown) {
            if (command === "desktop_frontend_diagnostic") {
              reports.push((args as { report: Report }).report);
              return null;
            }
            throw { code };
          },
        },
      });
      const { tauriHost } = await window.__scenarioModules!.tauriHost();
      const refused = await tauriHost()
        .agentSession!.send({
          conversation_id: "c",
          text: "Hello",
          selection: { provider: "local", transport: "api", model: "m" },
        })
        .then(
          () => null,
          (error: { code?: string }) => error.code ?? null,
        );
      // The record is made once the refusal is known.
      await new Promise((resolve) => window.setTimeout(resolve, 0));
      return { refused, reports };
    }, code);
    expect(reports.refused).toBe(code);
    expect(reports.reports).toMatchObject([
      { level, command: "agent_send", code },
    ]);
  });
