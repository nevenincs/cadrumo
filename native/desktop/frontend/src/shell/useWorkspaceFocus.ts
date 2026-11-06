import { useEffect, useRef, type RefObject } from "react";
import type { Maximized, PanelTab } from "./layout";
import type { TerminalStatus } from "../components/TerminalPane";

export const WORKSPACE_COLUMNS = ["agent", "tui", "docs"] as const;
type Column = (typeof WORKSPACE_COLUMNS)[number];
type FocusTarget = RefObject<{ focus(): void } | null>;
const PANEL_VIEWS: ReadonlySet<string> = new Set<PanelTab>([
  "console",
  "python",
  "logs",
]);

/** Keeps keyboard focus in an available pane as workspace visibility changes. */
export function useWorkspaceFocus({
  agentVisible,
  tuiVisible,
  firstPaneShown,
  maximized,
  gated,
  tuiPhase,
  tab,
  focusView,
  focusRail,
  signInButton,
  profilePage,
  ledgerPage,
  declarationsPage,
  calendarPage,
  aeatSyncPage,
  docs,
  agentBody,
  wantsAgent,
}: {
  agentVisible: boolean;
  tuiVisible: boolean;
  firstPaneShown: boolean;
  maximized: Maximized;
  gated: boolean;
  tuiPhase: TerminalStatus["phase"];
  tab: PanelTab;
  focusView: (view: "tui" | PanelTab) => void;
  focusRail: () => void;
  signInButton: FocusTarget;
  profilePage: FocusTarget;
  ledgerPage: FocusTarget;
  declarationsPage: FocusTarget;
  calendarPage: FocusTarget;
  aeatSyncPage: FocusTarget;
  docs: FocusTarget;
  agentBody: FocusTarget;
  wantsAgent: RefObject<boolean>;
}) {
  // A column hidden from under the keyboard: focus goes to the TUI while
  // that is shown, else to the first pane, else to the agent, else to the
  // rail, never to nothing. The bottom panel maximized over them hands
  // focus on by itself.
  const columnsWere = useRef<Record<Column, boolean>>({
    agent: agentVisible,
    tui: tuiVisible,
    docs: firstPaneShown,
  });
  useEffect(() => {
    const now = { agent: agentVisible, tui: tuiVisible, docs: firstPaneShown };
    const gone = WORKSPACE_COLUMNS.filter(
      (column) => columnsWere.current[column] && !now[column],
    );
    columnsWere.current = now;
    // Only when one has just been hidden: a window that starts without a
    // column moves no focus. What held focus inside it is still named as
    // the focused element for a moment after it stops being shown.
    const held = document.activeElement;
    if (
      gone.length === 0 ||
      maximized === "panel" ||
      (held !== null &&
        held !== document.body &&
        !gone.some((column) => held.closest(`.pane-${column}`) !== null))
    )
      return;
    // Only where the TUI's pane holds something to focus: the way in while
    // signed out, or a session.
    const tuiFocusable =
      signInButton.current !== null || (!gated && tuiPhase !== "unavailable");
    if (tuiVisible && tuiFocusable) focusView("tui");
    else if (
      firstPaneShown &&
      (profilePage.current ??
        ledgerPage.current ??
        declarationsPage.current ??
        calendarPage.current ??
        aeatSyncPage.current ??
        docs.current)
    )
      (
        profilePage.current ??
        ledgerPage.current ??
        declarationsPage.current ??
        calendarPage.current ??
        aeatSyncPage.current ??
        docs.current
      )?.focus();
    else if (agentVisible) agentBody.current?.focus();
    else focusRail();
  }, [
    agentVisible,
    tuiVisible,
    firstPaneShown,
    maximized,
    gated,
    tuiPhase,
    focusView,
    focusRail,
    signInButton,
    profilePage,
    ledgerPage,
    declarationsPage,
    calendarPage,
    aeatSyncPage,
    docs,
    agentBody,
  ]);
  useEffect(() => {
    if (agentVisible && wantsAgent.current) {
      wantsAgent.current = false;
      agentBody.current?.focus();
    }
  }, [agentVisible, wantsAgent, agentBody]);
  // The bottom panel maximized over the panes above it: focus held in one
  // of them goes into the panel, to the view its tab shows. Every docked
  // pane outside the panel is covered, the TUI's as much as the page's.
  const panelMaximized = maximized === "panel";
  const panelWasMaximized = useRef(panelMaximized);
  useEffect(() => {
    const covered = !panelWasMaximized.current && panelMaximized;
    panelWasMaximized.current = panelMaximized;
    const held = document.activeElement;
    const heldPane =
      held?.closest<HTMLElement>("[data-dock-pane]")?.dataset.dockPane;
    if (
      !covered ||
      (held !== null &&
        held !== document.body &&
        (heldPane === undefined || PANEL_VIEWS.has(heldPane)))
    )
      return;
    focusView(tab);
  }, [panelMaximized, tab, focusView]);

  return panelMaximized;
}
