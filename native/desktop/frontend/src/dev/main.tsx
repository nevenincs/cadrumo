// The development entry: the production `App`, mounted on the scenario host.
// Only scenarios.html loads this module, and the production build takes
// index.html alone as its input, so nothing here reaches the product.

import { StrictMode, useCallback, useMemo, useRef, useState } from "react";
import ReactDOM from "react-dom/client";
import { identity } from "virtual:desktop-content";
import { port as docsPort } from "virtual:docs-fixture";
import { App } from "../App";
import type { DocsLanguage } from "../ipc/environment";
import { LOG_LEVELS } from "../shell/records";
import "./index.css";
import { ScenarioBar, type HostCallLine } from "./ScenarioBar";
import {
  CALENDAR_SHAPES,
  scenarioHost,
  type CalendarShape,
} from "./scenarioHost";
import { HOUSEHOLD_SCENARIOS } from "./householdFixture";
import { BORRADOR_SCENARIOS } from "./borradorFixture";
import { ELECTION_SCENARIOS } from "./imputationElectionFixture";
import { LEDGER_SHAPES } from "./ledgerFixture";
import { modeloShape } from "./modeloFixture";
import { findScenario, type Scenario } from "./scenarios";
import { SETUP_SHAPES } from "./setupFixture";
import { parseFixtureEngineHealth } from "./fixtures/agentCatalog";

import "virtual:desktop-palette.css";

const LANGUAGES = ["en", "es", "ca", "hu"] as const;
const CALL_LIMIT = 40;
const DEFAULT_LATENCY_MS = 600;

// The documentation fixture listens beside this development server on a port
// of its own. The host name this page was opened on, with that port, is a
// different origin, as the documentation is in the desktop window, and it is
// reachable from wherever this page is.
function docsOrigin(): string | null {
  return docsPort === null
    ? null
    : `${window.location.protocol}//${window.location.hostname}:${docsPort}`;
}

function docsLanguages(origin: string, search: string): DocsLanguage[] {
  return LANGUAGES.map((code) => ({
    code,
    entry: `${origin}/${code === "en" ? "" : `${code}/`}index.html?search=${search}`,
  }));
}

/** The engine and placement lists a scenario's address writes, each a
 * comma-separated list; none where it writes neither. */
function engineChoices(engines: string | null, placements: string | null) {
  if (engines === null && placements === null) return undefined;
  const list = (text: string) => text.split(",");
  return {
    ...(engines === null ? {} : { engines: list(engines) }),
    ...(placements === null ? {} : { placements: list(placements) }),
  };
}

function readParams() {
  const params = new URLSearchParams(window.location.search);
  const language = params.get("lang");
  const latency = Number(params.get("latency"));
  return {
    scenario: findScenario(params.get("scenario")),
    language: (LANGUAGES as readonly string[]).includes(language ?? "")
      ? (language as string)
      : "en",
    latencyMs:
      params.has("latency") && Number.isFinite(latency) && latency >= 0
        ? latency
        : DEFAULT_LATENCY_MS,
    bar: params.get("bar") !== "off",
    // A log of this many generated records, for measuring the log view.
    logRecords: Math.max(0, Math.trunc(Number(params.get("records")) || 0)),
    logReplayGap: params.get("logReplayGap") === "true",
    // A batch of records every this many milliseconds, for a log that grows.
    logFeedMs: Math.max(0, Math.trunc(Number(params.get("feed")) || 0)),
    logAttachFailures: Math.max(
      0,
      Math.trunc(Number(params.get("logAttachFailures")) || 0),
    ),
    logLevel: LOG_LEVELS.find((level) => level === params.get("logLevel")),
    // Another shape of the fixture calendar, for where its mark for the
    // evaluated day stands.
    calendar: ((shape) =>
      shape !== null && shape in CALENDAR_SHAPES
        ? (shape as CalendarShape)
        : null)(params.get("calendar")),
    // The agent's reply with a piece of its stream missing, for how the
    // column recovers it.
    agentStream: params.get("stream") === "gap" ? ("gap" as const) : undefined,
    // What every agent reply stops to ask: questions, a tool's approval or
    // a Cadrumo review.
    agentAsks: (["questions", "approval", "review"] as const).find(
      (asks) => asks === params.get("asks"),
    ),
    // What the conversations have stored for `@` to name.
    agentDocuments: (["stored", "none", "unavailable", "failed"] as const).find(
      (documents) => documents === params.get("documents"),
    ),
    // How the agent serves its skills to `/`.
    agentSkills: (["bundled", "many", "failed", "unavailable"] as const).find(
      (skills) => skills === params.get("skills"),
    ),
    // How the service answers the agent's catalog.
    agentCatalog: (
      [
        "served",
        "busy",
        "busy-past-ready",
        "declared",
        "unsupported",
        "local-only",
        "engines-only",
      ] as const
    ).find((catalog) => catalog === params.get("catalog")),
    // Which of the local lane's models the made-up computer holds.
    localModels: (["none", "all"] as const).find(
      (held) => held === params.get("models"),
    ),
    // What the made-up agent states of each local engine: a JSON object
    // keyed by engine token.
    engineHealth: parseFixtureEngineHealth(params.get("engine_health")),
    // The engines and placements the made-up agent offers, each a
    // comma-separated list written as served.
    engineChoices: engineChoices(
      params.get("engine_choices"),
      params.get("placement_choices"),
    ),
    // The local engine the agent's stored record names at the start.
    localEngine: (["llamacpp", "ollama"] as const).find(
      (held) => held === params.get("engine"),
    ),
    // The shape of the component setup.
    setup: SETUP_SHAPES.find((shape) => shape === params.get("setup")),
    // How the made-up ledger answers.
    ledger: LEDGER_SHAPES.find((shape) => shape === params.get("ledger")),
    // What the made-up profile states for the household.
    household: HOUSEHOLD_SCENARIOS.find(
      (state) => state === params.get("household"),
    ),
    // How the made-up declarations answer.
    modelo: modeloShape(params.get("modelo")),
    // What the made-up profile states for the imputation election.
    election: ELECTION_SCENARIOS.find(
      (state) => state === params.get("election"),
    ),
    // The stage the made-up profile's AEAT draft and calculation are at.
    borrador: BORRADOR_SCENARIOS.find(
      (state) => state === params.get("borrador"),
    ),
    // A made-up window port, for how the page answers a close.
    window: params.get("window") === "port",
  };
}

