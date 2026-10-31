import {
  useState,
  useEffect,
  useReducer,
  useRef,
  useMemo,
  Fragment,
  type Dispatch,
  type ReactNode,
  type RefObject,
} from "react";
import { clsx as cx } from "clsx";
import "@/styles/ledger-prototype.css";
import { Logo } from "@/components/Logo";
import { Icon, type IconName } from "./Icon";
import { PageCtx, usePage } from "./page";
import {
  CLOCK,
  COL_LABEL,
  PRESETS,
  StoreCtx,
  initState,
  reducer,
  useStore,
} from "./store";
import {
  Alert,
  Button,
  Dialog,
  Empty,
  Field,
  IconButton,
  Input,
  LiveRegion,
  Menu,
  Seg,
  Select,
  Spinner,
  Tabs,
  ToastHost,
  TooltipLayer,
  announce,
  chord,
  copyText,
  isShellChord,
  OverlayCtx,
  sleep,
  useToast,
} from "./Primitives";
import { PROFILE, hashHex, quarterOf } from "./data";
import type {
  ActionOpts,
  DialogName,
  DialogProps,
  DialogState,
  LifecycleActionType,
  PageApi,
  Registered,
} from "./page";
import type { GridActive, GridApi, GridColumn } from "./DataGrid";
import type { InvoicePrefill } from "./Sections";
import type { PaletteAction } from "./Dialogs";
import type { Action, StageChange } from "./store";
import type { Cls, Invoice, Movement, State, Suggestion, View } from "./types";
import { EMPTY_FILTERS } from "./model";
import {
  ChangesTray,
  MovementsSection,
  useMedia,
  useNarrow,
} from "./Movements";
import {
  GROUPS,
  PREFS,
  SAVED_VIEWS,
  canon,
  canonOf,
  effDate,
  effective,
  fmtDateLong,
  fmtMoney,
  getField,
  inPeriod,
  lockReason,
  parseAmount,
  periodShort,
  plural,
  reviewStatus,
  stepPeriod,
  trayCounts,
  tsvEscape,
} from "./model";
import { CLASSIFIED } from "./vocab";
import { PeriodControl } from "./PeriodSelector";
import { stageLinkAction } from "./Inspector";
import {
  ActionDialog,
  ClassifyDialog,
  ColumnsDialog,
  DiscardDialog,
  ExportDialog,
  ImportDialog,
  LeaveDialog,
  Palette,
  PasteDialog,
  ReviewDialog,
  RuleDialog,
  ShortcutsDialog,
  SuggestionsDialog,
} from "./Dialogs";
import {
  DocumentsSection,
  HealthSection,
  InvoiceSheet,
  InvoicesSection,
  RegistersSection,
  RulesSection,
} from "./Sections";
import { DataGrid } from "./DataGrid";

/* ── The window: title bar, rail, the Ledger pane. ───────────────────── */
export type Guard = (what: string, proceed: () => void) => void;
export function Titlebar({
  signedIn,
  guard,
}: {
  signedIn: boolean;
  guard: Guard;
}) {
  const [menu, setMenu] = useState<HTMLElement | null>(null);
  const [, dispatch] = useStore();
  const toast = useToast();
  return (
    <header className="titlebar" aria-label="Title bar">
      <h1 className="titlebar-brand" aria-label="Cadrumo">
        <Logo size="sm" />
      </h1>
      <div className="titlebar-space" aria-hidden="true"></div>
      <div className="titlebar-account">
        <Button
          variant="ghost"
          size="sm"
          className="profile-trigger"
          aria-haspopup="menu"
          aria-expanded={!!menu}
          onClick={(e) => setMenu(e.currentTarget)}
        >
          <Icon name="user" className="narrow-only" />
          <span
            className={cx("profile-status", signedIn && "on")}
            aria-hidden="true"
          />
          <span
            className="truncate"
            style={{ maxWidth: "calc(var(--spacing) * 48)" }}
          >
            {PROFILE.name}
          </span>
          <span className="sr-only">
            , {signedIn ? "Signed in" : "Signed out"}
          </span>
          <Icon name="chevronDown" size="xs" />
        </Button>
        {menu ? (
          <Menu
            anchor={menu}
            label="Account"
            align="end"
            onClose={() => setMenu(null)}
            items={[
              {
                label: "Switch profile…",
                icon: "users",
                onSelect: () =>
                  guard("Switching profile", () =>
                    toast(
                      "The profile switcher is the shell's; not part of this prototype",
                    ),
                  ),
              },
              {
                label: "Sign out",
                icon: "lock",
                disabled: !signedIn,
                onSelect: () =>
                  guard("Signing out", () => {
                    dispatch({ type: "DISCARD" });
                    dispatch({ type: "PROTO", patch: { state: "signedOut" } });
                  }),
              },
            ]}
          />
        ) : null}
      </div>
      <div className="window-controls">
        <button
          type="button"
          className="btn ghost icon-lg window-control"
          aria-label="Minimize"
          data-tip="Minimize"
        >
          <span className="wglyph-min" aria-hidden="true"></span>
        </button>
        <button
          type="button"
          className="btn ghost icon-lg window-control"
          aria-label="Maximize"
          data-tip="Maximize"
        >
          <Icon name="windowMaximize" size="xs" />
        </button>
        <button
          type="button"
          className="btn ghost icon-lg window-control close"
          aria-label="Close"
          data-tip="Close"
          onClick={() =>
            guard("Closing the window", () =>
              toast("The window would close now"),
            )
          }
        >
          <Icon name="close" size="xs" />
        </button>
      </div>
    </header>
  );
}
export function Rail({
  onPalette,
  guard,
  hidden,
}: {
  onPalette: () => void;
  guard: Guard;
  hidden?: boolean;
}) {
  const toast = useToast();
  const other = (n: string, what?: string) => () =>
    guard(
      `Opening ${(what || n).replace(/^The /, "the ").replace(/^Your /, "your ")}`,
      () => toast(`${n} is another part of the shell, outside this prototype`),
    );
  type RailItem = {
    id: string;
    icon: IconName;
    label: string;
    shortcut?: string;
    divided?: boolean;
    pressed?: boolean;
    run: () => void;
  };
  const top: RailItem[] = [
    {
      id: "search",
      icon: "search",
      label: "Search and commands",
      shortcut: "Ctrl+K",
      run: onPalette,
    },
    {
      id: "agent",
      icon: "agent",
      label: "Assistant",
      shortcut: "Ctrl+Shift+A",
      run: other("The assistant"),
    },
    {
      id: "tui",
      icon: "tui",
      label: "Terminal workbench",
      shortcut: "Ctrl+Shift+T",
      run: other("The terminal workbench"),
    },
    {
      id: "docs",
      icon: "book",
      label: "Documentation",
      shortcut: "Ctrl+Shift+H",
      run: other("Documentation"),
    },
    {
      id: "profile",
      icon: "user",
      label: "Your profile",
      divided: true,
      run: other("Your profile"),
    },
    {
      id: "calendar",
      icon: "calendar",
      label: "Filing calendar",
      shortcut: "Ctrl+Shift+L",
      run: other("The filing calendar"),
    },
    {
      id: "ledger",
      icon: "ledger",
      label: "Ledger",
      pressed: true,
      run: () => {},
    },
    {
      id: "messages",
      icon: "mail",
      label: "AEAT notifications",
      run: other("AEAT notifications"),
    },
    {
      id: "aeat",
      icon: "office",
      label: "AEAT access",
      divided: true,
      run: other("AEAT access"),
    },
  ];
  const bottom: RailItem[] = [
    {
      id: "panel",
      icon: "console",
      label: "Panel",
      shortcut: "Ctrl+`",
      run: other("The panel"),
    },
    {
      id: "settings",
      icon: "settings",
      label: "Settings",
      shortcut: "Ctrl+,",
      run: other("Settings"),
    },
  ];
  const ref = useRef<HTMLDivElement>(null);
  if (hidden) return null;
  const btn = (it: RailItem) => (
    <Fragment key={it.id}>
      {it.divided ? (
        <span className="rail-sep" aria-hidden="true"></span>
      ) : null}
      <IconButton
        className="rail-btn"
        size="lg"
        side="right"
        icon={it.icon}
        iconSize="lg"
        label={it.label}
        shortcut={it.shortcut}
        aria-pressed={it.pressed}
        aria-current={it.pressed ? "page" : undefined}
        data-rail={it.id}
        onClick={it.run}
      />
    </Fragment>
  );
  return (
    <nav className="rail" aria-label="Areas">
      <div
        ref={ref}
        className="rail-inner"
        role="toolbar"
        aria-orientation="vertical"
        aria-label="Areas"
        onKeyDown={(e) => {
          const bs = [...(ref.current?.querySelectorAll("button") ?? [])];
          const i = bs.indexOf(document.activeElement as HTMLButtonElement);
          if (e.key === "ArrowDown") {
            e.preventDefault();
            bs[(i + 1) % bs.length]?.focus();
          }
          if (e.key === "ArrowUp") {
            e.preventDefault();
            bs[(i - 1 + bs.length) % bs.length]?.focus();
          }
        }}
      >
        <div className="rail-group">{top.map(btn)}</div>
        <div className="rail-group">{bottom.map(btn)}</div>
      </div>
    </nav>
  );
}

