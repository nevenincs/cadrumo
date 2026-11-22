import { expect, test, type Page } from "@playwright/test";
import type { AgentServiceStatus } from "../../src/shell/agentSession";
import type {
  ProviderSettings,
  ProviderSettingsView,
} from "../../src/shell/providerSettings";
import type {
  ProviderSettingsAnswer,
  ProviderSettingsRecord,
} from "../../src/shell/providerSettingsContract";

// The production provider settings hook, driven with a host whose answers the
// test chooses. A busy answer and an answer the service is still completing
// wait on a cue: a status the service publishes (which it sends again once a
// read it answered busy or pending for has settled), or the person coming
// back to the window. The page's clock is installed and run far past any
// pause, so a read made by time alone would show.

type Probe = {
  reads: () => number;
  view: () => ProviderSettingsView["read"];
  publish: (status: AgentServiceStatus) => void;
  /** Ends the read still out with the answer it was asked for. */
  settle: () => void;
  unmount: () => void;
};

declare global {
  interface Window {
    __providerCueProbe?: Probe;
  }
}

type Answer = "busy" | "pending" | "complete";

async function mount(
  page: Page,
  answers: readonly Answer[],
  held: boolean,
): Promise<void> {
  await page.clock.install();
  await page.goto("/scenarios.html?scenario=signed-out&bar=off");
  await page.waitForFunction(() => Boolean(window.__scenarioModules));
  await page.evaluate(
    async ({ answers, held }) => {
      const { react, dom, client } =
        await window.__scenarioModules!.profileViews();
      const { settings } = await window.__scenarioModules!.providerReads();
      const record: ProviderSettingsRecord = {
        id: "example_api",
        provider: "example",
        display_name: "Example",
        transport: "api",
        auth_kind: "api_key",
        mode: "key",
        available: true,
        source: "profile",
        readiness: "ready",
        revision: "0".repeat(64),
        consumers: ["assistant"],
        credential_saved: false,
        reads_off_host: true,
        sign_out_available: false,
      };
      let reads = 0;
      let release: (() => void) | null = null;
      const answer = (kind: Answer): Promise<ProviderSettingsAnswer> =>
        kind === "busy"
          ? Promise.reject({ code: "busy" })
          : Promise.resolve({
              providers: [record],
              reads_pending: kind === "pending",
            });
      const change = () => Promise.resolve(record);
      const host: ProviderSettings = {
        status: () => {
          const kind = answers[Math.min(reads, answers.length - 1)]!;
          reads += 1;
          if (!held) return answer(kind);
          return new Promise<void>((resolve) => {
            release = resolve;
          }).then(() => answer(kind));
        },
        set: change,
        turnOff: change,
        turnOn: change,
        reset: change,
        signOut: change,
      };
      let view!: ProviderSettingsView;
      function Shown({ published }: { published: AgentServiceStatus }) {
        const current = settings.useProviderSettings(
          host,
          "A",
          true,
          0,
          published,
        );
        react.useLayoutEffect(() => {
          view = current;
        });
        return null;
      }
      const container = document.createElement("div");
      document.body.append(container);
      const root = client.createRoot(container);
      const render = (published: AgentServiceStatus) =>
        dom.flushSync(() =>
          root.render(react.createElement(Shown, { published })),
        );
      render({ state: "ready", agent_version: "1" });
      window.__providerCueProbe = {
        reads: () => reads,
        view: () => view.read,
        // Each publication is a new object, as each one the host sends is.
        publish: (status) => render({ ...status }),
        settle: () => {
          const held = release;
          release = null;
          held?.();
        },
        unmount: () => {
          dom.flushSync(() => root.unmount());
          container.remove();
        },
      };
    },
    { answers, held },
  );
}

const reads = (page: Page) =>
  page.evaluate(() => window.__providerCueProbe!.reads());

const shown = (page: Page) =>
  page.evaluate(() => {
    const read = window.__providerCueProbe!.view();
    return read.kind === "ready"
      ? read.value.readsPending
        ? "pending"
        : "complete"
      : read.kind === "failed"
        ? read.code
        : read.kind;
  });

const publish = (page: Page) =>
  page.evaluate(() =>
    window.__providerCueProbe!.publish({ state: "ready", agent_version: "1" }),
  );

test.afterEach(async ({ page }) => {
  await page.evaluate(() => window.__providerCueProbe?.unmount());
});

for (const first of ["busy", "pending"] as const)
  test(`settings answering ${first} are read again once on a published status and never by time`, async ({
    page,
  }) => {
    await mount(page, [first, "complete"], false);
    await expect.poll(() => shown(page)).toBe(first);
    expect(await reads(page)).toBe(1);

    // Far past any pause the settings once waited: nothing is read again.
    await page.clock.runFor(10 * 60_000);
    expect(await shown(page)).toBe(first);
    expect(await reads(page)).toBe(1);

    // The service's cue: the status is published again.
    await publish(page);
    await expect.poll(() => shown(page)).toBe("complete");
    expect(await reads(page)).toBe(2);

    // A complete answer waits on nothing: neither a cue nor time reads it.
    await publish(page);
    await page.clock.runFor(10 * 60_000);
    expect(await reads(page)).toBe(2);
  });

test("settings that stay busy are read once per published status", async ({
  page,
}) => {
  await mount(page, ["busy"], false);
  await expect.poll(() => shown(page)).toBe("busy");
  for (let cue = 1; cue <= 3; cue++) {
    await publish(page);
    await expect.poll(() => reads(page)).toBe(1 + cue);
    await page.clock.runFor(60_000);
    expect(await reads(page)).toBe(1 + cue);
  }
  expect(await shown(page)).toBe("busy");
});

test("busy settings are read again when the person comes back to the window", async ({
  page,
}) => {
  await mount(page, ["busy", "complete"], false);
  await expect.poll(() => shown(page)).toBe("busy");
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect.poll(() => shown(page)).toBe("complete");
  expect(await reads(page)).toBe(2);
});

test("a status published while a busy read is out is taken once that read ends", async ({
  page,
}) => {
  await mount(page, ["busy", "busy", "complete"], true);
  await page.evaluate(() => window.__providerCueProbe!.settle());
  await expect.poll(() => shown(page)).toBe("busy");
  await publish(page);
  await expect.poll(() => reads(page)).toBe(2);
  // The cue comes while the second read is out: no third read joins it.
  await publish(page);
  await page.clock.runFor(60_000);
  expect(await reads(page)).toBe(2);
  // It ends busy, and the cue that came meanwhile reads once more.
  await page.evaluate(() => window.__providerCueProbe!.settle());
  await expect.poll(() => reads(page)).toBe(3);
  await page.evaluate(() => window.__providerCueProbe!.settle());
  await expect.poll(() => shown(page)).toBe("complete");
  expect(await reads(page)).toBe(3);
});
