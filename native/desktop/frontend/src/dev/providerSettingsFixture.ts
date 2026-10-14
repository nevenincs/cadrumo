import type {
  ProviderSettings,
  ProviderSettingsRecord,
} from "../shell/providerSettings";
import { FIXTURE_CATALOG } from "./fixtures/agentCatalog";

// The scenario host's model providers: one lane per lane of the made-up
// catalog the host serves, each in its own way of signing in, starting with
// nothing set. Cadrumo keeps no list of real providers; these are the host's
// own stand-ins. Where a command-line app stands is reported as the backend
// reports it today: not checked, since no safe check exists yet of whether a
// provider's app is installed and signed in. A change is checked as the
// backend checks it and then forgotten: the fixture keeps whether a key was
// given, never the key.

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
  alpha_cli: "oauth_token_or_provider_sign_in",
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
).map((lane): Seed => {
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
});

const SEEDS: readonly Seed[] = FIXTURE_SETTINGS_LANES;

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
}): ProviderSettings {
  let changes = 0;
  const records = new Map<string, ProviderSettingsRecord>(
    SEEDS.map((seed) => [
      seed.id,
      { ...seed, ...initial(seed), revision: NO_RECORD },
    ]),
  );
  const take = async (provider: string, revision: string) => {
    await wait();
    if (!readable()) throw coded("not_signed_in");
    const record = records.get(provider);
    if (!record || record.auth_kind === "provider_sign_in_only")
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

  return {
    async status() {
      say("providerStatus");
      await wait();
      if (!readable()) throw coded("not_signed_in");
      return { development: false, providers: [...records.values()] };
    },
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
        mode:
          record.auth_kind === "oauth_token_or_provider_sign_in"
            ? "oauth_token"
            : "key",
        available: true,
        source: "profile",
        readiness: "not_verified",
      });
    },
    async turnOff({ provider, revision }) {
      say(`providerTurnOff ${provider}`);
      const record = await take(provider, revision);
      return await keep({
        ...record,
        mode: "disabled",
        available: false,
        source: "none",
        readiness: "disabled",
      });
    },
    async reset({ provider, revision }) {
      say(`providerReset ${provider}`);
      const record = await take(provider, revision);
      // Reset forgets the record, so the lane has none again.
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
}
