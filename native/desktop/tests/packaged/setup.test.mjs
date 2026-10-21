import assert from "node:assert/strict";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve, sep } from "node:path";
import { test } from "node:test";

import { Results } from "./results.mjs";
import {
  FREE_SPACE_FLOOR_BYTES,
  NO_TRANSFER_ALLOWANCE_BYTES,
  SETUP_VARIABLE,
  browserResumeVerdict,
  fingerprint,
  fingerprintChanges,
  freeSpaceVerdict,
  isolatedEnvironment,
  itemEvidenceVerdict,
  planApprovalVerdict,
  realStorageVerdict,
  recordItemEvidence,
  removeScratch,
  resumeVerdict,
  scratchLayout,
  secondSetupVerdict,
  setupHostVerdict,
  setupItemsFrom,
  treeBytes,
} from "./setup.mjs";
import { FAIL, PASS } from "./verdicts.mjs";

const testing = resolve(tmpdir(), "cadrumo-testing");
const run = resolve(testing, "cadrumo-setup-run");
const settled = "2026-10-18T12:00:00.000Z";
const later = "2026-10-18T12:05:00.000Z";
const earlier = "2026-10-18T11:55:00.000Z";
const fullCheck = { source: "full_check", mode: "full", checkedAt: later };

test("the setup refuses unless asked for, with a clean root inside a throwaway run under the testing directory", () => {
  const clean = {
    env: { [SETUP_VARIABLE]: "1" },
    storageRoot: join(run, "storage"),
    storageEntries: [],
    runDirectory: run,
    testingRoot: testing,
  };
  assert.equal(setupHostVerdict(clean).verdict, PASS);
  for (const defect of [
    { env: {} },
    { env: { [SETUP_VARIABLE]: "true" } },
    { storageRoot: resolve(tmpdir(), "elsewhere", "storage") },
    { storageRoot: run },
    { storageRoot: "storage" },
    { runDirectory: resolve(tmpdir(), "elsewhere") },
    { runDirectory: testing, storageRoot: join(testing, "storage") },
    { testingRoot: undefined },
    { storageEntries: ["components"] },
    { storageEntries: undefined },
  ]) {
    assert.equal(
      setupHostVerdict({ ...clean, ...defect }).verdict,
      FAIL,
      JSON.stringify(defect),
    );
  }
});

test("the items to set up are the host's rows, the browser and the local AI", () => {
  const rows = [{ itemId: "browser" }, { itemId: "local_ai" }];
  assert.deepEqual(setupItemsFrom(rows), ["browser", "local_ai"]);
});

test("one approval of a digest-bound plan must cover every item before any byte moves", () => {
  const required = ["browser", "local_ai"];
  const approval = { digest: "a".repeat(64), itemIds: required, at: settled };
  assert.equal(
    planApprovalVerdict({
      approvals: [approval],
      requiredItemIds: required,
      firstTransferAt: later,
    }).verdict,
    PASS,
  );
  const defects = [
    { approvals: [], requiredItemIds: required },
    { approvals: [approval, approval], requiredItemIds: required },
    {
      approvals: [{ ...approval, itemIds: ["browser"] }],
      requiredItemIds: required,
    },
    {
      approvals: [{ ...approval, itemIds: [...required, "google"] }],
      requiredItemIds: required,
    },
    { approvals: [{ ...approval, digest: "" }], requiredItemIds: required },
    {
      approvals: [approval],
      requiredItemIds: required,
      firstTransferAt: earlier,
    },
    { approvals: [approval], requiredItemIds: [] },
  ];
  for (const defect of defects) {
    assert.equal(
      planApprovalVerdict(defect).verdict,
      FAIL,
      JSON.stringify(defect),
    );
  }
});

