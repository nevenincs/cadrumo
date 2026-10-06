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
import type { ProfileAccounts } from "../shell/profiles";
import type { ProfileViews } from "../shell/views";
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

/** Identities shaped like the product's, and plainly not one of them. */
const fixtureId = (index: number) =>
  `00000000-0000-4000-8000-${String(index).padStart(12, "0")}`;

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
  let clipboard = "";

  // The profiles of this made-up computer, and the one that is selected.
  // A host with no profile commands still has the one its status names.
  const first = scenario.signIn.profile ?? FIXTURE_PROFILE;
  const accounts: { id: string; name: string }[] =
    scenario.profiles === "none" ||
    (scenario.profiles === "absent" && scenario.signIn.profile === null)
      ? []
      : [first, ...(scenario.profiles === "several" ? OTHER_PROFILES : [])].map(
          (name, index) => ({ id: fixtureId(index + 1), name }),
        );
  let active: string | null =
    scenario.signIn.profile === null ? null : (accounts[0]?.id ?? null);

  const status = (): SignInStatus => ({
    ...scenario.signIn.status,
    state: presence,
    active_profile: accounts.find((a) => a.id === active)?.name ?? null,
  });

  const profiles: ProfileAccounts = {
    async list() {
      say("profiles");
      if (scenario.profiles === "unreadable") throw failure("timed_out", "cli");
      return {
        profiles: [...accounts]
          .sort((a, b) => a.name.localeCompare(b.name))
          .map((a) => ({ ...a, active: a.id === active })),
        complete: true,
      };
    },
    async create(name) {
      // The name is the person's own text: reported by its length only.
      say(`createProfile ${name.length} characters`);
      const outcome = scenario.signIn.create ?? { kind: "accept" };
      if (outcome.kind === "pending") return never();
      await wait(options.latencyMs);
      if (outcome.kind === "fail") throw failure(outcome.code, "cli");
      const taken = accounts.some(
        (a) => a.name.toLocaleLowerCase() === name.toLocaleLowerCase(),
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
      const made = { id: fixtureId(accounts.length + 1), name };
      accounts.push(made);
      active = made.id;
      presence = "absent";
      return { kind: "created", ...made };
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

  return {
    available: true,
    ...(scenario.views === "none" ? {} : { views }),
    ...(scenario.profiles === "absent" ? {} : { profiles }),
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
        return Promise.reject(failure(scenario.signIn.statusFailure, "cli"));
      return Promise.resolve(status());
    },

    async signIn(_password, profile) {
      say("signIn");
      // Which profile, by its place in the list: never its name.
      const named = accounts.findIndex((a) => a.id === profile);
      if (profile !== undefined) say(`signInProfile ${named + 1}`);
      const outcome = scenario.signIn.submit;
      if (outcome.kind === "pending") return never();
      await wait(options.latencyMs);
      if (outcome.kind === "fail") throw failure(outcome.code, "cli");
      if (outcome.kind === "refuse")
        return {
          kind: "refused",
          code: outcome.code,
          retryAfterSeconds: outcome.retryAfterSeconds,
        };
      // A sign-in that is accepted is what selects the profile.
      if (named >= 0) active = accounts[named]?.id ?? active;
      presence = "present";
      return { kind: "signed-in" };
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
                  state: AVAILABLE,
                },
                {
                  records: FIXTURE_RECORDS.slice(split),
                  dropped: FIXTURE_DROPPED,
                  state: AVAILABLE,
                },
              ]
            : [
                {
                  records: [],
                  dropped: 0,
                  state:
                    scenario.logs === "empty"
                      ? AVAILABLE
                      : scenario.logs === "missing"
                        ? MISSING
                        : UNREADABLE,
                },
              ];
      let subscribed = true;
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
