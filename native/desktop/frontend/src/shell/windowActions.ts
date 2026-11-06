import {
  useMemo,
  type Dispatch,
  type RefObject,
  type SetStateAction,
} from "react";
import type { AboutState } from "./about";
import type { Action } from "./actions";
import type { Translate } from "./strings";
import type { useFullscreen } from "./useFullscreen";

type Flag = Dispatch<SetStateAction<boolean>>;

/** The window's own: full screen, and the palette with what the shown page adds to it. */
export function useWindowChromeActions({
  t,
  fullscreen,
  enterFullscreen,
  setPaletteExtra,
  setPaletteOpen,
  contributed,
}: {
  t: Translate;
  fullscreen: ReturnType<typeof useFullscreen>;
  enterFullscreen: ReturnType<typeof useFullscreen>["toggle"];
  setPaletteExtra: Dispatch<SetStateAction<Action[]>>;
  setPaletteOpen: Flag;
  contributed: RefObject<(() => Action[]) | null>;
}): Action[] {
  return useMemo<Action[]>(
    () => [
      {
        id: "window.fullscreen",
        label: t(
          fullscreen.fullscreen
            ? "desktop.dock.exit_fullscreen"
            : "desktop.dock.fullscreen",
        ),
        group: "layout",
        icon: "windowMaximize",
        chords: [{ code: "F11", key: "F11", scope: "global" }],
        run: () => enterFullscreen(),
      },
      {
        id: "window.leaveFullscreen",
        label: t("desktop.dock.exit_fullscreen"),
        group: "layout",
        icon: "restore",
        hidden: true,
        chords: [{ code: "Escape", key: "Esc", scope: "global" }],
        enabled: () => fullscreen.fullscreen,
        run: () => enterFullscreen(),
      },
      {
        id: "palette.open",
        label: t("desktop.palette.placeholder"),
        group: "general",
        icon: "search",
        hidden: true,
        chords: [
          { mod: true, code: "KeyK", key: "K", scope: "app" },
          { mod: true, shift: true, code: "KeyK", key: "K", scope: "global" },
        ],
        run: () => {
          setPaletteExtra(contributed.current?.() ?? []);
          setPaletteOpen((open) => !open);
        },
      },
    ],
    [
      t,
      fullscreen.fullscreen,
      enterFullscreen,
      setPaletteExtra,
      setPaletteOpen,
      contributed,
    ],
  );
}

/** The settings and the About dialog. */
export function useWindowDialogActions({
  t,
  setSettingsOpen,
  about,
  setAboutOpen,
}: {
  t: Translate;
  setSettingsOpen: Flag;
  about: AboutState | null;
  setAboutOpen: Flag;
}): Action[] {
  return useMemo<Action[]>(
    () => [
      {
        id: "settings.open",
        label: t("desktop.settings.title"),
        group: "general",
        icon: "settings",
        chords: [{ mod: true, code: "Comma", key: ",", scope: "app" }],
        run: () => setSettingsOpen((open) => !open),
      },
      {
        id: "about.open",
        label: t("desktop.about.open"),
        group: "general",
        icon: "info",
        keywords: t("desktop.palette.keywords.about"),
        enabled: () => about !== null,
        run: () => {
          setSettingsOpen(false);
          setAboutOpen(true);
        },
      },
    ],
    [t, setSettingsOpen, about, setAboutOpen],
  );
}

/** Moving focus from one area of the window to the next. */
export function useFocusActions({
  t,
  cycleFocus,
}: {
  t: Translate;
  cycleFocus: (step: 1 | -1) => void;
}): Action[] {
  return useMemo<Action[]>(
    () => [
      {
        id: "focus.next",
        label: t("desktop.action.focus_next"),
        group: "general",
        icon: "arrow",
        keywords: t("desktop.palette.keywords.focus"),
        chords: [{ code: "F6", key: "F6", scope: "global" }],
        run: () => cycleFocus(1),
      },
      {
        id: "focus.previous",
        label: t("desktop.action.focus_previous"),
        group: "general",
        icon: "back",
        keywords: t("desktop.palette.keywords.focus"),
        chords: [{ shift: true, code: "F6", key: "F6", scope: "global" }],
        run: () => cycleFocus(-1),
      },
    ],
    [t, cycleFocus],
  );
}
