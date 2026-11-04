import assert from "node:assert/strict";
import { test } from "node:test";
import { contextMenuVerdict } from "./context-menu-verdict.mjs";
import { FAIL, PASS, noEffectVerdict } from "./verdicts.mjs";

function fixture() {
  const host = { hwnd: 11, pid: 101, owner: 0, class: "host", title: "host" };
  const popup = { hwnd: 21, pid: 202, owner: 11, class: "popup", title: "" };
  const scope = () => ({
    admitted: true,
    requestedPidMatches: true,
    objectHwndMatches: true,
    objectPidKnown: true,
    objectPidMatches: true,
  });
  const hostEvidence = {
    ...host,
    processRole: "host",
    metadata: {
      hwnd: 11,
      pid: 101,
      owner: 0,
      visible: true,
      foreground: true,
      foregroundHwnd: 11,
      foregroundInScope: true,
    },
  };
  const popupEvidence = {
    ...popup,
    processRole: "webview",
    metadata: {
      hwnd: 21,
      pid: 202,
      owner: 11,
      visible: true,
      foreground: false,
      foregroundHwnd: 11,
      foregroundInScope: true,
    },
  };
  const before = {
    markers: { shell: "shell", docs: "docs" },
    urls: { shell: "http://shell/", docs: "http://docs/" },
    navigations: 1,
    beforeprint: 0,
    zoom: "1/1",
    targets: 2,
    windows: [host],
  };
  const after = { ...structuredClone(before), windows: [host, popup] };
  const boundary = {
    hostPid: 101,
    webviewPids: [202, 203],
    diagnosticErrors: [],
    before: { windows: [hostEvidence] },
    after: { windows: [hostEvidence, popupEvidence] },
    delta: [popupEvidence],
    removed: [],
    deltaAccessibility: [
      {
        hwnd: 21,
        expectedTitleAvailable: true,
        complete: false,
        diagnosticError: "UIA PID outside requested root",
        maxNodes: 16,
        maxDepth: 3,
        candidateCount: 2,
        nodes: [
          {
            controlType: "ControlType.Pane",
            controlTypeId: 50033,
            frameworkId: "Win32",
            offscreen: false,
            hasKeyboardFocus: false,
            depth: 0,
            scope: {
              admitted: true,
              depth: 0,
              uiPidKnown: true,
              uiPidMatchesRoot: true,
              hasNativeHwnd: true,
              nativeHwndEqualsRoot: true,
              win32PidKnown: true,
              win32PidMatchesRoot: true,
              isChildOfRequestedRoot: null,
              ancestorAdmitted: false,
            },
          },
        ],
        scopeRejection: {
          admitted: false,
          depth: 1,
          uiPidKnown: true,
          uiPidMatchesRoot: false,
          hasNativeHwnd: null,
          nativeHwndEqualsRoot: null,
          win32PidKnown: null,
          win32PidMatchesRoot: null,
          isChildOfRequestedRoot: null,
          ancestorAdmitted: true,
          diagnosticError: "UIA PID outside requested root",
        },
        rootMsaa: {
          complete: true,
          requestedInScope: true,
          expectedTitleAvailable: true,
          released: true,
          roleId: 16,
          completionReason: "exact HWND root role read",
          scope: scope(),
        },
        msaaTree: {
          complete: true,
          maxCandidates: 16,
          maxDepth: 3,
          candidateCount: 2,
          candidateCountIncludesReserved: true,
          expectedTitleAvailable: true,
          completionReason: "bounded same HWND MSAA tree exhausted",
          releaseSettlement: {
            acquired: 2,
            released: 2,
            errors: 0,
            complete: true,
            enumerationCleanupKnown: true,
          },
          nodes: [
            {
              index: 0,
              parentIndex: null,
              depth: 0,
              roleId: 16,
              simpleChild: false,
              childCount: 1,
              scope: scope(),
            },
            {
              index: 1,
              parentIndex: 0,
              depth: 1,
              roleId: 13,
              simpleChild: false,
              childCount: 0,
              nameMatchesExpectedTitle: true,
              scope: scope(),
            },
          ],
        },
      },
    ],
  };
  return structuredClone({ before, after, boundary });
}