test("readiness rests only on the item's own full check after setup settled", () => {
  const ready = {
    itemId: "browser",
    state: "ready",
    evidence: fullCheck,
    setupSettledAt: settled,
  };
  assert.equal(itemEvidenceVerdict(ready).verdict, PASS);
  assert.equal(itemEvidenceVerdict({ ...ready, state: "stale" }).verdict, PASS);
  const defects = [
    { evidence: { ...fullCheck, source: "receipt" } },
    { evidence: { ...fullCheck, source: "installer_exit" } },
    { evidence: { ...fullCheck, source: "declaration" } },
    { evidence: { ...fullCheck, mode: "quick" } },
    { evidence: { ...fullCheck, checkedAt: earlier } },
    { evidence: undefined },
    { state: "unknown" },
    { state: "failed" },
    { itemId: "local_model" },
  ];
  for (const defect of defects) {
    assert.equal(
      itemEvidenceVerdict({ ...ready, ...defect }).verdict,
      FAIL,
      JSON.stringify(defect),
    );
  }
});

test("Resume continues an interrupted transfer under the same approval and ends usable", () => {
  const interrupted = {
    state: "failed",
    failureCategory: "interrupted",
    completedBytes: 1_000_000,
    totalBytes: 4_000_000,
    digest: "d",
  };
  const resumed = {
    approvalsShown: 0,
    digest: "d",
    firstCompletedBytes: 1_000_000,
    finalState: "ready",
  };
  assert.equal(resumeVerdict({ interrupted, resumed }).verdict, PASS);
  const defects = [
    { interrupted: undefined },
    { interrupted: { ...interrupted, failureCategory: "unexpected" } },
    {
      interrupted: {
        ...interrupted,
        state: "absent",
        failureCategory: undefined,
      },
    },
    { interrupted: { ...interrupted, completedBytes: 0 } },
    { resumed: { ...resumed, approvalsShown: 1 } },
    { resumed: { ...resumed, digest: "e" } },
    { resumed: { ...resumed, firstCompletedBytes: 0 } },
    { resumed: { ...resumed, finalState: "failed" } },
  ];
  for (const defect of defects) {
    assert.equal(
      resumeVerdict({ interrupted, resumed, ...defect }).verdict,
      FAIL,
      JSON.stringify(defect),
    );
  }
});

test("each item's evidence lands in its own file", (t) => {
  const parent = resolve(tmpdir());
  const directory = mkdtempSync(join(parent, "cadrumo-setup-evidence-"));
  t.after(() => {
    assert.equal(dirname(resolve(directory)), parent);
    rmSync(directory, { recursive: true });
  });
  const results = new Results(join(directory, "results"));
  const items = [
    { itemId: "browser", state: "ready", evidence: fullCheck },
    { itemId: "local_ai", state: "ready", evidence: fullCheck },
  ];
  const written = recordItemEvidence(results, items);
  assert.equal(new Set(written).size, items.length);
  for (const [index, item] of items.entries()) {
    const stored = JSON.parse(
      readFileSync(join(results.directory, written[index]), "utf8"),
    );
    assert.equal(stored.itemId, item.itemId);
  }
});

test("the run refuses a volume under the free-space floor or one it cannot read", () => {
  assert.equal(
    freeSpaceVerdict({ freeBytes: FREE_SPACE_FLOOR_BYTES }).verdict,
    PASS,
  );
  for (const freeBytes of [FREE_SPACE_FLOOR_BYTES - 1, -1, Number.NaN, null])
    assert.equal(
      freeSpaceVerdict({ freeBytes }).verdict,
      FAIL,
      String(freeBytes),
    );
});

test("every location of a run is inside its root and no setting of the caller's leaks through", () => {
  const layout = scratchLayout(run);
  for (const path of Object.values(layout))
    assert(path === run || path.startsWith(`${run}${sep}`), path);
  const env = isolatedEnvironment(
    {
      PATH: "p",
      CADRUMO_LOCAL_STORAGE_ROOT: "real",
      cadrumo_secret_store_dir: "real",
      PLAYWRIGHT_BROWSERS_PATH: "real",
      OLLAMA_MODELS: "real",
      WEBVIEW2_USER_DATA_FOLDER: "real",
      HTTPS_PROXY: "real",
      no_proxy: "real",
      LOCALAPPDATA: "real",
      APPDATA: "real",
      TEMP: "real",
    },
    layout,
    "CADRUMO_LOCAL_STORAGE_ROOT",
  );
  assert.deepEqual(env, {
    PATH: "p",
    CADRUMO_LOCAL_STORAGE_ROOT: layout.storage,
    LOCALAPPDATA: layout.local,
    APPDATA: layout.roaming,
    TEMP: layout.temporary,
    TMP: layout.temporary,
    TMPDIR: layout.temporary,
  });
});

