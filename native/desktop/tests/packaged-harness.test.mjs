// Tests the packaged run's own frame handling and assertion logic in a plain
// Chromium against stand-in pages, so each check is shown to report both a
// passing and a failing window. It needs no WebView2 and no desktop session.
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { performance } from "node:perf_hooks";
import { after, describe, test } from "node:test";

import { docsProbe, instrument, pasteInto } from "./packaged/browser.mjs";
import {
  OBSERVATION_LIMITS,
  ObservationError,
} from "./packaged/terminal-observer.mjs";
import { docsUiChecks } from "./packaged/docs-ui.mjs";
import {
  DesktopInput,
  desktopInputEnvironment,
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
import { canonicalFailure, SignInFixture } from "./packaged/sign-in.mjs";
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
  tokenVerdict,
} from "./packaged/verdicts.mjs";

const cleanups = [];

test("failed docs search closes its palette and preserves the original failure", async () => {
  for (const refuseCleanup of [false, true]) {
    const original = new Error("original documentation search failure");
    const calls = [];
    let visible = false;
    const rail = {
      first: () => rail,
      locator: () => rail,
      nth: () => ({ click: async () => (visible = true) }),
    };
    const palette = {
      isVisible: async () => visible,
      waitFor: async (options) => {
        calls.push(options);
        if (refuseCleanup) throw new Error("palette cleanup refused");
        assert.equal(visible, false);
      },
    };
    await docsUiChecks({
      session: {
        page: {
          locator: (selector) => (selector === ".palette" ? palette : rail),
          keyboard: {
            press: async (key) => {
              calls.push(key);
              visible = false;
            },
          },
        },
        shell: async () => {
          throw original;
        },
      },
      check: async (id, _title, run) => {
        if (id === "palette-docs-navigation") {
          let error;
          try {
            await run();
          } catch (failed) {
            error = failed;
          }
          assert.equal(error, original);
        } else {
          assert.equal(visible, false, `${id} must not inherit the palette`);
        }
      },
      visit: async () => {},
      shown: "http://localhost/index.html",
    });
    assert.deepEqual(calls, ["Escape", { state: "hidden", timeout: 5000 }]);
  }
});

test("desktop input environment removes compiler search paths without changing its parent", () => {
  const inherited = Object.freeze({
    LIB: "missing-native-library",
    LiB: "another-native-library",
    lib: "lowercase-native-library",
    LIBPATH: "missing-managed-library",
    lIbPaTh: "another-managed-library",
    PATH: "os-command-path",
    SystemRoot: "os-root",
    TEMP: "os-temp",
    LIBRARY: "unrelated-value",
  });
  assert.deepEqual(desktopInputEnvironment(inherited), {
    PATH: "os-command-path",
    SystemRoot: "os-root",
    TEMP: "os-temp",
    LIBRARY: "unrelated-value",
  });
  assert.equal(inherited.LIB, "missing-native-library");
  assert.equal(inherited.lIbPaTh, "another-managed-library");
});

