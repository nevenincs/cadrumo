// Real CLI/runtime fixture and WebView2 sign-in assertions. No host response is mocked.
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { resolve } from "node:path";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";

import { waitFor, sleep } from "./session.mjs";
import { PASS } from "./verdicts.mjs";

/** Retain typed failure identifiers only, never arbitrary diagnostic payloads. */
export function canonicalFailure(stderr, secrets = []) {
  if (typeof stderr !== "string" || stderr.length > 65536) return {};
  let envelope;
  try {
    envelope = JSON.parse(stderr);
  } catch {
    return {};
  }
  const identifiers = {
    schema: [envelope?.schema_version, /^[0-9]{1,3}$/],
    command: [envelope?.command, /^[a-z][a-z0-9_.-]{0,79}$/],
    code: [envelope?.error?.code, /^[A-Z][A-Z0-9_]{0,79}$/],
    reason: [envelope?.error?.context?.reason, /^[A-Z][A-Z0-9_]{0,79}$/],
  };
  return Object.fromEntries(
    Object.entries(identifiers)
      .filter(
        ([, [value, pattern]]) =>
          typeof value === "string" &&
          pattern.test(value) &&
          !secrets.some((secret) => value.includes(secret)),
      )
      .map(([key, [value]]) => [key, value]),
  );
}

export class SignInFixture {
  constructor({ config, env, contract, results }) {
    this.config = config;
    this.env = env;
    this.results = results;
    this.secret = `Desktop-acceptance-${randomBytes(24).toString("base64url")}!`;
    this.wrong = `Rejected-${randomBytes(24).toString("base64url")}!`;
    results.secret(this.secret);
    results.secret(this.wrong);
    const layout = contract.layout;
    for (const name of ["aeat", "cadrumo-runtime"])
      assert(
        Object.hasOwn(layout.entrypoints, name),
        `missing declared ${name}`,
      );
    this.cli = resolve(
      config.packageRoot,
      layout.paths.native,
      `aeat${layout.entrypoint_suffix}`,
    );
    this.runtime = resolve(
      config.packageRoot,
      layout.paths.native,
      `cadrumo-runtime${layout.entrypoint_suffix}`,
    );
    this.python = resolve(config.packageRoot, layout.paths.executable);
    this.messages = [];
    this.stderr = "";
    this.cliSamples = 0;
    this.argvLeak = false;
    this.created = false;
  }

  cliCall(args, input, revealIdentifiers = false, timeout = 120000) {
    const payload =
      input === undefined ? undefined : Buffer.from(JSON.stringify(input));
    let result;
    try {
      result = spawnSync(this.cli, ["--format", "json", ...args], {
        cwd: this.config.run,
        env: revealIdentifiers
          ? { ...this.env, CADRUMO_CLI_REVEAL_IDENTIFIERS: "true" }
          : this.env,
        input: payload,
        encoding: "utf8",
        timeout,
        maxBuffer: 1024 * 1024,
        windowsHide: true,
      });
    } finally {
      payload?.fill(0);
    }
    // Preserve only bounded, syntax-checked canonical identifiers on failure.
    const failure =
      result.status === 0
        ? {}
        : canonicalFailure(result.stderr, [this.secret, this.wrong]);
    assert.equal(
      result.status,
      0,
      `canonical CLI ${args.slice(0, 3).join(" ")} failed (exit ${result.status}; identifiers ${JSON.stringify(failure)})`,
    );
    const envelope = JSON.parse(result.stdout);
    assert.equal(envelope.schema_version, "2");
    assert(["success", "warning"].includes(envelope.status));
    return envelope;
  }

