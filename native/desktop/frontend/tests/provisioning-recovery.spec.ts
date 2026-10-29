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

// The setup action a refusal stands for, from its plain shape: an agent
// tool's refusal that names it, a settled operation's registered error code,
// a statement file or a label reading that stood because the local AI could
// not read, or a batch whose reading paused. And the ledger port that hands
// each such refusal to the window's provisioning panel once. The scenario
// ledger needs a window; a bare one stands in for it here. No page is opened.

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

/** A settled operation's registered error detail, refused with `code`. */
const detail = (code: string | null) => ({
  detail_version: 1,
  kind: "registered_error",
  error_code: code,
  message_key: null,
  context: [],
  context_entries_omitted: 0,
  precondition_verdict_json: null,
});

test("the setup action is found in every plain shape of a refusal", () => {
  expect(
    provisionActionOf({
      code: "operation_not_successful",
      recovery_action_id: "operator.provision.browser",
    }),
  ).toBe("operator.provision.browser");
  expect(provisionActionOf(detail("REFUSED_LEDGER_EVIDENCE_READER"))).toBe(
    LOCAL_AI_SETUP_ACTION,
  );
  expect(provisionActionOf(detail("REFUSED_BROWSER_NOT_READY"))).toBe(
    "operator.provision.browser",
  );
  expect(provisionActionOf({ code: "REFUSED_BROWSER_NOT_READY" })).toBe(
    "operator.provision.browser",
  );
  expect(
    provisionActionOf({
      cause: "reader_unavailable",
      unread_fields: ["grand_total"],
      reader_error_type: "InvoiceDraftReaderUnavailableError",
    }),
  ).toBe(LOCAL_AI_SETUP_ACTION);
  expect(
    provisionActionOf({
      file_name: "movimientos-tarjeta.pdf",
      reason_code: "reader_unavailable",
    }),
  ).toBe(LOCAL_AI_SETUP_ACTION);
  // Setup as a whole is a setup action too; where it leads is the window's.
  expect(provisionActionOf("operator.provision.setup")).toBe(
    "operator.provision.setup",
  );
});

test("a refusal that stands for no component, or names it malformed, has none", () => {
  expect(provisionActionOf(detail("ERROR_EVIDENCE_NOT_FOUND"))).toBeNull();
  expect(provisionActionOf(detail(null))).toBeNull();
  expect(provisionActionOf(null)).toBeNull();
  expect(provisionActionOf({ code: "refused" })).toBeNull();
  expect(provisionActionOf({ code: "toString" })).toBeNull();
  expect(
    provisionActionOf({
      cause: "load_headroom_refused",
      unread_fields: [],
      reader_error_type: "LLMContentionError",
    }),
  ).toBeNull();
  expect(
    provisionActionOf({ file_name: "a.csv", reason_code: "source_changed" }),
  ).toBeNull();
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

test("each ledger refusal that stands for a setup reaches the prompt once, unchanged", async () => {
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
  await routed.submit("ledger.evidence.list", {});
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
      // The batch settles: its pause stands for the local AI's setup.
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
  expect(pausedActionOf({ run: { inference_pause: null } })).toBeNull();
  expect(pausedActionOf(null)).toBeNull();
});

test("a ledger refusal that names no setup offers nothing", async () => {
  // With the reader present the scan is read; a refusal for something else
  // names nothing either.
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