test(
  "console target comparison normalizes both absolute paths and preserves the exact target",
  { skip: process.platform !== "win32" && "Windows only" },
  async (t) => {
    const cases = [
      {
        actual: "C:/package-fixture/app\\bin\\cadrumo-runtime.exe",
        expected: "c:\\PACKAGE-FIXTURE\\app/bin/cadrumo-runtime.exe",
        equal: true,
      },
      {
        actual: "C:/package-fixture/app/bin/cadrumo-runtime.exe",
        expected: "C:\\package-fixture\\app\\bin\\cadrumo-runtime.exe",
        equal: true,
      },
      {
        actual: "C:/other-fixture/app\\bin\\cadrumo-runtime.exe",
        expected: "C:\\package-fixture\\app\\bin\\cadrumo-runtime.exe",
        equal: false,
      },
      {
        actual: "",
        expected: "C:/package-fixture/app/bin/cadrumo-runtime.exe",
        equal: false,
      },
      {
        actual: "C:/package-fixture/app/bin/cadrumo-runtime.exe",
        expected: "",
        equal: false,
      },
      {
        actual: "bin/cadrumo-runtime.exe",
        expected: "C:/package-fixture/app/bin/cadrumo-runtime.exe",
        equal: false,
      },
      {
        actual: "C:/package-fixture/app/bin/cadrumo-runtime.exe",
        expected: "bin/cadrumo-runtime.exe",
        equal: false,
      },
    ];
    const encoded = JSON.stringify(cases).replaceAll("'", "''");
    const script = `
      $cases = '${encoded}' | ConvertFrom-Json
      foreach ($case in $cases) {
        $actual = [string]$case.actual
        $expected = [string]$case.expected
        $equal = ($actual -and $expected -and [IO.Path]::IsPathRooted($actual) -and [IO.Path]::IsPathRooted($expected) -and ([IO.Path]::GetFullPath($actual) -eq [IO.Path]::GetFullPath($expected)))
        if ($equal -ne $case.equal) { throw "path comparison mismatch" }
      }
      "path-comparison-cases-passed"
    `;
    const started = performance.now();
    const result = spawnSync(
      "powershell.exe",
      ["-NoProfile", "-NonInteractive", "-Command", script],
      {
        windowsHide: true,
        env: desktopInputEnvironment(),
        encoding: "utf8",
        timeout: 10000,
      },
    );
    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stdout.trim(), "path-comparison-cases-passed");
    t.diagnostic(
      JSON.stringify({
        fixture: "console-path-normalization",
        cases: cases.length,
        elapsedMs: performance.now() - started,
      }),
    );
  },
);

test(
  "desktop input helper starts with invalid inherited compiler search paths",
  { skip: process.platform !== "win32" && "Windows only" },
  async () => {
    const helper = new URL("./packaged/os.mjs", import.meta.url).href;
    const script = `
      import assert from "node:assert/strict";
      import { DesktopInput } from ${JSON.stringify(helper)};
      const before = { ...process.env };
      const input = new DesktopInput();
      try {
        const session = await input.session();
        assert.equal(typeof session.sessionId, "number");
        assert.deepEqual({ ...process.env }, before);
      } finally {
        input.close();
      }
    `;
    const child = spawn(
      process.execPath,
      ["--input-type=module", "-e", script],
      {
        stdio: ["ignore", "pipe", "pipe"],
        windowsHide: true,
        env: {
          ...desktopInputEnvironment(),
          LiB: join(tmpdir(), "cadrumo-missing-native-library"),
          lIbPaTh: join(tmpdir(), "cadrumo-missing-managed-library"),
        },
      },
    );
    let stderr = "";
    child.stderr.on("data", (data) => (stderr += data));
    const code = await new Promise((resolve, reject) => {
      child.on("error", reject);
      child.on("exit", resolve);
    });
    assert.equal(code, 0, stderr);
  },
);

function signInControlFixture() {
  const calls = [];
  const profileId = "c12751fa-6b64-4848-b8ab-914f2560f325";
  const fixture = new SignInFixture({
    config: { packageRoot: tmpdir(), run: tmpdir() },
    env: {},
    contract: {
      layout: {
        entrypoints: { aeat: {}, "cadrumo-runtime": {} },
        paths: { native: "bin", executable: "python.exe" },
        entrypoint_suffix: ".exe",
      },
    },
    results: { secret() {} },
  });
  fixture.child = {
    exitCode: null,
    stdin: {
      write(command, done) {
        calls.push(command.trim());
        assert.equal(command, "profile-created\n");
        fixture.messages.push({ kind: "profile-ready", profileId });
        done();
      },
      end() {
        fixture.messages.push({
          kind: fixture.created ? "profile-cleaned" : "setup-incomplete",
          ...(fixture.created ? { profileId } : {}),
        });
        fixture.messages.push({ kind: "stopped" });
      },
    },
  };
  fixture.startRuntime = async () => fixture.waitMessage("ready");
  fixture.exited = Promise.resolve(0);
  fixture.cliCall = (args) => {
    calls.push(args.join(" "));
    return args[1] === "profile"
      ? { command: "config.profile.create" }
      : {
          command: "config.sign-in-status",
          result: { status: { presence: "absent" } },
        };
  };
  return { fixture, calls, profileId };
}

