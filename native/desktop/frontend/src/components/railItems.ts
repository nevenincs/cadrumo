import type { SetStateAction } from "react";
import { primaryChord, type Action } from "../shell/actions";
import type { Host } from "../shell/host";
import type { Layout } from "../shell/layout";
import type { MessagesState } from "../shell/messages";
import type { ProvisioningStore } from "../shell/provisioning";
import type { AccountPhase } from "../shell/signIn";
import type { Translate } from "../shell/strings";
import { accountLabel } from "./accountWords";
import type { RailItem } from "./Rail";

/** The rail's buttons: the palette, the window's columns and pages, the
 * profile's views, the ways out of the window and the bottom panel above;
 * Settings below. */
export function railItems({
  t,
  byId,
  runAction,
  host,
  views,
  layout,
  setLayout,
  setPage,
  paletteOpen,
  settingsOpen,
  setSettingsOpen,
  signedIn,
  phase,
  reader,
  messages,
  agentVisible,
  tuiVisible,
  docsVisible,
  firstPaneShown,
  profileOn,
  aeatSyncOn,
  ledgerVisible,
  declarationsVisible,
  calendarVisible,
  browserVisible,
  panelVisible,
  showSede,
  aeatMenu,
  driveUrl,
  errorCount,
  provisioning,
  setupIncomplete,
}: {
  t: Translate;
  byId: (id: string) => Action | undefined;
  runAction: (id: string) => void;
  host: Host;
  views: Host["views"];
  layout: Layout;
  setLayout: (update: SetStateAction<Layout>) => void;
  setPage: (next: Layout["page"]) => void;
  paletteOpen: boolean;
  settingsOpen: boolean;
  setSettingsOpen: (update: SetStateAction<boolean>) => void;
  signedIn: boolean;
  phase: AccountPhase;
  reader: string | null;
  messages: MessagesState;
  agentVisible: boolean;
  tuiVisible: boolean;
  docsVisible: boolean;
  firstPaneShown: boolean;
  profileOn: boolean;
  aeatSyncOn: boolean;
  ledgerVisible: boolean;
  declarationsVisible: boolean;
  calendarVisible: boolean;
  browserVisible: boolean;
  panelVisible: boolean;
  showSede: () => void;
  aeatMenu: RailItem["onMenu"];
  driveUrl: string | null;
  errorCount: number;
  provisioning: ProvisioningStore;
  setupIncomplete: boolean;
}): { top: RailItem[]; bottom: RailItem[] } {
  const railTop: RailItem[] = [
    {
      id: "search",
      icon: "search",
      label: t("desktop.rail.search"),
      shortcut: primaryChord(byId("palette.open")),
      expanded: paletteOpen,
      onClick: () => runAction("palette.open"),
    },
    // The window's columns, in the order they are laid out by default.
    {
      id: "agent",
      dockPane: "agent",
      icon: "agent",
      label: t("desktop.rail.agent"),
      shortcut: primaryChord(byId("agent.toggle")),
      pressed: agentVisible,
      ...(signedIn ? {} : { heldBy: t("desktop.agent.sign_in_first") }),
      divided: true,
      onClick: () => runAction("agent.toggle"),
    },
    {
      id: "tui",
      dockPane: "tui",
      icon: "tui",
      label: t("desktop.rail.tui"),
      shortcut: primaryChord(byId("tui.toggle")),
      pressed: tuiVisible,
      onClick: () => runAction("tui.toggle"),
    },
    {
      id: "docs",
      dockPane: "docs",
      icon: "book",
      label: t("desktop.rail.docs"),
      shortcut: primaryChord(byId("docs.toggle")),
      pressed: docsVisible,
      onClick: () => runAction("docs.toggle"),
    },
    ...(host.userProfile
      ? [
          {
            id: "profile",
            icon: "user",
            label: t("desktop.profile.title"),
            pressed: profileOn && firstPaneShown,
            onClick: () => {
              setPage("profile");
              setLayout((current) => ({ ...current, maximized: null }));
            },
          } satisfies RailItem,
        ]
      : []),
    ...(host.aeatSync
      ? [
          {
            id: "aeat-sync",
            icon: "sync",
            label: t("desktop.aeat_sync.title"),
            pressed: aeatSyncOn && firstPaneShown,
            onClick: () => {
              setPage("aeat-sync");
              setLayout((current) => ({ ...current, maximized: null }));
            },
          } satisfies RailItem,
        ]
      : []),
    ...(host.ledger
      ? [
          {
            id: "ledger",
            icon: "ledger",
            label: t("desktop.ledger.title"),
            pressed: ledgerVisible,
            onClick: () => runAction("view.ledger"),
          } satisfies RailItem,
        ]
      : []),
    ...(host.modelo
      ? [
          {
            id: "declarations",
            icon: "page",
            label: t("workspace.declarations.destination.overview"),
            pressed: declarationsVisible,
            onClick: () => runAction("view.declarations"),
          } satisfies RailItem,
        ]
      : []),
    // Shortcuts, between the window's own toggles and the bottom panel's:
    // the profile's views where the host offers them, then the ways out of
    // the window.
    ...(views
      ? [
          {
            id: "calendar",
            icon: "calendar",
            label: t("desktop.calendar.title"),
            shortcut: primaryChord(byId("view.calendar")),
            pressed: calendarVisible,
            divided: true,
            onClick: () => runAction("view.calendar"),
          } satisfies RailItem,
          {
            id: "messages",
            icon: "mail",
            label: t("desktop.rail.messages"),
            ...(messages.kind === "ready"
              ? messages.summary.captured_at === null
                ? { hint: t("desktop.messages.never"), pin: "unknown" }
                : messages.summary.unread > 0
                  ? {
                      badge: messages.summary.unread,
                      badgeLabel: t("desktop.messages.unread", {
                        count: messages.summary.unread,
                      }),
                    }
                  : { hint: t("desktop.messages.none_unread") }
              : messages.kind === "failed"
                ? {
                    hint: t("desktop.messages.failed"),
                    pin: "failed",
                  }
                : // Not read: while the account withholds it, for the
                  // account's own reason; otherwise the answer is on its way.
                  {
                    pin: "unknown",
                    ...(reader === null && accountLabel(phase)
                      ? { hint: t(accountLabel(phase) ?? "") }
                      : {}),
                  }),
            onClick: () => runAction("view.messages"),
          } satisfies RailItem,
        ]
      : []),
    ...(host.sedeView
      ? [
          {
            id: "browser",
            icon: "globe",
            label: t("desktop.browser.title"),
            pressed: browserVisible,
            divided: !views,
            onClick: () => runAction("view.browser"),
          } satisfies RailItem,
        ]
      : []),
    {
      id: "aeat",
      icon: "office",
      label: t("desktop.rail.aeat"),
      divided: !views && !host.sedeView,
      // Where the window has a browser the shortcut opens it, and the
      // person's own browser is its menu's choice.
      ...(host.sedeView
        ? { onClick: showSede, onMenu: aeatMenu }
        : { onClick: () => runAction("link.aeat") }),
    },
    ...(driveUrl
      ? [
          {
            id: "drive",
            icon: "folder",
            label: t("desktop.google.open_drive"),
            onClick: () => runAction("link.drive"),
          } satisfies RailItem,
        ]
      : []),
    {
      id: "panel",
      dockPane: layout.tab,
      icon: "console",
      label: t("desktop.panel.label"),
      shortcut: primaryChord(byId("panel.toggle")),
      pressed: panelVisible,
      divided: true,
      badge: errorCount,
      badgeLabel: t("desktop.logs.errors", { count: errorCount }),
      onClick: () => runAction("panel.toggle"),
    },
  ];
  const railBottom: RailItem[] = [
    {
      id: "settings",
      icon: "settings",
      label: t("desktop.rail.settings"),
      shortcut: primaryChord(byId("settings.open")),
      expanded: settingsOpen,
      ...(provisioning.anyLive
        ? { pin: "busy", hint: t("desktop.setup.rail_busy") }
        : setupIncomplete
          ? { pin: "attention", hint: t("desktop.setup.rail_incomplete") }
          : {}),
      onClick: () => setSettingsOpen((open) => !open),
    },
  ];
  return { top: railTop, bottom: railBottom };
}
