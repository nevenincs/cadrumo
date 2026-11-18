import type { ProviderSettings } from "../shell/providerSettings";
import type {
  ProviderSignInMethod,
  ProviderSignInSnapshot,
  ProviderSettingsRecord,
} from "../shell/providerSettingsContract";
import {
  FIXTURE_CATALOG,
  fixtureAuthKind,
  servedUnderEngine,
} from "./fixtures/agentCatalog";

// The scenario host's model providers: one lane per lane of the made-up
// catalog the host serves, each in its own way of signing in, starting with
// nothing set. Codex and Claude below are presentation-only artwork examples;
// they do not say those providers are configured or served by the fixture
// agent. Cadrumo keeps no list of real providers. Where an app stands is
// reported as not checked, since the backend has no safe check yet. A change
// is checked as the backend checks it and then forgotten: the fixture keeps
// whether a key was given, never the key.

export type Seed = Omit<
  ProviderSettingsRecord,
  "mode" | "available" | "source" | "readiness" | "revision"
>;

/** The revision of a lane that has no record: 64 zeros. Every record the
 * profile holds has one of 64 lowercase hex digits that changes with it. */
const NO_RECORD = "0".repeat(64);

/** A revision for a changed record: a SHA-256 of the lane and its n-th
 * change, as hex. */
async function revisionOf(id: string, change: number): Promise<string> {
  const bytes = new TextEncoder().encode(`${id}:${change}`);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
}

/** The address a gateway lane is reached at unless the person gives one. */
const DEFAULT_BASE_URL: Record<string, string> = {
  zhipu_cli: "https://gateway.example/v1",
  // The address the made-up agent declares for its keyless lane; the agent
  // runs against the one the desktop launches it with, so none is shown.
  zai_api: "http://127.0.0.1:41000",
};

/** The lanes the made-up agent declares run on this computer. It declares
 * every other lane to send a conversation off it, as the agent declares
 * each lane itself. */
const ON_THIS_COMPUTER = new Set(["zai_api", "ollama_api", "llamacpp_api"]);

/** The command-line lanes the made-up agent declares a logout for. */
const LOGOUT_DECLARED = new Set(["antigravity_cli"]);

/** A lane as the service serves it: it can be signed out while it is signed
 * in and its agent declares a logout for it. */
const served = (record: ProviderSettingsRecord): ProviderSettingsRecord => ({
  ...record,
  sign_out_available:
    LOGOUT_DECLARED.has(record.id) &&
    record.mode !== "disabled" &&
    record.cli_state === "installed_signed_in",
});

/** The settings lanes of the made-up catalog: id `<provider>_<transport>`. */
export const FIXTURE_SETTINGS_LANES: readonly Seed[] = (
  FIXTURE_CATALOG.providers ?? []
)
  .map((lane): Seed => {
    const id = `${lane.provider_id}_${lane.transport}`;
    const base = DEFAULT_BASE_URL[id];
    return {
      id,
      provider: lane.provider_id,
      transport: lane.transport as "api" | "cli",
      display_name: lane.display_name,
      auth_kind: fixtureAuthKind(lane.provider_id, lane.transport),
      consumers: ["assistant"],
      credential_saved: false,
      ...(base ? { default_base_url: base } : {}),
      ...(lane.transport === "cli" ? { cli_state: "unknown" as const } : {}),
      reads_off_host: !ON_THIS_COMPUTER.has(id),
      sign_out_available: false,
    };
  })
  .concat(
    (
      [
        { id: "codex_api", provider: "codex", display_name: "Codex" },
        { id: "claude_api", provider: "claude", display_name: "Claude" },
      ] as const
    )
      .filter(
        (artwork) =>
          !(FIXTURE_CATALOG.providers ?? []).some(
            (lane) => lane.provider_id === artwork.provider,
          ),
      )
      .map((artwork): Seed => ({
        ...artwork,
        transport: "api",
        auth_kind: "api_key",
        consumers: ["assistant"],
        credential_saved: false,
        reads_off_host: true,
        sign_out_available: false,
      })),
  );

const SEEDS: readonly Seed[] = FIXTURE_SETTINGS_LANES;

/** The engine a profile that chose none runs, as the made-up agent's own
 * record starts. */
const DEFAULT_ENGINE = "llamacpp";

/** The settings lanes the service serves while the engine record selects
 * `selected`: the keyless lane of an engine it does not select is not listed. */
