import { expect, test } from "@playwright/test";
import {
  pausedActionOf,
  provisionActionOf,
  routeCensoRefusals,
  routeProvisioningRefusals,
} from "../src/shell/provisioningRecovery";
import type { LedgerPort } from "../src/shell/ledger";
import { setupTargetOf } from "../src/shell/setup";
import type { SetupRow } from "../src/ipc/contract";

/** The action the engine names as the local AI's recovery. */
const LOCAL_AI_SETUP_ACTION = "operator.provision.local_ai";

// The setup action a refusal names, wherever its shape carries it: an agent
// tool's refusal, a settled operation's error detail with the verdict as its
// JSON text, a verdict snapshot, or a label reading that stood without its
// model fill. And the ledger port that hands each refusal naming one to the
// window's provisioning panel once. The scenario ledger needs a window; a bare one
// stands in for it here. No page is opened.

const stand = globalThis as unknown as { window?: unknown };
stand.window = {
  location: { search: "" },
  setTimeout: globalThis.setTimeout,
};
const { ledgerFixture } = await import("../src/dev/ledgerFixture");
const { censoFixture } = await import("../src/dev/censoFixture");
/** The scenario Censo pull reads the profile only to check readiness and to
 * apply a review, neither of which a start or a status read does. */
const unreadProfile = {} as unknown as Parameters<typeof censoFixture>[0];

/** A verdict as the product serializes it, recovered by `action`. */
const verdict = (action: string | null) => ({
  failed_condition_id: "provisioning.role_model.installed",
  evidence: [],
  action: action === null ? null : { action_id: action },
  argument_bindings: [],
  missing_argument_names: [],
  conditionality: action === null ? "no_recovery" : "immediate",
  no_recovery_outcome: action === null ? "not_recoverable" : null,
});
const detail = (verdictJson: string | null) => ({
  detail_version: 1,
  kind: "registered_error",
  error_code: "REFUSED_LEDGER_EVIDENCE_READER",
  message_key: "errors.refused.refused_ledger_evidence_reader_unavailable",
  context: [],
  context_entries_omitted: 0,
  precondition_verdict_json: verdictJson,
});

test("the setup action is found in every shape a refusal carries it", () => {
  expect(
    provisionActionOf({
      code: "operation_not_successful",
      recovery_action_id: "operator.provision.browser",
    }),
  ).toBe("operator.provision.browser");
  expect(
    provisionActionOf(
      detail(JSON.stringify(verdict("operator.provision.local_ai"))),
    ),
  ).toBe("operator.provision.local_ai");
  expect(
    provisionActionOf({
      failed_condition_id: "provisioning.runtime.installed",
      action_id: "operator.provision.local_ai",
    }),
  ).toBe("operator.provision.local_ai");
  expect(
    provisionActionOf({
      cause: "reader_unavailable",
      unread_fields: ["grand_total"],
      reader_error_type: "InvoiceDraftReaderUnavailableError",
      recovery_action_id: LOCAL_AI_SETUP_ACTION,
    }),
  ).toBe(LOCAL_AI_SETUP_ACTION);
  // Setup as a whole is a setup action too; where it leads is the window's.
  expect(provisionActionOf("operator.provision.setup")).toBe(
    "operator.provision.setup",
  );
});

test("a refusal that names no setup, or names it malformed, has none", () => {
  // A verdict with no recovery, and one recovered by something else.
  expect(provisionActionOf(detail(JSON.stringify(verdict(null))))).toBeNull();
  expect(
    provisionActionOf(
      detail(JSON.stringify(verdict("operator.ledger.classify"))),
    ),
  ).toBeNull();
  expect(provisionActionOf(detail(null))).toBeNull();
  expect(provisionActionOf(detail("{not json"))).toBeNull();
  expect(provisionActionOf(null)).toBeNull();
  expect(provisionActionOf({ code: "refused" })).toBeNull();
  for (const malformed of [
    "operator.provision.",
    "operator.provision.Browser",
    "operator.provision.browser now",
    `operator.provision.${"a".repeat(128)}`,
    "provision.browser",
  ])
    expect(provisionActionOf({ recovery_action_id: malformed })).toBeNull();
});

