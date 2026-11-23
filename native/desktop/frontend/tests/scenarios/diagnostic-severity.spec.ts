import { expect, test } from "@playwright/test";

// A refusal the window answers by asking again, within the wait the caller
// expects, is a debug note; one asked again past that wait is a warning; the
// refusal that ends the asking, and any refusal that does not pass by
// waiting, is an error. A read that lists models is the exception: what it
// answers of the person's setup is a state, noted at INFO. The real Tauri
// adapter runs against a recording invoke boundary.

type Report = { level: string; command: string | null; code: string | null };

// A catalogue read that answers busy reports where the agent's start stands:
// it is noted at INFO, said as the agent starting, and read again on the
// next status the service publishes. Nothing asks again on a timer, so two
// minutes of the page's clock bring no further read.
test("Local AI catalog read busy: noted at INFO and read again on the next published status, not on a timer", async ({
  page,
}) => {
  await page.clock.install();
  await page.goto("/scenarios.html?scenario=signed-out&bar=off");
  await page.waitForFunction(() => Boolean(window.__scenarioModules));
  await page.evaluate(async () => {
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
    type Status = import("../../src/shell/agentSession").AgentServiceStatus;
    const held = {
      reads: 0,
      busy: true,
      levels: [] as string[],
      status: "",
      failure: null as string | null,
      publish: null as ((status: Status) => void) | null,
    };
    (window as unknown as { __localAi: typeof held }).__localAi = held;
    Object.assign(window, {
      __CADRUMO_SHELL__: { token: "d".repeat(64) },
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
            if (held.busy) throw { code: "agent_service_busy" };
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
      status: async (): Promise<Status> => ({
        state: "ready",
        agent_version: "fixture",
      }),
      observeStatus: async (listener: (status: Status) => void) => {
        held.publish = listener;
        return () => {};
      },
    };
    function Probe() {
      const current = lanes.useLocalAiLanes(
        { reader: "A", session, providerSettings: provider },
        true,
        0,
      );
      react.useLayoutEffect(() => {
        held.status = current.status;
        held.failure = current.failure;
      });
      return null;
    }
    const container = document.createElement("div");
    document.body.append(container);
    dom.flushSync(() =>
      client.createRoot(container).render(react.createElement(Probe)),
    );
  });
  const view = () =>
    page.evaluate(() => {
      const held = (
        window as unknown as {
          __localAi: {
            reads: number;
            levels: string[];
            status: string;
            failure: string | null;
          };
        }
      ).__localAi;
      return {
        reads: held.reads,
        levels: [...held.levels],
        status: held.status,
        failure: held.failure,
      };
    });
  await expect
    .poll(async () => (await view()).failure)
    .toBe("agent_service_busy");
  for (let step = 0; step < 12; step++) {
    await page.clock.fastForward("00:10");
    await page.waitForTimeout(20);
  }
  expect(await view()).toEqual({
    reads: 1,
    levels: ["INFO"],
    status: "failed",
    failure: "agent_service_busy",
  });
  // The service publishes the agent's status: that is the cue.
  await page.evaluate(() => {
    const held = (
      window as unknown as {
        __localAi: {
          busy: boolean;
          publish: (status: { state: "ready"; agent_version: string }) => void;
        };
      }
    ).__localAi;
    held.busy = false;
    held.publish({ state: "ready", agent_version: "fixture" });
  });
  await expect.poll(async () => (await view()).status).toBe("ready");
  expect((await view()).reads).toBe(2);
});

/** What the agent column's catalog hook, mounted alone over the real Tauri
 * adapter whose service answers every catalog read busy, has asked and had
 * recorded. */
type BusyColumn = {
  reads: number;
  levels: string[];
  publish: () => void;
};

test("an agent column whose service stays busy notes each refusal at INFO and asks again only when a status is published", async ({
  page,
}) => {
  await page.clock.install();
  await page.goto("/scenarios.html?scenario=signed-out&bar=off");
  await page.waitForFunction(() => Boolean(window.__scenarioModules));
  await page.evaluate(async () => {
    const { react, dom, client } =
      await window.__scenarioModules!.profileViews();
    const hook = await window.__scenarioModules!.agentCatalog();
    const held: BusyColumn = { reads: 0, levels: [], publish: () => {} };
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
    const t = ((key: string) =>
      key) as unknown as import("../../src/shell/strings").Translate;
    function Probe() {
      const [status, setStatus] = react.useState<Status>({
        state: "ready",
        agent_version: "fixture",
      });
      held.publish = () =>
        setStatus({ state: "ready", agent_version: "fixture" });
      hook.useAgentCatalog({
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
      return null;
    }
    const container = document.createElement("div");
    document.body.append(container);
    dom.flushSync(() =>
      client.createRoot(container).render(react.createElement(Probe)),
    );
  });
  const column = () =>
    page.evaluate(() => {
      const held = (window as unknown as { __busyColumn: BusyColumn })
        .__busyColumn;
      return { reads: held.reads, levels: [...held.levels] };
    });
  await expect.poll(async () => (await column()).levels.length).toBe(1);
  // Two minutes pass with nothing published: nothing is asked again.
  for (let step = 0; step < 24; step++) {
    await page.clock.fastForward(5_000);
    await page.waitForTimeout(20);
  }
  expect(await column()).toEqual({ reads: 1, levels: ["INFO"] });
  await page.evaluate(() =>
    (window as unknown as { __busyColumn: BusyColumn }).__busyColumn.publish(),
  );
  await expect.poll(async () => (await column()).reads).toBe(2);
  await expect
    .poll(async () => (await column()).levels)
    .toEqual(["INFO", "INFO"]);
});

// A send the agent refuses for a model this computer does not hold, or for a
// provider with no key or sign-in yet, is said to the person with its next
// step: it is noted as a warning with its code. A send refusal the column has
// no next step for stays an error.
for (const [code, level] of [
  ["agent_gateway_model_not_installed", "WARNING"],
  ["agent_gateway_model_does_not_fit", "WARNING"],
  ["agent_provider_credential_missing", "WARNING"],
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

// A Sede view open refused `conflict` while the previous view publishes its
// session is the handover the panel waits on: noted below a warning while the
// panel asks again within the wait it expects, a warning once the wait runs
// long, and a warning when the panel does not ask again.
for (const [scheduled, expected, level] of [
  [true, true, "DEBUG"],
  [true, false, "WARNING"],
  [false, true, "WARNING"],
] as const)
  test(`a Sede view open refused conflict, scheduled=${scheduled} expected=${expected}, is reported at ${level}`, async ({
    page,
  }) => {
    await page.goto("/scenarios.html");
    const reports = await page.evaluate(
      async ([scheduled, expected]) => {
        const reports: Report[] = [];
        Object.assign(window, {
          __CADRUMO_SHELL__: { token: "e".repeat(64) },
          __TAURI_INTERNALS__: {
            transformCallback: () => 0,
            async invoke(command: string, args: unknown) {
              if (command === "desktop_frontend_diagnostic") {
                reports.push((args as { report: Report }).report);
                return null;
              }
              throw { code: "conflict" };
            },
          },
        });
        const { tauriHost } = await window.__scenarioModules!.tauriHost();
        const refused = await tauriHost()
          .sedeView!.open(
            { cssWidth: 800, cssHeight: 600, scale: 1 },
            () => undefined,
            { scheduled: () => scheduled, expected: () => expected },
          )
          .then(
            () => null,
            (error: { code?: string }) => error.code ?? null,
          );
        await new Promise((resolve) => window.setTimeout(resolve, 0));
        return { refused, reports };
      },
      [scheduled, expected] as const,
    );
    expect(reports.refused).toBe("conflict");
    expect(reports.reports).toMatchObject([
      { level, command: "sede_view_open", code: "conflict" },
    ]);
  });