export const settingsLanesUnderEngine = (selected: string): readonly Seed[] =>
  FIXTURE_SETTINGS_LANES.filter((seed) =>
    servedUnderEngine(seed.provider, seed.transport, selected),
  );

/** Only one made-up provider advertises GUI sign-in in scenario evidence. */
export const FIXTURE_SIGN_IN_PROVIDERS: readonly string[] = [
  ...new Set(
    SEEDS.filter((seed) => seed.auth_kind === "provider_sign_in_only").map(
      (seed) => seed.provider,
    ),
  ),
].slice(0, 1);

export type ProviderSignInFixtureFailure =
  "provider_unavailable" | "provider_error" | "busy";

/** The words a failed attempt carries beside its reason. They are plain
 * text here, as a host may send any: the window keeps only the closed ones. */
export type ProviderSignInFixtureDetail = {
  cause?: string;
  next_step?: string;
  status_cause?: string;
  /** The diagnostic id the host wrote the failure under in its log. */
  log_ref?: string;
};

/** What a refused call carries beside its code, as a host sends it on the
 * rejection: a reason, a cause, a next step and a diagnostic id. */
export type ProviderSignInFixtureRefusal = ProviderSignInFixtureDetail & {
  reason?: string;
  /** The refusal's code, where it is not the generic `read_failed`. */
  code?: string;
};

/** One sign-in call the scenario host was asked, with the attempt it named. */
export type ProviderSignInFixtureCall = {
  op: "start" | "status" | "cancel" | "submit_code";
  attempt_id?: string;
};

/** What a lane says of its state when the probe could not confirm it: its
 * app's state and why, or that nothing has verified the lane. */
export type ProviderLaneFixtureState = Pick<
  ProviderSettingsRecord,
  "cli_state" | "cli_state_cause" | "next_step"
> &
  Partial<Pick<ProviderSettingsRecord, "readiness">>;

/** The console command the made-up service serves, as the real one does. */
const CONSOLE_SIGN_IN_COMMAND =
  "cadrumo-agent-service provider-login --provider {provider}";

export type ProviderSignInFixtureControls = {
  /** The next settings read rejects `read_failed`, with `detail` beside it
   * as the host sends it. */
  failNextSettingsRead: (detail?: ProviderSignInFixtureRefusal) => void;
  deferNextStart: () => void;
  completeStart: () => void;
  failNextStart: (
    reason: ProviderSignInFixtureFailure,
    detail?: ProviderSignInFixtureDetail,
  ) => void;
  /** The next start is refused: it rejects with `code` and `detail`, and no
   * attempt is made. */
  rejectNextStart: (
    code: string,
    detail?: ProviderSignInFixtureRefusal,
  ) => void;
  /** Which providers the service declares GUI sign-in for. */
  offerSignIn: (providers: readonly string[]) => void;
  /** The next `times` status reads answer while the service still reads the
   * sign-in routes behind them: `reads_pending`, with none offered. */
  pendSignInReads: (times?: number) => void;
  /** Every settings status read answers `busy`, as the host does before it
   * has admitted the service, until `releaseSettingsBusy`. */
  holdSettingsBusy: () => void;
  releaseSettingsBusy: () => void;
  /** A browser sign-in asks for an authorization code to be pasted back. */
  askForCode: () => void;
  /** The sign-in calls asked so far, with the attempt each named. */
  signInCalls: () => ProviderSignInFixtureCall[];
  /** Sets what a lane's app reports; the next settings read serves it. */
  leaveLaneUnconfirmed: (id: string, state: ProviderLaneFixtureState) => void;
  setMethods: (methods: readonly ProviderSignInMethod[]) => void;
  /** The next `times` status reads reject with `code` (`read_failed` once
   * unless given) and `detail`. */
  failNextStatus: (
    code?: string,
    detail?: ProviderSignInFixtureRefusal,
    times?: number,
  ) => void;
  /** The next sign-out rejects with `code` and `detail` beside it. */
  failNextSignOut: (
    code: string,
    detail?: ProviderSignInFixtureRefusal,
  ) => void;
  /** The next code submission rejects with `code` (`busy` unless given). */
  failNextSubmit: (
    code?: string,
    detail?: ProviderSignInFixtureRefusal,
  ) => void;
  deferNextStatus: () => void;
  completeStatus: () => void;
  deferNextCancel: () => void;
  completeCancel: () => void;
  deferNextOpenExternal: () => void;
  completeOpenExternal: (fail?: boolean) => void;
  /** The current attempt turns failed, with `detail` beside its reason
   * (`provider_unavailable` unless given). */
  failCurrentAttempt: (detail?: ProviderSignInFixtureRefusal) => void;
  /** The service ends the current attempt as cancelled, with `detail`
   * beside it, as it does when the profile's authority ends under it. */
  cancelCurrentAttempt: (detail?: ProviderSignInFixtureRefusal) => void;
  /** The current attempt succeeds; `signedIn` also leaves the lane signed
   * in, as the next settings read reports it. */
  succeedCurrentAttempt: (signedIn?: boolean) => void;
  /** The current attempt, still active, is reported with `detail` beside its
   * event from the next status read on, as a host may while it works. */
  noteCurrentAttempt: (detail: ProviderSignInFixtureDetail) => void;
  /** The next cancel is answered with `detail` beside its still-active event. */
  answerNextCancelWith: (detail: ProviderSignInFixtureDetail) => void;
};

