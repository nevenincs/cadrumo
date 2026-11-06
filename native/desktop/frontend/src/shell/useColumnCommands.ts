import { useCallback, type RefObject, type SetStateAction } from "react";
import type { DockPane } from "./docking";
import type { TerminalKind } from "./host";
import type { Layout, Maximized, PanelTab } from "./layout";
import { WORKSPACE_COLUMNS } from "./useWorkspaceFocus";

/** How a column, the bottom panel or a maximized area is shown and put away,
 * from the rail, the palette, a shortcut or a pane's own controls. */
export function useColumnCommands({
  layout,
  maximized,
  setMaximized,
  patch,
  focusView,
  guarded,
  showPage,
  showDocs,
  pageOn,
  panelVisible,
  activePanes,
  agentVisible,
  agentFits,
  tuiVisible,
  docsVisible,
  mainOccupied,
  wantsAgent,
}: {
  layout: Layout;
  maximized: Maximized;
  setMaximized: (update: SetStateAction<Maximized>) => void;
  patch: (change: Partial<Layout>) => void;
  focusView: (view: TerminalKind | "logs") => void;
  guarded: (proceed: () => void) => void;
  showPage: (page: Layout["page"]) => void;
  showDocs: () => void;
  pageOn: boolean;
  panelVisible: boolean;
  activePanes: DockPane[];
  agentVisible: boolean;
  agentFits: boolean;
  tuiVisible: boolean;
  docsVisible: boolean;
  mainOccupied: boolean;
  wantsAgent: RefObject<boolean>;
}) {
  // The TUI is where the profile is worked on: shown, with the keyboard.
  const showTui = useCallback(() => {
    setMaximized((area) => (area === "tui" ? area : null));
    patch({ tuiShown: true });
    focusView("tui");
  }, [patch, focusView, setMaximized]);

  const openTab = useCallback(
    (tab: PanelTab, { toggle = true }: { toggle?: boolean } = {}) => {
      if (
        toggle &&
        panelVisible &&
        activePanes.includes(tab) &&
        layout.tab === tab
      ) {
        patch({ panelOpen: false });
        if (maximized === "panel") setMaximized(null);
        return;
      }
      if (maximized && maximized !== "panel") setMaximized(null);
      patch({ panelOpen: true, tab });
      focusView(tab);
    },
    [
      panelVisible,
      activePanes,
      layout.tab,
      maximized,
      patch,
      focusView,
      setMaximized,
    ],
  );

  const toggleMaximize = useCallback(
    (area: Exclude<Maximized, null>) => {
      if (maximized === area) {
        setMaximized(null);
        return;
      }
      if (area === "agent" && !layout.agentShown) patch({ agentShown: true });
      if (area === "tui" && !layout.tuiShown) patch({ tuiShown: true });
      if (area === "docs" && !layout.docsShown && !pageOn)
        patch({ docsShown: true });
      if (area === "panel" && !layout.panelOpen) patch({ panelOpen: true });
      setMaximized(area);
      if (area === "tui") focusView("tui");
    },
    [
      maximized,
      setMaximized,
      layout.agentShown,
      layout.tuiShown,
      layout.docsShown,
      layout.panelOpen,
      pageOn,
      patch,
      focusView,
    ],
  );

  // A column's own close: put away, and the layout restored if it was the
  // one maximized.
  const closeColumn = useCallback(
    (column: (typeof WORKSPACE_COLUMNS)[number]) => {
      if (column === "docs") {
        guarded(() => {
          showPage("docs");
          patch({ docsShown: false });
          setMaximized((area) => (area === column ? null : area));
        });
      } else {
        setMaximized((area) => (area === column ? null : area));
        patch(column === "agent" ? { agentShown: false } : { tuiShown: false });
      }
    },
    [patch, setMaximized, guarded, showPage],
  );
  // A column asked for from the rail, the palette or a shortcut: put away
  // when it is on screen, else shown with the layout restored around it.
  const toggleColumn = useCallback(
    (column: (typeof WORKSPACE_COLUMNS)[number]) => {
      const onScreen =
        column === "agent"
          ? agentVisible
          : column === "tui"
            ? tuiVisible
            : docsVisible;
      if (onScreen && maximized === null) return closeColumn(column);
      if (column === "agent" && !agentFits) {
        // Too narrow to sit beside anything: the agent takes the window.
        if (onScreen) return closeColumn(column);
        patch({ agentShown: true });
        setMaximized(mainOccupied ? "agent" : null);
        wantsAgent.current = true;
        return;
      }
      setMaximized(null);
      if (column === "docs") showDocs();
      else if (column === "agent") {
        patch({ agentShown: true });
        wantsAgent.current = true;
      } else {
        patch({ tuiShown: true });
        focusView("tui");
      }
    },
    [
      agentVisible,
      agentFits,
      mainOccupied,
      tuiVisible,
      docsVisible,
      maximized,
      closeColumn,
      setMaximized,
      showDocs,
      patch,
      focusView,
      wantsAgent,
    ],
  );
  return { showTui, openTab, toggleMaximize, closeColumn, toggleColumn };
}
