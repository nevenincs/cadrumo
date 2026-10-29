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
  guardedChange,
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
  setupFailureVerdict,
  concurrentSetupVerdict,
  treeBytes,
} from "./setup.mjs";
import { FAIL, PASS, cspVerdict } from "./verdicts.mjs";
import {
  startupPanelVerdict,
  firstNullSnapshotVerdict,
  panelRowsVerdict,
  progressVerdict,
  partSizesVerdict,
  localAiPartsVerdict,
  smallestLocalModels,
  settingsVerdict,
  removalVerdict,
} from "./provisioning.mjs";
import { sedeMissingVerdict } from "./probes.mjs";

const testing = resolve(tmpdir(), "cadrumo-testing");
const run = resolve(testing, "cadrumo-setup-run");
const settled = "2026-10-18T12:00:00.000Z";
const later = "2026-10-18T12:05:00.000Z";
const earlier = "2026-10-18T11:55:00.000Z";
const fullCheck = { source: "full_check", mode: "full", checkedAt: later };

test("check 1 rejects startup overlap, missing first snapshot and an unexercised null snapshot", () => {
  const valid = {
    states: [
      { signIn: true, panel: false },
      { signIn: false, panel: true },
    ],
    reads: [{ snapshot: { complete: null } }],
    overflow: false,
  };
  for (const judge of [startupPanelVerdict, firstNullSnapshotVerdict]) {
    assert.equal(judge(valid).verdict, PASS);
    for (const defect of [
      { states: [] },
      { reads: [] },
      { overflow: true },
      {
        states: [
          { signIn: true, panel: true },
          { signIn: false, panel: true },
        ],
      },
      {
        states: [
          { signIn: true, panel: false },
          { signIn: false, panel: false },
        ],
      },
    ])
      assert.equal(judge({ ...valid, ...defect }).verdict, FAIL);
  }
  assert.equal(
    firstNullSnapshotVerdict({
      ...valid,
      reads: [{ snapshot: { complete: false } }],
    }).verdict,
    FAIL,
  );
});

test("check 2 rejects missing, duplicated or unordered engine rows and duplicate sentences or close controls", () => {
  const snapshot = {
    rows: [
      { item: "browser", recovery: "set_up" },
      { item: "local_ai", recovery: "set_up" },
    ],
  };
  const action = { label: "Set up", disabled: false };
  const browser = {
    item: "browser",
    expandable: false,
    sentences: ["Not installed"],
    buttons: [action],
  };
  const local = {
    item: "local_ai",
    expandable: true,
    expanded: true,
    sentences: [],
    buttons: [action],
    nested: [
      { item: "local_ai", sentences: ["Not installed"], actions: [action] },
    ],
  };
  const valid = { elements: [browser, local], close: ["Close"] };
  assert.equal(panelRowsVerdict(snapshot, valid).verdict, PASS);
  for (const defect of [
    { elements: [browser] },
    { elements: [local, browser] },
    { elements: [browser, browser] },
    { close: [] },
    { close: ["Close", "Close"] },
    { elements: [{ ...browser, sentences: ["Absent", "Absent"] }, local] },
    { elements: [{ ...browser, buttons: [] }, local] },
    { elements: [browser, { ...local, nested: [] }] },
    {
      elements: [
        browser,
        {
          ...local,
          nested: [{ ...local.nested[0], sentences: ["Absent", "Absent"] }],
        },
      ],
    },
    {
      elements: [
        browser,
        { ...local, nested: [{ ...local.nested[0], actions: [] }] },
      ],
    },
  ])
    assert.equal(
      panelRowsVerdict(snapshot, { ...valid, ...defect }).verdict,
      FAIL,
    );
});

