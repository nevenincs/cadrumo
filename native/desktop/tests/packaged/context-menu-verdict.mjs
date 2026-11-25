import { FAIL, PASS, noEffectVerdict } from "./verdicts.mjs";

const record = (value) =>
  value !== null && typeof value === "object" && !Array.isArray(value);
const positive = (value) => Number.isSafeInteger(value) && value > 0;
const shape = (value, fields) =>
  record(value) &&
  Object.keys(value).length === Object.keys(fields).length &&
  Object.entries(fields).every(([key, expected]) => value[key] === expected);
const scope = (value) =>
  shape(value, {
    admitted: true,
    requestedPidMatches: true,
    objectHwndMatches: true,
    objectPidKnown: true,
    objectPidMatches: true,
  });
const sameWindow = (a, b) =>
  record(a) &&
  record(b) &&
  a.hwnd === b.hwnd &&
  a.pid === b.pid &&
  a.owner === b.owner;
const windows = (value) =>
  Array.isArray(value) &&
  value.every(
    (window) =>
      record(window) &&
      positive(window.hwnd) &&
      positive(window.pid) &&
      Number.isSafeInteger(window.owner) &&
      window.owner >= 0,
  ) &&
  new Set(value.map((window) => window.hwnd)).size === value.length;
const sameWindows = (a, b) =>
  windows(a) &&
  windows(b) &&
  a.length === b.length &&
  a.every((window) => b.some((other) => sameWindow(window, other)));
const frameMap = (value) =>
  record(value) &&
  Object.keys(value).length === 2 &&
  ["shell", "docs"].every(
    (role) => typeof value[role] === "string" && value[role].length > 0,
  );
const snapshot = (value) =>
  record(value) &&
  frameMap(value.markers) &&
  frameMap(value.urls) &&
  ["navigations", "beforeprint", "targets"].every(
    (key) => Number.isSafeInteger(value[key]) && value[key] >= 0,
  ) &&
  typeof value.zoom === "string" &&
  value.zoom.length > 0;
const clean = (value) =>
  record(value) &&
  !Object.keys(value).some((key) => key.endsWith("Error")) &&
  !Object.hasOwn(value, "scopeRejection") &&
  !Object.hasOwn(value, "limit");

function expectedTooltipTree(tree) {
  if (
    !clean(tree) ||
    tree.complete !== true ||
    tree.maxCandidates !== 16 ||
    tree.maxDepth !== 3 ||
    tree.candidateCountIncludesReserved !== true ||
    tree.candidateCount !== 2 ||
    tree.expectedTitleAvailable !== true ||
    tree.completionReason !== "bounded same HWND MSAA tree exhausted" ||
    Object.keys(tree).length !== 9 ||
    !Array.isArray(tree.nodes) ||
    tree.nodes.length !== 2 ||
    !shape(tree.releaseSettlement, {
      acquired: 2,
      released: 2,
      errors: 0,
      complete: true,
      enumerationCleanupKnown: true,
    })
  )
    return false;
  const [pane, tooltip] = tree.nodes;
  return (
    scope(pane?.scope) &&
    scope(tooltip?.scope) &&
    shape(pane, {
      index: 0,
      parentIndex: null,
      depth: 0,
      roleId: 16,
      simpleChild: false,
      childCount: 1,
      scope: pane.scope,
    }) &&
    shape(tooltip, {
      index: 1,
      parentIndex: 0,
      depth: 1,
      roleId: 13,
      simpleChild: false,
      childCount: 0,
      nameMatchesExpectedTitle: true,
      scope: tooltip.scope,
    })
  );
}

function preservedUiaRefusal(evidence) {
  const error = "UIA PID outside requested root";
  const pane = evidence.nodes?.[0];
  return (
    Object.keys(evidence).length === 11 &&
    evidence.complete === false &&
    evidence.diagnosticError === error &&
    evidence.expectedTitleAvailable === true &&
    evidence.maxNodes === 16 &&
    evidence.maxDepth === 3 &&
    evidence.candidateCount === 2 &&
    Array.isArray(evidence.nodes) &&
    evidence.nodes.length === 1 &&
    shape(pane?.scope, {
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
    }) &&
    shape(pane, {
      controlType: "ControlType.Pane",
      controlTypeId: 50033,
      frameworkId: "Win32",
      offscreen: false,
      hasKeyboardFocus: false,
      depth: 0,
      scope: pane.scope,
    }) &&
    shape(evidence.scopeRejection, {
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
      diagnosticError: error,
    })
  );
}

function activeHost(window, hostPid) {
  const metadata = window?.metadata;
  return (
    window?.processRole === "host" &&
    window.pid === hostPid &&
    window.owner === 0 &&
    clean(metadata) &&
    metadata.hwnd === window.hwnd &&
    metadata.pid === hostPid &&
    metadata.owner === 0 &&
    metadata.visible === true &&
    metadata.foreground === true &&
    metadata.foregroundHwnd === window.hwnd &&
    metadata.foregroundInScope === true
  );
}