export const PRIMARY: [string, string][] = [
  ["movements", "Movements"],
  ["invoices", "Invoices"],
  ["documents", "Documents"],
];
export const SETUP: [string, string][] = [
  ["rules", "Rules"],
  ["registers", "Registers"],
  ["health", "Health"],
];
export const SECTION_LABEL: Record<string, string> = Object.fromEntries([
  ...PRIMARY,
  ...SETUP,
]);

type SheetState = { id: string | null; prefill?: InvoicePrefill };
export type PageStart = {
  section?: string;
  dialog?: DialogState;
  sheet?: SheetState;
  /** The movement and column the grid opens on, which the inspector follows. */
  focus?: { id: string; col: string };
  /** The inspector section that opens first. */
  inspectorAt?: string;
};

export function LedgerPage({
  registerShell,
  guardRef,
  pageHandle,
  maximized,
  setMaximized,
  start,
}: {
  registerShell: (actions: () => PaletteAction[]) => void;
  guardRef: RefObject<Guard>;
  pageHandle: RefObject<PageApi | null>;
  maximized: boolean;
  setMaximized: (next: boolean) => void;
  start?: PageStart;
}) {
  const [state, dispatch] = useStore();
  const toast = useToast();
  const narrow = useNarrow();
  const [section, setSectionState] = useState(start?.section ?? "movements");
  const [dialog, setDialog] = useState<DialogState | null>(
    start?.dialog ?? null,
  );
  const [sheet, setSheet] = useState<SheetState | null>(start?.sheet ?? null);
  const [setupMenu, setSetupMenu] = useState<HTMLElement | null>(null);
  const [rereading, setRereading] = useState(false);
  const [suggs, setSuggs] = useState<
    Record<string, (Suggestion & { digest?: string }) | null>
  >({});
  const [peekId, setPeekId] = useState<string | null>(null);
  const [inspTick, setInspTick] = useState(0);
  const [linkOffer, setLinkOffer] = useState<{
    rowId: string;
    inv: Invoice;
  } | null>(null);
  const [docFocus, setDocFocus] = useState<string | null>(null);
  const gridApi = useRef<GridApi | null>(null);
  const searchRef = useRef<HTMLInputElement | null>(null);
  const reg = useRef<Registered>({});
  const pageRef = useRef<Partial<PageApi>>({
    inspAt: start?.inspectorAt ?? null,
    startFocus: start?.focus
      ? { key: start.focus.id, col: start.focus.col }
      : undefined,
  });
  const ps = state.proto.state;
  const setSection = (s: string) => {
    setSectionState(s);
    setPeekId(null);
  };

  const suggestionFor = (row: Movement) =>
    suggs[row.id] === null ? null : suggs[row.id] || row.suggestion;
  const page: PageApi = Object.assign(pageRef.current, {
    gridApi,
    searchRef,
    toast,
    rereading,
    docFocus,
    peekId,
    inspTick,
    sheetInvoice: sheet?.id,
    get windowInfo() {
      return reg.current.windowInfo?.() || {};
    },
    register: (o: Registered) => Object.assign(reg.current, o),
    setSection,
    openDialog: <N extends DialogName>(
      name: N,
      ...args: [props?: DialogProps[N]]
    ) => setDialog({ name, props: args[0] } as DialogState),
    openAction: (type: LifecycleActionType, ids: string[], opts?: ActionOpts) =>
      setDialog({ name: "action", props: { type, ids, opts } }),
    visibleIds: () => reg.current.visibleIds?.() || [],
    focusGrid: () => reg.current.focusGrid?.(),
    focusFirstRow: () => reg.current.focusFirst?.(),
    /* ADV-25: a "Show" keeps the working view. A row outside it opens in
       the inspector with a Back chip instead of wiping filters. */
    jumpTo: (id: string, col?: string) => {
      const go = () => {
        if (reg.current.jumpTo?.(id, col)) {
          dispatch({ type: "SELECT", mode: "set", ids: [id] });
          setPeekId(null);
          return;
        }
        if (state.data.byId[id]) {
          setPeekId(id);
          dispatch({ type: "VIEW", patch: { inspector: true } });
          announce("Shown in the inspector: it is not in the current view");
        }
      };
      if (section !== "movements") {
        setSectionState("movements");
        setTimeout(go, 80);
      } else go();
    },
    setPeek: (id: string | null) => {
      setPeekId(id);
      if (!id) setTimeout(() => reg.current.focusGrid?.(), 0);
    },
    showInGrid: (id: string) => {
      const r = state.data.byId[id];
      if (!r) return;
      setPeekId(null);
      dispatch({
        type: "VIEW",
        patch: {
          period: {
            year: +effDate(r).slice(0, 4),
            code: quarterOf(effDate(r)) + "T",
          },
          filters: { ...EMPTY_FILTERS },
          search: "",
          savedView: "all",
          collapsed: {},
        },
      });
      setTimeout(() => {
        reg.current.jumpTo?.(id);
        dispatch({ type: "SELECT", mode: "set", ids: [id] });
      }, 90);
    },
    editCell: (id: string, field: string) => {
      if (!reg.current.startEdit?.(id, field))
        page.toast("Show the movement in the grid to edit that cell.");
    },
    openInvoice: (id: string) => {
      setSheet({ id });
    },
    newInvoiceFor: (row: Movement) => {
      setSheet({
        id: null,
        prefill: {
          kind:
            row.direction === "in"
              ? "issued"
              : row.direction === "out"
                ? "received"
                : "",
          counterparty: row.counterparty,
          date: effDate(row),
          amount: row.amount,
          currency: row.currency,
          description: row.description,
          rowId: row.id,
        },
      });
    },
    addInvoice: () => {
      setSheet({ id: null });
    },
    offerLink: (rowId: string, inv: Invoice) => setLinkOffer({ rowId, inv }),
    openDoc: (id: string) => {
      setDocFocus(id);
      setSection("documents");
    },
    copyRows: (ids: string[]) => {
      const cols = state.view.order.filter(
        (k) =>
          state.view.visible.includes(k) && k !== "select" && k !== "status",
      );
      const rows = ids
        .flatMap((id) => state.data.byId[id] ?? [])
        .map((r) => effective(r, state.staged.rows));
      const text = [
        cols.map((k) => COL_LABEL[k]).join("\t"),
        ...rows.map((r) =>
          cols
            .map((k) =>
              tsvEscape(
                k === "eur"
                  ? r.fx
                    ? canon(r.fx.eur)
                    : ""
                  : canonOf(k, getField(r, k)),
              ),
            )
            .join("\t"),
        ),
      ].join("\n");
      copyText(text);
      toast(
        `Copied ${plural(rows.length, "movement")} × ${cols.length} columns as TSV`,
      );
    },
    askModel: async (ids: string[], mode?: string) => {
      if (ps === "modelUnavailable") {
        toast("The local model is not available");
        return;
      }
      toast(`Asking the local model about ${plural(ids.length, "movement")}…`);
      await sleep(ids.length > 1 ? 1400 : 400);
      const add: Record<string, Suggestion & { digest?: string }> = {};
      ids.forEach((id) => {
        const r = state.data.byId[id];
        if (
          !r ||
          CLASSIFIED.has(r.cls) ||
          r.direction === "transfer" ||
          r.lifecycle !== "active"
        )
          return;
        add[id] = {
          ...guessSuggestion(r, mode),
          digest: hashHex("rv" + id + CLOCK, 12),
        };
      });
      setSuggs((s) => ({ ...s, ...add }));
      const got = Object.keys(add);
      if (ids.length > 1 && got.length)
        setDialog({ name: "suggestions", props: { ids: got } });
      else
        toast(
          got.length
            ? "A suggestion is ready in the inspector"
            : "Nothing to suggest: already classified, a transfer, or not active",
        );
    },
    dropSuggestion: (id: string) => setSuggs((s) => ({ ...s, [id]: null })),
    suggestionFor,
    startAdd: () => {
      setSection("movements");
      setTimeout(() => reg.current.startAdd?.(), 0);
    },
    /* M4: the one classify-selection command. Every route calls it. */
    hiddenSelected: () => {
      const vis = new Set(reg.current.visibleIds?.() || []);
      const sel = Object.keys(state.selection).filter(
        (id) => state.data.byId[id],
      );
      return { sel, hidden: sel.filter((id) => !vis.has(id)) };
    },
    classifySelection: (
      kind: string,
      idsArg?: string[],
      opts: { group?: boolean } = {},
    ) => {
      const sel =
        idsArg ||
        Object.keys(state.selection).filter((id) => state.data.byId[id]);
      if (!sel.length) {
        toast("Select movements first");
        return false;
      }
      if (!opts.group) {
        const vis = new Set(reg.current.visibleIds?.() || []);
        const hidden = sel.filter((id) => !vis.has(id));
        if (hidden.length) {
          toast(
            `${hidden.length} of ${sel.length} selected are hidden · Show them · Keep only visible`,
          );
          announce(`${hidden.length} of ${sel.length} selected are hidden`);
          return false;
        }
      }
      const rows = sel
        .flatMap((id) => state.data.byId[id] ?? [])
        .map((r) => effective(r, state.staged.rows, state.staged.actions));
      const ok = rows.filter(
        (r) =>
          !lockReason(r, "cls", false, state.staged.actions) &&
          !(r.direction === "transfer" && kind !== "personal"),
      );
      if (!ok.length) {
        toast(
          kind !== "personal" && rows.every((r) => r.direction === "transfer")
            ? "Transfers can only be Personal or stay unclassified"
            : "None of these can be classified: sealed or read-only",
        );
        return false;
      }
      const info = reg.current.windowInfo?.();
      const skipped = rows.length - ok.length;
      if (kind === "personal") {
        dispatch({
          type: "STAGE",
          changes: ok.flatMap((r) => [
            { id: r.id, field: "cls", value: "personal" },
            { id: r.id, field: "share", value: null },
          ]),
          label: "Classify as Personal",
        });
        toast(
          `Personal · ${plural(ok.length, "movement")} staged${skipped ? ` · ${skipped} skipped` : ""}`,
        );
        return true;
      }
      setDialog({
        name: "classify",
        props: {
          kind,
          ids: ok.map((r) => r.id),
          skipped,
          partial: info?.truncated ? info : null,
        },
      });
      return true;
    },
    altI: () => {
      const insp = document.querySelector(".inspector");
      if (!state.view.inspector || !insp) {
        dispatch({ type: "VIEW", patch: { inspector: true } });
        page.inspFocusIndex = true;
        setInspTick((t) => t + 1);
        return;
      }
      if (insp.contains(document.activeElement)) {
        dispatch({ type: "VIEW", patch: { inspector: false } });
        setPeekId(null);
        setTimeout(() => reg.current.focusGrid?.(), 0);
        return;
      }
      insp.querySelector<HTMLElement>(".insp-index button")?.focus();
    },
    toggleInspector: () => {
      if (state.view.inspector) {
        dispatch({ type: "VIEW", patch: { inspector: false } });
        setPeekId(null);
        setTimeout(() => reg.current.focusGrid?.(), 0);
      } else {
        dispatch({ type: "VIEW", patch: { inspector: true } });
        page.inspFocusIndex = true;
        setInspTick((t) => t + 1);
      }
    },
    openInspectorAt: (sec: string) => {
      dispatch({ type: "VIEW", patch: { inspector: true } });
      page.inspAt = sec;
      setInspTick((t) => t + 1);
    },
    showSelected: () => {
      dispatch({
        type: "VIEW",
        patch: {
          filters: { ...EMPTY_FILTERS },
          search: "",
          savedView: "all",
          period: { year: 2026, code: "ALL" },
          loaded: 100000,
          groupBy: "none",
        },
      });
      toast("Showing every period so the whole selection is visible");
    },
    stageArchiveDuplicate: (id: string) => {
      const r = state.data.byId[id];
      if (!r) return;
      dispatch({
        type: "STAGE_ACTION",
        action: {
          id: "archive-dup-" + id,
          type: "archive",
          rowIds: [id],
          label: `Archive as duplicate · ${r.description}`,
          tech: "ledger.archive · reason: duplicate import",
          payload: { reason: "Duplicate of a movement imported earlier" },
        },
      });
      toast("Archive staged · not saved");
    },
    stageKeepBoth: (id: string) => {
      const r = state.data.byId[id];
      if (!r) return;
      dispatch({
        type: "STAGE_ACTION",
        action: {
          id: "keep-" + id,
          type: "keepBoth",
          rowIds: [id],
          label: `Keep both · ${r.description}`,
          tech: "ledger.update · clears the possible-duplicate marker",
          payload: {},
        },
      });
      toast("Keep both staged · not saved");
    },
    reread: async () => {
      setRereading(true);
      await sleep(1300);
      setRereading(false);
      const had = state.paused;
      dispatch({ type: "REREAD" });
      dispatch({ type: "CHECK" });
      if (ps === "stale" || ps === "unknown")
        dispatch({ type: "PROTO", patch: { state: "normal" } });
      toast(
        had
          ? state.proto.unknownResolves === "saved"
            ? "Read again: the earlier change was saved. Writes resumed."
            : "Read again: the earlier change was not saved and is staged again. Writes resumed."
          : "Read the ledger again",
      );
    },
  });
  useEffect(() => {
    setDocFocus(null);
  }, [section]);

  // Leaving with staged work asks first (R11).
  pageHandle.current = page;
  guardRef.current = (what, proceed) => {
    if (trayCounts(state).total)
      setDialog({ name: "leave", props: { what, onLeave: proceed } });
    else proceed();
  };

  // The page's commands join the window's palette; the page binds no Ctrl+K.
  // Built when the palette opens, so reasons reflect the grid as it is then.
  useEffect(() => {
    registerShell(() =>
      paletteActions(state, dispatch, page, setSection, setDialog),
    );
  });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (isShellChord(e) || e.defaultPrevented) return;
      const t = e.target as HTMLElement;
      const typing =
        t.tagName === "INPUT" ||
        t.tagName === "TEXTAREA" ||
        t.tagName === "SELECT";
      if (document.querySelector(".dialog, .sheet, .palette")) return;
      // M2: Alt+I is handled once, here.
      if (chord(e, "i", { alt: true }) && section === "movements") {
        e.preventDefault();
        page.altI();
        return;
      }
      if (chord(e, "Enter", { ctrl: true })) {
        e.preventDefault();
        if (state.paused) toast("Writes are paused: re-read first");
        else if (trayCounts(state).total) setDialog({ name: "review" });
        else toast("Nothing to save");
        return;
      }
      if (typing) return;
      if (chord(e, "z", { ctrl: true })) {
        e.preventDefault();
        if (state.undo.length) {
          dispatch({ type: "UNDO" });
          toast(
            "Undone: " +
              state.undo[state.undo.length - 1]!.label +
              " · Ctrl+Shift+Z redoes it",
          );
        } else
          toast(
            state.appliedAt
              ? "Saved changes cannot be undone here. Edit the movement again to reverse one."
              : "Nothing to undo",
          );
        return;
      }
      if (
        chord(e, "z", { ctrl: true, shift: true }) ||
        chord(e, "y", { ctrl: true })
      ) {
        e.preventDefault();
        if (state.redo.length) {
          dispatch({ type: "REDO" });
          toast("Redone: " + state.redo[state.redo.length - 1]!.label);
        }
        return;
      }
      const inGrid = !!t.closest?.(".grid");
      if (!inGrid && chord(e, "/") && section === "movements") {
        e.preventDefault();
        searchRef.current?.focus();
        return;
      }
      if (!inGrid && e.key === "?" && !e.ctrlKey && !e.altKey) {
        e.preventDefault();
        setDialog({ name: "shortcuts" });
        return;
      }
      for (const [k, kind] of [
        ["b", "business"],
        ["p", "personal"],
        ["m", "mixed"],
      ] as const)
        if (chord(e, k, { alt: true }) && section === "movements") {
          e.preventDefault();
          page.classifySelection(kind);
          return;
        }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const inPer = (r: Movement) => inPeriod(effDate(r), state.view.period);
  const pending = Object.values(state.data.byId).filter(
    (r) =>
      r.lifecycle === "active" && reviewStatus(r) === "pending" && inPer(r),
  ).length;
  const docQueue = state.data.docs.filter(
    (d) => d.state === "draft" || d.state === "paused",
  ).length;
  const unmatched = state.data.invoices.filter((i) => !i.linked.length).length;
  const tabs = PRIMARY.map(([v, l]) => ({
    value: v,
    label: l,
    badge:
      v === "movements" && pending
        ? pending
        : v === "documents" && docQueue
          ? docQueue
          : v === "invoices" && unmatched
            ? unmatched
            : undefined,
    badgeLabel:
      v === "movements"
        ? `${pending} to classify in ${periodShort(state.view.period)}`
        : v === "documents"
          ? `${docQueue} to review`
          : `${unmatched} unmatched`,
  }));
  const p = state.view.period;
  const blocked = [
    "signedOut",
    "sessionLost",
    "unavailable",
    "locked",
    "neverCaptured",
    "loading",
  ].includes(ps);
  const inSetup = SETUP.some(([k]) => k === section);
  const lo = linkOffer ? state.data.byId[linkOffer.rowId] : undefined;
  const close = () => setDialog(null);
  return (
    <PageCtx.Provider value={page}>
      <section className="ledger" aria-label="Ledger">
        <div className="pane-head">
          <h2 className="pane-title">Ledger</h2>
          <div className="pane-head-slot">
            {narrow ? (
              <div style={{ width: "calc(var(--spacing) * 44)" }}>
                <Select
                  size="sm"
                  aria-label="Ledger section"
                  value={section}
                  onChange={(e) => setSection(e.target.value)}
                >
                  {PRIMARY.map(([k, l]) => (
                    <option key={k} value={k}>
                      {l}
                    </option>
                  ))}
                  <optgroup label="Setup">
                    {SETUP.map(([k, l]) => (
                      <option key={k} value={k}>
                        {l}
                      </option>
                    ))}
                  </optgroup>
                </Select>
              </div>
            ) : (
              <>
                <div className="scroll-x head-tabs" style={{ minWidth: 0 }}>
                  <Tabs
                    value={inSetup ? null : section}
                    onChange={setSection}
                    tabs={tabs}
                    label="Ledger sections"
                    idBase="sec"
                  />
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className={cx("setup-btn", inSetup && "on")}
                  aria-haspopup="menu"
                  aria-expanded={!!setupMenu}
                  aria-current={inSetup ? "page" : undefined}
                  iconRight="chevronDown"
                  onClick={(e) => setSetupMenu(e.currentTarget)}
                >
                  {inSetup ? `Setup · ${SECTION_LABEL[section]}` : "Setup"}
                </Button>
              </>
            )}
          </div>
          <div className="head-actions">
            {section === "movements" || section === "invoices" ? (
              <>
                <PeriodControl
                  label="Ledger period"
                  value={p}
                  onChange={(v) =>
                    dispatch({
                      type: "VIEW",
                      patch: {
                        period: v,
                        loaded: 250,
                        groupBy:
                          v.code === "ALL" && state.view.groupBy !== "group"
                            ? "none"
                            : state.view.groupBy,
                      },
                    })
                  }
                />
                <span className="vsep"></span>
              </>
            ) : null}
            <Button
              variant="ghost"
              size="sm"
              icon="upload"
              className="collapse-lbl"
              aria-label="Import"
              data-tip="Import"
              onClick={() => setDialog({ name: "import" })}
            >
              <span className="lbl">Import</span>
            </Button>
            <Button
              variant="ghost"
              size="sm"
              icon="download"
              className="collapse-lbl"
              aria-label="Export"
              data-tip="Export"
              onClick={() => setDialog({ name: "export" })}
            >
              <span className="lbl">Export</span>
            </Button>
            {section === "invoices" ? (
              <Button size="sm" icon="plus" onClick={() => page.addInvoice()}>
                <span className="lbl">Add invoice</span>
              </Button>
            ) : (
              <Button
                size="sm"
                icon="plus"
                disabled={blocked}
                aria-label="Add movement"
                onClick={() => page.startAdd()}
              >
                <span className="lbl">Add movement</span>
              </Button>
            )}
            <IconButton
              icon="keyboard"
              label="Keyboard shortcuts"
              shortcut="?"
              onClick={() => setDialog({ name: "shortcuts" })}
            />
            <IconButton
              icon={maximized ? "collapseAll" : "maximize"}
              label={maximized ? "Restore the pane" : "Maximize the pane"}
              aria-pressed={maximized}
              onClick={() => setMaximized(!maximized)}
            />
          </div>
        </div>
        {setupMenu ? (
          <Menu
            anchor={setupMenu}
            label="Setup"
            onClose={() => setSetupMenu(null)}
            items={SETUP.map(([k, l]) => ({
              label: l,
              checked: section === k,
              onSelect: () => setSection(k),
            }))}
          />
        ) : null}
        {lo ? (
          <div className="banner">
            <Alert
              icon="link"
              title={`Link ${linkOffer?.inv.number} to its movement?`}
            >
              {lo.description} · {fmtDateLong(effDate(lo))} ·{" "}
              {fmtMoney(lo.amount)}. A link is permanent once saved.
            </Alert>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                if (linkOffer)
                  stageLinkAction(dispatch, lo, linkOffer.inv, toast);
                setLinkOffer(null);
              }}
            >
              Link · permanent
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setLinkOffer(null)}
            >
              Not now
            </Button>
          </div>
        ) : null}
        <PageBody section={section} />
        <ChangesTray />
        {dialog?.name === "review" ? <ReviewDialog onClose={close} /> : null}
        {dialog?.name === "discard" ? <DiscardDialog onClose={close} /> : null}
        {dialog?.name === "leave" ? (
          <LeaveDialog {...dialog.props} onClose={close} />
        ) : null}
        {dialog?.name === "action" ? (
          <ActionDialog {...dialog.props} onClose={close} />
        ) : null}
        {dialog?.name === "import" ? <ImportDialog onClose={close} /> : null}
        {dialog?.name === "export" ? (
          <ExportDialog {...(dialog.props ?? {})} onClose={close} />
        ) : null}
        {dialog?.name === "shortcuts" ? (
          <ShortcutsDialog onClose={close} />
        ) : null}
        {dialog?.name === "paste" ? (
          <PasteDialog {...dialog.props} onClose={close} />
        ) : null}
        {dialog?.name === "rule" ? (
          <RuleDialog {...dialog.props} onClose={close} />
        ) : null}
        {dialog?.name === "columns" ? <ColumnsDialog onClose={close} /> : null}
        {dialog?.name === "suggestions" ? (
          <SuggestionsDialog {...dialog.props} onClose={close} />
        ) : null}
        {dialog?.name === "classify" ? (
          <ClassifyDialog {...dialog.props} onClose={close} />
        ) : null}
        {dialog?.name === "gridDemo" ? <GridDemo onClose={close} /> : null}
        {sheet ? (
          <InvoiceSheet
            key={sheet.id || "new"}
            id={sheet.id}
            prefill={sheet.prefill}
            onClose={() => setSheet(null)}
          />
        ) : null}
      </section>
    </PageCtx.Provider>
  );
}
export function PageBody({ section }: { section: string }) {
  const [state, dispatch] = useStore();
  const page = usePage();
  const ps = state.proto.state;
  if (ps === "loading")
    return (
      <div className="col" style={{ flex: 1, minHeight: 0 }}>
        <div className="strip">
          <span
            className="skeleton"
            style={{ width: "calc(var(--spacing) * 24)" }}
          ></span>
          <span
            className="skeleton"
            style={{ width: "calc(var(--spacing) * 32)" }}
          ></span>
          <span
            className="skeleton"
            style={{ width: "calc(var(--spacing) * 40)" }}
          ></span>
        </div>
        <div
          role="status"
          className="row g2 muted t-sm"
          style={{
            padding: "calc(var(--spacing) * 3) calc(var(--spacing) * 4)",
          }}
        >
          <Spinner />
          Reading the ledger for {periodShort(state.view.period)}…
        </div>
        <div
          className="col g3"
          style={{ padding: "0 calc(var(--spacing) * 4)" }}
          aria-hidden="true"
        >
          {Array.from({ length: 14 }, (_, i) => (
            <div key={i} className="row g4">
              <span
                className="skeleton"
                style={{ width: "calc(var(--spacing) * 16)" }}
              ></span>
              <span
                className="skeleton"
                style={{ width: 10 + ((i * 7) % 14) + "rem" }}
              ></span>
              <span
                className="skeleton"
                style={{ width: "calc(var(--spacing) * 32)" }}
              ></span>
              <span
                className="skeleton f1"
                style={{
                  maxWidth: "calc(var(--spacing) * 24)",
                  marginLeft: "auto",
                }}
              ></span>
            </div>
          ))}
        </div>
      </div>
    );
  if (ps === "signedOut" || ps === "sessionLost")
    return (
      <Empty
        icon="lock"
        title={
          ps === "signedOut"
            ? "Sign in to see your ledger"
            : "Your session ended"
        }
        desc={
          ps === "signedOut"
            ? "Nothing is shown until you sign in."
            : "This window's ledger data and unsaved changes were cleared."
        }
      >
        <Button
          onClick={() =>
            dispatch({ type: "PROTO", patch: { state: "normal" } })
          }
        >
          Sign in
        </Button>
      </Empty>
    );
  if (ps === "unavailable" || ps === "locked" || ps === "neverCaptured") {
    const m = {
      unavailable: [
        "The ledger could not be read",
        "Nothing is retried on its own.",
      ],
      locked: ["The ledger is locked", "Another window is resetting it."],
      neverCaptured: ["Nothing has been read yet", "Not read in this window."],
    }[ps];
    return (
      <Empty icon="unplug" title={m[0]} desc={m[1]}>
        <Button
          variant="outline"
          icon="sync"
          pending={page.rereading}
          onClick={async () => {
            await page.reread();
            dispatch({ type: "PROTO", patch: { state: "normal" } });
          }}
        >
          Retry
        </Button>
      </Empty>
    );
  }
  switch (section) {
    case "movements":
      return <MovementsSection />;
    case "invoices":
      return <InvoicesSection />;
    case "documents":
      return <DocumentsSection />;
    case "rules":
      return <RulesSection />;
    case "registers":
      return <RegistersSection />;
    default:
      return <HealthSection />;
  }
}
export function guessSuggestion(r: Movement, mode?: string) {
  const d = (r.description + " " + r.counterparty).toUpperCase();
  const pick = (
    cls: Cls,
    category: string | null,
    ivaCategory: string | null,
    confidence: number,
    reason: string,
    share?: number | null,
  ): Suggestion => ({
    cls,
    category: mode === "saturated" || category ? category : null,
    ivaCategory: mode === "classification" ? null : ivaCategory,
    confidence,
    reason,
    share,
  });
  if (/REPSOL|PLENOIL|GASOLIN/.test(d))
    return pick(
      "mixed",
      "vehiculo_combustible",
      "domestic_general",
      0.74,
      "Fuel for a vehicle you also use privately. No share is proposed: your ratio decides it.",
      null,
    );
  if (/AEAT|AGENCIA TRIBUTARIA/.test(d))
    return pick(
      "personal",
      null,
      null,
      0.62,
      "A tax settlement, not an expense. Consider excluding it from filing instead.",
    );
  if (
    /FARMACIA|IKEA|ZARA|MERCADONA|BIZUM|CAJERO|CONSUM|HORNO|CINES|GLOVO/.test(d)
  )
    return pick(
      "personal",
      null,
      null,
      0.81,
      "A personal purchase pattern; no business use recorded for this counterparty.",
    );
  if (/AMAZON|PAPELERIA|CORREOS/.test(d))
    return pick(
      "business",
      "material_oficina",
      "domestic_general",
      0.63,
      "Small office purchase; check the order before approving.",
    );
  if (/DOMESTIKA|UDEMY|CURSO/.test(d))
    return pick(
      "business",
      "formacion_profesional",
      "intra_community_service_acquisition_reverse_charge",
      0.57,
      "An online course related to your activity; a foreign supplier, so reverse charge may apply.",
    );
  if (/HARBOR|SWIFT/.test(d))
    return pick(
      "business",
      null,
      "operacion_no_sujeta",
      0.9,
      "A client payment from outside the EU for design services: not subject to Spanish IVA.",
    );
  return pick(
    "business",
    "suministros_cliente_directos",
    "domestic_general",
    0.52,
    "Low confidence: the description does not say what was bought.",
  );
}
export function paletteActions(
  state: State,
  dispatch: Dispatch<Action>,
  page: PageApi,
  setSection: (section: string) => void,
  setDialog: (dialog: DialogState) => void,
): PaletteAction[] {
  const c = trayCounts(state);
  const v = (patch: Partial<View>) => () => {
    setSection("movements");
    dispatch({ type: "VIEW", patch });
  };
  const prev = stepPeriod(
    state.view.period.code === "ALL"
      ? { year: 2026, code: "4T" }
      : state.view.period,
    -1,
  );
  const sel = Object.keys(state.selection).filter((id) => state.data.byId[id]);
  const hs = page.hiddenSelected ? page.hiddenSelected() : { sel, hidden: [] };
  const why = !sel.length
    ? "nothing selected"
    : hs.hidden.length
      ? `${hs.hidden.length} of ${sel.length} selected are hidden · Show them · Keep only visible`
      : null;
  const partial = page.windowInfo?.truncated ? " (loaded rows only)" : "";
  const classify = (cls: string) => () => page.classifySelection(cls);
  return [
    {
      id: "add",
      group: "Ledger page",
      label: "Add movement",
      icon: "plus",
      run: () => page.startAdd(),
    },
    {
      id: "import",
      group: "Ledger page",
      label: "Import…",
      icon: "upload",
      run: () => setDialog({ name: "import" }),
    },
    {
      id: "export",
      group: "Ledger page",
      label: "Export…",
      icon: "download",
      run: () => setDialog({ name: "export" }),
    },
    {
      id: "review",
      group: "Ledger page",
      label: "Review and save",
      icon: "check",
      shortcut: "Ctrl+Enter",
      disabled: !c.total
        ? "nothing to save"
        : state.paused
          ? "re-read first"
          : null,
      run: () => setDialog({ name: "review" }),
    },
    {
      id: "cls-b",
      group: "Ledger page",
      label: "Classify selection as Business…" + partial,
      icon: "tick",
      shortcut: "Alt+B",
      disabled: why,
      run: classify("business"),
    },
    {
      id: "cls-p",
      group: "Ledger page",
      label: "Classify selection as Personal" + partial,
      icon: "user",
      shortcut: "Alt+P",
      disabled: why,
      run: classify("personal"),
    },
    {
      id: "cls-m",
      group: "Ledger page",
      label: "Classify selection as Mixed…" + partial,
      icon: "scale",
      shortcut: "Alt+M",
      disabled: why,
      run: classify("mixed"),
    },
    {
      id: "undo",
      group: "Ledger page",
      label: "Undo",
      icon: "undo",
      shortcut: "Ctrl+Z",
      disabled: !state.undo.length ? "nothing to undo" : null,
      run: () => dispatch({ type: "UNDO" }),
    },
    {
      id: "redo",
      group: "Ledger page",
      label: "Redo",
      icon: "redo",
      shortcut: "Ctrl+Shift+Z",
      disabled: !state.redo.length ? "nothing to redo" : null,
      run: () => dispatch({ type: "REDO" }),
    },
    {
      id: "discard",
      group: "Ledger page",
      label: "Discard every unsaved change",
      icon: "erase",
      disabled: !c.total ? "nothing unsaved" : null,
      run: () => setDialog({ name: "discard" }),
    },
    {
      id: "reread",
      group: "Ledger page",
      label: "Read the ledger again",
      icon: "sync",
      run: page.reread,
    },
    {
      id: "goto-prev",
      group: "Ledger page",
      label: `Go to ${periodShort(prev)}`,
      icon: "calendar",
      run: v({ period: prev, loaded: 250 }),
    },
    {
      id: "goto",
      group: "Ledger page",
      label: "Go to a period",
      icon: "calendar",
      hidden: true,
      run: (period) => {
        if (period && typeof period !== "string") v({ period, loaded: 250 })();
      },
    },
    {
      id: "jump-id",
      group: "Ledger page",
      label: "Go to a movement by id",
      icon: "search",
      run: (arg) => {
        const prefix = String(arg ?? "");
        const r = Object.values(state.data.byId).find((x) =>
          x.id.startsWith(prefix),
        );
        if (r) page.jumpTo(r.id);
        else page.toast(`No movement id starts with ${prefix}`);
      },
    },
    ...[...PRIMARY, ...SETUP].map(([k, l]): PaletteAction => ({
      id: "sec-" + k,
      group: "Ledger page",
      label: `Show ${l}`,
      icon: "forward",
      run: () => setSection(k),
    })),
    ...Object.entries(SAVED_VIEWS).map(([k, s]): PaletteAction => ({
      id: "view-" + k,
      group: "Ledger page",
      label: `View: ${s.label}`,
      icon: "bookmark",
      run: v({
        savedView: k,
        filters: { ...EMPTY_FILTERS, ...s.filters },
        groupBy: s.groupBy || "none",
      }),
    })),
    ...Object.entries(GROUPS).map(([k, g]): PaletteAction => ({
      id: "group-" + k,
      group: "Ledger page",
      label:
        k === "none" ? "Remove grouping" : `Group by ${g.label.toLowerCase()}`,
      icon: "group",
      run: v({ groupBy: k, collapsed: {} }),
    })),
    {
      id: "cols",
      group: "Ledger page",
      label: "Columns and density…",
      icon: "columns",
      run: () => setDialog({ name: "columns" }),
    },
    {
      id: "insp",
      group: "Ledger page",
      label: state.view.inspector ? "Hide the inspector" : "Show the inspector",
      icon: "panelRight",
      shortcut: "Alt+I",
      run: () => {
        setSection("movements");
        page.toggleInspector();
      },
    },
    {
      id: "next-issue",
      group: "Ledger page",
      label: "Next readiness issue",
      icon: "alert",
      shortcut: "F8",
      run: () => page.toast("Press F8 in the grid"),
    },
    {
      id: "invoice",
      group: "Ledger page",
      label: "Add invoice",
      icon: "receipt",
      run: () => page.addInvoice(),
    },
    {
      id: "keys",
      group: "Ledger page",
      label: "Keyboard shortcuts",
      icon: "keyboard",
      shortcut: "?",
      run: () => setDialog({ name: "shortcuts" }),
    },
  ];
}
export const WINDOW_ACTIONS = (
  toast: (text: string) => void,
  guard: Guard,
): PaletteAction[] =>
  (
    [
      ["Open Settings", "settings", "Ctrl+,"],
      ["Open the filing calendar", "calendar", "Ctrl+Shift+L"],
      ["Open your profile", "user"],
      ["Open the assistant", "agent", "Ctrl+Shift+A"],
      ["Open AEAT notifications", "mail"],
    ] as [string, IconName, string?][]
  ).map(([l, i, s]) => ({
    id: "w-" + l,
    group: "Window",
    label: l,
    icon: i,
    shortcut: s,
    run: () =>
      guard(l.replace("Open", "Opening"), () =>
        toast(`${l.replace("Open ", "")}: another part of the shell`),
      ),
  }));

