import { useMemo } from "react";
import { dockGeometry, type DockLayout, type DockPane } from "./docking";
import type { Host } from "./host";
import type { Layout, Maximized } from "./layout";

type Area = Exclude<Maximized, null>;

/** Which areas of the workspace are offered, expanded and on screen, and the
 * room the dock gives each, from the layout and the window's width. */
export function useWorkspaceVisibility({
  host,
  layout,
  docking,
  maximized,
  fullscreenPane,
  signedIn,
  viewportWidth,
  railWidth,
  splitMinA,
  splitMinBRow,
  agentMin,
  docsMin,
  panelMin,
  ledgerFloor,
}: {
  host: Host;
  layout: Layout;
  docking: DockLayout;
  maximized: Maximized;
  fullscreenPane: DockPane | null;
  signedIn: boolean;
  viewportWidth: number;
  railWidth: number;
  splitMinA: number;
  splitMinBRow: number;
  agentMin: number;
  docsMin: number;
  panelMin: number;
  ledgerFloor: number | null;
}) {
  const page = layout.page;
  const views = host.views;
  // What is on screen: a maximized area alone, otherwise every area that is
  // shown. The first pane holds the documentation or a view of the profile,
  // and is on screen while either is asked for.
  const profileOn = host.userProfile !== undefined && page === "profile";
  const calendarOn = views !== undefined && page === "calendar";
  const ledgerOn = host.ledger !== undefined && page === "ledger";
  const declarationsOn = host.modelo !== undefined && page === "declarations";
  const browserOn = host.sedeView !== undefined && page === "browser";
  const aeatSyncOn = host.aeatSync !== undefined && page === "aeat-sync";
  // A page of the window holds the first pane, in place of the documentation.
  const pageOn =
    calendarOn ||
    profileOn ||
    ledgerOn ||
    declarationsOn ||
    browserOn ||
    aeatSyncOn;
  const besideRail = Math.max(0, viewportWidth - railWidth);
  const mainMin = Math.max(splitMinA, ledgerOn ? (ledgerFloor ?? 0) : 0);
  const agentFits = besideRail >= agentMin + mainMin;
  const agentTab = dockGeometry(docking, [
    "agent",
    "docs",
    "tui",
    "console",
    "python",
    "logs",
  ]).groups.find((entry) => entry.group.tabs.includes("agent"));
  const agentHasRoom =
    agentFits ||
    maximized === "agent" ||
    fullscreenPane === "agent" ||
    docking.floating.some((entry) => entry.pane === "agent") ||
    (agentTab?.group.tabs.length ?? 0) > 1 ||
    (!layout.docsShown && !pageOn && !layout.tuiShown && !layout.panelOpen);
  const dockOffered = useMemo<DockPane[]>(
    () =>
      [
        ...(signedIn && layout.agentShown && agentHasRoom
          ? ["agent" as const]
          : []),
        ...(layout.docsShown || pageOn ? ["docs" as const] : []),
        ...(layout.tuiShown ? ["tui" as const] : []),
        ...(layout.panelOpen ? (["console", "python", "logs"] as const) : []),
      ].filter((pane) => !docking.closed.includes(pane)),
    [
      signedIn,
      layout.agentShown,
      agentHasRoom,
      layout.docsShown,
      pageOn,
      layout.tuiShown,
      layout.panelOpen,
      docking.closed,
    ],
  );
  const requestedExpansion =
    fullscreenPane ?? (maximized === "panel" ? layout.tab : maximized);
  const expandedPane =
    requestedExpansion && dockOffered.includes(requestedExpansion)
      ? requestedExpansion
      : null;
  const activePanes = useMemo(
    () =>
      expandedPane
        ? [expandedPane]
        : [
            ...dockGeometry(docking, dockOffered).groups.map(
              (item) => item.group.active,
            ),
            ...docking.floating
              .filter((item) => dockOffered.includes(item.pane))
              .map((item) => item.pane),
          ],
    [expandedPane, docking, dockOffered],
  );
  const unhidden = (area: Area) =>
    area === "panel"
      ? activePanes.some(
          (pane) => pane === "console" || pane === "python" || pane === "logs",
        )
      : activePanes.includes(area);
  const firstPaneShown =
    (layout.docsShown || pageOn || maximized === "docs") && unhidden("docs");
  const fitLedger =
    ledgerOn &&
    firstPaneShown &&
    !docking.floating.some((entry) => entry.pane === "docs");
  const dockMinimumWidths = useMemo(
    () => (fitLedger ? { docs: mainMin, agent: agentMin } : undefined),
    [fitLedger, mainMin, agentMin],
  );
  // Side by side needs room for both panes' minimums; a narrower window
  // stacks them without changing the remembered arrangement.
  const dockBesideWidths = useMemo(
    () => ({ docs: mainMin, tui: splitMinBRow }),
    [mainMin, splitMinBRow],
  );
  // The panel keeps a usable handful of rows and the panes above it their
  // floor; a window too short for both shares its height between them.
  const dockMinimumHeights = useMemo(
    () => ({
      docs: docsMin,
      tui: docsMin,
      agent: docsMin,
      console: panelMin,
      python: panelMin,
      logs: panelMin,
    }),
    [docsMin, panelMin],
  );
  const docsVisible = firstPaneShown && !pageOn;
  const calendarVisible = calendarOn && firstPaneShown;
  const ledgerVisible = ledgerOn && firstPaneShown;
  const declarationsVisible = declarationsOn && firstPaneShown;
  const browserVisible = browserOn && firstPaneShown;
  const tuiVisible =
    (layout.tuiShown || maximized === "tui") && unhidden("tui");
  const panelVisible = layout.panelOpen && unhidden("panel");
  const mainOccupied = firstPaneShown || tuiVisible || panelVisible;
  // The agent works only for a profile signed in here: signed out, it is
  // not there at all, and it comes back as it was laid out on signing in.
  const agentVisible =
    signedIn &&
    (layout.agentShown || maximized === "agent") &&
    unhidden("agent");
  return {
    profileOn,
    calendarOn,
    ledgerOn,
    declarationsOn,
    browserOn,
    aeatSyncOn,
    pageOn,
    agentFits,
    dockOffered,
    expandedPane,
    activePanes,
    firstPaneShown,
    dockMinimumWidths,
    dockBesideWidths,
    dockMinimumHeights,
    docsVisible,
    calendarVisible,
    ledgerVisible,
    declarationsVisible,
    browserVisible,
    tuiVisible,
    panelVisible,
    mainOccupied,
    agentVisible,
  };
}
