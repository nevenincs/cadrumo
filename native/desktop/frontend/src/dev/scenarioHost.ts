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
  ManagerStatus,
  SignInSignal,
  SignInStatus,
} from "../ipc/contract";
import type { AgentViews } from "../shell/agentViews";
import type { Host } from "../shell/host";
import type { ProfileAccounts } from "../shell/profiles";
import type { ProfileViews } from "../shell/views";
import {
  FIXTURE_CONVERSATIONS,
  FIXTURE_DOCUMENTS,
  FIXTURE_HISTORY,
} from "./fixtures/agent";
import { BUSY_CALENDAR } from "./fixtures/calendarBusy";
import {
  AHEAD_CALENDAR,
  BEHIND_CALENDAR,
  EMPTY_CALENDAR,
  FIXTURE_CALENDAR,
  STRADDLING_CALENDAR,
  FIXTURE_NOTIFICATIONS,
  NEVER_CAPTURED,
} from "./fixtures/calendar";
import {
  AVAILABLE,
  FIXTURE_DROPPED,
  FIXTURE_RECORDS,
  feedBatch,
  FEED_BATCH,
  generatedBatches,
  MISSING,
  UNREADABLE,
} from "./fixtures/logs";
import { openFixtureTerminal } from "./fixtures/terminal";
import { SCENARIO_HOST_MARKER } from "./marker";
import type { Scenario } from "./scenarios";

export const FIXTURE_PROFILE = "Demo profile";

/** The other profiles of a computer that has several. Made-up names. */
const OTHER_PROFILES = ["Ana Soler Vidal", "Taller Ribera, S.L."];
/** A name the product's command line would rewrite. */
const ODD_PROFILE = "Rebajas 50%";

export type ScenarioHostOptions = {
  /** The documentation fixture the environment reports, or null for none. */
  docs: { origin: string; languages: DocsLanguage[] } | null;
  /** The output language the environment reports. */
  language: string;
  /** Fixed delay before a sign-in or sign-out answer, in milliseconds. */
  latencyMs: number;
  /** Replace the fixture records with this many generated ones. */
  logRecords?: number;
  /** Keep the log growing: a batch of records every this many milliseconds
   * after the backlog, as a process writing its log sends them. */
  logFeedMs?: number;
  /** Another shape of the fixture calendar: everything behind the day it
   * was evaluated on, everything ahead, that day inside a month, or the
   * turn of a year with many windows open at once. */
  calendar?: CalendarShape | null;
  /** Receives one line per host call; never a password or its length. */
  onCall?: (call: string) => void;
};

