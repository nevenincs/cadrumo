import { expect, test } from "@playwright/test";

// Signing out: the host tells every profile observer that the session ended,
// and the household reads again on that news. Once the window has asked the
// session to end, the household asks no more, and a read that was already with
// the host when the window asked is refused for an end the log notes once, at
// INFO, without an error or the internal-failure notice behind the Errores
// badge. After a session ended without being asked (an idle expiry) the window
// sends the household no read at all. A refusal that arrives before the window
// heard of such an end is noted the same way once the sign-in state finds the
// session gone; one for a session that is still there stays an error. The real
// Tauri adapter runs against a recording invoke boundary.

type Report = { level: string; command: string | null; code: string | null };

async function run(
  page: import("@playwright/test").Page,
  scenario:
    | "ended-before-news"
    | "ended-in-flight"
    | "expired"
    | "expired-unheard"
    | "not-foreseen",
) {
  await page.goto("/scenarios.html?scenario=signed-out&bar=off");
  await page.waitForFunction(() => Boolean(window.__scenarioModules));
  return page.evaluate(async (scenario) => {
    const { react, dom, client, household, fixture } =
      await window.__scenarioModules!.profileHousehold();
    const { gate } = await window.__scenarioModules!.sessionGate();
    gate.startSession();
    // The sign-in state's own read of the session: it finds the session gone
    // only where the session expired unheard.
    let confirmations = 0;
    const release = gate.confirmSessionWith(async () => {
      confirmations += 1;
      if (scenario === "expired-unheard") gate.endSession();
    });
    let failures = 0;
    window.addEventListener("cadrumo-internal-failure", () => (failures += 1));
    const stated = await fixture
      .householdFixture("unknown")
      .reads.household("en");
    const reports: Report[] = [];
    let reads = 0;
    let answer!: () => void;
    const held = new Promise<void>((resolve) => (answer = resolve));
    Object.assign(window, {
      __CADRUMO_SHELL__: { token: "f".repeat(64) },
      __TAURI_INTERNALS__: {
        async invoke(command: string, args: unknown) {
          if (command === "desktop_frontend_diagnostic") {
            reports.push((args as { report: Report }).report);
            return null;
          }
          if (command !== "user_profile_household") return null;
          reads += 1;
          if (reads === 1) return stated;
          if (scenario === "ended-in-flight") await held;
          throw { code: "not_signed_in" };
        },
      },
    });
    const { tauriHost } = await window.__scenarioModules!.tauriHost();
    const reads_ = tauriHost().profileCompanions!;
    let ended = false;
    let news!: () => void;
    const container = document.createElement("div");
    document.body.append(container);
    const root = client.createRoot(container);
    const settle = () => new Promise((resolve) => setTimeout(resolve, 250));
    try {
      dom.flushSync(() =>
        root.render(
          react.createElement(household.Household, {
            reads: reads_,
            change: async () => undefined,
            observe: async (changed: () => void) => {
              news = changed;
              return () => {};
            },
            language: "en",
            sessionEnded: () => ended,
          }),
        ),
      );
      await settle();
      if (scenario === "ended-before-news") {
        // The window asks the session to end; the host then announces it.
        ended = true;
        news();
      }
      if (scenario === "ended-in-flight") {
        // The news arrives first and its read is with the host when the
        // window asks the session to end; the host then refuses it.
        news();
        await settle();
        ended = true;
        answer();
      }
      if (scenario === "expired") {
        // The session ends without the window asking; the household hears
        // twice before anything else stops it.
        gate.endSession();
        news();
        await settle();
        news();
      }
      if (scenario === "expired-unheard" || scenario === "not-foreseen") news();
      await settle();
      return {
        reads,
        failures,
        confirmations,
        reports: reports.filter(
          (report) => report.command === "user_profile_household",
        ),
      };
    } finally {
      release();
      dom.flushSync(() => root.unmount());
      container.remove();
    }
  }, scenario);
}

test("a household asks nothing after the window asked the session to end", async ({
  page,
}) => {
  const result = await run(page, "ended-before-news");
  expect(result.reads).toBe(1);
  expect(result.reports).toEqual([]);
  expect(result.failures).toBe(0);
});

test("a household read refused for an end the window asked for is noted once, not as an error", async ({
  page,
}) => {
  const result = await run(page, "ended-in-flight");
  expect(result.reads).toBe(2);
  expect(result.reports).toMatchObject([
    { level: "INFO", command: "user_profile_household", code: "not_signed_in" },
  ]);
  expect(result.failures).toBe(0);
});

test("a household sends no read after an expiry the window heard of", async ({
  page,
}) => {
  const result = await run(page, "expired");
  expect(result.reads).toBe(1);
  expect(result.reports).toEqual([]);
  expect(result.failures).toBe(0);
});

test("a household read refused before the window heard of an expiry is noted once, not as an error", async ({
  page,
}) => {
  const result = await run(page, "expired-unheard");
  expect(result.reads).toBe(2);
  expect(result.confirmations).toBe(1);
  expect(result.reports).toMatchObject([
    { level: "INFO", command: "user_profile_household", code: "not_signed_in" },
  ]);
  expect(result.reports).toHaveLength(1);
  expect(result.failures).toBe(0);
});

test("a household refusal the window did not see coming stays an error", async ({
  page,
}) => {
  const result = await run(page, "not-foreseen");
  expect(result.reads).toBe(2);
  expect(result.confirmations).toBe(1);
  expect(result.reports).toMatchObject([
    {
      level: "ERROR",
      command: "user_profile_household",
      code: "not_signed_in",
    },
  ]);
});