declare global {
  interface Window {
    /** Every host call of the current run, in order, for the scenario tests. */
    __scenarioHostCalls?: string[];
    /** Product modules the specs drive directly. A build has no module
     * addresses to import them from, so the entry hands them over. */
    __scenarioModules?: {
      tauriHost(): Promise<typeof import("../shell/tauriHost")>;
      profileViews(): Promise<{
        react: typeof import("react");
        dom: typeof import("react-dom");
        client: typeof import("react-dom/client");
        calendar: typeof import("../shell/calendar");
        messages: typeof import("../shell/messages");
      }>;
      ledgerReads(): Promise<{
        react: typeof import("react");
        dom: typeof import("react-dom");
        client: typeof import("react-dom/client");
        documents: typeof import("../components/ledger/documents/useLedgerRead");
        setup: typeof import("../components/ledger/setup/SetupParts");
      }>;
      declarationsList(): Promise<
        typeof import("../components/modelo/declarations/useDeclarationsList")
      >;
      profileHousehold(): Promise<{
        react: typeof import("react");
        dom: typeof import("react-dom");
        client: typeof import("react-dom/client");
        household: typeof import("../components/profile/Household");
        fixture: typeof import("./householdFixture");
      }>;
      localAiReads(): Promise<{
        lanes: typeof import("../shell/localAiLanes");
        agent: typeof import("./agentFixtureHost");
        providers: typeof import("./providerSettingsFixture");
      }>;
      sedeViewHook(): Promise<{
        react: typeof import("react");
        dom: typeof import("react-dom");
        client: typeof import("react-dom/client");
        hook: typeof import("../components/browser/useSedeView");
      }>;
      catalogReadPolicy(): Promise<typeof import("../shell/catalogReadPolicy")>;
      agentCatalog(): Promise<
        typeof import("../components/agent/useAgentCatalog")
      >;
      providerReads(): Promise<{
        settings: typeof import("../shell/providerSettings");
        views: typeof import("../shell/agentViews");
      }>;
      agentReaders(): Promise<{
        models: typeof import("../shell/readingModel");
        live: typeof import("../shell/agentLive");
      }>;
      hostCall(): Promise<typeof import("../shell/hostCall")>;
      sessionGate(): Promise<{
        react: typeof import("react");
        dom: typeof import("react-dom");
        client: typeof import("react-dom/client");
        gate: typeof import("../shell/sessionGate");
        run: typeof import("../shell/aeatSyncRun");
        signIn: typeof import("../shell/signIn");
      }>;
    };
  }
}

window.__scenarioModules = {
  profileHousehold: async () => ({
    react: await import("react"),
    dom: await import("react-dom"),
    client: await import("react-dom/client"),
    household: await import("../components/profile/Household"),
    fixture: await import("./householdFixture"),
  }),
  localAiReads: async () => ({
    lanes: await import("../shell/localAiLanes"),
    agent: await import("./agentFixtureHost"),
    providers: await import("./providerSettingsFixture"),
  }),
  agentReaders: async () => ({
    models: await import("../shell/readingModel"),
    live: await import("../shell/agentLive"),
  }),
  sedeViewHook: async () => ({
    react: await import("react"),
    dom: await import("react-dom"),
    client: await import("react-dom/client"),
    hook: await import("../components/browser/useSedeView"),
  }),
  catalogReadPolicy: () => import("../shell/catalogReadPolicy"),
  agentCatalog: () => import("../components/agent/useAgentCatalog"),
  providerReads: async () => ({
    settings: await import("../shell/providerSettings"),
    views: await import("../shell/agentViews"),
  }),
  declarationsList: () =>
    import("../components/modelo/declarations/useDeclarationsList"),
  tauriHost: () => import("../shell/tauriHost"),
  hostCall: () => import("../shell/hostCall"),
  sessionGate: async () => ({
    react: await import("react"),
    dom: await import("react-dom"),
    client: await import("react-dom/client"),
    gate: await import("../shell/sessionGate"),
    run: await import("../shell/aeatSyncRun"),
    signIn: await import("../shell/signIn"),
  }),
  profileViews: async () => ({
    react: await import("react"),
    dom: await import("react-dom"),
    client: await import("react-dom/client"),
    calendar: await import("../shell/calendar"),
    messages: await import("../shell/messages"),
  }),
  ledgerReads: async () => ({
    react: await import("react"),
    dom: await import("react-dom"),
    client: await import("react-dom/client"),
    documents: await import("../components/ledger/documents/useLedgerRead"),
    setup: await import("../components/ledger/setup/SetupParts"),
  }),
};