/* ── The grid primitive serving its second consumer (Modelo forms). ─── */
type DemoItem =
  | { key: string; kind: "heading"; height: number; title: string }
  | {
      key: string;
      kind: "row";
      box: string;
      label: string;
      value: number;
    };
export function GridDemo({ onClose }: { onClose: () => void }) {
  const api = useRef<GridApi | null>(null);
  const items = useMemo(() => {
    const out: DemoItem[] = [];
    let box = 1;
    for (let s = 1; s <= 24; s++) {
      out.push({
        key: "sec-" + s,
        kind: "heading",
        height: 44,
        title: `Section ${s} · ${["Régimen general", "Adquisiciones intracomunitarias", "Modificación de bases", "Resultado", "Prorrata", "Regularización bienes de inversión"][s % 6]!}`,
      });
      for (let i = 0; i < 18; i++) {
        out.push({
          key: "box-" + String(box).padStart(3, "0"),
          kind: "row",
          box: String(box).padStart(3, "0"),
          label: `Casilla ${String(box).padStart(3, "0")}`,
          value: ((box * 37) % 5000) * 100,
        });
        box++;
      }
    }
    return out;
  }, []);
  const [active, setActive] = useState<GridActive>({
    key: "box-001",
    col: "value",
  });
  const [vals, setVals] = useState<Record<string, number>>({});
  const [editing, setEditing] = useState<string | null>(null);
  const [jump, setJump] = useState("");
  const cols: GridColumn[] = [
    { key: "box", width: 80, header: "Box", sticky: true, lastSticky: true },
    { key: "label", width: 340, header: "Concept" },
    { key: "value", width: 160, header: "Value", num: true },
  ];
  return (
    <Dialog
      className="xwide"
      placement="top"
      onClose={onClose}
      title="Grid primitive, second consumer"
      desc={`The same data grid with Modelo-form rows: ${items.length} rows of two kinds, windowed. Enter edits a value in place; Esc cancels; Enter or Tab keeps it.`}
    >
      <div className="col g3">
        <div className="row g2">
          <Field label="Jump to box" className="f1">
            <Input
              size="sm"
              placeholder="e.g. 214"
              value={jump}
              onChange={(e) => setJump(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  const k = "box-" + jump.padStart(3, "0");
                  if (!api.current?.jumpTo(k, "value")) setJump("");
                }
              }}
            />
          </Field>
        </div>
        <div className="demo-grid">
          <DataGrid
            items={items}
            columns={cols}
            rowHeight={32}
            label="Modelo 390 sample"
            apiRef={api}
            active={active}
            editing={!!editing}
            onActive={(key, col) => setActive({ key, col: col || "value" })}
            onKeyDown={(e, { item }) => {
              if (
                item?.kind === "row" &&
                (e.key === "Enter" || e.key === "F2")
              ) {
                e.preventDefault();
                setEditing(item.key);
                return true;
              }
              return false;
            }}
            renderCell={(it, c) =>
              it.kind !== "row" ? null : c.key === "value" ? (
                editing === it.key ? (
                  <div className="g-editor">
                    <input
                      autoFocus
                      aria-label={it.label}
                      className="num"
                      defaultValue={canon(vals[it.key] ?? it.value)}
                      onKeyDown={(e) => {
                        e.stopPropagation();
                        if (e.key === "Escape") {
                          setEditing(null);
                          api.current?.focus();
                        }
                        if (e.key === "Enter" || e.key === "Tab") {
                          e.preventDefault();
                          const field = e.currentTarget;
                          const r = parseAmount(field.value);
                          if (r.error) {
                            field.setAttribute("aria-invalid", "true");
                            field.title = r.error;
                            return;
                          }
                          setVals({ ...vals, [it.key]: Number(r.value) });
                          setEditing(null);
                          const i = items.findIndex((x) => x.key === it.key);
                          const n = items
                            .slice(i + 1)
                            .find((x) => x.kind === "row");
                          if (n) api.current?.jumpTo(n.key, "value");
                        }
                      }}
                    />
                  </div>
                ) : (
                  <span className={cx("v tnum", vals[it.key] != null && "fw5")}>
                    {fmtMoney(vals[it.key] ?? it.value)}
                  </span>
                )
              ) : c.key === "box" ? (
                <span className="mono t-sm">{it.box}</span>
              ) : (
                <span className="v">{it.label}</span>
              )
            }
            renderFull={(it) =>
              it.kind === "heading" ? (
                <div className="demo-heading">
                  <b className="fw6">{it.title}</b>
                </div>
              ) : null
            }
          />
        </div>
        <p className="t-xs muted">
          The primitive takes rows keyed by a stable id, each with its own
          height and kind, a render function per cell or per full row, roving
          focus and a jumpTo(key) API. Nothing in it names a ledger or a Modelo
          concept.
        </p>
      </div>
    </Dialog>
  );
}

