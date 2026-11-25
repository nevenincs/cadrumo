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

// The same run through the real Tauri adapter and the real sign-in state. An
// idle expiry reaches the window as a pushed sign-in status; the window's
// session ends on that status itself, before any view renders, so the host's
// news that follows asks it for no progress. A progress read the host refuses
// before that status arrives is noted once at INFO, after the sign-in state's
// own read finds the session gone, and never as an error.

type Report = { level: string; command: string | null; code: string | null };

async function expire(
  page: import("@playwright/test").Page,
  how: "announced" | "unannounced",
) {
  await page.goto("/scenarios.html?scenario=signed-out&bar=off");
  await page.waitForFunction(() => Boolean(window.__scenarioModules));
  return page.evaluate(async (how) => {
    const { react, dom, client, gate, run, signIn } =
      await window.__scenarioModules!.sessionGate();
    const present = {
      supported: true,
      state: "present" as const,
      active_profile: "A",
      runtimeAvailable: true,
      refusal: null,
    };
    const absent = { ...present, state: "absent" as const };
    let current: typeof present | typeof absent = present;
    let expired = false;
    const reports: Report[] = [];
    const calls: string[] = [];
    Object.assign(window, {
      __CADRUMO_SHELL__: { token: "d".repeat(64) },
      __TAURI_INTERNALS__: {
        async invoke(command: string, args: unknown) {
          if (command === "desktop_frontend_diagnostic") {
            reports.push((args as { report: Report }).report);
            return null;
          }
          calls.push(command);
          if (expired) throw { code: "not_signed_in" };
          return null;
        },
      },
    });
    const { tauriHost } = await window.__scenarioModules!.tauriHost();
    let changed!: () => void;
    const port = {
      ...tauriHost().aeatSyncRun!,
      async observe(listener: () => void) {
        changed = listener;
        return () => {};
      },
    };
    let push!: (signal: import("../../src/ipc/account").SignInSignal) => void;
    const host = {
      available: true,
      signInStatus: async () => current,
      async observeSignIn(
        listener: (
          signal: import("../../src/ipc/account").SignInSignal,
        ) => void,
      ) {
        push = listener;
        return () => {};
      },
    } as unknown as import("../../src/shell/host").Host;
    const Shell = () => {
      signIn.useSignIn(host);
      run.useAeatSyncRun(port, "A", true);
      return null;
    };
    const container = document.createElement("div");
    document.body.append(container);
    const root = client.createRoot(container);
    const settle = () => new Promise((resolve) => setTimeout(resolve, 250));
    const progress = () =>
      calls.filter((call) => call === "aeat_sync_progress").length;
    const seen: { progress: number; ended: boolean }[] = [];
    try {
      dom.flushSync(() => root.render(react.createElement(Shell)));
      await settle();
      seen.push({ progress: progress(), ended: gate.sessionEnded() });
      if (how === "announced") {
        // The session expires; the sign-in status says so first.
        current = absent;
        expired = true;
        push({ kind: "sign-in-state", revision: 1, status: absent });
        seen.push({ progress: progress(), ended: gate.sessionEnded() });
        changed();
        await settle();
        seen.push({ progress: progress(), ended: gate.sessionEnded() });
        // A new sign-in starts a session the run is read for again.
        current = present;
        expired = false;
        push({ kind: "sign-in-state", revision: 2, status: present });
        seen.push({ progress: progress(), ended: gate.sessionEnded() });
        changed();
        await settle();
        seen.push({ progress: progress(), ended: gate.sessionEnded() });
      } else {
        // The session expires and the host's news arrives before the
        // sign-in status does.
        current = absent;
        expired = true;
        changed();
        await settle();
        seen.push({ progress: progress(), ended: gate.sessionEnded() });
        changed();
        await settle();
        seen.push({ progress: progress(), ended: gate.sessionEnded() });
      }
      return {
        seen,
        reports: reports.filter((report) => report.command !== null),
      };
    } finally {
      dom.flushSync(() => root.unmount());
      container.remove();
    }
  }, how);
}

test("an announced expiry ends the session on its status and no progress is read until a new sign-in", async ({
  page,
}) => {
  const result = await expire(page, "announced");
  expect(result.seen).toEqual([
    { progress: 1, ended: false },
    { progress: 1, ended: true },
    { progress: 1, ended: true },
    { progress: 1, ended: false },
    { progress: 2, ended: false },
  ]);
  expect(result.reports).toEqual([]);
});

test("a progress read refused before the expiry was announced is noted once at INFO and none follows", async ({
  page,
}) => {
  const result = await expire(page, "unannounced");
  expect(result.seen).toEqual([
    { progress: 1, ended: false },
    { progress: 2, ended: true },
    { progress: 2, ended: true },
  ]);
  expect(result.reports).toMatchObject([
    { level: "INFO", command: "aeat_sync_progress", code: "not_signed_in" },
  ]);
  expect(result.reports).toHaveLength(1);
});
