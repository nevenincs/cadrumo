import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
} from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/components/ui/cn";
import { Empty, EmptyDescription, EmptyMedia } from "@/components/ui/empty";
import { IconButton } from "@/components/ui/icon-button";
import { ResizeHandle } from "@/components/ui/resize-handle";
import { Spinner } from "@/components/ui/spinner";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Toast } from "@/components/ui/toast";
import { CommandPalette, type DocsSearch } from "./components/CommandPalette";
import { ContextMenu } from "./components/ContextMenu";
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
import {
  DEFAULT_FILTERS,
  LEVELS,
  RecordList,
  recordLine,
  type RecordFilters,
} from "./components/RecordList";
import { Settings } from "./components/Settings";
import { Account, SignedOut, SignInDialog } from "./components/SignIn";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useSignIn } from "./shell/signIn";
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
import {
  SOURCE_LOCALE,
  StringsContext,
  translator,
  type Translate,
} from "./shell/strings";
import { DARK_TERMINAL, LIGHT_TERMINAL } from "./shell/terminalThemes";
import { failureCode } from "./errors";

const RECORD_CAP = 10000;
const COUNT_LIMIT = 99;
const TOAST_MS = 2400;
const TABS: readonly (readonly [PanelTab, string, IconName])[] = [
  ["console", "desktop.rail.console", "console"],
  ["python", "desktop.rail.python", "python"],
  ["logs", "desktop.rail.logs", "logs"],
];

type Environment =
  | { state: "loading" }
  | { state: "ready"; value: DesktopEnvironment }
  | { state: "unavailable" };

type MenuEntry =
  (ContextMenuAction & { run?: () => void }) | ContextMenuSeparator;
type OpenMenu = { items: MenuEntry[]; at: { x: number; y: number } };

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

