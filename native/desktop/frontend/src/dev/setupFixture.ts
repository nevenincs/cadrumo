import type {
  DesktopSetup,
  GoogleAccount,
  SetupFailureCategory,
  SetupItemId,
  SetupItemProgress,
  SetupPlanEntry,
  SetupReview,
  SetupRow,
  SetupRun,
  SetupSnapshot,
} from "../ipc/contract";
import type { Setup } from "../shell/host";
import { catalogLanes } from "../shell/localModelLanes";
import { FIXTURE_CATALOG } from "./fixtures/agentCatalog";

// The scenario host's component setup: a made-up computer with the browser
// and the local AI (its program and its models, one item), each in the state
// a shape gives it, and the profile's Google account beside them -- not a
// setup item. Like the host, it sends codes only, which the window words.
// Nothing is downloaded: every plan, byte count and receipt is synthetic. With a latency the fixture runs a setup by itself; with none it
// waits for the scenario tests to move it on through `window.__scenarioSetup`.

export const SETUP_SHAPES = [
  "fresh",
  "ready",
  "partial",
  "interrupted",
  "offline",
  "hardware",
  "low_space",
  "plan_changes",
  "resume_changes",
  "busy",
  "unavailable",
  "google_signed_out",
  /** Nothing set up, and no status read settled until `readRows`. */
  "unread",
] as const;
export type SetupShape = (typeof SETUP_SHAPES)[number];

export type SetupFixtureControls = {
  /** Changes the underlying files; only the next host command observes it. */
  setAbsent(item: SetupItemId): void;
  /** Moves a running setup on by one step. */
  step(): void;
  /** A retry notice on the item now running. */
  retry(attempt: number, delaySeconds: number): void;
  /** The item now running fails in this way; the setup settles. */
  fail(category: SetupFailureCategory): void;
  /** The setup stops part-way, as when the computer sleeps or Cadrumo
   * closes. */
  interrupt(): void;
  /** Google's own page answers the sign-in this window started. */
  finishGoogle(succeeded: boolean): void;
  setGoogle(account: GoogleAccount): void;
  /** The first status read settles: an `unread` setup has its rows. */
  readRows(): void;
};

declare global {
  interface Window {
    __scenarioSetup?: SetupFixtureControls;
  }
}

const GB = 1_000_000_000;
const MB = 1_000_000;

type Seed = {
  row: SetupRow;
  // What the plan says of the entry.
  plan: Omit<SetupPlanEntry, "item">;
};

/** The operator action the product names as each kind's recovery. */
const RECOVERY_ACTION: Record<SetupRow["kind"], string> = {
  browser: "operator.provision.browser",
  local_ai: "operator.provision.local_ai",
};

const GOOGLE_EMAIL = "persona@example.com";

const row = (
  item: SetupItemId,
  kind: SetupRow["kind"],
  size: number | null,
): SetupRow => ({
  item,
  kind,
  mode: "quick",
  state: "absent",
  stale_reason: null,
  blocked_reason: null,
  failure: null,
  recovery: "set_up",
  recovery_action_id: RECOVERY_ACTION[kind],
  version: null,
  size_bytes: size,
});

function seeds(): Seed[] {
  return [
    {
      row: row("browser", "browser", 180 * MB),
      plan: {
        download_bytes: 180 * MB,
        source_hosts: ["cdn.playwright.dev"],
        destination: "components/browser",
        installs_outside_program: false,
        shares_download_with: null,
        parts: [],
      },
    },
    {
      // One item: the program that runs the models, then the model selected for
      // each role. Two roles select the same model, so only the first downloads it.
      row: row("local_ai", "local_ai", 3.4 * GB),
      plan: {
        download_bytes: 3.4 * GB,
        source_hosts: ["github.com", "registry.ollama.ai"],
        destination: "models",
        installs_outside_program: true,
        shares_download_with: null,
        parts: [
          { part: "program", download_bytes: null },
          { part: "vision_transcription", download_bytes: 2.4 * GB },
          { part: "text_extraction", download_bytes: 1 * GB },
          { part: "column_role_mapping", download_bytes: 0 },
          { part: "supply_nature_proposal", download_bytes: 0 },
        ],
      },
    },
  ];
}

function readied(held: SetupRow): SetupRow {
  return {
    ...held,
    state: "ready",
    stale_reason: null,
    blocked_reason: null,
    failure: null,
    recovery: null,
    recovery_action_id: null,
    version: "1.0",
  };
}

