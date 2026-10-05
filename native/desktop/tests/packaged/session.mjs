// The harness's connection to a running window over the Chrome DevTools
// protocol, shared by the packaged run and the harness's own tests.
import { existsSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { pathToFileURL } from "node:url";

import { instrument, terminalRows, terminalState } from "./browser.mjs";
import { originOf } from "./verdicts.mjs";

const frontend = new URL("../../frontend/package.json", import.meta.url);

/** Playwright's Chromium driver from the frontend's pinned devDependency. */
export async function chromium() {
  const require = createRequire(frontend);
  const directory = dirname(require.resolve("playwright-core/package.json"));
  const entry = resolve(directory, "index.mjs");
  if (!existsSync(entry)) throw new Error("playwright-core has no ESM entry");
  return (await import(pathToFileURL(entry).href)).chromium;
}

export const sleep = (ms) => new Promise((done) => setTimeout(done, ms));

/** Polls `read` until it returns a truthy value or the deadline passes. */
export async function waitFor(
  read,
  { timeout = 15000, interval = 100, what } = {},
) {
  const deadline = Date.now() + timeout;
  let last;
  for (;;) {
    try {
      last = await read();
      if (last) return last;
    } catch (error) {
      last = error;
    }
    if (Date.now() > deadline)
      throw new Error(
        `Timed out after ${timeout} ms waiting for ${what ?? "a condition"}${last instanceof Error ? `: ${last.message}` : ""}`,
      );
    await sleep(interval);
  }
}

/** Waits until a DevTools endpoint answers on `port`. */
export async function devtoolsEndpoint(port, timeout = 60000) {
  const endpoint = `http://127.0.0.1:${port}`;
  await waitFor(async () => (await fetch(`${endpoint}/json/version`)).ok, {
    timeout,
    interval: 250,
    what: `DevTools on port ${port}`,
  });
  return endpoint;
}

export class Session {
  constructor({ browser, page, shellOrigins, docsOrigin }) {
    this.browser = browser;
    this.page = page;
    this.shellOrigins = shellOrigins;
    this.docsOrigin = docsOrigin;
    this.navigations = 0;
    this.console = [];
    page.on("framenavigated", (frame) => {
      if (frame === page.mainFrame()) this.navigations += 1;
    });
    page.on("console", (message) =>
      this.console.push({
        at: Date.now(),
        type: message.type(),
        text: message.text().slice(0, 400),
        url: message.location()?.url ?? "",
      }),
    );
  }

  /** The documentation frame: a direct child of the shell on the docs origin. */
  docsFrame() {
    return (
      this.page
        .mainFrame()
        .childFrames()
        .find((frame) => originOf(frame.url()) === this.docsOrigin) ?? null
    );
  }

  async waitDocs(timeout = 30000) {
    const frame = await waitFor(() => this.docsFrame(), {
      timeout,
      what: "the documentation frame",
    });
    await frame.waitForLoadState("load", { timeout });
    await waitFor(() => frame.evaluate(() => !!window.__s10), {
      timeout,
      what: "the documentation frame's instrumentation",
    });
    return frame;
  }

  shell(fn, arg) {
    return this.page.evaluate(fn, arg);
  }

  docs(fn, arg) {
    const frame = this.docsFrame();
    if (!frame) throw new Error("No documentation frame");
    return frame.evaluate(fn, arg);
  }

  /** A host command from the shell document, with the shell's token. */
  call(command, args = {}) {
    return this.page.evaluate(
      ({ command, args }) => window.__s10.call(command, args),
      { command, args },
    );
  }

  /** One frame's instrumentation record, without the shell's bulky traces. */
  static frameState(frame) {
    return frame.evaluate(() => {
      const s = window.__s10;
      if (!s) return null;
      return {
        role: s.role,
        origin: s.origin,
        href: location.href,
        marker: s.marker,
        csp: s.csp,
        console: s.console,
        messages: s.messages,
        keys: s.keys,
        menus: s.menus,
        beforeprint: s.beforeprint,
        zoom: window.devicePixelRatio,
      };
    });
  }

  async frames() {
    const states = [await Session.frameState(this.page.mainFrame())];
    const docs = this.docsFrame();
    if (docs) states.push(await Session.frameState(docs));
    return states.filter(Boolean);
  }

  /**
   * What a gesture could change, for noEffectVerdict: each frame's load
   * marker and address, top-frame navigations, print requests and zoom, plus
   * the key and menu events each page has seen. `windows` and `targets` come
   * from the operating system and the browser.
   */
  async effectState({ windows = [], targets = 0 } = {}) {
    const frames = await this.frames();
    const docs = frames.find((frame) => frame.role === "docs");
    return {
      markers: { shell: frames[0]?.marker, docs: docs?.marker },
      urls: { shell: frames[0]?.href, docs: docs?.href },
      navigations: this.navigations,
      beforeprint: frames.reduce((sum, frame) => sum + frame.beforeprint, 0),
      zoom: frames.map((frame) => frame.zoom).join("/"),
      windows,
      targets,
      keys: Object.fromEntries(
        frames.map((frame) => [frame.role, frame.keys.length]),
      ),
      menus: Object.fromEntries(
        frames.map((frame) => [frame.role, frame.menus.length]),
      ),
    };
  }

  rows(kind) {
    return this.page.evaluate(terminalRows, kind);
  }

  terminal(kind) {
    return this.page.evaluate(terminalState, kind);
  }

  waitRows(kind, test, { timeout = 30000, what } = {}) {
    return waitFor(
      async () => {
        const rows = await this.rows(kind);
        return rows !== null && test(rows) ? rows : null;
      },
      { timeout, what: what ?? `${kind} terminal output` },
    );
  }

  async showTab(kind) {
    if (kind === "tui") return;
    await this.page.click(`#tab-${kind}`);
    await this.page.waitForSelector(`[data-terminal="${kind}"]:not([hidden])`);
  }

  async focusTerminal(kind) {
    await this.showTab(kind);
    await this.page.click(`[data-terminal="${kind}"] .xterm-screen`, {
      position: { x: 20, y: 10 },
    });
  }

  async type(kind, text, { enter = true } = {}) {
    await this.focusTerminal(kind);
    await this.page.keyboard.type(text, { delay: 8 });
    if (enter) await this.page.keyboard.press("Enter");
  }

  async cdp() {
    return this.page.context().newCDPSession(this.page);
  }
}

/**
 * Connects to a running window, instruments it and reloads the shell so the
 * instrumentation sees every document from its start.
 */
export async function connect({
  endpoint,
  shellOrigins,
  docsOrigin,
  ipcPrefix,
  blockExternal = true,
  timeout = 60000,
}) {
  const browser = await (
    await chromium()
  ).connectOverCDP(endpoint, { timeout });
  const context = await waitFor(() => browser.contexts()[0], {
    timeout,
    what: "a browser context",
  });
  const page = await waitFor(
    () =>
      context
        .pages()
        .find((candidate) => shellOrigins.includes(originOf(candidate.url()))),
    { timeout, what: "the shell document" },
  );
  const session = new Session({ browser, page, shellOrigins, docsOrigin });
  await page.addInitScript(instrument, {
    shellOrigins,
    docsOrigin,
    ipcPrefix,
    blockExternal,
  });
  await page.reload({ waitUntil: "load", timeout });
  await waitFor(() => page.evaluate(() => !!window.__s10?.call), {
    timeout,
    what: "the shell's instrumentation",
  });
  await waitFor(() => page.evaluate(() => window.__s10.tokenSeen), {
    timeout,
    what: "the shell's first command",
  });
  return session;
}
