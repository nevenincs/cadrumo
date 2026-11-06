import { useMemo, type Dispatch, type SetStateAction } from "react";
import type { Action } from "./actions";
import {
  orientDockPane,
  swapDockPane,
  type DockLayout,
  type DockPane,
} from "./docking";
import { focusedArea } from "./focusedArea";
import type { Maximized, Prefs } from "./layout";
import type { Translate } from "./strings";
import { WORKSPACE_COLUMNS } from "./useWorkspaceFocus";

/** The arrangement's: maximizing a column, and the split's orientation and order. */
export function useArrangementActions({
  t,
  maximized,
  setMaximized,
  toggleMaximize,
  agentVisible,
  tuiVisible,
  firstPaneShown,
  prefs,
  narrowedPanes,
  changeDocking,
  setPrefs,
}: {
  t: Translate;
  maximized: Maximized;
  setMaximized: (update: SetStateAction<Maximized>) => void;
  toggleMaximize: (area: Exclude<Maximized, null>) => void;
  agentVisible: boolean;
  tuiVisible: boolean;
  firstPaneShown: boolean;
  prefs: Prefs;
  narrowedPanes: readonly DockPane[];
  changeDocking: (update: (current: DockLayout) => DockLayout) => void;
  setPrefs: Dispatch<SetStateAction<Prefs>>;
}): Action[] {
  return useMemo<Action[]>(
    () => [
      {
        id: "view.maximize",
        label: maximized
          ? t("desktop.pane.restore")
          : t("desktop.pane.maximize_focused"),
        group: "layout",
        icon: maximized ? "restore" : "maximize",
        chords: [
          { mod: true, shift: true, code: "KeyM", key: "M", scope: "global" },
        ],
        run: () => {
          if (maximized) return setMaximized(null);
          const area = focusedArea();
          toggleMaximize(
            area && area !== "rail"
              ? area
              : (WORKSPACE_COLUMNS.find((column) =>
                  column === "agent"
                    ? agentVisible
                    : column === "tui"
                      ? tuiVisible
                      : firstPaneShown,
                ) ?? "docs"),
          );
        },
      },
      {
        id: "view.maximizeAgent",
        label: t("desktop.pane.maximize_agent"),
        group: "layout",
        icon: "maximize",
        enabled: () => maximized !== "agent",
        run: () => toggleMaximize("agent"),
      },
      {
        id: "view.maximizeDocs",
        label: t("desktop.pane.maximize_docs"),
        group: "layout",
        icon: "maximize",
        enabled: () => maximized !== "docs",
        run: () => toggleMaximize("docs"),
      },
      {
        id: "view.maximizeTui",
        label: t("desktop.pane.maximize_tui"),
        group: "layout",
        icon: "maximize",
        enabled: () => maximized !== "tui",
        run: () => toggleMaximize("tui"),
      },
      {
        id: "view.maximizePanel",
        label: t("desktop.pane.maximize_panel"),
        group: "layout",
        icon: "maximize",
        enabled: () => maximized !== "panel",
        run: () => toggleMaximize("panel"),
      },
      {
        id: "split.orientation",
        label:
          prefs.orientation === "row"
            ? t("desktop.split.stack")
            : t("desktop.split.side_by_side"),
        group: "layout",
        icon: prefs.orientation === "row" ? "splitColumn" : "splitRow",
        // While the window forces stacking, the choice would change nothing
        // visible, so it is not offered.
        enabled: () => !narrowedPanes.includes("docs"),
        run: () => {
          changeDocking((current) => orientDockPane(current, "docs"));
          setPrefs((p) => ({
            ...p,
            orientation: p.orientation === "row" ? "column" : "row",
          }));
        },
      },
      {
        id: "split.swap",
        label: t("desktop.split.swap"),
        group: "layout",
        icon: "swap",
        run: () => {
          changeDocking((current) => swapDockPane(current, "docs"));
          setPrefs((p) => ({
            ...p,
            order: p.order === "docs" ? "tui" : "docs",
          }));
        },
      },
    ],
    [
      t,
      maximized,
      setMaximized,
      toggleMaximize,
      agentVisible,
      tuiVisible,
      firstPaneShown,
      prefs.orientation,
      narrowedPanes,
      changeDocking,
      setPrefs,
    ],
  );
}
