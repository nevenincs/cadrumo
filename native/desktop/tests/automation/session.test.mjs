import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { test } from "node:test";
import {
  mkdtempSync,
  mkdirSync,
  symlinkSync,
  rmSync,
  writeFileSync,
  readFileSync,
  readdirSync,
  statSync,
  unlinkSync,
} from "node:fs";
import { resolve } from "node:path";
import { buildPath } from "../../scripts/build-paths.mjs";
import {
  hostEnvironment,
  waitForWebDriver,
  within,
  queuePickerSelection,
  prepareResume,
} from "./session.mjs";

test("readiness reports a signal exit that happened before subscription", async () => {
  const child = spawn(process.execPath, [
    "-e",
    "process.kill(process.pid, 'SIGKILL')",
  ]);
  await once(child, "exit");
  await assert.rejects(
    waitForWebDriver(child, 1, "/synthetic/run"),
    process.platform === "win32"
      ? /exit_code=1; inspect \/synthetic\/run/
      : /exit_signal=SIGKILL; inspect \/synthetic\/run/,
  );
});

test("readiness interrupts a pending request on signal exit", async () => {
  const child = spawn(process.execPath, ["-e", "setInterval(() => {}, 1000)"]);
  const ready = waitForWebDriver(child, 1, "/synthetic/run", {
    fetchStatus: () => new Promise(() => {}),
  });
  child.kill("SIGKILL");
  await assert.rejects(ready, /exit_signal=SIGKILL; inspect \/synthetic\/run/);
});

test("readiness reports a launch failure without exposing the executable", async () => {
  const child = spawn("/missing/secret-executable");
  await assert.rejects(
    waitForWebDriver(child, 1, "/synthetic/run"),
    (error) =>
      /launch_failed; inspect \/synthetic\/run/.test(error.message) &&
      !error.message.includes("secret-executable"),
  );
});

test("readiness promptly reports a numeric exit while a request is pending", async () => {
  const child = spawn(process.execPath, ["-e", "process.exit(23)"]);
  await assert.rejects(
    waitForWebDriver(child, 1, "/synthetic/run", {
      fetchStatus: () => new Promise(() => {}),
    }),
    /exit_code=23; inspect \/synthetic\/run/,
  );
});

test("readiness succeeds when the listener responds", async () => {
  const child = spawn(process.execPath, ["-e", "setInterval(() => {}, 1000)"]);
  try {
    await waitForWebDriver(child, 1, "/synthetic/run", {
      fetchStatus: async () => ({ ok: true }),
    });
    assert.equal(child.exitCode, null);
  } finally {
    child.kill();
    await once(child, "exit");
  }
});

test("readiness timeout reports only bounded status and run path", async () => {
  const child = spawn(process.execPath, ["-e", "setInterval(() => {}, 1000)"]);
  try {
    await assert.rejects(
      waitForWebDriver(child, 1, "/synthetic/run", {
        attempts: 1,
        interval: 0,
        fetchStatus: async () => {
          throw new Error("secret");
        },
      }),
      (error) =>
        /child=running readiness=connection_failed; inspect \/synthetic\/run/.test(
          error.message,
        ) && !error.message.includes("secret"),
    );
  } finally {
    child.kill();
    await once(child, "exit");
  }
});

test("native exploration gets isolated storage and no inherited runtime authority", () => {
  const env = hostEnvironment(
    {
      PATH: "/tools",
      CADRUMO_STORAGE_ROOT: "/real",
      CADRUMO_PROFILE: "real",
      WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS: "override",
      TAURI_WEBDRIVER_PORT: "1",
      HTTP_PROXY: "remote",
    },
    "/synthetic/run",
    "/test/package",
    4445,
  );
  assert.equal(env.CADRUMO_STORAGE_ROOT, resolve("/synthetic/run", "storage"));
  assert.equal(env.CADRUMO_DESKTOP_PACKAGE_ROOT, "/test/package");
  assert.equal(env.TAURI_WEBDRIVER_PORT, "4445");
  assert.equal(env.CADRUMO_PROFILE, undefined);
  assert.equal(env.WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS, undefined);
  assert.equal(env.HTTP_PROXY, undefined);
  assert.equal(env.PATH, "/tools");
});

