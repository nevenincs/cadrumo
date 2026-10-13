import type {
  ProviderSettings,
  ProviderSettingsRecord,
} from "../shell/providerSettings";
import { DECLARED_SETTINGS_LANES } from "./fixtures/agentLanes.generated";

// The scenario host's model providers: the lanes cadrumo-agent declares (one
// per way into a provider, generated in agentLanes.generated.ts), each in its
// own way of signing in, starting with nothing set. Where a command-line app
// stands is reported as the backend reports it today: not checked, since no
// safe check exists yet of whether a provider's app is installed and signed
// in. A change is
// checked as the backend checks it and then forgotten: the fixture keeps
// whether a key was given, never the key.

type Seed = Omit<
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

const SEEDS: Seed[] = DECLARED_SETTINGS_LANES.map(
  ({ default_base_url, ...lane }): Seed => ({
    ...lane,
    ...(default_base_url ? { default_base_url } : {}),
    ...(lane.transport === "cli" ? { cli_state: "unknown" as const } : {}),
  }),
);

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
