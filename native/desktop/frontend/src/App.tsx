import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import settings from "virtual:operational-settings";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toast } from "@/components/ui/toast";
import { AboutDialog } from "./components/AboutDialog";
import { AccountDialogs, type SignInOpener } from "./components/AccountDialogs";
import { AccountMenu } from "./components/AccountMenu";
import type { AgentColumnControl } from "./components/AgentColumn";
import { AttendanceRequests } from "./components/AttendanceRequests";
import { CommandPalette, type PastedLink } from "./components/CommandPalette";
import {
  ContextMenu,
  type MenuAction,
  type MenuAnchor,
  type MenuEntry,
} from "./components/ContextMenu";
import type { DocsFrameApi } from "./components/DocsFrame";
import { GoogleAccount } from "./components/GoogleAccount";
import type { LeaveGuard } from "./components/ledger/editing/LedgerEditing";
import { MainPane } from "./components/MainPane";
import { NavigationPrompt } from "./components/NavigationPrompt";
import type { PaneControl } from "./components/PaneHeader";
import { Rail } from "./components/Rail";
import { railItems } from "./components/railItems";
import { ReconnectingNotice } from "./components/ReconnectingNotice";
import { Settings } from "./components/Settings";
import { ProvisioningPanel } from "./components/setup/ProvisioningPanel";
import { ShellDock } from "./components/ShellDock";
import type { TerminalApi, TerminalStatus } from "./components/TerminalPane";
import { Titlebar } from "./components/Titlebar";
import type { DocsTheme } from "./ipc/docsBridge";
import { useAbout } from "./shell/about";
import { primaryChord, type Action } from "./shell/actions";
import type { ModelList } from "./shell/agentModelList";
import { useFilingCalendar } from "./shell/calendar";
import { activateDockPane, type DockPane } from "./shell/docking";
import type { Host, TerminalKind } from "./shell/host";
import {
  DEFAULT_LAYOUT,
  DEFAULT_PREFS,
  type Layout,
  type LedgerView,
  type Maximized,
  type ProfileView,
} from "./shell/layout";
import { useMessages } from "./shell/messages";
import { useMetric, useTerminalFontSize } from "./shell/metrics";
import { isCadrumoLink, parseViewLink } from "./shell/navigation/links";
import { NAVIGATION } from "./shell/navigation/projection";
import { elementOf } from "./shell/navigation/register";
import {
  refusalReasonText,
  useNavigator,
} from "./shell/navigation/useNavigator";
import { useWindowCloseGuard } from "./shell/navigation/useWindowCloseGuard";
import {
  mountedNow,
  pageViewId,
  type WindowViewEntry,
} from "./shell/navigation/windowViews";
import { ShellContexts } from "./shell/ShellContexts";
import { useSignIn } from "./shell/signIn";
import {
  OUTPUT_LANGUAGES,
  SOURCE_LOCALE,
  translator,
  type Translate,
} from "./shell/strings";
import { DARK_TERMINAL, LIGHT_TERMINAL } from "./shell/terminalThemes";
import { useColumnCommands } from "./shell/useColumnCommands";
import { useDesktopEnvironment } from "./shell/useDesktopEnvironment";
import { useDocsNavigation } from "./shell/useDocsNavigation";
import { useFocusCycle } from "./shell/useFocusCycle";
import { useFocusWish } from "./shell/useFocusWish";
import { useFullscreen } from "./shell/useFullscreen";
import { useHostClipboard } from "./shell/useHostClipboard";
import { useHostNotices } from "./shell/useHostNotices";
import { useLanguage } from "./shell/useLanguage";
import { useLogControls } from "./shell/useLogControls";
import { usePageMemories } from "./shell/usePageMemories";
import { usePersistedLayout } from "./shell/usePersistedLayout";
import { usePersonActivity } from "./shell/usePersonActivity";
import { useShellActions } from "./shell/useShellActions";
import { useShellLayout } from "./shell/useShellLayout";
import { useShellMenus } from "./shell/useShellMenus";
import { useShellShortcuts } from "./shell/useShellShortcuts";
import { useToastMessage } from "./shell/useToastMessage";
import { useUserProfile } from "./shell/userProfile";
import { useWindowPresentation } from "./shell/useWindowPresentation";
import { useWindowSetup } from "./shell/useWindowSetup";
import { useWorkspaceFocus } from "./shell/useWorkspaceFocus";
import { useWorkspaceVisibility } from "./shell/useWorkspaceVisibility";

type OpenMenu = { items: MenuEntry[]; at: MenuAnchor };

const isAction = (item: MenuEntry): item is MenuAction => "id" in item;