/** The scenario ledger on a computer without its local AI, and the image
 * among its documents, which only that reader can read. */
async function missingReader(shape: "reader_missing" | "documents") {
  const port = ledgerFixture({
    say: () => undefined,
    wait: async () => undefined,
    signedIn: () => true,
    shape,
  });
  const listed = await port.submit("ledger.evidence.list", {});
  if (listed.kind !== "settled") throw new Error("the list did not settle");
  const scan = listed.result.rows.find(
    (record) => record.media_kind === "image",
  );
  if (!scan) throw new Error("the ledger has no scan");
  return { port, scan: scan.evidence_id };
}

test("each ledger refusal that names a setup reaches the prompt once, unchanged", async () => {
  const { port, scan } = await missingReader("reader_missing");
  const offered: string[] = [];
  const routed: LedgerPort = routeProvisioningRefusals(port, (action) => {
    offered.push(action);
  });
  const refused = await routed.submit("ledger.evidence.extract", {
    evidence_id: scan,
  });
  expect(refused.kind).toBe("refused");
  expect(offered).toEqual([LOCAL_AI_SETUP_ACTION]);
  // The page still reads the refusal as the host gave it.
  if (refused.kind !== "refused") throw new Error("not refused");
  expect(refused.reason).toBe("REFUSED_LEDGER_EVIDENCE_READER");
  // Observed again, the same operation is not offered twice; a new one is.
  await routed.observe(refused.operation_id);
  expect(offered).toHaveLength(1);
  await routed.submit("ledger.evidence.extract", { evidence_id: scan });
  expect(offered).toHaveLength(2);
  // A read that settles offers nothing.
  await routed.submit("ledger.evidence.reader-readiness", {});
  expect(offered).toHaveLength(2);
});

test("a batch whose reading the missing local AI paused reaches the prompt once", async () => {
  for (const shape of ["reader_missing", "documents"] as const) {
    const port = ledgerFixture({
      say: () => undefined,
      wait: async () => undefined,
      signedIn: () => true,
      shape,
    });
    const offered: string[] = [];
    const routed = routeProvisioningRefusals(port, (action) => {
      offered.push(action);
    });
    const picked = await routed.pickFiles("documents", "files", "documents");
    const scans = picked.files.filter(
      (file) => !/\.(pdf|xml)$/i.test(file.name),
    );
    expect(scans.length).toBeGreaterThan(0);
    const added = await routed.submit("ledger.evidence.batch", {
      sources: scans.map((file) => file.token),
      direction: "received",
    });
    if (added.kind !== "settled") throw new Error("the batch did not settle");
    const paused = added.result.run.items.filter(
      (item) => item.status === "paused",
    );
    if (shape === "reader_missing") {
      // The batch settles: its pause names the local AI's setup.
      expect(paused).toHaveLength(scans.length);
      expect(pausedActionOf(added.result)).toBe(LOCAL_AI_SETUP_ACTION);
      expect(offered).toEqual([LOCAL_AI_SETUP_ACTION]);
      await routed.observe(added.operation_id);
      expect(offered).toHaveLength(1);
    } else {
      // With the local AI there, nothing pauses and nothing is offered.
      expect(paused).toHaveLength(0);
      expect(pausedActionOf(added.result)).toBeNull();
      expect(offered).toEqual([]);
    }
  }
  // A pause whose verdict names no action names nothing.
  expect(
    pausedActionOf({
      run: {
        inference_pause: { facts: [], precondition_verdict: verdict(null) },
      },
    }),
  ).toBeNull();
  expect(pausedActionOf({ run: { inference_pause: null } })).toBeNull();
  expect(pausedActionOf(null)).toBeNull();
});