/* ── Prototype controls, outside the product. ────────────────────────── */
export const PROTO_STATES: [string, string][] = [
  ["normal", "Normal"],
  ["firstRun", "First run"],
  ["loading", "Loading"],
  ["empty", "Empty period"],
  ["signedOut", "Not signed in"],
  ["sessionLost", "Session lost"],
  ["unavailable", "Ledger unavailable"],
  ["locked", "Locked"],
  ["neverCaptured", "Never read"],
  ["stale", "Stale"],
  ["partial", "Partial window"],
  ["unknown", "Outcome unknown"],
  ["modelUnavailable", "Model unavailable"],
  ["noRate", "No exchange rate"],
  ["unmeasured", "Not measured"],
  ["staged", "Staged changes"],
];

/* What each of the prototype's state buttons does to the page, as the
   reducer actions it dispatches. A button that needs a movement to be
   shown also names the cell to reveal. */
export function protoActions(
  k: string,
  state: State,
): { actions: Action[]; focus?: { id: string; col: string } } {
  const rows = state.data.order.flatMap((id) => state.data.byId[id] ?? []);
  const actions: Action[] = [];
  const normal: Action = { type: "PROTO", patch: { state: "normal" } };
  if (!rows.length && k !== "firstRun") {
    actions.push({ type: "RESET_ALL" });
    if (k === "normal") return { actions };
  }
  if (k === "firstRun") {
    return { actions: [normal, { type: "FIRST_RUN" }] };
  }
  if (k === "empty") {
    return {
      actions: [
        ...actions,
        normal,
        { type: "VIEW", patch: { period: { year: 2025, code: "3T" } } },
      ],
    };
  }
  if (k === "partial") {
    return {
      actions: [
        ...actions,
        normal,
        {
          type: "VIEW",
          patch: {
            period: { year: 2026, code: "ALL" },
            loaded: 250,
            groupBy: "none",
          },
        },
      ],
    };
  }
  if (k === "noRate") {
    const r = rows.find((x) => x.fxMissing);
    if (!r) return { actions };
    return {
      actions: [
        ...actions,
        normal,
        {
          type: "VIEW",
          patch: {
            period: { year: 2026, code: "4T" },
            inspector: true,
            filters: { ...EMPTY_FILTERS },
            search: "",
            preset: "review",
            visible: PRESETS.review!.cols,
          },
        },
        { type: "SELECT", mode: "set", ids: [r.id] },
      ],
      focus: { id: r.id, col: "eur" },
    };
  }
  if (k === "unknown") {
    const r = rows.find(
      (x) =>
        x.counterparty.startsWith("Repsol") && effDate(x).startsWith("2026-10"),
    );
    if (!r) return { actions };
    return {
      actions: [
        ...actions,
        { type: "VIEW", patch: { period: { year: 2026, code: "4T" } } },
        {
          type: "STAGE",
          changes: [
            {
              id: r.id,
              field: "description",
              value: r.description + " (DIESEL)",
            },
          ],
          label: "Edit description",
        },
        {
          type: "OUTCOME",
          id: r.id,
          status: "unknown",
          msg: "No answer came back. It may or may not have been saved; re-read before writing again.",
          label: `Correction · ${r.description}`,
        },
        { type: "PROTO", patch: { state: "unknown" } },
      ],
    };
  }
  if (k === "staged") {
    return {
      actions: [
        ...actions,
        normal,
        { type: "VIEW", patch: { period: { year: 2026, code: "4T" } } },
        ...seedStaged(state),
      ],
    };
  }
  if (k === "signedOut" || k === "sessionLost")
    actions.push({ type: "DISCARD" });
  actions.push({ type: "PROTO", patch: { state: k } });
  return { actions };
}

