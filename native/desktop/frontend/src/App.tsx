import { useDesktopEnvironment } from "./shell/useDesktopEnvironment";
import { useWindowPresentation } from "./shell/useWindowPresentation";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type SetStateAction,
} from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/components/ui/cn";
import {
  Empty,
  EmptyDescription,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { IconButton } from "@/components/ui/icon-button";
import { ResizeHandle } from "@/components/ui/resize-handle";
import { Spinner } from "@/components/ui/spinner";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Toast } from "@/components/ui/toast";
import { CommandPalette, type DocsSearch } from "./components/CommandPalette";
import { ContextMenu, type MenuAnchor } from "./components/ContextMenu";
import { Icon, type IconName } from "@/components/ui/icon";
import {
  DocsFrame,
  type DocsFrameApi,
  type DocsMenuRequest,
} from "./components/DocsFrame";
import type {
  ContextMenuAction,
  ContextMenuItem,
  ContextMenuSeparator,
  DocsTheme,
  HostFailure,
} from "./ipc/contract";
import { PaneHeader, type PaneControl } from "./components/PaneHeader";
import { Rail, type RailItem } from "./components/Rail";
import { AgentColumn } from "./components/AgentColumn";
import { AttendanceRequests } from "./components/AttendanceRequests";
import { HostRecordList } from "./components/HostRecordList";
import type { RecordMenuRequest } from "./components/RecordList";
import {
  DEFAULT_FILTERS,
  levelRank,
  recordLine,
  type RecordFilters,
} from "./shell/records";
import { Settings } from "./components/Settings";
import { accountLabel } from "./components/accountWords";
import { SignedOut, SignInDialog } from "./components/SignIn";
import { AccountMenu } from "./components/AccountMenu";
import { Titlebar } from "./components/Titlebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useFilingCalendar } from "./shell/calendar";
import { useMessages } from "./shell/messages";
import { useSignIn } from "./shell/signIn";
import {
  FilingCalendarView,
  type CalendarMemory,
} from "./components/FilingCalendar";
import { Button } from "@/components/ui/button";
import { Split } from "./components/Split";
import {
  TerminalPane,
  type TerminalApi,
  type TerminalStatus,
} from "./components/TerminalPane";
import {
  bridgeChords,
  chordLabel,
  findAction,
  primaryChord,
  type Action,
  type FocusArea,
} from "./shell/actions";
import type { Host, TerminalKind } from "./shell/host";
import {
  DEFAULT_LAYOUT,
  DEFAULT_PREFS,
  loadState,
  saveState,
  type Layout,
  type Maximized,
  type PanelTab,
  type Prefs,
} from "./shell/layout";
import { useMetric, useTerminalFontSize } from "./shell/metrics";
import { AEAT_SEDE } from "./shell/links";
import { fromPointer } from "./shell/pointer";
import {
  SOURCE_LOCALE,
  StringsContext,
  translator,
  type Translate,
} from "./shell/strings";
import {
  DARK_TERMINAL,
  LIGHT_TERMINAL,
  DARK_TUI,
  LIGHT_TUI,
} from "./shell/terminalThemes";
import { failureCode } from "./errors";

const COUNT_LIMIT = 99;
const TOAST_MS = 2400;
// A dragged splitter changes the layout on every pointer move; it is written
// to storage once the changes have paused.
const SAVE_DELAY_MS = 250;
// How long a wish to focus a view waits for that view to be shown.
const FOCUS_WISH_MS = 1000;
const TABS: readonly (readonly [PanelTab, string, IconName])[] = [
  ["console", "desktop.rail.console", "console"],
  ["python", "desktop.rail.python", "python"],
  ["logs", "desktop.rail.logs", "logs"],
];

type MenuEntry =
  (ContextMenuAction & { run?: () => void }) | ContextMenuSeparator;
type OpenMenu = { items: MenuEntry[]; at: MenuAnchor };

const isSeparator = (item: MenuEntry): item is { separator: true } =>
  "separator" in item;

const isHostFailure = (value: unknown): value is HostFailure =>
  typeof value === "object" &&
  value !== null &&
  typeof (value as Partial<HostFailure>).code === "string" &&
  typeof (value as Partial<HostFailure>).operation === "string";

/** The exit code of a session that has exited, null when it is unknown. */
const exitCode = (status: TerminalStatus): number | null | undefined =>
  status.phase === "exited" ? status.code : undefined;

/** Why a session could not start or carry on, when it has failed. */
const failure = (status: TerminalStatus): string | undefined =>
  status.phase === "failed" ? status.message : undefined;

type Area = Exclude<Maximized, null>;

/** The columns of the workspace, each shown and put away on its own. */
const COLUMNS = ["agent", "tui", "docs"] as const;
type Column = (typeof COLUMNS)[number];

/** The workspace area that holds focus, the documentation frame included. */
const focusedArea = (): Area | "rail" | null => {
  const element = document.activeElement;
  if (!element || element === document.body) return null;
  if (element.closest(".pane-agent")) return "agent";
  if (element.closest(".pane-docs")) return "docs";
  if (element.closest(".pane-tui")) return "tui";
  if (element.closest(".panel")) return "panel";
  if (element.closest(".rail")) return "rail";
  return null;
};

const activeTerminal = (): TerminalKind | null => {
  const owner = document.activeElement?.closest<HTMLElement>("[data-terminal]");
  const kind = owner?.dataset.terminal;
  return kind === "console" || kind === "python" || kind === "tui"
    ? kind
    : null;
};

