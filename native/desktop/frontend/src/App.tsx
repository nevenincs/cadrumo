import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
  DesktopEnvironment,
  DocsTheme,
  HostFailure,
  LogRecord,
  LogSourceState,
} from "./ipc/contract";
import { PaneHeader, type PaneControl } from "./components/PaneHeader";
import { Rail, type RailItem } from "./components/Rail";
import { RecordList, type RecordMenuRequest } from "./components/RecordList";
import {
  DEFAULT_FILTERS,
  LEVELS,
  recordLine,
  type RecordFilters,
} from "./shell/records";
import { Settings } from "./components/Settings";
import { accountLabel } from "./components/accountWords";
import { Account, SignedOut, SignInDialog } from "./components/SignIn";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useFilingCalendar } from "./shell/calendar";
import { useMessages } from "./shell/messages";
import { useSignIn } from "./shell/signIn";
import { FilingCalendarView } from "./components/FilingCalendar";
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
import { HostUnavailable, type Host, type TerminalKind } from "./shell/host";
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
import { DARK_TERMINAL, LIGHT_TERMINAL } from "./shell/terminalThemes";
import { failureCode } from "./errors";
import { identity } from "virtual:desktop-content";

const RECORD_CAP = 10000;
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

type Environment =
  | { state: "loading" }
  | { state: "ready"; value: DesktopEnvironment }
  /** There is no desktop host to ask: the page runs in a plain browser. */
  | { state: "unavailable" }
  /** The host was asked and could not answer. */
  | { state: "failed" };

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

