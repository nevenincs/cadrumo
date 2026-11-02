import { useCallback, type RefObject, type SetStateAction } from "react";
import type { DocsMenuRequest } from "../components/DocsFrame";
import type { RecordMenuRequest } from "../components/RecordList";
import type {
  MenuAnchor,
  MenuEntry,
  OpenMenu,
} from "../components/ContextMenu";
import type { TerminalApi } from "../components/TerminalPane";
import type { Action } from "./actions";
import type { TerminalKind } from "./host";
import type { Translate } from "./strings";
import {
  levelRank,
  recordLine,
  recordsText,
  type RecordFilters,
} from "./records";

/** Context menus share the action registry's shortcuts and the shell's commands. */
export function useShellMenus({
  actionsRef,
  terminals,
  openMenu,
  t,
  copy,
  copyLogs,
  paste,
  runAction,
  setFilters,
  selectLogLevel,
}: {
  actionsRef: RefObject<Action[]>;
  terminals: RefObject<Partial<Record<TerminalKind, TerminalApi>>>;
  openMenu: OpenMenu;
  t: Translate;
  copy: (text: string) => void;
  copyLogs: (text: string) => void;
  paste: (kind: TerminalKind) => void;
  runAction: (id: string) => void;
  setFilters: (update: SetStateAction<RecordFilters>) => void;
  selectLogLevel: (level: number) => void;
}) {
  // An item that does what a registry action does takes its icon and its
  // first chord, so a shown shortcut is one the keymap binds.
  const registered = useCallback(
    (id: string) => {
      const known = actionsRef.current.find((action) => action.id === id);
      return { icon: known?.icon, chord: known?.chords?.[0] };
    },
    [actionsRef],
  );

  const docsMenu = useCallback(
    (request: DocsMenuRequest) => {
      openMenu(
        [
          {
            id: "copy",
            label: t("desktop.menu.copy"),
            icon: "copy",
            enabled: !!request.selection,
            run: () => copy(request.selection),
          },
          {
            id: "link",
            label: t("desktop.menu.copy_link"),
            icon: "link",
            enabled: !!request.link,
            run: () => copy(request.link?.href ?? ""),
          },
          { separator: true },
          {
            id: "back",
            label: t("desktop.action.docs_back"),
            ...registered("docs.back"),
            enabled: true,
            run: () => runAction("docs.back"),
          },
          {
            id: "forward",
            label: t("desktop.action.docs_forward"),
            ...registered("docs.forward"),
            enabled: true,
            run: () => runAction("docs.forward"),
          },
          {
            id: "home",
            label: t("desktop.rail.docs_home"),
            ...registered("docs.home"),
            enabled: true,
            run: () => runAction("docs.home"),
          },
        ],
        { x: request.x, y: request.y },
      );
    },
    [openMenu, registered, t, copy, runAction],
  );

  // The AEAT shortcut opens the browser in the window; its menu is the way
  // to the person's own browser.
  const aeatMenu = useCallback(
    (at: MenuAnchor) =>
      openMenu(
        [
          {
            id: "external",
            label: t("desktop.browser.external"),
            ...registered("link.aeat"),
            enabled: true,
            run: () => runAction("link.aeat"),
          },
        ],
        at,
      ),
    [openMenu, registered, t, runAction],
  );

  const terminalMenu = useCallback(
    (event: MouseEvent, kind: TerminalKind) => {
      const api = terminals.current[kind];
      if (!api) return;
      const items: MenuEntry[] = [
        {
          id: "copy",
          label: t("desktop.menu.copy"),
          ...registered("terminal.copy"),
          enabled: api.hasSelection(),
          run: () => copy(api.selection()),
        },
        {
          id: "paste",
          label: t("desktop.menu.paste"),
          ...registered("terminal.paste"),
          enabled: true,
          run: () => paste(kind),
        },
        {
          id: "select-all",
          label: t("desktop.menu.select_all"),
          icon: "selectAll",
          enabled: true,
          run: () => api.selectAll(),
        },
      ];
      if (kind !== "tui")
        items.push(
          { separator: true },
          {
            id: "clear",
            label: t("desktop.menu.clear"),
            icon: "erase",
            enabled: true,
            run: () => api.clear(),
          },
        );
      openMenu(items, { x: event.clientX, y: event.clientY });
    },
    [openMenu, registered, t, copy, paste, terminals],
  );

  const recordMenu = useCallback(
    ({ at, record, visible }: RecordMenuRequest) => {
      openMenu(
        [
          {
            id: "line",
            label: t("desktop.menu.copy_line"),
            icon: "copy",
            enabled: true,
            run: () =>
              copy(
                record.detail
                  ? `${recordLine(record)}\n${record.detail}`
                  : recordLine(record),
              ),
          },
          {
            id: "visible",
            label: t("desktop.menu.copy_visible"),
            icon: "copyAll",
            enabled: true,
            run: () => copyLogs(recordsText(visible)),
          },
          { separator: true },
          {
            id: "logger",
            label: t("desktop.menu.only_logger"),
            icon: "filter",
            enabled: !!record.logger,
            run: () => setFilters((f) => ({ ...f, logger: record.logger })),
          },
          {
            id: "level",
            label: t("desktop.menu.only_level", {
              level: (record.level ?? "INFO").toLowerCase(),
            }),
            icon: "filter",
            enabled: !!record.level,
            run: () => selectLogLevel(Math.max(0, levelRank(record.level))),
          },
        ],
        at,
      );
    },
    [openMenu, t, copy, copyLogs, setFilters, selectLogLevel],
  );
  return { docsMenu, aeatMenu, terminalMenu, recordMenu };
}
