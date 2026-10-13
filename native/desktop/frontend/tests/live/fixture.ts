import * as base from "playwright/test";
import type { Browser, BrowserContext, Page } from "playwright/test";

// The live project runs the shared agent specs against the packaged desktop.
// Its tsconfig resolves "@playwright/test" to this module, so the specs and
// their helpers import Playwright unchanged and receive the desktop's own
// window, attached over the WebView2 DevTools protocol, as their `page`.
//
// What the specs address as the scenario page is the desktop's shell entry
// here: a scenario's query selects fixture behaviour that the live host does
// not have. Checks that only the scenario host can satisfy are skipped where
// `test.info().project.metadata.agentHost` is "live".

export * from "playwright/test";

/** The address the specs open the scenario host at. */
const SCENARIO_PAGE = "/scenarios.html";

/** The packaged shell's entry: its window URL under the custom protocol. */
const PACKAGED_ENTRY = "http://tauri.localhost/index.html";

const ATTACH_TIMEOUT = 60_000;

type Goto = Page["goto"];

function endpoint(): string {
  const value = process.env.CADRUMO_AGENT_LIVE_ENDPOINT;
  if (!value)
    throw new Error(
      "The live project attaches to a running lane desktop. Run it with `just desktop-agent-live`, or set CADRUMO_AGENT_LIVE_ENDPOINT to the desktop's DevTools endpoint.",
    );
  const url = new URL(value);
  if (url.hostname !== "127.0.0.1" && url.hostname !== "[::1]")
    throw new Error("The DevTools endpoint must be on the loopback address.");
  return url.origin;
}

/** The shell entry the desktop loads, packaged or served. */
export function shellEntry(): URL {
  return new URL(process.env.CADRUMO_AGENT_LIVE_ENTRY || PACKAGED_ENTRY);
}

/**
 * Where a spec's address leads on the desktop: the scenario page is the
 * shell entry itself; any other address is resolved against the entry.
 */
export function liveAddress(
  address: string,
  entry: URL = shellEntry(),
): string {
  const target = new URL(address, entry);
  if (target.origin === entry.origin && target.pathname === SCENARIO_PAGE)
    return entry.href;
  return target.href;
}

async function shellPage(context: BrowserContext, entry: URL): Promise<Page> {
  const deadline = Date.now() + ATTACH_TIMEOUT;
  for (;;) {
    const page = context
      .pages()
      .find(
        (candidate) =>
          URL.canParse(candidate.url()) &&
          new URL(candidate.url()).origin === entry.origin,
      );
    if (page) return page;
    if (Date.now() > deadline)
      throw new Error(
        `No desktop page on ${entry.origin} within ${ATTACH_TIMEOUT} ms.`,
      );
    await new Promise((done) => setTimeout(done, 250));
  }
}

export const test = base.test.extend<object, { liveBrowser: Browser }>({
  liveBrowser: [
    async ({ playwright }, use) => {
      // Connected through the runner's own Playwright, so traces and
      // screenshots follow the desktop's context as they would a new one.
      const browser = await playwright.chromium.connectOverCDP(endpoint(), {
        timeout: ATTACH_TIMEOUT,
      });
      await use(browser);
      // Disconnects; the desktop's lifetime belongs to the lane.
      await browser.close();
    },
    { scope: "worker", timeout: ATTACH_TIMEOUT * 2 },
  ],
  browser: [
    async ({ liveBrowser }, use) => use(liveBrowser),
    { scope: "worker" },
  ],
  context: async ({ browser }, use) => {
    const context = browser.contexts()[0];
    if (!context) throw new Error("The desktop exposes no browser context.");
    await use(context);
  },
  page: async ({ context }, use) => {
    const entry = shellEntry();
    const page = await shellPage(context, entry);
    // Every test starts from the desktop's shell entry with empty web
    // storage, as each test on the scenario host starts in a new context.
    await page.goto(entry.href);
    await page.evaluate(() => {
      localStorage.clear();
      sessionStorage.clear();
    });
    const original: Goto = page.goto.bind(page);
    const goto: Goto = (address, options) =>
      original(liveAddress(address, entry), options);
    Object.defineProperty(page, "goto", {
      value: goto,
      configurable: true,
      writable: true,
    });
    try {
      await use(page);
    } finally {
      delete (page as { goto?: Goto }).goto;
    }
  },
});

export default test;