/** The workspace area that holds focus, the documentation frame included. */
const focusedArea = (): Area | "rail" | null => {
  const element = document.activeElement;
  if (!element || element === document.body) return null;
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
  const initial = useMemo(loadState, []);
  const [prefs, setPrefs] = useState<Prefs>(initial.prefs);
  const [layout, setLayout] = useState<Layout>(initial.layout);
  const [maximized, setMaximized] = useState<Maximized>(null);
  // What the first pane shows: the documentation, or a view of the profile
  // where the host offers one. The documentation stays loaded underneath.
  const [page, setPage] = useState<"docs" | "calendar">("docs");
  const calendarPage = useRef<HTMLElement>(null);
  // The calendar was asked for: it takes focus once it is laid out.
  const wantsCalendar = useRef(false);
  // What held focus when the sign-in dialog was asked for, and whether
  // that was in the calendar: the control itself may be gone by the close.
  const signInOpener = useRef<{
    element: Element | null;
    calendar: boolean;
  } | null>(null);
  const [environment, setEnvironment] = useState<Environment>({
    state: "loading",
  });
  const [viewportHeight, setViewportHeight] = useState(window.innerHeight);
  const [viewportWidth, setViewportWidth] = useState(window.innerWidth);
  const [docsTheme, setDocsTheme] = useState<DocsTheme>("auto");
  const [docsSearchReady, setDocsSearchReady] = useState(false);
  const [prefersDark, setPrefersDark] = useState(
    () => matchMedia("(prefers-color-scheme: dark)").matches,
  );
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
  const signInButton = useRef<HTMLButtonElement>(null);
  // The log ring and what it has lost, held together: a batch changes both.
  const [log, setLog] = useState<{
    records: LogRecord[] | null;
    dropped: number;
  }>({ records: null, dropped: 0 });
  const { records, dropped } = log;
  const [sourceState, setSourceState] = useState<
    LogSourceState | "unavailable" | null
  >(null);
  const [filters, setFilters] = useState<RecordFilters>(DEFAULT_FILTERS);
  const docs = useRef<DocsFrameApi>(null);
  const terminals = useRef<Partial<Record<TerminalKind, TerminalApi>>>({});
  const toastTimer = useRef(0);
  const nativeMenus = useRef(host.nativeMenus);

  // Layout geometry, read from the canonical tokens (src/tokens.css) instead
  // of duplicated as literals; each metric re-reads on resize.
  const docsMin = useMetric("--docs-min", 200);
  const panelMin = useMetric("--panel-min", 140);
  const splitMinA = useMetric("--split-min-a", 260);
  const splitMinBRow = useMetric("--split-min-b-row", 320);
  const splitMinBCol = useMetric("--split-min-b-col", 160);
  const railWidth = useMetric("--rail-w", 48);
  const panelResizeStep = useMetric("--resize-step", 24);
  const panelCollapseThreshold = useMetric("--panel-collapse-threshold", 60);
  const terminalFontSize = useTerminalFontSize(prefs.fontSize);

  const patch = useCallback(
    (change: Partial<Layout>) =>
      setLayout((current) => ({ ...current, ...change })),
    [],
  );

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
  const accountRef = useRef(account);
  accountRef.current = account;
  const signOut = useCallback(() => {
    // Signing out here is not a reason to ask for the password again.
    setSignInDismissed(true);
    void accountRef.current.signOut();
  }, []);
  useEffect(() => {
    if (gated) return;
    // Admitted: the next time the gate closes, the dialog opens again.
    setSignInDismissed(false);
  }, [gated]);
  const signOutFailed = account.signOutFailure !== null;
  useEffect(() => {
    // A sign-out that failed leaves the person signed in: the next time the
    // gate closes it is not by their choice, so the dialog opens.
    if (signOutFailed) setSignInDismissed(false);
  }, [signOutFailed]);
  const mayEnterPassword = account.canSignIn;

  const views = host.views;
  const firstPaneShown = maximized !== "tui" && maximized !== "panel";
  const calendarOn = views !== undefined && page === "calendar";
  const calendarVisible = calendarOn && firstPaneShown;
  // Whose views are read: the signed-in profile's. Where the platform signs
  // in inside the TUI the shell cannot tell, so it asks and shows the answer.
  const reader =
    signedIn || phase === "unsupported"
      ? (account.status?.active_profile ?? "")
      : null;
  const recheckAccount = useCallback(() => accountRef.current.recheck(), []);
  const [rechecking, setRechecking] = useState(false);
  const lookAgain = useCallback(() => {
    setRechecking(true);
    void recheckAccount().finally(() => setRechecking(false));
  }, [recheckAccount]);
  const calendar = useFilingCalendar(
    views,
    reader,
    calendarVisible,
    recheckAccount,
  );
  const messages = useMessages(views, reader, recheckAccount);
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
    if (calendarVisible && phase === "in-tui") void recheckAccount();
  }, [calendarVisible, phase, recheckAccount]);
  const askSignIn = useCallback(() => {
    const element = document.activeElement;
    signInOpener.current = {
      element,
      calendar: element?.closest(".calendar-page") != null,
    };
    setSignInDismissed(false);
  }, []);
  // Settings closes by more than one way; what it showed is settled by all.
  useEffect(() => {
    if (!settingsOpen) accountRef.current.settle();
  }, [settingsOpen]);

  useEffect(() => {
    let current = true;
    host
      .environment()
      .then((value) => current && setEnvironment({ state: "ready", value }))
      .catch(
        (error: unknown) =>
          current &&
          setEnvironment({
            state: error instanceof HostUnavailable ? "unavailable" : "failed",
          }),
      );
    return () => {
      current = false;
    };
  }, [host]);

  useEffect(() => {
    const query = matchMedia("(prefers-color-scheme: dark)");
    const change = () => setPrefersDark(query.matches);
    const resize = () => {
      setViewportHeight(window.innerHeight);
      setViewportWidth(window.innerWidth);
    };
    query.addEventListener("change", change);
    window.addEventListener("resize", resize);
    return () => {
      query.removeEventListener("change", change);
      window.removeEventListener("resize", resize);
    };
  }, []);

  // Log batches: a bounded ring; a missing or unreadable source keeps its state.
  useEffect(() => {
    let unsubscribe: (() => void) | null = null;
    let current = true;
    host
      .subscribeLogs((batch) => {
        if (!current) return;
        setSourceState(batch.state);
        setLog((held) => {
          const next = [...(held.records ?? []), ...batch.records];
          const over = Math.max(0, next.length - RECORD_CAP);
          return {
            records: over ? next.slice(over) : next,
            dropped: held.dropped + batch.dropped + over,
          };
        });
      })
      .then((stop) => {
        if (current) unsubscribe = stop;
        else stop();
      })
      .catch((error: unknown) => {
        if (current)
          setSourceState(
            error instanceof HostUnavailable
              ? "unavailable"
              : {
                  kind: "unreadable",
                  detail: "",
                  failure: isHostFailure(error) ? error : null,
                },
          );
      });
    return () => {
      current = false;
      unsubscribe?.();
    };
  }, [host]);

  // The window's language: the person's own choice where the documentation
  // is bundled in it, otherwise the language Cadrumo reports.
  const languages = useMemo(
    () =>
      environment.state === "ready"
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
    const { languages: bundled } = environment.value.docs;
    return (
      bundled.find((language) => language.code === locale) ?? bundled[0] ?? null
    );
  }, [environment, locale]);

  const say = useCallback((text: string) => {
    setToast(text);
    window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(null), TOAST_MS);
  }, []);

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
  } | null>(null);
  const grantFocus = useCallback(() => {
    const wish = wanted.current;
    if (!wish) return;
    if (performance.now() > wish.since + FOCUS_WISH_MS) {
      wanted.current = null;
      return;
    }
    if (wish.granted && document.activeElement !== document.body) return;
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
    else return;
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
  // Every way into the TUI's own flow, from the pane, the dialog, settings
  // or the palette: the TUI is shown and the keyboard goes to it.
  const continueInTui = useCallback(() => {
    // Wherever it was asked from, the keyboard goes on to the TUI.
    signInOpener.current = null;
    accountRef.current.openTui();
    setSettingsOpen(false);
    showTui();
  }, [showTui]);
  // Whether the last render showed a gate the person could act on. The
  // first status read is a gate too, but not one anybody was standing at:
  // being let through it at startup moves no focus.
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
    stoodAtGate.current = gated && phase !== "checking";
  }, [gated, phase, focusView]);
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
      if (area === "tui" && !layout.tuiShown) patch({ tuiShown: true });
      if (area === "panel" && !layout.panelOpen) patch({ panelOpen: true });
      setMaximized(area);
      if (area === "tui") focusView("tui");
    },
    [maximized, layout.tuiShown, layout.panelOpen, patch, focusView],
  );

  // The keyboard's way between the areas of the window, in the order they
  // are laid out. A focused terminal keeps Tab for itself, so this is how
  // focus leaves one.
  const cycleFocus = useCallback(
    (step: 1 | -1) => {
      const tuiOn =
        (layout.tuiShown || maximized === "tui") &&
        maximized !== "docs" &&
        maximized !== "panel";
      const panelOn =
        layout.panelOpen && maximized !== "docs" && maximized !== "tui";
      const stops: [Area | "rail", boolean, () => void][] = [
        [
          "docs",
          maximized !== "tui" &&
            maximized !== "panel" &&
            (calendarPage.current !== null || !!docs.current),
          () => (calendarPage.current ?? docs.current)?.focus(),
        ],
        [
          "tui",
          // Only where the pane holds something to focus: the way in while
          // signed out, or a session.
          tuiOn &&
            (signInButton.current !== null ||
              (!gated && status.tui.phase !== "unavailable")),
          () =>
            signInButton.current
              ? signInButton.current.focus()
              : terminals.current.tui?.focus(),
        ],
        [
          "panel",
          panelOn,
          () => {
            if (layout.tab === "logs")
              document
                .querySelector<HTMLElement>(".logview .filter-text")
                ?.focus();
            // Without a session there is no terminal to focus; its tab is.
            else if (status[layout.tab].phase === "unavailable")
              document.getElementById(`tab-${layout.tab}`)?.focus();
            else terminals.current[layout.tab]?.focus();
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
      layout.tuiShown,
      layout.panelOpen,
      layout.tab,
      maximized,
      gated,
      status,
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
    setPage("docs");
    if (docs.current?.home()) return;
    // A documentation page without the home command still reloads its entry.
    const frame = document.querySelector<HTMLIFrameElement>(".docs-frame");
    if (frame && docsEntry) frame.src = docsEntry.entry;
  }, [docsEntry]);

  const openDoc = useCallback(
    (url: string) => {
      setPage("docs");
      if (docs.current?.navigate(url)) return;
      const frame = document.querySelector<HTMLIFrameElement>(".docs-frame");
      if (!frame || environment.state !== "ready") return;
      // Only a documentation-origin address ever becomes the frame's source.
      let origin: string;
      try {
        origin = new URL(url).origin;
      } catch {
        return;
      }
      if (origin === environment.value.docs.origin) frame.src = url;
    },
    [environment],
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
        id: "tui.toggle",
        label:
          layout.tuiShown && !maximized
            ? t("desktop.tui.hide")
            : t("desktop.tui.show"),
        group: "layout",
        icon: "tui",
        chords: [
          { mod: true, shift: true, code: "KeyT", key: "T", scope: "global" },
        ],
        run: () => {
          const shown = maximized ? true : !layout.tuiShown;
          if (maximized) setMaximized(null);
          patch({ tuiShown: shown });
          if (shown) focusView("tui");
        },
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
          toggleMaximize(area && area !== "rail" ? area : "docs");
        },
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
        run: () => setFilters(DEFAULT_FILTERS),
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
        // The TUI's own flow, wherever the account is not settled: the way
        // on when no password can settle it.
        id: "account.openTui",
        label: t("desktop.signin.open_tui"),
        group: "account",
        icon: "tui",
        keywords: "unlock recovery another profile",
        enabled: () => gated && phase !== "checking" && phase !== "no-profile",
        run: continueInTui,
      },
      {
        id: "account.createProfile",
        label: t("desktop.account.create_profile"),
        group: "account",
        icon: "user",
        keywords: "register new account",
        enabled: () => phase === "no-profile",
        run: continueInTui,
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
      layout.tuiShown,
      layout.panelOpen,
      layout.tab,
      layout.zoom,
      prefs.orientation,
      maximized,
      docsSearchReady,
      docsEntry,
      phase,
      views,
      messages,
      say,
      showTui,
      calendarOn,
      calendarVisible,
      gated,
      askSignIn,
      mayEnterPassword,
      continueInTui,
      signedIn,
      signOut,
      cycleFocus,
      openLink,
      goHome,
      patch,
      focusView,
      toggleMaximize,
      openTab,
      copy,
      paste,
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
                minLevel: Math.max(0, LEVELS.indexOf(record.level ?? "INFO")),
              })),
          },
        ],
        at,
        pointer,
      );
    },
    [openMenu, t, copy],
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

  const errorCount = useMemo(
    () =>
      (records ?? []).filter(
        (r) => r.level === "ERROR" || r.level === "CRITICAL",
      ).length,
    [records],
  );
  const tabOpen = (tab: PanelTab) =>
    layout.panelOpen &&
    layout.tab === tab &&
    maximized !== "docs" &&
    maximized !== "tui";
  const tuiVisible =
    (layout.tuiShown || maximized === "tui") && maximized !== "docs";
  const panelVisible =
    layout.panelOpen && maximized !== "docs" && maximized !== "tui";

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
  // Side by side needs room for both panes' minimums; a narrower window
  // stacks them without changing the remembered preference.
  const orientation =
    prefs.orientation === "row" &&
    viewportWidth - railWidth < splitMinA + splitMinBRow
      ? "column"
      : prefs.orientation;

  const splitControls: PaneControl[] = maximized
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
    {
      id: "home",
      icon: "book",
      label: t("desktop.rail.docs_home"),
      shortcut: primaryChord(byId("docs.home")),
      divided: true,
      onClick: () => runAction("docs.home"),
    },
    {
      id: "tui",
      icon: "tui",
      label: t("desktop.rail.tui"),
      shortcut: primaryChord(byId("tui.toggle")),
      pressed: tuiVisible,
      onClick: () => runAction("tui.toggle"),
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
      id: "console",
      icon: "console",
      label: t("desktop.rail.console"),
      shortcut: primaryChord(byId("panel.console")),
      pressed: tabOpen("console"),
      divided: true,
      onClick: () => openTab("console"),
    },
    {
      id: "python",
      icon: "python",
      label: t("desktop.rail.python"),
      shortcut: primaryChord(byId("panel.python")),
      pressed: tabOpen("python"),
      onClick: () => openTab("python"),
    },
    {
      id: "logs",
      icon: "logs",
      label: t("desktop.rail.logs"),
      shortcut: primaryChord(byId("panel.logs")),
      pressed: tabOpen("logs"),
      badge: errorCount,
      badgeLabel: t("desktop.logs.errors", { count: errorCount }),
      onClick: () => openTab("logs"),
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
        // The TUI's own flow has ended, or never began: the person is back
        // at the gate, and is told when it was because it could not start.
        if (s.phase === "failed" && accountRef.current.phase === "in-tui")
          say(t("desktop.session.failed", { reason: s.message }));
        if (s.phase === "exited" || s.phase === "failed") account.tuiExited();
      }}
      onMenu={terminalMenu}
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
          ...(tuiVisible
            ? splitControls.map((control) => ({ ...control, yields: true }))
            : []),
          // The calendar is put away as the TUI is: by its pane's close.
          ...(calendarOn
            ? [
                {
                  id: "close",
                  icon: "close",
                  label: t("desktop.calendar.close"),
                  run: () => setPage("docs"),
                } satisfies PaneControl,
              ]
            : []),
        ]}
      />
      {calendarOn && (
        <FilingCalendarView
          page={calendarPage}
          state={calendar.state}
          attempt={calendar.attempt}
          // Withheld, it says what the TUI pane says of the account, with
          // the same ways on. While the person carries on in the TUI the
          // window does not know how that went: it offers to look again.
          withheld={
            phase === "in-tui" ? (
              <Empty>
                <EmptyMedia>
                  <Icon name="tui" />
                </EmptyMedia>
                <EmptyTitle>{t("desktop.account.in_tui")}</EmptyTitle>
                <Button
                  variant="outline"
                  pending={rechecking}
                  onClick={lookAgain}
                >
                  {t("desktop.calendar.refresh")}
                </Button>
              </Empty>
            ) : (
              <SignedOut
                account={account}
                lead={t("desktop.calendar.signed_out")}
                quiet
                onSignIn={askSignIn}
                onOpenTui={continueInTui}
              />
            )
          }
          locale={locale}
          refreshing={calendar.refreshing}
          onRefresh={calendar.refresh}
        />
      )}
      {/* Put aside, not unloaded: the page it was on is there on return. */}
      <div className={calendarOn ? "hidden" : "contents"}>
        {environment.state === "ready" && docsEntry ? (
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
    // The TUI paints its own dark theme, so its whole area is a dark scheme.
    <div className={cn(pane, "pane-tui")} data-scheme="dark">
      <PaneHeader
        title={t("desktop.pane.tui")}
        // While the account withholds the TUI there is no session: the
        // header says the account's phase, not the last session's.
        status={
          account.gated
            ? {
                phase: phase === "checking" ? "starting" : "unavailable",
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
            run: () => runAction("tui.toggle"),
          },
        ]}
      />
      {account.gated ? (
        <SignedOut
          account={account}
          onSignIn={askSignIn}
          onOpenTui={continueInTui}
          signInButton={signInButton}
        />
      ) : (
        terminalPane("tui", tuiVisible, DARK_TERMINAL)
      )}
    </div>
  );
  const panelMax = maximizeControl("panel", "desktop.pane.maximize_panel");

  return (
    <StringsContext.Provider value={t}>
      <TooltipProvider>
        <div className="shell grid h-dvh grid-cols-[auto_1fr] grid-rows-[minmax(0,1fr)] bg-chrome">
          <header className="sr-only">
            <h1>{identity.name}</h1>
          </header>
          <Rail
            label={t("desktop.rail.label")}
            top={railTop}
            bottom={railBottom}
          />
          <div className="flex min-h-0 min-w-0 flex-col">
            <main
              className="main-area flex min-h-0 flex-auto"
              hidden={maximized === "panel"}
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
                aShown={maximized !== "tui"}
                bShown={tuiVisible}
                label={t("desktop.split.resize")}
              />
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
                    const next = viewportHeight - y;
                    if (next < panelMin - panelCollapseThreshold)
                      patch({ panelOpen: false });
                    else setPanelHeight(next);
                  }}
                  onStep={(direction) =>
                    setPanelHeight(panelHeight - direction * panelResizeStep)
                  }
                  onLimit={(limit) =>
                    setPanelHeight(
                      limit === "min" ? panelMin : viewportHeight - docsMin,
                    )
                  }
                  onReset={() =>
                    setPanelHeight(DEFAULT_LAYOUT.panelRatio * viewportHeight)
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
                      {tab !== "logs" && failure(status[tab]) !== undefined && (
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
                            {t("desktop.logs.errors", { count: errorCount })}
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
                <RecordList
                  records={records}
                  sourceState={sourceState}
                  dropped={dropped}
                  filters={filters}
                  setFilters={setFilters}
                  onMenu={recordMenu}
                  shown={tabOpen("logs")}
                />
              </div>
            </section>
          </div>

          {settingsOpen && (
            <Settings
              account={
                <Account
                  account={account}
                  onSignIn={() => {
                    setSettingsOpen(false);
                    signInOpener.current = null;
                    setSignInDismissed(false);
                  }}
                  onSignOut={signOut}
                  onOpenTui={continueInTui}
                />
              }
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
            onOpenTui={continueInTui}
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
              // The dialog takes a moment to leave. Focus the person has
              // already put somewhere in that moment is left where it is.
              const held = document.activeElement;
              if (held && held !== document.body && !held.closest(".sign-in"))
                return;
              const shown = (element: Element | null): element is HTMLElement =>
                element instanceof HTMLElement &&
                element.isConnected &&
                element.offsetParent !== null;
              const from = opener?.element ?? null;
              const page = calendarPage.current;
              if (account.gated) {
                if (shown(from)) from.focus();
                else if (opener?.calendar && shown(page)) page.focus();
                else if (shown(signInButton.current))
                  signInButton.current.focus();
                else if (shown(page)) page.focus();
                else focusRail();
              } else if (opener?.calendar && shown(page)) page.focus();
              else if (tuiVisible) focusView("tui");
              else if (shown(page)) page.focus();
              else focusRail();
            }}
          />
        </div>
      </TooltipProvider>
    </StringsContext.Provider>
  );
}
