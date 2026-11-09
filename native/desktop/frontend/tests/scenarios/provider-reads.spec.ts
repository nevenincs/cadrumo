import { expect, test } from "@playwright/test";
import type {
  ProviderSettings,
  ProviderSettingsRecord,
  ProviderSettingsView,
} from "../../src/shell/providerSettings";
import type { AgentRead } from "../../src/shell/agentViews";
import { servedLocalLanes } from "../support/servedLocalLanes";

// The lanes the host serves with the engine setting it answers.
const SERVED = servedLocalLanes().map((lane) => lane.id);

for (const transition of ["profile", "sign-out", "host"] as const)
  for (const outcome of ["success", "failure"] as const)
    test(`provider ${outcome} is retired after ${transition} changes`, async ({
      page,
    }) => {
      await page.goto("/scenarios.html?scenario=signed-out&bar=off");
      await page.waitForFunction(() => Boolean(window.__scenarioModules));
      const result = await page.evaluate(
        async ({ transition, outcome }) => {
          const { react, dom, client } =
            await window.__scenarioModules!.profileViews();
          const { settings } = await window.__scenarioModules!.providerReads();
          const pending: {
            resolve(record: ProviderSettingsRecord): void;
            reject(error: Error): void;
          }[] = [];
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
          };
          const change = () =>
            new Promise<ProviderSettingsRecord>((resolve, reject) =>
              pending.push({ resolve, reject }),
            );
          const host: ProviderSettings = {
            status: async () => ({ providers: [record] }),
            set: change,
            turnOff: change,
            turnOn: change,
            reset: change,
          };
          const replacement = { ...host };
          let view!: ProviderSettingsView;
          function Probe({
            reader,
            replaced,
          }: {
            reader: string | null;
            replaced: boolean;
          }) {
            const current = settings.useProviderSettings(
              replaced ? replacement : host,
              reader,
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
          const render = (reader: string | null, replaced = false) =>
            dom.flushSync(() =>
              root.render(react.createElement(Probe, { reader, replaced })),
            );
          const turn = () =>
            new Promise((resolve) => window.setTimeout(resolve, 10));
          const ready = async () => {
            for (let at = 0; at < 100; at++) {
              if (view.read.kind === "ready") return;
              await turn();
            }
            throw new Error("Provider status never became ready");
          };
          try {
            render("A");
            await ready();
            dom.flushSync(() => view.turnOff(record.id));
            const obsolete = pending.at(-1)!;
            if (transition === "sign-out") render(null);
            render(transition === "profile" ? "B" : "A", transition === "host");
            await ready();
            dom.flushSync(() => view.turnOff(record.id));
            const current = pending.at(-1)!;
            if (outcome === "success") obsolete.resolve(record);
            else obsolete.reject(new Error("obsolete failure"));
            await turn();
            const afterObsolete = {
              busy: view.busyId,
              changes: view.changes,
              outcomes: view.outcomes,
            };
            current.resolve(record);
            for (let at = 0; at < 100 && view.busyId !== null; at++)
              await turn();
            return {
              afterObsolete,
              finalBusy: view.busyId,
              finalChanges: view.changes,
            };
          } finally {
            dom.flushSync(() => root.unmount());
            container.remove();
          }
        },
        { transition, outcome },
      );
      expect(result.afterObsolete).toEqual({
        busy: "example_api",
        changes: 0,
        outcomes: {},
      });
      expect(result.finalBusy).toBeNull();
      expect(result.finalChanges).toBe(1);
    });

test("an accepted provider status supersedes an older read and still permits refresh", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=signed-out&bar=off");
  await page.waitForFunction(() => Boolean(window.__scenarioModules));
  const result = await page.evaluate(async () => {
    const { react, dom, client } =
      await window.__scenarioModules!.profileViews();
    const { views } = await window.__scenarioModules!.providerReads();
    const pending: ((value: string) => void)[] = [];
    const first = () => new Promise<string>((resolve) => pending.push(resolve));
    const replacement = () =>
      new Promise<string>((resolve) => pending.push(resolve));
    let read: AgentRead<string> = { kind: "loading" };
    let put: (value: string) => void = () => {};
    function Probe({ ask, replaced }: { ask: number; replaced: boolean }) {
      const current = views.useCachedRead(
        replaced ? replacement : first,
        "profile",
        true,
        ask,
      );
      react.useLayoutEffect(() => {
        read = current.read;
        put = current.put;
      });
      return null;
    }
    const container = document.createElement("div");
    document.body.append(container);
    const root = client.createRoot(container);
    const render = (ask: number, replaced = false) =>
      dom.flushSync(() =>
        root.render(react.createElement(Probe, { ask, replaced })),
      );
    const turn = () => new Promise((resolve) => window.setTimeout(resolve, 10));
    const value = () => (read.kind === "ready" ? read.value : read.kind);
    const until = async (expected: string) => {
      for (let at = 0; at < 100; at++) {
        if (value() === expected) return;
        await turn();
      }
      throw new Error(`Status never became ${expected}`);
    };
    try {
      render(0);
      dom.flushSync(() => put("accepted"));
      pending[0]!("obsolete");
      await turn();
      const afterOld = value();
      render(1);
      pending.at(-1)!("refreshed");
      await until("refreshed");
      render(1, true);
      const requests = pending.length;
      pending.at(-1)!("new-host");
      await until("new-host");
      return { afterOld, requests, final: value() };
    } finally {
      dom.flushSync(() => root.unmount());
      container.remove();
    }
  });
  expect(result).toEqual({
    afterOld: "accepted",
    requests: 3,
    final: "new-host",
  });
});

