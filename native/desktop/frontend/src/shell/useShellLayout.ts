import { useCallback, useMemo, useState, type SetStateAction } from "react";
import {
  dockPanes,
  initialDockLayout,
  returnDockPane,
  type DockLayout,
} from "./docking";
import { loadState, type Layout, type Maximized, type Prefs } from "./layout";

/** The saved preferences and arrangement, the dock within it with every
 * pane placed somewhere, and the updates the window makes to them. */
export function useShellLayout() {
  const initial = useMemo(loadState, []);
  const [prefs, setPrefs] = useState<Prefs>(initial.prefs);
  const [layout, setLayout] = useState<Layout>(() => {
    let docking =
      initial.layout.docking ??
      initialDockLayout(initial.prefs, initial.layout);
    for (const pane of [
      "agent",
      "docs",
      "tui",
      "console",
      "python",
      "logs",
    ] as const) {
      if (
        !dockPanes(docking.root).includes(pane) &&
        !docking.floating.some((item) => item.pane === pane)
      )
        docking = returnDockPane(docking, pane);
    }
    return { ...initial.layout, docking };
  });
  const docking = layout.docking ?? initialDockLayout(prefs, layout);
  const changeDocking = useCallback(
    (update: (current: DockLayout) => DockLayout) => {
      setLayout((current) => ({
        ...current,
        docking: update(current.docking ?? initialDockLayout(prefs, current)),
      }));
    },
    [prefs],
  );
  const setMaximized = useCallback((update: SetStateAction<Maximized>) => {
    setLayout((current) => ({
      ...current,
      maximized:
        typeof update === "function" ? update(current.maximized) : update,
    }));
  }, []);
  return {
    prefs,
    setPrefs,
    layout,
    setLayout,
    docking,
    changeDocking,
    setMaximized,
  };
}