export function App({ host }: { host: Host }) {
  const account = useSignIn(host);
  const initial = useMemo(loadState, []);
  const [prefs, setPrefs] = useState<Prefs>(initial.prefs);
  const [layout, setLayout] = useState<Layout>(initial.layout);
  const [maximized, setMaximized] = useState<Maximized>(null);
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
  const [records, setRecords] = useState<LogRecord[] | null>(null);
  const [dropped, setDropped] = useState(0);
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

  useEffect(() => saveState(prefs, layout), [prefs, layout]);

  const gated = account.gated;
  useEffect(() => {
    if (gated) return;
    // Admitted: the next time the gate closes, the dialog opens again.
    setSignInDismissed(false);
  }, [gated]);

  useEffect(() => {
    let current = true;
    host
      .environment()
      .then((value) => current && setEnvironment({ state: "ready", value }))
      .catch(() => current && setEnvironment({ state: "unavailable" }));
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
        setDropped((d) => d + batch.dropped);
        setRecords((existing) => {
          const next = [...(existing ?? []), ...batch.records];
          if (next.length <= RECORD_CAP) return next;
          setDropped((d) => d + next.length - RECORD_CAP);
          return next.slice(-RECORD_CAP);
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

  const focusTerminal = useCallback((kind: TerminalKind) => {
    requestAnimationFrame(() => terminals.current[kind]?.focus());
  }, []);

  const openTab = useCallback(
    (tab: PanelTab, { toggle = true }: { toggle?: boolean } = {}) => {
      if (toggle && layout.panelOpen && layout.tab === tab) {
        patch({ panelOpen: false });
        if (maximized === "panel") setMaximized(null);
        return;
      }
      if (maximized && maximized !== "panel") setMaximized(null);
      patch({ panelOpen: true, tab });
      if (tab === "logs")
        requestAnimationFrame(() =>
          document.querySelector<HTMLElement>(".logview .filter-text")?.focus(),
        );
      else focusTerminal(tab);
    },
    [layout.panelOpen, layout.tab, maximized, patch, focusTerminal],
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
      if (area === "tui") focusTerminal("tui");
    },
    [maximized, layout.tuiShown, layout.panelOpen, patch, focusTerminal],
  );

  const focusedArea = (): Exclude<Maximized, null> | null => {
    const element = document.activeElement;
    if (!element || element === document.body) return null;
    if (element.closest(".pane-docs")) return "docs";
    if (element.closest(".pane-tui")) return "tui";
    if (element.closest(".panel")) return "panel";
    return null;
  };

  const activeTerminal = (): TerminalKind | null => {
    const owner =
      document.activeElement?.closest<HTMLElement>("[data-terminal]");
    const kind = owner?.dataset.terminal;
    return kind === "console" || kind === "python" || kind === "tui"
      ? kind
      : null;
  };

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
    if (docs.current?.home()) return;
    // A documentation page without the home command still reloads its entry.
    const frame = document.querySelector<HTMLIFrameElement>(".docs-frame");
    if (frame && docsEntry) frame.src = docsEntry.entry;
  }, [docsEntry]);

  const openDoc = useCallback(
    (url: string) => {
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
        run: () => docs.current?.back(),
      },
      {
        id: "docs.forward",
        label: t("desktop.action.docs_forward"),
        group: "docs",
        icon: "forward",
        chords: [{ alt: true, code: "ArrowRight", key: "→", scope: "docs" }],
        run: () => docs.current?.forward(),
      },
      {
        id: "docs.zoomIn",
        label: t("desktop.action.zoom_in"),
        group: "docs",
        icon: "zoomIn",
        chords: [{ mod: true, code: "Equal", key: "=", scope: "docs" }],
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
        run: () =>
          patch({
            zoom: Math.max(0.5, Math.round((layout.zoom - 0.1) * 10) / 10),
          }),
      },
      {
        id: "docs.zoomReset",
        label: t("desktop.action.zoom_reset"),
        group: "docs",
        icon: "search",
        chords: [{ mod: true, code: "Digit0", key: "0", scope: "docs" }],
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
          if (shown) focusTerminal("tui");
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
        run: () =>
          maximized
            ? setMaximized(null)
            : toggleMaximize(focusedArea() ?? "docs"),
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
        icon: "chevronDown",
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
        icon: "copy",
        hidden: true,
        chords: [
          { mod: true, shift: true, code: "KeyV", key: "V", scope: "terminal" },
        ],
        run: () => paste(activeTerminal()),
      },
    ],
    [
      t,
      layout,
      prefs.orientation,
      maximized,
      docsSearchReady,
      docsEntry,
      goHome,
      patch,
      focusTerminal,
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
  const chordsKey = JSON.stringify(bridgeChords(actions));
  const chords = useMemo(
    () => JSON.parse(chordsKey) as ReturnType<typeof bridgeChords>,
    [chordsKey],
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
      event.preventDefault();
      event.stopPropagation();
      action.run();
    };
    window.addEventListener("keydown", key, true);
    return () => window.removeEventListener("keydown", key, true);
  }, []);

  // Menus: drawn by the operating system when the host can, otherwise here.
  const openMenu = useCallback(
    (items: MenuEntry[], at: { x: number; y: number }, pointer: boolean) => {
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
        host.showMenu(plain, pointer ? undefined : at).then(run, (error) => {
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
      // The menu key fires contextmenu with no pointer type; that menu
      // belongs at the event's position rather than at the cursor.
      const pointer = (event as PointerEvent).pointerType !== "";
      openMenu(items, { x: event.clientX, y: event.clientY }, pointer);
    },
    [openMenu, t, copy, paste],
  );

  const recordMenu = useCallback(
    (event: ReactMouseEvent, record: LogRecord, visible: LogRecord[]) => {
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
        { x: event.clientX, y: event.clientY },
        true,
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
    Math.max(panelMin, Math.min(viewportHeight - docsMin, height));
  const panelHeight = clampPanel(
    Math.round(layout.panelRatio * viewportHeight),
  );
  const setPanelHeight = (height: number) =>
    patch({ panelOpen: true, panelRatio: clampPanel(height) / viewportHeight });

  const errorCount = (records ?? []).filter(
    (r) => r.level === "ERROR" || r.level === "CRITICAL",
  ).length;
  const tabOpen = (tab: PanelTab) =>
    layout.panelOpen &&
    layout.tab === tab &&
    maximized !== "docs" &&
    maximized !== "tui";
  const tuiVisible =
    (layout.tuiShown || maximized === "tui") && maximized !== "docs";
  const panelVisible =
    layout.panelOpen && maximized !== "docs" && maximized !== "tui";

  const exitNote = (kind: TerminalKind) => {
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
      pressed: paletteOpen,
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
      onClick: () => openTab("logs"),
    },
  ];
  const railBottom: RailItem[] = [
    {
      id: "settings",
      icon: "settings",
      label: t("desktop.rail.settings"),
      shortcut: primaryChord(byId("settings.open")),
      pressed: settingsOpen,
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
        if (k === "tui" && s.phase === "exited") account.tuiExited();
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
        title={t("desktop.pane.docs")}
        onToggleMaximize={() => toggleMaximize("docs")}
        controls={[
          maximizeControl("docs", "desktop.pane.maximize_docs"),
          ...(tuiVisible ? splitControls : []),
        ]}
      />
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
          onShortcut={runAction}
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
          <EmptyDescription className="pane-note">
            {t("desktop.host.unavailable")}
          </EmptyDescription>
        </Empty>
      ) : (
        <Empty role="status">
          <Spinner />
          <EmptyDescription>{t("desktop.docs.loading")}</EmptyDescription>
        </Empty>
      )}
    </div>
  );
  const tuiPane = (
    // The TUI paints its own dark theme, so its whole area is a dark scheme.
    <div className={cn(pane, "pane-tui")} data-scheme="dark">
      <PaneHeader
        title={t("desktop.pane.tui")}
        status={{ phase: status.tui.phase, note: exitNote("tui") }}
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
          onSignIn={() => setSignInDismissed(false)}
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
        <div
          className={cn(
            "shell grid h-dvh grid-cols-[auto_1fr] bg-chrome",
            `scheme-${scheme}`,
          )}
        >
          <Rail
            label={t("desktop.rail.label")}
            top={railTop}
            bottom={railBottom}
          />
          <div className="workspace flex min-h-0 min-w-0 flex-col">
            <main
              className="main-area flex min-h-(--docs-min) flex-auto"
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
            <section
              className={cn(
                "panel flex min-h-0 flex-col bg-chrome",
                maximized === "panel" ? "is-maximized flex-auto" : "flex-none",
              )}
              hidden={!panelVisible}
              style={
                maximized === "panel" ? undefined : { height: panelHeight }
              }
              aria-label={t("desktop.panel.label")}
            >
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
                      onClick={() => openTab(tab, { toggle: false })}
                    >
                      <Icon name={icon} />
                      {t(labelKey)}
                      {tab !== "logs" &&
                        exitCode(status[tab]) !== undefined && (
                          <span className="exit-note text-xs font-normal text-faint">
                            {t("desktop.session.exited", {
                              code: exitCode(status[tab]) ?? "?",
                            })}
                          </span>
                        )}
                      {tab === "logs" && errorCount > 0 && (
                        <Badge variant="count">
                          {errorCount > COUNT_LIMIT
                            ? `${COUNT_LIMIT}+`
                            : errorCount}
                        </Badge>
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
              <div className="panel-body relative flex min-h-0 flex-1">
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
                  onSignOut={() => {
                    setSignInDismissed(true);
                    void account.signOut();
                  }}
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
            />
          )}
          {menu && (
            <ContextMenu
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
            onOpenChange={(open) => setSignInDismissed(!open)}
            // Dismissed, focus goes to the way back in; signed in, to the
            // TUI that has just started.
            onClosed={() => {
              if (signInButton.current) signInButton.current.focus();
              else requestAnimationFrame(() => terminals.current.tui?.focus());
            }}
          />
        </div>
      </TooltipProvider>
    </StringsContext.Provider>
  );
}
