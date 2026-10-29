import type {
  DesktopSetup,
  GoogleAccount,
  SetupFailureCategory,
  SetupItemId,
  SetupItemProgress,
  SetupPartProgress,
  SetupPlanEntry,
  SetupPlanPart,
  SetupReview,
  SetupRow,
  SetupRun,
  SetupSnapshot,
} from "../ipc/contract";
import type { Setup } from "../shell/host";
import { catalogLanes } from "../shell/localModelLanes";
import {
  FIXTURE_CATALOG,
  type FixtureModelPresence,
} from "./fixtures/agentCatalog";

// The scenario host's component setup: a made-up computer with the browser
// and the local AI (its program and its models, one item), each in the state
// a shape gives it, and the profile's Google account beside them -- not a
// setup item. Like the host, it serves the items whether or not anyone is
// signed in, and refuses only what is a profile's while nobody is: the
// Google account, beside which it shows no sign-in, and a model of the
// person's list. Signed in while the profile's runtime does not answer, it
// still serves the items, shows the account as unreadable and refuses what is
// the profile's as `unavailable`. Like the host, it sends codes only, which
// the window words.
// Nothing is downloaded: every plan, byte count and receipt is synthetic. Each
// item has a setup of its own, and items set up side by side. The local AI's
// setup installs its program when it is missing, then the one model asked
// for, each as a part with progress of its own. With a latency the fixture
// runs a setup by itself; with none it waits for the scenario tests to move
// it on through `window.__scenarioSetup`, whose controls act on the first
// item setting up now, or on the item they name.

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
  /** The browser's builds are in place but no current receipt records them,
   * as an earlier installer left them: it reads unknown with Check again,
   * and the full check records it ready. */
  "unrecorded",
  /** Nothing set up, and no status read settled until `readRows`. */
  "unread",
  /** Nothing set up, and every setup's network check finds a host it
   * downloads from unreachable: the setup settles failed before its review,
   * leaving its row as it was. */
  "unreachable",
] as const;
export type SetupShape = (typeof SETUP_SHAPES)[number];