test("profile creation waits for a verified runtime and binds its exact profile", async () => {
  const { fixture, calls, profileId } = signInControlFixture();
  const starting = fixture.start();
  await sleep(20);
  assert.deepEqual(calls, [], "no CLI mutation before runtime readiness");
  fixture.messages.push({ kind: "ready" });
  const result = await starting;
  assert.equal(result.verdict, PASS);
  assert.deepEqual(calls, [
    "config profile create Desktop Acceptance --quiet --secrets-stdin",
    "profile-created",
    "config sign-in-status",
  ]);
  assert.equal(
    fixture.messages.find((message) => message.kind === "profile-ready")
      .profileId,
    profileId,
  );
});

test("failed runtime readiness prevents profile creation", async () => {
  const { fixture, calls } = signInControlFixture();
  fixture.messages.push({ kind: "failed", errorType: "RuntimeError" });
  await assert.rejects(fixture.start(), /runtime fixture: RuntimeError/);
  assert.deepEqual(calls, []);
  assert.equal(fixture.created, false);
});

test("failed profile enrollment still settles the runtime without a selected profile", async () => {
  const { fixture } = signInControlFixture();
  fixture.messages.push({ kind: "ready" });
  fixture.cliCall = () => {
    throw new Error("canonical create refused");
  };
  await assert.rejects(fixture.start(), /canonical create refused/);
  const result = await fixture.stop();
  assert.equal(result.verdict, PASS);
  assert.match(result.detail, /failed enrollment left no selected profile/);
});

test("successful profile enrollment requires exact-profile cleanup", async () => {
  const { fixture } = signInControlFixture();
  fixture.messages.push({ kind: "ready" });
  await fixture.start();
  fixture.child.stdin.end = () => {
    fixture.messages.push({ kind: "setup-incomplete" }, { kind: "stopped" });
  };
  await assert.rejects(fixture.stop(), /the new profile must be cleaned/);
});

test("refused profile binding reports a typed failure and preserves runtime cleanup", async () => {
  const { fixture } = signInControlFixture();
  fixture.messages.push({ kind: "ready" });
  fixture.child.stdin.write = (_command, done) => {
    done(new Error("untrusted diagnostic SECRET_TOKEN"));
  };
  await assert.rejects(fixture.start(), {
    message: "runtime fixture: FixtureControlWriteFailed",
  });
  assert.deepEqual(fixture.messages.at(-1), {
    kind: "failed",
    errorType: "FixtureControlWriteFailed",
  });
  assert.equal((await fixture.stop()).verdict, PASS);
});

test("already closed runtime input is not ended again during cleanup", async () => {
  const { fixture } = signInControlFixture();
  fixture.child.stdin.destroyed = true;
  fixture.child.stdin.end = () =>
    assert.fail("closed control stream ended again");
  fixture.messages.push({ kind: "setup-incomplete" }, { kind: "stopped" });
  assert.equal((await fixture.stop()).verdict, PASS);
});

test("completed runtime teardown releases its deadline timer", async (t) => {
  const { fixture } = signInControlFixture();
  const scheduled = [];
  const cleared = [];
  t.mock.method(globalThis, "setTimeout", (_work, delay) => {
    const token = { delay };
    scheduled.push(token);
    return token;
  });
  t.mock.method(globalThis, "clearTimeout", (token) => cleared.push(token));
  assert.equal((await fixture.stop()).verdict, PASS);
  assert.deepEqual(scheduled, [{ delay: 15000 }]);
  assert.deepEqual(cleared, scheduled);
});

test("profile binding rejects noncanonical identifiers", async () => {
  const { fixture } = signInControlFixture();
  fixture.messages.push({ kind: "ready" });
  fixture.child.stdin.write = (_command, done) => {
    fixture.messages.push({ kind: "profile-ready", profileId: "untrusted-id" });
    done();
  };
  await assert.rejects(fixture.start(), /bind its exact new profile/);
});

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
  assert.deepEqual(
    canonicalFailure(
      JSON.stringify({ error: { context: { reason: "runtime_unavailable" } } }),
    ),
    { reason: "runtime_unavailable" },
  );
});

