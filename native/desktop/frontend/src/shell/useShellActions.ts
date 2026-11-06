import {
  useMemo,
  type Dispatch,
  type RefObject,
  type SetStateAction,
} from "react";
import type { DocsLanguage } from "@/ipc/environment";
import type { SetupItemId, SetupRun } from "@/ipc/componentSetup";
import type { DocsFrameApi } from "../components/DocsFrame";
import type { TerminalApi } from "../components/TerminalPane";
import { canSignInGoogle, itemName } from "../components/setup/setupWords";
import type { AboutState } from "./about";
import { viewActions, type Action, type ViewActionSpec } from "./actions";
import { labelled } from "./compose";
import {
  orientDockPane,
  swapDockPane,
  type DockLayout,
  type DockPane,
} from "./docking";
import { activeTerminal, focusedArea } from "./focusedArea";
import type { Host, TerminalKind } from "./host";
import type { Layout, Maximized, PanelTab, Prefs } from "./layout";
import { AEAT_SEDE } from "./links";
import type { MessagesState } from "./messages";
import { formatViewLink } from "./navigation/links";
import { NAVIGATION } from "./navigation/projection";
import type { useNavigator } from "./navigation/useNavigator";
import type { ProvisioningStore } from "./provisioning";
import { levelRank, type RecordFilters } from "./records";
import { liveRunOf, needsSetup, type SetupControl } from "./setup";
import type { Translate } from "./strings";
import type { useFullscreen } from "./useFullscreen";
import { WORKSPACE_COLUMNS } from "./useWorkspaceFocus";

type Navigator = ReturnType<typeof useNavigator>;
type Flag = Dispatch<SetStateAction<boolean>>;
type Column = (typeof WORKSPACE_COLUMNS)[number];

/** The window's single action registry: the palette, the shortcuts, the
 * rail and the menus all run what it declares. */
