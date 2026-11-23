import { expect, test } from "@playwright/test";
import type { AgentEngineHealth } from "../src/shell/agentSession";
import { laneStatus, type LaneStanding } from "../src/shell/agentOffer";

// A lane's status and reason, read from each served settings record the
// service projects (resolution.py `_availability` and `status_entry`): the
// expected values are written out by hand, one per served state. No page is
// opened.

const KEY_MISSING: LaneStanding = {
  authKind: "api_key",
  mode: "unset",
  readiness: "missing",
  available: false,
  reason: "not_configured",
};

const KEY_STORED: LaneStanding = {
  authKind: "api_key",
  mode: "key",
  readiness: "not_verified",
  available: true,
};

const APP_SIGNED_IN: LaneStanding = {
  authKind: "provider_sign_in_only",
  mode: "provider_sign_in",
  readiness: "not_verified",
  available: true,
  cliState: "installed_signed_in",
};

const APP_SIGNED_OUT: LaneStanding = {
  authKind: "provider_sign_in_only",
  mode: "unset",
  readiness: "sign_in_required",
  available: false,
  reason: "sign_in_with_provider_tool",
  cliState: "installed_signed_out",
};

const KEYLESS: LaneStanding = {
  authKind: "none",
  mode: "unset",
  readiness: "not_verified",
  available: true,
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

test("a key lane reads as not set up without a key, and as a saved key with one, never as ready", () => {
  expect(laneStatus(KEY_MISSING, null, null)).toEqual({
    status: "setup_needed",
    reason: "add_key",
  });
  expect(laneStatus(KEY_STORED, null, null)).toEqual({
    status: "saved",
    reason: "key_saved",
  });
  expect(
    laneStatus(
      { ...KEY_STORED, authKind: "api_key_with_base_url", mode: "oauth_token" },
      null,
      null,
    ),
  ).toEqual({ status: "saved", reason: "key_saved" });
});

test("a lane turned off is off whatever else it serves, and an unreadable record says so first", () => {
  for (const lane of [KEY_STORED, APP_SIGNED_IN, KEYLESS])
    expect(
      laneStatus(
        {
          ...lane,
          mode: "disabled",
          readiness: "disabled",
          available: false,
          reason: "turned_off",
        },
        RUNNING,
        true,
      ),
    ).toEqual({ status: "off", reason: "turned_off" });
  expect(
    laneStatus(
      {
        ...KEY_MISSING,
        readiness: "unusable",
        reason: "record_unreadable",
      },
      null,
      null,
    ),
  ).toEqual({ status: "setup_needed", reason: "record_unreadable" });
});

test("a lane signing in through its app stands on what the service found of the app", () => {
  expect(laneStatus(APP_SIGNED_IN, null, null)).toEqual({
    status: "signed_in",
    reason: "signed_in",
  });
  expect(laneStatus(APP_SIGNED_OUT, null, null)).toEqual({
    status: "sign_in_needed",
    reason: "sign_in",
  });
  expect(
    laneStatus(
      {
        ...APP_SIGNED_OUT,
        readiness: "unusable",
        reason: "not_configured",
        cliState: "not_installed",
      },
      null,
      null,
    ),
  ).toEqual({ status: "setup_needed", reason: "app_missing" });
  expect(
    laneStatus(
      {
        ...APP_SIGNED_OUT,
        cliState: "unknown",
        cliStateCause: "probe_timed_out",
      },
      null,
      null,
    ),
  ).toEqual({ status: "unconfirmed", reason: "app_unconfirmed" });
  expect(
    laneStatus({ ...APP_SIGNED_OUT, cliState: "unknown" }, null, null),
  ).toEqual({ status: "sign_in_needed", reason: "sign_in" });
  // A key lane the person chose to sign in to through the provider's app.
  expect(
    laneStatus({ ...APP_SIGNED_IN, authKind: "api_key" }, null, null),
  ).toEqual({ status: "signed_in", reason: "signed_in" });
});

test("a lane on this computer is ready exactly when its served setup row is, else as its engine measured", () => {
  for (const engine of [RUNNING, NOT_RUNNING, null]) {
    expect(laneStatus(KEYLESS, engine, true)).toEqual({
      status: "ready",
      reason: "local_ready",
    });
    expect(laneStatus(KEYLESS, engine, false)).toEqual({
      status: "setup_needed",
      reason: "local_setup",
    });
  }
  expect(laneStatus(KEYLESS, RUNNING, null)).toEqual({
    status: "ready",
    reason: "local_ready",
  });
  expect(laneStatus(KEYLESS, NOT_RUNNING, null)).toEqual({
    status: "engine_not_running",
    reason: "engine_not_running",
  });
  expect(laneStatus(KEYLESS, null, null)).toEqual({
    status: "not_checked",
    reason: "not_checked",
  });
});