// Exercise the production Local AI hook with the same catalogs and settings
// hosts as the shell; only admission timing and obsolete responses are controlled.
for (const recovery of [
  "agent_service_busy",
  "agent_reconnecting",
  "published",
])
  test(`Local AI catalog recovers ${recovery} without manual Retry`, async ({
    page,
  }) => {
    await page.goto("/scenarios.html?scenario=signed-out&bar=off");
    await page.waitForFunction(() => Boolean(window.__scenarioModules));
    const result = await localAiProbe(page, { recovery });
    expect(result).toEqual({
      status: "ready",
      lanes: SERVED,
      catalog: 2,
      settings: 1,
      beforeAdmission: 0,
    });
  });

// A status-host busy rejection represents the native bounded collector
// returning busy; exercise the real hook's outer collection and owner fences.
for (const settingsMode of [
  "recover",
  "published",
  "inflight",
  "exhaustion",
  "shared",
])
  test(`Local AI collects settings busy: ${settingsMode}`, async ({ page }) => {
    await page.goto("/scenarios.html?scenario=signed-out&bar=off");
    await page.waitForFunction(() => Boolean(window.__scenarioModules));
    const result = await localAiProbe(page, { settingsMode });
    const exhausted =
      settingsMode === "exhaustion" || settingsMode === "shared";
    expect(result).toEqual({
      status: exhausted ? "failed" : "ready",
      lanes: exhausted ? [] : SERVED,
      catalog: settingsMode === "shared" ? 3 : 1,
      settings: settingsMode === "exhaustion" ? 4 : 2,
      pauses: exhausted ? [2_000, 4_000, 8_000] : [2_000],
      beforeAdmission: 0,
      maxPendingSettings: 1,
      readsWhilePending: settingsMode === "inflight" ? 1 : 0,
      readsAfterPublication: ["published", "inflight"].includes(settingsMode)
        ? 2
        : 0,
      extraAfterWake: 0,
      queuedAfterWake: 0,
      retried: "ready",
    });
  });

for (const settingsRefusal of [
  "not_signed_in",
  "profile_locked",
  "catalog_unavailable",
  "runtime_unavailable",
  "agent_service_busy",
  "agent_reconnecting",
  "timeout",
  "unknown",
])
  test(`Local AI does not replay settings ${settingsRefusal}`, async ({
    page,
  }) => {
    await page.goto("/scenarios.html?scenario=signed-out&bar=off");
    await page.waitForFunction(() => Boolean(window.__scenarioModules));
    expect(
      await localAiProbe(page, { settingsMode: "refusal", settingsRefusal }),
    ).toEqual({
      status: "failed",
      lanes: [],
      catalog: 1,
      settings: 1,
      pauses: [],
      beforeAdmission: 0,
      maxPendingSettings: 1,
      readsWhilePending: 0,
      readsAfterPublication: 0,
      extraAfterWake: 0,
      queuedAfterWake: 0,
      retried: "ready",
    });
  });