const evaluate = ({ before, after, boundary }) =>
  contextMenuVerdict(before, after, boundary);
const evidence = (f) => f.boundary.deltaAccessibility[0];
const tree = (f) => evidence(f).msaaTree;
function freeze(value) {
  if (value && typeof value === "object") {
    Object.freeze(value);
    Object.values(value).forEach(freeze);
  }
  return value;
}

test("context menu accepts only the complete expected tooltip and retains both failure records", () => {
  const f = freeze(fixture());
  const original = noEffectVerdict(f.before, f.after);
  assert.equal(original.verdict, FAIL);
  const result = evaluate(f);
  assert.equal(result.verdict, PASS);
  assert.deepEqual(result.originalNoEffectVerdict, original);
  assert.equal(result.tooltipAssessment.accepted, true);
  assert.equal(result.tooltipAssessment.uiaRefusalPreserved, true);
  assert.equal(evidence(f).complete, false);
  assert.equal(evidence(f).scopeRejection.uiPidMatchesRoot, false);
  assert.deepEqual(noEffectVerdict(f.before, f.after), original);
});

test("class and bounds supply no tooltip authority", () => {
  const f = fixture();
  f.after.windows[1].class = "Chrome_WidgetWin_1";
  f.boundary.delta[0].metadata.windowBounds = [10, 20, 125, 32];
  assert.equal(evaluate(f).verdict, PASS);
  delete evidence(f).msaaTree;
  assert.equal(evaluate(f).verdict, FAIL);
});

test("no-window context menu retains the ordinary no-effect decision", () => {
  const f = fixture();
  f.after = structuredClone(f.before);
  const result = evaluate(f);
  assert.equal(result.verdict, PASS);
  assert.equal(result.tooltipAssessment.accepted, false);
  assert.deepEqual(
    result.originalNoEffectVerdict,
    noEffectVerdict(f.before, f.after),
  );
});

