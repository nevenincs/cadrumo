// Tests the packaged run's own frame handling and assertion logic in a plain
// Chromium against stand-in pages, so each check is shown to report both a
// passing and a failing window. It needs no WebView2 and no desktop session.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, describe, test } from "node:test";

import { docsProbe, pasteInto } from "./packaged/browser.mjs";
import {
  DesktopInput,
  descendants,
  freePort,
  survivors,
} from "./packaged/os.mjs";
import { refusalProbe, tokenCheck } from "./packaged/probes.mjs";
import {
  chromium,
  connect,
  devtoolsEndpoint,
  sleep,
  waitFor,
} from "./packaged/session.mjs";
import { startStandin } from "./packaged/standin.mjs";
import { canonicalFailure } from "./packaged/sign-in.mjs";
import {
  CREDIT_WINDOW,
  FAIL,
  PASS,
  READ_CHUNK,
  channelFetchVerdict,
  closeVerdict,
  creditVerdict,
  cspVerdict,
  everyByteVerdict,
  framesVerdict,
  noEffectVerdict,
  pagefindVerdict,
  refusalVerdict,
  terminalVerdict,
} from "./packaged/verdicts.mjs";

const cleanups = [];
test("canonical failure evidence retains identifiers and excludes payloads", () => {
  const secret = "SECRET_TOKEN";
  assert.deepEqual(
    canonicalFailure(
      JSON.stringify({
        schema_version: "2",
        command: "config.login",
        message: secret,
        error: {
          code: "REFUSED",
          message: secret,
          context: { reason: "CREDENTIAL_REJECTED", password: secret },
        },
      }),
      [secret],
    ),
    {
      schema: "2",
      command: "config.login",
      code: "REFUSED",
      reason: "CREDENTIAL_REJECTED",
    },
  );
  assert.deepEqual(
    canonicalFailure(
      JSON.stringify({
        error: {
          code: secret,
          context: { reason: "untrusted payload\n" + secret },
        },
      }),
      [secret],
    ),
    {},
  );
  assert.deepEqual(canonicalFailure("x".repeat(65537)), {});
  assert.deepEqual(canonicalFailure("not json"), {});
});
after(async () => {
  const failures = [];
  for (const cleanup of cleanups.reverse()) {
    try {
      await cleanup();
    } catch (error) {
      failures.push(error);
    }
  }
  if (failures.length)
    throw new AggregateError(failures, "stand-in cleanup failed");
});

