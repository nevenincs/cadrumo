import { expect, test } from "@playwright/test";
import type {
  ProviderSettings,
  ProviderSettingsRecord,
  ProviderSettingsView,
} from "../../src/shell/providerSettings";
import type { AgentRead } from "../../src/shell/agentViews";

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
            status: async () => ({ development: false, providers: [record] }),
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