test("checks 2 and 3 reject aggregate progress sizes, premature bytes and missing separate local AI steps", () => {
  assert.equal(
    progressVerdict({ completed: 0, total: 100, displayedBytes: "" }).verdict,
    PASS,
  );
  assert.equal(
    progressVerdict({ completed: 0, total: 100, displayedBytes: "0 / 100" })
      .verdict,
    FAIL,
  );
  assert.equal(
    progressVerdict({
      completed: 10,
      total: 100,
      displayedBytes: "10 / 100 MB",
      expectedTotalText: "100 MB",
    }).verdict,
    PASS,
  );
  assert.equal(
    progressVerdict({
      completed: 10,
      total: 100,
      displayedBytes: "10 / 900 MB",
      expectedTotalText: "100 MB",
    }).verdict,
    FAIL,
  );
  const expected = [
    { part: "program", sizeBytes: 100, sizeText: "100 MB" },
    { part: "download", sizeBytes: 20, sizeText: "20 MB" },
  ];
  const rendered = [
    { part: "program", text: "Program 100 MB" },
    { part: "download", text: "Model synthetic:small 20 MB" },
  ];
  assert.equal(partSizesVerdict(expected, rendered).verdict, PASS);
  assert.equal(
    partSizesVerdict(expected, [
      { ...rendered[0], text: "Program 120 MB" },
      rendered[1],
    ]).verdict,
    FAIL,
  );
  assert.equal(partSizesVerdict(expected, rendered.slice(1)).verdict, FAIL);
  const review = {
    entries: [
      {
        item: "local_ai",
        parts: [
          { part: "program" },
          { part: "download", model: "synthetic:small" },
        ],
      },
    ],
  };
  assert.equal(
    localAiPartsVerdict(review, "synthetic:small", rendered).verdict,
    PASS,
  );
  assert.equal(
    localAiPartsVerdict(review, "synthetic:other", rendered).verdict,
    FAIL,
  );
  assert.equal(
    localAiPartsVerdict(review, "synthetic:small", rendered.slice(1)).verdict,
    FAIL,
  );
  assert.equal(
    localAiPartsVerdict({ entries: [] }, "synthetic:small", rendered).verdict,
    FAIL,
  );
});

test("check 3 derives the smallest local model from agent sizes and refuses unknown or nonlocal candidates", () => {
  const settings = { providers: [{ id: "synthetic_api", auth_kind: "none" }] };
  const catalog = {
    kind: "declared",
    catalog: {
      providers: [
        {
          id: "synthetic_api",
          provider: "synthetic",
          models: [
            { id: "large", size_bytes: 200 },
            { id: "small", size_bytes: 20 },
            { id: "unknown" },
          ],
        },
      ],
    },
  };
  assert.equal(smallestLocalModels(catalog, settings).model, "small");
  assert.throws(() => smallestLocalModels(catalog, { providers: [] }));
  assert.throws(() =>
    smallestLocalModels(
      {
        kind: "declared",
        catalog: {
          providers: [{ id: "synthetic_api", models: [{ id: "unknown" }] }],
        },
      },
      settings,
    ),
  );
  const served = {
    providers: [
      {
        provider_id: "synthetic",
        transport: "api",
        model_source: "catalog",
        catalog: { models: [{ model: "small", size_bytes: 20 }] },
      },
    ],
  };
  assert.equal(smallestLocalModels(served, settings).model, "small");
  assert.throws(() =>
    smallestLocalModels(
      { providers: [{ ...served.providers[0], model_source: "custom" }] },
      settings,
    ),
  );
});

test("check 6 rejects duplicate Settings sections, extra controls and a panel that did not open or close", () => {
  const valid = {
    sections: 2,
    provisioningSections: 1,
    statuses: 1,
    statusText: "Setup incomplete",
    provisioningButtons: 1,
    windowButtons: 1,
    extraSetupControls: 0,
    panelOpened: true,
    panelClosed: true,
    panelVerdict: { verdict: PASS },
  };
  assert.equal(settingsVerdict(valid).verdict, PASS);
  for (const defect of [
    { sections: 3 },
    { provisioningSections: 2 },
    { statuses: 2 },
    { statusText: "" },
    { provisioningButtons: 2 },
    { windowButtons: 2 },
    { extraSetupControls: 1 },
    { panelOpened: false },
    { panelClosed: false },
    { panelVerdict: { verdict: FAIL } },
  ])
    assert.equal(settingsVerdict({ ...valid, ...defect }).verdict, FAIL);
});

