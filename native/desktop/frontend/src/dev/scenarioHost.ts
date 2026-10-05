// The development scenario host: a `Host` that answers from a scenario
// instead of a desktop process. It exists so every shell state can be opened
// and refined in a browser. It is reachable only from the development entry
// (scenarios.html), which the production build never reads.
//
// Everything it reports is synthetic. A sign-in it "accepts" authenticated
// nothing, and a menu or clipboard it serves says nothing about the native
// one: its answers are design and test evidence only.

import type {
  DocsLanguage,
  HostFailure,
  LogBatch,
  SignInStatus,
} from "../ipc/contract";
import type { Host } from "../shell/host";
import {
  AVAILABLE,
  FIXTURE_RECORDS,
  MISSING,
  UNREADABLE,
} from "./fixtures/logs";
import { openFixtureTerminal } from "./fixtures/terminal";
import { SCENARIO_HOST_MARKER } from "./marker";
import type { Scenario } from "./scenarios";

export const FIXTURE_PROFILE = "Demo profile";

export type ScenarioHostOptions = {
  /** The documentation fixture the environment reports, or null for none. */
  docs: { origin: string; languages: DocsLanguage[] } | null;
  /** The output language the environment reports. */
  language: string;
  /** Fixed delay before a sign-in or sign-out answer, in milliseconds. */
  latencyMs: number;
  /** Receives one line per host call; never a password or its length. */
  onCall?: (call: string) => void;
};

const never = <T>() => new Promise<T>(() => undefined);

const wait = (ms: number) =>
  new Promise<void>((resolve) => window.setTimeout(resolve, ms));

function failure(
  code: HostFailure["code"],
  operation: HostFailure["operation"],
): HostFailure {
  return { code, operation, message: `${SCENARIO_HOST_MARKER}: ${code}` };
}

export function scenarioHost(
  scenario: Scenario,
  options: ScenarioHostOptions,
): Host {
  const say = (call: string) => options.onCall?.(call);
  let presence = scenario.signIn.status.state;
  let clipboard = "";

  const status = (): SignInStatus => ({
    ...scenario.signIn.status,
    state: presence,
    active_profile: FIXTURE_PROFILE,
  });

  return {
    available: true,
    // The shell draws its own menu here; the native popup is not simulated.
    nativeMenus: false,

    environment() {
      say("environment");
      if (scenario.environment === "pending") return never();
      if (scenario.environment === "failed" || !options.docs)
        return Promise.reject(failure("environment_failed", "environment"));
      return Promise.resolve({
        outputLanguage: options.language,
        docs: options.docs,
      });
    },

    signInStatus() {
      say("signInStatus");
      if (scenario.signIn.statusPending) return never();
      if (scenario.signIn.statusFailure)
        return Promise.reject(
          failure(scenario.signIn.statusFailure, "environment"),
        );
      return Promise.resolve(status());
    },

    async signIn() {
      say("signIn");
      const outcome = scenario.signIn.submit;
      if (outcome.kind === "pending") return never();
      await wait(options.latencyMs);
      if (outcome.kind === "refuse")
        return {
          kind: "refused",
          code: outcome.code,
          retryAfterSeconds: outcome.retryAfterSeconds,
        };
      presence = "present";
      return { kind: "signed-in" };
    },

    async signOut() {
      say("signOut");
      await wait(options.latencyMs);
      if (scenario.services === "refused")
        throw failure("timed_out", "environment");
      presence = "absent";
      return {
        remainingAccess: { automationEnabled: true, automationRevoked: false },
      };
    },

    openTerminal(kind, size, listener) {
      say(`openTerminal ${kind} ${size.cols}x${size.rows}`);
      if (scenario.terminals === "pending") return never();
      if (scenario.terminals === "failed")
        return Promise.reject(failure("spawn_failed", "terminal"));
      return Promise.resolve(
        openFixtureTerminal(kind, size, listener, scenario.terminals),
      );
    },

    subscribeLogs(listener) {
      say("subscribeLogs");
      if (scenario.logs === "pending") return never();
      const batch: LogBatch =
        scenario.logs === "records"
          ? { records: [...FIXTURE_RECORDS], dropped: 0, state: AVAILABLE }
          : {
              records: [],
              dropped: 0,
              state:
                scenario.logs === "empty"
                  ? AVAILABLE
                  : scenario.logs === "missing"
                    ? MISSING
                    : UNREADABLE,
            };
      let subscribed = true;
      window.setTimeout(() => subscribed && listener(batch), 0);
      return Promise.resolve(() => {
        subscribed = false;
      });
    },

    readClipboard() {
      say("readClipboard");
      return scenario.services === "refused"
        ? Promise.reject(failure("output_limit", "webview"))
        : Promise.resolve(clipboard);
    },

    writeClipboard(text) {
      say(`writeClipboard ${text.length} characters`);
      if (scenario.services === "refused")
        return Promise.reject(failure("invalid_arguments", "webview"));
      clipboard = text;
      return Promise.resolve();
    },

    showMenu() {
      return Promise.reject(failure("unsupported_platform", "webview"));
    },

    openExternal(url) {
      // Reported, never opened: a scenario leaves the page alone.
      say(`openExternal ${url}`);
      return scenario.services === "refused"
        ? Promise.reject(failure("spawn_failed", "webview"))
        : Promise.resolve();
    },
  };
}