test("sign-in phase timings retain monotonic boundaries and a closed lifecycle summary", async (t) => {
  let clock = 0;
  t.mock.method(performance, "now", () => clock);
  const { fixture, profileId } = signInControlFixture();
  const originAt = fixture.timingStats().originAt;
  assert.match(originAt, /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/);
  const artifacts = [];
  fixture.results.evidence = (name, value) => {
    assert.equal(name, "sign-in-phase-timings.json");
    artifacts.push(value);
  };
  fixture.startRuntime = async () => {
    clock += 25;
    fixture.messages.push({
      kind: "ready",
      storageIdentity: "private-storage",
      owner: "private-owner",
    });
  };
  const cli = fixture.cliCall;
  fixture.cliCall = (...args) => {
    clock += args[0][1] === "profile" ? 40 : 5;
    return cli(...args);
  };
  const write = fixture.child.stdin.write;
  fixture.child.stdin.write = (...args) => {
    clock += 10;
    return write(...args);
  };
  const end = fixture.child.stdin.end;
  fixture.child.stdin.end = () => {
    clock += 3;
    return end();
  };
  await fixture.start();
  fixture.messages.push({
    kind: "runtime-exited-before-cleanup",
    exitCode: 1074,
    pid: 123,
    profileId,
    rawstderr: fixture.secret,
  });
  await fixture.stop();
  assert.equal(fixture.timingStats().originAt, originAt);
  assert.deepEqual(fixture.timingStats().phases, [
    {
      phase: "runtime-readiness",
      outcome: "success",
      startedMs: 0,
      elapsedMs: 25,
    },
    {
      phase: "profile-create",
      outcome: "success",
      startedMs: 25,
      elapsedMs: 40,
    },
    {
      phase: "profile-binding",
      outcome: "success",
      startedMs: 65,
      elapsedMs: 10,
    },
    {
      phase: "initial-cli-status",
      outcome: "success",
      startedMs: 75,
      elapsedMs: 5,
    },
    {
      phase: "runtime-cleanup",
      outcome: "success",
      startedMs: 80,
      elapsedMs: 3,
    },
  ]);
  assert.deepEqual(artifacts.at(-1).lifecycle, {
    readySeen: true,
    profileBound: true,
    runtimeExitBeforeCleanup: 1074,
    cleanupStopped: true,
  });
  const serialized = JSON.stringify(artifacts);
  for (const forbidden of [
    fixture.secret,
    fixture.wrong,
    profileId,
    "private-storage",
    "private-owner",
    "rawstderr",
    "profileId",
    "storageIdentity",
  ])
    assert(!serialized.includes(forbidden));
});

test("sign-in timing failures preserve the original error and exact-profile cleanup evidence", async () => {
  const { fixture, profileId } = signInControlFixture();
  const original = new Error(
    `private status diagnostic ${fixture.secret} ${profileId}`,
  );
  fixture.messages.push({ kind: "ready" });
  const cli = fixture.cliCall;
  fixture.cliCall = (args) => {
    if (args[1] !== "profile") throw original;
    return cli(args);
  };
  const artifacts = [];
  fixture.results.evidence = (_name, value) => artifacts.push(value);
  await assert.rejects(fixture.start(), (error) => error === original);
  assert.equal(fixture.timingStats().phases.at(-1).outcome, "failure");
  assert.equal(fixture.timingStats().phases.at(-1).phase, "initial-cli-status");
  fixture.messages.push({
    kind: "runtime-exited-before-cleanup",
    exitCode: "untrusted",
  });
  assert.equal(fixture.timingStats().lifecycle.runtimeExitBeforeCleanup, null);
  await fixture.stop();
  assert.equal(artifacts.at(-1).lifecycle.cleanupStopped, true);
  assert.equal(artifacts.at(-1).lifecycle.profileBound, true);
  assert(!JSON.stringify(artifacts).includes(fixture.secret));
  assert(!JSON.stringify(artifacts).includes(profileId));
});