for (const serviceState of ["stopped", "refused"])
  test(`Local AI preserves a ${serviceState} service without catalog reads`, async ({
    page,
  }) => {
    await page.goto("/scenarios.html?scenario=signed-out&bar=off");
    await page.waitForFunction(() => Boolean(window.__scenarioModules));
    expect(await localAiProbe(page, { serviceState })).toEqual({
      status: "failed",
      catalog: 0,
      settings: 0,
    });
  });

test("Local AI asks nothing while the agent starts and reads once it runs", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=signed-out&bar=off");
  await page.waitForFunction(() => Boolean(window.__scenarioModules));
  expect(await localAiProbe(page, { starting: true })).toEqual({
    whileStarting: { status: "loading", catalog: 0, settings: 0, host: true },
    status: "ready",
    catalog: 1,
    lanes: SERVED,
    host: true,
  });
});

for (const refusal of ["agent_service_busy", "agent_service_failed"])
  test(`Local AI catalog bounds ${refusal} recovery and permits explicit Retry`, async ({
    page,
  }) => {
    await page.goto("/scenarios.html?scenario=signed-out&bar=off");
    await page.waitForFunction(() => Boolean(window.__scenarioModules));
    const result = await localAiProbe(page, { refusal });
    expect(result).toEqual({
      status: "failed",
      catalog: refusal === "agent_service_busy" ? 4 : 1,
      settings: 0,
      afterPublications: refusal === "agent_service_busy" ? 4 : 1,
      retried: "ready",
    });
  });

for (const transition of [
  "profile",
  "host",
  "provider-host",
  "session",
  "refresh",
  "sign-out",
  "hide",
  "unmount",
])
  for (const stage of [
    "catalog",
    "catalog-failure",
    "settings",
    "settings-failure",
    "settings-busy",
    "settings-wait-busy",
    "busy",
  ])
    test(`Local AI retires ${stage} work after ${transition}`, async ({
      page,
    }) => {
      await page.goto("/scenarios.html?scenario=signed-out&bar=off");
      await page.waitForFunction(() => Boolean(window.__scenarioModules));
      const result = await localAiProbe(page, { transition, stage });
      expect(result.initialSettings).toBe(stage.startsWith("settings") ? 1 : 0);
      expect(result.extraSettings).toBe(0);
      expect(result.extraCatalogs).toBe(0);
      expect(result.oldListeners).toBe(0);
      const stillShown = [
        "profile",
        "host",
        "provider-host",
        "session",
        "refresh",
      ].includes(transition);
      expect(result.retiredStatus).toBe(
        stillShown
          ? "ready"
          : transition === "unmount"
            ? "unmounted"
            : "failed",
      );
      expect(result.retiredLanes).toEqual(stillShown ? SERVED : []);
      expect(result.status).toBe(
        transition === "unmount" ? "unmounted" : "ready",
      );
      expect(result.lanes).toEqual(transition === "unmount" ? [] : SERVED);
    });