function provenTooltip(before, after, boundary, opened) {
  if (
    !record(boundary) ||
    !positive(boundary.hostPid) ||
    !Array.isArray(boundary.webviewPids) ||
    !boundary.webviewPids.every(positive) ||
    boundary.webviewPids.includes(boundary.hostPid) ||
    new Set(boundary.webviewPids).size !== boundary.webviewPids.length ||
    !Array.isArray(boundary.diagnosticErrors) ||
    boundary.diagnosticErrors.length !== 0 ||
    !sameWindows(before.windows, boundary.before?.windows) ||
    !sameWindows(after.windows, boundary.after?.windows) ||
    !Array.isArray(boundary.removed) ||
    boundary.removed.length !== 0 ||
    !Array.isArray(boundary.delta) ||
    boundary.delta.length !== 1 ||
    !sameWindow(opened, boundary.delta[0]) ||
    !Array.isArray(boundary.deltaAccessibility) ||
    boundary.deltaAccessibility.length !== 1
  )
    return false;
  const owner = before.windows.find(
    (window) => window.hwnd === opened.owner && window.pid === boundary.hostPid,
  );
  const popup = boundary.delta[0];
  const current = boundary.after.windows.find((w) => w.hwnd === opened.hwnd);
  const evidence = boundary.deltaAccessibility[0];
  const metadata = popup.metadata;
  const root = evidence?.rootMsaa;
  return (
    !!owner &&
    activeHost(
      boundary.before.windows.find((window) => window.hwnd === owner.hwnd),
      boundary.hostPid,
    ) &&
    activeHost(
      boundary.after.windows.find((window) => window.hwnd === owner.hwnd),
      boundary.hostPid,
    ) &&
    before.windows.every((window) =>
      after.windows.some((other) => sameWindow(window, other)),
    ) &&
    opened.pid !== boundary.hostPid &&
    boundary.webviewPids.includes(opened.pid) &&
    popup.processRole === "webview" &&
    current.processRole === "webview" &&
    clean(metadata) &&
    clean(current.metadata) &&
    [metadata, current.metadata].every(
      (item) =>
        item.hwnd === opened.hwnd &&
        item.pid === opened.pid &&
        item.owner === owner.hwnd &&
        item.visible === true &&
        item.foreground === false &&
        item.foregroundHwnd === owner.hwnd &&
        item.foregroundInScope === true,
    ) &&
    record(evidence) &&
    evidence.hwnd === opened.hwnd &&
    preservedUiaRefusal(evidence) &&
    clean(root) &&
    scope(root.scope) &&
    shape(root, {
      complete: true,
      requestedInScope: true,
      expectedTitleAvailable: true,
      released: true,
      roleId: 16,
      completionReason: "exact HWND root role read",
      scope: root.scope,
    }) &&
    expectedTooltipTree(evidence.msaaTree)
  );
}

/** The context-menu path may distinguish one fully proven expected tooltip. */
export function contextMenuVerdict(before, after, boundary) {
  let originalNoEffectVerdict;
  let invalidObservations = false;
  try {
    originalNoEffectVerdict = noEffectVerdict(before, after);
  } catch {
    invalidObservations = true;
    originalNoEffectVerdict = {
      verdict: FAIL,
      detail: "invalid context-menu observations",
    };
  }
  const keep = (reason) => ({
    ...originalNoEffectVerdict,
    originalNoEffectVerdict,
    tooltipAssessment: { accepted: false, reason },
  });
  if (invalidObservations) return keep("invalid context-menu observations");
  if (!snapshot(before) || !snapshot(after))
    return {
      ...keep("incomplete context-menu observations"),
      verdict: FAIL,
      detail: "incomplete context-menu effect observations",
    };
  if (!windows(before?.windows) || !windows(after?.windows))
    return {
      ...keep("invalid window identities"),
      verdict: FAIL,
      detail: "invalid context-menu window identities",
    };
  if (
    !before.windows.every((window) =>
      after.windows.some((other) => sameWindow(window, other)),
    )
  )
    return {
      ...keep("existing window identity changed or disappeared"),
      verdict: FAIL,
      detail: "existing context-menu window identity changed or disappeared",
    };
  if (originalNoEffectVerdict.verdict !== FAIL) return keep("no new effect");
  const known = new Set(before.windows.map((window) => window.hwnd));
  const opened = after.windows.filter((window) => !known.has(window.hwnd));
  if (opened.length !== 1 || !provenTooltip(before, after, boundary, opened[0]))
    return keep("new window lacks complete expected-tooltip proof");
  const residual = noEffectVerdict(before, {
    ...after,
    windows: after.windows.filter((window) => window.hwnd !== opened[0].hwnd),
  });
  if (residual.verdict === FAIL) return keep("another effect remains");
  return {
    verdict: PASS,
    detail: "no default menu; one fully proven expected-title tooltip",
    originalNoEffectVerdict,
    tooltipAssessment: {
      accepted: true,
      hwnd: opened[0].hwnd,
      uiaRefusalPreserved: true,
    },
  };
}