test("sign-in timing history is bounded and evidence refusal cannot change operation results", async () => {
  const { fixture } = signInControlFixture();
  fixture.results.evidence = () => {
    throw new Error("private artifact failure");
  };
  for (let index = 0; index < 18; index++)
    assert.equal(
      fixture.measure("profile-create", () => 7),
      7,
    );
  const stats = fixture.timingStats();
  assert.equal(stats.phases.length, 16);
  assert.equal(stats.dropped, 2);
  assert.equal(stats.evidenceWriteFailed, true);
  assert.throws(
    () => fixture.measure(fixture.secret, () => true),
    /unknown fixture timing phase/,
  );
  const original = new Error("private operation failure");
  await assert.rejects(
    fixture.measure("runtime-readiness", async () => {
      throw original;
    }),
    (error) => error === original,
  );
  assert.equal(fixture.timingStats().dropped, 3);
  assert(!JSON.stringify(fixture.timingStats()).includes("private"));
});

test("sign-in UI phase timings distinguish rejected, throttled and successful explicit submissions", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const { fixture } = signInControlFixture();
  const submitted = [];
  fixture.submit = async (_session, password) => {
    submitted.push(password);
    if (password === fixture.wrong)
      return {
        kind: "refused",
        code: "CREDENTIAL_REJECTED",
        privatePayload: fixture.secret,
      };
    return submitted.length === 2
      ? { kind: "refused", code: "THROTTLED", retryAfterSeconds: 0 }
      : { kind: "signed-in", privatePayload: fixture.secret };
  };
  let statuses = 0;
  const session = {
    call: async () => ({
      ok: true,
      value: statuses++
        ? { state: "present", active_profile: "Desktop Acceptance" }
        : { state: "absent", supported: true },
    }),
    shell: async () => submitted.length,
    page: {
      locator: () => ({
        waitFor: async () => {},
        innerText: async () => "Desktop Acceptance",
      }),
    },
  };
  fixture.cliCall = () => ({ result: { status: { presence: "present" } } });
  fixture.results.evidence = () => {};
  const input = { processes: async () => [] };
  const pending = fixture.signIn(session, input, 123);
  const flush = () => new Promise((resolve) => setImmediate(resolve));
  await flush();
  assert.deepEqual(submitted, [fixture.wrong]);
  t.mock.timers.tick(1500);
  await flush();
  assert.deepEqual(submitted, [fixture.wrong, fixture.secret]);
  t.mock.timers.tick(500);
  await flush();
  t.mock.timers.tick(50);
  assert.equal((await pending).verdict, PASS);
  assert.deepEqual(submitted, [fixture.wrong, fixture.secret, fixture.secret]);
  assert.deepEqual(
    fixture
      .timingStats()
      .phases.map(({ phase, outcome }) => ({ phase, outcome })),
    [
      { phase: "ui-wrong-password", outcome: "success" },
      { phase: "ui-valid-password", outcome: "failure" },
      { phase: "ui-throttle-wait", outcome: "success" },
      { phase: "ui-valid-password", outcome: "success" },
    ],
  );
  assert(!JSON.stringify(fixture.timingStats()).includes(fixture.secret));
});