// React StrictMode may evaluate the scenario host factory twice in dev mode.
// Keep the presentation controls shared so the exposed window handle and the
// host instance mounted by React always address the same next operation.
let failNextStart: ProviderSignInFixtureFailure | null = null;
let failNextDetail: ProviderSignInFixtureDetail = {};
let deferNextStart = false;
let completeDeferredStart: (() => void) | null = null;
let rejectNextStart: {
  code: string;
  detail: ProviderSignInFixtureRefusal;
} | null = null;
let fixtureSignInProviders: readonly string[] = FIXTURE_SIGN_IN_PROVIDERS;
let pendingSignInReads = 0;
let settingsBusy = false;
let askForCode = false;
let fixtureSignInCalls: ProviderSignInFixtureCall[] = [];
let failNextStatus: {
  code: string;
  detail: ProviderSignInFixtureRefusal;
  times: number;
} | null = null;
let failNextSubmit: {
  code: string;
  detail: ProviderSignInFixtureRefusal;
} | null = null;
let deferNextStatus = false;
let completeDeferredStatus: (() => void) | null = null;
let deferNextCancel = false;
let completeDeferredCancel: (() => void) | null = null;
let deferNextOpenExternal = false;
let completeDeferredOpenExternal: ((fail: boolean) => void) | null = null;
let fixtureAttemptNumber = 0;
let fixtureAttempt: ProviderSignInSnapshot | null = null;
let fixtureCancelRequestedFor: string | null = null;
let fixtureCancelDetail: ProviderSignInFixtureDetail | null = null;
let rejectNextSettingsRead: ProviderSignInFixtureRefusal | null = null;
let rejectNextSignOut: {
  code: string;
  detail: ProviderSignInFixtureRefusal;
} | null = null;
let fixtureSignInMethods: readonly ProviderSignInMethod[] = [
  "browser",
  "device",
];

export type ProviderSettingsFixture = {
  settings: ProviderSettings;
  signInControls: ProviderSignInFixtureControls;
  /** The lanes turned off, as `<provider>_<transport>`: the agent's catalog
   * leaves them out, as the service does. */
  turnedOffLanes: () => ReadonlySet<string>;
};

/** Where a lane stands before anything is set. A lane that signs in with the
 * provider's own app stands on that app. */
function initial(
  seed: Seed,
): Pick<
  ProviderSettingsRecord,
  "mode" | "available" | "source" | "readiness" | "reason"
> {
  // A lane with nothing to set up is ready once it is listed.
  if (seed.auth_kind === "none")
    return {
      mode: "unset",
      available: true,
      source: "none",
      readiness: "ready",
    };
  if (seed.auth_kind !== "provider_sign_in_only")
    return {
      mode: "unset",
      available: false,
      source: "none",
      readiness: "missing",
    };
  switch (seed.cli_state) {
    case "installed_signed_in":
      return {
        mode: "provider_sign_in",
        available: true,
        source: "none",
        readiness: "ready",
      };
    case "not_installed":
      return {
        mode: "unset",
        available: false,
        source: "none",
        readiness: "unusable",
        reason: "not_configured",
      };
    default:
      return {
        mode: "unset",
        available: false,
        source: "none",
        readiness: "sign_in_required",
        reason: "sign_in_with_provider_tool",
      };
  }
}

