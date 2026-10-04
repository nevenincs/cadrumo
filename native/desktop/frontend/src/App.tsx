import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
} from "react";
import { CommandPalette, type DocsSearch } from "./components/CommandPalette";
import { ContextMenu } from "./components/ContextMenu";
import { Icon } from "./components/Icon";
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
import {
  IconButton,
  PaneHeader,
  type PaneControl,
} from "./components/PaneHeader";
import { Rail, type RailItem } from "./components/Rail";
import {
  DEFAULT_FILTERS,
  LEVELS,
  RecordList,
  recordLine,
  type RecordFilters,
} from "./components/RecordList";
import { Settings } from "./components/Settings";
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

const RECORD_CAP = 10000;
const TABS: readonly (readonly [PanelTab, string, string])[] = [
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
  const initial = useMemo(loadState, []);
  const [prefs, setPrefs] = useState<Prefs>(initial.prefs);
  const [layout, setLayout] = useState<Layout>(initial.layout);
  const [maximized, setMaximized] = useState<Maximized>(null);
  const [environment, setEnvironment] = useState<Environment>({
    state: "loading",
  });
  const [viewportHeight, setViewportHeight] = useState(window.innerHeight);
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
  const [records, setRecords] = useState<LogRecord[] | null>(null);
  const [dropped, setDropped] = useState(0);
  const [sourceState, setSourceState] = useState<
    LogSourceState | "unavailable" | null
  >(null);
  const [filters, setFilters] = useState<RecordFilters>(DEFAULT_FILTERS);
  const docs = useRef<DocsFrameApi>(null);
  const terminals = useRef<Partial<Record<TerminalKind, TerminalApi>>>({});
  const returnFocus = useRef<Element | null>(null);
  const toastTimer = useRef(0);
  const nativeMenus = useRef(host.nativeMenus);

  // Layout geometry, read from the canonical tokens (src/tokens.css) instead
  // of duplicated as literals; each metric re-reads on resize.
  const docsMin = useMetric("--docs-min", 200);
  const panelMin = useMetric("--panel-min", 140);
  const splitMinA = useMetric("--split-min-a", 260);
  const splitMinBRow = useMetric("--split-min-b-row", 320);
  const splitMinBCol = useMetric("--split-min-b-col", 160);
  const panelResizeStep = useMetric("--resize-step", 24);
  const panelCollapseThreshold = useMetric("--panel-collapse-threshold", 60);
  const terminalFontSize = useTerminalFontSize(prefs.fontSize);

  const patch = useCallback(
    (change: Partial<Layout>) =>
      setLayout((current) => ({ ...current, ...change })),
    [],
  );

  useEffect(() => saveState(prefs, layout), [prefs, layout]);

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
    const resize = () => setViewportHeight(window.innerHeight);
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

  const locale =
    environment.state === "ready"
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
    const { docs: d, outputLanguage } = environment.value;
    return (
      d.languages.find((language) => language.code === outputLanguage) ??
      d.languages[0] ??
      null
    );
  }, [environment]);

  const say = useCallback((text: string) => {
    setToast(text);
    window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(null), 2400);
  }, []);

  const copy = useCallback(
    (text: string) => {
      if (!text) return;
      host.writeClipboard(text).then(
        () => say(t("desktop.toast.copied")),
        () => undefined,
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
        () => undefined,
      );
    },
    [host],
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
      if (
        frame &&
        environment.state === "ready" &&
        new URL(url).origin === environment.value.docs.origin
      )
        frame.src = url;
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
        run: () =>
          setPaletteOpen((open) => {
            if (!open) returnFocus.current = document.activeElement;
            return !open;
          }),
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
        icon: "zoom",
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
        icon: "zoom",
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
        icon: "zoom",
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
        run: () =>
          copy(terminals.current[activeTerminal() ?? "tui"]?.selection() ?? ""),
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
        true,
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
      openMenu(items, { x: event.clientX, y: event.clientY }, true);
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
  const dragPanel = (event: ReactMouseEvent) => {
    event.preventDefault();
    const startY = event.clientY;
    const start = panelHeight;
    document.body.classList.add("dragging-y");
    const move = (e: PointerEvent) => {
      const next = start + (startY - e.clientY);
      if (next < panelMin - panelCollapseThreshold) patch({ panelOpen: false });
      else
        patch({
          panelOpen: true,
          panelRatio: clampPanel(next) / viewportHeight,
        });
    };
    const up = () => {
      document.body.classList.remove("dragging-y");
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };

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
    const chord = primaryChord(byId("view.maximize"));
    return {
      id: "maximize",
      icon: on ? "restore" : "maximize",
      label: `${on ? t("desktop.pane.restore") : t(labelKey)} (${chord})`,
      pressed: on,
      run: () => toggleMaximize(area),
    };
  };
  const splitControls: PaneControl[] = maximized
    ? []
    : [
        {
          id: "swap",
          icon: "swap",
          label: t("desktop.split.swap"),
          run: () => runAction("split.swap"),
        },
        {
          id: "orientation",
          icon: byId("split.orientation")?.icon ?? "splitColumn",
          label: byId("split.orientation")?.label ?? "",
          run: () => runAction("split.orientation"),
        },
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
      onStatus={(k, s) => setStatus((all) => ({ ...all, [k]: s }))}
      onMenu={terminalMenu}
      register={(k, api) => {
        terminals.current[k] = api;
      }}
      tabPanel={kind !== "tui"}
    />
  );

  const docsPane = (
    <div className="pane pane-docs">
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
        <p className="pane-note" role="status">
          {t("desktop.host.unavailable")}
        </p>
      ) : null}
    </div>
  );
  const tuiPane = (
    // The TUI paints its own dark theme, so its whole area is a dark scheme.
    <div className="pane pane-tui" data-scheme="dark">
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
            label: `${t("desktop.tui.hide")} (${primaryChord(byId("tui.toggle"))})`,
            run: () => runAction("tui.toggle"),
          },
        ]}
      />
      {terminalPane("tui", tuiVisible, DARK_TERMINAL)}
    </div>
  );
  const panelMax = maximizeControl("panel", "desktop.pane.maximize_panel");

  return (
    <StringsContext.Provider value={t}>
      <div className={`shell scheme-${scheme}`}>
        <Rail
          label={t("desktop.rail.label")}
          top={railTop}
          bottom={railBottom}
        />
        <div className="workspace">
          <main className="main-area" hidden={maximized === "panel"}>
            <Split
              orientation={prefs.orientation}
              reversed={prefs.order === "tui"}
              ratio={layout.splitRatio}
              onRatio={(ratio) => patch({ splitRatio: ratio })}
              minA={splitMinA}
              minB={prefs.orientation === "row" ? splitMinBRow : splitMinBCol}
              a={docsPane}
              b={tuiPane}
              aShown={maximized !== "tui"}
              bShown={tuiVisible}
              label={t("desktop.split.resize")}
            />
          </main>
          {layout.panelOpen && !maximized && (
            <div
              className="panel-separator"
              role="separator"
              aria-orientation="horizontal"
              aria-label={t("desktop.panel.resize")}
              tabIndex={0}
              onPointerDown={dragPanel}
              onKeyDown={(event) => {
                if (event.key === "ArrowUp")
                  patch({
                    panelRatio:
                      clampPanel(panelHeight + panelResizeStep) /
                      viewportHeight,
                  });
                if (event.key === "ArrowDown")
                  patch({
                    panelRatio:
                      clampPanel(panelHeight - panelResizeStep) /
                      viewportHeight,
                  });
              }}
            />
          )}
          <section
            className={`panel ${maximized === "panel" ? "is-maximized" : ""}`}
            hidden={!panelVisible}
            style={maximized === "panel" ? undefined : { height: panelHeight }}
            aria-label={t("desktop.panel.label")}
          >
            <div
              className="tabstrip"
              role="tablist"
              aria-label={t("desktop.panel.label")}
              onDoubleClick={(event) =>
                event.target === event.currentTarget && toggleMaximize("panel")
              }
            >
              {TABS.map(([tab, labelKey, icon], index) => (
                <button
                  key={tab}
                  id={`tab-${tab}`}
                  role="tab"
                  aria-selected={layout.tab === tab}
                  aria-controls={`panel-${tab}`}
                  tabIndex={layout.tab === tab ? 0 : -1}
                  className="tab"
                  onClick={() => openTab(tab, { toggle: false })}
                  onKeyDown={(event) => {
                    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft")
                      return;
                    const next =
                      TABS[
                        (index +
                          (event.key === "ArrowRight" ? 1 : TABS.length - 1)) %
                          TABS.length
                      ]?.[0];
                    if (!next) return;
                    patch({ tab: next });
                    document.getElementById(`tab-${next}`)?.focus();
                  }}
                >
                  <Icon name={icon} size="s" />
                  {t(labelKey)}
                  {tab !== "logs" && exitCode(status[tab]) !== undefined && (
                    <span className="exit-note">
                      {t("desktop.session.exited", {
                        code: exitCode(status[tab]) ?? "?",
                      })}
                    </span>
                  )}
                  {tab === "logs" && errorCount > 0 && (
                    <span className="tab-badge">{errorCount}</span>
                  )}
                </button>
              ))}
              <span className="tools-spacer" />
              <IconButton
                icon={panelMax.icon}
                label={panelMax.label}
                pressed={panelMax.pressed}
                run={panelMax.run}
              />
              <IconButton
                icon="chevronDown"
                label={`${t("desktop.panel.hide")} (${primaryChord(byId("panel.toggle"))})`}
                run={() => runAction("panel.toggle")}
              />
            </div>
            <div className="panel-body">
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
            prefs={prefs}
            setPrefs={setPrefs}
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
            close={() => {
              setPaletteOpen(false);
              const back = returnFocus.current;
              if (back instanceof HTMLElement)
                requestAnimationFrame(() => back.focus());
            }}
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
        {toast && (
          <div className="toast" role="status">
            {toast}
          </div>
        )}
      </div>
    </StringsContext.Provider>
  );
}
