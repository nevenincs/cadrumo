import { expect, test } from "@playwright/test";
import type { SetupRow } from "../src/ipc/componentSetup";
import type { AgentEngineHealth } from "../src/shell/agentSession";
import {
  connectionStatus,
  localLaneDetail,
} from "../src/components/settings/connectionStatus";
import type { ProviderStatus } from "../src/components/settings/types";

// What a keyless lane on this computer says, read through a translator that
// returns the key it is asked for. No page is opened.

const KEYS = (key: string) => key;

const LANE: ProviderStatus = {
  id: "synthetic_local_api",
  provider: "synthetic-local",
  name: "Synthetic local",
  transport: "api",
  authKind: "none",
  mode: "unset",
  readiness: "not_verified",
  source: "none",
};

const RUNNING: AgentEngineHealth = {
  engine: "llamacpp",
  state: "running",
  reason: null,
  door: null,
};

const NOT_RUNNING: AgentEngineHealth = {
  engine: "llamacpp",
  state: "not_running",
  reason: "not_reachable",
  door: "local_ai_setup",
};

function setup(fields: Partial<SetupRow>): SetupRow {
  return {
    item: "local_ai",
    kind: "local_ai",
    mode: "quick",
    state: "ready",
    stale_reason: null,
    blocked_reason: null,
    failure: null,
    recovery: null,
    recovery_action_id: null,
    version: null,
    size_bytes: null,
    removals: [],
    ...fields,
  };
}

test("a local lane with no model file to run is not set up, even while its engine answers", () => {
  const absent = setup({ state: "absent" });
  for (const engine of [RUNNING, NOT_RUNNING, null]) {
    const status = connectionStatus(LANE, engine, absent);
    expect(status).toBe("setup_needed");
    expect(localLaneDetail(KEYS, status, absent)).toBe(
      "desktop.setup.state.absent",
    );
  }
});

test("a set-up local lane is ready while its engine runs, and while it sleeps until a document is read", () => {
  const ready = setup({});
  expect(connectionStatus(LANE, RUNNING, ready)).toBe("ready");
  expect(localLaneDetail(KEYS, "ready", ready)).toBeNull();

  const dormant = setup({ server: "dormant" });
  const status = connectionStatus(LANE, NOT_RUNNING, dormant);
  expect(status).toBe("ready");
  expect(localLaneDetail(KEYS, status, dormant)).toBe(
    "desktop.setup.ready_dormant",
  );
});

test("a set-up local lane whose server should run but does not answer says its engine is not running", () => {
  expect(connectionStatus(LANE, NOT_RUNNING, setup({}))).toBe(
    "engine_not_running",
  );
});

test("a lane turned off, or with no local AI row, reads as before", () => {
  expect(
    connectionStatus(
      { ...LANE, mode: "disabled" },
      RUNNING,
      setup({ state: "absent" }),
    ),
  ).toBe("off");
  expect(connectionStatus(LANE, RUNNING, null)).toBe("ready");
  expect(connectionStatus(LANE, null, null)).toBe("not_checked");
  expect(localLaneDetail(KEYS, "ready", null)).toBeNull();
});
