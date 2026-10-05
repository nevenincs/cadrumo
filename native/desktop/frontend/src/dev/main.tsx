// The development entry: the production `App`, mounted on the scenario host.
// Only scenarios.html loads this module, and the production build takes
// index.html alone as its input, so nothing here reaches the product.

import { useCallback, useMemo, useState } from "react";
import ReactDOM from "react-dom/client";
import { identity } from "virtual:desktop-content";
import { App } from "../App";
import type { DocsLanguage } from "../ipc/contract";
import "../tokens.css";
import "../styles.css";
import "./dev.css";
import { ScenarioBar } from "./ScenarioBar";
import { scenarioHost } from "./scenarioHost";
import { findScenario, type Scenario } from "./scenarios";

import.meta.glob("../generated/palette.css", { eager: true });

const LANGUAGES = ["en", "es", "ca", "hu"] as const;
const CALL_LIMIT = 40;
const DEFAULT_LATENCY_MS = 600;

// The documentation fixture is served by this same development server. The
// other loopback name makes it a different origin, as the documentation is in
// the desktop window.
function docsOrigin(): string {
  const name =
    window.location.hostname === "127.0.0.1" ? "localhost" : "127.0.0.1";
  return `${window.location.protocol}//${name}:${window.location.port}`;
}

function docsLanguages(origin: string, search: string): DocsLanguage[] {
  return LANGUAGES.map((code) => ({
    code,
    entry: `${origin}/docs-fixture/${code === "en" ? "" : `${code}/`}index.html?search=${search}`,
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
  };
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
  const [calls, setCalls] = useState<string[]>([]);

  const restart = useCallback((change: Partial<Omit<Run, "id">> = {}) => {
    setCalls([]);
    setRun((current) => ({ ...current, ...change, id: current.id + 1 }));
  }, []);

  const host = useMemo(() => {
    const origin = docsOrigin();
    return scenarioHost(run.scenario, {
      docs: {
        origin,
        languages: docsLanguages(origin, run.scenario.docsSearch),
      },
      language: run.language,
      latencyMs: initial.latencyMs,
      onCall: (call) =>
        setCalls((current) => [...current, call].slice(-CALL_LIMIT)),
    });
  }, [run, initial.latencyMs]);

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
ReactDOM.createRoot(root).render(<Scenarios />);
