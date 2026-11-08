import { expect, test } from "@playwright/test";
import type { AgentLocalEngine } from "../src/ipc/contract";
import {
  engineRefusalWords,
  heldBackByEngine,
  lanesForEngine,
} from "../src/shell/localModelLanes";

// Which local lanes are offered for the selected engine: an engine's lane
// only while it is the selected one, every other lane unchanged, and nothing
// held back while no readable engine is known.

const lane = (provider: string) => ({ id: `${provider}_api`, provider });
const LANES = [lane("local"), lane("ollama"), lane("llamacpp"), lane("alpha")];
const readable = (engine: "llamacpp" | "ollama"): AgentLocalEngine => ({
  state: "readable",
  engine,
  placement: "auto",
  revision: "r1",
});
const providers = (engine: AgentLocalEngine | null) =>
  lanesForEngine(LANES, engine).map((held) => held.provider);

test("the selected engine's lane is offered and the other engine's is not", () => {
  expect(providers(readable("ollama"))).toEqual(["local", "ollama", "alpha"]);
  expect(providers(readable("llamacpp"))).toEqual([
    "local",
    "llamacpp",
    "alpha",
  ]);
});

test("nothing is held back without a readable engine", () => {
  expect(providers(null)).toEqual(["local", "ollama", "llamacpp", "alpha"]);
  expect(providers({ state: "unreadable", revision: "r1" })).toEqual([
    "local",
    "ollama",
    "llamacpp",
    "alpha",
  ]);
});

test("a lane that is no engine's is never held back", () => {
  expect(heldBackByEngine(lane("alpha"), readable("ollama"))).toBe(false);
  expect(heldBackByEngine(lane("llamacpp"), readable("ollama"))).toBe(true);
  expect(heldBackByEngine(lane("ollama"), readable("ollama"))).toBe(false);
});

test("a refusal with a word of its own says it, any other says the change failed", () => {
  const t = (key: string) => key;
  expect(engineRefusalWords(t, "agent_local_models_revision_conflict")).toBe(
    "desktop.providers.local_models_refused_revision_conflict",
  );
  expect(
    engineRefusalWords(t, "agent_local_models_committed_readback_failed"),
  ).toBe("desktop.providers.local_models_refused_committed_readback_failed");
  expect(engineRefusalWords(t, "agent_local_models_catalog_unavailable")).toBe(
    "desktop.providers.local_models_refused_catalog_unavailable",
  );
  expect(engineRefusalWords(t, "agent_local_models_unknown")).toBe(
    "desktop.providers.local_models_refused_unknown",
  );
  expect(engineRefusalWords(t, "agent_local_models_full")).toBe(
    "desktop.providers.local_engine_change_failed",
  );
  expect(engineRefusalWords(t, "something_else")).toBe(
    "desktop.providers.local_engine_change_failed",
  );
});
