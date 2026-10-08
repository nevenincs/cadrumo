// Real CLI/runtime fixture and WebView2 sign-in assertions. No host response is mocked.
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { resolve } from "node:path";
import { performance } from "node:perf_hooks";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";

import { waitFor, sleep } from "./session.mjs";
import { PASS } from "./verdicts.mjs";

const TIMING_PHASES = new Set([
  "runtime-readiness",
  "profile-create",
  "profile-binding",
  "initial-cli-status",
  "ui-wrong-password",
  "ui-valid-password",
  "ui-throttle-wait",
  "runtime-cleanup",
]);
const TIMING_LIMIT = 16;
const SUBMISSION_LIMIT = 4;
const SUBMISSION_PHASES = new Set(["wrong-password", "valid-password"]);

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
    reason: [envelope?.error?.context?.reason, /^[A-Za-z][A-Za-z0-9_]{0,79}$/],
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
    this.profileBound = false;
    this.timingOrigin = performance.now();
    this.timingOriginAt = new Date().toISOString();
    this.phaseTimings = [];
    this.submissionTimings = [];
    this.submissionTimingsDropped = 0;
    this.timingsDropped = 0;
    this.timingEvidenceFailed = false;
  }

  /** Closed scalar facts only: fixture messages and identity never leave here. */
  timingStats() {
    const exit = this.messages.find(
      (message) => message.kind === "runtime-exited-before-cleanup",
    )?.exitCode;
    return {
      originAt: this.timingOriginAt,
      phases: this.phaseTimings.map((phase) => ({ ...phase })),
      submissions: this.submissionTimings.map((submission) => ({
        ...submission,
      })),
      submissionsDropped: this.submissionTimingsDropped,
      submissionLimit: SUBMISSION_LIMIT,
      dropped: this.timingsDropped,
      limit: TIMING_LIMIT,
      evidenceWriteFailed: this.timingEvidenceFailed,
      lifecycle: {
        readySeen: this.messages.some((message) => message.kind === "ready"),
        profileBound: this.profileBound,
        runtimeExitBeforeCleanup: Number.isSafeInteger(exit) ? exit : null,
        cleanupStopped: this.messages.some(
          (message) => message.kind === "stopped",
        ),
      },
    };
  }

  /** Evidence refusal must never replace the measured action's original result. */
  writeTimingEvidence() {
    try {
      this.results.evidence?.("sign-in-phase-timings.json", this.timingStats());
    } catch {
      this.timingEvidenceFailed = true;
    }
  }

  /** Measure an existing boundary without retaining its arguments or result. */
  measure(phase, run, successful = () => true) {
    assert(TIMING_PHASES.has(phase), "unknown fixture timing phase");
    const started = performance.now();
    let recorded = false;
    const record = (outcome) => {
      if (recorded) return;
      recorded = true;
      if (this.phaseTimings.length < TIMING_LIMIT)
        this.phaseTimings.push({
          phase,
          outcome,
          startedMs: started - this.timingOrigin,
          elapsedMs: performance.now() - started,
        });
      else
        this.timingsDropped = Math.min(
          Number.MAX_SAFE_INTEGER,
          this.timingsDropped + 1,
        );
      this.writeTimingEvidence();
    };
    const completed = (value) => {
      try {
        record(successful(value) ? "success" : "failure");
      } catch (error) {
        record("failure");
        throw error;
      }
      return value;
    };
    const failed = (error) => {
      record("failure");
      throw error;
    };
    try {
      const value = run();
      return typeof value?.then === "function"
        ? value.then(completed, failed)
        : completed(value);
    } catch (error) {
      return failed(error);
    }
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

  async startRuntime() {
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
    this.child.stdin.on("error", () =>
      this.messages.push({
        kind: "failed",
        errorType: "FixtureControlWriteFailed",
      }),
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
    await this.waitMessage("ready");
  }

  async waitMessage(kind) {
    const deadline = Date.now() + 120000;
    for (;;) {
      const failed = this.messages.find((m) => m.kind === "failed");
      assert(!failed, `runtime fixture: ${failed?.errorType}`);
      assert(
        this.child.exitCode === null,
        `runtime fixture exited before ${kind}`,
      );
      const message = this.messages.find((m) => m.kind === kind);
      if (message) return message;
      assert(Date.now() < deadline, `real packaged runtime ${kind} timed out`);
      await sleep(50);
    }
  }

  async start() {
    const setupStarted = performance.now();
    await this.measure("runtime-readiness", () => this.startRuntime());
    const profileCreateStarted = performance.now();
    this.measure("profile-create", () => {
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
      assert.equal(created.command, "config.profile.create");
      return created;
    });
    const profileCreateSeconds =
      (performance.now() - profileCreateStarted) / 1000;
    this.created = true;
    await this.measure("profile-binding", async () => {
      await new Promise((done, reject) => {
        const refused = () => {
          this.messages.push({
            kind: "failed",
            errorType: "FixtureControlWriteFailed",
          });
          reject(new Error("runtime fixture: FixtureControlWriteFailed"));
        };
        const control = this.child.stdin;
        if (
          control.destroyed ||
          control.writableEnded ||
          this.child.exitCode !== null
        ) {
          refused();
          return;
        }
        try {
          control.write("profile-created\n", (error) => {
            if (error) refused();
            else done();
          });
        } catch {
          refused();
        }
      });
      const profile = await this.waitMessage("profile-ready");
      assert(
        typeof profile.profileId === "string" &&
          /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(
            profile.profileId,
          ),
        "the runtime fixture must bind its exact new profile",
      );
      this.profileBound = true;
    });
    this.measure("initial-cli-status", () => {
      const before = this.cliCall(["config", "sign-in-status"]);
      assert.equal(before.command, "config.sign-in-status");
      assert.equal(before.result.status.presence, "absent");
    });
    return {
      verdict: PASS,
      detail:
        "contained packaged runtime completed verified handshake; canonical CLI then created fresh profile",
      data: {
        profileCreateSeconds,
        setupSeconds: (performance.now() - setupStarted) / 1000,
      },
    };
  }

  async submit(session, password, phase = "valid-password") {
    assert(SUBMISSION_PHASES.has(phase), "unknown sign-in submission phase");
    const started = performance.now();
    const formAt = Date.now();
    let observed = null;
    let outcome = "failed";
    try {
      const before = await session.shell(
        () =>
          window.__s10.ipc.filter((row) => row.cmd === "sign_in_submit").length,
      );
      const field = session.page.locator("#profile-password");
      await field.waitFor({ state: "visible", timeout: 30000 });
      await field.fill(password);
      await session.page.locator(".sign-in button[type=submit]").click();
      const answer = await waitFor(
        async () => {
          const row = await session.shell((index) => {
            const request = window.__s10.ipc.filter(
              (entry) => entry.cmd === "sign_in_submit",
            )[index];
            return request ?? null;
          }, before);
          // Cache scalar timestamps during existing polling, including pending
          // requests. Failure cleanup needs no additional browser roundtrip.
          if (row) observed = { at: row.at, ms: row.ms };
          return row?.answer || row?.ok === false ? row : null;
        },
        // One accepted submission may wait 30 s behind a read, then owns a
        // separate 30 s child deadline. This does not retry the password.
        { timeout: 75000, what: "the canonical sign-in host answer" },
      );
      if (answer.ok !== true) outcome = "host-refused";
      assert.equal(answer.ok, true, `sign-in host refused: ${answer.code}`);
      assert.equal(
        answer.args,
        null,
        "password body must not be recorded in IPC evidence",
      );
      if (answer.answer?.kind === "signed-in") outcome = "signed-in";
      else if (answer.answer?.kind === "refused") {
        if (answer.answer.code === "CREDENTIAL_REJECTED")
          outcome = "credential-rejected";
        else if (answer.answer.code === "THROTTLED") outcome = "throttled";
      }
      return answer.answer;
    } finally {
      const elapsedMs = performance.now() - started;
      const hostAt =
        Number.isSafeInteger(observed?.at) &&
        observed.at >= 0 &&
        observed.at <= 8640000000000000
          ? observed.at
          : null;
      const dispatchMs = hostAt === null ? null : hostAt - formAt;
      if (this.submissionTimings.length < SUBMISSION_LIMIT)
        this.submissionTimings.push({
          phase,
          outcome,
          startedMs: started - this.timingOrigin,
          elapsedMs,
          formStartedAt: new Date(formAt).toISOString(),
          dispatchObserved: hostAt !== null,
          hostStartedAt:
            hostAt === null ? null : new Date(hostAt).toISOString(),
          hostElapsedMs:
            Number.isFinite(observed?.ms) &&
            observed.ms >= 0 &&
            observed.ms <= Number.MAX_SAFE_INTEGER
              ? observed.ms
              : null,
          // Both timestamps use same-machine UTC Date.now. This includes form
          // filling/clicking; browser and Node performance clocks are not mixed.
          formToDispatchUtcMs:
            dispatchMs !== null &&
            dispatchMs >= 0 &&
            dispatchMs <= elapsedMs + 1000
              ? dispatchMs
              : null,
        });
      else
        this.submissionTimingsDropped = Math.min(
          Number.MAX_SAFE_INTEGER,
          this.submissionTimingsDropped + 1,
        );
      this.writeTimingEvidence();
    }
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
      this.results.evidence("sign-in-initial-status.json", before);
      assert.equal(
        before.ok,
        true,
        `initial host sign-in status failed: ${before.error?.code ?? "unknown"}`,
      );
      assert.equal(
        before.value.state,
        "absent",
        "initial sign-in status must be absent",
      );
      assert.equal(
        before.value.supported,
        true,
        "native sign-in support must be available",
      );
      // The form says, under a label of its own, which profile the
      // password is for.
      const named = session.page.locator(".sign-in .profile-named");
      await named.waitFor({ state: "visible", timeout: 30000 });
      assert.match(await named.innerText(), /Desktop Acceptance/);
      const rejected = await this.measure(
        "ui-wrong-password",
        () => this.submit(session, this.wrong, "wrong-password"),
        (answer) =>
          answer.kind === "refused" && answer.code === "CREDENTIAL_REJECTED",
      );
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
      const admit = () =>
        this.measure(
          "ui-valid-password",
          () => this.submit(session, this.secret),
          (answer) => answer.kind === "signed-in",
        );
      let admitted = await admit();
      if (admitted.kind === "refused" && admitted.code === "THROTTLED") {
        assert(
          Number.isFinite(admitted.retryAfterSeconds) &&
            admitted.retryAfterSeconds <= 120,
        );
        await this.measure("ui-throttle-wait", () =>
          sleep(admitted.retryAfterSeconds * 1000 + 500),
        );
        // A new explicit form submission after observing the actual countdown.
        admitted = await admit();
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
      (message) => message.kind === "profile-ready",
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
    return this.measure("runtime-cleanup", async () => {
      if (!this.child)
        return {
          verdict: "INFO",
          detail:
            "runtime fixture never started; no profile creation was attempted",
        };
      if (!this.child.stdin.destroyed && !this.child.stdin.writableEnded)
        this.child.stdin.end();
      let deadline;
      let code;
      try {
        code = await Promise.race([
          this.exited,
          new Promise((done) => {
            deadline = setTimeout(() => done("timeout"), 15000);
          }),
        ]);
      } finally {
        clearTimeout(deadline);
      }
      if (code === "timeout") this.child.kill();
      assert.equal(
        code,
        0,
        "runtime fixture must settle its contained runtime and exact-profile keychain teardown",
      );
      assert(this.messages.some((m) => m.kind === "stopped"));
      const cleaned = this.messages.some((m) => m.kind === "profile-cleaned");
      assert(
        cleaned ||
          (!this.created &&
            this.messages.some((m) => m.kind === "setup-incomplete")),
        "the new profile must be cleaned, or failed enrollment must leave no selected profile",
      );
      return {
        verdict: PASS,
        detail: cleaned
          ? "runtime process scope terminated; exact-profile receipt absence verified after cleanup"
          : "runtime process scope terminated; failed enrollment left no selected profile",
      };
    });
  }
}