async function localAiProbe(
  page: import("@playwright/test").Page,
  options: {
    recovery?: string;
    refusal?: string;
    transition?: string;
    stage?: string;
    serviceState?: string;
    starting?: boolean;
    settingsMode?: string;
    settingsRefusal?: string;
  },
) {
  return page.evaluate(async (options) => {
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
    const catalogAnswer = await fixture.session.providerCatalog();
    const settingsAnswer = await provider.status();
    const realTimeout = window.setTimeout.bind(window);
    const realClearTimeout = window.clearTimeout.bind(window);
    const queued = new Map<number, () => void>();
    const pauses: number[] = [];
    let timerId = 0;
    window.setTimeout = ((
      callback: TimerHandler,
      delay?: number,
      ...args: unknown[]
    ) => {
      if (
        (options.settingsMode || options.stage === "settings-wait-busy") &&
        delay !== undefined &&
        delay >= 2_000
      ) {
        if (typeof callback !== "function")
          throw new Error("Expected callback");
        pauses.push(delay);
        const resume = () => callback(...args);
        queued.set(--timerId, resume);
        if (options.stage === "settings-wait-busy") release = resume;
        return timerId;
      }
      return realTimeout(
        callback,
        delay !== undefined && delay >= 2_000
          ? delay /
              (options.stage === "busy" ||
              options.stage === "settings-wait-busy" ||
              options.recovery === "published"
                ? 10
                : 200)
          : delay,
        ...args,
      );
    }) as typeof window.setTimeout;
    window.clearTimeout = (id) => {
      if (typeof id === "number" && queued.delete(id)) return;
      realClearTimeout(id);
    };
    const listeners = new Set<
      (
        status: import("../../src/shell/agentSession").AgentServiceStatus,
      ) => void
    >();
    let catalogs = 0,
      settings = 0,
      beforeAdmission = 0;
    let pendingSettings = 0,
      maxPendingSettings = 0;
    let admitted = false,
      succeed = false;
    let release: (() => void) | undefined;
    let view!: import("../../src/shell/localAiLanes").LocalAiLanes;
    const source: import("../../src/shell/localAiLanes").LocalAiSource = {
      reader: "A",
      session: {
        ...fixture.session,
        status: async () =>
          options.serviceState === "stopped"
            ? { state: "stopped" }
            : options.serviceState === "refused"
              ? { state: "refused", code: "agent_service_failed" }
              : options.starting
                ? { state: "starting" }
                : { state: "ready", agent_version: "fixture" },
        observeStatus: async (listener) => {
          listeners.add(listener);
          return () => {
            listeners.delete(listener);
          };
        },
        providerCatalog: async () => {
          catalogs++;
          if (options.stage?.startsWith("catalog") && catalogs === 1)
            await new Promise<void>((resolve, reject) => {
              release = () =>
                options.stage === "catalog-failure"
                  ? reject({ code: "agent_service_failed" })
                  : resolve();
            });
          if (
            (options.stage === "busy" && catalogs === 1) ||
            (options.settingsMode === "shared" && !succeed && catalogs <= 2) ||
            (!succeed &&
              (options.refusal || (options.recovery && catalogs === 1)))
          )
            throw {
              code:
                options.refusal ??
                (options.recovery === "agent_reconnecting"
                  ? options.recovery
                  : "agent_service_busy"),
            };
          admitted = true;
          return catalogAnswer;
        },
      },
      providerSettings: {
        ...provider,
        status: async () => {
          settings++;
          pendingSettings++;
          maxPendingSettings = Math.max(maxPendingSettings, pendingSettings);
          if (!admitted) beforeAdmission++;
          try {
            if (options.stage === "settings-wait-busy" && settings === 1)
              throw { code: "busy" };
            if (options.stage?.startsWith("settings") && settings === 1) {
              await new Promise<void>((resolve, reject) => {
                release = () =>
                  options.stage === "settings-failure"
                    ? reject({ code: "agent_service_failed" })
                    : options.stage === "settings-busy"
                      ? reject({ code: "busy" })
                      : resolve();
              });
              return { providers: [] };
            }
            if (options.settingsMode && !succeed) {
              if (options.settingsMode === "inflight" && settings === 1)
                await new Promise<void>((resolve) => {
                  release = resolve;
                });
              if (
                settings === 1 ||
                ["exhaustion", "shared", "refusal"].includes(
                  options.settingsMode,
                )
              )
                throw { code: options.settingsRefusal ?? "busy" };
            }
            return settingsAnswer;
          } finally {
            pendingSettings--;
          }
        },
      },
    };
    const replacement = {
      reader: "B",
      session: fixture.session,
      providerSettings: provider,
    };
    function Probe({
      source,
      active,
      again,
    }: {
      source: import("../../src/shell/localAiLanes").LocalAiSource | null;
      active: boolean;
      again: number;
    }) {
      const current = lanes.useLocalAiLanes(source, active, again);
      react.useLayoutEffect(() => {
        view = current;
      });
      return null;
    }
    const container = document.createElement("div");
    document.body.append(container);
    const root = client.createRoot(container);
    const render = (current: typeof source | null, active = true, again = 0) =>
      dom.flushSync(() =>
        root.render(
          react.createElement(Probe, { source: current, active, again }),
        ),
      );
    const settle = async () => {
      for (let i = 0; i < 5; i++)
        await new Promise<void>((resolve) =>
          requestAnimationFrame(() => resolve()),
        );
    };
    // Recovery timers are accelerated above; React scheduling stays real.
    const advance = async () => {
      await new Promise<void>((resolve) => {
        realTimeout(resolve, 200);
      });
      await settle();
    };
    const publish = () => {
      for (const listener of listeners)
        listener({ state: "ready", agent_version: "fixture" });
    };
    let unmounted = false;
    try {
      render(source);
      await settle();
      if (options.starting) {
        // The service has no connection yet: nothing is asked, and the lanes
        // are loading rather than failed.
        const whileStarting = {
          status: view.status,
          catalog: catalogs,
          settings,
          host: view.host === null,
        };
        publish();
        await settle();
        return {
          whileStarting,
          status: view.status,
          catalog: catalogs,
          lanes: view.lanes.map((lane) => lane.id),
          host: view.host !== null,
        };
      }
      if (options.serviceState)
        return { status: view.status, catalog: catalogs, settings };
      if (options.transition) {
        const initialSettings = settings;
        if (options.transition === "unmount") {
          dom.flushSync(() => root.unmount());
          unmounted = true;
        } else if (options.transition === "hide") render(source, false);
        else if (options.transition === "refresh") render(source, true, 1);
        else if (options.transition === "sign-out")
          render({ ...source, reader: null });
        else
          render(
            options.transition === "profile"
              ? { ...source, reader: "B" }
              : options.transition === "provider-host"
                ? { ...source, providerSettings: provider }
                : { ...source, session: fixture.session },
          );
        await settle();
        const oldListeners = listeners.size;
        // Profile/provider replacement still owns the same session's new listener.
        const expectedActive =
          options.transition === "profile" ||
          options.transition === "provider-host" ||
          options.transition === "refresh";
        const beforeSettings = settings,
          beforeCatalogs = catalogs;
        release?.();
        await advance();
        const extraSettings = settings - beforeSettings;
        const extraCatalogs = catalogs - beforeCatalogs;
        const retiredStatus = unmounted ? "unmounted" : view.status;
        const retiredLanes = unmounted ? [] : view.lanes.map((lane) => lane.id);
        if (!unmounted) {
          render(
            options.transition === "hide" || options.transition === "sign-out"
              ? source
              : replacement,
          );
          await settle();
        }
        return {
          initialSettings,
          extraSettings,
          extraCatalogs,
          retiredStatus,
          retiredLanes,
          oldListeners: expectedActive ? oldListeners - 1 : oldListeners,
          status: unmounted ? "unmounted" : view.status,
          lanes: unmounted ? [] : view.lanes.map((lane) => lane.id),
        };
      }
      if (options.settingsMode) {
        let readsWhilePending = 0;
        if (options.settingsMode === "inflight") {
          publish();
          await settle();
          publish();
          await settle();
          readsWhilePending = settings;
          release!();
          await settle();
        } else if (options.settingsMode === "published") {
          publish();
          await settle();
        }
        const readsAfterPublication = ["published", "inflight"].includes(
          options.settingsMode,
        )
          ? settings
          : 0;
        // Drive only the hook's retry timers, leaving React scheduling real.
        for (let i = 0; i < 10 && queued.size > 0; i++) {
          queued.values().next().value!();
          await settle();
        }
        const status = view.status,
          shown = view.lanes.map((lane) => lane.id),
          count = settings,
          catalog = catalogs,
          spentPauses = [...pauses];
        for (let i = 0; i < 6; i++) {
          publish();
          await settle();
        }
        const extraAfterWake = settings + catalogs - count - catalog;
        const queuedAfterWake = queued.size;
        succeed = true;
        dom.flushSync(() => view.retry());
        await settle();
        return {
          status,
          lanes: shown,
          catalog,
          settings: count,
          pauses: spentPauses,
          beforeAdmission,
          maxPendingSettings,
          readsWhilePending,
          readsAfterPublication,
          extraAfterWake,
          queuedAfterWake,
          retried: view.status,
        };
      }
      if (options.recovery === "published") {
        publish();
        await advance();
      } else await advance();
      if (options.refusal) {
        // Exhaust all 2/4/8-second retries, then prove status events cannot
        // restart an exhausted (or permanent) failure.
        await advance();
        await advance();
        const status = view.status,
          count = catalogs;
        for (let i = 0; i < 6; i++) {
          publish();
          await settle();
        }
        const afterPublications = catalogs;
        succeed = true;
        dom.flushSync(() => view.retry());
        await settle();
        return {
          status,
          catalog: count,
          settings: settings - 1,
          afterPublications,
          retried: view.status,
        };
      }
      return {
        status: view.status,
        lanes: view.lanes.map((lane) => lane.id),
        catalog: catalogs,
        settings,
        beforeAdmission,
      };
    } finally {
      if (!unmounted) dom.flushSync(() => root.unmount());
      container.remove();
      window.setTimeout = realTimeout;
      window.clearTimeout = realClearTimeout;
    }
  }, options);
}
