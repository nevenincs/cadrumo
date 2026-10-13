// A provider of the profile's settings as the settings section shows it:
// what kind of credential it takes, what uses it, and where it stands. No
// stored key is ever part of it; the section can say whether a key is there,
// never what it is.

/** How a provider is reached: by a key, a key and a gateway's address, a
 * token or the provider's own sign-in, or only that sign-in. */
export type ProviderAuthKind =
  | "api_key"
  | "api_key_with_base_url"
  | "oauth_token_or_provider_sign_in"
  | "provider_sign_in_only";

/** What the profile holds for a provider. */
export type ProviderMode =
  "key" | "oauth_token" | "provider_sign_in" | "disabled" | "unset";

/** Whether the provider can be used now, and if not, why. */
export type ProviderReadiness =
  | "ready"
  | "not_verified"
  | "missing"
  | "disabled"
  | "sign_in_required"
  | "unusable";

/** Where the provider's credential comes from. */
export type ProviderSource = "profile" | "environment" | "none";

/** What in Cadrumo may use a provider. */
export type ProviderConsumer = "assistant" | "extraction";

/** How Cadrumo reaches a provider: its web API, or its own command-line
 * app on this computer. One provider can be reached both ways, and each way
 * is set up on its own. */
export type ProviderTransport = "api" | "cli";

export type ProviderStatus = {
  id: string;
  /** The provider's own name, the same in every language. */
  name: string;
  transport: ProviderTransport;
  authKind: ProviderAuthKind;
  consumers: readonly ProviderConsumer[];
  mode: ProviderMode;
  readiness: ProviderReadiness;
  source: ProviderSource;
  /** Why it is not ready, as a stable code, where it says. */
  reason?: string;
  /** The gateway address the person stored, if any. */
  baseUrl?: string;
  /** The gateway address used when none is stored, if there is one. */
  defaultBaseUrl?: string;
};

/** How the last change to a provider ended, as the section says it. */
export type ProviderOutcome =
  /** Saved, but its status could not be read back: refresh to see it. */
  { kind: "saved_unread" } | { kind: "refused"; code: string };

/** A key or token on its way to be saved, read once from its field. */
export type ProviderSecret = {
  /** Given straight to the host, never kept. */
  secret: string;
  /** The gateway address, where the provider takes one; empty for its
   * default. */
  baseUrl?: string;
};
