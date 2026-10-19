import type {
  ProviderSignInMethod,
  ProviderSignInSnapshot,
  ProviderSettings,
  ProviderSettingsRecord,
} from "../shell/providerSettings";
import { FIXTURE_CATALOG } from "./fixtures/agentCatalog";

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

/** How each made-up lane signs in; a lane not named here takes a key. */
const AUTH: Record<string, ProviderSettingsRecord["auth_kind"]> = {
  gamma_cli: "provider_sign_in_only",
  beta_cli: "provider_sign_in_only",
  gateway_cli: "api_key_with_base_url",
  relay_cli: "api_key_with_base_url",
};

/** The address a gateway lane is reached at unless the person gives one. */
const DEFAULT_BASE_URL: Record<string, string> = {
  gateway_cli: "https://gateway.example/v1",
};

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
      auth_kind: AUTH[id] ?? "api_key",
      ...(base ? { default_base_url: base } : {}),
      ...(lane.transport === "cli" ? { cli_state: "unknown" as const } : {}),
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
      })),
  );

const SEEDS: readonly Seed[] = FIXTURE_SETTINGS_LANES;

/** Only one made-up provider advertises GUI sign-in in scenario evidence. */
export const FIXTURE_SIGN_IN_PROVIDERS: readonly string[] = [
  ...new Set(
    SEEDS.filter((seed) => seed.auth_kind === "provider_sign_in_only").map(
      (seed) => seed.provider,
    ),
  ),
].slice(0, 1);

export type ProviderSignInFixtureFailure =
  "provider_unavailable" | "provider_error";

export type ProviderSignInFixtureControls = {
  failNextSettingsRead: () => void;
  deferNextStart: () => void;
  completeStart: () => void;
  failNextStart: (reason: ProviderSignInFixtureFailure) => void;
  setMethods: (methods: readonly ProviderSignInMethod[]) => void;
  failNextStatus: () => void;
  deferNextStatus: () => void;
  completeStatus: () => void;
  deferNextCancel: () => void;
  completeCancel: () => void;
  deferNextOpenExternal: () => void;
  completeOpenExternal: (fail?: boolean) => void;
  failCurrentAttempt: () => void;
  succeedCurrentAttempt: () => void;
};

// React StrictMode may evaluate the scenario host factory twice in dev mode.
// Keep the presentation controls shared so the exposed window handle and the
// host instance mounted by React always address the same next operation.
let failNextStart: ProviderSignInFixtureFailure | null = null;
let deferNextStart = false;
let completeDeferredStart: (() => void) | null = null;
let failNextStatus = false;
let deferNextStatus = false;
let completeDeferredStatus: (() => void) | null = null;
let deferNextCancel = false;
let completeDeferredCancel: (() => void) | null = null;
let deferNextOpenExternal = false;
let completeDeferredOpenExternal: ((fail: boolean) => void) | null = null;
let fixtureAttemptNumber = 0;
let fixtureAttempt: ProviderSignInSnapshot | null = null;
let fixtureCancelRequestedFor: string | null = null;
let rejectNextSettingsRead = false;
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

const coded = (code: string) => Object.assign(new Error(code), { code });

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
}: {
  say: (call: string) => void;
  wait: () => Promise<void>;
  /** A profile is signed in whose providers these are. */
  readable: () => boolean;
}): ProviderSettingsFixture {
  // React StrictMode may construct more than one host fixture. Mutable
  // sign-in state is shared so the exposed controls reach the mounted host.
  fixtureAttemptNumber = 0;
  fixtureAttempt = null;
  fixtureCancelRequestedFor = null;
  rejectNextSettingsRead = false;
  failNextStatus = false;
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
    return kept;
  };

  const AUTH_URL = "https://provider.example/sign-in";
  const cancelReply = (target: ProviderSignInSnapshot) => ({
    attempt_id: target.attempt_id,
    provider: target.provider,
    event: "browser_action" as const,
  });
  const signInControls: ProviderSignInFixtureControls = {
    failNextSettingsRead() {
      rejectNextSettingsRead = true;
      say("providerStatusFailureQueued");
    },
    deferNextStart() {
      deferNextStart = true;
    },
    completeStart() {
      completeDeferredStart?.();
      completeDeferredStart = null;
    },
    failNextStart(reason) {
      failNextStart = reason;
      say(`providerSignInFailureQueued ${reason}`);
    },
    setMethods(methods) {
      fixtureSignInMethods = [...methods];
    },
    failNextStatus() {
      failNextStatus = true;
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
    failCurrentAttempt() {
      if (!fixtureAttempt) return;
      fixtureAttempt = {
        attempt_id: fixtureAttempt.attempt_id,
        provider: fixtureAttempt.provider,
        event: "failed",
        reason: "provider_unavailable",
      };
      say("providerSignInAttemptFailed provider_unavailable");
    },
    succeedCurrentAttempt() {
      if (!fixtureAttempt) return;
      fixtureAttempt = {
        attempt_id: fixtureAttempt.attempt_id,
        provider: fixtureAttempt.provider,
        event: "succeeded",
      };
      fixtureCancelRequestedFor = null;
      say("providerSignInAttemptSucceeded");
    },
  };
  const makeAttempt = async (
    provider: string,
    method: "browser" | "device",
  ): Promise<ProviderSignInSnapshot> => {
    const record = records.get(provider);
    if (
      !record ||
      record.auth_kind !== "provider_sign_in_only" ||
      !FIXTURE_SIGN_IN_PROVIDERS.includes(record.provider)
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
    failNextStart = null;
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
        }
      : {
          attempt_id: attemptId,
          provider,
          event: method === "browser" ? "browser_action" : "started",
          ...(method === "browser"
            ? { url: AUTH_URL }
            : { user_code: "EXAMPLE-1234" }),
        };
    fixtureCancelRequestedFor = null;
    return fixtureAttempt;
  };

  const signInControlsSettings: NonNullable<ProviderSettings["signIn"]> = {
    async start({ provider, revision, method }) {
      say(`providerSignInStart ${provider} ${method}`);
      if (!readable()) throw coded("not_signed_in");
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
      if (failNextStatus) {
        failNextStatus = false;
        say("providerSignInStatusFailureReturned read_failed");
        throw coded("read_failed");
      }
      await wait();
      if (!fixtureAttempt || fixtureAttempt.attempt_id !== attemptId)
        throw coded("unknown");
      if (
        fixtureCancelRequestedFor === fixtureAttempt.attempt_id &&
        (fixtureAttempt.event === "starting" ||
          fixtureAttempt.event === "started" ||
          fixtureAttempt.event === "browser_action")
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
    async cancel({ attemptId }) {
      say("providerSignInCancel");
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
        rejectNextSettingsRead = false;
        throw coded("read_failed");
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
      return {
        development: false,
        providers: [...records.values()],
        sign_in_providers: [...FIXTURE_SIGN_IN_PROVIDERS],
        sign_in_methods: Object.fromEntries(
          FIXTURE_SIGN_IN_PROVIDERS.map((provider) => [
            provider,
            [...fixtureSignInMethods],
          ]),
        ),
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
