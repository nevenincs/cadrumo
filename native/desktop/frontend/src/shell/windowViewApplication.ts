import type { SetStateAction } from "react";
import type { Layout, LedgerView, Maximized } from "./layout";
import type { WindowViewEntry } from "./navigation/windowViews";
import type { useColumnCommands } from "./useColumnCommands";

type Columns = ReturnType<typeof useColumnCommands>;

/** A register element the navigator let through, applied to the layout
 * store. A page and the agent take the keyboard through the focus register;
 * the terminals and the panel through their own focus wishes. */
export function windowViewApplication({
  tab,
  agentFits,
  mainOccupied,
  setMaximized,
  patch,
  showPage,
  changeLedgerView,
  setAeatAsked,
  showTui,
  openTab,
}: {
  tab: Layout["tab"];
  agentFits: boolean;
  mainOccupied: boolean;
  setMaximized: (update: SetStateAction<Maximized>) => void;
  patch: (change: Partial<Layout>) => void;
  showPage: (page: Layout["page"]) => void;
  changeLedgerView: (update: (current: LedgerView) => LedgerView) => void;
  setAeatAsked: (asked: boolean) => void;
  showTui: Columns["showTui"];
  openTab: Columns["openTab"];
}) {
  return (_id: string, entry: WindowViewEntry) => {
    const view = entry.view;
    if (view.kind === "page") {
      const section = view.section;
      if (section !== null)
        changeLedgerView((current) => ({ ...current, section }));
      setMaximized((area) => (area === "docs" ? area : null));
      if (view.page === "docs") patch({ docsShown: true });
      setAeatAsked(view.dialog === "aeat-access");
      showPage(view.page);
    } else if (view.kind === "agent") {
      if (agentFits) setMaximized((area) => (area === "agent" ? area : null));
      else setMaximized(mainOccupied ? "agent" : null);
      patch({ agentShown: true });
    } else if (view.kind === "terminal") showTui();
    else openTab(view.tab ?? tab, { toggle: false });
  };
}