/** A Chromium on a DevTools port, showing a stand-in shell, connected through the harness. */
async function openWindow(variant) {
  const standin = await startStandin({ variant });
  const profile = mkdtempSync(join(tmpdir(), "cadrumo-packaged-harness-"));
  const port = await freePort();
  const browser = spawn(
    (await chromium()).executablePath(),
    [
      "--headless=new",
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${profile}`,
      "--no-first-run",
      "--no-default-browser-check",
      // The sandbox cannot start in a service session; the pages are local fixtures.
      "--no-sandbox",
      standin.shellUrl,
    ],
    { stdio: "ignore", windowsHide: true },
  );
  const exited = new Promise((done) => browser.on("exit", done));
  let session;
  cleanups.push(async () => {
    const failures = [];
    const attempt = async (release) => {
      try {
        await release();
      } catch (error) {
        failures.push(error);
      }
    };
    await attempt(async () => {
      if (session) {
        const control = await session.browser.newBrowserCDPSession();
        await control.send("Browser.close").catch(() => undefined);
      }
    });
    await attempt(async () => {
      const stopped = await Promise.race([
        exited.then(() => true),
        sleep(5000).then(() => false),
      ]);
      if (!stopped) {
        browser.kill();
        assert.equal(
          await Promise.race([
            exited.then(() => true),
            sleep(10000).then(() => false),
          ]),
          true,
          "stand-in browser must exit",
        );
      }
    });
    await attempt(() => session?.browser.close());
    await attempt(() => standin.close());
    await attempt(() =>
      rmSync(profile, {
        recursive: true,
        force: true,
        maxRetries: 10,
        retryDelay: 500,
      }),
    );
    if (failures.length)
      throw new AggregateError(failures, "stand-in releases failed");
  });
  session = await connect({
    endpoint: await devtoolsEndpoint(port),
    shellOrigins: [standin.shellOrigin],
    docsOrigin: standin.docsOrigin,
    ipcPrefix: `${standin.ipcOrigin}/`,
  });
  await waitFor(() => session.shell(() => !!window.standin), {
    what: "the stand-in shell",
  });
  await session.waitDocs();
  return { session, standin };
}

/** Delivers one channel frame the way the host's interceptor evaluates it. */
function deliver(session, frames) {
  return session.shell((list) => {
    const { channel } = window.standin;
    for (const { tag, text, index } of list) {
      const payload = new TextEncoder().encode(text);
      const bytes = new Uint8Array(payload.length + 1);
      bytes[0] = tag;
      bytes.set(payload, 1);
      window.__TAURI_INTERNALS__.runCallback(channel, {
        message: bytes.buffer,
        index,
      });
    }
  }, frames);
}

describe("against a refusing stand-in", async () => {
  const { session, standin } = await openWindow("refusing");
  const baseline = "S10-BASELINE-standin";

  test("the frames are found on their origins, and a wrong title or origin fails", async () => {
    const frame = session.docsFrame();
    const observed = {
      shellUrl: session.page.url(),
      shellOrigins: [standin.shellOrigin],
      docsUrl: frame.url(),
      docsOrigin: standin.docsOrigin,
      docsTitle: await frame.title(),
    };
    assert.equal(
      framesVerdict({ ...observed, expectedTitle: "Stand-in docs /index.html" })
        .verdict,
      PASS,
    );
    assert.equal(
      framesVerdict({ ...observed, expectedTitle: "Other" }).verdict,
      FAIL,
    );
    assert.equal(
      framesVerdict({ ...observed, docsOrigin: standin.shellOrigin }).verdict,
      FAIL,
    );
  });

  test("a clean policy in both frames passes the CSP check", async () => {
    const frames = await session.frames();
    assert.deepEqual(
      frames.map((f) => f.role),
      ["shell", "docs"],
    );
    const verdict = cspVerdict(
      frames,
      session.console.map((e) => e.text),
    );
    assert.equal(verdict.verdict, PASS, verdict.detail);
  });

  test("the token check passes: read once by the shell, unreachable from the docs frame", async () => {
    const verdict = await tokenCheck(session);
    assert.equal(verdict.verdict, PASS, verdict.detail);
  });

  test("every docs-frame transport is reported as refused", async () => {
    await session.call("shell_clipboard_write", { text: baseline });
    for (const kind of [
      "invoke",
      "fetch",
      "ipc-post-message",
      "webview-post-message",
    ]) {
      const verdict = await refusalProbe(session, kind, {
        ipcOrigin: standin.ipcOrigin,
        baseline,
      });
      assert.equal(verdict.verdict, PASS, `${kind}: ${verdict.detail}`);
    }
    assert.equal(standin.state.clipboard, baseline);
  });

  test("channel frames are counted per channel, gaps are found and the alternate screen is seen across frames", async () => {
    await deliver(session, [
      { tag: 1, text: '{"pid":42}', index: 0 },
      { tag: 0, text: "hello ", index: 1 },
      { tag: 0, text: "\x1b[?10", index: 2 },
      { tag: 0, text: "49h world", index: 3 },
    ]);
    const id = await session.shell(() => window.standin.channel);
    let channel = await session.shell((key) => window.__s10.channels[key], id);
    assert.equal(channel.kind, "python");
    assert.equal(channel.session, 7);
    assert.equal(
      channel.dataBytes,
      ["hello ", "[?10", "49h world"].join("").length,
    );
    assert.equal(channel.started.pid, 42);
    assert.equal(channel.altScreen, true);
    assert.equal(channel.maxIndex + 1 - channel.seen, 0);
    await deliver(session, [{ tag: 0, text: "late", index: 5 }]);
    channel = await session.shell((key) => window.__s10.channels[key], id);
    const gaps = channel.maxIndex + 1 - channel.seen;
    assert.equal(gaps, 1);
    assert.equal(
      channelFetchVerdict({ outcomes: [], gaps, outOfOrder: 0 }).verdict,
      FAIL,
    );
    assert.equal(
      channelFetchVerdict({ outcomes: [], gaps: 0, outOfOrder: 0 }).verdict,
      PASS,
    );
  });

  test("an exact acknowledgement probe passes and a host that delivered more fails", async () => {
    const received = await session.shell(
      () => window.__s10.channels[window.standin.channel].dataBytes,
    );
    const probe = async () => ({
      atReceived: await session.call("terminal_ack", {
        session: 7,
        offset: received,
      }),
      pastReceived: await session.call("terminal_ack", {
        session: 7,
        offset: received + 1,
      }),
    });
    standin.state.delivered = received;
    assert.equal(
      everyByteVerdict({ received, gaps: 0, ...(await probe()) }).verdict,
      PASS,
    );
    standin.state.delivered = received + 100;
    assert.equal(
      everyByteVerdict({ received, gaps: 0, ...(await probe()) }).verdict,
      FAIL,
    );
  });

  test("held acknowledgements reach the host only after release", async () => {
    standin.state.delivered = 1 << 30;
    const before = standin.state.acks.length;
    await session.shell(() => window.__s10.hold());
    const pending = session.shell(() => window.standin.ack(3));
    await sleep(500);
    assert.equal(standin.state.acks.length, before);
    await session.shell(() => window.__s10.release());
    await pending;
    assert.equal(standin.state.acks.length, before + 1);
    const acked = await session.shell(
      () => window.__s10.channels[window.standin.channel].acked,
    );
    assert.equal(acked, 3);
  });

  test("an external open is intercepted before it reaches the host", async () => {
    await session.shell(() =>
      window.standin.openExternal("https://example.com/s10"),
    );
    const external = await session.shell(() => window.__s10.external);
    assert.deepEqual(
      external.map((e) => e.url),
      ["https://example.com/s10"],
    );
    assert(!standin.state.commands.includes("open_external"));
  });

  test("page handlers are suppressed only on request", async () => {
    const press = async (suppressed) => {
      await session.shell((value) => {
        window.__s10.suppressPageHandlers = value;
      }, suppressed);
      await session.page.mouse.click(2, 2);
      await session.page.keyboard.press("a");
      await sleep(200);
      return session.shell(() => window.__s10.keys.at(-1));
    };
    const handled = await press(false);
    assert.equal(handled.prevented, true);
    const suppressed = await press(true);
    assert.equal(suppressed.prevented, false);
    assert.equal(suppressed.suppressed, true);
    await session.shell(() => {
      window.__s10.suppressPageHandlers = false;
    });
  });

  test("the effect detector passes a quiet gesture and fails print, frame navigation, top navigation and reload", async () => {
    const quiet = await session.effectState();
    assert.equal(
      noEffectVerdict(quiet, await session.effectState()).verdict,
      PASS,
    );

    const before = await session.effectState();
    await session.docs(() => window.dispatchEvent(new Event("beforeprint")));
    assert.match(
      noEffectVerdict(before, await session.effectState()).detail,
      /printing/,
    );

    const kept = await session.effectState();
    await session.shell((url) => {
      location.href = url;
    }, `${standin.shellOrigin}/nav-204`);
    await sleep(1000);
    assert.equal(
      noEffectVerdict(kept, await session.effectState()).verdict,
      PASS,
    );

    const docsBefore = await session.effectState();
    await session.docsFrame().goto(`${standin.docsOrigin}/other.html`);
    await session.waitDocs();
    const docsAfter = await session.effectState();
    assert.match(
      noEffectVerdict(docsBefore, docsAfter).detail,
      /docs (document replaced|navigated)/,
    );

    const reloadBefore = await session.effectState();
    await session.page.reload({ waitUntil: "load" });
    await session.waitDocs();
    await waitFor(() => session.shell(() => !!window.standin));
    const reloaded = noEffectVerdict(reloadBefore, await session.effectState());
    assert.equal(reloaded.verdict, FAIL);
    assert.match(reloaded.detail, /shell document replaced/);

    const leaveBefore = await session.effectState();
    await session
      .shell((url) => {
        location.href = url;
      }, `${standin.shellOrigin}/nav-200`)
      .catch(() => undefined);
    await session.page.waitForURL(/nav-200/);
    const left = await session.effectState().catch(() => null);
    assert(
      left === null || noEffectVerdict(leaveBefore, left).verdict === FAIL,
    );
  });
});

describe("against a leaking stand-in", async () => {
  const { session, standin } = await openWindow("leaking");
  const baseline = "S10-BASELINE-leak";

  test("a docs frame that reaches the token fails the token check", async () => {
    const verdict = await tokenCheck(session);
    assert.equal(verdict.verdict, FAIL);
    assert.match(verdict.detail, /docs frame sees __CADRUMO_SHELL__/);
  });

  test("delivery to the docs frame or a command's effect fails each refusal check", async () => {
    await session.call("shell_clipboard_write", { text: baseline });
    const expected = {
      invoke: /delivered to the documentation frame/,
      fetch: /delivered to the documentation frame/,
      "ipc-post-message": /the command ran/,
    };
    for (const [kind, pattern] of Object.entries(expected)) {
      await session.call("shell_clipboard_write", { text: baseline });
      const verdict = await refusalProbe(session, kind, {
        ipcOrigin: standin.ipcOrigin,
        baseline,
      });
      assert.equal(verdict.verdict, FAIL, kind);
      assert.match(verdict.detail, pattern, kind);
    }
  });

  test("a channel fetch that returns data fails", async () => {
    const fetched = await session.docs(docsProbe, {
      kind: "channel-fetch",
      ids: 4,
      timeoutMs: 3000,
    });
    const verdict = channelFetchVerdict({
      outcomes: fetched.outcomes,
      gaps: 0,
      outOfOrder: 0,
    });
    assert.equal(verdict.verdict, FAIL, verdict.detail);
  });
});

describe("against a violating stand-in", async () => {
  const { session } = await openWindow("violating");

  test("a blocked inline script fails the CSP check", async () => {
    const verdict = cspVerdict(
      await session.frames(),
      session.console.map((e) => e.text),
    );
    assert.equal(verdict.verdict, FAIL);
    assert(
      verdict.data.events.some(
        (e) => e.role === "docs" && /script-src/.test(e.directive),
      ),
    );
  });

  test("the Pagefind main-thread fallback warning fails the search check", async () => {
    const texts = [
      ...session.console.map((e) => e.text),
      ...(await session.frames()).flatMap((f) => f.console.map((c) => c.text)),
    ];
    assert.equal(
      pagefindVerdict({ results: 3, consoleTexts: texts }).verdict,
      FAIL,
    );
    assert.equal(
      pagefindVerdict({ results: 3, consoleTexts: [] }).verdict,
      PASS,
    );
    assert.equal(
      pagefindVerdict({ results: 0, consoleTexts: [] }).verdict,
      FAIL,
    );
  });

  test("a paste reaches xterm's paste handler shape", async () => {
    await session.shell(() => {
      const holder = document.createElement("div");
      holder.dataset.terminal = "python";
      const area = document.createElement("textarea");
      area.className = "xterm-helper-textarea";
      area.addEventListener("paste", (event) => {
        window.pasted = event.clipboardData.getData("text/plain");
      });
      holder.append(area);
      document.body.append(holder);
    });
    assert.equal(
      await session.shell(pasteInto, { kind: "python", text: "a\nb" }),
      true,
    );
    assert.equal(await session.shell(() => window.pasted), "a\nb");
  });
});

test("pure decisions report both outcomes", () => {
  assert.equal(creditVerdict({ plateau: CREDIT_WINDOW }).verdict, PASS);
  assert.equal(
    creditVerdict({ plateau: CREDIT_WINDOW + READ_CHUNK - 1 }).verdict,
    PASS,
  );
  assert.equal(creditVerdict({ plateau: CREDIT_WINDOW - 1 }).verdict, FAIL);
  assert.equal(
    creditVerdict({ plateau: CREDIT_WINDOW + READ_CHUNK }).verdict,
    FAIL,
  );
  const refused = { ok: false, error: { code: "invalid_arguments" } };
  assert.equal(
    everyByteVerdict({
      received: 9,
      atReceived: { ok: true },
      pastReceived: refused,
      gaps: 0,
    }).verdict,
    PASS,
  );
  assert.equal(
    everyByteVerdict({
      received: 9,
      atReceived: { ok: true },
      pastReceived: refused,
      gaps: 2,
    }).verdict,
    FAIL,
  );
  assert.equal(
    everyByteVerdict({
      received: 9,
      atReceived: refused,
      pastReceived: refused,
      gaps: 0,
    }).verdict,
    FAIL,
  );
  assert.equal(
    refusalVerdict({
      outcomes: [{ settled: "rejected" }],
      effect: null,
      refusals: 1,
    }).detail,
    "refused by the host (1 refusal record(s))",
  );
  assert.equal(
    refusalVerdict({
      outcomes: [{ settled: "absent" }],
      effect: null,
      refusals: 0,
    }).detail,
    "the surface is absent in the frame",
  );
  assert.equal(
    refusalVerdict({
      outcomes: [{ settled: "timeout" }],
      effect: "the clipboard changed",
      refusals: 0,
    }).verdict,
    FAIL,
  );
  assert.equal(
    closeVerdict({ exitCode: 0, exitMs: 900, survivors: [] }).verdict,
    PASS,
  );
  assert.equal(
    closeVerdict({ exitCode: 0, exitMs: 10001, survivors: [] }).verdict,
    FAIL,
  );
  assert.equal(
    closeVerdict({ exitCode: null, exitMs: null, survivors: [] }).verdict,
    FAIL,
  );
  assert.equal(
    closeVerdict({
      exitCode: 0,
      exitMs: 10,
      survivors: [{ pid: 4, name: "python.exe" }],
    }).verdict,
    FAIL,
  );
  assert.equal(terminalVerdict(">>> ", [">>>"], "prompt").verdict, PASS);
  assert.equal(terminalVerdict("PS C:\\> ", [">>>"], "prompt").verdict, FAIL);
  assert.equal(terminalVerdict(null, [">>>"], "prompt").verdict, FAIL);
  const windows = {
    markers: {},
    urls: {},
    navigations: 0,
    beforeprint: 0,
    zoom: "1",
    targets: 1,
  };
  assert.equal(
    noEffectVerdict(
      { ...windows, windows: [{ hwnd: 1 }] },
      {
        ...windows,
        windows: [
          { hwnd: 1 },
          { hwnd: 2, class: "Chrome_WidgetWin_2", title: "", pid: 9 },
        ],
      },
    ).verdict,
    FAIL,
  );
  assert.equal(
    noEffectVerdict(
      { ...windows, windows: [] },
      { ...windows, windows: [], targets: 2 },
    ).verdict,
    FAIL,
  );
  assert.equal(
    noEffectVerdict(
      { ...windows, windows: [] },
      { ...windows, windows: [], zoom: "1.1" },
    ).verdict,
    FAIL,
  );
});

test("process bookkeeping follows the tree and ignores reused process ids", () => {
  const list = [
    { pid: 10, ppid: 1, created: "a" },
    { pid: 11, ppid: 10, created: "b" },
    { pid: 12, ppid: 11, created: "c" },
    { pid: 13, ppid: 99, created: "d" },
  ];
  assert.deepEqual(
    descendants(list, 10).map((p) => p.pid),
    [11, 12],
  );
  const now = [
    { pid: 11, created: "b" },
    { pid: 12, created: "reused" },
  ];
  assert.deepEqual(
    survivors(descendants(list, 10), now).map((p) => p.pid),
    [11],
  );
});

test(
  "the desktop input helper withholds keys and clicks unless the target owns the foreground",
  { skip: process.platform !== "win32" && "Windows only" },
  async () => {
    const input = new DesktopInput();
    try {
      const session = await input.session();
      assert.equal(typeof session.sessionId, "number");
      assert.deepEqual(await input.windows([process.pid]), []);
      await assert.rejects(input.chord(process.pid, "f5"), /input withheld/);
      await assert.rejects(
        input.click(process.pid, 1, 1, true),
        /input withheld/,
      );
      await assert.rejects(
        input.chord(process.pid, "unknown-key"),
        /input withheld|unknown key/,
      );
    } finally {
      input.close();
    }
  },
);
