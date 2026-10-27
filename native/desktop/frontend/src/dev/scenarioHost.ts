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
  DesktopLanguage,
  HostFailure,
  LogBatch,
  LogLevel,
  ManagerStatus,
  PresentationOutcome,
  SignInSignal,
  SignInStatus,
  WindowAction,
} from "../ipc/contract";
import { censoFixture } from "./censoFixture";
import { ledgerFixture, type LedgerShape } from "./ledgerFixture";
import { modeloFixture, type ModeloShape } from "./modeloFixture";
import { sedeViewFixture } from "./sedeViewFixture";
import { SCENARIO_PASSWORD } from "./fixtures/password";
import { userProfileFixture } from "./userProfileFixture";
import type { Host } from "../shell/host";
import { NAVIGATION } from "../shell/navigation/projection";
import { admitsTuiView } from "../shell/navigation/register";
import type { AgentServiceStatus } from "../shell/agentSession";
import type { ProfileAccounts } from "../shell/profiles";
import type { ProfileViews } from "../shell/views";
import {
  fixtureAgent,
  type FixtureAsks,
  type FixtureCatalog,
  type FixtureDocuments,
  type FixtureStream,
} from "./agentFixtureHost";
import { agentAccessFixture } from "./agentAccessFixture";
import { setupApprovalsFixture } from "./setupApprovalsFixture";
import { ABOUT_FIXTURE } from "./fixtures/about";
import type { FixtureSkills } from "./fixtures/agentSkills";
import { BUSY_CALENDAR } from "./fixtures/calendarBusy";
import {
  providerSettingsFixture,
  type ProviderSignInFixtureControls,
} from "./providerSettingsFixture";
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
  MANAGER_AVAILABLE,
  MISSING,
  UNREADABLE,
} from "./fixtures/logs";
import { openFixtureTerminal } from "./fixtures/terminal";
import { setupFixture, type SetupShape } from "./setupFixture";
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
  /** The default minimum level reported by the host environment. */
  logLevel?: LogLevel;
  /** Another shape of the fixture calendar: everything behind the day it
   * was evaluated on, everything ahead, that day inside a month, or the
   * turn of a year with many windows open at once. */
  calendar?: CalendarShape | null;
  /** How the agent's reply streams: in order, or with a piece missing. */
  agentStream?: FixtureStream;
  /** What every agent reply stops to ask the person, if anything. */
  agentAsks?: FixtureAsks;
  /** What the agent's conversations have stored for `@` to name. */
  agentDocuments?: FixtureDocuments;
  /** How the agent serves its skills to `/`. */
  agentSkills?: FixtureSkills;
  /** How the service answers the agent's catalog. */
  agentCatalog?: FixtureCatalog;
  /** The shape of the made-up computer's component setup; where neither
   * this nor the scenario names one, the host offers no setup. */
  setup?: SetupShape | null;
  /** Offer setup reviews that an assistant's setup leaves for the person. */
  setupReviews?: boolean;
  /** How the made-up ledger answers, over the scenario's own shape. */
  ledger?: LedgerShape | null;
  /** How the made-up declarations answer. */
  modelo?: ModeloShape | null;
  /** Offer a made-up window port whose close is guarded as the native
   * host guards it, so a close the system raised can be played. */
  window?: boolean;
  /** Receives one line per host call; never a password or its length. */
  onCall?: (call: string) => void;
};

const EVIDENCE_CALENDAR: typeof FIXTURE_CALENDAR = {
  ...FIXTURE_CALENDAR,
  warnings: [
    {
      code: "filing.justificante_unverified",
      message: "The filing receipt has not been verified.",
      affected_modelos: ["111"],
    },
  ],
};
export const CALENDAR_SHAPES = {
  behind: BEHIND_CALENDAR,
  ahead: AHEAD_CALENDAR,
  straddling: STRADDLING_CALENDAR,
  busy: BUSY_CALENDAR,
  evidence: EVIDENCE_CALENDAR,
} as const;
export type CalendarShape = keyof typeof CALENDAR_SHAPES;

const never = <T>() => new Promise<T>(() => undefined);

