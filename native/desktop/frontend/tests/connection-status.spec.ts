import { expect, test } from "@playwright/test";
import type { SetupRow, SetupState } from "../src/ipc/componentSetup";
import type { AgentEngineHealth } from "../src/shell/agentSession";
import {
  connectionStatus,
  localLaneDetail,
} from "../src/components/settings/connectionStatus";
import type { ProviderStatus } from "../src/components/settings/types";

// What a keyless lane on this computer shows, read through a translator that
// returns the key it is asked for. No page is opened. Which local AI is set
// up, and whether its engine runs, sleeps or failed to start, the setup host
// serves as the row; these cases check only that the lane renders that row.

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

test("a local lane is ready exactly when its served setup row is, whatever the engine answers", () => {
  const states: SetupState[] = [
    "absent",
    "provisioning",
    "verifying",
    "stale",
    "failed",
    "blocked",
    "unknown",
  ];
  for (const engine of [RUNNING, NOT_RUNNING, null]) {
    expect(connectionStatus(LANE, engine, setup({}))).toBe("ready");
    for (const state of states) {
      expect(connectionStatus(LANE, engine, setup({ state }))).toBe(
        "setup_needed",
      );
    }
  }
});

test("a local lane says its served setup row in the setup's own words", () => {
  expect(localLaneDetail(KEYS, setup({ state: "absent" }))).toBe(
    "desktop.setup.state.absent",
  );
  expect(localLaneDetail(KEYS, setup({ server: "dormant" }))).toBe(
    "desktop.setup.ready_dormant",
  );
  expect(
    localLaneDetail(
      KEYS,
      setup({ state: "failed", failure: "program_not_running" }),
    ),
  ).toBe("desktop.setup.failure.program_not_running");
});

test("a lane turned off, or with no setup row, reads as before", () => {
  expect(
    connectionStatus(
      { ...LANE, mode: "disabled" },
      RUNNING,
      setup({ state: "absent" }),
    ),
  ).toBe("off");
  expect(connectionStatus(LANE, RUNNING, null)).toBe("ready");
  expect(connectionStatus(LANE, NOT_RUNNING, null)).toBe("engine_not_running");
  expect(connectionStatus(LANE, null, null)).toBe("not_checked");
  expect(localLaneDetail(KEYS, null)).toBeNull();
});