/** The button the engine offers after each failure. */
const RECOVERY: Record<SetupFailureCategory, SetupRow["recovery"]> = {
  offline: "check_again",
  host_unreachable: "try_again",
  secure_connection_failed: "try_again",
  blocked_by_network: "try_again",
  disk_full: "try_again",
  no_permission: "try_again",
  damaged_download: "try_again",
  not_enough_memory: null,
  memory_busy: "try_again",
  program_missing: "try_again",
  program_not_running: "try_again",
  program_proxy_differs: "try_again",
  interrupted: "resume",
  needs_sign_in: "try_again",
  not_in_this_build: null,
  cancelled: "try_again",
  unexpected: "try_again",
};

function failed(held: SetupRow, failure: SetupFailureCategory): SetupRow {
  const recovery = RECOVERY[failure];
  return {
    ...held,
    state: failure === "offline" ? "blocked" : "failed",
    blocked_reason: failure === "offline" ? "offline" : null,
    failure: failure === "offline" ? null : failure,
    recovery,
    recovery_action_id: recovery ? RECOVERY_ACTION[held.kind] : null,
  };
}

function shaped(shape: SetupShape): Seed[] {
  const all = seeds();
  const set = (item: SetupItemId, change: (held: SetupRow) => SetupRow) => {
    const seed = all.find((entry) => entry.row.item === item);
    if (seed) seed.row = change(seed.row);
  };
  switch (shape) {
    case "ready":
      all.forEach((seed) => (seed.row = readied(seed.row)));
      break;
    case "google_signed_out":
      all.forEach((seed) => (seed.row = readied(seed.row)));
      break;
    case "partial":
      set("browser", readied);
      set("local_ai", (held) => failed(held, "damaged_download"));
      break;
    case "interrupted":
      set("browser", readied);
      set("local_ai", (held) => failed(held, "interrupted"));
      break;
    case "offline":
      set("browser", (held) => failed(held, "offline"));
      set("local_ai", (held) => failed(held, "offline"));
      break;
    case "hardware":
      set("browser", readied);
      set("local_ai", (held) => ({
        ...held,
        state: "blocked",
        blocked_reason: "hardware",
        recovery: null,
        recovery_action_id: null,
      }));
      break;
    default:
      break;
  }
  return all;
}

const usable = (held: SetupRow) =>
  held.state === "ready" || held.state === "stale";