const refusals = {
  "missing boundary": (f) => (f.boundary = undefined),
  "metadata diagnostic": (f) => f.boundary.diagnosticErrors.push("unavailable"),
  "unscoped host": (f) => (f.boundary.hostPid = 999),
  "foreign popup PID": (f) => (f.boundary.webviewPids = [203]),
  "host in webview scope": (f) => f.boundary.webviewPids.push(101),
  "duplicate PID scope": (f) => f.boundary.webviewPids.push(202),
  "duplicate after HWND": (f) => f.after.windows.push(f.after.windows[1]),
  "extra window": (f) =>
    f.after.windows.push({ hwnd: 22, pid: 202, owner: 11 }),
  "extra delta": (f) => f.boundary.delta.push(f.boundary.delta[0]),
  "omitted delta": (f) => (f.boundary.delta = []),
  "removed window": (f) => f.boundary.removed.push(f.before.windows[0]),
  "missing metadata window": (f) => f.boundary.after.windows.pop(),
  "extra metadata window": (f) =>
    f.boundary.after.windows.push({ hwnd: 99, pid: 202, owner: 11 }),
  "foreign owner": (f) => (f.boundary.delta[0].owner = 99),
  "foreign metadata PID": (f) => (f.boundary.delta[0].metadata.pid = 999),
  "foreign metadata HWND": (f) => (f.boundary.delta[0].metadata.hwnd = 99),
  "foreign metadata owner": (f) => (f.boundary.delta[0].metadata.owner = 99),
  "popup foreground": (f) => (f.boundary.delta[0].metadata.foreground = true),
  "foreign foreground": (f) =>
    (f.boundary.delta[0].metadata.foregroundHwnd = 99),
  "hidden popup": (f) => (f.boundary.delta[0].metadata.visible = false),
  "metadata identity error": (f) =>
    (f.boundary.delta[0].metadata.processIdentityError = "unavailable"),
  "inactive owner": (f) =>
    (f.boundary.after.windows[0].metadata.foreground = false),
  "missing accessibility": (f) => delete f.boundary.deltaAccessibility,
  "duplicate accessibility": (f) =>
    f.boundary.deltaAccessibility.push(evidence(f)),
  "foreign accessibility HWND": (f) => (evidence(f).hwnd = 99),
  "missing expected title": (f) => (evidence(f).expectedTitleAvailable = false),
  "unknown UIA error": (f) => (evidence(f).diagnosticError = "query failed"),
  "contradictory UIA menu": (f) => (evidence(f).nodes[0].controlTypeId = 50009),
  "extra UIA node": (f) => evidence(f).nodes.push(evidence(f).nodes[0]),
  "UIA root unowned": (f) =>
    (evidence(f).nodes[0].scope.win32PidMatchesRoot = false),
  "unknown UIA descendant PID": (f) =>
    (evidence(f).scopeRejection.uiPidKnown = false),
  "UIA refusal rewritten": (f) => (evidence(f).complete = true),
  "extra accessibility data": (f) => (evidence(f).extra = true),
  "missing root proof": (f) => delete evidence(f).rootMsaa,
  "root incomplete": (f) => (evidence(f).rootMsaa.complete = false),
  "root unreleased": (f) => (evidence(f).rootMsaa.released = false),
  "root custom role": (f) => (evidence(f).rootMsaa.roleId = "tooltip"),
  "root other role": (f) => (evidence(f).rootMsaa.roleId = 9),
  "root foreign HWND": (f) =>
    (evidence(f).rootMsaa.scope.objectHwndMatches = false),
  "root unqueried PID": (f) =>
    (evidence(f).rootMsaa.scope.objectPidKnown = null),
  "tree incomplete": (f) => (tree(f).complete = false),
  "tree scope refusal": (f) => (tree(f).scopeRejection = {}),
  "tree diagnostic": (f) => (tree(f).diagnosticError = "query failed"),
  "tree cap": (f) => (tree(f).limit = "depth"),
  "tree not exhausted": (f) => (tree(f).completionReason = "role found"),
  "wrong candidate budget": (f) => (tree(f).maxCandidates = 32),
  "wrong depth budget": (f) => (tree(f).maxDepth = 4),
  "unvisited candidate": (f) => (tree(f).candidateCount = 3),
  "unknown reservation semantics": (f) =>
    delete tree(f).candidateCountIncludesReserved,
  "tree title unavailable": (f) => (tree(f).expectedTitleAvailable = false),
  "missing tooltip": (f) => tree(f).nodes.pop(),
  "extra pane": (f) => tree(f).nodes.push(structuredClone(tree(f).nodes[0])),
  "coexisting menu": (f) => {
    const menu = { ...structuredClone(tree(f).nodes[1]), roleId: 11, index: 2 };
    tree(f).nodes.push(menu);
    tree(f).nodes[0].childCount = 2;
    tree(f).candidateCount = 3;
    tree(f).releaseSettlement.acquired = tree(f).releaseSettlement.released = 3;
  },
  "menu instead of tooltip": (f) => (tree(f).nodes[1].roleId = 11),
  "menu item instead of tooltip": (f) => (tree(f).nodes[1].roleId = 12),
  "window instead of tooltip": (f) => (tree(f).nodes[1].roleId = 9),
  "unknown role": (f) => (tree(f).nodes[1].roleId = 65),
  "custom string role": (f) => (tree(f).nodes[1].roleId = "ToolTip"),
  "wrong parent index": (f) => (tree(f).nodes[1].parentIndex = 1),
  "wrong node index": (f) => (tree(f).nodes[1].index = 0),
  "wrong depth": (f) => (tree(f).nodes[1].depth = 3),
  "unobserved children": (f) => (tree(f).nodes[1].childCount = 1),
  "unobserved pane children": (f) => (tree(f).nodes[0].childCount = 0),
  "unexpected simple child": (f) => (tree(f).nodes[1].simpleChild = true),
  "title mismatch": (f) => (tree(f).nodes[1].nameMatchesExpectedTitle = false),
  "missing title comparison": (f) =>
    delete tree(f).nodes[1].nameMatchesExpectedTitle,
  "string true title comparison": (f) =>
    (tree(f).nodes[1].nameMatchesExpectedTitle = "true"),
  "foreign tree HWND": (f) =>
    (tree(f).nodes[1].scope.objectHwndMatches = false),
  "foreign tree PID": (f) => (tree(f).nodes[1].scope.objectPidMatches = false),
  "unknown tree PID": (f) => (tree(f).nodes[1].scope.objectPidKnown = null),
  "unknown admission": (f) => (tree(f).nodes[1].scope.admitted = null),
  "extra node data": (f) => (tree(f).nodes[1].name = "not evidence"),
  "pane Name data": (f) => (tree(f).nodes[0].nameMatchesExpectedTitle = true),
  "release incomplete": (f) => (tree(f).releaseSettlement.complete = false),
  "release error": (f) => (tree(f).releaseSettlement.errors = 1),
  "unsettled reference": (f) => (tree(f).releaseSettlement.released = 1),
  "extra acquired reference": (f) => (tree(f).releaseSettlement.acquired = 3),
  "unknown enumeration cleanup": (f) =>
    (tree(f).releaseSettlement.enumerationCleanupKnown = null),
};
for (const [name, mutate] of Object.entries(refusals)) {
  test(`context-menu refuses ${name}`, () => {
    const f = fixture();
    mutate(f);
    const result = evaluate(f);
    assert.equal(result.verdict, FAIL);
    assert.equal(result.tooltipAssessment.accepted, false);
  });
}