/** External runtime events and delayed transport answers for browser scenarios. */
declare global {
  interface Window {
    __scenarioLanguage?: {
      publish(state: DesktopLanguage): void;
      switchAccount(profile: string, language: string): void;
      cacheNextObservation(state: DesktopLanguage): void;
      refuseNextRead(): void;
      refuseNextSet(): void;
      deferNextSet(): void;
      completeSet(state: DesktopLanguage): void;
    };
    /** Controls for synthetic, presentation-only provider sign-in attempts. */
    __scenarioProviderSignIn?: ProviderSignInFixtureControls;
    /** Publishes the fixture agent's status, as its service does when ready. */
    __scenarioAgentPublishStatus?: (status?: AgentServiceStatus) => void;
    /** Commits a change to the fixture agent's local model list elsewhere. */
    __scenarioLocalModelsChangeElsewhere?: () => void;
    /** The next password change is answered as unconfirmed. */
    __scenarioPassword?: { uncertain(): void; changes(): number };
    /** The made-up window port, where the scenario offers one. */
    __scenarioWindow?: ScenarioWindowControls;
  }
}

/** Plays the system's close on the made-up window and reads its answers. */
export type ScenarioWindowControls = {
  /** A close the system raised, as the window's own close or Alt+F4. */
  systemClose(): void;
  /** Every action the page sent, in order. */
  actions(): WindowAction[];
  /** Whether the window has closed. */
  closed(): boolean;
};

// One made-up window per page, whichever host instance answers: a scenario
// may build its host more than once.
let windowPage: (() => void) | null = null;
let windowAsked = false;
let windowReleasing = false;
let windowClosed = false;
const windowActions: WindowAction[] = [];

/** A close of the made-up window, held as the native host holds it. */
function closeWindow() {
  if (windowClosed) return;
  if (windowReleasing || windowAsked || windowPage === null) {
    windowClosed = true;
    return;
  }
  windowAsked = true;
  windowPage();
}

/**
 * A window port that holds a close the system raised as the native host
 * does: while the page listens the first close asks it, a second close
 * while it has not answered closes, `close_now` closes without asking
 * again and `keep_open` lets the next close ask again. Nothing closes:
 * `closed` only says the native window would have.
 */
function windowFixture(): NonNullable<Host["window"]> {
  window.__scenarioWindow = {
    systemClose: closeWindow,
    actions: () => [...windowActions],
    closed: () => windowClosed,
  };
  return {
    action(action) {
      windowActions.push(action);
      // `close` raises the same close the system does.
      if (action === "close") closeWindow();
      else if (action === "close_now") {
        windowReleasing = true;
        windowClosed = true;
      } else if (action === "keep_open") windowAsked = false;
      return Promise.resolve();
    },
    observe(listener) {
      listener({ maximized: false, fullscreen: false });
      return Promise.resolve(() => undefined);
    },
    guardClose(asking) {
      const listener = () => asking();
      windowPage = listener;
      return Promise.resolve(() => {
        if (windowPage === listener) windowPage = null;
      });
    },
  };
}

const wait = (ms: number) =>
  new Promise<void>((resolve) => window.setTimeout(resolve, ms));

function failure(
  code: HostFailure["code"],
  operation: HostFailure["operation"],
): HostFailure {
  return { code, operation, message: `${SCENARIO_HOST_MARKER}: ${code}` };
}

// One set of password-change controls per page, whichever host instance
// answers: a scenario may build its host more than once.
let passwordChanges = 0;
let passwordUncertain = false;
window.__scenarioPassword = {
  uncertain() {
    passwordUncertain = true;
  },
  changes: () => passwordChanges,
};