export function App({ host }: { host: Host }) {
  const account = useSignIn(host);
  const environment = useDesktopEnvironment(host);
  const language = useLanguage(
    host,
    environment.state === "ready"
      ? environment.value.outputLanguage
      : SOURCE_LOCALE,
    { phase: account.phase, profile: account.status?.active_profile ?? null },
  );
  const locale = language.locale;
  const languages = OUTPUT_LANGUAGES;
  const languageControl = {
    value: locale,
    languages,
    pending: language.pending,
    failed: language.failed,
    onChange: (code: string) => void language.change(code),
  };

  const workspace = useRef<HTMLDivElement>(null);
  const { viewportWidth, prefersDark } = useWindowPresentation(workspace);
  // How many log records are errors, as the log view reports it.
  const [errorCount, setErrorCount] = useState(0);
  const {
    prefs,
    setPrefs,
    layout,
    setLayout,
    docking,
    changeDocking,
    setMaximized,
  } = useShellLayout();
  // Panes whose side-by-side split the window is too narrow to draw.
  const [narrowedPanes, setNarrowedPanes] = useState<readonly DockPane[]>([]);
  const fullscreen = useFullscreen(host, () =>
    say(t("desktop.titlebar.failed")),
  );
  const enterFullscreen = fullscreen.toggle;
  const revealPane = fullscreen.reveal;
  const activatePane = useCallback(
    (pane: DockPane) => {
      revealPane(pane);
      changeDocking((current) => activateDockPane(current, pane));
    },
    [changeDocking, revealPane],
  );
  // The least width the Ledger page asks beside the agent, while it shows.
  const [ledgerFloor, setLedgerFloor] = useState<number | null>(null);
  // Account gating affects presentation without erasing the saved arrangement.
  const maximized =
    layout.maximized === "agent" && account.phase !== "signed-in"
      ? null
      : layout.maximized;
  // What the first pane shows: the documentation, or a view of the profile
  // where the host offers one. The documentation stays loaded underneath.
  const page = layout.page;
  // Every navigation passes one guard register and one navigator: a link,
  // the palette, the rail, a page, sign-out, a profile switch and the
  // window's close. What it calls back is read when it runs, after render.
  const layoutNow = useRef(layout);
  layoutNow.current = layout;
  const nav = useNavigator({
    register: NAVIGATION,
    t: (key, values) => t(key, values),
    say: (text) => say(text),
    shown: () => ({
      page: layoutNow.current.page,
      ledgerSection: layoutNow.current.ledgerView.section,
    }),
    hasPort: (port) => host[port] !== undefined,
    signedIn: () => accountRef.current.phase === "signed-in",
    showInWindow: (id, entry) => showInWindow(id, entry),
    askSignIn: () => askSignIn(),
  });
  const guardNavigation = nav.guard;
  // An owner that hands the shell a leave guard of its own is registered as
  // dirty work of the page it was shown on; its guard asks only when it has
  // something staged. `guarded` leaves the page shown.
  const ownerGuard = useRef<(() => void) | null>(null);
  const guardLeave = useCallback(
    (guard: LeaveGuard | null) => {
      ownerGuard.current?.();
      ownerGuard.current = guard
        ? nav.runtime.guards.register({
            owner: layoutNow.current.page,
            state: () => "dirty",
            ask: guard,
          })
        : null;
    },
    [nav.runtime],
  );
  const guarded = useCallback(
    (proceed: () => void, stay?: () => void) =>
      guardNavigation(
        {
          kind: "navigate",
          unmounted: mountedNow(
            layoutNow.current.page,
            layoutNow.current.ledgerView.section,
          ),
        },
        proceed,
        stay,
      ),
    [guardNavigation],
  );
  useWindowCloseGuard(host, guardNavigation);
  // Shows a page through the layout store; only the navigator, past the
  // guards, calls it directly.
  const showPage = useCallback(
    (page: Layout["page"]) => {
      revealPane("docs");
      setLayout((current) => ({
        ...current,
        page,
        docking: current.docking
          ? activateDockPane(current.docking, "docs")
          : null,
      }));
    },
    [revealPane, setLayout],
  );
  // Leaving the page shown takes it down, so its owners are asked first.
  const setPage = useCallback(
    (next: Layout["page"]) => {
      const shown = layoutNow.current;
      if (next === shown.page) {
        activatePane("docs");
        return;
      }
      guardNavigation(
        {
          kind: "navigate",
          unmounted: mountedNow(shown.page, shown.ledgerView.section),
        },
        () => showPage(next),
      );
    },
    [guardNavigation, showPage, activatePane],
  );
  // The census pull was asked for from any page: the profile page takes the
  // one census flow over once it has the profile, and starts it only when
  // none is running. Leaving the page withdraws the ask.
  const [censoAsked, setCensoAsked] = useState(false);
  const censoHandled = useCallback(() => setCensoAsked(false), []);
  const askCenso = useCallback(() => {
    const shown = layoutNow.current;
    const proceed = () => {
      setCensoAsked(true);
      setLayout((current) => ({
        ...current,
        page: "profile",
        maximized: null,
      }));
    };
    if (shown.page === "profile") proceed();
    else
      guardNavigation(
        {
          kind: "navigate",
          unmounted: mountedNow(shown.page, shown.ledgerView.section),
        },
        proceed,
      );
  }, [guardNavigation, setLayout]);
  const calendarPage = useRef<HTMLElement>(null);
  const aeatSyncPage = useRef<HTMLElement>(null);
  const profilePage = useRef<HTMLElement>(null);
  const ledgerPage = useRef<HTMLElement>(null);
  // The ledger was asked for: it takes focus once it is laid out.
  const wantsLedger = useRef(false);
  const declarationsPage = useRef<HTMLElement>(null);
  // The declarations, or one declaration, were asked for: the page takes
  // focus once it is laid out.
  const wantsDeclarations = useRef(false);
  const browserPage = useRef<HTMLElement>(null);
  // The browser was asked for: the page takes focus once it is laid out.
  const wantsBrowser = useRef(false);
  // The agent column was asked for: it takes focus once it is laid out.
  const wantsAgent = useRef(false);
  const agentBody = useRef<HTMLElement>(null);
  // Where the keyboard goes when a navigation opens each page or the agent.
  // The window provides the navigation context, so it registers its own
  // targets on the runtime directly; its commits are their mount signal.
  useEffect(() => {
    const focus = nav.runtime.focus;
    const targets: [string, { current: HTMLElement | null }][] = [
      ["profile", profilePage],
      ["calendar", calendarPage],
      ["aeat-sync", aeatSyncPage],
      ["ledger", ledgerPage],
      ["declarations", declarationsPage],
      ["agent", agentBody],
      // The documentation is a frame the window does not hold a ref to.
      [
        "docs",
        {
          get current() {
            return document.querySelector<HTMLElement>(".docs-frame");
          },
        },
      ],
    ];
    const releases = targets.map(([id, ref]) =>
      focus.register(id, () => ref.current),
    );
    return () => releases.forEach((release) => release());
  }, [nav.runtime]);
  // The calendar was asked for: it takes focus once it is laid out.
  const wantsCalendar = useRef(false);
  // What held focus when the sign-in dialog was asked for, and whether
  // that was in the calendar: the control itself may be gone by the close.
  const signInOpener = useRef<SignInOpener>(null);
  const [docsTheme, setDocsTheme] = useState<DocsTheme>("auto");
  const [docsSearchReady, setDocsSearchReady] = useState(false);
  const [status, setStatus] = useState<Record<TerminalKind, TerminalStatus>>({
    console: { phase: "starting" },
    python: { phase: "starting" },
    tui: { phase: "starting" },
  });
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
  const about = useAbout(host);
  const [menu, setMenu] = useState<OpenMenu | null>(null);
  const { toast, say } = useToastMessage(settings.shell_toast_ms);
  // The sign-in dialog opens by itself whenever the TUI becomes gated; a
  // person who dismisses it, or who has just signed out here, reopens it.
  const [signInDismissed, setSignInDismissed] = useState(false);
  // The dialog as the form that creates a profile, where one was asked for.
  const [creatingProfile, setCreatingProfile] = useState(false);
  const [managingProfiles, setManagingProfiles] = useState(false);
  const signInButton = useRef<HTMLButtonElement>(null);
  const docs = useRef<DocsFrameApi>(null);
  const terminals = useRef<Partial<Record<TerminalKind, TerminalApi>>>({});

  // Layout geometry, read from the canonical tokens (src/styles/tokens.css) instead
  // of duplicated as literals; each metric re-reads on resize.
  const splitMinA = useMetric("--split-min-a", 260);
  const splitMinBRow = useMetric("--split-min-b-row", 320);
  const railWidth = useMetric("--rail-w", 48);
  const agentMin = useMetric("--agent-min", 240);
  const docsMin = useMetric("--docs-min", 200);
  const panelMin = useMetric("--panel-min", 140);
  const terminalFontSize = useTerminalFontSize(prefs.fontSize);

  const patch = useCallback(
    (change: Partial<Layout>) => {
      const pane =
        change.tab ??
        (change.agentShown
          ? "agent"
          : change.tuiShown
            ? "tui"
            : change.docsShown
              ? "docs"
              : change.panelOpen
                ? layoutNow.current.tab
                : null);
      if (pane) revealPane(pane);
      setLayout((current) => {
        let docking = current.docking;
        if (docking && pane) docking = activateDockPane(docking, pane);
        return { ...current, docking, ...change };
      });
    },
    [revealPane, setLayout],
  );
  // The documentation asked for by name: its pane is shown first.
  const showDocs = useCallback(() => {
    setPage("docs");
    setMaximized((area) => (area === "docs" ? area : null));
    patch({ docsShown: true });
  }, [patch, setPage, setMaximized]);

  usePersistedLayout(prefs, layout, settings.layout_save_delay_ms);

  const gated = account.gated;
  const phase = account.phase;
  const signedIn = phase === "signed-in";
  // The sign-in form is asked for by a gate that withholds the TUI, and by a
  // session the runtime keeps suspended that only the password can bring back.
  const signInAsked = gated || account.reconnecting?.passwordRequired === true;
  usePersonActivity(host, signedIn);
  const accountRef = useRef(account);
  accountRef.current = account;
  const signOut = useCallback(() => {
    guardNavigation({ kind: "sign_out" }, () => {
      // Signing out here is not a reason to ask for the password again.
      setSignInDismissed(true);
      void accountRef.current.signOut();
    });
  }, [guardNavigation]);
  // The palette shortcut enters the same account flow as the header.
  const switchProfile = useCallback(() => {
    guardNavigation({ kind: "switch" }, () => {
      setSettingsOpen(false);
      signInOpener.current = null;
      setSignInDismissed(false);
      void accountRef.current.signOut();
    });
  }, [guardNavigation]);
  useEffect(() => {
    if (signInAsked) return;
    // Admitted: the next time the gate closes, the dialog opens again, and
    // as the sign-in, whatever it was last asked to be.
    setSignInDismissed(false);
    setCreatingProfile(false);
  }, [signInAsked]);
  const signOutFailed = account.signOutFailure !== null;
  useEffect(() => {
    // A sign-out that failed leaves the person signed in: the next time the
    // gate closes it is not by their choice, so the dialog opens.
    if (signOutFailed) setSignInDismissed(false);
  }, [signOutFailed]);
  const mayEnterPassword = account.canSignIn;

  const views = host.views;
  const {
    profileOn,
    calendarOn,
    ledgerOn,
    declarationsOn,
    browserOn,
    aeatSyncOn,
    pageOn,
    agentFits,
    dockOffered,
    expandedPane,
    activePanes,
    firstPaneShown,
    dockMinimumWidths,
    dockBesideWidths,
    dockMinimumHeights,
    docsVisible,
    calendarVisible,
    ledgerVisible,
    declarationsVisible,
    browserVisible,
    tuiVisible,
    panelVisible,
    mainOccupied,
    agentVisible,
  } = useWorkspaceVisibility({
    host,
    layout,
    docking,
    maximized,
    fullscreenPane: fullscreen.pane,
    signedIn,
    viewportWidth,
    railWidth,
    splitMinA,
    splitMinBRow,
    agentMin,
    docsMin,
    panelMin,
    ledgerFloor,
  });
  // Whose views are read: the signed-in profile's. Where the platform signs
  // in inside the TUI the shell cannot tell, so it asks and shows the answer.
  const reader =
    signedIn || phase === "unsupported"
      ? (account.status?.active_profile ?? "")
      : null;
  const recheckAccount = useCallback(() => accountRef.current.recheck(), []);
  const {
    setBrowserKeptFor,
    browserMounted,
    browserHome,
    setBrowserHome,
    calendarMemory,
    ledgerMemory,
    openDeclaration,
    openWorkUnit,
  } = usePageMemories({ reader, browserOn, wantsDeclarations });
  const calendar = useFilingCalendar(
    views,
    reader,
    calendarVisible,
    recheckAccount,
    locale,
  );
  const calendarProfile = useUserProfile(
    host.userProfile,
    reader,
    locale,
    calendarVisible,
  );
  const observedMessages = useMessages(views, reader, recheckAccount, locale);
  // Withhold private counts in the same render as the account gate. The
  // existing hook settles old reads and clears its cache in its effect.
  const messages = useMemo(
    () => (reader === null ? { kind: "unknown" as const } : observedMessages),
    [reader, observedMessages],
  );
  // The keyboard goes to the calendar when it was asked for and is laid
  // out. Put away, focus stays where it is, unless it was in the page: then
  // it goes to what the pane shows instead.
  const calendarWas = useRef(calendarVisible);
  useEffect(() => {
    if (calendarVisible && wantsCalendar.current) {
      wantsCalendar.current = false;
      calendarPage.current?.focus();
    } else if (
      !calendarVisible &&
      calendarWas.current &&
      firstPaneShown &&
      document.activeElement === document.body
    )
      (
        docs.current ??
        document.querySelector<HTMLElement>(".rail [role=toolbar]")
      )?.focus();
    calendarWas.current = calendarVisible;
  }, [calendarVisible, firstPaneShown]);
  useEffect(() => {
    if (ledgerVisible && wantsLedger.current) {
      wantsLedger.current = false;
      ledgerPage.current?.focus();
    }
  }, [ledgerVisible]);
  useEffect(() => {
    if (declarationsVisible && wantsDeclarations.current) {
      wantsDeclarations.current = false;
      declarationsPage.current?.focus();
    }
  }, [declarationsVisible, openDeclaration]);
  useEffect(() => {
    if (browserVisible && wantsBrowser.current) {
      wantsBrowser.current = false;
      browserPage.current?.focus();
    }
  }, [browserVisible]);
  // The page asks for the Sede itself, so opening it names no address; shown
  // already, it only takes the keyboard.
  const showBrowser = useCallback(() => {
    if (browserVisible) {
      browserPage.current?.focus();
      return;
    }
    wantsBrowser.current = true;
    setMaximized((area) => (area === "docs" ? area : null));
    setPage("browser");
  }, [browserVisible, setMaximized, setPage]);
  // The AEAT shortcut: the browser at the Sede. A view already open is sent
  // back there; a new one starts there.
  const showSede = useCallback(() => {
    if (browserMounted) setBrowserHome((count) => count + 1);
    showBrowser();
  }, [browserMounted, showBrowser, setBrowserHome]);
  const askSignIn = useCallback(() => {
    const element = document.activeElement;
    signInOpener.current = {
      element,
      calendar: element?.closest(".calendar-page") != null,
    };
    setSignInDismissed(false);
  }, []);
  const canCreateProfile = account.canCreate;
  // Another profile, or a new one, only while nobody is signed in.
  const offersProfiles = account.offering;
  const askNewProfile = useCallback(() => {
    setSettingsOpen(false);
    askSignIn();
    setCreatingProfile(true);
  }, [askSignIn]);

  const t: Translate = useMemo(() => translator(locale), [locale]);

  const docsResolved =
    docsTheme === "auto" ? (prefersDark ? "dark" : "light") : docsTheme;
  const scheme =
    prefs.appearance === "follow" ? docsResolved : prefs.appearance;
  const terminalTheme =
    prefs.terminals === "dark" || scheme === "dark"
      ? DARK_TERMINAL
      : LIGHT_TERMINAL;

  useEffect(() => {
    document.documentElement.dataset.scheme = scheme;
    document.documentElement.lang = locale;
  }, [scheme, locale]);

  const { docsEntry, goHome, openDoc, searchDocs } = useDocsNavigation({
    environment,
    locale,
    docs,
    docsSearchReady,
    showDocs,
  });

  useHostNotices({ host, manager: account.manager, say, t });

  // An address opened in the system browser. A refusal is said aloud: the
  // person must not wait for a page that is not coming.
  const openLink = useCallback(
    (url: string) => {
      host.openExternal(url).catch(() => say(t("desktop.toast.open_failed")));
    },
    [host, say, t],
  );

  const { copy, paste } = useHostClipboard({ host, terminals, say, t });

  const {
    setup,
    setupOffered,
    setupSnapshot,
    driveUrl,
    setupLive,
    setupRetryable,
    setupCancellable,
    settledSetups,
    provisioning,
    setupIncomplete,
    openSetup,
    onToolRefused,
    routedLedger,
    profileHost,
  } = useWindowSetup({
    host,
    reader,
    signedIn,
    locale,
    held: (signInAsked && !signInDismissed) || managingProfiles,
    setSettingsOpen,
    say,
    t,
  });

  const {
    defaultFilters,
    filters,
    setFilters,
    selectLogLevel,
    copyLogs,
    revealLogs,
    exportLogs,
  } = useLogControls({
    host,
    environment,
    logLevel: layout.logLevel,
    setLayout,
    say,
    t,
  });

  const { grantFocus, focusView, focusRail } = useFocusWish({
    signInButton,
    terminals,
  });
  // Whether the last render showed a gate the person could act on, with
  // the dialog put aside. The first status read is a gate too, but not one
  // anybody was standing at: being let through it at startup moves no
  // focus. And with the dialog still up, its own close decides where focus
  // goes: this must not get there first.
  const stoodAtGate = useRef(false);
  useEffect(() => {
    // Admitted after the dialog was put aside: the way in that held focus
    // went with the gate, and the TUI that has started takes it.
    if (
      stoodAtGate.current &&
      !gated &&
      document.activeElement === document.body
    )
      focusView("tui");
    stoodAtGate.current =
      gated && phase !== "checking" && phase !== "starting" && signInDismissed;
  }, [gated, phase, signInDismissed, focusView]);
  useEffect(() => {
    // Signed out from here, no dialog follows. If the terminal that held
    // focus went with the session, the pane's way back in takes it.
    if (gated && signInDismissed && document.activeElement === document.body)
      focusView("tui");
  }, [gated, signInDismissed, focusView]);

  const { showTui, openTab, toggleMaximize, closeColumn, toggleColumn } =
    useColumnCommands({
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
    });

  const cycleFocus = useFocusCycle({
    agentVisible,
    firstPaneShown,
    tuiVisible,
    panelVisible,
    activePanes,
    gated,
    status,
    focusView,
    focusRail,
    profilePage,
    ledgerPage,
    declarationsPage,
    calendarPage,
    aeatSyncPage,
    docs,
    signInButton,
    agentBody,
  });

  const { openView, openLink: openViewLink, resolve: resolveView } = nav;
  // The model documents are read with is picked in the agent column's model
  // picker; a page beside a reading with no model leads to the picker.
  const agentSession = host.agentSession;
  const agentControl = useRef<AgentColumnControl>(null);
  const modelList = useMemo<ModelList | null>(
    () =>
      agentSession?.localModels && agentSession.chooseReadingModel
        ? {
            open: () => {
              openView("agent");
              agentControl.current?.openModelPicker();
            },
          }
        : null,
    [agentSession, openView],
  );
  // The register element of the main view shown: the first pane's page, or
  // its Ledger section; nothing while the first pane is put away.
  const shownViewId = firstPaneShown
    ? pageViewId(pageOn ? page : "docs", layout.ledgerView.section)
    : undefined;
  // A query that is a `cadrumo:` link is one palette entry: the view it
  // opens, or why it opens none.
  const pastedLink = useCallback(
    (text: string): PastedLink | null => {
      if (!isCadrumoLink(text)) return null;
      const parsed = parseViewLink(text, NAVIGATION);
      if (parsed.kind === "refused")
        return {
          label: refusalReasonText(t, NAVIGATION, parsed.reason, null),
          open: null,
        };
      const resolved = resolveView(parsed.link);
      if (resolved.kind === "refused")
        return {
          label: refusalReasonText(
            t,
            NAVIGATION,
            resolved.reason,
            parsed.link.viewId,
          ),
          open: null,
        };
      const element = elementOf(NAVIGATION, resolved.opened);
      return {
        label: t("desktop.palette.open_link", {
          view: element ? t(element.label) : resolved.opened,
        }),
        open: () => openViewLink(text),
      };
    },
    [t, resolveView, openViewLink],
  );

  const actions = useShellActions({
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
  });
  const actionsRef = useRef(actions);
  actionsRef.current = actions;
  const byId = (id: string) => actions.find((action) => action.id === id);
  // The profile page is large: what it is given stays the same object from
  // one render of the window to the next, so it draws only when it changes.
  const profileAccountActions = useCallback(
    () =>
      ["account.switchProfile", "account.manageProfiles", "account.signOut"]
        .map((id) => actionsRef.current.find((action) => action.id === id))
        .filter((action) => action !== undefined),
    [],
  );
  const toggleProfileMaximized = useCallback(
    () => toggleMaximize("docs"),
    [toggleMaximize],
  );
  const changeProfileView = useCallback(
    (update: (current: ProfileView) => ProfileView) =>
      setLayout((current) => ({
        ...current,
        profileView: update(current.profileView),
      })),
    [setLayout],
  );
  const changeLedgerView = useCallback(
    (update: (current: LedgerView) => LedgerView) =>
      setLayout((current) => ({
        ...current,
        ledgerView: update(current.ledgerView),
      })),
    [setLayout],
  );
  // The AEAT access editor was asked for: the profile page opens it once it
  // has the profile. Leaving the page withdraws the ask.
  const [aeatAsked, setAeatAsked] = useState(false);
  const aeatHandled = useCallback(() => setAeatAsked(false), []);
  useEffect(() => {
    if (layout.page !== "profile") {
      setAeatAsked(false);
      setCensoAsked(false);
    }
  }, [layout.page]);
  // A register element the navigator let through, applied to the layout
  // store. A page and the agent take the keyboard through the focus
  // register; the terminals and the panel through their own focus wishes.
  const showInWindow = (_id: string, entry: WindowViewEntry) => {
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
    else openTab(view.tab ?? layout.tab, { toggle: false });
  };
  const runAction = useCallback(
    (id: string) =>
      actionsRef.current.find((action) => action.id === id)?.run(),
    [],
  );
  const { isShellChord, chords, runShortcut } = useShellShortcuts(
    actions,
    actionsRef,
    paletteOpen,
    menu !== null ||
      (signInAsked && !signInDismissed && account.status !== null),
  );

  // Menus: the shell draws every one, in the Cadrumo theme, whichever host it
  // runs in. The caller places it: at the pointer, or at what holds focus.
  const openMenu = useCallback(
    (items: MenuEntry[], at: MenuAnchor) => setMenu({ items, at }),
    [],
  );

  const { docsMenu, aeatMenu, terminalMenu, recordMenu } = useShellMenus({
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
  });

  const panelMaximized = useWorkspaceFocus({
    agentVisible,
    tuiVisible,
    firstPaneShown,
    maximized,
    gated,
    tuiPhase: status.tui.phase,
    tab: layout.tab,
    focusView,
    focusRail,
    signInButton,
    profilePage,
    ledgerPage,
    declarationsPage,
    calendarPage,
    aeatSyncPage,
    docs,
    agentBody,
    wantsAgent,
  });

  const maximizeControl = (
    area: Exclude<Maximized, null>,
    labelKey: string,
  ): PaneControl => {
    const on = maximized === area;
    return {
      id: "maximize",
      icon: on ? "restore" : "maximize",
      label: on ? t("desktop.pane.restore") : t(labelKey),
      shortcut: primaryChord(byId("view.maximize")),
      pressed: on,
      run: () => toggleMaximize(area),
    };
  };
  const orientation = prefs.orientation;

  // The split's own controls, only while it holds both panes.
  const splitControls: PaneControl[] =
    maximized || !(firstPaneShown && tuiVisible)
      ? []
      : [
          {
            id: "swap",
            icon: "swap",
            label: t("desktop.split.swap"),
            run: () => runAction("split.swap"),
          },
          // While the window forces stacking, the orientation choice would
          // change nothing visible, so it is not offered.
          ...(orientation === prefs.orientation
            ? [
                {
                  id: "orientation",
                  icon: byId("split.orientation")?.icon ?? "splitColumn",
                  label: byId("split.orientation")?.label ?? "",
                  run: () => runAction("split.orientation"),
                },
              ]
            : []),
        ];

  const { top: railTop, bottom: railBottom } = railItems({
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
  });

  // A page of the first pane is put away by its own close, back to the
  // documentation where that is shown.
  const closePage = () => {
    setPage("docs");
    setMaximized(null);
  };
  const docsPane = (
    <MainPane
      host={host}
      reader={reader}
      account={account}
      t={t}
      locale={locale}
      signedIn={signedIn}
      layout={layout}
      prefs={prefs}
      maximized={maximized}
      pageOn={pageOn}
      firstPaneShown={firstPaneShown}
      declarationsOn={declarationsOn}
      ledgerOn={ledgerOn}
      browserOn={browserOn}
      browserMounted={browserMounted}
      profileOn={profileOn}
      aeatSyncOn={aeatSyncOn}
      calendarOn={calendarOn}
      openDeclaration={openDeclaration}
      openWorkUnit={openWorkUnit}
      guarded={guarded}
      askCenso={askCenso}
      askSignIn={askSignIn}
      runAction={runAction}
      openView={openView}
      openViewLink={openViewLink}
      ledgerMemory={ledgerMemory}
      setPage={setPage}
      showPage={showPage}
      setMaximized={setMaximized}
      openLink={openLink}
      guardLeave={guardLeave}
      declarationsPage={declarationsPage}
      ledgerPage={ledgerPage}
      browserPage={browserPage}
      profilePage={profilePage}
      aeatSyncPage={aeatSyncPage}
      calendarPage={calendarPage}
      toggleMaximize={toggleMaximize}
      maximizeControl={maximizeControl}
      splitControls={splitControls}
      closePage={closePage}
      routedLedger={routedLedger}
      modelList={modelList}
      changeLedgerView={changeLedgerView}
      changeProfileView={changeProfileView}
      contribute={contribute}
      setLedgerFloor={setLedgerFloor}
      browserHome={browserHome}
      isShellChord={isShellChord}
      setBrowserKeptFor={setBrowserKeptFor}
      toggleProfileMaximized={toggleProfileMaximized}
      byId={byId}
      openMenu={openMenu}
      profileAccountActions={profileAccountActions}
      copy={copy}
      say={say}
      profileHost={profileHost}
      aeatAsked={aeatAsked}
      aeatHandled={aeatHandled}
      censoAsked={censoAsked}
      censoHandled={censoHandled}
      calendar={calendar}
      calendarProfile={calendarProfile}
      calendarMemory={calendarMemory}
      patch={patch}
      environment={environment}
      docsEntry={docsEntry}
      docs={docs}
      languages={languages}
      language={language}
      chords={chords}
      setDocsTheme={setDocsTheme}
      setDocsSearchReady={setDocsSearchReady}
      runShortcut={runShortcut}
      docsMenu={docsMenu}
    />
  );

  return (
    <ShellContexts t={t} navigation={nav.runtime} provisioning={provisioning}>
      <TooltipProvider>
        <div className="desktop-window flex h-dvh min-w-0 flex-col bg-chrome">
          <Titlebar
            host={host}
            onPresentation={fullscreen.observe}
            guardClose={(proceed) =>
              guardNavigation({ kind: "close" }, proceed)
            }
            onFailure={() => say(t("desktop.titlebar.failed"))}
          >
            <AccountMenu
              account={account}
              onSignIn={() => {
                setSettingsOpen(false);
                signInOpener.current = null;
                setCreatingProfile(false);
                setSignInDismissed(false);
              }}
              google={
                signedIn && setupOffered && setupSnapshot ? (
                  <GoogleAccount
                    google={setupSnapshot.google}
                    disabled={setup.pending || account.busy}
                    refusal={setup.refusal}
                    onSignIn={setup.signInGoogle}
                    onSignOut={setup.signOutGoogle}
                  />
                ) : undefined
              }
              onProfile={
                host.userProfile
                  ? () => {
                      setPage("profile");
                      setLayout((current) => ({
                        ...current,
                        maximized: null,
                      }));
                    }
                  : undefined
              }
              onSignOut={signOut}
              onCreate={askNewProfile}
              onManage={
                host.profiles
                  ? () => {
                      setSignInDismissed(true);
                      setManagingProfiles(true);
                    }
                  : undefined
              }
              onAbout={
                about
                  ? () => {
                      setSettingsOpen(false);
                      setAboutOpen(true);
                    }
                  : undefined
              }
            />
          </Titlebar>
          <div
            ref={workspace}
            className="shell grid min-h-0 flex-1 grid-cols-[auto_1fr] grid-rows-[minmax(0,1fr)] bg-chrome"
          >
            <Rail
              label={t("desktop.rail.label")}
              top={railTop}
              bottom={railBottom}
            />
            <ShellDock
              host={host}
              t={t}
              locale={locale}
              account={account}
              phase={phase}
              signedIn={signedIn}
              scheme={scheme}
              terminalTheme={terminalTheme}
              terminalFontSize={terminalFontSize}
              status={status}
              setStatus={setStatus}
              terminals={terminals}
              isShellChord={isShellChord}
              terminalMenu={terminalMenu}
              recordMenu={recordMenu}
              signInButton={signInButton}
              askSignIn={askSignIn}
              agentControl={agentControl}
              agentBody={agentBody}
              openMenu={openMenu}
              onToolRefused={onToolRefused}
              openLink={openLink}
              openViewLink={openViewLink}
              settledSetups={settledSetups}
              byId={byId}
              runAction={runAction}
              maximizeControl={maximizeControl}
              splitControls={splitControls}
              layout={layout}
              prefs={prefs}
              setLayout={setLayout}
              maximized={maximized}
              setMaximized={setMaximized}
              patch={patch}
              docking={docking}
              changeDocking={changeDocking}
              setNarrowedPanes={setNarrowedPanes}
              dockMinimumWidths={dockMinimumWidths}
              dockBesideWidths={dockBesideWidths}
              dockMinimumHeights={dockMinimumHeights}
              dockOffered={dockOffered}
              expandedPane={expandedPane}
              fullscreen={fullscreen}
              enterFullscreen={enterFullscreen}
              revealPane={revealPane}
              grantFocus={grantFocus}
              focusView={focusView}
              focusRail={focusRail}
              toggleMaximize={toggleMaximize}
              closeColumn={closeColumn}
              guarded={guarded}
              showPage={showPage}
              closePage={closePage}
              setBrowserKeptFor={setBrowserKeptFor}
              agentVisible={agentVisible}
              tuiVisible={tuiVisible}
              panelVisible={panelVisible}
              activePanes={activePanes}
              pageOn={pageOn}
              profileOn={profileOn}
              calendarOn={calendarOn}
              ledgerOn={ledgerOn}
              declarationsOn={declarationsOn}
              browserOn={browserOn}
              aeatSyncOn={aeatSyncOn}
              docsEntry={docsEntry}
              setErrorCount={setErrorCount}
              filters={filters}
              defaultFilters={defaultFilters}
              setFilters={setFilters}
              selectLogLevel={selectLogLevel}
              copyLogs={copyLogs}
              exportLogs={exportLogs}
              revealLogs={revealLogs}
              main={docsPane}
            />

            {settingsOpen && (
              <Settings
                prefs={prefs}
                setPrefs={setPrefs}
                language={languageControl}
                close={() => setSettingsOpen(false)}
                about={
                  about
                    ? {
                        state: about,
                        onOpen: () => {
                          setSettingsOpen(false);
                          setAboutOpen(true);
                        },
                      }
                    : undefined
                }
                onReset={() => {
                  setPrefs(DEFAULT_PREFS);
                  setLayout((current) => ({
                    ...DEFAULT_LAYOUT,
                    logLevel: current.logLevel,
                    calendarView: current.calendarView,
                    profileView: current.profileView,
                    ledgerView: current.ledgerView,
                  }));
                  setMaximized(null);
                  say(t("desktop.settings.layout_reset"));
                }}
              />
            )}
            <AboutDialog
              open={aboutOpen && about !== null}
              onOpenChange={setAboutOpen}
              state={about}
              onCopy={copy}
            />
            {paletteOpen && (
              <CommandPalette
                actions={[...paletteExtra, ...actions]}
                pastedLink={pastedLink}
                language={languageControl}
                searchDocs={searchDocs}
                openDoc={openDoc}
                close={() => setPaletteOpen(false)}
                fallbackFocus={focusRail}
              />
            )}
            {menu && (
              <ContextMenu
                // Each menu is its own: it remembers where its own focus came
                // from.
                key={`${menu.at.x}:${menu.at.y}`}
                label={t("desktop.palette.actions")}
                items={menu.items}
                at={menu.at}
                choose={(id) => {
                  const items = menu.items;
                  setMenu(null);
                  items
                    .find(
                      (item): item is MenuAction =>
                        isAction(item) && item.id === id,
                    )
                    ?.run?.();
                }}
              />
            )}
            <Toast>{toast}</Toast>
            <ReconnectingNotice
              reconnecting={account.reconnecting}
              onSignIn={askSignIn}
            />
            {nav.prompt && <NavigationPrompt prompt={nav.prompt} />}
            {setupOffered && (
              <ProvisioningPanel
                locale={locale}
                onCopyDetails={copy}
                signedOut={!signedIn}
                localAi={
                  signedIn && agentSession && host.providerSettings
                    ? {
                        session: agentSession,
                        providerSettings: host.providerSettings,
                        reader,
                      }
                    : null
                }
              />
            )}
            <AccountDialogs
              host={host}
              account={account}
              accountRef={accountRef}
              signInAsked={signInAsked}
              signInDismissed={signInDismissed}
              setSignInDismissed={setSignInDismissed}
              creatingProfile={creatingProfile}
              setCreatingProfile={setCreatingProfile}
              managingProfiles={managingProfiles}
              setManagingProfiles={setManagingProfiles}
              askNewProfile={askNewProfile}
              signInOpener={signInOpener}
              signInButton={signInButton}
              calendarPage={calendarPage}
              docs={docs}
              grantFocus={grantFocus}
              focusView={focusView}
              focusRail={focusRail}
              panelMaximized={panelMaximized}
              tab={layout.tab}
              tuiVisible={tuiVisible}
            />
          </div>
        </div>
        <AttendanceRequests
          attendance={host.attendance}
          profile={signedIn ? (account.status?.active_profile ?? null) : null}
          locale={locale}
        />
      </TooltipProvider>
    </ShellContexts>
  );
}
