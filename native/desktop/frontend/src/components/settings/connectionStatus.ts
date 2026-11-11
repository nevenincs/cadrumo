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
 * keyless lane whose engine runs on this computer is first as ready as the
 * local AI set up to run it, as `setup` serves it: with no model file to run
 * it is not set up, whatever the engine answers. Set up, it is ready while
 * its engine runs, and while the engine sleeps until a document is read;
 * otherwise it says what the service measured of the engine. */
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
  // local AI. Where the service measured its engine, that measurement is its
  // status once the local AI is set up.
  if (provider.authKind === "none") {
    if (setup && setup.state !== "ready") return "setup_needed";
    if (engine?.state === "running") return "ready";
    if (setup?.server === "dormant") return "ready";
    if (engine?.state === "not_running") return "engine_not_running";
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

/** The line beneath a keyless local lane in the setup's own words: what is
 * missing while its local AI is not set up, and that its engine starts when a
 * document is read while it sleeps; null otherwise. */
export function localLaneDetail(
  t: Translate,
  status: ConnectionStatus,
  setup: SetupRow | null,
): string | null {
  if (!setup) return null;
  if (status === "setup_needed" && setup.state !== "ready")
    return rowSentence(t, setup);
  if (status === "ready" && setup.server === "dormant")
    return rowSentence(t, setup);
  return null;
}