test("a ledger refusal that names no setup offers nothing", async () => {
  // With the reader present the scan is read; a refusal whose detail holds
  // no verdict names nothing either.
  const { port, scan } = await missingReader("documents");
  const offered: string[] = [];
  const routed = routeProvisioningRefusals(port, (action) => {
    offered.push(action);
  });
  const read = await routed.submit("ledger.evidence.extract", {
    evidence_id: scan,
  });
  expect(read.kind).toBe("settled");
  const missing = await routed.submit("ledger.evidence.extract", {
    evidence_id: "0".repeat(64),
  });
  expect(missing.kind).toBe("refused");
  expect(offered).toEqual([]);
});

test("each Censo pull that stops for a missing component reaches the prompt once, unchanged", async () => {
  const offered: string[] = [];
  const routed = routeCensoRefusals(
    censoFixture(unreadProfile, "browser_missing"),
    (action) => offered.push(action),
  );
  const first = await routed.start("profile");
  expect(first.state).toBe("failed");
  expect(offered).toEqual(["operator.provision.browser"]);
  // Read again, the same pull is not offered twice; a new pull is.
  await routed.status("profile", first.operation);
  expect(offered).toHaveLength(1);
  const second = await routed.start("profile");
  expect(second.operation).not.toBe(first.operation);
  expect(offered).toEqual([
    "operator.provision.browser",
    "operator.provision.browser",
  ]);
});

test("a Censo pull that reaches its review offers nothing", async () => {
  const offered: string[] = [];
  const routed = routeCensoRefusals(
    censoFixture(unreadProfile, "ready"),
    (action) => offered.push(action),
  );
  expect((await routed.start("profile")).state).toBe("review");
  expect(offered).toEqual([]);
});

/** A local AI row as the host sends it, in `state`. */
const localAiRow = (
  state: SetupRow["state"],
  blocked: SetupRow["blocked_reason"] = null,
): SetupRow => ({
  item: "local_ai",
  kind: "local_ai",
  mode: "quick",
  state,
  stale_reason: null,
  blocked_reason: blocked,
  failure: null,
  recovery: state === "absent" ? "set_up" : null,
  recovery_action_id: state === "absent" ? LOCAL_AI_SETUP_ACTION : null,
  version: null,
  size_bytes: null,
});

test("an item's setup leads to its row, and nowhere while the status has no row", () => {
  const absent = localAiRow("absent");
  const blocked = localAiRow("blocked", "hardware");
  expect(setupTargetOf(LOCAL_AI_SETUP_ACTION, [absent])).toBe(absent);
  // A blocked row is still the target: the surface says its sentence and
  // offers nothing to press.
  expect(setupTargetOf(LOCAL_AI_SETUP_ACTION, [blocked])).toBe(blocked);
  // Loading or unreadable: no row says whether setup could act, so the
  // item's setup leads nowhere, never to setup as a whole.
  expect(setupTargetOf(LOCAL_AI_SETUP_ACTION, [])).toBeNull();
  expect(setupTargetOf("operator.provision.browser", [absent])).toBeNull();
  // Setup as a whole still leads there, and other actions nowhere.
  expect(setupTargetOf("operator.provision.setup", [])).toBe("general");
  expect(setupTargetOf("operator.ledger.classify", [absent])).toBeNull();
});

test("a row that names its recovery is found by that action alone", () => {
  // The engine names the action; the window routes by it, not by a list of
  // its own.
  const named = {
    ...localAiRow("absent"),
    recovery_action_id: "operator.provision.local_ai_program",
  };
  expect(setupTargetOf("operator.provision.local_ai_program", [named])).toBe(
    named,
  );
  expect(setupTargetOf(LOCAL_AI_SETUP_ACTION, [named])).toBeNull();
  // A row offering no recovery is still its own item's.
  const ready = localAiRow("ready");
  expect(setupTargetOf(LOCAL_AI_SETUP_ACTION, [named, ready])).toBe(ready);
});