/** One mounted shell: a new run remounts it on a fresh host. */
type Run = { id: number; scenario: Scenario; language: string };

function remember(name: "scenario" | "lang", value: string) {
  const url = new URL(window.location.href);
  url.searchParams.set(name, value);
  window.history.replaceState(null, "", url);
}

function Scenarios() {
  const initial = useMemo(readParams, []);
  const [run, setRun] = useState<Run>({
    id: 0,
    scenario: initial.scenario,
    language: initial.language,
  });
  const [calls, setCalls] = useState<HostCallLine[]>([]);
  const nextCall = useRef(0);

  const restart = useCallback((change: Partial<Omit<Run, "id">> = {}) => {
    window.__scenarioHostCalls = [];
    setCalls([]);
    setRun((current) => ({ ...current, ...change, id: current.id + 1 }));
  }, []);

  const host = useMemo(() => {
    const origin = docsOrigin();
    return scenarioHost(run.scenario, {
      docs: origin
        ? {
            origin,
            languages: docsLanguages(origin, run.scenario.docsSearch),
          }
        : null,
      logRecords: initial.logRecords,
      logReplayGap: initial.logReplayGap,
      logFeedMs: initial.logFeedMs,
      logAttachFailures: initial.logAttachFailures,
      logLevel: initial.logLevel,
      calendar: initial.calendar,
      agentStream: initial.agentStream,
      agentAsks: initial.agentAsks,
      agentDocuments: initial.agentDocuments,
      agentSkills: initial.agentSkills,
      agentCatalog: initial.agentCatalog,
      localModels: initial.localModels,
      engineHealth: initial.engineHealth,
      engineChoices: initial.engineChoices,
      localEngine: initial.localEngine,
      setup: initial.setup,
      ledger: initial.ledger,
      modelo: initial.modelo,
      election: initial.election,
      borrador: initial.borrador,
      household: initial.household,
      window: initial.window,
      language: run.language,
      latencyMs: initial.latencyMs,
      onCall: (call) => {
        (window.__scenarioHostCalls ??= []).push(call);
        const id = nextCall.current++;
        setCalls((current) => [...current, { id, call }].slice(-CALL_LIMIT));
      },
    });
  }, [run, initial]);

  return (
    <>
      <App key={run.id} host={host} />
      {initial.bar && (
        <ScenarioBar
          scenario={run.scenario}
          language={run.language}
          languages={LANGUAGES}
          calls={calls}
          onScenario={(id) => {
            remember("scenario", id);
            restart({ scenario: findScenario(id) });
          }}
          onLanguage={(language) => {
            remember("lang", language);
            restart({ language });
          }}
          onRestart={() => restart()}
        />
      )}
    </>
  );
}

document.title = `${identity.name} · scenarios`;
const root = document.getElementById("root");
if (!root) throw new Error("Application root is missing.");
// A stylesheet lost to the connection serving it leaves the shell mounted
// unstyled, with controls off the page and every later failure blaming them.
// Module scripts run only once linked stylesheets have settled, so a link with
// no rules here will not get any. A failed link still holds a sheet: reading
// its rules throws, which is the only sign the browser leaves of the failure.
function hasRules(link: HTMLLinkElement): boolean {
  try {
    return (link.sheet?.cssRules.length ?? 0) > 0;
  } catch {
    return false;
  }
}
const undelivered = Array.from(
  document.querySelectorAll<HTMLLinkElement>('link[rel="stylesheet"]'),
)
  .filter((link) => !hasRules(link))
  .map((link) => link.href);
if (undelivered.length > 0) {
  const refusal = document.createElement("p");
  refusal.setAttribute("role", "alert");
  refusal.textContent = `Stylesheet did not load: ${undelivered.join(", ")}`;
  root.replaceChildren(refusal);
  throw new Error(refusal.textContent);
}
// Strict mode runs every effect twice in development, which is how a missing
// cleanup shows itself here instead of in the desktop window.
const shell = ReactDOM.createRoot(root);
// Reevaluating this entry must remove the previous shell's effects and portals
// before a new root mounts, including when Fast Refresh requests a full reload.
import.meta.hot?.dispose(() => shell.unmount());
shell.render(
  <StrictMode>
    <Scenarios />
  </StrictMode>,
);
