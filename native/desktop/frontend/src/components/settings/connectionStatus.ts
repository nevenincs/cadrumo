import type { SetupRow } from "../../ipc/componentSetup";
import type { AgentEngineHealth } from "../../shell/agentSession";
import type { Translate } from "../../shell/strings";
import { rowSentence } from "../setup/setupWords";
import type { ProviderStatus } from "./types";

/** One status for a connection, in the same words wherever it is shown. */
export type ConnectionStatus =
  | "ready"
  | "saved"
  | "not_checked"
  | "setup_needed"
  | "sign_in_needed"
  | "unconfirmed"
  | "engine_not_running"
  | "off";

/** Describe what is set, without claiming more than the reading says. A
 * keyless lane whose engine runs on this computer shows the local AI's setup
 * row, `setup`, which the setup host serves already combined from the model
 * files, the engine's server and its last start: ready exactly when the row
 * is. Without such a row it says what the service measured of its engine. */
export function connectionStatus(
  provider: ProviderStatus,
  engine: AgentEngineHealth | null = null,
  setup: SetupRow | null = null,
): ConnectionStatus {
  if (provider.reason === "record_unreadable") return "setup_needed";
  if (provider.mode === "disabled") return "off";
  if (provider.readiness === "unusable") return "setup_needed";
  // An app connection needs its app, whatever it signs in with.
  if (provider.cliState === "not_installed") return "setup_needed";
  // A connection with no key and no sign-in has nothing to set up but its
  // local AI, whose served row is its status.
  if (provider.authKind === "none") {
    if (setup) return setup.state === "ready" ? "ready" : "setup_needed";
    if (engine?.state === "not_running") return "engine_not_running";
    if (engine?.state === "running") return "ready";
    return provider.readiness === "ready" ? "ready" : "not_checked";
  }
  if (provider.authKind === "provider_sign_in_only") {
    if (
      provider.cliState === "installed_signed_in" ||
      provider.readiness === "ready"
    )
      return "ready";
    // The probe could not say, and said why: that is not "signed out".
    if (provider.cliState === "unknown" && provider.cliStateCause)
      return "unconfirmed";
    if (
      provider.cliState === "installed_signed_out" ||
      provider.readiness === "sign_in_required"
    )
      return "sign_in_needed";
    return "not_checked";
  }
  if (provider.readiness === "ready") return "ready";
  if (provider.readiness === "sign_in_required") return "sign_in_needed";
  if (
    provider.mode === "key" ||
    provider.mode === "oauth_token" ||
    provider.source !== "none"
  )
    return "saved";
  return "setup_needed";
}

/** The line beneath a keyless local lane: its local AI's setup row in the
 * setup's own words, or null without one. */
export function localLaneDetail(
  t: Translate,
  setup: SetupRow | null,
): string | null {
  return setup ? rowSentence(t, setup) : null;
}
