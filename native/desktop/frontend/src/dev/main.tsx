// The development entry: the production `App`, mounted on the scenario host.
// Only scenarios.html loads this module, and the production build takes
// index.html alone as its input, so nothing here reaches the product.

import { StrictMode, useCallback, useMemo, useRef, useState } from "react";
import ReactDOM from "react-dom/client";
import { identity } from "virtual:desktop-content";
import { port as docsPort } from "virtual:docs-fixture";
import { App } from "../App";
import type { DocsLanguage } from "../ipc/contract";
import "./index.css";
import { ScenarioBar, type HostCallLine } from "./ScenarioBar";
import { scenarioHost } from "./scenarioHost";
import { findScenario, type Scenario } from "./scenarios";

import.meta.glob("../generated/palette.css", { eager: true });

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
    // A batch of records every this many milliseconds, for a log that grows.
    logFeedMs: Math.max(0, Math.trunc(Number(params.get("feed")) || 0)),
  };
}

declare global {
  interface Window {
    /** Every host call of the current run, in order, for the scenario tests. */
    __scenarioHostCalls?: string[];
  }
}

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
      logFeedMs: initial.logFeedMs,
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
// Strict mode runs every effect twice in development, which is how a missing
// cleanup shows itself here instead of in the desktop window.
ReactDOM.createRoot(root).render(
  <StrictMode>
    <Scenarios />
  </StrictMode>,
);