export function scenarioHost(
  scenario: Scenario,
  options: ScenarioHostOptions,
): Host {
  const say = (call: string) => options.onCall?.(call);
  let presence = scenario.signIn.status.state;
  let runtimeAvailable = scenario.signIn.status.runtimeAvailable;
  // The session waits for a fresh proof until a sign-in or a sign-out ends it.
  let reconnecting = scenario.signIn.status.reconnecting;
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
    reconnecting,
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
    async changePassword(passwords) {
      say("changePassword");
      await wait(options.latencyMs);
      passwordChanges += 1;
      if (presence !== "present")
        return {
          kind: "refused",
          code: "not_signed_in",
          retryAfterSeconds: null,
        };
      if (passwordUncertain) {
        passwordUncertain = false;
        return { kind: "unknown" };
      }
      const sent = JSON.parse(new TextDecoder().decode(passwords)) as Record<
        string,
        string
      >;
      return sent.current_passphrase === SCENARIO_PASSWORD
        ? { kind: "changed" }
        : {
            kind: "refused",
            code: "CREDENTIAL_REJECTED",
            retryAfterSeconds: null,
          };
    },
    async reviewDelete(name) {
      say("reviewProfileDelete");
      await wait(options.latencyMs);
      if (!accounts.includes(name)) throw failure("invalid_arguments", "cli");
      return { name, profileId: name, digest: "fixture" };
    },
    async delete(review, confirmation, acknowledged) {
      say("deleteProfile");
      await wait(options.latencyMs);
      if (
        !acknowledged ||
        confirmation !== review.name ||
        !accounts.includes(review.name)
      )
        throw failure("invalid_arguments", "cli");
      accounts.splice(accounts.indexOf(review.name), 1);
      if (active === review.name) {
        active = null;
        presence = "absent";
      }
    },
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
  const signedIn = () =>
    presence === "present" || !scenario.signIn.status.supported;
  const readable = () => scenario.views !== "refused" && signedIn();
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

  // The profile's ledger goes with its views, as the agent does.
  const ledger = ledgerFixture({
    say,
    wait: () => wait(options.latencyMs),
    signedIn,
    shape: options.ledger ?? scenario.ledger ?? "fixture",
  });
  const modelo = modeloFixture({
    say,
    wait: () => wait(options.latencyMs),
    signedIn,
    shape: options.modelo ?? "fixture",
  });

  const providerFixture = providerSettingsFixture({
    say,
    wait: () => wait(options.latencyMs),
    readable,
  });

  // The agent goes with the profile's views: offered, empty, refused or not
  // offered together. Its conversations are read as the signed-in
  // profile's too.
  const {
    agent,
    session: agentSession,
    publishStatus,
    changeListElsewhere,
  } = fixtureAgent({
    say,
    wait: () => wait(options.latencyMs),
    signedIn,
    readable,
    empty: scenario.views === "empty",
    stream: options.agentStream ?? "steady",
    asks: options.agentAsks ?? null,
    refused: () => failure("timed_out", "cli"),
    turnedOff: providerFixture.turnedOffLanes,
    documents: options.agentDocuments ?? "stored",
    skills: options.agentSkills ?? "bundled",
    catalog: options.agentCatalog ?? "served",
  });
  // Every host this page made publishes, as one service would for each.
  const publishedBefore = window.__scenarioAgentPublishStatus;
  window.__scenarioAgentPublishStatus = (status) => {
    publishedBefore?.(status);
    publishStatus(status);
  };
  const changedBefore = window.__scenarioLocalModelsChangeElsewhere;
  window.__scenarioLocalModelsChangeElsewhere = () => {
    changedBefore?.();
    changeListElsewhere();
  };

  const providerSettings = providerFixture.settings;
  window.__scenarioProviderSignIn = providerFixture.signInControls;

  const agentAccess = agentAccessFixture({
    say,
    wait: () => wait(options.latencyMs),
    readable,
  });

  const setupShape = options.setup ?? scenario.setup ?? null;
  const setup = setupShape
    ? setupFixture({
        shape: setupShape,
        latencyMs: options.latencyMs,
        say,
        readable: () => presence === "present",
      })
    : undefined;

  let languageRevision = 0;
  let outputLanguage = options.language;
  let refuseLanguageSet = false;
  let refuseLanguageRead = false;
  let cachedLanguage: DesktopLanguage | null = null;
  let deferLanguageSet = false;
  let completeLanguageSet: ((state: DesktopLanguage) => void) | null = null;
  const languageListeners = new Set<(state: DesktopLanguage) => void>();
  const languageState = (): DesktopLanguage => ({
    language: outputLanguage,
    persisted: presence === "present",
    profile: presence === "present" ? (status().active_profile ?? null) : null,
    revision: languageRevision,
  });
  const languageControls: NonNullable<Window["__scenarioLanguage"]> = {
    publish(state) {
      // Transport delivery can be stale; the canonical fixture stays current.
      if (
        state.profile === languageState().profile &&
        state.revision >= languageRevision
      ) {
        outputLanguage = state.language;
        languageRevision = state.revision;
      }
      languageListeners.forEach((listener) => listener(state));
    },
    switchAccount(profile, language) {
      active = profile;
      presence = "present";
      outputLanguage = language;
      languageRevision += 1;
      signInListener?.({
        kind: "sign-in-state",
        revision: languageRevision,
        status: status(),
      });
      languageListeners.forEach((listener) => listener(languageState()));
    },
    cacheNextObservation(state) {
      cachedLanguage = state;
    },
    refuseNextRead() {
      refuseLanguageRead = true;
    },
    refuseNextSet() {
      refuseLanguageSet = true;
    },
    deferNextSet() {
      deferLanguageSet = true;
    },
    completeSet(state) {
      completeLanguageSet?.(state);
      completeLanguageSet = null;
    },
  };
  const userProfile = userProfileFixture(scenario.censo);
  return {
    language: {
      read: () => {
        if (refuseLanguageRead) {
          refuseLanguageRead = false;
          return Promise.reject(failure("read_failed", "cli"));
        }
        return Promise.resolve(languageState());
      },
      set: (language) => {
        say(`language.set ${language}`);
        if (refuseLanguageSet) {
          refuseLanguageSet = false;
          return Promise.reject(failure("read_failed", "cli"));
        }
        if (deferLanguageSet) {
          deferLanguageSet = false;
          return new Promise<DesktopLanguage>((resolve) => {
            completeLanguageSet = resolve;
          });
        }
        outputLanguage = language;
        languageRevision += 1;
        const next = languageState();
        languageListeners.forEach((listener) => listener(next));
        return Promise.resolve(next);
      },
      observe: (listener) => {
        languageListeners.add(listener);
        window.__scenarioLanguage = languageControls;
        if (cachedLanguage) {
          const cached = cachedLanguage;
          cachedLanguage = null;
          listener(cached);
        }
        return Promise.resolve(() => {
          languageListeners.delete(listener);
          if (
            languageListeners.size === 0 &&
            window.__scenarioLanguage === languageControls
          ) {
            delete window.__scenarioLanguage;
          }
        });
      },
    },
    userProfile,
    censo: censoFixture(userProfile, scenario.censo),
    presentation: {
      async present(view, params) {
        await wait(options.latencyMs);
        // As the host does: only a TUI view of the projection, with only
        // its declared parameters, is ever sent.
        if (!admitsTuiView(NAVIGATION, view, params))
          throw failure("invalid_arguments", "cli");
        const outcome: PresentationOutcome =
          presence !== "present"
            ? { outcome: "signed_out" }
            : { outcome: "presented", delivered: 1 };
        const shown = Object.entries(params)
          .sort(([a], [b]) => (a < b ? -1 : 1))
          .map(([name, value]) => ` ${name}=${value}`)
          .join("");
        say(`presentView ${view}${shown} ${outcome.outcome}`);
        return outcome;
      },
    },
    available: true,
    ...(options.window ? { window: windowFixture() } : {}),
    ...(scenario.views === "none"
      ? {}
      : {
          views,
          ledger,
          modelo,
          sedeView: sedeViewFixture({ say }),
          agent,
          agentSession,
          providerSettings,
          agentAccess,
        }),
    ...(setup ? { setup } : {}),
    ...(options.setupReviews
      ? { setupReview: setupApprovalsFixture(say) }
      : {}),
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
        }
      : {}),
    observeSignIn: ((listener) => {
      signInListener = listener;
      return Promise.resolve(() => {
        if (signInListener === listener) signInListener = null;
      });
    }) satisfies NonNullable<Host["observeSignIn"]>,
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

    about() {
      say("about");
      return scenario.services === "refused"
        ? Promise.reject(failure("package_unavailable", "package"))
        : Promise.resolve(ABOUT_FIXTURE);
    },

    environment() {
      say("environment");
      if (scenario.environment === "pending") return never();
      if (scenario.environment === "failed" || !options.docs)
        return Promise.reject(failure("environment_failed", "environment"));
      return Promise.resolve({
        outputLanguage: options.language,
        logLevel: options.logLevel ?? "INFO",
        docs:
          new URLSearchParams(window.location.search).get("docs") === "none"
            ? { state: "notBundled" }
            : { state: "bundled", ...options.docs },
      });
    },

    noteActivity() {
      say("noteActivity");
      return Promise.resolve();
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
      reconnecting = undefined;
      return { kind: "signed-in", status: acknowledged ?? status() };
    },

    async signOut() {
      say("signOut");
      await wait(options.latencyMs);
      if (scenario.signIn.signOutFailure)
        throw failure(scenario.signIn.signOutFailure, "cli");
      presence = "absent";
      reconnecting = undefined;
      // The product's reply: the saved setting, which a sign-out keeps, and
      // whether an issued key can still admit.
      const access = scenario.signIn.signOutAccess;
      return {
        remainingAccess: {
          automationEnabled: access ? access.automationEnabled : true,
          automationAccessRemains: access
            ? access.automationAccessRemains
            : false,
          automationRevoked: false,
        },
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
      if (scenario.managerLog === "absent") {
        for (const batch of batches) {
          batch.states = { ...batch.states };
          delete batch.states.manager;
        }
      } else if (scenario.managerLog) {
        for (const batch of batches) {
          batch.states = {
            ...batch.states,
            manager: {
              ...MANAGER_AVAILABLE,
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
    revealLogs() {
      say("revealLogs");
      return Promise.resolve();
    },

    writeClipboard(text) {
      say(`writeClipboard ${text.length} characters`);
      if (scenario.services === "refused")
        return Promise.reject(failure("invalid_arguments", "webview"));
      clipboard = text;
      return Promise.resolve();
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
