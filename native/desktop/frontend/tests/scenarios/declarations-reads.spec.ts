import { expect, test } from "@playwright/test";
import type { ModeloPort } from "../../src/shell/modelo";
import type { ModeloDeclarationsListProjectionV1 } from "../../src/shell/modeloContract/modeloDeclarations";
import type { ListMemory } from "../../src/components/modelo/declarations/useDeclarationsList";

for (const outcome of ["success", "failure"] as const) {
  test(`a late declarations ${outcome} preserves workspace invalidation`, async ({
    page,
  }) => {
    await page.goto("/scenarios.html?scenario=signed-out&bar=off");
    await page.waitForFunction(() => Boolean(window.__scenarioModules));
    const result = await page.evaluate(async (outcome) => {
      const { react, dom, client } =
        await window.__scenarioModules!.profileViews();
      const { useDeclarationsList } =
        await window.__scenarioModules!.declarationsList();
      const pending: {
        resolve(list: ModeloDeclarationsListProjectionV1): void;
        reject(error: Error): void;
      }[] = [];
      const port = {
        declarations: () =>
          new Promise<ModeloDeclarationsListProjectionV1>((resolve, reject) =>
            pending.push({ resolve, reject }),
          ),
      } as unknown as ModeloPort;
      const memory: { current: ListMemory } = { current: {} };
      const answer = (marker: string): ModeloDeclarationsListProjectionV1 => ({
        result_version: 1,
        profile_id: "profile",
        output_language: "en",
        rows: [],
        zones: [],
        sources: [],
        notices: [marker],
        deadline_note_words: null,
        creation_targets: [],
      });
      let refresh = () => {};
      function Probe({ shown }: { shown: boolean }) {
        const { reread } = useDeclarationsList(
          port,
          "profile",
          "en",
          shown,
          memory,
        );
        react.useLayoutEffect(() => {
          refresh = reread;
        });
        return null;
      }
      const container = document.createElement("div");
      document.body.append(container);
      const root = client.createRoot(container);
      const render = (mounted: boolean, shown = true) =>
        dom.flushSync(() =>
          root.render(mounted ? react.createElement(Probe, { shown }) : null),
        );
      const turn = () =>
        new Promise((resolve) => window.setTimeout(resolve, 10));
      const waitFor = async (marker: string) => {
        for (let at = 0; at < 100; at++) {
          if (memory.current.list?.notices[0] === marker) return;
          await turn();
        }
        throw new Error(`List never accepted ${marker}`);
      };
      try {
        render(true);
        pending.at(-1)!.resolve(answer("initial"));
        await waitFor("initial");
        render(false);
        render(true);
        const cachedRequests = pending.length;
        dom.flushSync(refresh);
        const obsolete = pending.at(-1)!;
        render(false);
        // The workspace wrote while the list was unmounted.
        memory.current.stale = true;
        if (outcome === "success") obsolete.resolve(answer("obsolete"));
        else obsolete.reject(new Error("obsolete failure"));
        await turn();
        const afterWorkspaceWrite = {
          marker: memory.current.list?.notices[0],
          stale: memory.current.stale,
        };
        render(true);
        const returnedRequests = pending.length;
        pending.at(-1)!.resolve(answer("current"));
        await waitFor("current");
        dom.flushSync(refresh);
        const beforeWrite = pending.at(-1)!;
        // Creation marks the mounted list stale and requests a new read.
        memory.current.stale = true;
        dom.flushSync(refresh);
        beforeWrite.resolve(answer("before-write"));
        await turn();
        const afterMountedWrite = {
          marker: memory.current.list?.notices[0],
          stale: memory.current.stale,
        };
        pending.at(-1)!.resolve(answer("after-write"));
        await waitFor("after-write");
        dom.flushSync(refresh);
        const hidden = pending.at(-1)!;
        render(true, false);
        hidden.resolve(answer("hidden"));
        await turn();
        const beforeShowing = pending.length;
        render(true);
        const resumedRequests = pending.length - beforeShowing;
        pending.at(-1)!.resolve(answer("resumed"));
        await waitFor("resumed");
        return {
          resumedRequests,
          cachedRequests,
          returnedRequests,
          afterWorkspaceWrite,
          afterMountedWrite,
          finalStale: memory.current.stale,
        };
      } finally {
        dom.flushSync(() => root.unmount());
        container.remove();
      }
    }, outcome);
    expect(result.cachedRequests).toBe(1);
    expect(result.returnedRequests).toBe(3);
    expect(result.afterWorkspaceWrite).toEqual({
      marker: "initial",
      stale: true,
    });
    expect(result.afterMountedWrite).toEqual({
      marker: "current",
      stale: true,
    });
    expect(result.finalStale).toBe(false);
    expect(result.resumedRequests).toBe(1);
  });
}
