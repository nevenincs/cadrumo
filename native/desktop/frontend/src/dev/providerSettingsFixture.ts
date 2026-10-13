import type {
  ProviderSettings,
  ProviderSettingsRecord,
} from "../shell/providerSettings";

// The scenario host's model providers: the providers the profile settings
// cover, each in its own way of signing in, starting with nothing set. A
// change is checked as the backend checks it and then forgotten: the fixture
// keeps whether a key was given, never the key.

type Seed = Omit<
  ProviderSettingsRecord,
  "mode" | "available" | "source" | "readiness" | "revision"
>;

const SEEDS: Seed[] = [
  {
    id: "anthropic",
    display_name: "Claude",
    transport: "api",
    auth_kind: "api_key",
    consumers: ["assistant", "extraction"],
  },
  {
    id: "claude",
    display_name: "Claude",
    transport: "cli",
    auth_kind: "oauth_token_or_provider_sign_in",
    consumers: ["assistant"],
  },
  {
    id: "openai",
    display_name: "OpenAI",
    transport: "api",
    auth_kind: "api_key",
    consumers: ["assistant"],
  },
  {
    id: "kimi",
    display_name: "Kimi",
    transport: "cli",
    auth_kind: "api_key",
    consumers: ["assistant"],
  },
  ...(
    [
      ["zai", "Z.ai"],
      ["zhipu", "Zhipu"],
      ["deepseek", "DeepSeek"],
      ["moonshot", "Moonshot"],
      ["minimax", "MiniMax"],
    ] as const
  ).map(([id, name]): Seed => ({
    id,
    display_name: name,
    // A gateway runs Claude's command-line app with its own key.
    transport: "cli",
    auth_kind: "api_key_with_base_url",
    consumers: ["assistant"],
    default_base_url: `https://${id}.gateway.example/anthropic`,
  })),
  {
    id: "qwen",
    display_name: "Qwen",
    transport: "cli",
    auth_kind: "api_key_with_base_url",
    consumers: ["assistant"],
  },
  {
    id: "codex",
    display_name: "Codex",
    transport: "cli",
    auth_kind: "provider_sign_in_only",
    consumers: ["assistant"],
  },
  {
    id: "antigravity",
    display_name: "Antigravity",
    transport: "cli",
    auth_kind: "provider_sign_in_only",
    consumers: ["assistant"],
  },
  {
    id: "gemini",
    display_name: "Gemini",
    transport: "api",
    auth_kind: "api_key",
    consumers: ["extraction"],
  },
];

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
  let next = 0;
  const records = new Map<string, ProviderSettingsRecord>(
    SEEDS.map((seed) => [
      seed.id,
      {
        ...seed,
        mode: "unset",
        available: false,
        source: "none",
        readiness:
          seed.auth_kind === "provider_sign_in_only"
            ? "sign_in_required"
            : "missing",
        revision: `r${++next}`,
      },
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
  const keep = (record: ProviderSettingsRecord) => {
    const kept = { ...record, revision: `r${++next}` };
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
      return keep({
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
      return keep({
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
      return keep({
        ...withoutAddress(record),
        mode: "unset",
        available: false,
        source: "none",
        readiness: "missing",
      });
    },
  };
}