export const CALENDAR_SHAPES = {
  behind: BEHIND_CALENDAR,
  ahead: AHEAD_CALENDAR,
  straddling: STRADDLING_CALENDAR,
  busy: BUSY_CALENDAR,
} as const;
export type CalendarShape = keyof typeof CALENDAR_SHAPES;

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
  let runtimeAvailable = scenario.signIn.status.runtimeAvailable;
  let managerDispatched = scenario.manager?.autoDispatched ?? false;
  let managerReads = 0;
  let clipboard = "";
  const supervision = scenario.supervision;
  let observedManager: ManagerStatus | undefined = supervision?.initial;
  let managerRevision = 0;
  let signInListener: ((signal: SignInSignal) => void) | null = null;
  let statusDelayMs = 0;
  let statusFailure: HostFailure["code"] | undefined;

  // The profiles of this made-up computer, and the one that is selected.
  // A host with no profile commands still has the one its status names.
  const first = scenario.signIn.profile ?? FIXTURE_PROFILE;
  // Each is known by its label, as the product's own list knows them.
  const accounts: string[] =
    scenario.profiles === "none" ||
    (scenario.profiles === "absent" && scenario.signIn.profile === null)
      ? []
      : [
          first,
          ...(scenario.profiles === "several" || scenario.profiles === "once"
            ? OTHER_PROFILES
            : scenario.profiles === "odd"
              ? ["Ana Soler Vidal", ODD_PROFILE]
              : []),
        ];
  let listReads = 0;
  let active: string | null =
    scenario.signIn.profile === null ? null : (accounts[0] ?? null);

  const status = (): SignInStatus => ({
    ...scenario.signIn.status,
    state: presence,
    active_profile: active,
    runtimeAvailable,
  });

  const manager = scenario.manager;
  const managerCommand: Pick<Host, "startManager"> = manager
    ? {
        async startManager() {
          say("startManager");
          if (manager.result === "pending") return never();
          await wait(manager.delayMs ?? options.latencyMs);
          if (typeof manager.result === "object")
            throw failure(manager.result.code, "launch");
          if (manager.result === "dispatched") {
            managerDispatched = true;
            managerReads = 0;
          }
          return manager.result;
        },
      }
    : {};

  const profiles: ProfileAccounts = {
    async list() {
      say("profiles");
      // A process of the product's, as every other read is.
      await wait(options.latencyMs);
      listReads += 1;
      if (
        scenario.profiles === "unreadable" ||
        (scenario.profiles === "once" && listReads > 1)
      )
        throw failure("timed_out", "cli");
      return {
        profiles: [...accounts]
          .sort((a, b) => a.localeCompare(b))
          .map((name) => ({ name, active: name === active })),
        complete: true,
      };
    },
    async create(name) {
      // The name is the person's own text: reported by its length only.
      say(`createProfile ${name.length} characters`);
      const outcome = scenario.signIn.create ?? { kind: "accept" };
      if (outcome.kind === "pending") return never();
      await wait(options.latencyMs);
      if (outcome.kind === "fail") {
        // The answer is lost; the profile may be there all the same.
        if (scenario.signIn.createLands) {
          accounts.push(name);
          active = name;
          presence = "absent";
        }
        throw failure(outcome.code, "cli");
      }
      const taken = accounts.some(
        (held) => held.toLocaleLowerCase() === name.toLocaleLowerCase(),
      );
      if (outcome.kind === "refuse" || taken)
        return {
          kind: "refused",
          code:
            outcome.kind === "refuse" ? outcome.code : "profile_already_exists",
          retryAfterSeconds:
            outcome.kind === "refuse" ? outcome.retryAfterSeconds : null,
        };
      // As the product does: the new profile is selected, and signed out.
      accounts.push(name);
      active = name;
      presence = "absent";
      return { kind: "created", name };
    },
  };

  // A view belongs to a signed-in profile; without one it is refused.
  // Where the platform signs in inside the TUI the host cannot tell, and
  // the fixture session stands for a signed-in one.
  const readable = () =>
    scenario.views !== "refused" &&
    (presence === "present" || !scenario.signIn.status.supported);
  const views: ProfileViews = {
    async notifications() {
      say("notifications");
      await wait(options.latencyMs);
      if (!readable()) throw failure("timed_out", "cli");
      return scenario.views === "empty"
        ? NEVER_CAPTURED
        : FIXTURE_NOTIFICATIONS;
    },
    async filingCalendar(range) {
      say(`filingCalendar ${range.from} ${range.to}`);
      await wait(options.latencyMs);
      if (!readable()) throw failure("timed_out", "cli");
      if (scenario.views === "empty") return EMPTY_CALENDAR;
      return options.calendar
        ? CALENDAR_SHAPES[options.calendar]
        : FIXTURE_CALENDAR;
    },
  };

  // The agent's views go with the profile's: offered, empty, refused or not
  // offered together. They are read as the signed-in profile's too.
  const agent: AgentViews = {
    async conversations() {
      say("agentConversations");
      await wait(options.latencyMs);
      if (!readable()) throw failure("timed_out", "cli");
      return scenario.views === "empty" ? [] : FIXTURE_CONVERSATIONS;
    },
    async history(conversationId) {
      say(`agentHistory ${conversationId}`);
      await wait(options.latencyMs);
      if (!readable()) throw failure("timed_out", "cli");
      return scenario.views === "empty"
        ? []
        : (FIXTURE_HISTORY[conversationId] ?? []);
    },
    async documents(conversationId) {
      say(`agentDocuments ${conversationId}`);
      await wait(options.latencyMs);
      if (!readable()) throw failure("timed_out", "cli");
      return scenario.views === "empty"
        ? []
        : (FIXTURE_DOCUMENTS[conversationId] ?? []);
    },
  };

  return {
    available: true,
    ...(scenario.views === "none" ? {} : { views, agent }),
    ...(scenario.profiles === "absent" ? {} : { profiles }),
    ...managerCommand,
    ...(supervision
      ? {
          managerStatus() {
            say("managerStatus");
            return Promise.resolve(observedManager!);
          },
          observeManager: ((listener) => {
            say("observeManager");
            listener({
              kind: "manager-state",
              revision: 0,
              status: observedManager!,
            });
            const timers = supervision.events.map((event) => ({
              late: event.deliverAfterUnsubscribe,
              timer: window.setTimeout(() => {
                if (event.presence) presence = event.presence;
                if (event.statusDelayMs !== undefined)
                  statusDelayMs = event.statusDelayMs;
                statusFailure = event.statusFailure;
                if (event.manager) {
                  if (event.manager.revision > managerRevision) {
                    managerRevision = event.manager.revision;
                    observedManager =
                      event.manager.kind === "manager-state"
                        ? event.manager.status
                        : { state: "failed", failure: event.manager.error };
                    runtimeAvailable = observedManager.state === "ready";
                  }
                  listener(event.manager);
                }
                if (event.signIn) signInListener?.(event.signIn);
              }, event.afterMs),
            }));
            return Promise.resolve(() => {
              say("managerUnsubscribe");
              for (const timer of timers)
                if (!timer.late) window.clearTimeout(timer.timer);
            });
          }) satisfies NonNullable<Host["observeManager"]>,
          observeSignIn: ((listener) => {
            signInListener = listener;
            return Promise.resolve(() => {
              if (signInListener === listener) signInListener = null;
            });
          }) satisfies NonNullable<Host["observeSignIn"]>,
        }
      : {}),
    ...(manager?.installResult
      ? {
          async installManager(scope: "user" | "machine") {
            say(`installManager ${scope}`);
            const result = manager.installResult!;
            if (result === "pending") return never<"dispatched">();
            await wait(manager.delayMs ?? options.latencyMs);
            if (typeof result === "object")
              throw failure(result.code, "installation");
            managerDispatched = true;
            managerReads = 0;
            return result;
          },
        }
      : {}),
    // The shell draws its own menu here; the native popup is not simulated.
    nativeMenus: false,

    environment() {
      say("environment");
      if (scenario.environment === "pending") return never();
      if (scenario.environment === "failed" || !options.docs)
        return Promise.reject(failure("environment_failed", "environment"));
      return Promise.resolve({
        outputLanguage: options.language,
        docs: { state: "bundled", ...options.docs },
      });
    },

    signInStatus() {
      say("signInStatus");
      if (statusFailure) {
        const code = statusFailure;
        statusFailure = undefined;
        return Promise.reject(failure(code, "cli"));
      }
      if (statusDelayMs) {
        const captured = status();
        return wait(statusDelayMs).then(() => {
          say("managerAuthResolved");
          return captured;
        });
      }
      if (scenario.signIn.statusPending) return never();
      if (scenario.signIn.statusFailure)
        return Promise.reject(
          typeof scenario.signIn.statusFailure === "string"
            ? failure(scenario.signIn.statusFailure, "cli")
            : scenario.signIn.statusFailure,
        );
      if (managerDispatched && manager?.statusFailureAfterDispatch) {
        say("managerStatusRejected");
        return Promise.reject(
          failure(manager.statusFailureAfterDispatch, "cli"),
        );
      }
      if (
        managerDispatched &&
        manager?.readyAfterReads !== undefined &&
        ++managerReads >= manager.readyAfterReads
      ) {
        runtimeAvailable = true;
        presence = "absent";
        if (manager.readyReadDelayMs !== undefined) {
          const ready = status();
          return wait(manager.readyReadDelayMs).then(() => {
            say("managerReadinessResolved");
            return ready;
          });
        }
      }
      return Promise.resolve(status());
    },

    async signIn(_password, profile) {
      say("signIn");
      // Which profile, by its place in the list: never its name.
      const named = accounts.indexOf(profile ?? "");
      if (profile !== undefined) say(`signInProfile ${named + 1}`);
      const outcome = scenario.signIn.submit;
      const acknowledged = supervision
        ? { ...status(), state: "present" as const }
        : null;
      if (outcome.kind === "pending") return never();
      await wait(supervision?.submitDelayMs ?? options.latencyMs);
      if (outcome.kind === "fail") throw failure(outcome.code, "cli");
      if (outcome.kind === "refuse")
        return {
          kind: "refused",
          code: outcome.code,
          retryAfterSeconds: outcome.retryAfterSeconds,
        };
      // A sign-in that is accepted is what selects the profile.
      if (named >= 0) active = accounts[named] ?? active;
      presence = "present";
      return { kind: "signed-in", status: acknowledged ?? status() };
    },

    async signOut() {
      say("signOut");
      await wait(options.latencyMs);
      if (scenario.signIn.signOutFailure)
        throw failure(scenario.signIn.signOutFailure, "cli");
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
      // The backlog arrives over two batches, the second reporting records
      // the ring had already dropped, as a large backlog does.
      const split = Math.ceil(FIXTURE_RECORDS.length / 2);
      const batches: LogBatch[] =
        scenario.logs === "records" && options.logRecords
          ? generatedBatches(options.logRecords)
          : scenario.logs === "records"
            ? [
                {
                  records: FIXTURE_RECORDS.slice(0, split),
                  dropped: 0,
                  states: AVAILABLE,
                },
                {
                  records: FIXTURE_RECORDS.slice(split),
                  dropped: FIXTURE_DROPPED,
                  states: AVAILABLE,
                },
              ]
            : [
                {
                  records: [],
                  dropped: 0,
                  states:
                    scenario.logs === "empty"
                      ? AVAILABLE
                      : scenario.logs === "missing"
                        ? MISSING
                        : UNREADABLE,
                },
              ];
      let subscribed = true;
      if (scenario.managerLog) {
        for (const batch of batches) {
          batch.states = {
            ...batch.states,
            manager: {
              ...AVAILABLE.manager,
              kind:
                scenario.managerLog === "rejected"
                  ? "available"
                  : scenario.managerLog,
              failure:
                scenario.managerLog === "unreadable"
                  ? UNREADABLE.python.failure
                  : null,
              rejected: scenario.managerLog === "rejected" ? 2 : 0,
            },
          };
        }
      }
      let feed = 0;
      window.setTimeout(() => {
        for (const batch of batches) if (subscribed) listener(batch);
        if (!subscribed || scenario.logs !== "records" || !options.logFeedMs)
          return;
        let next =
          1 +
          Math.max(0, ...batches.flatMap((b) => b.records.map((r) => r.seq)));
        feed = window.setInterval(() => {
          listener(feedBatch(next));
          next += FEED_BATCH;
        }, options.logFeedMs);
      }, 0);
      return Promise.resolve(() => {
        subscribed = false;
        window.clearInterval(feed);
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