test("sign-in submission retains its 75-second answer deadline and clicks only once", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout", "Date"] });
  const { fixture } = signInControlFixture();
  let reads = 0;
  let clicks = 0;
  let fills = 0;
  const session = {
    shell: async () => (reads++ === 0 ? 0 : null),
    page: {
      locator: () => ({
        waitFor: async () => {},
        fill: async () => {
          fills++;
        },
        click: async () => {
          clicks++;
        },
      }),
    },
  };
  const pending = fixture.submit(session, fixture.secret);
  const rejected = assert.rejects(
    pending,
    /Timed out after 75000 ms waiting for the canonical sign-in host answer/,
  );
  await new Promise((resolve) => setImmediate(resolve));
  t.mock.timers.tick(74900);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(clicks, 1);
  assert.equal(fills, 1);
  t.mock.timers.tick(101);
  await rejected;
  assert.equal(clicks, 1);
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
async function openWindow(variant, options = {}) {
  const standin = await startStandin({ variant, ...options });
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

test("VT observation parses while ACKs are held and keeps renderer presence separate", async (t) => {
  const { session, standin } = await openWindow("refusing", { panels: true });
  const payload = "hello\rOK\x1b[K á漢";
  standin.state.delivered = Buffer.byteLength(payload);
  await session.shell(() => window.__s10.hold());
  let pending;
  try {
    await deliver(session, [{ tag: 0, text: payload, index: 0 }]);
    pending = session.shell(
      (bytes) => window.standin.ack(bytes),
      standin.state.delivered,
    );
    await waitFor(
      () => session.observationStats().parser.bytes === standin.state.delivered,
      { what: "VT parsing during the held ACK" },
    );
    assert.equal(session.rows("python"), null);
    assert.equal((await session.terminal("python")).acked, 0);
    assert.deepEqual(await session.presentation("python"), {
      visible: false,
      renderer: null,
    });
    await session.showTab("python");
    assert.deepEqual(await session.presentation("python"), {
      visible: true,
      renderer: null,
    });
    // Synthetic DOM fixtures exercise presence only; no GPU image claim.
    await session.shell(() => {
      const canvas = document.createElement("canvas");
      document
        .querySelector('[data-terminal="python"] .xterm-screen')
        .append(canvas);
    });
    assert.deepEqual(await session.presentation("python"), {
      visible: true,
      renderer: "canvas",
    });
    await session.shell(() => {
      document.querySelector('[data-terminal="python"] canvas').remove();
      const rows = document.createElement("div");
      rows.className = "xterm-rows";
      rows.textContent = "DOM fixture text must not become the VT observation";
      document
        .querySelector('[data-terminal="python"] .xterm-screen')
        .append(rows);
    });
    assert.deepEqual(await session.presentation("python"), {
      visible: true,
      renderer: "dom",
    });
    assert.equal(session.rows("python"), null);
  } finally {
    await session.shell(() => window.__s10.release());
    await pending;
  }
  assert.match(
    await session.waitRows("python", (rows) => rows.includes("OK á漢")),
    /^OK á漢/,
  );
  const before = session.observationStats();
  assert.equal(before.parser.dataFrames, 1);
  assert(before.capture.peakBytes <= OBSERVATION_LIMITS.bytes);
  assert(before.capture.peakRecords <= OBSERVATION_LIMITS.records);
  assert(before.drainMs >= 0 && before.parseMs >= 0);
  session.stopObservation();
  await session.observationPump;
  assert.equal(session.observationStats().stopped, true);
  assert.equal(session.observationStats().parser.cells, 0);
  assert.equal(
    session.observationStats().capture.drained,
    before.capture.drained,
  );
  assert.throws(() => session.rows("python"), ObservationError);
  t.diagnostic(JSON.stringify({ fixture: "held-ACK", ...before }));
});

test("browser capture bounds bytes and records, draining an oversized frame alone", async (t) => {
  const driver = await chromium();
  const browser = await driver.launch({ headless: true });
  try {
    const page = await browser.newPage();
    await page.goto("about:blank");
    // A controlled fetch response and callback map are local to this fixture.
    // The instrument's fetch wrapper delegates here; no packaged host is used.
    await page.route("https://fixture.invalid/**", (route) =>
      route.fulfill({
        status: 200,
        headers: {
          "Tauri-Response": "ok",
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Expose-Headers": "Tauri-Response",
        },
        body: '{"session":7}',
      }),
    );
    await page.evaluate(() => {
      window.__TAURI_INTERNALS__ = {
        callbacks: new Map([
          [123, () => {}],
          [124, () => {}],
          [125, () => {}],
          [126, () => {}],
        ]),
      };
    });
    await page.evaluate(instrument, {
      shellOrigins: ["null"],
      docsOrigin: "unused",
      ipcPrefix: "https://fixture.invalid/",
      observationLimits: OBSERVATION_LIMITS,
    });
    const exercise = async (mode) =>
      page.evaluate(
        async ({ mode, bounds }) => {
          const id = { oversized: 125, bytes: 124, records: 123, order: 126 }[
            mode
          ];
          const opening = fetch("https://fixture.invalid/terminal_open", {
            method: "POST",
            body: JSON.stringify({
              kind: "python",
              cols: 80,
              rows: 24,
              frames: "__CHANNEL__:" + id,
            }),
          });
          const callback = window.__TAURI_INTERNALS__.callbacks.get(id);
          if (mode === "order") {
            callback({
              index: 0,
              message: new Uint8Array([0, 111, 107]).buffer,
            });
            window.__TAURI_INTERNALS__.callbacks.get(125)({
              index: 2,
              message: new Uint8Array([0, 120]).buffer,
            });
            await opening;
            await fetch("https://fixture.invalid/terminal_resize", {
              method: "POST",
              body: JSON.stringify({ session: 7, cols: 90, rows: 25 }),
            });
            await fetch("https://fixture.invalid/terminal_ack", {
              method: "POST",
              body: JSON.stringify({ session: 7, offset: 2 }),
            });
            return window.__s10.drainVT();
          }
          await opening;
          if (window.__s10.channelFor("python") !== id)
            throw new Error(
              "Latest generation must follow request order, not callback ID",
            );
          window.__s10.drainVT();
          if (mode === "oversized") {
            callback({
              index: 0,
              message: new Uint8Array(bounds.batchBytes + 1).buffer,
            });
            callback({ index: 1, message: new Uint8Array([0, 120]).buffer });
            const first = window.__s10.drainVT();
            const second = window.__s10.drainVT();
            return { first, second };
          }
          if (mode === "bytes") {
            callback({
              index: 0,
              message: new Uint8Array(bounds.bytes / 2).buffer,
            });
            callback({
              index: 1,
              message: new Uint8Array(bounds.bytes / 2).buffer,
            });
            callback({ index: 2, message: new Uint8Array([0]).buffer });
          } else
            for (let index = 0; index <= bounds.records; index++)
              callback({ index, message: new Uint8Array([0]).buffer });
          const drained = window.__s10.drainVT();
          // Text is unavailable after loss. Keep stress-test evidence scalar.
          return {
            ...drained,
            records: drained.records.map(({ bytes, ...record }) => ({
              ...record,
              byteLength: bytes?.length ?? 0,
            })),
          };
        },
        { mode, bounds: OBSERVATION_LIMITS },
      );
    const { first, second } = await exercise("oversized");
    assert.equal(first.records.length, 1);
    assert.equal(
      first.records[0].bytes.length,
      OBSERVATION_LIMITS.batchBytes + 1,
    );
    assert.equal(first.more, true);
    assert.equal(second.records.length, 1);
    assert.equal(second.more, false);
    for (const mode of ["bytes", "records"]) {
      const started = performance.now();
      const result = await exercise(mode);
      assert.equal(result.losses[0].code, "TerminalObservationCaptureLimit");
      assert(result.captureStats.peakBytes <= OBSERVATION_LIMITS.bytes);
      assert(result.captureStats.peakRecords <= OBSERVATION_LIMITS.records);
      assert(result.records.length <= OBSERVATION_LIMITS.batchRecords);
      if (mode === "bytes")
        assert.equal(result.captureStats.peakBytes, OBSERVATION_LIMITS.bytes);
      else
        assert.equal(
          result.captureStats.peakRecords,
          OBSERVATION_LIMITS.records,
        );
      t.diagnostic(
        JSON.stringify({
          fixture: `capture-${mode}-limit`,
          elapsedMs: performance.now() - started,
          capture: result.captureStats,
          batchRecords: result.records.length,
          losses: result.losses,
        }),
      );
    }
    const ordering = await exercise("order");
    assert.deepEqual(
      ordering.records.map((record) => record.type),
      ["open", "frame", "bind", "resize", "ack"],
    );
    assert.equal(ordering.records[1].index, 0);
    assert.equal(ordering.records[1].bytes.length, 3);
    assert.equal(ordering.losses.length, 0);
  } finally {
    await browser.close();
  }
});

test("panel navigation opens lazy panes through the localized visible rail", async () => {
  const { session } = await openWindow("refusing", { panels: true });
  const { page } = session;
  const clicks = () => session.shell(() => window.standin.panelClicks);
  assert.equal(await page.locator(".panel").isVisible(), false);
  assert.equal(await page.locator(".xterm-screen").count(), 0);

  await session.showTab("python");
  assert.equal(await page.locator("#panel-python").isVisible(), true);
  assert.equal(await page.locator("#panel-console").isVisible(), false);
  assert.equal(await page.locator("#panel-python .xterm-screen").count(), 1);
  await session.showTab("python");
  await session.focusTerminal("python");
  assert.deepEqual(await clicks(), ["python"]);
  assert.equal(await page.locator("#panel-python textarea:focus").count(), 1);

  await session.showTab("console");
  assert.equal(await page.locator("#panel-console").isVisible(), true);
  assert.equal(await page.locator("#panel-python").isVisible(), false);
  assert.equal(await page.locator("#panel-python .xterm-screen").count(), 1);

  await session.showTab("logs");
  assert.equal(await page.locator("#panel-logs").isVisible(), true);
  assert.equal(await page.locator('[data-terminal="logs"]').count(), 0);
  await session.showTab("logs");
  assert.deepEqual(await clicks(), ["python", "console", "logs"]);
  await page.locator(".rail").getByRole("button").last().click();
  assert.equal(await page.locator(".panel").isVisible(), false);
  await session.showTab("logs");
  assert.equal(await page.locator("#panel-logs").isVisible(), true);
  assert.deepEqual(await clicks(), [
    "python",
    "console",
    "logs",
    "logs",
    "logs",
  ]);
});

test("token verdict accepts only the exact documented public globals", () => {
  const observed = {
    docs: {
      surface: { shellObject: "undefined" },
      names: ["cadrumoChromeStrings", "CadrumoDocs"],
      topShell: "SecurityError",
      parentShell: "SecurityError",
      topDocument: "SecurityError",
    },
    shell: {
      getterAtStart: true,
      getterNow: false,
      valueNow: "undefined",
      authorized: true,
    },
  };
  assert.equal(tokenVerdict(observed).verdict, PASS);
  for (const name of [
    "CadrumoNewDocs",
    "cadrumoChromeStringsToken",
    "cadrumoDocs",
    "__CADRUMO_TOKEN__",
  ]) {
    const verdict = tokenVerdict({
      ...observed,
      docs: { ...observed.docs, names: [...observed.docs.names, name] },
    });
    assert.equal(verdict.verdict, FAIL, name);
    assert(verdict.detail.includes(name));
  }
  for (const [key, value] of [
    ["surface", { shellObject: "object" }],
    ["topShell", "object"],
    ["parentShell", "object"],
    ["topDocument", "object"],
  ])
    assert.equal(
      tokenVerdict({ ...observed, docs: { ...observed.docs, [key]: value } })
        .verdict,
      FAIL,
      key,
    );
  for (const [key, value] of [
    ["getterAtStart", false],
    ["getterNow", true],
    ["valueNow", "string"],
    ["authorized", false],
  ])
    assert.equal(
      tokenVerdict({ ...observed, shell: { ...observed.shell, [key]: value } })
        .verdict,
      FAIL,
      key,
    );
});

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

  test("a docs frame that reaches the token fails alongside public docs globals", async () => {
    await session.docs(() => {
      window.cadrumoChromeStrings = {};
      window.CadrumoDocs = {};
    });
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
  "desktop input post handles optional HWND under strict mode without reaching a real window",
  { skip: process.platform !== "win32" && "Windows only" },
  async (t) => {
    const started = performance.now();
    const input = new DesktopInput();
    const exited = new Promise((resolve) => input.child.once("exit", resolve));
    const impossiblePid = 2147483647;
    let defaultRefusalMs;
    let explicitRefusalMs;
    try {
      await input.session();
      let requested = performance.now();
      await assert.rejects(
        input.post(impossiblePid, "close"),
        (error) =>
          error.message ===
          `process ${impossiblePid} has no visible main window`,
      );
      defaultRefusalMs = performance.now() - requested;
      requested = performance.now();
      // A nonnumeric explicit handle proves that branch still casts the HWND;
      // the conversion fails before any native window message can be sent.
      await assert.rejects(
        input.post(impossiblePid, "close", "explicit-invalid-hwnd"),
        /Cannot convert value "explicit-invalid-hwnd".*System.Int64/,
      );
      explicitRefusalMs = performance.now() - requested;
      assert.equal(typeof (await input.session()).sessionId, "number");
    } finally {
      input.close();
      assert.equal(await exited, 0);
    }
    t.diagnostic(
      JSON.stringify({
        fixture: "desktop-input-optional-hwnd",
        elapsedMs: performance.now() - started,
        defaultRefusalMs,
        explicitRefusalMs,
        targetPid: impossiblePid,
        helperExitCode: 0,
      }),
    );
  },
);

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
