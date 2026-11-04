import { expect, test } from "@playwright/test";

// The Sede view hook against a port that answers the open the way a host
// without its browser does: the view gets an id and an end in the same breath.
// The hook must not send the ended view a resize, a credit or an input.

for (const endsFirst of [true, false])
  test(`the Sede view hook ${endsFirst ? "stops sending to a view that ended before open resolved" : "still follows the panel's size while the view is open"}`, async ({
    page,
  }) => {
    await page.goto("/scenarios.html?scenario=signed-out&bar=off");
    await page.waitForFunction(() => Boolean(window.__scenarioModules));
    const result = await page.evaluate(async (endsFirst) => {
      const { react, dom, client, hook } =
        await window.__scenarioModules!.sedeViewHook();
      const calls = { resize: 0, credit: 0, input: 0, close: 0 };
      const port: import("../../src/shell/sedeView").SedeViewPort = {
        open: async (_size, listener) => {
          if (endsFirst)
            listener({
              kind: "ended",
              view: 1,
              reason: "component_not_ready",
              code: null,
              outcome: { condition: "refused", end: null, publication: null },
              recovery_action_id: "operator.provision.browser",
            });
          return {
            input: async () => void calls.input++,
            navigate: async () => undefined,
            clipboard: async () => undefined,
            resize: async () => void calls.resize++,
            credit: async () => void calls.credit++,
            dialog: async () => undefined,
            downloadAnswer: async () => ({ saving: false }),
            fileChooserAnswer: async () => ({ supplied: 0 }),
            openExternal: async () => undefined,
            close: async () => void calls.close++,
          };
        },
      };
      type View = ReturnType<typeof hook.useSedeView>;
      let view!: View;
      const first = { cssWidth: 800, cssHeight: 600, scale: 1 };
      const second = { cssWidth: 640, cssHeight: 480, scale: 1 };
      function Probe({
        size,
      }: {
        size: import("../../src/shell/sedeView").SedeViewSize;
      }) {
        const current = hook.useSedeView({
          port,
          size,
          shown: true,
          draw: async () => undefined,
        });
        react.useLayoutEffect(() => {
          view = current;
        });
        return null;
      }
      const container = document.createElement("div");
      document.body.append(container);
      const root = client.createRoot(container);
      const render = (size: typeof first) =>
        dom.flushSync(() => root.render(react.createElement(Probe, { size })));
      const turn = (ms: number) =>
        new Promise((resolve) => window.setTimeout(resolve, ms));
      try {
        render(first);
        await turn(100);
        render(second);
        // Longer than the settle pause and every retry the hook allows.
        await turn(1800);
        view.input({
          type: "pointer",
          action: "move",
          x: 1,
          y: 1,
          button: "none",
          click_count: 0,
          modifiers: 0,
        });
        await turn(20);
        return {
          phase: view.state.phase,
          problem: view.state.problem,
          resize: calls.resize,
          credit: calls.credit,
          input: calls.input,
        };
      } finally {
        dom.flushSync(() => root.unmount());
        container.remove();
      }
    }, endsFirst);
    if (endsFirst)
      expect(result).toEqual({
        phase: "ended",
        problem: null,
        resize: 0,
        credit: 0,
        input: 0,
      });
    else
      expect(result).toMatchObject({ phase: "opening", resize: 1, input: 1 });
  });
