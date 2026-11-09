import { expect, test } from "@playwright/test";

// The window follows an update from AEAT by reading its progress whenever the
// host says it changed. Once the window's session has ended, by signing out or
// by expiring, the host's news is about a session nobody is working for, so
// the window reads nothing until a session starts again.

test("the run's progress is not read after the session ended, and is again after a new one starts", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=signed-out&bar=off");
  await page.waitForFunction(() => Boolean(window.__scenarioModules));
  const reads = await page.evaluate(async () => {
    const { react, dom, client, gate, run } =
      await window.__scenarioModules!.sessionGate();
    gate.startSession();
    let reads = 0;
    let changed!: () => void;
    const port = {
      async progress() {
        reads += 1;
        return null;
      },
      async observe(listener: () => void) {
        changed = listener;
        return () => {};
      },
      async stop() {},
      async retry() {},
    } as unknown as import("../../src/shell/aeatSyncRun").AeatSyncRunPort;
    const Follower = () => {
      run.useAeatSyncRun(port, "profile", true);
      return null;
    };
    const container = document.createElement("div");
    document.body.append(container);
    const root = client.createRoot(container);
    const settle = () => new Promise((resolve) => setTimeout(resolve, 100));
    const seen: number[] = [];
    try {
      dom.flushSync(() => root.render(react.createElement(Follower)));
      await settle();
      seen.push(reads);
      gate.endSession();
      changed();
      await settle();
      seen.push(reads);
      gate.startSession();
      changed();
      await settle();
      seen.push(reads);
      return seen;
    } finally {
      dom.flushSync(() => root.unmount());
      container.remove();
    }
  });
  expect(reads).toEqual([1, 1, 2]);
});