test("check 7 rejects stale confirmations, refused removal or an unsuccessful reinstall", () => {
  const valid = {
    confirmationShown: true,
    removal: {
      cmd: "desktop_setup_remove",
      args: { removal: "local_ai" },
      ok: true,
    },
    removed: true,
    absentBefore: true,
    sawLive: true,
    confirmationReappeared: false,
    absentAfter: true,
    reinstall: { verdict: PASS },
    modelInstalled: true,
  };
  assert.equal(removalVerdict(valid).verdict, PASS);
  for (const defect of [
    { confirmationShown: false },
    { removal: { ...valid.removal, ok: false } },
    { removal: { ...valid.removal, args: { removal: "browser" } } },
    { removed: false },
    { absentBefore: false },
    { sawLive: false },
    { confirmationReappeared: true },
    { absentAfter: false },
    { reinstall: { verdict: FAIL } },
    { modelInstalled: false },
  ])
    assert.equal(removalVerdict({ ...valid, ...defect }).verdict, FAIL);
});

test("check 8 rejects CSP violation events and console reports", () => {
  assert.equal(
    cspVerdict([{ role: "shell", csp: [], console: [] }]).verdict,
    PASS,
  );
  assert.equal(
    cspVerdict([{ role: "shell", csp: [{ effectiveDirective: "script-src" }] }])
      .verdict,
    FAIL,
  );
  assert.equal(
    cspVerdict(
      [{ role: "shell" }],
      [
        "Refused to execute inline script because it violates the following Content Security Policy directive",
      ],
    ).verdict,
    FAIL,
  );
});

test("check 10 rejects a missing Sede offer, wrong persisted refusal or absent local warning", () => {
  const record = {
    service: {
      event: "feature_refused",
      feature: "sede_view",
      refusal: "component_not_ready",
      item: "browser",
    },
  };
  const valid = {
    absent: true,
    sentence: "The browser is not installed",
    offer: true,
    panel: true,
    records: [record],
    warning: true,
  };
  assert.equal(sedeMissingVerdict(valid).verdict, PASS);
  for (const defect of [
    { absent: false },
    { sentence: "Something failed" },
    { offer: false },
    { panel: false },
    { records: [] },
    { records: [record, record] },
    { warning: false },
    { records: [{ service: { ...record.service, item: "local_ai" } }] },
    { records: [{ service: { ...record.service, refusal: "unexpected" } }] },
  ])
    assert.equal(sedeMissingVerdict({ ...valid, ...defect }).verdict, FAIL);
});

test("concurrency requires real overlap, independent cancellation and a global spinner", () => {
  const run = (item, stage, outcome = null) => ({
    item,
    stage,
    outcome,
    operation_id: item,
  });
  const state = (...runs) => ({ snapshot: { runs } });
  const evidence = {
    overlap: state(run("browser", "running"), run("local_ai", "running")),
    cancelled: state(
      run("browser", "settled", "cancelled"),
      run("local_ai", "running"),
    ),
    browserWire: { bytes: 1024 },
    localAiWire: { bytes: 1024 },
    controls: { browserCancel: true, localAiCancel: true, modelHeld: true },
    browserActionAfterCancel: true,
    spinnerDuring: { present: true, overlay: true },
    spinnerAfterCancel: { present: true, overlay: true },
    spinnerAfter: { present: false },
  };
  assert.equal(concurrentSetupVerdict(evidence).verdict, PASS);
  for (const defect of [
    { overlap: state(run("browser", "settled"), run("local_ai", "running")) },
    { browserWire: { bytes: 0 } },
    {
      controls: { browserCancel: false, localAiCancel: true, modelHeld: true },
    },
    {
      cancelled: state(
        run("browser", "settled", "cancelled"),
        run("local_ai", "settled", "cancelled"),
      ),
    },
    {
      cancelled: state(run("browser", "settled", "cancelled"), {
        ...run("local_ai", "running"),
        operation_id: "replacement",
      }),
    },
    { spinnerAfterCancel: { present: false } },
    { spinnerDuring: { present: true, overlay: false } },
    { browserActionAfterCancel: false },
    { spinnerAfter: { present: true } },
  ])
    assert.equal(
      concurrentSetupVerdict({ ...evidence, ...defect }).verdict,
      FAIL,
    );
});