export function App({ host }: { host: Host }) {
  const account = useSignIn(host);
  const environment = useDesktopEnvironment(host);
  const workspace = useRef<HTMLDivElement>(null);
  const { viewportHeight, viewportWidth, prefersDark } =
    useWindowPresentation(workspace);
  // How many log records are errors, as the log view reports it.
  const [errorCount, setErrorCount] = useState(0);
  const initial = useMemo(loadState, []);
  const [prefs, setPrefs] = useState<Prefs>(initial.prefs);
  const [layout, setLayout] = useState<Layout>(initial.layout);
  const [maximized, setMaximized] = useState<Maximized>(null);
  // What the first pane shows: the documentation, or a view of the profile
  // where the host offers one. The documentation stays loaded underneath.
  const [page, setPage] = useState<"docs" | "calendar">("docs");
  const calendarPage = useRef<HTMLElement>(null);
  // The agent column was asked for: it takes focus once it is laid out.
  const wantsAgent = useRef(false);
  const agentColumn = useRef<HTMLElement>(null);
  const agentBody = useRef<HTMLElement>(null);
  // The calendar was asked for: it takes focus once it is laid out.
  const wantsCalendar = useRef(false);
  // What held focus when the sign-in dialog was asked for, and whether
  // that was in the calendar: the control itself may be gone by the close.
  const signInOpener = useRef<{
    element: Element | null;
    calendar: boolean;
  } | null>(null);
  const [docsTheme, setDocsTheme] = useState<DocsTheme>("auto");
  const [docsSearchReady, setDocsSearchReady] = useState(false);
  const [status, setStatus] = useState<Record<TerminalKind, TerminalStatus>>({
    console: { phase: "starting" },
    python: { phase: "starting" },
    tui: { phase: "starting" },
  });
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [menu, setMenu] = useState<OpenMenu | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  // The sign-in dialog opens by itself whenever the TUI becomes gated; a
  // person who dismisses it, or who has just signed out here, reopens it.
  const [signInDismissed, setSignInDismissed] = useState(false);
  // The dialog as the form that creates a profile, where one was asked for.
  const [creatingProfile, setCreatingProfile] = useState(false);
  const signInButton = useRef<HTMLButtonElement>(null);
  const defaultFilters = useMemo(
    () => ({
      ...DEFAULT_FILTERS,
      minLevel: levelRank(
        environment.state === "ready" ? environment.value.logLevel : "INFO",
      ),
    }),
    [environment],
  );
  const [filterOverride, setFilterOverride] = useState<RecordFilters | null>(
    null,
  );
  const filters = filterOverride ?? defaultFilters;
  const setFilters = useCallback(
    (update: SetStateAction<RecordFilters>) => {
      setFilterOverride((current) =>
        typeof update === "function"
          ? update(current ?? defaultFilters)
          : update,
      );
    },
    [defaultFilters],
  );
  const docs = useRef<DocsFrameApi>(null);
  const terminals = useRef<Partial<Record<TerminalKind, TerminalApi>>>({});
  const toastTimer = useRef(0);
  const nativeMenus = useRef(host.nativeMenus);

  // Layout geometry, read from the canonical tokens (src/styles/tokens.css) instead
  // of duplicated as literals; each metric re-reads on resize.
  const docsMin = useMetric("--docs-min", 200);
  const panelMin = useMetric("--panel-min", 140);
  const splitMinA = useMetric("--split-min-a", 260);
  const splitMinBRow = useMetric("--split-min-b-row", 320);
  const splitMinBCol = useMetric("--split-min-b-col", 160);
  const railWidth = useMetric("--rail-w", 48);
  const agentMin = useMetric("--agent-min", 240);
  const panelResizeStep = useMetric("--resize-step", 24);
  const panelCollapseThreshold = useMetric("--panel-collapse-threshold", 60);
  const terminalFontSize = useTerminalFontSize(prefs.fontSize);

  const patch = useCallback(
    (change: Partial<Layout>) =>
      setLayout((current) => ({ ...current, ...change })),
    [],
  );
  // The documentation asked for by name: its pane is shown first.
  const showDocs = useCallback(() => {
    setPage("docs");
    setMaximized((area) => (area === "docs" ? area : null));
    patch({ docsShown: true });
  }, [patch]);

  const unsaved = useRef({ prefs, layout });
  useEffect(() => {
    unsaved.current = { prefs, layout };
    const timer = window.setTimeout(
      () => saveState(prefs, layout),
      SAVE_DELAY_MS,
    );
    return () => window.clearTimeout(timer);
  }, [prefs, layout]);
  useEffect(() => {
    // Leaving before the pause has passed still keeps the last change.
    const flush = () =>
      saveState(unsaved.current.prefs, unsaved.current.layout);
    window.addEventListener("pagehide", flush);
    return () => window.removeEventListener("pagehide", flush);
  }, []);

  const gated = account.gated;
  const phase = account.phase;
  const signedIn = phase === "signed-in";
  // Signed out, the agent is not there to fill the window.
  if (!signedIn && maximized === "agent") setMaximized(null);
  const accountRef = useRef(account);
  accountRef.current = account;
  const signOut = useCallback(() => {
    // Signing out here is not a reason to ask for the password again.
    setSignInDismissed(true);
    void accountRef.current.signOut();
  }, []);
  // The palette shortcut enters the same account flow as the header.
  const switchProfile = useCallback(() => {
    setSettingsOpen(false);
    signInOpener.current = null;
    setSignInDismissed(false);
    void accountRef.current.signOut();
  }, []);
  useEffect(() => {
    if (gated) return;
    // Admitted: the next time the gate closes, the dialog opens again, and
    // as the sign-in, whatever it was last asked to be.
    setSignInDismissed(false);
    setCreatingProfile(false);
  }, [gated]);
  const signOutFailed = account.signOutFailure !== null;
  useEffect(() => {
    // A sign-out that failed leaves the person signed in: the next time the
    // gate closes it is not by their choice, so the dialog opens.
    if (signOutFailed) setSignInDismissed(false);
  }, [signOutFailed]);
  const mayEnterPassword = account.canSignIn;

  const views = host.views;
  // What is on screen: a maximized area alone, otherwise every area that is
  // shown. The first pane holds the documentation or a view of the profile,
  // and is on screen while either is asked for.
  const unhidden = (area: Area) => maximized === null || maximized === area;
  const calendarOn = views !== undefined && page === "calendar";
  const firstPaneShown =
    (layout.docsShown || calendarOn || maximized === "docs") &&
    unhidden("docs");
  const docsVisible = firstPaneShown && !calendarOn;
  const calendarVisible = calendarOn && firstPaneShown;
  const tuiVisible =
    (layout.tuiShown || maximized === "tui") && unhidden("tui");
  const panelVisible = layout.panelOpen && unhidden("panel");
  // The room beside the rail. A window too narrow for the agent column's
  // floor beside the main area's shows the agent only on its own: alone in
  // the window, or maximized.
  const besideRail = Math.max(0, viewportWidth - railWidth);
  const agentFits = besideRail >= agentMin + splitMinA;
  const mainOccupied = firstPaneShown || tuiVisible || panelVisible;
  // The agent works only for a profile signed in here: signed out, it is
  // not there at all, and it comes back as it was laid out on signing in.
  const agentVisible =
    signedIn &&
    (layout.agentShown || maximized === "agent") &&
    unhidden("agent") &&
    (maximized === "agent" || agentFits || !mainOccupied);
  // Whose views are read: the signed-in profile's. Where the platform signs
  // in inside the TUI the shell cannot tell, so it asks and shows the answer.
  const reader =
    signedIn || phase === "unsupported"
      ? (account.status?.active_profile ?? "")
      : null;
  const recheckAccount = useCallback(() => accountRef.current.recheck(), []);
  // What the reader has made of the calendar, kept while its page is away:
  // the page is taken down when it is put away, and comes back as it was.
  // A calendar belongs to its profile, and so does what was made of it: a
  // new memory for each profile, and for each time one is signed in.
  const [calendarKept, setCalendarKept] = useState(() => ({
    reader,
    memory: { current: {} as CalendarMemory },
  }));
  if (calendarKept.reader !== reader)
    setCalendarKept({ reader, memory: { current: {} } });
  const calendarMemory = calendarKept.memory;
  const calendar = useFilingCalendar(
    views,
    reader,
    calendarVisible,
    recheckAccount,
  );
  const observedMessages = useMessages(views, reader, recheckAccount);
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

  // The window's language: the person's own choice where the documentation
  // is bundled in it, otherwise the language Cadrumo reports.
  const languages = useMemo(
    () =>
      environment.state === "ready" &&
      environment.value.docs.state === "bundled"
        ? environment.value.docs.languages.map((language) => language.code)
        : [],
    [environment],
  );
  const locale = languages.includes(prefs.language)
    ? prefs.language
    : environment.state === "ready"
      ? environment.value.outputLanguage
      : SOURCE_LOCALE;
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

  const docsEntry = useMemo(() => {
    if (environment.state !== "ready") return null;
    const docs = environment.value.docs;
    if (docs.state !== "bundled") return null;
    const { languages: bundled } = docs;
    return (
      bundled.find((language) => language.code === locale) ?? bundled[0] ?? null
    );
  }, [environment, locale]);

  const say = useCallback((text: string) => {
    setToast(text);
    window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(null), TOAST_MS);
  }, []);

  const previousManager = useRef(account.manager?.state);
  useEffect(() => {
    const state = account.manager?.state;
    const previous = previousManager.current;
    previousManager.current = state;
    if (!state || state === previous) return;
    if (state === "recovering" || state === "waiting")
      say(t("desktop.signin.recovering_services"));
    else if (state === "failed" || state === "stopped")
      say(
        `${t("desktop.account.services_down")}: ${failureCode(account.manager?.failure)}`,
      );
    else if (
      state === "ready" &&
      (previous === "recovering" || previous === "waiting")
    )
      say(t("desktop.signin.services_recovered"));
  }, [account.manager, say, t]);

  // An address opened in the system browser. A refusal is said aloud: the
  // person must not wait for a page that is not coming.
  const openLink = useCallback(
    (url: string) => {
      host.openExternal(url).catch(() => say(t("desktop.toast.open_failed")));
    },
    [host, say, t],
  );

  const copy = useCallback(
    (text: string) => {
      if (!text) return;
      // A refused write, including one over the host's size cap, is said
      // aloud: the person must not believe a copy happened when it did not.
      host.writeClipboard(text).then(
        () => say(t("desktop.toast.copied")),
        () => say(t("desktop.toast.copy_failed")),
      );
    },
    [host, say, t],
  );

  // Focus asked for a view that may not be on screen yet: showing it is a
  // state change, and that commits later than the request does. The wish is
  // kept and granted after the commit that shows the view, or dropped when
  // none does in time. Granted, it is kept for the rest of its life: a view
  // that is rebuilt as it starts takes its focus with it, and the commit
  // that follows gives it back, unless focus has gone somewhere by then.
  const wanted = useRef<{
    view: TerminalKind | "logs";
    since: number;
    granted?: boolean;
    waitingForTerminal?: boolean;
  } | null>(null);
  const grantFocus = useCallback(() => {
    const wish = wanted.current;
    if (!wish) return;
    if (
      !wish.waitingForTerminal &&
      performance.now() > wish.since + FOCUS_WISH_MS
    ) {
      wanted.current = null;
      return;
    }
    if (wish.granted && document.activeElement !== document.body) return;
    // The sign-in dialog holds the keyboard while it is up: nothing behind
    // it is given focus, whatever was wished for before it opened. On its
    // way out it holds nothing, and a wish made then is granted at once.
    if (document.querySelector('.sign-in[data-state="open"]')) return;
    // Withheld, the TUI's pane holds the way in instead of a terminal.
    const wayIn = signInButton.current;
    if (wish.view === "tui" && wayIn && wayIn.offsetParent !== null) {
      wayIn.focus();
      wish.granted = true;
      return;
    }
    const target = document.querySelector<HTMLElement>(
      wish.view === "logs"
        ? ".logview .filter-text"
        : `[data-terminal="${wish.view}"]`,
    );
    // Laid out means shown: a hidden pane's content has no offset parent.
    if (!target || target.offsetParent === null) return;
    if (wish.view === "logs") target.focus();
    else if (terminals.current[wish.view])
      terminals.current[wish.view]?.focus();
    else {
      // First opening can wait for bundled fonts. Later user input still
      // cancels this wish; elapsed loading time alone must not lose it.
      wish.waitingForTerminal = true;
      return;
    }
    wish.waitingForTerminal = false;
    wish.granted = true;
  }, []);
  useEffect(grantFocus);
  useEffect(() => {
    // Whatever the person presses next decides where focus is: a wish from
    // before that press is dropped, never granted over it. The press that
    // made the wish is older than the wish and leaves it alone.
    const drop = (event: Event) => {
      if (wanted.current && wanted.current.since < event.timeStamp)
        wanted.current = null;
    };
    window.addEventListener("pointerdown", drop, true);
    window.addEventListener("keydown", drop, true);
    return () => {
      window.removeEventListener("pointerdown", drop, true);
      window.removeEventListener("keydown", drop, true);
    };
  }, []);
  const focusView = useCallback(
    (view: TerminalKind | "logs") => {
      wanted.current = { view, since: performance.now() };
      grantFocus();
    },
    [grantFocus],
  );
  const focusRail = useCallback(
    () => document.querySelector<HTMLElement>(".rail [role=toolbar]")?.focus(),
    [],
  );
  // The TUI is where the profile is worked on: shown, with the keyboard.
  const showTui = useCallback(() => {
    setMaximized((area) => (area === "tui" ? area : null));
    patch({ tuiShown: true });
    focusView("tui");
  }, [patch, focusView]);
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

  const openTab = useCallback(
    (tab: PanelTab, { toggle = true }: { toggle?: boolean } = {}) => {
      if (toggle && layout.panelOpen && layout.tab === tab) {
        patch({ panelOpen: false });
        if (maximized === "panel") setMaximized(null);
        return;
      }
      if (maximized && maximized !== "panel") setMaximized(null);
      patch({ panelOpen: true, tab });
      focusView(tab);
    },
    [layout.panelOpen, layout.tab, maximized, patch, focusView],
  );

  const toggleMaximize = useCallback(
    (area: Exclude<Maximized, null>) => {
      if (maximized === area) {
        setMaximized(null);
        return;
      }
      if (area === "agent" && !layout.agentShown) patch({ agentShown: true });
      if (area === "tui" && !layout.tuiShown) patch({ tuiShown: true });
      if (area === "docs" && !layout.docsShown && !calendarOn)
        patch({ docsShown: true });
      if (area === "panel" && !layout.panelOpen) patch({ panelOpen: true });
      setMaximized(area);
      if (area === "tui") focusView("tui");
    },
    [
      maximized,
      layout.agentShown,
      layout.tuiShown,
      layout.docsShown,
      layout.panelOpen,
      calendarOn,
      patch,
      focusView,
    ],
  );

  // A column's own close: put away, and the layout restored if it was the
  // one maximized.
  const closeColumn = useCallback(
    (column: Column) => {
      setMaximized((area) => (area === column ? null : area));
      if (column === "docs") {
        // The first pane shows the calendar where it was asked for; closed,
        // the calendar goes with the pane.
        setPage("docs");
        patch({ docsShown: false });
      } else
        patch(column === "agent" ? { agentShown: false } : { tuiShown: false });
    },
    [patch],
  );
  // A column asked for from the rail, the palette or a shortcut: put away
  // when it is on screen, else shown with the layout restored around it.
  const toggleColumn = useCallback(
    (column: Column) => {
      const onScreen =
        column === "agent"
          ? agentVisible
          : column === "tui"
            ? tuiVisible
            : docsVisible;
      if (onScreen && maximized === null) return closeColumn(column);
      if (column === "agent" && !agentFits) {
        // Too narrow to sit beside anything: the agent takes the window.
        if (onScreen) return closeColumn(column);
        patch({ agentShown: true });
        setMaximized(mainOccupied ? "agent" : null);
        wantsAgent.current = true;
        return;
      }
      setMaximized(null);
      if (column === "docs") showDocs();
      else if (column === "agent") {
        patch({ agentShown: true });
        wantsAgent.current = true;
      } else {
        patch({ tuiShown: true });
        focusView("tui");
      }
    },
    [
      agentVisible,
      agentFits,
      mainOccupied,
      tuiVisible,
      docsVisible,
      maximized,
      closeColumn,
      showDocs,
      patch,
      focusView,
    ],
  );

  // The keyboard's way between the areas of the window, in the order they
  // are laid out. A focused terminal keeps Tab for itself, so this is how
  // focus leaves one.
  const cycleFocus = useCallback(
    (step: 1 | -1) => {
      type Stop = [Area | "rail", boolean, () => void];
      const docsStop: Stop = [
        "docs",
        firstPaneShown && (calendarPage.current !== null || !!docs.current),
        () => (calendarPage.current ?? docs.current)?.focus(),
      ];
      const tuiStop: Stop = [
        "tui",
        // Only where the pane holds something to focus: the way in while
        // signed out, or a session.
        tuiVisible &&
          (signInButton.current !== null ||
            (!gated && status.tui.phase !== "unavailable")),
        () => focusView("tui"),
      ];
      const stops: Stop[] = [
        ["agent", agentVisible, () => agentBody.current?.focus()],
        ...(prefs.order === "tui" ? [tuiStop, docsStop] : [docsStop, tuiStop]),
        [
          "panel",
          panelVisible,
          () => {
            if (layout.tab === "logs")
              document
                .querySelector<HTMLElement>(".logview .filter-text")
                ?.focus();
            // Without a session there is no terminal to focus; its tab is.
            else if (status[layout.tab].phase === "unavailable")
              document.getElementById(`tab-${layout.tab}`)?.focus();
            else focusView(layout.tab);
          },
        ],
        ["rail", true, focusRail],
      ];
      const shown = stops.filter(([, on]) => on);
      const at = shown.findIndex(([area]) => area === focusedArea());
      const to =
        at === -1
          ? step === 1
            ? 0
            : shown.length - 1
          : (at + step + shown.length) % shown.length;
      shown[to]?.[2]();
    },
    [
      agentVisible,
      firstPaneShown,
      tuiVisible,
      panelVisible,
      prefs.order,
      layout.tab,
      gated,
      status,
      focusView,
      focusRail,
    ],
  );

  const paste = useCallback(
    (kind: TerminalKind | null) => {
      if (!kind) return;
      host.readClipboard().then(
        (text) => terminals.current[kind]?.paste(text),
        // The host refuses rather than truncates an oversized clipboard, so
        // say why nothing arrived.
        (error: unknown) =>
          say(
            t(
              failureCode(error) === "output_limit"
                ? "desktop.toast.paste_too_large"
                : "desktop.toast.paste_failed",
            ),
          ),
      );
    },
    [host, say, t],
  );

  const goHome = useCallback(() => {
    showDocs();
    if (docs.current?.home()) return;
    // A documentation page without the home command still reloads its entry.
    const frame = document.querySelector<HTMLIFrameElement>(".docs-frame");
    if (frame && docsEntry) frame.src = docsEntry.entry;
  }, [docsEntry, showDocs]);

  const openDoc = useCallback(
    (url: string) => {
      showDocs();
      if (docs.current?.navigate(url)) return;
      const frame = document.querySelector<HTMLIFrameElement>(".docs-frame");
      if (
        !frame ||
        environment.state !== "ready" ||
        environment.value.docs.state !== "bundled"
      )
        return;
      // Only a documentation-origin address ever becomes the frame's source.
      let origin: string;
      try {
        origin = new URL(url).origin;
      } catch {
        return;
      }
      if (origin === environment.value.docs.origin) frame.src = url;
    },
    [environment, showDocs],
  );

  // The single action registry.
  const actions = useMemo<Action[]>(
    () => [
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
        run: () => setPaletteOpen((open) => !open),
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
        enabled: () => !calendarOn,
        run: () => docs.current?.back(),
      },
      {
        id: "docs.forward",
        label: t("desktop.action.docs_forward"),
        group: "docs",
        icon: "forward",
        chords: [{ alt: true, code: "ArrowRight", key: "→", scope: "docs" }],
        enabled: () => !calendarOn,
        run: () => docs.current?.forward(),
      },
      {
        id: "docs.zoomIn",
        label: t("desktop.action.zoom_in"),
        group: "docs",
        icon: "zoomIn",
        chords: [{ mod: true, code: "Equal", key: "=", scope: "docs" }],
        enabled: () => !calendarOn,
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
        enabled: () => !calendarOn,
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
        enabled: () => !calendarOn,
        run: () => patch({ zoom: 1 }),
      },
      {
        id: "agent.toggle",
        label:
          agentVisible && !maximized
            ? t("desktop.agent.hide")
            : t("desktop.agent.show"),
        group: "layout",
        icon: "agent",
        chords: [
          { mod: true, shift: true, code: "KeyA", key: "A", scope: "global" },
        ],
        enabled: () => signedIn,
        run: () => toggleColumn("agent"),
      },
      {
        id: "tui.toggle",
        label:
          tuiVisible && !maximized
            ? t("desktop.tui.hide")
            : t("desktop.tui.show"),
        group: "layout",
        icon: "tui",
        chords: [
          { mod: true, shift: true, code: "KeyT", key: "T", scope: "global" },
        ],
        run: () => toggleColumn("tui"),
      },
      {
        id: "docs.toggle",
        label:
          docsVisible && !maximized
            ? t("desktop.docs.hide")
            : t("desktop.docs.show"),
        group: "layout",
        icon: "book",
        keywords: "documentation help manual",
        chords: [
          { mod: true, shift: true, code: "KeyH", key: "H", scope: "global" },
        ],
        run: () => toggleColumn("docs"),
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
              : (COLUMNS.find((column) =>
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
        run: () =>
          setPrefs((p) => ({
            ...p,
            orientation: p.orientation === "row" ? "column" : "row",
          })),
      },
      {
        id: "split.swap",
        label: t("desktop.split.swap"),
        group: "layout",
        icon: "swap",
        run: () =>
          setPrefs((p) => ({
            ...p,
            order: p.order === "docs" ? "tui" : "docs",
          })),
      },
      {
        id: "panel.toggle",
        label: layout.panelOpen
          ? t("desktop.panel.hide")
          : t("desktop.panel.show"),
        group: "layout",
        icon: layout.panelOpen ? "chevronDown" : "chevronUp",
        chords: [{ ctrl: true, code: "Backquote", key: "`", scope: "global" }],
        run: () => {
          if (!layout.panelOpen) openTab(layout.tab, { toggle: false });
          else {
            patch({ panelOpen: false });
            if (maximized === "panel") setMaximized(null);
          }
        },
      },
      {
        id: "panel.console",
        label: t("desktop.rail.console"),
        group: "panel",
        icon: "console",
        keywords: "shell powershell terminal",
        chords: [
          { mod: true, shift: true, code: "Digit1", key: "1", scope: "global" },
        ],
        run: () => openTab("console"),
        choose: () => openTab("console", { toggle: false }),
      },
      {
        id: "panel.python",
        label: t("desktop.rail.python"),
        group: "panel",
        icon: "python",
        keywords: "repl interpreter",
        chords: [
          { mod: true, shift: true, code: "Digit2", key: "2", scope: "global" },
        ],
        run: () => openTab("python"),
        choose: () => openTab("python", { toggle: false }),
      },
      {
        id: "panel.logs",
        label: t("desktop.rail.logs"),
        group: "panel",
        icon: "logs",
        chords: [
          { mod: true, shift: true, code: "Digit3", key: "3", scope: "global" },
          { mod: true, shift: true, code: "KeyL", key: "L", scope: "global" },
        ],
        run: () => openTab("logs"),
        choose: () => openTab("logs", { toggle: false }),
      },
      {
        id: "logs.errors",
        label: t("desktop.action.logs_errors"),
        group: "logs",
        icon: "logs",
        run: () => {
          setFilters((f) => ({ ...f, minLevel: 3 }));
          openTab("logs", { toggle: false });
        },
      },
      {
        id: "logs.reset",
        label: t("desktop.action.logs_reset"),
        group: "logs",
        icon: "logs",
        run: () => setFilterOverride(null),
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
        id: "view.calendar",
        label: t("desktop.calendar.title"),
        group: "views",
        icon: "calendar",
        keywords: "obligations deadlines modelo plazos",
        chords: [
          { mod: true, shift: true, code: "KeyD", key: "D", scope: "global" },
        ],
        // Only where the host offers the view: nothing leads to a page that
        // could not load.
        enabled: () => views !== undefined,
        run: () => {
          if (calendarVisible) {
            setPage("docs");
            return;
          }
          wantsCalendar.current = true;
          setMaximized((area) => (area === "docs" ? area : null));
          setPage("calendar");
        },
        choose: () => {
          if (calendarVisible) {
            calendarPage.current?.focus();
            return;
          }
          wantsCalendar.current = true;
          setMaximized((area) => (area === "docs" ? area : null));
          setPage("calendar");
        },
      },
      {
        id: "view.messages",
        label: t("desktop.rail.messages"),
        group: "views",
        icon: "mail",
        keywords: "notifications notificaciones dehu inbox unread",
        enabled: () => views !== undefined,
        // The notifications are read in the TUI; the window shows the count.
        // Why there is no count is said where a tap reaches too, not only
        // in a tooltip.
        run: () => {
          if (messages.kind === "failed")
            say(
              `${t("desktop.rail.messages")}: ${t("desktop.messages.failed", { code: messages.code })}`,
            );
          else if (
            messages.kind === "ready" &&
            messages.summary.captured_at === null
          )
            say(
              `${t("desktop.rail.messages")}: ${t("desktop.messages.never")}`,
            );
          showTui();
        },
      },
      {
        id: "link.aeat",
        label: t("desktop.rail.aeat"),
        group: "links",
        icon: "office",
        keywords: "sede agencia tributaria hacienda tax agency",
        run: () => openLink(AEAT_SEDE),
      },
      {
        id: "account.signIn",
        label: t("desktop.signin.submit"),
        group: "account",
        icon: "lock",
        keywords: "login password",
        enabled: () => mayEnterPassword,
        run: askSignIn,
      },
      {
        id: "account.createProfile",
        label: t("desktop.account.new_profile"),
        group: "account",
        icon: "userAdd",
        keywords: "register new account add another",
        enabled: () => canCreateProfile && offersProfiles,
        run: askNewProfile,
      },
      {
        id: "account.signOut",
        label: t("desktop.account.sign_out"),
        group: "account",
        icon: "signOut",
        keywords: "logout",
        enabled: () => signedIn,
        run: signOut,
      },
      {
        id: "account.switchProfile",
        label: t("desktop.account.switch_profile"),
        group: "account",
        icon: "swap",
        keywords: "change another user account choose",
        enabled: () => signedIn && canCreateProfile,
        run: switchProfile,
      },
      {
        id: "focus.next",
        label: t("desktop.action.focus_next"),
        group: "general",
        icon: "arrow",
        keywords: "pane area switch",
        chords: [{ code: "F6", key: "F6", scope: "global" }],
        run: () => cycleFocus(1),
      },
      {
        id: "focus.previous",
        label: t("desktop.action.focus_previous"),
        group: "general",
        icon: "back",
        keywords: "pane area switch",
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
      agentVisible,
      tuiVisible,
      docsVisible,
      firstPaneShown,
      toggleColumn,
      layout.panelOpen,
      layout.tab,
      layout.zoom,
      prefs.orientation,
      maximized,
      docsSearchReady,
      docsEntry,
      views,
      messages,
      say,
      showTui,
      calendarOn,
      calendarVisible,
      askSignIn,
      askNewProfile,
      canCreateProfile,
      offersProfiles,
      mayEnterPassword,
      signedIn,
      signOut,
      switchProfile,
      cycleFocus,
      openLink,
      goHome,
      patch,
      toggleMaximize,
      openTab,
      copy,
      paste,
      setFilters,
    ],
  );
  const actionsRef = useRef(actions);
  actionsRef.current = actions;
  const byId = (id: string) => actions.find((action) => action.id === id);
  const runAction = useCallback(
    (id: string) =>
      actionsRef.current.find((action) => action.id === id)?.run(),
    [],
  );
  const isShellChord = useCallback(
    (event: KeyboardEvent) =>
      findAction(actionsRef.current, event, "terminal") !== null,
    [],
  );

  // The bridge keymap changes only when chords do, not on every label change.
  const chordsKey = useMemo(
    () => JSON.stringify(bridgeChords(actions)),
    [actions],
  );
  const chords = useMemo(
    () => JSON.parse(chordsKey) as ReturnType<typeof bridgeChords>,
    [chordsKey],
  );

  // What holds the keyboard above the shell. A modal surface owns it: no
  // chord reaches the shell from under one, except the palette's own, which
  // closes the palette. The sign-in dialog is only on screen once the status
  // read has answered. Chords pressed in the documentation arrive by its
  // bridge and pass the same guard.
  const modal = useRef({ palette: false, other: false });
  modal.current = {
    palette: paletteOpen,
    other:
      menu !== null || (gated && !signInDismissed && account.status !== null),
  };
  const chordAllowed = useCallback(
    (id: string) =>
      !modal.current.other && (!modal.current.palette || id === "palette.open"),
    [],
  );
  const runShortcut = useCallback(
    (id: string) => {
      // A chord from the documentation asks for an action by name: one that
      // is not offered is not run, as a key pressed in the window is not.
      const action = actionsRef.current.find((known) => known.id === id);
      if (action && chordAllowed(id) && action.enabled?.() !== false)
        action.run();
    },
    [chordAllowed],
  );

  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      const focus: FocusArea = (event.target as HTMLElement | null)?.closest?.(
        ".xterm",
      )
        ? "terminal"
        : "chrome";
      const action = findAction(actionsRef.current, event, focus);
      if (!action) return;
      if (!chordAllowed(action.id)) return;
      event.preventDefault();
      event.stopPropagation();
      action.run();
    };
    window.addEventListener("keydown", key, true);
    return () => window.removeEventListener("keydown", key, true);
  }, [chordAllowed]);

  // Menus: drawn by the operating system when the host can, otherwise here.
  const openMenu = useCallback(
    (items: MenuEntry[], at: MenuAnchor, pointer: boolean) => {
      const run = (id: string | null) => {
        const chosen = items.find(
          (item) => !isSeparator(item) && item.id === id,
        );
        if (chosen && !isSeparator(chosen)) chosen.run?.();
      };
      if (nativeMenus.current) {
        const plain: ContextMenuItem[] = items.map((item) =>
          isSeparator(item)
            ? item
            : {
                id: item.id,
                label: item.label,
                shortcut: item.shortcut,
                enabled: item.enabled,
              },
        );
        // The host places a menu at a point: under the anchor, where it
        // has a height.
        const point = { x: at.x, y: at.y + (at.height ?? 0) };
        host.showMenu(plain, pointer ? undefined : point).then(run, (error) => {
          // Where the host cannot draw a blocking native menu, the shell
          // draws this one and every later menu itself.
          if (isHostFailure(error) && error.code === "unsupported_platform") {
            nativeMenus.current = false;
            setMenu({ items, at });
          }
        });
      } else {
        setMenu({ items, at });
      }
    },
    [host],
  );

  const docsMenu = useCallback(
    (request: DocsMenuRequest) => {
      openMenu(
        [
          {
            id: "copy",
            label: t("desktop.menu.copy"),
            shortcut: chordLabel({
              mod: true,
              code: "KeyC",
              key: "C",
              scope: "docs",
            }),
            enabled: !!request.selection,
            run: () => copy(request.selection),
          },
          {
            id: "link",
            label: t("desktop.menu.copy_link"),
            enabled: !!request.link,
            run: () => copy(request.link?.href ?? ""),
          },
          { separator: true },
          {
            id: "back",
            label: t("desktop.action.docs_back"),
            shortcut: primaryChord(
              actionsRef.current.find((a) => a.id === "docs.back"),
            ),
            enabled: true,
            run: () => runAction("docs.back"),
          },
          {
            id: "forward",
            label: t("desktop.action.docs_forward"),
            shortcut: primaryChord(
              actionsRef.current.find((a) => a.id === "docs.forward"),
            ),
            enabled: true,
            run: () => runAction("docs.forward"),
          },
          {
            id: "home",
            label: t("desktop.rail.docs_home"),
            shortcut: primaryChord(
              actionsRef.current.find((a) => a.id === "docs.home"),
            ),
            enabled: true,
            run: () => runAction("docs.home"),
          },
        ],
        { x: request.x, y: request.y },
        request.pointer,
      );
    },
    [openMenu, t, copy, runAction],
  );

  const terminalMenu = useCallback(
    (event: MouseEvent, kind: TerminalKind) => {
      const api = terminals.current[kind];
      if (!api) return;
      const items: MenuEntry[] = [
        {
          id: "copy",
          label: t("desktop.menu.copy"),
          shortcut: primaryChord(
            actionsRef.current.find((a) => a.id === "terminal.copy"),
          ),
          enabled: api.hasSelection(),
          run: () => copy(api.selection()),
        },
        {
          id: "paste",
          label: t("desktop.menu.paste"),
          shortcut: primaryChord(
            actionsRef.current.find((a) => a.id === "terminal.paste"),
          ),
          enabled: true,
          run: () => paste(kind),
        },
        {
          id: "select-all",
          label: t("desktop.menu.select_all"),
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
            enabled: true,
            run: () => api.clear(),
          },
        );
      openMenu(
        items,
        { x: event.clientX, y: event.clientY },
        fromPointer(event),
      );
    },
    [openMenu, t, copy, paste],
  );

  const recordMenu = useCallback(
    ({ at, pointer, record, visible }: RecordMenuRequest) => {
      openMenu(
        [
          {
            id: "line",
            label: t("desktop.menu.copy_line"),
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
            enabled: true,
            run: () => copy(visible.map(recordLine).join("\n")),
          },
          { separator: true },
          {
            id: "logger",
            label: t("desktop.menu.only_logger"),
            enabled: !!record.logger,
            run: () => setFilters((f) => ({ ...f, logger: record.logger })),
          },
          {
            id: "level",
            label: t("desktop.menu.only_level", {
              level: (record.level ?? "INFO").toLowerCase(),
            }),
            enabled: !!record.level,
            run: () =>
              setFilters((f) => ({
                ...f,
                minLevel: Math.max(0, levelRank(record.level)),
              })),
          },
        ],
        at,
        pointer,
      );
    },
    [openMenu, t, copy, setFilters],
  );

  const searchDocs: DocsSearch = useMemo(
    () =>
      docsSearchReady
        ? (query: string) =>
            docs.current?.search(query) ??
            Promise.reject(new Error("docs-unmounted"))
        : null,
    [docsSearchReady],
  );

  const clampPanel = (height: number) =>
    // A window too short for both floors, as a small one at a large text
    // size is, shares its height between them in proportion: neither the
    // documentation nor the panel is pushed out of the window.
    viewportHeight < docsMin + panelMin
      ? Math.round((viewportHeight * panelMin) / (docsMin + panelMin))
      : Math.max(panelMin, Math.min(viewportHeight - docsMin, height));
  const panelHeight = clampPanel(
    Math.round(layout.panelRatio * viewportHeight),
  );
  const setPanelHeight = (height: number) =>
    patch({ panelOpen: true, panelRatio: clampPanel(height) / viewportHeight });

  const tabOpen = (tab: PanelTab) => panelVisible && layout.tab === tab;
  // A column hidden from under the keyboard: focus goes to the TUI while
  // that is shown, else to the first pane, else to the agent, else to the
  // rail, never to nothing. The bottom panel maximized over them hands
  // focus on by itself.
  const columnsWere = useRef<Record<Column, boolean>>({
    agent: agentVisible,
    tui: tuiVisible,
    docs: firstPaneShown,
  });
  useEffect(() => {
    const now = { agent: agentVisible, tui: tuiVisible, docs: firstPaneShown };
    const gone = COLUMNS.filter(
      (column) => columnsWere.current[column] && !now[column],
    );
    columnsWere.current = now;
    // Only when one has just been hidden: a window that starts without a
    // column moves no focus. What held focus inside it is still named as
    // the focused element for a moment after it stops being shown.
    const held = document.activeElement;
    if (
      gone.length === 0 ||
      maximized === "panel" ||
      (held !== null &&
        held !== document.body &&
        !gone.some((column) => held.closest(`.pane-${column}`) !== null))
    )
      return;
    // Only where the TUI's pane holds something to focus: the way in while
    // signed out, or a session.
    const tuiFocusable =
      signInButton.current !== null ||
      (!gated && status.tui.phase !== "unavailable");
    if (tuiVisible && tuiFocusable) focusView("tui");
    else if (firstPaneShown && (calendarPage.current ?? docs.current))
      (calendarPage.current ?? docs.current)?.focus();
    else if (agentVisible) agentBody.current?.focus();
    else focusRail();
  }, [
    agentVisible,
    tuiVisible,
    firstPaneShown,
    maximized,
    gated,
    status.tui.phase,
    focusView,
    focusRail,
  ]);
  useEffect(() => {
    if (agentVisible && wantsAgent.current) {
      wantsAgent.current = false;
      agentBody.current?.focus();
    }
  }, [agentVisible]);
  // The bottom panel maximized over the panes above it: focus held in one
  // of them goes into the panel, to the view its tab shows.
  const panelMaximized = maximized === "panel";
  const panelWasMaximized = useRef(panelMaximized);
  useEffect(() => {
    const covered = !panelWasMaximized.current && panelMaximized;
    panelWasMaximized.current = panelMaximized;
    const held = document.activeElement;
    if (
      !covered ||
      (held !== null &&
        held !== document.body &&
        held.closest(".main-area, .pane-agent") === null)
    )
      return;
    focusView(layout.tab);
  }, [panelMaximized, layout.tab, focusView]);

  // What a session's header says beside its state: how it ended, or why it
  // could not start.
  const sessionNote = (kind: TerminalKind) => {
    const reason = failure(status[kind]);
    if (reason !== undefined) return t("desktop.session.failed", { reason });
    const code = exitCode(status[kind]);
    if (code === undefined) return undefined;
    return `${t("desktop.session.exited", { code: code ?? "?" })} · ${t("desktop.session.enter_restarts")}`;
  };
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
  // The agent column's width, as a share of the room beside the rail. A
  // window too narrow for its floor and the split's shares the room between
  // them in proportion, as the bottom panel shares the height.
  const clampAgent = (width: number) =>
    besideRail < agentMin + splitMinA
      ? Math.round((besideRail * agentMin) / (agentMin + splitMinA))
      : Math.max(agentMin, Math.min(besideRail - splitMinA, width));
  const agentWidth = clampAgent(Math.round(layout.agentRatio * besideRail));
  const setAgentWidth = (width: number) =>
    besideRail > 0 &&
    patch({ agentShown: true, agentRatio: clampAgent(width) / besideRail });

  // Side by side needs room for both panes' minimums; a narrower window
  // stacks them without changing the remembered preference.
  const orientation =
    prefs.orientation === "row" &&
    besideRail - (agentVisible && !maximized ? agentWidth : 0) <
      splitMinA + splitMinBRow
      ? "column"
      : prefs.orientation;

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
      icon: "tui",
      label: t("desktop.rail.tui"),
      shortcut: primaryChord(byId("tui.toggle")),
      pressed: tuiVisible,
      onClick: () => runAction("tui.toggle"),
    },
    {
      id: "docs",
      icon: "book",
      label: t("desktop.rail.docs"),
      shortcut: primaryChord(byId("docs.toggle")),
      pressed: docsVisible,
      onClick: () => runAction("docs.toggle"),
    },
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
                    hint: t("desktop.messages.failed", { code: messages.code }),
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
    {
      id: "aeat",
      icon: "office",
      label: t("desktop.rail.aeat"),
      divided: !views,
      onClick: () => runAction("link.aeat"),
    },
    {
      id: "panel",
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
      onClick: () => setSettingsOpen((open) => !open),
    },
  ];

  const terminalPane = (
    kind: TerminalKind,
    shown: boolean,
    theme = terminalTheme,
  ) => (
    <TerminalPane
      host={host}
      kind={kind}
      shown={shown}
      theme={theme}
      fontSize={terminalFontSize}
      label={
        kind === "tui"
          ? t("desktop.tui.label")
          : t(
              kind === "console"
                ? "desktop.rail.console"
                : "desktop.rail.python",
            )
      }
      isShellChord={isShellChord}
      onStatus={(k, s) => {
        setStatus((all) => ({ ...all, [k]: s }));
        if (k !== "tui") return;
        // The TUI's session has ended: what it did to the account is read
        // again.
        if (s.phase === "exited" || s.phase === "failed") account.tuiExited();
      }}
      onMenu={terminalMenu}
      onAppearanceToggle={() =>
        setPrefs((previous) => ({
          ...previous,
          appearance: scheme === "dark" ? "light" : "dark",
        }))
      }
      register={(k, api) => {
        terminals.current[k] = api;
      }}
      tabPanel={kind !== "tui"}
    />
  );

  const pane = "pane flex min-h-0 min-w-0 flex-1 flex-col bg-background";
  const docsPane = (
    <div className={cn(pane, "pane-docs")}>
      <PaneHeader
        title={t(calendarOn ? "desktop.calendar.title" : "desktop.pane.docs")}
        onToggleMaximize={() => toggleMaximize("docs")}
        controls={[
          maximizeControl(
            "docs",
            calendarOn
              ? "desktop.calendar.maximize"
              : "desktop.pane.maximize_docs",
          ),
          // The split's controls are on the TUI's header too: narrow, this
          // header gives them up before it cuts its title.
          ...splitControls.map((control) => ({ ...control, yields: true })),
          // Every column is put away by its own close. The calendar's puts
          // the calendar away, back to the documentation where that is shown.
          calendarOn
            ? {
                id: "close",
                icon: "close",
                label: t("desktop.calendar.close"),
                run: () => setPage("docs"),
              }
            : {
                id: "close",
                icon: "close",
                label: t("desktop.docs.hide"),
                shortcut: primaryChord(byId("docs.toggle")),
                run: () => closeColumn("docs"),
              },
        ]}
      />
      {calendarOn && (
        <FilingCalendarView
          page={calendarPage}
          state={calendar.state}
          attempt={calendar.attempt}
          today={calendar.today}
          memory={calendarMemory}
          // Withheld, it says what the TUI pane says of the account, with
          // the same ways on.
          withheld={
            <SignedOut
              account={account}
              lead={t("desktop.calendar.signed_out")}
              quiet
              onSignIn={askSignIn}
            />
          }
          locale={locale}
          refreshing={calendar.refreshing}
          onRefresh={calendar.refresh}
        />
      )}
      {/* Put aside, not unloaded: the page it was on is there on return. */}
      <div className={calendarOn ? "hidden" : "contents"}>
        {environment.state === "ready" &&
        environment.value.docs.state === "bundled" &&
        docsEntry ? (
          <DocsFrame
            ref={docs}
            origin={environment.value.docs.origin}
            entry={docsEntry.entry}
            title={t("desktop.docs.frame_title")}
            chords={chords}
            zoom={layout.zoom}
            appearance={prefs.appearance === "follow" ? null : prefs.appearance}
            onReady={({ theme, features }) => {
              setDocsTheme(theme);
              setDocsSearchReady(features.includes("search"));
            }}
            onTheme={setDocsTheme}
            onShortcut={runShortcut}
            onOpenExternal={(url) =>
              void host.openExternal(url).catch(() => undefined)
            }
            onMenu={docsMenu}
          />
        ) : environment.state === "ready" &&
          environment.value.docs.state !== "bundled" ? (
          // The documentation is optional: without it the window says so
          // and every other part works as usual.
          <Empty role="status">
            <EmptyMedia>
              <Icon name="tui" />
            </EmptyMedia>
            <EmptyDescription>
              {t(
                environment.value.docs.state === "notBundled"
                  ? "desktop.docs.not_bundled"
                  : "desktop.docs.unavailable",
              )}
            </EmptyDescription>
          </Empty>
        ) : environment.state === "unavailable" ? (
          <Empty role="status">
            <EmptyMedia>
              <Icon name="unplug" />
            </EmptyMedia>
            <EmptyDescription>{t("desktop.host.unavailable")}</EmptyDescription>
          </Empty>
        ) : environment.state === "failed" ? (
          <Empty role="alert">
            <EmptyMedia>
              <Icon name="alert" />
            </EmptyMedia>
            <EmptyDescription>{t("desktop.host.failed")}</EmptyDescription>
          </Empty>
        ) : (
          <Empty role="status">
            <Spinner />
            <EmptyDescription>{t("desktop.docs.loading")}</EmptyDescription>
          </Empty>
        )}
      </div>
    </div>
  );
  const tuiPane = (
    <div className={cn(pane, "pane-tui")} data-scheme={scheme}>
      <PaneHeader
        title={t("desktop.pane.tui")}
        // While the account withholds the TUI there is no session: the
        // header says the account's phase, not the last session's.
        status={
          account.gated
            ? {
                phase:
                  phase === "checking" ||
                  phase === "starting" ||
                  account.startingServices
                    ? "starting"
                    : "unavailable",
                note: t(accountLabel(phase) ?? "desktop.account.unknown"),
              }
            : { phase: status.tui.phase, note: sessionNote("tui") }
        }
        onToggleMaximize={() => toggleMaximize("tui")}
        controls={[
          maximizeControl("tui", "desktop.pane.maximize_tui"),
          ...splitControls,
          {
            id: "close",
            icon: "close",
            label: t("desktop.tui.hide"),
            shortcut: primaryChord(byId("tui.toggle")),
            run: () => closeColumn("tui"),
          },
        ]}
      />
      {account.gated ? (
        <SignedOut
          account={account}
          onSignIn={askSignIn}
          signInButton={signInButton}
        />
      ) : (
        terminalPane(
          "tui",
          tuiVisible,
          scheme === "dark" ? DARK_TUI : LIGHT_TUI,
        )
      )}
    </div>
  );
  const agentPane = (
    <div className={cn(pane, "pane-agent")}>
      {/* One bar: the conversation's own actions, then the column's maximize
          and close as every column has them. */}
      <AgentColumn
        agent={host.agent}
        session={host.agentSession}
        providerSettings={host.providerSettings}
        agentAccess={host.agentAccess}
        writeClipboard={(text) => host.writeClipboard(text)}
        // The agent works only for a profile that is signed in here: not
        // for one the shell cannot tell about.
        reader={signedIn ? (account.status?.active_profile ?? null) : null}
        shown={agentVisible}
        locale={locale}
        body={agentBody}
        onToggleMaximize={() => toggleMaximize("agent")}
        trailing={[
          maximizeControl("agent", "desktop.pane.maximize_agent"),
          {
            id: "close",
            icon: "close",
            label: t("desktop.agent.hide"),
            shortcut: primaryChord(byId("agent.toggle")),
            run: () => closeColumn("agent"),
          } satisfies PaneControl,
        ].map((control) => (
          <IconButton
            key={control.id}
            label={control.label}
            shortcut={control.shortcut}
            aria-pressed={control.pressed}
            onClick={control.run}
          >
            <Icon name={control.icon} />
          </IconButton>
        ))}
      />
    </div>
  );
  // Nothing open above the bottom panel: the main area says so, and offers
  // each column back.
  const canvasShown = !firstPaneShown && !tuiVisible;
  const canvas = (
    <Empty className="canvas bg-background">
      <EmptyMedia>
        <Icon name="canvas" />
      </EmptyMedia>
      <EmptyTitle>{t("desktop.canvas.title")}</EmptyTitle>
      <EmptyDescription>{t("desktop.canvas.lead")}</EmptyDescription>
      <div className="flex flex-wrap justify-center gap-2">
        {(
          [
            [
              "agent.toggle",
              "agent",
              "desktop.agent.show",
              signedIn && !agentVisible,
            ],
            ["tui.toggle", "tui", "desktop.tui.show", true],
            ["docs.toggle", "book", "desktop.docs.show", true],
          ] as const
        ).map(
          ([id, icon, labelKey, offered]) =>
            offered && (
              <Button key={id} variant="outline" onClick={() => runAction(id)}>
                <Icon name={icon} />
                {t(labelKey)}
              </Button>
            ),
        )}
      </div>
    </Empty>
  );
  const panelMax = maximizeControl("panel", "desktop.pane.maximize_panel");

  return (
    <StringsContext.Provider value={t}>
      <TooltipProvider>
        <div className="desktop-window flex h-dvh min-w-0 flex-col bg-chrome">
          <Titlebar
            host={host}
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
              onSignOut={signOut}
              onCreate={askNewProfile}
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
            <div className="flex min-h-0 min-w-0">
              {/* The agent column, always beside the rail, the full height of
                the window under the title bar. */}
              <aside
                ref={agentColumn}
                className={cn(
                  "agent-column flex min-h-0 min-w-0 bg-background",
                  maximized === "agent" ? "flex-1" : "flex-none",
                )}
                hidden={!agentVisible}
                style={
                  maximized === "agent" ? undefined : { width: agentWidth }
                }
                aria-label={t("desktop.pane.agent")}
              >
                {agentPane}
                {/* Inside the column, so the splitter is part of the area it
                    resizes. */}
                {agentVisible && !maximized && (
                  <ResizeHandle
                    className="agent-separator"
                    orientation="vertical"
                    aria-label={t("desktop.agent.resize")}
                    value={besideRail > 0 ? (agentWidth / besideRail) * 100 : 0}
                    // The column starts at the rail, so its width is what lies
                    // left of the pointer. Dragged well past its smallest size,
                    // it collapses.
                    onDrag={({ x }) => {
                      const next =
                        x -
                        (agentColumn.current?.getBoundingClientRect().left ??
                          0);
                      if (next < agentMin - panelCollapseThreshold)
                        patch({ agentShown: false });
                      else setAgentWidth(next);
                    }}
                    onStep={(direction) =>
                      setAgentWidth(agentWidth + direction * panelResizeStep)
                    }
                    onLimit={(limit) =>
                      setAgentWidth(
                        limit === "min" ? agentMin : besideRail - splitMinA,
                      )
                    }
                    onReset={() =>
                      setAgentWidth(DEFAULT_LAYOUT.agentRatio * besideRail)
                    }
                  />
                )}
              </aside>
              <div
                className="flex min-h-0 min-w-0 flex-1 flex-col"
                hidden={maximized === "agent"}
              >
                <main
                  className="main-area flex min-h-0 flex-auto"
                  hidden={maximized === "panel"}
                >
                  {/* Kept mounted while the canvas shows: neither the
                    documentation nor a live terminal is ever reloaded. */}
                  <div
                    className="flex min-h-0 min-w-0 flex-1"
                    hidden={canvasShown}
                  >
                    <Split
                      orientation={orientation}
                      reversed={prefs.order === "tui"}
                      ratio={layout.splitRatio}
                      onRatio={(ratio) => patch({ splitRatio: ratio })}
                      minA={splitMinA}
                      minB={orientation === "row" ? splitMinBRow : splitMinBCol}
                      a={docsPane}
                      b={tuiPane}
                      aShown={firstPaneShown}
                      bShown={tuiVisible}
                      label={t("desktop.split.resize")}
                    />
                  </div>
                  {canvasShown && canvas}
                </main>
                <section
                  className={cn(
                    // A container in both dimensions: its content answers to its width
                    // and, in the log's bar, to its height.
                    "panel flex min-h-0 flex-col bg-chrome [container:panel/size]",
                    maximized === "panel" ? "flex-auto" : "flex-none",
                  )}
                  hidden={!panelVisible}
                  style={
                    maximized === "panel" ? undefined : { height: panelHeight }
                  }
                  aria-label={t("desktop.panel.label")}
                >
                  {layout.panelOpen && !maximized && (
                    <ResizeHandle
                      className="panel-separator"
                      orientation="horizontal"
                      aria-label={t("desktop.panel.resize")}
                      value={(panelHeight / viewportHeight) * 100}
                      // The panel sits on the window's bottom edge, so its height
                      // is what lies below the pointer. Dragged well past its
                      // smallest size, it collapses.
                      onDrag={({ y }) => {
                        const next =
                          (workspace.current?.getBoundingClientRect().bottom ??
                            window.innerHeight) - y;
                        if (next < panelMin - panelCollapseThreshold)
                          patch({ panelOpen: false });
                        else setPanelHeight(next);
                      }}
                      onStep={(direction) =>
                        setPanelHeight(
                          panelHeight - direction * panelResizeStep,
                        )
                      }
                      onLimit={(limit) =>
                        setPanelHeight(
                          limit === "min" ? panelMin : viewportHeight - docsMin,
                        )
                      }
                      onReset={() =>
                        setPanelHeight(
                          DEFAULT_LAYOUT.panelRatio * viewportHeight,
                        )
                      }
                    />
                  )}
                  <Tabs
                    value={layout.tab}
                    // Arrow keys move through the tabs and choose; a click or
                    // Enter also hands the keyboard to the chosen view.
                    onValueChange={(tab) => patch({ tab: tab as PanelTab })}
                    className="tabstrip h-control-lg shrink-0 flex-row items-center border-b pr-1.5 pl-1"
                    onDoubleClick={(event) => {
                      if (!(event.target as HTMLElement).closest("button"))
                        toggleMaximize("panel");
                    }}
                  >
                    <TabsList
                      aria-label={t("desktop.panel.label")}
                      className="h-full"
                    >
                      {TABS.map(([tab, labelKey, icon]) => (
                        <TabsTrigger
                          key={tab}
                          value={tab}
                          id={`tab-${tab}`}
                          aria-controls={`panel-${tab}`}
                          title={t(labelKey)}
                          onClick={() => openTab(tab, { toggle: false })}
                          onKeyDown={(event) => {
                            // Enter and Space choose a tab without a click, so
                            // they hand the keyboard over here.
                            if (event.key === "Enter" || event.key === " ")
                              openTab(tab, { toggle: false });
                          }}
                        >
                          <Icon name={icon} />
                          {/* In a narrow panel the tab keeps its name, not its
                          width. */}
                          <span className="@max-md/panel:sr-only">
                            {t(labelKey)}
                          </span>
                          {tab !== "logs" &&
                            exitCode(status[tab]) !== undefined && (
                              <span className="text-xs font-normal text-faint">
                                {t("desktop.session.exited", {
                                  code: exitCode(status[tab]) ?? "?",
                                })}
                              </span>
                            )}
                          {tab !== "logs" &&
                            failure(status[tab]) !== undefined && (
                              <>
                                <Icon
                                  name="alert"
                                  size="xs"
                                  className="text-destructive"
                                />
                                <span className="sr-only">
                                  {t("desktop.session.failed", {
                                    reason: failure(status[tab]) ?? "",
                                  })}
                                </span>
                              </>
                            )}
                          {tab === "logs" && errorCount > 0 && (
                            <>
                              <Badge variant="count" aria-hidden="true">
                                {errorCount > COUNT_LIMIT
                                  ? `${COUNT_LIMIT}+`
                                  : errorCount}
                              </Badge>
                              <span className="sr-only">
                                {t("desktop.logs.errors", {
                                  count: errorCount,
                                })}
                              </span>
                            </>
                          )}
                        </TabsTrigger>
                      ))}
                    </TabsList>
                    <span className="flex-1 self-stretch" />
                    <IconButton
                      label={panelMax.label}
                      shortcut={panelMax.shortcut}
                      aria-pressed={panelMax.pressed}
                      onClick={panelMax.run}
                    >
                      <Icon name={panelMax.icon} />
                    </IconButton>
                    <IconButton
                      label={t("desktop.panel.hide")}
                      shortcut={primaryChord(byId("panel.toggle"))}
                      onClick={() => runAction("panel.toggle")}
                    >
                      <Icon name="chevronDown" />
                    </IconButton>
                  </Tabs>
                  <div className="relative flex min-h-0 flex-1">
                    {terminalPane("console", tabOpen("console"))}
                    {terminalPane("python", tabOpen("python"))}
                    <HostRecordList
                      host={host}
                      onErrors={setErrorCount}
                      filters={filters}
                      defaultFilters={defaultFilters}
                      setFilters={setFilters}
                      onMenu={recordMenu}
                      shown={tabOpen("logs")}
                    />
                  </div>
                </section>
              </div>
            </div>

            {settingsOpen && (
              <Settings
                prefs={prefs}
                setPrefs={setPrefs}
                languages={languages}
                close={() => setSettingsOpen(false)}
                onReset={() => {
                  setPrefs(DEFAULT_PREFS);
                  setLayout(DEFAULT_LAYOUT);
                  setMaximized(null);
                  say(t("desktop.settings.layout_reset"));
                }}
              />
            )}
            {paletteOpen && (
              <CommandPalette
                actions={actions}
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
                items={menu.items.map((item) =>
                  isSeparator(item)
                    ? item
                    : {
                        id: item.id,
                        label: item.label,
                        shortcut: item.shortcut,
                        enabled: item.enabled,
                      },
                )}
                at={menu.at}
                choose={(id) => {
                  const items = menu.items;
                  setMenu(null);
                  const chosen = items.find(
                    (item) => !isSeparator(item) && item.id === id,
                  );
                  if (chosen && !isSeparator(chosen)) chosen.run?.();
                }}
              />
            )}
            <Toast>{toast}</Toast>
            <SignInDialog
              account={account}
              open={account.gated && !signInDismissed}
              onOpenChange={(open) => {
                setSignInDismissed(!open);
                if (!open) accountRef.current.settle();
              }}
              create={creatingProfile}
              onCreateChange={setCreatingProfile}
              // Opened by the gate closing rather than by a press, the dialog
              // still took focus from somewhere: that is where it returns.
              onOpening={(from) => {
                signInOpener.current ??= {
                  element: from,
                  calendar: from?.closest(".calendar-page") != null,
                };
              }}
              // Put aside, focus goes back to what the dialog took it from
              // while that is on screen, else to the page it was in, else to
              // the TUI's way back in. Admitted, it goes on: to the calendar
              // the sign-in was asked from, else to the TUI that has started.
              // The rail is the last resort of both.
              onClosed={() => {
                const opener = signInOpener.current;
                signInOpener.current = null;
                // Something asked for while the dialog was up comes first.
                grantFocus();
                // The dialog takes a moment to leave. Focus the person has
                // already put somewhere in that moment is left where it is.
                const held = document.activeElement;
                if (held && held !== document.body && !held.closest(".sign-in"))
                  return;
                const shown = (
                  element: Element | null,
                ): element is HTMLElement =>
                  element instanceof HTMLElement &&
                  element.isConnected &&
                  element.offsetParent !== null;
                const from = opener?.element ?? null;
                const page = calendarPage.current;
                const frame = document.querySelector(".docs-frame");
                if (account.gated) {
                  if (shown(from)) from.focus();
                  else if (opener?.calendar && shown(page)) page.focus();
                  else if (shown(signInButton.current))
                    signInButton.current.focus();
                  else if (shown(page)) page.focus();
                  else if (shown(frame) && docs.current) docs.current.focus();
                  else focusRail();
                } else if (opener?.calendar && shown(page)) page.focus();
                else if (panelMaximized) focusView(layout.tab);
                else if (tuiVisible) focusView("tui");
                else if (shown(page)) page.focus();
                else if (shown(frame) && docs.current) docs.current.focus();
                else focusRail();
              }}
            />
          </div>
        </div>
        <AttendanceRequests
          attendance={host.attendance}
          profile={signedIn ? (account.status?.active_profile ?? null) : null}
        />
      </TooltipProvider>
    </StringsContext.Provider>
  );
}