export type SetupFixtureControls = {
  /** Changes the underlying files; only the next host command observes it. */
  setAbsent(item: SetupItemId): void;
  /** Moves the first running setup, or `item`'s, on by one step. */
  step(item?: SetupItemId): void;
  /** A retry notice on the first item now running. */
  retry(attempt: number, delaySeconds: number): void;
  /** The first item now running fails in this way; its setup settles. */
  fail(category: SetupFailureCategory): void;
  /** The first running setup, or `item`'s, stops part-way, as when the
   * computer sleeps or Cadrumo closes. */
  interrupt(item?: SetupItemId): void;
  /** Google's own page answers the sign-in this window started. */
  finishGoogle(succeeded: boolean): void;
  setGoogle(account: GoogleAccount): void;
  /** The first status read settles: an `unread` setup has its rows. */
  readRows(): void;
  /** The host reads again after the sign-in status changed, as it does on
   * the session's cue. */
  reread(): void;
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

/** The operator action the product names as an item's recovery. */
const recoveryAction = (item: SetupItemId) => `operator.provision.${item}`;

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
  recovery_action_id: recoveryAction(item),
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
      // One item: the program that runs the models, whose installer's size
      // is known only once it starts, then the model asked for. Its parts are
      // planned with each setup.
      row: row("local_ai", "local_ai", null),
      plan: {
        download_bytes: null,
        source_hosts: ["github.com", "registry.ollama.ai"],
        destination: "models",
        installs_outside_program: true,
        shares_download_with: null,
        parts: [],
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
    recovery_action_id: recovery ? recoveryAction(held.item) : null,
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
    case "unrecorded":
      set("browser", (held) => ({
        ...held,
        state: "unknown",
        recovery: "check_again",
        size_bytes: null,
      }));
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
  answers = () => true,
  models,
}: {
  shape: SetupShape;
  latencyMs: number;
  say: (call: string) => void;
  readable: () => boolean;
  /** Whether the signed-in profile's runtime answers. */
  answers?: () => boolean;
  /** Where a model this setup downloads or removes is marked on or off this
   * computer, for the catalog to report. */
  models?: FixtureModelPresence;
}): Setup {
  const items = shaped(shape);
  let revision = 1;
  // Each item's latest setup, in the rows' order.
  let runs: SetupRun[] = [];
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
  // The setups asked to stop, by operation id.
  const pendingCancel = new Set<string>();
  // Each planned row as it stood before its setup ran, for an item a setup
  // that stopped never reached.
  const before = new Map<SetupItemId, SetupRow>();
  // What an interrupted download had already fetched, by item and part: a
  // resume goes on from there instead of starting again.
  const partial = new Map<string, number>();
  // Whether the local AI's program is on this computer: a computer whose
  // local AI was set up once has it, whatever became of its models.
  let programReady =
    shape === "ready" ||
    shape === "google_signed_out" ||
    shape === "partial" ||
    shape === "hardware";

  const rows = () => items.map((seed) => seed.row);
  // Signed out there is no profile, so no Google sign-in either; signed in
  // with no runtime to ask, the profile's sign-in cannot be read.
  const account = (): GoogleAccount =>
    readable()
      ? answers()
        ? google
        : {
            state: "unknown",
            email: null,
            drive_folder_id: null,
            stage: "idle",
            failure: null,
          }
      : {
          state: "signed_out",
          email: null,
          drive_folder_id: null,
          stage: "idle",
          failure: null,
        };
  const snapshot = (): SetupSnapshot => {
    const now = unread ? [] : rows();
    const shown = account();
    return {
      rows: now,
      rows_mode: unread ? null : mode,
      complete: unread ? null : now.every(usable),
      hardware_limited: unread
        ? null
        : now.some((held) => held.blocked_reason === "hardware"),
      check,
      runs,
      google: shown,
      details: [
        "Cadrumo component report (simulated)",
        ...now.map(
          (held) =>
            `${held.item}: ${held.state}${held.failure ? ` (${held.failure})` : ""}`,
        ),
        `google: ${shown.state ?? "unread"}`,
        ...(runs.length > 0
          ? runs.map((held) => `setup ${held.operation_id}: ${held.stage}`)
          : ["no setup"]),
      ].join("\n"),
    };
  };
  const state = (): DesktopSetup =>
    shape === "unavailable"
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
    if (shape === "unavailable") return refuse("unavailable");
    return null;
  };
  // What is a profile's: its Google account and its person's model list.
  const personal = () =>
    ready() ??
    (!readable()
      ? refuse("not_signed_in")
      : answers()
        ? null
        : refuse("unavailable"));

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
    parts: seed.plan.parts.map((part): SetupPartProgress => ({
      part: part.part,
      ...(part.model ? { model: part.model } : {}),
      step: null,
      completed: null,
      total: null,
      result: null,
    })),
  });

  const seedOf = (item: SetupItemId) =>
    items.find((seed) => seed.row.item === item);
  const order = (item: SetupItemId) =>
    items.findIndex((seed) => seed.row.item === item);
  const runFor = (item: SetupItemId) =>
    runs.find((held) => held.item === item) ?? null;
  const runById = (operationId: string) =>
    runs.find((held) => held.operation_id === operationId) ?? null;
  /** Keeps `next` as its item's setup, in the rows' order. */
  const put = (next: SetupRun) => {
    runs = [...runs.filter((held) => held.item !== next.item), next].sort(
      (left, right) => order(left.item) - order(right.item),
    );
    return next;
  };
  /** The item setting up now that the scenario controls act on: `item`'s,
   * or the first. */
  const active = (item?: SetupItemId) =>
    runs.find(
      (held) =>
        held.stage === "running" && (item === undefined || held.item === item),
    ) ?? null;

  const settle = (
    run: SetupRun,
    outcome: NonNullable<SetupRun["outcome"]>,
  ): SetupRun => {
    for (const entry of run.items) {
      const seed = seedOf(entry.item);
      const held = before.get(entry.item);
      if (seed && held && !entry.result && seed.row.state === "provisioning")
        seed.row = held;
      before.delete(entry.item);
    }
    pendingCancel.delete(run.operation_id);
    return put({
      ...run,
      stage: "settled",
      review: null,
      cancellable: false,
      outcome,
      failure: null,
    });
  };

  const current = (run: SetupRun | null) =>
    run?.items.find((entry) => entry.result === null);
  /** The part of `entry` setting up now; none for an item without parts. */
  const currentPart = (entry: SetupItemProgress | undefined) =>
    entry?.parts.find((part) => part.result === null);

  type Track = Pick<
    SetupPartProgress,
    "step" | "completed" | "total" | "result"
  >;
  /** One step of one track, an item's or one of its parts': connect,
   * download in quarters where the size is known, install where it is a
   * program, check; then its result. */
  const advance = (
    track: Track,
    key: string,
    size: number | null,
    installs: boolean,
  ): Track => {
    switch (track.step) {
      case null:
        return { ...track, step: "preflight" };
      case "preflight":
        return {
          ...track,
          step: "download",
          completed: size === null ? null : (partial.get(key) ?? 0),
          total: size,
        };
      case "download": {
        if (track.total === null || track.completed === null)
          return { ...track, step: installs ? "install" : "verify" };
        const done = Math.min(track.total, track.completed + track.total / 4);
        if (done < track.total) return { ...track, completed: done };
        return {
          ...track,
          step: installs ? "install" : "verify",
          completed: null,
          total: null,
        };
      }
      case "install":
        return { ...track, step: "verify" };
      default:
        return {
          step: null,
          completed: null,
          total: null,
          result: {
            changed: true,
            failure: null,
            transferred_bytes: size ?? 0,
          },
        };
    }
  };

  /** The program's installer, sized once its download starts. */
  const PROGRAM_BYTES = 120 * MB;
  // Each item's plan as its latest setup worked it out.
  const plannedSeeds = new Map<SetupItemId, Seed>();
  const partSize = (part: SetupPartProgress, item: SetupItemId) =>
    part.model
      ? (plannedSeeds
          .get(item)
          ?.plan.parts.find((held) => held.model === part.model)
          ?.download_bytes ?? null)
      : PROGRAM_BYTES;
  const partKey = (item: SetupItemId, part: SetupPartProgress) =>
    `${item}:${part.model ?? part.part}`;

  /** One step of a running setup, on its current item and part; then the
   * outcome. */
  const stepOf = (run: SetupRun | null) => {
    if (!run || run.stage !== "running") return;
    if (pendingCancel.has(run.operation_id)) {
      run.items.forEach((entry) => {
        const seed = seedOf(entry.item);
        const held = before.get(entry.item);
        if (!entry.result && seed && held) seed.row = held;
      });
      settle(run, "cancelled");
      publish();
      return;
    }
    const entry = current(run);
    const seed = entry && seedOf(entry.item);
    if (!entry || !seed) {
      settle(run, "completed");
      publish();
      return;
    }
    let next: SetupItemProgress;
    const part = currentPart(entry);
    if (part) {
      const moved: SetupPartProgress = {
        ...part,
        ...advance(
          part,
          partKey(entry.item, part),
          partSize(part, entry.item),
          !part.model,
        ),
      };
      if (moved.result && !part.model) programReady = true;
      if (moved.result?.failure === null && part.model)
        models?.mark(part.model, true);
      const parts = entry.parts.map((held) => (held === part ? moved : held));
      const finished = parts.every((held) => held.result !== null);
      next = {
        ...entry,
        parts,
        step: moved.step,
        completed: moved.completed,
        total: moved.total,
        retry: moved.step === part.step ? entry.retry : null,
        result: finished
          ? {
              changed: true,
              failure: null,
              transferred_bytes: parts.reduce(
                (sum, held) => sum + (held.result?.transferred_bytes ?? 0),
                0,
              ),
            }
          : null,
      };
    } else
      next = {
        ...entry,
        ...advance(
          entry,
          entry.item,
          seed.plan.download_bytes,
          seed.plan.installs_outside_program,
        ),
        retry: null,
      };
    if (next.result) seed.row = readied(seed.row);
    let moved = put({
      ...run,
      items: run.items.map((held) => (held.item === entry.item ? next : held)),
    });
    if (!current(moved)) moved = settle(moved, "completed");
    publish();
    if (moved.stage === "running") {
      const id = moved.operation_id;
      later(() => stepOf(runById(id)));
    }
  };
  const step = (item?: SetupItemId) => stepOf(active(item));

  /** The approved plan starts: its rows are being set up from now on. */
  const begin = (run: SetupRun) => {
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
    const id = put({ ...run, stage: "running", review: null }).operation_id;
    const next = publish();
    later(() => stepOf(runById(id)));
    return next;
  };

  /** What setting up `seed` plans: the browser as it is; the local AI's
   * program where it is missing or nothing else is asked for, then the
   * model asked for. */
  const planned = (
    seed: Seed,
    model: { id: string; sizeBytes: number | null } | null,
  ): Seed => {
    if (!seed.plan.installs_outside_program) {
      plannedSeeds.set(seed.row.item, seed);
      return seed;
    }
    const parts: SetupPlanPart[] = [
      ...(!programReady || !model
        ? [{ part: "program", download_bytes: null }]
        : []),
      ...(model
        ? [
            {
              part: "download",
              model: model.id,
              download_bytes: model.sizeBytes,
            },
          ]
        : []),
    ];
    const known = parts.flatMap((part) =>
      part.download_bytes === null ? [] : [part.download_bytes],
    );
    const shaped: Seed = {
      ...seed,
      plan: {
        ...seed.plan,
        download_bytes:
          known.length === 0 ? null : known.reduce((sum, n) => sum + n, 0),
        parts,
      },
    };
    plannedSeeds.set(seed.row.item, shaped);
    return shaped;
  };

  const controls: SetupFixtureControls = {
    setAbsent(item) {
      const seed = seedOf(item);
      if (seed)
        seed.row = row(seed.row.item, seed.row.kind, seed.row.size_bytes);
    },
    step,
    retry(attempt, delaySeconds) {
      const run = active();
      const entry = current(run);
      if (!run || !entry) return;
      put({
        ...run,
        items: run.items.map((held) =>
          held.item === entry.item
            ? {
                ...held,
                retry: { attempt, delay_s: delaySeconds },
              }
            : held,
        ),
      });
      publish();
    },
    fail(category) {
      const run = active();
      const entry = current(run);
      const seed = entry && seedOf(entry.item);
      if (!run || !entry || !seed) return;
      const held = before.get(seed.row.item) ?? seed.row;
      before.delete(seed.row.item);
      seed.row = failed(held, category);
      const cut = {
        changed: false,
        failure: category,
        transferred_bytes: entry.completed ?? 0,
      };
      // Only the part it hit fails; the parts after it were never reached.
      const part = currentPart(entry);
      const ended = settle(
        {
          ...run,
          items: run.items.map((held) =>
            held.item === entry.item
              ? {
                  ...held,
                  step: null,
                  retry: null,
                  result: cut,
                  parts: held.parts.map((each) =>
                    each === part ? { ...each, step: null, result: cut } : each,
                  ),
                }
              : held,
          ),
        },
        "failed",
      );
      put({ ...ended, failure: category });
      publish();
    },
    interrupt(item) {
      const run = active(item);
      const entry = current(run);
      const seed = entry && seedOf(entry.item);
      if (!run || !seed) return;
      const held = before.get(seed.row.item) ?? seed.row;
      const part = currentPart(entry);
      if (entry.completed !== null)
        partial.set(
          part ? partKey(entry.item, part) : entry.item,
          entry.completed,
        );
      stopped = true;
      settle(run, "interrupted");
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
    reread() {
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
      // The full check launches builds no receipt recorded, and records them.
      if (shape === "unrecorded")
        items
          .filter(
            (seed) =>
              seed.row.state === "unknown" &&
              (wanted ?? [seed.row.item]).includes(seed.row.item),
          )
          .forEach((seed) => (seed.row = readied(seed.row)));
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
      say(`setup.start ${wanted}${options?.resume ? " resume" : ""}`);
      const refused = options?.download ? personal() : ready();
      if (refused) return refused;
      if (shape === "busy") return refuse("busy");
      const running = runFor(wanted);
      if (running && running.stage !== "settled")
        return Promise.resolve(state());
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
        .filter(
          (seed) =>
            seed.row.item === wanted &&
            (download !== undefined ||
              (seed.row.recovery !== null &&
                seed.row.recovery !== "check_again")),
        )
        .map((seed) => planned(seed, model));
      if (download) say(`setup.download ${download.lane} ${download.model}`);
      operations += 1;
      if (shape === "unreachable" && chosen.length > 0) {
        const failure: SetupFailureCategory = "host_unreachable";
        const result = { changed: false, failure, transferred_bytes: 0 };
        put({
          item: wanted,
          operation_id: `setup-${operations}`,
          stage: "settled",
          review: null,
          items: chosen.map((seed) => ({
            ...progress(seed),
            step: "preflight",
            result,
          })),
          cancellable: false,
          cancel_requested: false,
          outcome: "failed",
          failure,
        });
        return Promise.resolve(publish());
      }
      const plan = chosen.length === 0 ? null : review(chosen);
      const run = put({
        item: wanted,
        operation_id: `setup-${operations}`,
        stage: chosen.length === 0 ? "settled" : "review",
        review: plan,
        items: chosen.map(progress),
        cancellable: chosen.length > 0,
        cancel_requested: false,
        outcome: chosen.length === 0 ? "nothing_to_do" : null,
        failure: null,
      });
      // Resuming the plan this window approved before is approved already.
      if (options?.resume && plan && approved.has(plan.plan_digest))
        return Promise.resolve(begin(run));
      return Promise.resolve(publish());
    },
    answer(operationId, planDigest, decision) {
      say(`setup.answer ${decision}`);
      const refused = ready();
      if (refused) return refused;
      const run = runById(operationId);
      if (!run || run.stage !== "review" || !run.review)
        return refuse("not_pending");
      if (decision === "reject") {
        settle(run, "rejected");
        return Promise.resolve(publish());
      }
      if (run.review.plan_digest !== planDigest) return refuse("plan_changed");
      if (shape === "plan_changes" && plans === 1) {
        const chosen = run.items
          .map((entry) => plannedSeeds.get(entry.item) ?? seedOf(entry.item))
          .filter((seed): seed is Seed => seed !== undefined);
        put({ ...run, review: review(chosen) });
        publish();
        return refuse("plan_changed");
      }
      if (!run.review.space_sufficient) {
        settle(run, "not_enough_space");
        return Promise.resolve(publish());
      }
      approved.add(run.review.plan_digest);
      return Promise.resolve(begin(run));
    },
    cancel(operationId) {
      say("setup.cancel");
      const refused = ready();
      if (refused) return refused;
      const run = runById(operationId);
      if (!run || run.stage === "settled") return refuse("not_cancellable");
      if (run.stage === "review") {
        settle(run, "cancelled");
        return Promise.resolve(publish());
      }
      pendingCancel.add(operationId);
      put({ ...run, cancel_requested: true, cancellable: false });
      const next = publish();
      // Cancellation lands between transfer chunks: at the next step.
      later(() => stepOf(runById(operationId)));
      return Promise.resolve(next);
    },
    removeModel(model) {
      say(`setup.removeModel ${model}`);
      const refused = personal();
      if (refused) return refused;
      // Only the local AI's own setup holds its models.
      const localAi = runFor("local_ai");
      if (localAi && localAi.stage !== "settled") return refuse("busy");
      models?.mark(model, false);
      return Promise.resolve(publish());
    },
    remove(removal) {
      say(`setup.remove ${removal}`);
      const refused = removal === "local_ai" ? personal() : ready();
      if (refused) return refused;
      const item = removal === "browser" ? "browser" : "local_ai";
      const running = runFor(item);
      if (running && running.stage !== "settled") return refuse("busy");
      const seed = items.find((entry) => entry.row.item === item);
      if (seed)
        seed.row = row(item, item, item === "browser" ? 180 * MB : null);
      if (item === "local_ai") {
        programReady = false;
        // The program alone leaves every model; the whole local AI takes
        // the models on the person's lists with it.
        if (removal === "local_ai") models?.markAll(false);
      }
      return Promise.resolve(publish());
    },
    signInGoogle() {
      say("google.signIn");
      const refused = personal();
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
      const refused = personal();
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