test("a real setup failure needs its one plain sentence, recovery and exactly one persisted diagnostic event", () => {
  const event = {
    kind: "failure",
    source: "desktop",
    sequence: 17,
    hostPid: 123,
    failure: {
      code: "setup_failed",
      reason: "setup_browser_failed",
      causes: [
        {
          kind: "application",
          code: "setup_failed",
          reason: "blocked_by_network",
        },
      ],
    },
  };
  const valid = {
    run: { stage: "settled", outcome: "failed", failure: "blocked_by_network" },
    expectedSentence: "Your network is blocking the download.",
    sentences: ["Your network is blocking the download."],
    action: "Try again",
    refusals: 1,
    events: [event],
    records: [event],
  };
  assert.equal(setupFailureVerdict(valid).verdict, PASS);
  for (const defect of [
    { refusals: 0 },
    { run: { ...valid.run, outcome: "completed" } },
    { run: { ...valid.run, failure: "unexpected" } },
    { sentences: [] },
    { sentences: [...valid.sentences, ...valid.sentences] },
    { sentences: ["blocked_by_network"] },
    { expectedSentence: "" },
    {
      expectedSentence: "Cadrumo refused that request.",
      sentences: ["Cadrumo refused that request."],
    },
    { action: "" },
    { events: [] },
    { events: [event, event] },
    { events: [{ ...event, failure: { ...event.failure, causes: [] } }] },
    { records: [] },
    { records: [event, event] },
    { records: [{ ...event, sequence: 18 }] },
    { records: [{ ...event, hostPid: 456 }] },
  ])
    assert.equal(
      setupFailureVerdict({ ...valid, ...defect }).verdict,
      FAIL,
      JSON.stringify(defect),
    );
});

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

const STORAGE = resolve(tmpdir(), "real", "var", "storage");
const CACHE = resolve(tmpdir(), "real", "Local", "ms-playwright");
const RUN_ROOT = resolve(tmpdir(), "testing", "run-1");
const storageContext = (runCommandLines = []) => ({
  roots: [STORAGE, CACHE],
  marks: [RUN_ROOT, "profile-7"],
  browserCache: CACHE,
  runCommandLines,
});
const shellLog = join(
  CACHE,
  "chromium_headless_shell-1243",
  "chrome-headless-shell-win64",
  "debug.log",
);

test("another program's browser writing its own log in the real cache is reported, not charged to the run", () => {
  const context = storageContext([`"${join(RUN_ROOT, "app", "cadrumo.exe")}"`]);

  assert.equal(guardedChange(`changed ${shellLog}`, context), false);
  assert.equal(guardedChange(`added ${shellLog}`, context), false);
});

test("an install, a removal or this run's own browser in the real cache is charged to the run", () => {
  const context = storageContext();
  const build = join(CACHE, "chromium-1248");

  assert.equal(guardedChange(`added ${build}`, context), true);
  assert.equal(
    guardedChange(`added ${join(build, "INSTALLATION_COMPLETE")}`, context),
    true,
  );
  assert.equal(
    guardedChange(
      `changed ${join(build, "chrome-win64", "chrome.exe")}`,
      context,
    ),
    true,
  );
  assert.equal(guardedChange(`removed ${shellLog}`, context), true);
  const ranFromCache = storageContext([
    `"${join(CACHE, "chromium_headless_shell-1243", "chrome-headless-shell-win64", "chrome-headless-shell.exe")}" --headless`,
  ]);
  assert.equal(guardedChange(`changed ${shellLog}`, ranFromCache), true);
});

test("setup and profile members, marks and unwatched paths are charged; other storage members are not", () => {
  const context = storageContext();

  assert.equal(
    guardedChange(`added ${join(STORAGE, "components", "x")}`, context),
    true,
  );
  assert.equal(
    guardedChange(
      `added ${join(STORAGE, "development", "buckets", "b")}`,
      context,
    ),
    true,
  );
  assert.equal(
    guardedChange(`added ${join(STORAGE, "profile-custody-1")}`, context),
    true,
  );
  assert.equal(
    guardedChange(`added ${join(STORAGE, "logs", "x.log")}`, context),
    false,
  );
  assert.equal(
    guardedChange(`added ${join(STORAGE, "logs", "profile-7.log")}`, context),
    true,
  );
  assert.equal(
    guardedChange(`added ${resolve(tmpdir(), "elsewhere", "x")}`, context),
    true,
  );
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