  async start() {
    const setupStarted = performance.now();
    const created = this.cliCall(
      [
        "config",
        "profile",
        "create",
        "Desktop Acceptance",
        "--quiet",
        "--secrets-stdin",
      ],
      {
        passphrase: this.secret,
        passphrase_confirmation: this.secret,
      },
      false,
      300000, // Cold profile enrollment includes calibration and initial storage.
    );
    const profileCreateSeconds = (performance.now() - setupStarted) / 1000;
    assert.equal(created.command, "config.profile.create");
    this.created = true;
    const script = fileURLToPath(
      new URL("./runtime_fixture.py", import.meta.url),
    );
    this.child = spawn(this.python, ["-I", script, this.runtime], {
      cwd: this.config.run,
      env: this.env,
      stdio: ["pipe", "pipe", "pipe"],
      windowsHide: true,
    });
    this.exited = new Promise((done) =>
      this.child.once("close", (code) => done(code)),
    );
    this.child.on("error", () =>
      this.messages.push({ kind: "failed", errorType: "SpawnFailed" }),
    );
    createInterface({ input: this.child.stdout }).on("line", (line) => {
      try {
        this.messages.push(JSON.parse(line));
      } catch {
        this.messages.push({
          kind: "failed",
          errorType: "InvalidFixtureOutput",
        });
      }
    });
    this.child.stderr.on("data", (data) => {
      const remaining = 1024 * 1024 - this.stderr.length;
      this.stderr += data.toString().slice(0, remaining);
      if (this.stderr.length >= 1024 * 1024) this.child.stdin.end();
    });
    const deadline = Date.now() + 120000;
    while (!this.messages.some((m) => m.kind === "ready")) {
      const failed = this.messages.find((m) => m.kind === "failed");
      assert(!failed, `runtime fixture: ${failed?.errorType}`);
      assert(
        this.child.exitCode === null,
        "runtime fixture exited before readiness",
      );
      assert(
        Date.now() < deadline,
        "real packaged runtime handshake timed out",
      );
      await sleep(50);
    }
    const before = this.cliCall(["config", "sign-in-status"]);
    assert.equal(before.command, "config.sign-in-status");
    assert.equal(before.result.status.presence, "absent");
    return {
      verdict: PASS,
      detail:
        "canonical CLI created fresh profile; contained packaged runtime completed verified handshake",
      data: {
        profileCreateSeconds,
        setupSeconds: (performance.now() - setupStarted) / 1000,
      },
    };
  }

  async submit(session, password) {
    const before = await session.shell(
      () =>
        window.__s10.ipc.filter((row) => row.cmd === "sign_in_submit").length,
    );
    const field = session.page.locator("#profile-password");
    await field.waitFor({ state: "visible", timeout: 30000 });
    await field.fill(password);
    await session.page.locator(".sign-in button[type=submit]").click();
    const answer = await waitFor(
      () =>
        session.shell((index) => {
          const row = window.__s10.ipc.filter(
            (entry) => entry.cmd === "sign_in_submit",
          )[index];
          return row?.answer || row?.ok === false ? row : null;
        }, before),
      { timeout: 45000, what: "the canonical sign-in host answer" },
    );
    assert.equal(answer.ok, true, `sign-in host refused: ${answer.code}`);
    assert.equal(
      answer.args,
      null,
      "password body must not be recorded in IPC evidence",
    );
    return answer.answer;
  }

  async signIn(session, input, hostPid) {
    let observing = true;
    const observer = (async () => {
      while (observing) {
        for (const process of await input.processes(["aeat.exe"])) {
          if (
            process.ppid === hostPid &&
            process.commandLine?.includes("config") &&
            process.commandLine.includes("login")
          ) {
            this.cliSamples += 1;
            this.argvLeak ||= [this.secret, this.wrong].some((secret) =>
              process.commandLine.includes(secret),
            );
          }
        }
        await sleep(50);
      }
    })();
    observer.catch(() => undefined); // Retain the failure for the awaited cleanup below.
    try {
      const before = await session.call("sign_in_status");
      assert.equal(before.ok, true);
      assert.equal(before.value.state, "absent");
      assert.equal(before.value.supported, true);
      const rejected = await this.submit(session, this.wrong);
      assert.equal(rejected.kind, "refused");
      assert.equal(rejected.code, "CREDENTIAL_REJECTED");
      const count = await session.shell(
        () => window.__s10.ipc.filter((r) => r.cmd === "sign_in_submit").length,
      );
      await sleep(1500);
      assert.equal(
        await session.shell(
          () =>
            window.__s10.ipc.filter((r) => r.cmd === "sign_in_submit").length,
        ),
        count,
        "no automatic password retry",
      );
      let admitted = await this.submit(session, this.secret);
      if (admitted.kind === "refused" && admitted.code === "THROTTLED") {
        assert(
          Number.isFinite(admitted.retryAfterSeconds) &&
            admitted.retryAfterSeconds <= 120,
        );
        await sleep(admitted.retryAfterSeconds * 1000 + 500);
        // A new explicit form submission after observing the actual countdown.
        admitted = await this.submit(session, this.secret);
      }
      assert.equal(admitted.kind, "signed-in");
      const present = await waitFor(
        async () => {
          const response = await session.call("sign_in_status");
          return response.ok && response.value.state === "present"
            ? response.value
            : null;
        },
        { timeout: 30000, what: "runtime-owned shared sign-in presence" },
      );
      assert.equal(present.active_profile, "Desktop Acceptance");
      assert.equal(
        this.cliCall(["config", "sign-in-status"]).result.status.presence,
        "present",
      );
      return {
        verdict: PASS,
        detail:
          "real password form received CREDENTIAL_REJECTED, made no automatic retry, then canonical login published present sign-in",
      };
    } finally {
      observing = false;
      await observer;
    }
  }