test("session files cannot escape their run root through traversal or symlinks", () => {
  const root = mkdtempSync(
    resolve(buildPath("desktop_testing"), "automation-paths-"),
  );
  try {
    const runs = resolve(root, "runs");
    mkdirSync(runs);
    const inside = resolve(runs, "session.json");
    writeFileSync(inside, "{}");
    const outside = resolve(root, "outside.json");
    writeFileSync(outside, "{}");
    symlinkSync(outside, resolve(runs, "linked.json"));
    assert.equal(within(runs, inside), inside);
    assert.throws(() => within(runs, outside), /inside/);
    assert.throws(() => within(runs, resolve(runs, "linked.json")), /inside/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

function pickerRun() {
  const root = mkdtempSync(
    resolve(buildPath("desktop_testing"), "picker-queue-"),
  );
  const run = resolve(root, "run");
  for (const name of ["temporary", "fixtures", "exports"])
    mkdirSync(resolve(run, name), { recursive: true });
  return {
    root,
    run,
    queue: resolve(run, "temporary/native-picker-selection.json"),
  };
}

test("picker open queues a confined file once with private mode and no temporary leftovers", () => {
  const { root, run, queue } = pickerRun();
  try {
    const file = resolve(run, "fixtures", "document.txt");
    writeFileSync(file, "synthetic");
    assert.deepEqual(queuePickerSelection(run, "open", file), {
      kind: "open",
      selected: "document.txt",
    });
    assert.deepEqual(JSON.parse(readFileSync(queue, "utf8")), {
      kind: "open",
      path: file,
    });
    // Windows reports emulated mode bits; they do not represent its ACLs.
    if (process.platform !== "win32")
      assert.equal(statSync(queue).mode & 0o777, 0o600);
    assert.deepEqual(readdirSync(resolve(run, "temporary")), [
      "native-picker-selection.json",
    ]);
    assert.throws(
      () => queuePickerSelection(run, "open", file),
      /pending answer/,
    );
    assert.deepEqual(JSON.parse(readFileSync(queue, "utf8")), {
      kind: "open",
      path: file,
    });
    assert.deepEqual(readdirSync(resolve(run, "temporary")), [
      "native-picker-selection.json",
    ]);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("picker confinement rejects outside files, escaping links and existing save destinations", () => {
  const { root, run, queue } = pickerRun();
  try {
    const outside = resolve(root, "outside.txt");
    writeFileSync(outside, "synthetic");
    const fixtureLink = resolve(run, "fixtures", "outside-link");
    symlinkSync(outside, fixtureLink);
    const exportLink = resolve(run, "exports", "outside-dir");
    symlinkSync(root, exportLink);
    const existing = resolve(run, "exports", "exists.txt");
    writeFileSync(existing, "keep");
    const dangling = resolve(run, "exports", "dangling.txt");
    symlinkSync(resolve(root, "absent"), dangling);
    for (const [kind, path] of [
      ["open", outside],
      ["open", fixtureLink],
      ["open", "relative.txt"],
      ["save", existing],
      ["save", dangling],
      ["save", resolve(exportLink, "escape.txt")],
      ["save", resolve(root, "outside-export.txt")],
    ])
      assert.throws(
        () => queuePickerSelection(run, kind, path),
        /invalid path/,
      );
    assert.deepEqual(readdirSync(resolve(run, "temporary")), []);
    assert.equal(readFileSync(existing, "utf8"), "keep");
    const destination = resolve(run, "exports", "result.pdf");
    assert.deepEqual(queuePickerSelection(run, "save", destination), {
      kind: "save",
      selected: "result.pdf",
    });
    assert.deepEqual(JSON.parse(readFileSync(queue, "utf8")), {
      kind: "save",
      path: destination,
    });
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("picker cancellation is queued explicitly for either kind without replacing a pending answer", () => {
  const { root, run, queue } = pickerRun();
  try {
    for (const kind of ["open", "save"]) {
      assert.deepEqual(queuePickerSelection(run, kind, null), {
        kind,
        selected: null,
      });
      assert.deepEqual(JSON.parse(readFileSync(queue, "utf8")), {
        kind,
        path: null,
      });
      assert.throws(
        () => queuePickerSelection(run, kind, null),
        /pending answer/,
      );
      unlinkSync(queue);
    }
    assert.deepEqual(readdirSync(resolve(run, "temporary")), []);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("resume discards only a stale picker answer after the former host has exited", () => {
  const { root, run, queue } = pickerRun();
  try {
    const previous = { run, pid: 123, executable: "/synthetic/host" };
    const fixture = resolve(run, "fixtures", "keep.txt");
    writeFileSync(fixture, "keep");
    queuePickerSelection(run, "open", fixture);
    assert.throws(
      () =>
        prepareResume(previous, () => ({
          status: 0,
          stdout: "/synthetic/host --gui\n",
          stderr: "",
        })),
      /Stop this session/,
    );
    assert.throws(
      () =>
        prepareResume(previous, () => ({
          status: 2,
          stdout: "",
          stderr: "lookup failed",
        })),
      /Cannot confirm/,
    );
    assert.equal(JSON.parse(readFileSync(queue, "utf8")).kind, "open");
    prepareResume(previous, () => ({ status: 1, stdout: "", stderr: "" }));
    assert.deepEqual(readdirSync(resolve(run, "temporary")), []);
    assert.equal(readFileSync(fixture, "utf8"), "keep");
    prepareResume(previous, () => ({
      status: 0,
      stdout: "/other/process\n",
      stderr: "",
    }));
    symlinkSync(fixture, queue);
    assert.throws(
      () =>
        prepareResume(previous, () => ({ status: 1, stdout: "", stderr: "" })),
      /Invalid pending/,
    );
    assert.equal(readFileSync(fixture, "utf8"), "keep");
    unlinkSync(queue);
    mkdirSync(queue);
    writeFileSync(resolve(queue, "keep"), "keep");
    assert.throws(
      () =>
        prepareResume(previous, () => ({ status: 1, stdout: "", stderr: "" })),
      /Invalid pending/,
    );
    assert.equal(readFileSync(resolve(queue, "keep"), "utf8"), "keep");
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