export function ProtoPanel({
  pageHandle,
}: {
  pageHandle: RefObject<PageApi | null>;
}) {
  const [state, dispatch] = useStore();
  const [open, setOpen] = useState(true);
  const [locale, setLocale] = useState(PREFS.locale);
  const choose = (k: string) => {
    const { actions, focus } = protoActions(k, state);
    actions.forEach(dispatch);
    if (focus)
      setTimeout(() => pageHandle.current?.jumpTo(focus.id, focus.col), 80);
  };
  if (!open)
    return (
      <div className="proto closed">
        <Button
          variant="outline"
          size="sm"
          icon="settings"
          onClick={() => setOpen(true)}
        >
          Prototype states
        </Button>
      </div>
    );
  return (
    <aside
      className="proto"
      aria-label="Prototype controls (not part of the product)"
    >
      <div className="proto-title">
        <span className="f1">Prototype controls</span>
        <IconButton
          icon="close"
          label="Collapse prototype controls"
          onClick={() => setOpen(false)}
        />
      </div>
      <p className="t-xs muted proto-note">
        Outside the product chrome. Synthetic data only. Appearance is the
        toolbar's here and Settings' in the product.
      </p>
      <div className="proto-states" role="group" aria-label="States">
        {PROTO_STATES.map(([k, l]) => (
          <button
            key={k}
            type="button"
            className="btn ghost"
            aria-pressed={state.proto.state === k}
            onClick={() => choose(k)}
          >
            {l}
          </button>
        ))}
      </div>
      <div className="col g1">
        <span className="t-xs muted">How a save answers</span>
        <Select
          size="sm"
          aria-label="How a save answers"
          value={state.proto.outcome}
          onChange={(e) =>
            dispatch({ type: "PROTO", patch: { outcome: e.target.value } })
          }
        >
          <option value="mix">A realistic mix</option>
          <option value="ok">Everything saved</option>
          <option value="batchRefused">A part refused as a whole</option>
          <option value="batchUnknown">A part with no answer</option>
        </Select>
      </div>
      <div className="col g1">
        <span className="t-xs muted">An unknown outcome turns out</span>
        <Seg
          size="sm"
          label="An unknown outcome turns out"
          value={state.proto.unknownResolves}
          onChange={(v) =>
            dispatch({ type: "PROTO", patch: { unknownResolves: v } })
          }
          options={[
            { value: "saved", label: "Saved" },
            { value: "notSaved", label: "Not saved" },
          ]}
        />
      </div>
      <div className="col g1">
        <span className="t-xs muted">
          Number display (input stays canonical)
        </span>
        <Seg
          size="sm"
          label="Number display"
          value={locale}
          onChange={(v) => {
            PREFS.locale = v;
            setLocale(v);
            dispatch({ type: "VIEW", patch: {} });
          }}
          options={[
            { value: "en-GB", label: "1,234.50" },
            { value: "es-ES", label: "1.234,50" },
          ]}
        />
      </div>
      <div className="row g1 wrap">
        <Button
          size="xs"
          variant="outline"
          onClick={() => {
            setOpen(false);
            pageHandle.current?.openDialog("gridDemo");
          }}
        >
          Grid primitive demo
        </Button>
        <Button
          size="xs"
          variant="ghost"
          onClick={() => dispatch({ type: "RESET_ALL" })}
        >
          Reset data
        </Button>
      </div>
    </aside>
  );
}