export function setupFixture({
  shape,
  latencyMs,
  say,
  readable,
}: {
  shape: SetupShape;
  latencyMs: number;
  say: (call: string) => void;
  readable: () => boolean;
}): Setup {
  const items = shaped(shape);
  let revision = 1;
  let run: SetupRun | null = null;
  let operations = 0;
  let plans = 0;
  // The digests of the plans this window approved, and whether a setup has
  // stopped part-way, after which a `resume_changes` plan is larger.
  const approved = new Set<string>();
  let stopped = false;
  // The profile's Google account: signed in on a computer that is otherwise
  // set up, not yet on one where setup has only begun.
  const signedIn =
    shape === "ready" || shape === "partial" || shape === "hardware";
  let google: GoogleAccount = {
    state: signedIn ? "signed_in" : "signed_out",
    email: signedIn ? GOOGLE_EMAIL : null,
    drive_folder_id: signedIn ? "profile-drive-folder" : null,
    stage: "idle",
    failure: null,
  };
  let check: SetupSnapshot["check"] = null;
  let mode: SetupSnapshot["rows_mode"] = "quick";
  let unread = shape === "unread";
  const listeners = new Set<(state: DesktopSetup) => void>();
  const timers = new Set<number>();
  let pendingCancel = false;
  // Each planned row as it stood before its setup ran, for an item a setup
  // that stopped never reached.
  const before = new Map<SetupItemId, SetupRow>();
  // What an interrupted download had already fetched: a resume goes on from
  // there instead of starting again.
  const partial = new Map<SetupItemId, number>();

  const rows = () => items.map((seed) => seed.row);
  const snapshot = (): SetupSnapshot => {
    const now = unread ? [] : rows();
    return {
      rows: now,
      rows_mode: unread ? null : mode,
      complete: unread ? null : now.every(usable),
      hardware_limited: unread
        ? null
        : now.some((held) => held.blocked_reason === "hardware"),
      check,
      setup: run,
      google,
      details: [
        "Cadrumo component report (simulated)",
        ...now.map(
          (held) =>
            `${held.item}: ${held.state}${held.failure ? ` (${held.failure})` : ""}`,
        ),
        `google: ${google.state ?? "unread"}`,
        run ? `setup ${run.operation_id}: ${run.stage}` : "no setup",
      ].join("\n"),
    };
  };
  const state = (): DesktopSetup =>
    !readable()
      ? { revision, state: "signed_out", snapshot: null }
      : shape === "unavailable"
        ? { revision, state: "unavailable", snapshot: null }
        : { revision, state: "ready", snapshot: snapshot() };
  const publish = () => {
    revision += 1;
    const next = state();
    listeners.forEach((listener) => listener(next));
    return next;
  };
  const later = (act: () => void) => {
    if (latencyMs <= 0) return;
    const timer = window.setTimeout(() => {
      timers.delete(timer);
      act();
    }, latencyMs);
    timers.add(timer);
  };
  const refuse = (code: string) => Promise.reject({ code });
  const ready = () => {
    if (!readable()) return refuse("not_signed_in");
    if (shape === "unavailable") return refuse("unavailable");
    return null;
  };

  const review = (wanted: Seed[]): SetupReview => {
    plans += 1;
    // A plan that changes between being shown and being answered gains an
    // extra hundred megabytes the second time.
    const grown =
      (shape === "plan_changes" && plans > 1) ||
      (shape === "resume_changes" && stopped)
        ? 100 * MB
        : 0;
    const entries = wanted.map((seed): SetupPlanEntry => ({
      item: seed.row.item,
      ...seed.plan,
      download_bytes:
        seed.plan.download_bytes === null
          ? null
          : seed.plan.download_bytes + grown,
    }));
    const known = entries.reduce(
      (sum, entry) => sum + (entry.download_bytes ?? 0),
      0,
    );
    const required = Math.round(known * 1.2 + GB);
    const free = shape === "low_space" ? GB : 120 * GB;
    return {
      // Named by its content, as the host's digest is: the same plan has
      // the same digest whenever it is worked out.
      plan_digest: `plan-${entries
        .map((entry) => `${entry.item}:${entry.download_bytes ?? "?"}`)
        .join("|")}`,
      entries,
      known_download_bytes: known,
      // A part of unknown size, such as the program's installer, leaves the
      // whole plan's size partly unknown, as the product's plan does.
      has_unknown_size: entries.some(
        (entry) =>
          entry.download_bytes === null ||
          entry.parts.some((part) => part.download_bytes === null),
      ),
      installs_outside_program: entries.some(
        (entry) => entry.installs_outside_program,
      ),
      required_bytes: required,
      free_bytes: free,
      space_sufficient: free >= required,
    };
  };

  const progress = (seed: Seed): SetupItemProgress => ({
    item: seed.row.item,
    step: null,
    completed: null,
    total: null,
    retry: null,
    result: null,
  });

  const settle = (outcome: NonNullable<SetupRun["outcome"]>) => {
    if (!run) return;
    for (const entry of run.items) {
      const seed = seedOf(entry.item);
      const held = before.get(entry.item);
      if (seed && held && !entry.result && seed.row.state === "provisioning")
        seed.row = held;
    }
    before.clear();
    run = {
      ...run,
      stage: "settled",
      review: null,
      cancellable: false,
      outcome,
      failure: null,
    };
  };

  const current = () => run?.items.find((entry) => entry.result === null);
  const seedOf = (item: SetupItemId) =>
    items.find((seed) => seed.row.item === item);

  /** One step of a running setup: connect, download in quarters, check,
   * then the next item; then the outcome. */
  const step = () => {
    if (!run || run.stage !== "running") return;
    if (pendingCancel) {
      pendingCancel = false;
      run.items.forEach((entry) => {
        const seed = seedOf(entry.item);
        const held = before.get(entry.item);
        if (!entry.result && seed && held) seed.row = held;
      });
      before.clear();
      settle("cancelled");
      publish();
      return;
    }
    const entry = current();
    const seed = entry && seedOf(entry.item);
    if (!entry || !seed) {
      settle("completed");
      publish();
      return;
    }
    const total = seed.plan.download_bytes;
    const download = (): SetupItemProgress => ({
      ...entry,
      step: "download",
      completed: total === null ? null : (partial.get(entry.item) ?? 0),
      total,
    });
    let next: SetupItemProgress;
    if (entry.step === null) next = { ...entry, step: "preflight" };
    else if (entry.step === "preflight")
      // The local AI installs its program first, then fetches its models.
      next = seed.plan.installs_outside_program
        ? { ...entry, step: "install" }
        : download();
    else if (entry.step === "install") next = download();
    else if (entry.step === "download" && total !== null) {
      const done = Math.min(total, (entry.completed ?? 0) + total / 4);
      next =
        done >= total
          ? { ...entry, step: "verify", completed: null, total: null }
          : { ...entry, completed: done, retry: null };
    } else if (entry.step === "download") next = { ...entry, step: "verify" };
    else {
      seed.row = readied(seed.row);
      next = {
        ...entry,
        step: null,
        retry: null,
        result: {
          changed: true,
          failure: null,
          transferred_bytes: total ?? 0,
        },
      };
    }
    run = {
      ...run,
      items: run.items.map((held) => (held.item === entry.item ? next : held)),
    };
    if (!current()) settle("completed");
    publish();
    if (run.stage === "running") later(step);
  };

  /** The approved plan starts: its rows are being set up from now on. */
  const begin = () => {
    if (!run) return publish();
    for (const entry of run.items) {
      const seed = seedOf(entry.item);
      if (!seed) continue;
      before.set(entry.item, seed.row);
      seed.row = {
        ...seed.row,
        state: "provisioning",
        recovery: null,
        recovery_action_id: null,
      };
    }
    run = { ...run, stage: "running", review: null };
    const next = publish();
    later(step);
    return next;
  };

  const controls: SetupFixtureControls = {
    setAbsent(item) {
      const seed = seedOf(item);
      if (seed)
        seed.row = row(seed.row.item, seed.row.kind, seed.row.size_bytes);
    },
    step,
    retry(attempt, delaySeconds) {
      const entry = current();
      if (!run || !entry) return;
      run = {
        ...run,
        items: run.items.map((held) =>
          held.item === entry.item
            ? {
                ...held,
                retry: { attempt, delay_s: delaySeconds },
              }
            : held,
        ),
      };
      publish();
    },
    fail(category) {
      const entry = current();
      const seed = entry && seedOf(entry.item);
      if (!run || !entry || !seed) return;
      const held = before.get(seed.row.item) ?? seed.row;
      before.delete(seed.row.item);
      seed.row = failed(held, category);
      run = {
        ...run,
        items: run.items.map((held) =>
          held.item === entry.item
            ? {
                ...held,
                step: null,
                retry: null,
                result: {
                  changed: false,
                  failure: category,
                  transferred_bytes: held.completed ?? 0,
                },
              }
            : held,
        ),
      };
      settle("failed");
      run = { ...run, failure: category };
      publish();
    },
    interrupt() {
      const entry = current();
      const seed = entry && seedOf(entry.item);
      if (!run || !seed) return;
      const held = before.get(seed.row.item) ?? seed.row;
      if (entry.completed !== null) partial.set(entry.item, entry.completed);
      stopped = true;
      settle("interrupted");
      seed.row = failed(held, "interrupted");
      publish();
    },
    setGoogle(account) {
      google = account;
      publish();
    },
    readRows() {
      unread = false;
      publish();
    },
    finishGoogle(succeeded) {
      if (google.stage !== "signing_in") return;
      google = succeeded
        ? {
            state: "signed_in",
            email: GOOGLE_EMAIL,
            drive_folder_id: "profile-drive-folder",
            stage: "idle",
            failure: null,
          }
        : {
            ...google,
            stage: "failed",
            failure: "needs_sign_in",
          };
      publish();
    },
  };

  return {
    read() {
      say("setup.read");
      return ready() ?? Promise.resolve(state());
    },
    check(checkMode) {
      say(`setup.check ${checkMode}`);
      const refused = ready();
      if (refused) return refused;
      operations += 1;
      const id = `check-${operations}`;
      mode = checkMode;
      check = {
        operation_id: id,
        kind: checkMode === "full" ? "status_full" : "status_quick",
        stage: "done",
        failure: null,
        refusal: null,
      };
      return Promise.resolve(publish());
    },
    verify(wanted) {
      say(`setup.verify ${wanted?.join(",") ?? "all"}`);
      const refused = ready();
      if (refused) return refused;
      operations += 1;
      mode = "full";
      check = {
        operation_id: `verify-${operations}`,
        kind: "verify",
        stage: "done",
        failure: null,
        refusal: null,
      };
      return Promise.resolve(publish());
    },
    start(wanted, options) {
      say(
        `setup.start ${wanted?.join(",") ?? "all"}${options?.resume ? " resume" : ""}`,
      );
      const refused = ready();
      if (refused) return refused;
      if (shape === "busy") return refuse("busy");
      if (run && run.stage !== "settled") return Promise.resolve(state());
      const download = options?.download;
      // A model the catalog does not size, such as one the person named, is
      // planned with an unknown download.
      const lane = download
        ? catalogLanes(FIXTURE_CATALOG).find(
            (held) => held.id === download.lane,
          )
        : undefined;
      if (download && !lane) return refuse("model_selection_unusable");
      const model = download
        ? {
            id: download.model,
            sizeBytes:
              lane?.models.find((held) => held.id === download.model)
                ?.sizeBytes ?? null,
          }
        : null;
      const chosen = items
        .filter((seed) =>
          download
            ? seed.row.item === "local_ai"
            : (wanted === null
                ? !usable(seed.row)
                : wanted.includes(seed.row.item)) &&
              seed.row.recovery !== null &&
              seed.row.recovery !== "check_again",
        )
        .map((seed) =>
          download && model
            ? {
                ...seed,
                plan: {
                  ...seed.plan,
                  download_bytes: model.sizeBytes,
                  parts: [
                    {
                      part: "download",
                      model: model.id,
                      download_bytes: model.sizeBytes,
                    },
                  ],
                },
              }
            : seed,
        );
      if (download) say(`setup.download ${download.lane} ${download.model}`);
      operations += 1;
      const plan = chosen.length === 0 ? null : review(chosen);
      run = {
        operation_id: `setup-${operations}`,
        stage: chosen.length === 0 ? "settled" : "review",
        review: plan,
        items: chosen.map(progress),
        cancellable: chosen.length > 0,
        cancel_requested: false,
        outcome: chosen.length === 0 ? "nothing_to_do" : null,
        failure: null,
      };
      // Resuming the plan this window approved before is approved already.
      if (options?.resume && plan && approved.has(plan.plan_digest))
        return Promise.resolve(begin());
      return Promise.resolve(publish());
    },
    answer(operationId, planDigest, decision) {
      say(`setup.answer ${decision}`);
      const refused = ready();
      if (refused) return refused;
      if (
        !run ||
        run.operation_id !== operationId ||
        run.stage !== "review" ||
        !run.review
      )
        return refuse("not_pending");
      if (decision === "reject") {
        settle("rejected");
        return Promise.resolve(publish());
      }
      if (run.review.plan_digest !== planDigest) return refuse("plan_changed");
      if (shape === "plan_changes" && plans === 1) {
        const chosen = run.items
          .map((entry) => seedOf(entry.item))
          .filter((seed): seed is Seed => seed !== undefined);
        run = { ...run, review: review(chosen) };
        publish();
        return refuse("plan_changed");
      }
      if (!run.review.space_sufficient) {
        settle("not_enough_space");
        return Promise.resolve(publish());
      }
      approved.add(run.review.plan_digest);
      return Promise.resolve(begin());
    },
    cancel(operationId) {
      say("setup.cancel");
      const refused = ready();
      if (refused) return refused;
      if (!run || run.operation_id !== operationId || run.stage === "settled")
        return refuse("not_cancellable");
      if (run.stage === "review") {
        settle("cancelled");
        return Promise.resolve(publish());
      }
      pendingCancel = true;
      run = { ...run, cancel_requested: true, cancellable: false };
      const next = publish();
      // Cancellation lands between transfer chunks: at the next step.
      later(step);
      return Promise.resolve(next);
    },
    removeModel(model) {
      say(`setup.removeModel ${model}`);
      const refused = ready();
      if (refused) return refused;
      if (run && run.stage !== "settled") return refuse("busy");
      return Promise.resolve(publish());
    },
    signInGoogle() {
      say("google.signIn");
      const refused = ready();
      if (refused) return refused;
      google = {
        ...google,
        stage: "signing_in",
        failure: null,
      };
      const next = publish();
      later(() => controls.finishGoogle(true));
      return Promise.resolve(next);
    },
    signOutGoogle() {
      say("google.signOut");
      const refused = ready();
      if (refused) return refused;
      // Removing the stored sign-in contacts nothing, so it settles at once.
      google = {
        state: "signed_out",
        email: null,
        drive_folder_id: null,
        stage: "idle",
        failure: null,
      };
      return Promise.resolve(publish());
    },
    observe(listener) {
      say("setup.observe");
      listeners.add(listener);
      window.__scenarioSetup = controls;
      listener(state());
      return Promise.resolve(() => {
        listeners.delete(listener);
        if (listeners.size === 0) {
          timers.forEach((timer) => window.clearTimeout(timer));
          timers.clear();
          if (window.__scenarioSetup === controls)
            delete window.__scenarioSetup;
        }
      });
    },
  };
}
