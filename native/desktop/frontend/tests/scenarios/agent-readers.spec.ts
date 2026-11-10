import { expect, test } from "@playwright/test";
import type { AgentLocalModels } from "../../src/ipc/contract";
import type {
  AgentSession,
  AgentServiceStatus,
} from "../../src/shell/agentSession";

for (const outcome of ["success", "failure"] as const)
  test(`reading model ignores old-profile ${outcome} and preserves conflict recovery`, async ({
    page,
  }) => {
    await page.goto("/scenarios.html?scenario=signed-out&bar=off");
    await page.waitForFunction(() => Boolean(window.__scenarioModules));
    const result = await page.evaluate(async (outcome) => {
      const { react, dom, client } =
        await window.__scenarioModules!.profileViews();
      const { models } = await window.__scenarioModules!.agentReaders();
      const reads: ((value: AgentLocalModels) => void)[] = [];
      const choices: {
        resolve(value: AgentLocalModels): void;
        reject(error: { code: string }): void;
      }[] = [];
      const host = {
        read: () =>
          new Promise<AgentLocalModels>((resolve) => reads.push(resolve)),
        choose: () =>
          new Promise<AgentLocalModels>((resolve, reject) =>
            choices.push({ resolve, reject }),
          ),
      };
      const wanted = { lane: "example", model: "vision" };
      const answer = (revision: string, chosen = false): AgentLocalModels => ({
        state: "readable",
        models: [],
        ...(chosen
          ? { reading: wanted, reading_source: "chosen" as const }
          : { reading: null, reading_source: "none" as const }),
        local_lanes: [],
        revision,
      });
      let value: AgentLocalModels | null = null;
      const commits: (string | null)[] = [];
      function Probe({
        reader,
        available,
        version,
      }: {
        reader: string;
        available: boolean;
        version: number;
      }) {
        const current = models.useReadingModel(
          available ? host : null,
          wanted,
          version,
          reader,
        );
        react.useLayoutEffect(() => {
          value = current;
          commits.push(current?.revision ?? null);
        });
        return null;
      }
      const container = document.createElement("div");
      document.body.append(container);
      const root = client.createRoot(container);
      const render = (reader: string, available = true, version = 0) => {
        const at = commits.length;
        dom.flushSync(() =>
          root.render(
            react.createElement(Probe, { reader, available, version }),
          ),
        );
        return commits[at];
      };
      const turn = () =>
        new Promise((resolve) => window.setTimeout(resolve, 10));
      const until = async (done: () => boolean) => {
        for (let at = 0; at < 100; at++) {
          if (done()) return;
          await turn();
        }
        throw new Error("Reading model did not reach expected state");
      };
      try {
        render("A");
        reads[0]!(answer("0"));
        await until(() => choices.length === 1);
        render("A", true, 1);
        const oldRead = reads.at(-1)!;
        const firstB = render("B");
        reads.at(-1)!(answer("0"));
        await until(() => choices.length === 2);
        oldRead(answer("obsolete-read"));
        if (outcome === "success")
          choices[0]!.resolve(answer("obsolete-choice", true));
        else
          choices[0]!.reject({ code: "agent_local_models_revision_conflict" });
        await turn();
        const afterObsolete = {
          revision: (value as AgentLocalModels | null)?.revision,
          reads: reads.length,
          choices: choices.length,
        };
        choices[1]!.reject({ code: "agent_local_models_revision_conflict" });
        await until(() => reads.length === 4);
        reads.at(-1)!(answer("1"));
        await until(() => choices.length === 3);
        choices[2]!.resolve(answer("2", true));
        await until(() => value?.revision === "2");
        const disabled = render("B", false);
        const resumed = render("B");
        reads.at(-1)!(answer("0"));
        await until(() => choices.length === 4);
        choices[3]!.resolve(answer("3", true));
        await until(() => value?.revision === "3");
        return {
          firstB,
          afterObsolete,
          disabled,
          resumed,
          final: (value as AgentLocalModels | null)?.revision,
        };
      } finally {
        dom.flushSync(() => root.unmount());
        container.remove();
      }
    }, outcome);
    expect(result.firstB).toBeNull();
    expect(result.afterObsolete).toEqual({
      revision: "0",
      reads: 3,
      choices: 2,
    });
    expect(result.disabled).toBeNull();
    expect(result.resumed).toBeNull();
    expect(result.final).toBe("3");
  });

test("agent status belongs to one reader observation and pushes outrank initial reads", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=signed-out&bar=off");
  await page.waitForFunction(() => Boolean(window.__scenarioModules));
  const result = await page.evaluate(async () => {
    const { react, dom, client } =
      await window.__scenarioModules!.profileViews();
    const { live } = await window.__scenarioModules!.agentReaders();
    const pending: ((status: AgentServiceStatus) => void)[] = [];
    const listeners: ((status: AgentServiceStatus) => void)[] = [];
    let stopped = 0;
    const session = {
      status: () =>
        new Promise<AgentServiceStatus>((resolve) => pending.push(resolve)),
      observeStatus: async (listener: (status: AgentServiceStatus) => void) => {
        listeners.push(listener);
        return () => {
          stopped += 1;
        };
      },
    } as unknown as AgentSession;
    const commits: (string | null)[] = [];
    function Probe({ reader, enabled }: { reader: string; enabled: boolean }) {
      const status = live.useAgentStatus(session, reader, enabled);
      react.useLayoutEffect(() => {
        commits.push(status?.state ?? null);
      });
      return null;
    }
    const container = document.createElement("div");
    document.body.append(container);
    const root = client.createRoot(container);
    const render = (reader: string, enabled = true) => {
      const at = commits.length;
      dom.flushSync(() =>
        root.render(react.createElement(Probe, { reader, enabled })),
      );
      return commits[at];
    };
    const turn = () => new Promise((resolve) => window.setTimeout(resolve, 10));
    let mounted = true;
    try {
      render("A");
      dom.flushSync(() =>
        listeners[0]!({ state: "ready", agent_version: "A" }),
      );
      await turn();
      const firstB = render("B");
      listeners[0]!({ state: "ready", agent_version: "old" });
      pending[0]!({ state: "ready", agent_version: "old-read" });
      await turn();
      const afterOld = commits.at(-1);
      dom.flushSync(() => listeners[1]!({ state: "starting" }));
      pending[1]!({ state: "ready", agent_version: "initial" });
      await turn();
      const afterInitial = commits.at(-1);
      const hidden = render("B", false);
      const resumed = render("B");
      dom.flushSync(() =>
        listeners[2]!({ state: "ready", agent_version: "new" }),
      );
      await turn();
      const final = commits.at(-1);
      dom.flushSync(() => root.unmount());
      mounted = false;
      const beforeLate = commits.length;
      listeners[2]!({ state: "stopped" });
      pending[2]!({ state: "starting" });
      await turn();
      return {
        firstB,
        afterOld,
        afterInitial,
        hidden,
        resumed,
        final,
        stopped,
        late: commits.length - beforeLate,
      };
    } finally {
      if (mounted) dom.flushSync(() => root.unmount());
      container.remove();
    }
  });
  expect(result).toEqual({
    firstB: null,
    afterOld: null,
    afterInitial: "starting",
    hidden: null,
    resumed: null,
    final: "ready",
    stopped: 3,
    late: 0,
  });
});