/* A ready-made batch of staged edits, for walking through review. */
export function seedStaged(state: State): Action[] {
  const rows = state.data.order
    .flatMap((id) => state.data.byId[id] ?? [])
    .filter(
      (r) =>
        r.lifecycle === "active" && effDate(r) >= "2026-10-01" && !r.sealed,
    );
  const pend = rows.filter(
    (r) => r.cls === "pending" && r.direction !== "transfer",
  );
  const ch: StageChange[] = [];
  pend
    .filter(
      (r) =>
        r.counterparty.startsWith("Espacio") ||
        r.counterparty.startsWith("Arroyo") ||
        r.counterparty.startsWith("N26") ||
        r.counterparty.startsWith("Sanitas"),
    )
    .forEach((r) => ch.push({ id: r.id, field: "cls", value: "business" }));
  const aws = pend.find((r) => r.counterparty.startsWith("Amazon Web"));
  if (aws)
    ch.push({ id: aws.id, field: "category", value: "software_suscripcion" });
  const rep = pend.find((r) => r.counterparty.startsWith("Repsol"));
  if (rep)
    ch.push(
      { id: rep.id, field: "cls", value: "mixed" },
      { id: rep.id, field: "share", value: 0.5 },
      { id: rep.id, field: "category", value: "vehiculo_combustible" },
      { id: rep.id, field: "base", value: Math.round(rep.amount / 1.21) },
      { id: rep.id, field: "ivaRate", value: 0.21 },
      {
        id: rep.id,
        field: "ivaAmount",
        value: rep.amount - Math.round(rep.amount / 1.21) + 1,
      },
    );
  const ik = pend.find((r) => r.counterparty.startsWith("Ikea"));
  if (ik)
    ch.push({ id: ik.id, field: "category", value: "mobiliario_amortizable" });
  const ren = rows.find((r) => r.counterparty.startsWith("Renfe"));
  if (ren)
    ch.push(
      {
        id: ren.id,
        field: "description",
        value: "RENFE AVE VALENCIA-MADRID REUNION ATALAYA",
      },
      { id: ren.id, field: "group", value: "Atalaya catalogue" },
    );
  const vod = pend.find((r) => r.counterparty.startsWith("Vodafone"));
  if (vod)
    ch.push({
      id: vod.id,
      field: "counterparty",
      value: "Vodafone España SAU (línea trabajo)",
    });
  return [
    { type: "STAGE", changes: ch, label: "Sample edits" },
    {
      type: "ADD_DRAFT",
      fields: {
        date: "2026-10-22",
        description: "EFECTIVO PARKING FERIA DISEÑO",
        amount: 1200,
        direction: "out",
        counterparty: "Feria Valencia",
        cls: "business",
        category: "vehiculo_parking",
      },
    },
  ];
}