  async signOut(session) {
    const before = this.cliCall(["config", "sign-in-status"], undefined, true);
    const profileId = this.messages.find(
      (message) => message.kind === "ready",
    )?.profileId;
    assert(
      profileId,
      "the runtime fixture must identify its exact new profile",
    );
    assert.equal(before.result.profile_id, profileId);
    assert.equal(before.result.status.presence, "present");
    const response = await session.call("sign_out");
    assert.equal(response.ok, true);
    assert.equal(response.value.remainingAccess.automationRevoked, false);
    const after = await session.call("sign_in_status");
    assert.equal(after.ok, true);
    assert.equal(after.value.state, "absent");
    assert.equal(after.value.active_profile, "Desktop Acceptance");
    const fresh = this.cliCall(["config", "sign-in-status"], undefined, true);
    assert.equal(fresh.result.profile_id, profileId);
    assert.equal(fresh.result.status.presence, "absent");
    return {
      verdict: PASS,
      detail:
        "canonical logout revoked human access; selected profile and exact ID remain; host and fresh CLI report absent; remaining automation is explicit",
      data: response.value,
    };
  }

  async isolation(session, input, projected) {
    assert(
      this.cliSamples > 0,
      "at least one live canonical login process must be observed",
    );
    assert(
      !this.argvLeak,
      "a submitted password appeared in a live CLI argument list",
    );
    const processes = await input.processes([
      "aeat.exe",
      "python.exe",
      "cadrumo-runtime.exe",
      "cadrumo.exe",
    ]);
    const diagnostics = await session.call("diagnostics_snapshot", {
      after: 0,
    });
    const traces = await session.shell(() => ({
      ipc: window.__s10.ipc,
      logs: window.__s10.logs,
      messages: window.__s10.messages,
    }));
    const docs = await session.docs(() => ({
      html: document.documentElement.outerHTML,
      state: window.__s10,
    }));
    const observations = [
      JSON.stringify(processes),
      JSON.stringify(diagnostics),
      JSON.stringify(traces),
      JSON.stringify(docs),
      this.stderr,
    ];
    for (const directory of [projected.logs, this.config.results]) {
      for (const relative of readdirSync(directory, { recursive: true })) {
        const path = resolve(directory, relative);
        if (statSync(path).isFile() && /\.(?:log|jsonl|txt|json)$/.test(path))
          observations.push(readFileSync(path, "utf8"));
      }
    }
    for (const secret of [this.secret, this.wrong]) {
      for (const observation of observations)
        assert(
          !observation.includes(secret),
          "a submitted secret leaked into process arguments, diagnostics, logs, docs or evidence",
        );
    }
    return {
      verdict: PASS,
      detail: `submitted passwords absent from ${this.cliSamples} live CLI argv observations, host diagnostics, raw log files, IPC evidence and docs DOM/state`,
    };
  }

  async stop() {
    if (!this.child)
      return {
        verdict: "INFO",
        detail: this.created
          ? "profile creation completed, but runtime helper never started; no sign-in attempt ran and no human receipt was minted"
          : "runtime fixture never started; profile creation did not report success",
      };
    this.child.stdin.end();
    const code = await Promise.race([
      this.exited,
      sleep(15000).then(() => "timeout"),
    ]);
    if (code === "timeout") this.child.kill();
    assert.equal(
      code,
      0,
      "runtime fixture must settle its contained runtime and exact-profile keychain teardown",
    );
    assert(this.messages.some((m) => m.kind === "stopped"));
    return {
      verdict: PASS,
      detail:
        "runtime process scope terminated and exact-profile keychain cleanup completed",
    };
  }
}
