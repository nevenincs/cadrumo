import { expect, test } from "@playwright/test";

// The signed-in session can end while the Local AI lanes are being read. A read
// still pending when the window learns of the end is not followed by the
// provider-status read at all; one already with the host when the window
// learns of the end is refused for an end the log notes once, at INFO, like
// every refusal for an ended session. A provider-status refusal the window did
// not see coming stays an error and is not asked again: an earlier admitted
// catalog read does not prove the runtime session was still valid. The real
// Tauri adapter runs against a recording invoke boundary.

type Report = { level: string; command: string | null; code: string | null };

async function run(
  page: import("@playwright/test").Page,
  scenario: "refused" | "ended-first" | "ended-in-flight",
) {
  await page.goto("/scenarios.html?scenario=signed-out&bar=off");
  await page.waitForFunction(() => Boolean(window.__scenarioModules));
  return page.evaluate(async (scenario) => {
    const { react, dom, client } =
      await window.__scenarioModules!.profileViews();
    const { lanes, agent } = await window.__scenarioModules!.localAiReads();
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
    const reports: Report[] = [];
    const calls: string[] = [];
    let admit!: () => void;
    const admitted = new Promise<void>((resolve) => (admit = resolve));
    let answerStatus!: () => void;
    const statusAnswer = new Promise<void>(
      (resolve) => (answerStatus = resolve),
    );
    Object.assign(window, {
      __CADRUMO_SHELL__: { token: "e".repeat(64) },
      __TAURI_INTERNALS__: {
        async invoke(command: string, args: unknown) {
          if (command === "desktop_frontend_diagnostic") {
            reports.push((args as { report: Report }).report);
            return null;
          }
          calls.push(command);
          if (command === "agent_provider_catalog") {
            if (scenario === "ended-first") await admitted;
            return answer;
          }
          if (command === "provider_settings_status") {
            if (scenario === "ended-in-flight") await statusAnswer;
            throw { code: "not_signed_in" };
          }
          return null;
        },
      },
    });
    const { tauriHost } = await window.__scenarioModules!.tauriHost();
    const host = tauriHost();
    const real = host.agentSession!;
    const session = {
      ...real,
      status: async () => ({
        state: "ready" as const,
        agent_version: "fixture",
      }),
      observeStatus: async () => () => {},
    };
    let view!: import("../../src/shell/localAiLanes").LocalAiLanes;
    function Probe(props: { reader: string | null }) {
      const current = lanes.useLocalAiLanes(
        {
          reader: props.reader,
          session,
          providerSettings: host.providerSettings!,
        },
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
    const settle = () => new Promise((resolve) => setTimeout(resolve, 250));
    try {
      dom.flushSync(() =>
        root.render(react.createElement(Probe, { reader: "A" })),
      );
      if (scenario === "ended-first") {
        for (
          let at = 0;
          at < 100 && !calls.includes("agent_provider_catalog");
          at++
        )
          await new Promise((resolve) => setTimeout(resolve, 20));
        // The session ends: the window withdraws the reader, then the
        // catalog read it had in flight answers.
        dom.flushSync(() =>
          root.render(react.createElement(Probe, { reader: null })),
        );
        admit();
      }
      if (scenario === "ended-in-flight") {
        for (
          let at = 0;
          at < 100 && !calls.includes("provider_settings_status");
          at++
        )
          await new Promise((resolve) => setTimeout(resolve, 20));
        // The status read is already with the host when the window learns the
        // session ended; the host then refuses it for that reason.
        dom.flushSync(() =>
          root.render(react.createElement(Probe, { reader: null })),
        );
        answerStatus();
      }
      await settle();
      return {
        status: view.status,
        settingsReads: calls.filter(
          (call) => call === "provider_settings_status",
        ).length,
        reports: reports.filter(
          (report) => report.command === "provider_settings_status",
        ),
        errors: reports.filter((report) => report.level === "ERROR").length,
      };
    } finally {
      dom.flushSync(() => root.unmount());
      container.remove();
    }
  }, scenario);
}

test("a provider-status refusal the window did not observe coming stays an error and is not asked again", async ({
  page,
}) => {
  const result = await run(page, "refused");
  expect(result.settingsReads).toBe(1);
  expect(result.reports).toMatchObject([
    {
      level: "ERROR",
      command: "provider_settings_status",
      code: "not_signed_in",
    },
  ]);
  expect(result.errors).toBe(1);
  // The lanes of a session that is gone are not shown.
  expect(result.status).toBe("failed");
});

test("no provider-status read follows once the session has ended", async ({
  page,
}) => {
  const result = await run(page, "ended-first");
  expect(result.settingsReads).toBe(0);
  expect(result.reports).toEqual([]);
  expect(result.errors).toBe(0);
});

test("a provider-status read already asked when the session ends is noted once, not as an error", async ({
  page,
}) => {
  const result = await run(page, "ended-in-flight");
  expect(result.settingsReads).toBe(1);
  expect(result.reports).toMatchObject([
    {
      level: "INFO",
      command: "provider_settings_status",
      code: "not_signed_in",
    },
  ]);
  expect(result.reports).toHaveLength(1);
  expect(result.errors).toBe(0);
});