test("Resume passes only when the window offered it and showed no second plan", () => {
  const interrupted = { wireBytes: 30_000_000, offered: "resume" };
  const resumed = {
    resumeRequested: true,
    reviewsShown: 0,
    answersSent: 0,
    rebuilt: [],
    finalState: "ready",
    wireBytes: 300_000_000,
  };
  assert.equal(browserResumeVerdict({ interrupted, resumed }).verdict, PASS);
  for (const defect of [
    { interrupted: undefined },
    { interrupted: { ...interrupted, wireBytes: 0 } },
    { interrupted: { ...interrupted, offered: "try_again" } },
    { interrupted: { ...interrupted, offered: "set_up" } },
    { resumed: { ...resumed, resumeRequested: false } },
    { resumed: { ...resumed, reviewsShown: 1 } },
    { resumed: { ...resumed, answersSent: 1 } },
    { resumed: { ...resumed, rebuilt: ["chromium-1223"] } },
    { resumed: { ...resumed, finalState: "failed" } },
  ])
    assert.equal(
      browserResumeVerdict({ interrupted, resumed, ...defect }).verdict,
      FAIL,
      JSON.stringify(defect),
    );
});

test("a second setup passes only when it moved nothing, showed nothing and changed nothing", () => {
  const quiet = {
    outcome: "nothing_to_do",
    reviewsShown: 0,
    wireBytes: 40_000,
    changedPaths: [],
  };
  assert.equal(secondSetupVerdict(quiet).verdict, PASS);
  for (const defect of [
    { outcome: "completed" },
    { reviewsShown: 1 },
    { wireBytes: NO_TRANSFER_ALLOWANCE_BYTES + 1 },
    { wireBytes: undefined },
    { changedPaths: ["changed x"] },
  ])
    assert.equal(
      secondSetupVerdict({ ...quiet, ...defect }).verdict,
      FAIL,
      JSON.stringify(defect),
    );
});

test("real storage fails on any guarded change and reports the others", () => {
  assert.equal(
    realStorageVerdict({ guarded: [], observed: ["changed logs/x"] }).verdict,
    PASS,
  );
  assert.equal(
    realStorageVerdict({ guarded: ["added components/x"], observed: [] })
      .verdict,
    FAIL,
  );
  assert.equal(realStorageVerdict({ guarded: [] }).verdict, FAIL);
});

test("fingerprints see additions, removals and changes, and the root is removed only inside its parent", async (t) => {
  const parent = mkdtempSync(join(resolve(tmpdir()), "cadrumo-setup-scratch-"));
  t.after(() => rmSync(parent, { recursive: true, force: true }));
  const root = join(parent, "run-1");
  mkdirSync(join(root, "a"), { recursive: true });
  writeFileSync(join(root, "a", "kept"), "12345");
  writeFileSync(join(root, "gone"), "1");
  assert.equal(treeBytes(root), 6);
  const before = fingerprint([root, join(parent, "missing")]);
  rmSync(join(root, "gone"));
  writeFileSync(join(root, "a", "kept"), "123456");
  writeFileSync(join(root, "new"), "1");
  const changes = fingerprintChanges(
    before,
    fingerprint([root, join(parent, "missing")]),
  );
  assert(changes.includes(`added ${join(root, "new")}`));
  assert(changes.includes(`removed ${join(root, "gone")}`));
  assert(changes.includes(`changed ${join(root, "a", "kept")}`));
  await assert.rejects(removeScratch(join(root, "a"), parent));
  assert.equal(await removeScratch(root, parent), true);
  assert.equal(existsSync(root), false);
});