for (const [name, mutate] of Object.entries({
  "shell replacement": (f) => (f.after.markers.shell = "replaced"),
  "docs replacement": (f) => (f.after.markers.docs = "replaced"),
  "shell navigation": (f) => (f.after.urls.shell = "http://other/"),
  "docs navigation": (f) => (f.after.urls.docs = "http://other/"),
  "navigation event": (f) => f.after.navigations++,
  printing: (f) => f.after.beforeprint++,
  zoom: (f) => (f.after.zoom = "2/2"),
  "DevTools target": (f) => f.after.targets++,
})) {
  test(`proven tooltip does not hide ${name}`, () => {
    const f = fixture();
    mutate(f);
    const result = evaluate(f);
    assert.equal(result.verdict, FAIL);
    assert.equal(result.tooltipAssessment.accepted, false);
    assert.deepEqual(
      result.originalNoEffectVerdict,
      noEffectVerdict(f.before, f.after),
    );
  });
}

test("malformed observations refuse without exception or raw diagnostic content", () => {
  for (const malformed of [null, {}, { windows: null }]) {
    const result = contextMenuVerdict(malformed, malformed, null);
    assert.equal(result.verdict, FAIL);
    assert.equal(result.tooltipAssessment.accepted, false);
  }
});

test("context-menu refuses same-HWND PID reuse even without a new-window generic failure", () => {
  const f = fixture();
  f.after = structuredClone(f.before);
  f.after.windows[0].pid = 999;
  assert.equal(noEffectVerdict(f.before, f.after).verdict, PASS);
  assert.equal(evaluate(f).verdict, FAIL);
});

for (const [name, mutate] of Object.entries({
  "untyped markers": (f) => (f.before.markers = f.after.markers = "same"),
  "missing docs marker": (f) => {
    delete f.before.markers.docs;
    delete f.after.markers.docs;
  },
  "missing docs URL": (f) => {
    delete f.before.urls.docs;
    delete f.after.urls.docs;
  },
  "unobserved navigation count": (f) => {
    delete f.before.navigations;
    delete f.after.navigations;
  },
  "unobserved print count": (f) => {
    delete f.before.beforeprint;
    delete f.after.beforeprint;
  },
  "unobserved target count": (f) => {
    delete f.before.targets;
    delete f.after.targets;
  },
  "unobserved zoom": (f) => {
    delete f.before.zoom;
    delete f.after.zoom;
  },
})) {
  test(`context-menu refuses ${name} despite valid tooltip metadata`, () => {
    const f = fixture();
    mutate(f);
    assert.equal(evaluate(f).verdict, FAIL);
  });
}