/** How a story starts the prototype: what happens to the page before it is
 * first drawn, and where it opens. */
export type Scenario = {
  /** Reducer actions applied to the fresh page, chosen from what it holds. */
  prepare?: (state: State) => Action[];
  /** The section, dialog or sheet the page opens on. */
  start?: (state: State) => PageStart;
  /** The window's title bar and rail around the page. */
  chrome?: boolean;
  /** The prototype's own state controls. */
  controls?: boolean;
};

function build(scenario: Scenario) {
  PREFS.locale = "en-GB";
  const fresh = initState();
  const state = (scenario.prepare?.(fresh) ?? []).reduce(reducer, fresh);
  return { state, start: scenario.start?.(state) };
}

const SHELL_NAV: Record<string, string> = {
  "Control+,": "Settings",
  "Control+Shift+l": "the filing calendar",
  "Control+Shift+t": "the terminal workbench",
  "Control+Shift+h": "the documentation",
};
const SHELL_SIDE: Record<string, string> = {
  "Control+Shift+a": "The assistant",
  "Control+`": "The panel",
};

/** The ledger editor prototype: the Ledger page over synthetic data, every
 * write simulated in memory. */
export function LedgerPrototype({ scenario = {} }: { scenario?: Scenario }) {
  const seed = useMemo(() => build(scenario), [scenario]);
  const [state, dispatch] = useReducer(reducer, seed.state);
  const [root, setRoot] = useState<HTMLDivElement | null>(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [maximized, setMaximized] = useState(false);
  const shellActions = useRef<() => PaletteAction[]>(() => []);
  const toastRef = useRef<((text: string) => void) | null>(null);
  const guardRef = useRef<Guard>((_what, proceed) => proceed());
  const pageHandle = useRef<PageApi | null>(null);
  // Width bands are attributes of the root: a style rule cannot read a token
  // in a media condition.
  const wide = useMedia("(min-width: 90rem)");
  const compact = useMedia("(max-width: 90rem)");
  const narrow = useMedia("(max-width: 47.5rem)");
  const tiny = useMedia("(max-width: 30rem)");
  // Ctrl+K is the window's: the palette lists the page's commands with its own.
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if (chord(e, "k", { ctrl: true })) {
        e.preventDefault();
        setPaletteOpen(true);
        return;
      }
      const key = e.key.length === 1 ? e.key.toLowerCase() : e.key;
      const name = [
        (e.ctrlKey || e.metaKey) && "Control",
        e.shiftKey && "Shift",
        key,
      ]
        .filter(Boolean)
        .join("+");
      const nav = SHELL_NAV[name];
      const side = SHELL_SIDE[name];
      if (nav)
        guardRef.current(`Opening ${nav}`, () =>
          toastRef.current?.(
            `${nav.slice(0, 1).toUpperCase() + nav.slice(1)}: another part of the shell`,
          ),
        );
      else if (side)
        toastRef.current?.(`${side} opens beside the page (shell)`);
    };
    window.addEventListener("keydown", k, true);
    return () => window.removeEventListener("keydown", k, true);
  }, []);
  const signedIn = !(
    state.proto.state === "signedOut" || state.proto.state === "sessionLost"
  );
  const guard: Guard = (what, proceed) => guardRef.current(what, proceed);
  const page = (
    <LedgerPage
      registerShell={(actions) => (shellActions.current = actions)}
      guardRef={guardRef}
      pageHandle={pageHandle}
      maximized={maximized}
      setMaximized={setMaximized}
      start={seed.start}
    />
  );
  return (
    <div
      className="ledger-proto"
      ref={setRoot}
      data-wide={wide || undefined}
      data-compact={compact || undefined}
      data-narrow={narrow || undefined}
      data-tiny={tiny || undefined}
    >
      <OverlayCtx.Provider value={root}>
        <StoreCtx.Provider value={[state, dispatch]}>
          <ToastHost>
            <ShellToast
              guard={guard}
              paletteOpen={paletteOpen}
              setPaletteOpen={setPaletteOpen}
              shellActions={shellActions}
              toastRef={toastRef}
            >
              {scenario.chrome ? (
                <div className="window">
                  <Titlebar signedIn={signedIn} guard={guard} />
                  <div className="shell">
                    <Rail
                      onPalette={() => setPaletteOpen(true)}
                      guard={guard}
                      hidden={maximized}
                    />
                    <main className="main">
                      <div className="pane">{page}</div>
                    </main>
                  </div>
                </div>
              ) : (
                <main className="main">
                  <div className="pane">{page}</div>
                </main>
              )}
              {scenario.controls ? (
                <ProtoPanel pageHandle={pageHandle} />
              ) : null}
              <TooltipLayer />
              <LiveRegion />
            </ShellToast>
          </ToastHost>
        </StoreCtx.Provider>
      </OverlayCtx.Provider>
    </div>
  );
}

/* The shell's palette, with the toast available to its window commands. */
function ShellToast({
  children,
  guard,
  paletteOpen,
  setPaletteOpen,
  shellActions,
  toastRef,
}: {
  children: ReactNode;
  guard: Guard;
  paletteOpen: boolean;
  setPaletteOpen: (open: boolean) => void;
  shellActions: RefObject<() => PaletteAction[]>;
  toastRef: RefObject<((text: string) => void) | null>;
}) {
  const toast = useToast();
  toastRef.current = toast;
  return (
    <Fragment>
      {children}
      {paletteOpen ? (
        <Palette
          actions={(() => {
            const acts = shellActions.current();
            return [
              ...acts.filter((a) => !a.hidden),
              ...acts.filter((a) => a.hidden),
              ...WINDOW_ACTIONS(toast, guard),
            ];
          })()}
          onClose={() => setPaletteOpen(false)}
        />
      ) : null}
    </Fragment>
  );
}