export function useShellActions({
  t,
  fullscreen,
  enterFullscreen,
  setPaletteExtra,
  setPaletteOpen,
  contributed,
  docsSearchReady,
  docsEntry,
  docs,
  goHome,
  pageOn,
  patch,
  layout,
  prefs,
  maximized,
  setMaximized,
  toggleMaximize,
  agentVisible,
  tuiVisible,
  docsVisible,
  firstPaneShown,
  panelVisible,
  activePanes,
  narrowedPanes,
  changeDocking,
  setPrefs,
  selectLogLevel,
  openTab,
  setFilters,
  defaultFilters,
  host,
  revealLogs,
  setSettingsOpen,
  about,
  setAboutOpen,
  setup,
  setupOffered,
  setupSnapshot,
  setupLive,
  setupRetryable,
  setupCancellable,
  openSetup,
  calendarVisible,
  ledgerVisible,
  declarationsVisible,
  browserVisible,
  wantsCalendar,
  wantsLedger,
  wantsDeclarations,
  setPage,
  showBrowser,
  toggleColumn,
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
  mayEnterPassword,
  askSignIn,
  canCreateProfile,
  offersProfiles,
  askNewProfile,
  signedIn,
  signOut,
  setSignInDismissed,
  setManagingProfiles,
  switchProfile,
  askCenso,
  cycleFocus,
  terminals,
  paste,
}: {
  t: Translate;
  fullscreen: ReturnType<typeof useFullscreen>;
  enterFullscreen: ReturnType<typeof useFullscreen>["toggle"];
  setPaletteExtra: Dispatch<SetStateAction<Action[]>>;
  setPaletteOpen: Flag;
  contributed: RefObject<(() => Action[]) | null>;
  docsSearchReady: boolean;
  docsEntry: DocsLanguage | null;
  docs: RefObject<DocsFrameApi | null>;
  goHome: () => void;
  pageOn: boolean;
  patch: (change: Partial<Layout>) => void;
  layout: Layout;
  prefs: Prefs;
  maximized: Maximized;
  setMaximized: (update: SetStateAction<Maximized>) => void;
  toggleMaximize: (area: Exclude<Maximized, null>) => void;
  agentVisible: boolean;
  tuiVisible: boolean;
  docsVisible: boolean;
  firstPaneShown: boolean;
  panelVisible: boolean;
  activePanes: DockPane[];
  narrowedPanes: readonly DockPane[];
  changeDocking: (update: (current: DockLayout) => DockLayout) => void;
  setPrefs: Dispatch<SetStateAction<Prefs>>;
  selectLogLevel: (minLevel: number) => void;
  openTab: (tab: PanelTab, options?: { toggle?: boolean }) => void;
  setFilters: (update: SetStateAction<RecordFilters>) => void;
  defaultFilters: RecordFilters;
  host: Host;
  revealLogs: () => void;
  setSettingsOpen: Flag;
  about: AboutState | null;
  setAboutOpen: Flag;
  setup: SetupControl;
  setupOffered: boolean;
  setupSnapshot: SetupControl["snapshot"];
  setupLive: SetupRun[];
  setupRetryable: { item: SetupItemId; resume: boolean }[];
  setupCancellable: SetupRun[];
  openSetup: ProvisioningStore["open"];
  calendarVisible: boolean;
  ledgerVisible: boolean;
  declarationsVisible: boolean;
  browserVisible: boolean;
  wantsCalendar: RefObject<boolean>;
  wantsLedger: RefObject<boolean>;
  wantsDeclarations: RefObject<boolean>;
  setPage: (next: Layout["page"]) => void;
  showBrowser: () => void;
  toggleColumn: (column: Column) => void;
  resolveView: Navigator["resolve"];
  openView: Navigator["openView"];
  shownViewId: string | undefined;
  copy: (text: string) => void;
  views: Host["views"];
  messages: MessagesState;
  say: (text: string) => void;
  showTui: () => void;
  openLink: (url: string) => void;
  driveUrl: string | null;
  mayEnterPassword: boolean;
  askSignIn: () => void;
  canCreateProfile: boolean;
  offersProfiles: boolean;
  askNewProfile: () => void;
  signedIn: boolean;
  signOut: () => void;
  setSignInDismissed: Flag;
  setManagingProfiles: Flag;
  switchProfile: () => void;
  askCenso: () => void;
  cycleFocus: (step: 1 | -1) => void;
  terminals: RefObject<Partial<Record<TerminalKind, TerminalApi>>>;
  paste: (kind: TerminalKind | null) => void;
}): Action[] {
  // The single action registry.
  const actions = useMemo<Action[]>(
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
      {
        id: "docs.search",
        label: t("desktop.palette.documentation"),
        group: "docs",
        icon: "book",
        enabled: () => !docsSearchReady && docsEntry !== null,
        run: () => docs.current?.openSearch(),
      },
      {
        id: "docs.home",
        label: t("desktop.rail.docs_home"),
        group: "docs",
        icon: "book",
        chords: [{ alt: true, code: "Home", key: "Home", scope: "docs" }],
        run: goHome,
      },
      {
        id: "docs.back",
        label: t("desktop.action.docs_back"),
        group: "docs",
        icon: "back",
        chords: [{ alt: true, code: "ArrowLeft", key: "←", scope: "docs" }],
        enabled: () => !pageOn,
        run: () => docs.current?.back(),
      },
      {
        id: "docs.forward",
        label: t("desktop.action.docs_forward"),
        group: "docs",
        icon: "forward",
        chords: [{ alt: true, code: "ArrowRight", key: "→", scope: "docs" }],
        enabled: () => !pageOn,
        run: () => docs.current?.forward(),
      },
      {
        id: "docs.zoomIn",
        label: t("desktop.action.zoom_in"),
        group: "docs",
        icon: "zoomIn",
        chords: [{ mod: true, code: "Equal", key: "=", scope: "docs" }],
        enabled: () => !pageOn,
        run: () =>
          patch({
            zoom: Math.min(2, Math.round((layout.zoom + 0.1) * 10) / 10),
          }),
      },
      {
        id: "docs.zoomOut",
        label: t("desktop.action.zoom_out"),
        group: "docs",
        icon: "zoomOut",
        chords: [{ mod: true, code: "Minus", key: "-", scope: "docs" }],
        enabled: () => !pageOn,
        run: () =>
          patch({
            zoom: Math.max(0.5, Math.round((layout.zoom - 0.1) * 10) / 10),
          }),
      },
      {
        id: "docs.zoomReset",
        label: t("desktop.action.zoom_reset"),
        group: "docs",
        icon: "reset",
        chords: [{ mod: true, code: "Digit0", key: "0", scope: "docs" }],
        enabled: () => !pageOn,
        run: () => patch({ zoom: 1 }),
      },
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
      {
        id: "logs.errors",
        label: t("desktop.action.logs_errors"),
        group: "logs",
        icon: "logs",
        run: () => {
          selectLogLevel(levelRank("ERROR"));
          openTab("logs", { toggle: false });
        },
      },
      {
        id: "logs.reset",
        label: t("desktop.action.logs_reset"),
        group: "logs",
        icon: "logs",
        run: () => setFilters(defaultFilters),
      },
      {
        id: "logs.reveal",
        label: t("desktop.logs.reveal"),
        group: "logs",
        icon: "logs",
        enabled: () => !!host.revealLogs,
        run: revealLogs,
      },
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
      {
        id: "setup.open",
        label: t("desktop.setup.palette_open"),
        group: "setup",
        icon: "download",
        keywords: t("desktop.palette.keywords.setup_open"),
        enabled: () => setupOffered,
        run: () => openSetup(null),
      },
      {
        id: "setup.check",
        label: t("desktop.setup.palette_check"),
        group: "setup",
        icon: "check",
        keywords: t("desktop.palette.keywords.setup_check"),
        enabled: () => setupOffered && setupLive.length === 0,
        run: () => {
          openSetup(null);
          setup.check("full");
        },
      },
      // One way to each element the engine reports: it opens the panel on
      // that element, and sets it up where it can be.
      ...(setupSnapshot?.rows ?? []).map((row): Action => ({
        id: `setup.item.${row.item}`,
        label: t("desktop.setup.palette_item", {
          name: itemName(t, row.item),
        }),
        group: "setup",
        icon: "download",
        enabled: () => setupOffered,
        run: () => {
          openSetup(row.item);
          if (needsSetup(row) && liveRunOf(setupSnapshot, row.item) === null)
            setup.start(row.item, { resume: row.recovery === "resume" });
        },
      })),
      {
        id: "setup.retry",
        label: t("desktop.setup.palette_retry"),
        group: "setup",
        icon: "reset",
        enabled: () => setupOffered && setupRetryable.length > 0,
        run: () => {
          openSetup(null);
          for (const { item, resume } of setupRetryable)
            setup.start(item, { resume });
        },
      },
      {
        id: "setup.cancel",
        label: t("desktop.setup.palette_cancel"),
        group: "setup",
        icon: "stop",
        enabled: () => setupOffered && setupCancellable.length > 0,
        run: () => {
          for (const run of setupCancellable) setup.cancel(run.item);
        },
      },
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
      {
        id: "account.signIn",
        label: t("desktop.signin.submit"),
        group: "account",
        icon: "lock",
        keywords: t("desktop.palette.keywords.sign_in"),
        enabled: () => mayEnterPassword,
        run: askSignIn,
      },
      {
        id: "account.createProfile",
        label: t("desktop.account.new_profile"),
        group: "account",
        icon: "userAdd",
        keywords: t("desktop.palette.keywords.create_profile"),
        enabled: () => canCreateProfile && offersProfiles,
        run: askNewProfile,
      },
      {
        id: "account.signOut",
        label: t("desktop.account.sign_out"),
        group: "account",
        icon: "signOut",
        keywords: t("desktop.palette.keywords.sign_out"),
        enabled: () => signedIn,
        run: signOut,
      },
      {
        // The profile's own Google sign-in; not part of setup.
        id: "account.google",
        label: t("desktop.google.palette_sign_in"),
        group: "account",
        icon: "user",
        keywords: t("desktop.palette.keywords.google_sign_in"),
        enabled: () =>
          signedIn &&
          setupOffered &&
          canSignInGoogle(setupSnapshot?.google ?? null),
        run: () => setup.signInGoogle(),
      },
      {
        id: "account.manageProfiles",
        label: t("desktop.account.manage.title"),
        group: "account",
        icon: "users",
        keywords: t("desktop.palette.keywords.manage_profiles"),
        enabled: () => host.profiles !== undefined,
        run: () => {
          setSignInDismissed(true);
          setManagingProfiles(true);
        },
      },
      {
        id: "account.switchProfile",
        label: t("desktop.account.switch_profile"),
        group: "account",
        icon: "swap",
        keywords: t("desktop.palette.keywords.switch_profile"),
        enabled: () => signedIn && canCreateProfile,
        run: switchProfile,
      },
      {
        // The one census flow, from any page: the profile page runs it.
        id: "census.sync",
        label: t("desktop.profile.censo.title"),
        group: "profile",
        icon: "sync",
        keywords: t("desktop.palette.keywords.census_sync"),
        enabled: () => signedIn && !!host.censo && !!host.userProfile,
        run: askCenso,
      },
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
      {
        id: "terminal.copy",
        label: t("desktop.menu.copy"),
        group: "terminal",
        icon: "copy",
        hidden: true,
        chords: [
          { mod: true, shift: true, code: "KeyC", key: "C", scope: "terminal" },
        ],
        // Only the focused terminal's selection; without one, nothing.
        run: () => {
          const kind = activeTerminal();
          if (kind) copy(terminals.current[kind]?.selection() ?? "");
        },
      },
      {
        id: "terminal.paste",
        label: t("desktop.menu.paste"),
        group: "terminal",
        icon: "paste",
        hidden: true,
        chords: [
          { mod: true, shift: true, code: "KeyV", key: "V", scope: "terminal" },
        ],
        run: () => paste(activeTerminal()),
      },
    ],
    [
      t,
      fullscreen.fullscreen,
      panelVisible,
      activePanes,
      enterFullscreen,
      changeDocking,
      setMaximized,
      setPage,
      about,
      agentVisible,
      tuiVisible,
      docsVisible,
      firstPaneShown,
      toggleColumn,
      openView,
      resolveView,
      shownViewId,
      layout.panelOpen,
      layout.tab,
      layout.zoom,
      prefs.orientation,
      narrowedPanes,
      maximized,
      docsSearchReady,
      docsEntry,
      views,
      messages,
      say,
      showTui,
      pageOn,
      calendarVisible,
      ledgerVisible,
      declarationsVisible,
      browserVisible,
      showBrowser,
      askSignIn,
      askNewProfile,
      canCreateProfile,
      offersProfiles,
      mayEnterPassword,
      signedIn,
      signOut,
      switchProfile,
      askCenso,
      cycleFocus,
      openLink,
      driveUrl,
      host,
      revealLogs,
      goHome,
      patch,
      toggleMaximize,
      openTab,
      copy,
      paste,
      setFilters,
      selectLogLevel,
      defaultFilters,
      setup,
      setupOffered,
      setupSnapshot,
      setupLive,
      setupRetryable,
      setupCancellable,
      openSetup,
      contributed,
      docs,
      terminals,
      wantsCalendar,
      wantsLedger,
      wantsDeclarations,
      setPaletteExtra,
      setPaletteOpen,
      setPrefs,
      setSettingsOpen,
      setAboutOpen,
      setSignInDismissed,
      setManagingProfiles,
    ],
  );
  return actions;
}
