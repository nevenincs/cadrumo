import { useMemo, type RefObject, type SetStateAction } from "react";
import { viewActions, type Action, type ViewActionSpec } from "./actions";
import { labelled } from "./compose";
import type { DockPane } from "./docking";
import type { Host } from "./host";
import type { Layout, Maximized, PanelTab } from "./layout";
import { AEAT_SEDE } from "./links";
import type { MessagesState } from "./messages";
import { formatViewLink } from "./navigation/links";
import { NAVIGATION } from "./navigation/projection";
import type { useNavigator } from "./navigation/useNavigator";
import { pageViewId } from "./navigation/windowViews";
import type { Translate } from "./strings";
import { WORKSPACE_COLUMNS } from "./useWorkspaceFocus";

type Navigator = ReturnType<typeof useNavigator>;
type Column = (typeof WORKSPACE_COLUMNS)[number];

/** Every view the register names, the link to the one shown, the messages, and the external addresses. */
export function useViewActions({
  t,
  calendarVisible,
  ledgerVisible,
  declarationsVisible,
  browserVisible,
  wantsCalendar,
  wantsLedger,
  wantsDeclarations,
  setMaximized,
  setPage,
  showBrowser,
  toggleColumn,
  docsVisible,
  maximized,
  signedIn,
  agentVisible,
  tuiVisible,
  layout,
  panelVisible,
  openTab,
  patch,
  activePanes,
  resolveView,
  openView,
  firstPaneShown,
  pageOn,
  copy,
  views,
  messages,
  say,
  showTui,
  openLink,
  driveUrl,
}: {
  t: Translate;
  calendarVisible: boolean;
  ledgerVisible: boolean;
  declarationsVisible: boolean;
  browserVisible: boolean;
  wantsCalendar: RefObject<boolean>;
  wantsLedger: RefObject<boolean>;
  wantsDeclarations: RefObject<boolean>;
  setMaximized: (update: SetStateAction<Maximized>) => void;
  setPage: (next: Layout["page"]) => void;
  showBrowser: () => void;
  toggleColumn: (column: Column) => void;
  docsVisible: boolean;
  maximized: Maximized;
  signedIn: boolean;
  agentVisible: boolean;
  tuiVisible: boolean;
  layout: Layout;
  panelVisible: boolean;
  openTab: (tab: PanelTab, options?: { toggle?: boolean }) => void;
  patch: (change: Partial<Layout>) => void;
  activePanes: DockPane[];
  resolveView: Navigator["resolve"];
  openView: Navigator["openView"];
  firstPaneShown: boolean;
  pageOn: boolean;
  copy: (text: string) => void;
  views: Host["views"];
  messages: MessagesState;
  say: (text: string) => void;
  showTui: () => void;
  openLink: (url: string) => void;
  driveUrl: string | null;
}): Action[] {
  // The register element of the main view shown: the first pane's page, or
  // its Ledger section; nothing while the first pane is put away.
  const shownViewId = firstPaneShown
    ? pageViewId(pageOn ? layout.page : "docs", layout.ledgerView.section)
    : undefined;
  return useMemo<Action[]>(
    () => [
      // Every view the register names, each declared once: its label and
      // keywords come from the register, and choosing one by name opens it
      // through the navigator. Only what the window adds is said here: an
      // older id, an icon, a chord, and for a page or a pane the toggle its
      // chord and rail button keep. Pages take no chord where none is
      // declared: the shell's own are spoken for, and a page's grid keeps
      // the plain and Alt keys.
      ...viewActions(
        NAVIGATION,
        t,
        {
          profile: { icon: "user", group: "views" },
          calendar: {
            id: "view.calendar",
            icon: "calendar",
            group: "views",
            chords: [
              {
                mod: true,
                shift: true,
                code: "KeyD",
                key: "D",
                scope: "global",
              },
            ],
            run: () => {
              if (calendarVisible) {
                setPage("docs");
                return;
              }
              wantsCalendar.current = true;
              setMaximized((area) => (area === "docs" ? area : null));
              setPage("calendar");
            },
          },
          ledger: {
            id: "view.ledger",
            icon: "ledger",
            group: "views",
            run: () => {
              if (ledgerVisible) {
                setPage("docs");
                return;
              }
              wantsLedger.current = true;
              setMaximized((area) => (area === "docs" ? area : null));
              setPage("ledger");
            },
          },
          // Every Ledger section the window draws, as the register lists
          // them, wears the Ledger's icon.
          ...Object.fromEntries(
            NAVIGATION.elements
              .filter(
                (element) =>
                  element.parent === "ledger" &&
                  element.surfaces.includes("gui"),
              )
              .map((element) => [
                element.id,
                { icon: "ledger", group: "views" } as const,
              ]),
          ),
          declarations: {
            id: "view.declarations",
            icon: "page",
            group: "views",
            run: () => {
              if (declarationsVisible) {
                setPage("docs");
                return;
              }
              wantsDeclarations.current = true;
              setMaximized((area) => (area === "docs" ? area : null));
              setPage("declarations");
            },
          },
          browser: {
            icon: "globe",
            group: "views",
            run: () => {
              if (browserVisible) {
                setPage("docs");
                return;
              }
              showBrowser();
            },
          },
          docs: {
            id: "docs.toggle",
            icon: "book",
            group: "layout",
            chords: [
              {
                mod: true,
                shift: true,
                code: "KeyH",
                key: "H",
                scope: "global",
              },
            ],
            run: () => toggleColumn("docs"),
            shown: docsVisible && !maximized,
          },
          agent: {
            id: "agent.toggle",
            icon: "agent",
            group: "layout",
            chords: [
              {
                mod: true,
                shift: true,
                code: "KeyA",
                key: "A",
                scope: "global",
              },
            ],
            enabled: () => signedIn,
            run: () => toggleColumn("agent"),
            shown: agentVisible && !maximized,
          },
          terminal: {
            id: "tui.toggle",
            icon: "tui",
            group: "layout",
            chords: [
              {
                mod: true,
                shift: true,
                code: "KeyT",
                key: "T",
                scope: "global",
              },
            ],
            run: () => toggleColumn("tui"),
            shown: tuiVisible && !maximized,
          },
          panel: {
            id: "panel.toggle",
            icon: layout.panelOpen ? "chevronDown" : "chevronUp",
            group: "layout",
            chords: [
              { ctrl: true, code: "Backquote", key: "`", scope: "global" },
            ],
            run: () => {
              if (!panelVisible) openTab(layout.tab, { toggle: false });
              else {
                patch({ panelOpen: false });
                if (maximized === "panel") setMaximized(null);
              }
            },
            shown: panelVisible,
          },
          "panel/console": {
            id: "panel.console",
            icon: "console",
            group: "panel",
            chords: [
              {
                mod: true,
                shift: true,
                code: "Digit1",
                key: "1",
                scope: "global",
              },
            ],
            run: () => openTab("console"),
            shown: panelVisible && activePanes.includes("console"),
          },
          "panel/python": {
            id: "panel.python",
            icon: "python",
            group: "panel",
            chords: [
              {
                mod: true,
                shift: true,
                code: "Digit2",
                key: "2",
                scope: "global",
              },
            ],
            run: () => openTab("python"),
            shown: panelVisible && activePanes.includes("python"),
          },
          "panel/logs": {
            id: "panel.logs",
            icon: "logs",
            group: "panel",
            chords: [
              {
                mod: true,
                shift: true,
                code: "Digit3",
                key: "3",
                scope: "global",
              },
              {
                mod: true,
                shift: true,
                code: "KeyL",
                key: "L",
                scope: "global",
              },
            ],
            run: () => openTab("logs"),
            shown: panelVisible && activePanes.includes("logs"),
          },
        } satisfies Record<string, ViewActionSpec>,
        (id) => {
          const resolved = resolveView({
            viewId: id,
            params: {},
            prefer: null,
          });
          return resolved.kind === "opened" && resolved.opened === id;
        },
        (id) => openView(id),
      ),
      {
        // The link to the main view shown: the first pane's page, or its
        // Ledger section. A pane beside it is not a place a link returns to.
        id: "view.copyLink",
        label: t("desktop.palette.copy_link"),
        group: "views",
        icon: "link",
        keywords: t("desktop.palette.keywords.copy_link"),
        enabled: () => shownViewId !== undefined,
        run: () => {
          if (shownViewId !== undefined)
            copy(formatViewLink(NAVIGATION, shownViewId));
        },
      },
      {
        id: "view.messages",
        label: t("desktop.rail.messages"),
        group: "views",
        icon: "mail",
        keywords: t("desktop.palette.keywords.messages"),
        enabled: () => views !== undefined,
        // The notifications are read in the TUI; the window shows the count.
        // Why there is no count is said where a tap reaches too, not only
        // in a tooltip.
        run: () => {
          if (messages.kind === "failed")
            say(
              labelled(
                t,
                t("desktop.rail.messages"),
                t("desktop.messages.failed"),
              ),
            );
          else if (
            messages.kind === "ready" &&
            messages.summary.captured_at === null
          )
            say(
              labelled(
                t,
                t("desktop.rail.messages"),
                t("desktop.messages.never"),
              ),
            );
          showTui();
        },
      },
      {
        id: "link.aeat",
        label: t("desktop.browser.external"),
        context: t("desktop.rail.aeat"),
        group: "links",
        icon: "external",
        keywords: t("desktop.palette.keywords.aeat_link"),
        run: () => openLink(AEAT_SEDE),
      },
      {
        id: "link.drive",
        label: t("desktop.google.open_drive"),
        group: "links",
        icon: "folder",
        keywords: t("desktop.palette.keywords.drive_link"),
        enabled: () => driveUrl !== null,
        run: () => {
          if (driveUrl) openLink(driveUrl);
        },
      },
    ],
    [
      t,
      calendarVisible,
      ledgerVisible,
      declarationsVisible,
      browserVisible,
      wantsCalendar,
      wantsLedger,
      wantsDeclarations,
      setMaximized,
      setPage,
      showBrowser,
      toggleColumn,
      docsVisible,
      maximized,
      signedIn,
      agentVisible,
      tuiVisible,
      layout.panelOpen,
      layout.tab,
      panelVisible,
      openTab,
      patch,
      activePanes,
      resolveView,
      openView,
      shownViewId,
      copy,
      views,
      messages,
      say,
      showTui,
      openLink,
      driveUrl,
    ],
  );
}
