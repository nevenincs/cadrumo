import { expect, test } from "@playwright/test";
import { build } from "esbuild";
import { fileURLToPath } from "node:url";

// A profile reader reads the profile on first need, after a change cue and on
// an explicit refresh, and never because it was shown or hidden. One read is
// about nine host operations, so a reader that reads again at every show
// queues them behind each other. The hook is compiled with the project's own
// React and driven in a page with a fake port that counts what it is asked.

type Counts = { reads: number; observes: number; stops: number };
type Harness = {
  /** Renders one reader per entry of `readers`, all on the same port. */
  render(readers: { id: string; shown: boolean }[]): Promise<void>;
  cue(): Promise<void>;
  refresh(id: string): Promise<void>;
  counts(): Counts;
  text(id: string): string | null;
  unmount(): Promise<void>;
};
declare global {
  interface Window {
    makeHarness(): Harness;
  }
}

async function bundle(): Promise<string> {
  const hook = JSON.stringify(
    fileURLToPath(new URL("../src/shell/userProfile.ts", import.meta.url)),
  );
  const built = await build({
    stdin: {
      contents: `
        import { createElement as h } from "react";
        import { createRoot } from "react-dom/client";
        import { flushSync } from "react-dom";
        import { useUserProfile } from ${hook};
        const settle = () => new Promise((done) => setTimeout(done, 25));
        window.makeHarness = () => {
          const counts = { reads: 0, observes: 0, stops: 0 };
          const cues = new Set();
          const refreshers = new Map();
          const port = {
            read: async () => {
              counts.reads += 1;
              return { profile_id: "synthetic-profile", record_revision: counts.reads };
            },
            change: async () => undefined,
            observe: async (changed) => {
              counts.observes += 1;
              cues.add(changed);
              return () => {
                counts.stops += 1;
                cues.delete(changed);
              };
            },
            aeat: {},
          };
          const Probe = ({ id, shown }) => {
            const profile = useUserProfile(port, "synthetic-reader", "en", shown);
            refreshers.set(id, profile.refresh);
            return h(
              "span",
              { id },
              profile.data ? "data " + profile.data.record_revision : profile.loading ? "loading" : "none",
            );
          };
          const host = document.createElement("div");
          document.body.append(host);
          const root = createRoot(host);
          return {
            async render(readers) {
              flushSync(() =>
                root.render(
                  h("div", null, readers.map(({ id, shown }) => h(Probe, { key: id, id, shown }))),
                ),
              );
              await settle();
            },
            async cue() {
              for (const changed of [...cues]) changed();
              await settle();
            },
            async refresh(id) {
              refreshers.get(id)();
              await settle();
            },
            counts: () => ({ ...counts }),
            text: (id) => document.getElementById(id)?.textContent ?? null,
            async unmount() {
              flushSync(() => root.unmount());
              await settle();
            },
          };
        };
      `,
      resolveDir: fileURLToPath(new URL("..", import.meta.url)),
      loader: "js",
    },
    bundle: true,
    write: false,
    platform: "browser",
    format: "iife",
    jsx: "automatic",
    define: { "process.env.NODE_ENV": '"production"' },
    logLevel: "silent",
  });
  return built.outputFiles.map((file) => file.text).join("");
}

test.beforeEach(async ({ page }) => {
  await page.setContent("<body></body>");
  await page.addScriptTag({ content: await bundle() });
});

test("showing and hiding a profile reader again and again makes one read", async ({
  page,
}) => {
  const counts = await page.evaluate(async () => {
    const harness = window.makeHarness();
    for (const shown of [true, false, true, false, true, false, true])
      await harness.render([{ id: "reader", shown }]);
    return harness.counts();
  });
  expect(counts).toEqual({ reads: 1, observes: 1, stops: 0 });
});

test("a change cue while the reader is hidden reads once, when it is shown", async ({
  page,
}) => {
  const result = await page.evaluate(async () => {
    const harness = window.makeHarness();
    const one = (shown: boolean) => [{ id: "reader", shown }];
    await harness.render(one(true));
    await harness.render(one(false));
    await harness.cue();
    await harness.cue();
    const hidden = harness.counts();
    await harness.render(one(true));
    const shown = harness.counts();
    await harness.render(one(false));
    await harness.render(one(true));
    return {
      hidden,
      shown,
      after: harness.counts(),
      text: harness.text("reader"),
    };
  });
  expect(result.hidden.reads).toBe(1);
  expect(result.shown.reads).toBe(2);
  expect(result.after).toEqual({ reads: 2, observes: 1, stops: 0 });
  expect(result.text).toBe("data 2");
});

test("a change cue while the reader is shown reads at once", async ({
  page,
}) => {
  const reads = await page.evaluate(async () => {
    const harness = window.makeHarness();
    await harness.render([{ id: "reader", shown: true }]);
    await harness.cue();
    return harness.counts().reads;
  });
  expect(reads).toBe(2);
});

test("a reader that is never shown makes no read", async ({ page }) => {
  const counts = await page.evaluate(async () => {
    const harness = window.makeHarness();
    for (let step = 0; step < 3; step += 1)
      await harness.render([{ id: "reader", shown: false }]);
    await harness.cue();
    return harness.counts();
  });
  expect(counts.reads).toBe(0);
});

test("a reader mounted beside a reader that has read draws its data without a read", async ({
  page,
}) => {
  const result = await page.evaluate(async () => {
    const harness = window.makeHarness();
    await harness.render([{ id: "window", shown: true }]);
    // The window's own reader stays; a page mounts, is shown, unmounts and
    // mounts again, as navigating to it and away does.
    for (let visit = 0; visit < 4; visit += 1) {
      await harness.render([
        { id: "window", shown: false },
        { id: "page", shown: true },
      ]);
      await harness.render([{ id: "window", shown: true }]);
    }
    return { counts: harness.counts(), text: harness.text("window") };
  });
  expect(result.counts.reads).toBe(1);
  expect(result.text).toBe("data 1");
});

test("an explicit refresh reads once more", async ({ page }) => {
  const reads = await page.evaluate(async () => {
    const harness = window.makeHarness();
    await harness.render([{ id: "reader", shown: true }]);
    await harness.refresh("reader");
    return harness.counts().reads;
  });
  expect(reads).toBe(2);
});

test("leaving the last reader ends the subscription", async ({ page }) => {
  const counts = await page.evaluate(async () => {
    const harness = window.makeHarness();
    await harness.render([{ id: "reader", shown: true }]);
    await harness.unmount();
    return harness.counts();
  });
  expect(counts).toEqual({ reads: 1, observes: 1, stops: 1 });
});