const coded = (code: string, detail: ProviderSignInFixtureRefusal = {}) =>
  Object.assign(new Error(code), { ...detail, code });

const withoutAddress = (
  record: ProviderSettingsRecord,
): ProviderSettingsRecord => {
  const copy = { ...record };
  delete copy.base_url;
  return copy;
};

export function providerSettingsFixture({
  say,
  wait,
  readable,
  selectedEngine = () => DEFAULT_ENGINE,
}: {
  say: (call: string) => void;
  wait: () => Promise<void>;
  /** A profile is signed in whose providers these are. */
  readable: () => boolean;
  /** The local engine the agent's record selects, read at each status: only
   * its keyless lane is listed, as the service lists. */
  selectedEngine?: () => string;
}): ProviderSettingsFixture {
  // React StrictMode may construct more than one host fixture. Mutable
  // sign-in state is shared so the exposed controls reach the mounted host.
  fixtureAttemptNumber = 0;
  fixtureAttempt = null;
  fixtureCancelRequestedFor = null;
  fixtureCancelDetail = null;
  rejectNextSettingsRead = null;
  rejectNextSignOut = null;
  failNextStatus = null;
  fixtureSignInCalls = [];
  pendingSignInReads = 0;
  settingsBusy = false;
  let changes = 0;
  const records = new Map<string, ProviderSettingsRecord>(
    SEEDS.map((seed) => [
      seed.id,
      { ...seed, ...initial(seed), revision: NO_RECORD },
    ]),
  );
  // What each lane held before it was turned off, by lane id.
  const turnedOff = new Map<string, ProviderSettingsRecord>();
  const seedOf = (id: string) => SEEDS.find((seed) => seed.id === id)!;
  // Any lane can be turned off and on; only a lane that takes a key has one
  // to set or forget.
  const take = async (provider: string, revision: string, anyLane = false) => {
    await wait();
    if (!readable()) throw coded("not_signed_in");
    const record = records.get(provider);
    if (!record || (!anyLane && record.auth_kind === "provider_sign_in_only"))
      throw coded("unknown");
    if (record.revision !== revision) throw coded("revision_conflict");
    return record;
  };
  const keep = async (record: ProviderSettingsRecord) => {
    const kept = {
      ...record,
      revision: await revisionOf(record.id, ++changes),
    };
    records.set(record.id, kept);
    return served(kept);
  };

  const AUTH_URL = "https://provider.example/sign-in";
  const cancelReply = (target: ProviderSignInSnapshot) => {
    const detail = fixtureCancelDetail ?? {};
    fixtureCancelDetail = null;
    return {
      attempt_id: target.attempt_id,
      provider: target.provider,
      event: "browser_action" as const,
      // What a host sends beside the event; the window checks it.
      ...(detail as Partial<ProviderSignInSnapshot>),
    };
  };
  const signInControls: ProviderSignInFixtureControls = {
    failNextSettingsRead(detail = {}) {
      rejectNextSettingsRead = detail;
      say("providerStatusFailureQueued");
    },
    deferNextStart() {
      deferNextStart = true;
    },
    completeStart() {
      completeDeferredStart?.();
      completeDeferredStart = null;
    },
    failNextStart(reason, detail = {}) {
      failNextStart = reason;
      failNextDetail = detail;
      say(`providerSignInFailureQueued ${reason}`);
    },
    rejectNextStart(code, detail = {}) {
      rejectNextStart = { code, detail };
      say(`providerSignInRefusalQueued ${code}`);
    },
    offerSignIn(providers) {
      fixtureSignInProviders = [...providers];
    },
    pendSignInReads(times = 1) {
      pendingSignInReads = times;
    },
    holdSettingsBusy() {
      settingsBusy = true;
    },
    releaseSettingsBusy() {
      settingsBusy = false;
    },
    askForCode() {
      askForCode = true;
    },
    signInCalls() {
      return fixtureSignInCalls.map((call) => ({ ...call }));
    },
    leaveLaneUnconfirmed(id, state) {
      const record = records.get(id);
      if (record) records.set(id, { ...record, ...state });
    },
    setMethods(methods) {
      fixtureSignInMethods = [...methods];
    },
    failNextSubmit(code = "busy", detail = {}) {
      failNextSubmit = { code, detail };
    },
    failNextSignOut(code, detail = {}) {
      rejectNextSignOut = { code, detail };
    },
    failNextStatus(code = "read_failed", detail = {}, times = 1) {
      failNextStatus = { code, detail, times };
    },
    deferNextStatus() {
      deferNextStatus = true;
    },
    completeStatus() {
      completeDeferredStatus?.();
      completeDeferredStatus = null;
    },
    deferNextCancel() {
      deferNextCancel = true;
    },
    completeCancel() {
      completeDeferredCancel?.();
      completeDeferredCancel = null;
    },
    deferNextOpenExternal() {
      deferNextOpenExternal = true;
    },
    completeOpenExternal(fail = false) {
      completeDeferredOpenExternal?.(fail);
      completeDeferredOpenExternal = null;
    },
    failCurrentAttempt(detail = {}) {
      if (!fixtureAttempt) return;
      const reason = detail.reason ?? "provider_unavailable";
      fixtureAttempt = {
        attempt_id: fixtureAttempt.attempt_id,
        provider: fixtureAttempt.provider,
        event: "failed",
        // What a host sends beside the reason; the window checks it.
        ...(detail as Partial<ProviderSignInSnapshot>),
        // A made-up host may send any word; the window keeps only the closed ones.
        reason: reason as ProviderSignInSnapshot["reason"],
      };
      say(`providerSignInAttemptFailed ${reason}`);
    },
    cancelCurrentAttempt(detail = {}) {
      if (!fixtureAttempt) return;
      fixtureAttempt = {
        attempt_id: fixtureAttempt.attempt_id,
        provider: fixtureAttempt.provider,
        event: "cancelled",
        ...(detail as Partial<ProviderSignInSnapshot>),
      };
      say(`providerSignInAttemptCancelled ${detail.reason ?? "none"}`);
    },
    succeedCurrentAttempt(signedIn = false) {
      if (!fixtureAttempt) return;
      fixtureAttempt = {
        attempt_id: fixtureAttempt.attempt_id,
        provider: fixtureAttempt.provider,
        event: "succeeded",
      };
      fixtureCancelRequestedFor = null;
      const record = records.get(fixtureAttempt.provider);
      if (signedIn && record)
        records.set(record.id, {
          ...record,
          cli_state: "installed_signed_in",
          mode: "provider_sign_in",
          available: true,
          readiness: "ready",
          reason: null,
        });
      say("providerSignInAttemptSucceeded");
    },
    noteCurrentAttempt(detail) {
      if (!fixtureAttempt) return;
      fixtureAttempt = {
        ...fixtureAttempt,
        ...(detail as Partial<ProviderSignInSnapshot>),
      };
    },
    answerNextCancelWith(detail) {
      fixtureCancelDetail = detail;
    },
  };
  const makeAttempt = async (
    provider: string,
    method: ProviderSignInMethod,
  ): Promise<ProviderSignInSnapshot> => {
    const record = records.get(provider);
    if (
      !record ||
      record.auth_kind !== "provider_sign_in_only" ||
      !fixtureSignInProviders.includes(record.provider)
    )
      throw coded("unsupported");
    records.set(provider, {
      ...record,
      // The service commits assistant_auth before launching the helper, so
      // the next provider read must carry a new revision even if login closes.
      // Selecting sign-in does not prove a usable model lane.
      mode: "provider_sign_in",
      available: true,
      source: "profile",
      readiness: "not_verified",
      reason: null,
      revision: await revisionOf(record.id, ++changes),
    });
    const failure = failNextStart;
    const detail = failNextDetail;
    failNextStart = null;
    failNextDetail = {};
    if (failure) say(`providerSignInFailureReturned ${failure}`);
    const attemptId = `3d9e8452-6ce3-4f70-9dd5-${(++fixtureAttemptNumber)
      .toString(16)
      .padStart(12, "0")}`;
    fixtureAttempt = failure
      ? {
          attempt_id: attemptId,
          provider,
          event: "failed",
          reason: failure,
          // What a host sends beside the reason; the window checks it.
          ...(detail as Partial<ProviderSignInSnapshot>),
        }
      : {
          attempt_id: attemptId,
          provider,
          event:
            method === "browser-code" || (method === "browser" && askForCode)
              ? "authorization_code_required"
              : method === "browser"
                ? "browser_action"
                : "started",
          ...(method !== "device"
            ? { url: AUTH_URL }
            : { user_code: "EXAMPLE-1234" }),
        };
    fixtureCancelRequestedFor = null;
    return fixtureAttempt;
  };

  const signInControlsSettings: NonNullable<ProviderSettings["signIn"]> = {
    async start({ provider, revision, method }) {
      say(`providerSignInStart ${provider} ${method}`);
      fixtureSignInCalls.push({ op: "start" });
      if (!readable()) throw coded("not_signed_in");
      if (rejectNextStart) {
        const refusal = rejectNextStart;
        rejectNextStart = null;
        await wait();
        say(`providerSignInRefusalReturned ${refusal.code}`);
        throw coded(refusal.code, refusal.detail);
      }
      const record = records.get(provider);
      if (!record || record.revision !== revision)
        throw coded("revision_conflict");
      if (deferNextStart) {
        deferNextStart = false;
        return new Promise<ProviderSignInSnapshot>((resolve, reject) => {
          completeDeferredStart = () => {
            void makeAttempt(provider, method).then(resolve, reject);
          };
        });
      }
      await wait();
      if (!readable()) throw coded("not_signed_in");
      return makeAttempt(provider, method);
    },
    async status({ attemptId }) {
      say("providerSignInStatus");
      fixtureSignInCalls.push({ op: "status", attempt_id: attemptId });
      if (failNextStatus) {
        const failure = failNextStatus;
        failNextStatus =
          failure.times > 1 ? { ...failure, times: failure.times - 1 } : null;
        say(`providerSignInStatusFailureReturned ${failure.code}`);
        throw coded(failure.code, failure.detail);
      }
      await wait();
      if (!fixtureAttempt || fixtureAttempt.attempt_id !== attemptId)
        throw coded("unknown");
      if (
        fixtureCancelRequestedFor === fixtureAttempt.attempt_id &&
        (fixtureAttempt.event === "starting" ||
          fixtureAttempt.event === "started" ||
          fixtureAttempt.event === "browser_action" ||
          fixtureAttempt.event === "authorization_code_required")
      ) {
        fixtureAttempt = {
          attempt_id: fixtureAttempt.attempt_id,
          provider: fixtureAttempt.provider,
          event: "cancelled",
        };
        return fixtureAttempt;
      }
      return fixtureAttempt;
    },
    async submitCode({ attemptId, code }) {
      fixtureSignInCalls.push({ op: "submit_code", attempt_id: attemptId });
      if (
        !fixtureAttempt ||
        fixtureAttempt.attempt_id !== attemptId ||
        fixtureAttempt.event !== "authorization_code_required" ||
        !/^[!-~]{1,2048}$/.test(code)
      )
        throw coded("invalid_request");
      say("providerSignInSubmitCode");
      if (failNextSubmit) {
        const refusal = failNextSubmit;
        failNextSubmit = null;
        throw coded(refusal.code, refusal.detail);
      }
      fixtureAttempt = {
        attempt_id: attemptId,
        provider: fixtureAttempt.provider,
        event: "started",
      };
      return fixtureAttempt;
    },
    async cancel({ attemptId }) {
      say("providerSignInCancel");
      fixtureSignInCalls.push({ op: "cancel", attempt_id: attemptId });
      if (!fixtureAttempt || fixtureAttempt.attempt_id !== attemptId)
        throw coded("unknown");
      const target = fixtureAttempt;
      if (deferNextCancel) {
        deferNextCancel = false;
        return new Promise<ProviderSignInSnapshot>((resolve) => {
          completeDeferredCancel = () => {
            fixtureCancelRequestedFor = target.attempt_id;
            say("providerSignInCancelSettled");
            resolve(cancelReply(target));
          };
        });
      }
      fixtureCancelRequestedFor = attemptId;
      await wait();
      say("providerSignInCancelSettled");
      // Model the service's cleanup window: still active, but its one-time URL
      // and device code have already been removed.
      return cancelReply(target);
    },
    async openExternal() {
      // Deliberately do not retain or report the transient address.
      say("providerSignInOpenExternal");
      if (deferNextOpenExternal) {
        deferNextOpenExternal = false;
        return new Promise<void>((resolve, reject) => {
          completeDeferredOpenExternal = (fail) => {
            if (fail) reject(coded("open_external_failed"));
            else resolve();
          };
        });
      }
    },
  };

  const settings: ProviderSettings = {
    async status() {
      say("providerStatus");
      if (rejectNextSettingsRead) {
        const detail = rejectNextSettingsRead;
        rejectNextSettingsRead = null;
        throw coded(detail.code ?? "read_failed", detail);
      }
      if (settingsBusy) {
        say("providerStatusBusy");
        throw coded("busy");
      }
      if (deferNextStatus) {
        deferNextStatus = false;
        await new Promise<void>((resolve) => {
          completeDeferredStatus = resolve;
        });
      }
      await wait();
      if (!readable()) throw coded("not_signed_in");
      say("providerStatusResolved");
      const listed = new Set(
        settingsLanesUnderEngine(selectedEngine()).map((seed) => seed.id),
      );
      // While the service still reads the sign-in routes it offers none and
      // says the answer is pending.
      const readsPending = pendingSignInReads > 0;
      if (readsPending) pendingSignInReads -= 1;
      const offered = readsPending ? [] : fixtureSignInProviders;
      return {
        providers: [...records.values()]
          .filter((record) => listed.has(record.id))
          .map(served),
        sign_in_providers: [...offered],
        sign_in_methods: Object.fromEntries(
          offered.map((provider) => [provider, [...fixtureSignInMethods]]),
        ),
        console_sign_in_command: CONSOLE_SIGN_IN_COMMAND,
        reads_pending: readsPending,
      };
    },
    signIn: signInControlsSettings,
    async set({ provider, revision, secret, base_url }) {
      say(`providerSet ${provider}`);
      const record = await take(provider, revision);
      // A key has no spaces in it; what has is not a key.
      if (secret === "" || /\s/.test(secret)) throw coded("invalid_key_format");
      const address = base_url?.trim() ?? "";
      if (address !== "" && !address.startsWith("https://"))
        throw coded("base_url_rejected");
      if (
        record.auth_kind === "api_key_with_base_url" &&
        address === "" &&
        !record.default_base_url
      )
        throw coded("base_url_rejected");
      return await keep({
        ...withoutAddress(record),
        ...(address ? { base_url: address } : {}),
        mode: "key",
        available: true,
        source: "profile",
        readiness: "not_verified",
        credential_saved: true,
      });
    },
    async turnOff({ provider, revision }) {
      say(`providerTurnOff ${provider}`);
      const record = await take(provider, revision, true);
      // What was saved is kept for when it is turned on again.
      turnedOff.set(record.id, record);
      return await keep({
        ...record,
        mode: "disabled",
        available: false,
        source: "none",
        readiness: "disabled",
        reason: "turned_off",
      });
    },
    async turnOn({ provider, revision }) {
      say(`providerTurnOn ${provider}`);
      const record = await take(provider, revision, true);
      if (record.mode !== "disabled") throw coded("unknown");
      const before = turnedOff.get(record.id);
      turnedOff.delete(record.id);
      const restored: ProviderSettingsRecord = before
        ? { ...before, revision: record.revision }
        : {
            ...withoutAddress(record),
            ...initial(seedOf(record.id)),
            reason: null,
          };
      return await keep(restored);
    },
    async signOut({ provider, revision }) {
      say(`providerSignOut ${provider}`);
      if (rejectNextSignOut) {
        const { code, detail } = rejectNextSignOut;
        rejectNextSignOut = null;
        await wait();
        throw coded(code, detail);
      }
      const record = await take(provider, revision, true);
      if (!served(record).sign_out_available) throw coded("unsupported_flow");
      return await keep({
        ...record,
        cli_state: "installed_signed_out",
        mode: "unset",
        available: false,
        source: "none",
        readiness: "sign_in_required",
        reason: "sign_in_with_provider_tool",
      });
    },
    async reset({ provider, revision }) {
      say(`providerReset ${provider}`);
      const record = await take(provider, revision);
      // Reset forgets the record, so the lane has none again.
      turnedOff.delete(record.id);
      const forgotten = {
        ...withoutAddress(record),
        mode: "unset",
        available: false,
        source: "none",
        readiness: "missing",
        revision: NO_RECORD,
      } satisfies ProviderSettingsRecord;
      records.set(record.id, forgotten);
      return forgotten;
    },
  };
  const turnedOffLanes = () =>
    new Set(
      [...records.values()]
        .filter((record) => record.mode === "disabled")
        .map((record) => record.id),
    );
  return { settings, signInControls, turnedOffLanes };
}
