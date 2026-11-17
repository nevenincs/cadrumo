// A way into a provider of the profile's settings as the settings section
// shows it: what kind of credential it takes and where it stands. No stored
// key is ever part of it; the section can say whether a key is there, never
// what it is.

import type {
  AuthKind,
  ProviderTransport,
} from "../../shell/agentCatalogContract";
import type {
  ProviderCredentialSource,
  ProviderReadiness,
  ProviderSettingsMode,
  ProviderStatusReason,
} from "../../shell/providerSettingsContract";
import type {
  CliStateCause,
  NextStep,
  SignInCause,
} from "../../shell/providerSignInWords";

/** Where a command-line app stands on this computer. */
export type CliState =
  "installed_signed_in" | "installed_signed_out" | "not_installed" | "unknown";

/** One way into a provider: its API, or its command-line app. */
export type ProviderStatus = {
  /** The way's own id, which a change to it names. */
  id: string;
  /** The provider it reaches, as cadrumo-agent names it; the ways of one
   * provider share it, and it picks the provider's mark. */
  provider: string;
  /** The provider's own name, the same in every language and on each way. */
  name: string;
  transport: ProviderTransport;
  authKind: AuthKind;
  mode: ProviderSettingsMode;
  readiness: ProviderReadiness;
  source: ProviderCredentialSource;
  /** Where the app stands, for a command-line way. */
  cliState?: CliState;
  /** Why the app's state is not established, as a closed word the service
   * serves; only a command-line way has one. */
  cliStateCause?: CliStateCause;
  /** What the person can do about `cliStateCause`. */
  nextStep?: NextStep;
  /** A key is stored for it, kept while it is turned off. */
  credentialSaved?: boolean;
  /** Why it is not ready, as a stable code, where it says. */
  reason?: ProviderStatusReason;
  /** The gateway address the person stored, if any. */
  baseUrl?: string;
  /** The gateway address used when none is stored, if there is one. */
  defaultBaseUrl?: string;
  /** Whether a conversation on it leaves this computer, as the service
   * serves the agent's declaration; absent where it serves none. */
  readsOffHost?: boolean;
  /** The service can sign the lane out: served, never worked out here. */
  signOutAvailable?: boolean;
};

/** How the last change to a provider ended, as the section says it. */
export type ProviderOutcome =
  /** Saved, but its status could not be read back: refresh to see it. */
  | { kind: "saved_unread" }
  | {
      kind: "refused";
      code: string;
      /** Why, as the service's closed word, where it served one. */
      cause?: SignInCause;
      /** The reference of the log line that records it, where served. */
      logRef?: string;
    };

/** A key or token on its way to be saved, read once from its field. */
export type ProviderSecret = {
  /** Given straight to the host, never kept. */
  secret: string;
  /** The gateway address, where the provider takes one; empty for its
   * default. */
  baseUrl?: string;
};
