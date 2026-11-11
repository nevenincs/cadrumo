import { expect, test } from "@playwright/test";
import { engineRefusalWords } from "../src/shell/localModelLanes";

// The words that say why the engine or placement was not changed.

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
  expect(engineRefusalWords(t, "agent_local_engine_unavailable")).toBe(
    "desktop.providers.local_engine_unavailable",
  );
  expect(engineRefusalWords(t, "agent_local_models_full")).toBe(
    "desktop.providers.local_engine_change_failed",
  );
  expect(engineRefusalWords(t, "something_else")).toBe(
    "desktop.providers.local_engine_change_failed",
  );
});
