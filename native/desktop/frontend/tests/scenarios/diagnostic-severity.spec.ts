import { expect, test } from "@playwright/test";

// A refusal the window answers by asking again is a warning; the refusal that
// ends the asking, and any refusal that does not pass by waiting, is an error.
// The real Tauri adapter runs against a recording invoke boundary.

type Report = { level: string; command: string | null; code: string | null };

for (const [name, code, scheduled, level] of [
  [
    "a busy refusal that will be asked again",
    "agent_service_busy",
    true,
    "WARNING",
  ],
  [
    "a reconnecting refusal that will be asked again",
    "agent_reconnecting",
    true,
    "WARNING",
  ],
  ["a busy refusal with no further ask", "agent_service_busy", false, "ERROR"],
  [
    "a failure that waiting does not cure",
    "agent_service_failed",
    true,
    "ERROR",
  ],
] as const)
  test(`${name} is reported at ${level}`, async ({ page }) => {
    await page.goto("/scenarios.html");
    const reports = await page.evaluate(
      async ({ code, scheduled }) => {
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
          .providerCatalog(catalogReadRetry(() => scheduled))
          .catch(() => undefined);
        return reports;
      },
      { code, scheduled },
    );
    expect(reports).toMatchObject([
      { level, command: "agent_provider_catalog", code },
    ]);
  });

for (const busyReads of [1, 4])
  test(`Local AI catalog reads busy ${busyReads} time(s): warnings while it retries, an error only when it gives up`, async ({
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
        ? { status: "ready", reads: 2, levels: ["WARNING"] }
        : {
            status: "failed",
            reads: 4,
            levels: ["WARNING", "WARNING", "WARNING", "ERROR"],
          },
    );
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
