import { useCallback, useEffect, useRef, useState } from "react";
import type { MenuAnchor, MenuEntry } from "../components/ContextMenu";
import type { Action } from "./actions";

/** A context menu the shell draws, where, and what its opener hears once it
 * is no longer shown. */
export type ShownMenu = {
  items: MenuEntry[];
  at: MenuAnchor;
  closed?: () => void;
};

/** What the window lays over the workspace: the palette with what the shown
 * page adds to it, the settings, the About dialog and the context menu. */
export function useWindowOverlays() {
  const [paletteOpen, setPaletteOpen] = useState(false);
  // What the shown page offers the palette besides the window's own actions,
  // read as the palette opens and listed before them.
  const contributed = useRef<(() => Action[]) | null>(null);
  const [paletteExtra, setPaletteExtra] = useState<Action[]>([]);
  const contribute = useCallback((actions: (() => Action[]) | null) => {
    contributed.current = actions;
  }, []);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [aboutOpen, setAboutOpen] = useState(false);
  const [menu, setMenu] = useState<ShownMenu | null>(null);
  // Menus: the shell draws every one, in the Cadrumo theme, whichever host it
  // runs in. The caller places it: at the pointer, or at what holds focus.
  const openMenu = useCallback(
    (items: MenuEntry[], at: MenuAnchor, closed?: () => void) =>
      setMenu({ items, at, closed }),
    [],
  );
  // A menu stops being shown when it is chosen from, put away or replaced by
  // another; each of those tells its opener, which shows it is collapsed.
  useEffect(() => {
    const shown = menu;
    return () => shown?.closed?.();
  }, [menu]);
  return {
    paletteOpen,
    setPaletteOpen,
    contributed,
    paletteExtra,
    setPaletteExtra,
    contribute,
    settingsOpen,
    setSettingsOpen,
    aboutOpen,
    setAboutOpen,
    menu,
    setMenu,
    openMenu,
  };
}
