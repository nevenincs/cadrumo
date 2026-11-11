import { expect, test } from "@playwright/test";
import type {
  SetupBlockedReason,
  SetupFailureCategory,
  SetupItemKind,
  SetupRecovery,
  SetupRow,
  SetupStaleReason,
  SetupState,
} from "../src/ipc/componentSetup";
import {
  actionWords,
  failureWords,
  itemName,
  refusalWords,
  rowSentence,
} from "../src/components/setup/setupWords";

// What the setup window says of a refused command, read through a translator
// that returns the key it is asked for. No page is opened.

const KEYS = (key: string) => key;

test("each code the setup host refuses a command with has a sentence of its own", () => {
  const codes = [
    "not_signed_in",
    "busy",
    "plan_changed",
    "not_pending",
    "not_cancellable",
    "unavailable",
    "model_selection_unusable",
    "browser_not_removed",
    "local_ai_not_removed",
  ];

  const keys = codes.map((code) => refusalWords(KEYS, code));

  expect(new Set(keys).size).toBe(codes.length);
  expect(keys).not.toContain("desktop.setup.refused_other");
});

test("a refused local model selection says what to do about the selection, not that setup was unreachable", () => {
  expect(refusalWords(KEYS, "model_selection_unusable")).toBe(
    "desktop.setup.refused_model_selection_unusable",
  );
});

test("a code the window does not know gets the general sentence", () => {
  expect(refusalWords(KEYS, "a_code_from_a_newer_host")).toBe(
    "desktop.setup.refused_other",
  );
});

// The setup words are looked up in tables written with whole keys. Each
// member of a closed value must reach the key of its own family, and a value
// the host sends that the window does not know must read as a sentence, never
// as a key built from the value.

const STATES: SetupState[] = [
  "absent",
  "provisioning",
  "verifying",
  "ready",
  "stale",
  "failed",
  "blocked",
  "unknown",
];
const STALE_REASONS: SetupStaleReason[] = ["older_revision", "program_too_old"];
const BLOCKED_REASONS: SetupBlockedReason[] = [
  "offline",
  "needs_person",
  "hardware",
  "not_in_this_build",
];
const FAILURES: SetupFailureCategory[] = [
  "offline",
  "host_unreachable",
  "server_error",
  "secure_connection_failed",
  "blocked_by_network",
  "disk_full",
  "no_permission",
  "damaged_download",
  "not_enough_memory",
  "memory_busy",
  "program_missing",
  "program_not_running",
  "engine_program_unusable",
  "engine_package_damaged",
  "interrupted",
  "needs_sign_in",
  "not_in_this_build",
  "cancelled",
  "unexpected",
];
const RECOVERIES: SetupRecovery[] = [
  "set_up",
  "update",
  "try_again",
  "resume",
  "check_again",
  "reinstall_engine_program",
];
const ITEMS: SetupItemKind[] = ["browser", "local_ai"];

function row(fields: Partial<SetupRow>): SetupRow {
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

/** A value the host could send that this window has no word for. */
const FROM_A_NEWER_HOST = "from_a_newer_host" as never;

test("every row state is said by the key of its own state", () => {
  for (const state of STATES) {
    expect(rowSentence(KEYS, row({ state }))).toBe(
      `desktop.setup.state.${state}`,
    );
  }
});

test("a stale or blocked row says its reason, and a failed row says its failure", () => {
  for (const reason of STALE_REASONS) {
    expect(
      rowSentence(KEYS, row({ state: "stale", stale_reason: reason })),
    ).toBe(`desktop.setup.stale.${reason}`);
  }
  for (const reason of BLOCKED_REASONS) {
    expect(
      rowSentence(KEYS, row({ state: "blocked", blocked_reason: reason })),
    ).toBe(`desktop.setup.blocked.${reason}`);
  }
  for (const failure of FAILURES) {
    expect(rowSentence(KEYS, row({ state: "failed", failure }))).toBe(
      `desktop.setup.failure.${failure}`,
    );
    expect(failureWords(KEYS, failure)).toBe(
      `desktop.setup.failure.${failure}`,
    );
  }
});

test("every recovery has the button words of its own recovery", () => {
  for (const recovery of RECOVERIES) {
    expect(actionWords(KEYS, recovery)).toBe(
      `desktop.setup.action.${recovery}`,
    );
  }
  expect(actionWords(KEYS, null)).toBeNull();
});

test("every item is named by the key of its own item", () => {
  for (const item of ITEMS) {
    expect(itemName(KEYS, item)).toBe(`desktop.setup.item.${item}`);
  }
});

test("a state, reason, failure, recovery or item the window does not know never reads as a built key", () => {
  expect(rowSentence(KEYS, row({ state: FROM_A_NEWER_HOST }))).toBe(
    "desktop.setup.state.unknown",
  );
  expect(
    rowSentence(KEYS, row({ state: "stale", stale_reason: FROM_A_NEWER_HOST })),
  ).toBe("desktop.setup.state.stale");
  expect(
    rowSentence(
      KEYS,
      row({ state: "blocked", blocked_reason: FROM_A_NEWER_HOST }),
    ),
  ).toBe("desktop.setup.state.blocked");
  expect(failureWords(KEYS, FROM_A_NEWER_HOST)).toBe(
    "desktop.setup.failure.unexpected",
  );
  expect(actionWords(KEYS, FROM_A_NEWER_HOST)).toBeNull();
  expect(itemName(KEYS, FROM_A_NEWER_HOST)).toBe("desktop.setup.title");
});

test("a value named like an inherited property is not a member", () => {
  const inherited = "constructor" as never;
  expect(failureWords(KEYS, inherited)).toBe(
    "desktop.setup.failure.unexpected",
  );
  expect(actionWords(KEYS, inherited)).toBeNull();
  expect(itemName(KEYS, inherited)).toBe("desktop.setup.title");
});
