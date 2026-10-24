import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type RefObject,
} from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type { DataGridHandle, GridRow } from "@/components/ui/data-grid";
import { exactly } from "@/components/ui/dataGridModel";
import { EmptyState } from "@/components/ui/empty";
import { Icon } from "@/components/ui/icon";
import { Toast } from "@/components/ui/toast";
import { ContextMenu, type MenuAnchor } from "../../ContextMenu";
import type { ContextMenuItem } from "../../../ipc/contract";
import type { Action } from "../../../shell/actions";
import type { LedgerView } from "../../../shell/layout";
import type { LedgerPort, LedgerRow } from "../../../shell/ledger";
import {
  CLASSIFY_KINDS,
  categoryCells,
  classifyAvailability,
  classifyCells,
  type ClassifyBlock,
  type ClassifyKind,
} from "../../../shell/ledgerCommands";
import { parsePercent, type LedgerPeriod } from "../../../shell/ledgerGrammar";
import {
  useLedgerMembership,
  useOwnAccounts,
  useSearchElsewhere,
} from "../../../shell/ledgerMovementReads";
import {
  stagedMovements,
  type DraftField,
  type StageEvent,
  type StageState,
} from "../../../shell/ledgerStage";
import {
  readinessSnapshot,
  shownRows,
  windowComplete,
  type LedgerWindow,
  type Readiness,
} from "../../../shell/ledgerWindow";
import { useStrings, type Translate } from "../../../shell/strings";
import { dateFormats } from "../../../shared/dateFormats";
import { draftRow, stageTally } from "../editing/editingModel";
import { useMovementEditing } from "../editing/MovementEditing";
import { periodText } from "../ledgerWords";
import { ClassifyDialog } from "./ClassifyDialog";
import { MovementsGrid } from "./MovementsGrid";
import {
  COLUMN_SPECS,
  DEFAULT_SORT,
  NO_FILTERS,
  REASON_FIX,
  SERVER_GROUPING,
  columnLayout,
  currencySums,
  groupRows,
  groupValue,
  keepsRow,
  matchesSearch,
  presetHidden,
  readinessSets,
  searchTerms,
  serverFilters,
  serverSortField,
  shownColumns,
  sortRows,
  type ColumnId,
  type CurrencySum,
  type GroupingId,
  type MovementFilters,
  type ReadinessFilter,
  type SortLabels,
} from "./movementsModel";
import { MovementsToolbar } from "./MovementsToolbar";
import { monthNames } from "../ledgerWords";
import {
  accountLabel,
  amountText,
  categoryLabel,
  classificationLabel,
  classificationText,
  classifiedByLabel,
  directionLabel,
  familyLabel,
  irpfCategoryLabel,
  ivaCategoryLabel,
  lifecycleLabel,
  reasonDetail,
  statusLabel,
  statusWord,
} from "./movementWords";
import { ReadinessStrip } from "./ReadinessStrip";
import type { MovementsView } from "./useMovementsView";
import type { ImportedBatches } from "../../../shell/ledgerImports";
import type { SpendingCategoryFamily } from "../../../shell/ledgerVocabulary";

/** How long a confirmation stays on screen. */
const TOAST_MS = 4000;

const idOf = (row: LedgerRow) => row.transaction.transaction_id;

/** A classification dialog asked for, and what it would act on. */
type Asking = {
  kind: "business" | "mixed" | "category";
  ids: string[];
  skipped: number;
  partial: boolean;
  error: string | null;
  /** A new movement's classification, filled in rather than staged. */
  draft?: string;
};

/** What staged editing on the section needs from the page. */
export type SectionEditing = {
  openReview: () => void;
  /** A new movement to focus once it is drawn. */
  focusDraft: string | null;
  onDraftFocused: () => void;
  /** Movements a finalized declaration cites, where the page knows. */
  sealed?: ReadonlySet<string>;
};
const NO_SEALED: ReadonlySet<string> = new Set();

function blockText(t: Translate, block: ClassifyBlock): string {
  switch (block.kind) {
    case "nothing_selected":
      return t("desktop.ledger.classify.nothing");
    case "hidden":
      return t("desktop.ledger.selection.hidden", {
        hidden: block.hidden,
        selected: block.selected,
      });
    case "transfers_only":
      return t("desktop.ledger.classify.transfers_only");
    case "inactive_only":
      return t("desktop.ledger.classify.inactive_only");
  }
}

function SumLine({ sums, locale }: { sums: CurrencySum[]; locale: string }) {
  const t = useStrings();
  return (
    <span className="flex flex-wrap items-center gap-x-3 tabular-nums">
      {sums.map((sum) => (
        <span key={sum.currency} className="flex items-center gap-2">
          {sum.currency !== "EUR" && (
            <span className="text-xs">{sum.currency}</span>
          )}
          {(
            [
              ["incoming", "desktop.ledger.sum.in"],
              ["outgoing", "desktop.ledger.sum.out"],
              ["transfer", "desktop.ledger.sum.transfer"],
            ] as const
          ).map(([side, key]) =>
            sum[side] === null ? null : (
              <span key={side}>
                {t(key, { amount: amountText(locale, sum[side]) })}
              </span>
            ),
          )}
        </span>
      ))}
    </span>
  );
}

/** What a group header's buttons do: set by the section after each render,
 * read when one is pressed. */
type GroupCommands = {
  classify: (kind: ClassifyKind, ids: readonly string[]) => void;
  category: (ids: string[]) => void;
  select: (ids: string[]) => void;
};

/** A group header's quick actions, which act on the group's movements
 * through the page's one classify command. */
function GroupActions({
  ids,
  transfers,
  commands,
}: {
  ids: string[];
  transfers: boolean;
  commands: RefObject<GroupCommands>;
}) {
  const t = useStrings();
  const button = (label: string, run: () => void, held?: string) => (
    <Button
      variant="ghost"
      size="xs"
      tabIndex={-1}
      aria-disabled={held ? true : undefined}
      aria-label={held ? `${label}, ${held}` : undefined}
      onClick={(event) => {
        event.stopPropagation();
        if (!held) run();
      }}
      onDoubleClick={(event) => event.stopPropagation()}
    >
      {label}
    </Button>
  );
  const transferNote = transfers
    ? t("desktop.ledger.classify.transfers_only")
    : undefined;
  return (
    <span className="ledger-group-actions flex items-center gap-0.5">
      {button(
        t("desktop.ledger.group.business"),
        () => commands.current.classify("business", ids),
        transferNote,
      )}
      {button(t("desktop.ledger.group.personal"), () =>
        commands.current.classify("personal", ids),
      )}
      {button(
        t("desktop.ledger.group.mixed"),
        () => commands.current.classify("mixed", ids),
        transferNote,
      )}
      {button(t("desktop.ledger.group.category"), () =>
        commands.current.category(ids),
      )}
      {button(t("desktop.ledger.group.select", { count: ids.length }), () =>
        commands.current.select(ids),
      )}
    </span>
  );
}

/** A group's name: the label of what it groups by, or what it lacks. */
function groupLabelOf(
  t: Translate,
  locale: string,
  by: GroupingId,
  value: string,
  first: LedgerRow,
): string {
  if (value === "") return t(`desktop.ledger.group.empty.${by}`);
  switch (by) {
    case "category":
      return categoryLabel(t, value);
    case "category_family":
      return familyLabel(t, value as SpendingCategoryFamily);
    case "classification":
      return classificationLabel(t, value);
    case "status":
      return t(`desktop.ledger.review.${value}`);
    case "direction":
      return directionLabel(t, value);
    case "month": {
      const [year, month] = value.split("-").map(Number);
      const date = new Date(2000, (month ?? 1) - 1, 1);
      date.setFullYear(year ?? 2000);
      return dateFormats(locale).month.format(date);
    }
    case "iva_category":
      return ivaCategoryLabel(t, value);
    case "counterparty":
      return first.transaction.counterparty.trim();
    default:
      return value;
  }
}

/** The account grouping's labels come from the register, read once. */
function accountGroupLabel(
  t: Translate,
  accounts: readonly { id: string; label: string }[] | null,
  value: string,
): string {
  return accountLabel(t, accounts, value === "" ? null : value);
}

/**
 * The Movements section: the readiness strip, the toolbar and the grid of
 * a period's movements, as stored. Filters, search, sort and groups refine
 * a window read whole; a window read in part is filtered and sorted by the
 * product, and says how much of it is loaded. Classifying goes through the
 * page's one classify command and stages changes; nothing here saves.
 */
export function MovementsSection({
  port,
  reader,
  period,
  periodWindow,
  readAll,
  readiness,
  movements,
  stage,
  onStage,
  view,
  onViewChange,
  locale,
  onPeriod,
  onOpenInspector,
  register,
  shownImport,
  onImportCleared,
  editing: pageEditing,
}: {
  port: LedgerPort;
  reader: string;
  period: LedgerPeriod | null;
  periodWindow: LedgerWindow;
  readAll: () => void;
  readiness: Readiness;
  movements: MovementsView;
  stage: StageState;
  onStage: (event: StageEvent) => void;
  view: LedgerView;
  onViewChange: (update: (current: LedgerView) => LedgerView) => void;
  locale: string;
  /** Shows another period, as a search's other-period hint does. */
  onPeriod: (period: LedgerPeriod | null) => void;
  /** Opens the movement inspector on one of its sections, where the page
   * has one. */
  onOpenInspector?: (section: "classify") => void;
  /** Hands the page's palette what the section offers. */
  register: (actions: (() => Action[]) | null) => void;
  /** An import's movements, which the grid shows when asked. */
  shownImport: ImportedBatches | null;
  /** The person took the import's filter off. */
  onImportCleared?: () => void;
  editing: SectionEditing;
}) {
  const t = useStrings();
  const grid = useRef<DataGridHandle>(null);
  const numbers = useMemo(() => new Intl.NumberFormat(locale), [locale]);
  const {
    filters,
    setFilters: replaceFilters,
    search,
    setSearch,
    sort,
    setSort,
    collapsed,
    setCollapsed,
    selection,
    setSelection,
    savedView,
    chooseView,
    groupBy,
    setGroupBy,
  } = movements;
  // Taking the import's filter off says the import is no longer shown.
  const setFilters = (next: MovementFilters) => {
    if (filters.importBatches.length && !next.importBatches.length)
      onImportCleared?.();
    replaceFilters(next);
  };

  const held = shownRows(periodWindow) ?? { rows: [], total: 0 };
  const rows = held.rows;
  const partial = rows.length < held.total;
  const complete = windowComplete(periodWindow) && !partial;
  const allPeriods = period === null;
  const byId = useMemo(
    () => new Map(rows.map((row) => [idOf(row), row])),
    [rows],
  );
  const snapshot = readinessSnapshot(readiness);
  const sets = useMemo(() => readinessSets(rows, snapshot), [rows, snapshot]);

  // The product's own filters: in the window's read where one read says
  // them, otherwise as reads of the movements they keep.
  const scopes = serverFilters(filters);
  const inWindow = allPeriods && scopes.length === 1;
  const membership = useLedgerMembership(
    port,
    reader,
    period,
    inWindow ? [] : scopes,
    periodWindow.phase === "ready" ? periodWindow.generation : null,
  );
  const members = useMemo(
    () =>
      membership.kind === "ready"
        ? membership.ids
        : membership.kind === "none"
          ? null
          : new Set<string>(),
    [membership],
  );
  const [wantAccounts, setWantAccounts] = useState(false);
  const accountsShown =
    shownColumns(columnLayout(view.columns)).includes("account") ||
    groupBy === "account" ||
    stage.content.drafts.length > 0;
  const accounts = useOwnAccounts(
    port,
    reader,
    wantAccounts || filters.account !== null || accountsShown,
  );
  const elsewhere = useSearchElsewhere(port, reader, period, search);

  // ---- What is shown ---------------------------------------------------------
  const labels = useMemo<SortLabels>(
    () => ({
      category: (id) => categoryLabel(t, id),
      ivaCategory: (id) => ivaCategoryLabel(t, id),
      irpfCategory: (id) => irpfCategoryLabel(t, id),
      classification: (row) => classificationText(t, row.transaction),
      direction: (direction) => directionLabel(t, direction),
      lifecycle: (state) => lifecycleLabel(t, state),
      classifiedBy: (source) => classifiedByLabel(t, source),
      account: (id) => accountLabel(t, accounts, id),
      status: (row) => {
        const issues = sets.issues.get(idOf(row))?.length ?? 0;
        return statusLabel(t, statusWord(row.review_status, issues), issues);
      },
    }),
    [t, sets, accounts],
  );
  const terms = useMemo(() => searchTerms(search), [search]);
  const months = useMemo(() => {
    const long = new Intl.DateTimeFormat(locale, { month: "long" });
    return [
      Array.from({ length: 12 }, (_, month) =>
        long.format(new Date(2000, month, 1)),
      ),
      monthNames(locale),
    ];
  }, [locale]);
  const filtered = useMemo(
    () =>
      rows.filter(
        (row) =>
          keepsRow(row, filters, sets, members) &&
          matchesSearch(row, terms, {
            months,
            category: labels.category,
          }),
      ),
    [rows, filters, sets, members, terms, months, labels],
  );
  // A window read in part comes in the product's order; only its own axes
  // sort it.
  const effectiveSort =
    complete || serverSortField(sort.key) ? sort : DEFAULT_SORT;
  const sorted = useMemo(
    () => (complete ? sortRows(filtered, sort, labels) : filtered),
    [complete, filtered, sort, labels],
  );
  const grouping: GroupingId | null =
    groupBy && (complete || groupBy === SERVER_GROUPING) ? groupBy : null;

  const groups = useMemo(() => {
    if (!grouping) return null;
    const firstOf = new Map<string, LedgerRow>();
    for (const row of sorted) {
      const value = groupValue(row, grouping);
      if (!firstOf.has(value)) firstOf.set(value, row);
    }
    return groupRows(sorted, grouping, {
      label: (value) =>
        grouping === "account"
          ? accountGroupLabel(t, accounts, value)
          : groupLabelOf(t, locale, grouping, value, firstOf.get(value)!),
      pendingFirst: savedView === "to_classify",
      descending:
        effectiveSort.key === "date" && effectiveSort.direction === "desc",
    });
  }, [grouping, sorted, savedView, effectiveSort, t, locale, accounts]);

  // The group headers' buttons act on the state of the moment they are
  // pressed.
  const groupCommands = useRef<GroupCommands>({
    classify: () => undefined,
    category: () => undefined,
    select: () => undefined,
  });
  const gridRows = useMemo<GridRow<LedgerRow>[]>(() => {
    if (!groups)
      return sorted.map((row) => ({ kind: "data", key: idOf(row), data: row }));
    const out: GridRow<LedgerRow>[] = [];
    for (const group of groups) {
      const first = group.rows[0]!;
      const folded = collapsed.has(group.key);
      out.push({
        kind: "section",
        key: group.key,
        label:
          grouping === "account"
            ? accountGroupLabel(t, accounts, group.value)
            : groupLabelOf(t, locale, grouping!, group.value, first),
        hint: t("desktop.ledger.group.count", { count: group.rows.length }),
        collapsed: folded,
        summary: complete ? (
          <span className="flex items-center gap-3">
            <SumLine sums={currencySums(group.rows)} locale={locale} />
            <GroupActions
              ids={group.rows.map(idOf)}
              transfers={group.rows.every(
                (row) => row.transaction.direction === "INTERNAL_TRANSFER",
              )}
              commands={groupCommands}
            />
          </span>
        ) : undefined,
      });
      if (!folded)
        for (const row of group.rows)
          out.push({ kind: "data", key: idOf(row), data: row });
    }
    return out;
  }, [groups, grouping, sorted, collapsed, complete, locale, t, accounts]);
  const visible = useMemo(
    () => gridRows.flatMap((row) => (row.kind === "data" ? [row.key] : [])),
    [gridRows],
  );
  // New movements sit at the top, outside every group and sort.
  const drafts = stage.content.drafts;
  const draftGridRows = useMemo<GridRow<LedgerRow>[]>(
    () =>
      drafts.map((draft) => ({
        kind: "data",
        key: draft.key,
        data: draftRow(draft),
      })),
    [drafts],
  );
  const drawnGridRows = useMemo(
    () => (draftGridRows.length ? [...draftGridRows, ...gridRows] : gridRows),
    [draftGridRows, gridRows],
  );
  const drawnRows = useMemo(
    () => [...drafts.map((draft) => draft.key), ...visible],
    [drafts, visible],
  );
  const visibleSet = useMemo(() => new Set(visible), [visible]);

  // ---- Selection -------------------------------------------------------------
  const selected = useMemo(
    () => new Set([...selection].filter((id) => byId.has(id))),
    [selection, byId],
  );
  const hiddenSelected = [...selected].filter((id) => !visibleSet.has(id));
  const shownSelected = visible.filter((id) => selected.has(id)).length;
  const extent: "none" | "some" | "all" =
    shownSelected === 0
      ? "none"
      : shownSelected === visible.length
        ? "all"
        : "some";

  // ---- Feedback --------------------------------------------------------------
  const [toast, setToast] = useState<string | null>(null);
  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), TOAST_MS);
    return () => window.clearTimeout(timer);
  }, [toast]);
  const [spoken, setSpoken] = useState("");

  // A filter that leads somewhere selects and focuses its first movement
  // once the rows it keeps are drawn.
  const [focusWanted, setFocusWanted] = useState<{
    column: ColumnId;
    rows: readonly string[];
  } | null>(null);
  useEffect(() => {
    if (focusWanted === null || focusWanted.rows === visible) return;
    if (membership.kind === "reading") return;
    setFocusWanted(null);
    const first = visible[0];
    if (!first) return;
    setSelection(new Set([first]));
    grid.current?.focusCell(first, focusWanted.column);
  }, [focusWanted, visible, membership.kind, setSelection]);

  // An import's movements, when the person asks to see them.
  const [answeredImport, setAnsweredImport] = useState<ImportedBatches | null>(
    null,
  );
  useEffect(() => {
    if (!shownImport || shownImport === answeredImport) return;
    setAnsweredImport(shownImport);
    setFocusWanted({ column: "description", rows: visible });
    replaceFilters({ ...NO_FILTERS, importBatches: [...shownImport.batches] });
  }, [shownImport, answeredImport, visible, replaceFilters]);

  // ---- Columns ---------------------------------------------------------------
  const layout = useMemo(() => columnLayout(view.columns), [view.columns]);
  const order = shownColumns(layout);
  const remPx =
    typeof document === "undefined"
      ? 16
      : parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
  const widths = useMemo(() => {
    const out: Record<string, number> = {};
    for (const [column, px] of Object.entries(view.columns.widths))
      out[column] = px / remPx;
    return out;
  }, [view.columns.widths, remPx]);
  const missing = filters.reason
    ? (() => {
        const column = REASON_FIX[filters.reason]?.column ?? null;
        return column ? { column, reason: filters.reason } : null;
      })()
    : null;
  const setLayout = (nextOrder: ColumnId[], hidden: ColumnId[]) =>
    onViewChange((current) => ({
      ...current,
      columns: { ...current.columns, order: nextOrder, hidden },
    }));
  const columnContext = {
    locale,
    density: view.density,
    widths,
    readiness: sets,
    missing,
    withYear: period === null,
    extent,
    onSelectShown: (how: "replace" | "add" | "remove") => {
      if (how === "replace") setSelection(new Set(visible));
      else if (how === "add") setSelection(new Set([...selected, ...visible]));
      else
        setSelection(
          new Set([...selected].filter((id) => !visibleSet.has(id))),
        );
    },
    sortable: (column: ColumnId) =>
      complete || COLUMN_SPECS[column].server !== undefined,
    accounts,
  };

  // ---- Staged editing ---------------------------------------------------------
  const edit = useMovementEditing({
    t,
    locale,
    grid,
    byId,
    stage,
    onStage,
    sealed: pageEditing.sealed ?? NO_SEALED,
    drawnRows,
    drawnColumns: order,
    withYear: period === null,
    accounts,
    classify: (kind, ids) => classifySelection(kind, { ids }),
    askDraft: (kind, key) =>
      setAsking({
        kind,
        ids: [],
        skipped: 0,
        partial: false,
        error: null,
        draft: key,
      }),
    say: (text) => setToast(text),
    openReview: pageEditing.openReview,
    focusDraft: pageEditing.focusDraft,
    onDraftFocused: pageEditing.onDraftFocused,
  });

  // ---- Commands --------------------------------------------------------------
  const [asking, setAsking] = useState<Asking | null>(null);
  const classifyTarget = (scope?: { ids: readonly string[] }) =>
    scope
      ? { ids: scope.ids, hidden: 0, partial }
      : { ids: [...selected], hidden: hiddenSelected.length, partial };

  function stageClassified(
    kind: ClassifyKind,
    ids: readonly string[],
    answer: { category?: string; share?: string },
  ): string | null {
    const outcome = classifyCells({ kind, ids, ...answer }, byId);
    if (outcome.kind === "refused")
      return t("desktop.ledger.classify.share_refused", {
        raw: outcome.refusal.raw,
      });
    if (outcome.kind === "needs") return null;
    const classification = classificationLabel(
      t,
      kind === "business"
        ? "BUSINESS"
        : kind === "mixed"
          ? "MIXED"
          : "PERSONAL",
    );
    const said = answer.category
      ? t("desktop.ledger.classify.staged_detail", {
          classification,
          detail: categoryLabel(t, answer.category),
          count: outcome.movements,
        })
      : answer.share
        ? t("desktop.ledger.classify.staged_detail", {
            classification,
            detail: `${answer.share.trim().replace(/\s*%$/, "")}%`,
            count: outcome.movements,
          })
        : t("desktop.ledger.classify.staged", {
            classification,
            count: outcome.movements,
          });
    edit.stageChecked(outcome.event, () => setToast(said));
    return null;
  }

  /** The page's one classify command: every control calls it. */
  function classifySelection(
    kind: ClassifyKind,
    scope?: { ids: readonly string[] },
  ) {
    const availability = classifyAvailability(
      kind,
      classifyTarget(scope),
      byId,
    );
    if (availability.kind === "blocked") {
      setToast(blockText(t, availability.block));
      return;
    }
    if (kind === "personal") {
      stageClassified(kind, availability.ids, {});
      return;
    }
    setAsking({
      kind,
      ids: availability.ids,
      skipped: availability.skipped,
      partial: availability.partial,
      error: null,
    });
  }
  const availabilityOf = (kind: ClassifyKind) =>
    classifyAvailability(kind, classifyTarget(), byId);

  function askCategory(ids: string[]) {
    const takes = ids.filter((id) => {
      const row = byId.get(id);
      return (
        row?.transaction.lifecycle_state === "ACTIVE" &&
        ["BUSINESS", "MIXED"].includes(row.transaction.business_classification)
      );
    });
    if (takes.length === 0) {
      setToast(t("desktop.ledger.classify.category_needs_classification"));
      return;
    }
    setAsking({
      kind: "category",
      ids: takes,
      skipped: ids.length - takes.length,
      partial,
      error: null,
    });
  }

  // ---- Leading to the fix ----------------------------------------------------
  const leadTo = (next: MovementFilters, column: ColumnId) => {
    setFocusWanted({ column, rows: visible });
    setFilters(next);
    onOpenInspector?.("classify");
  };
  const onPill = (filter: ReadinessFilter | null) => {
    if (filter === null) return setFilters({ ...filters, readiness: null });
    leadTo(
      { ...NO_FILTERS, readiness: filter },
      filter === "no_rate"
        ? "eur"
        : filter === "to_classify"
          ? "classification"
          : "status",
    );
    if (filter === "no_rate") showColumns(["eur"]);
  };
  const showColumns = (wanted: ColumnId[]) => {
    if (wanted.every((column) => !layout.hidden.has(column))) return;
    setLayout(
      [...layout.order],
      [...layout.hidden].filter((column) => !wanted.includes(column)),
    );
  };
  const onReason = (reason: string | null) => {
    if (reason === null) return setFilters({ ...filters, reason: null });
    const fix = REASON_FIX[reason];
    if (fix && fix.column && layout.hidden.has(fix.column))
      setLayout([...layout.order], presetHidden(fix.preset));
    leadTo({ ...NO_FILTERS, reason }, fix?.column ?? "status");
  };

  const stepIssue = (by: 1 | -1) => {
    const issues = visible.filter((id) => sets.fix.has(id));
    if (issues.length === 0) {
      setSpoken(t("desktop.ledger.issue.none"));
      return;
    }
    const at = grid.current?.activeCell()?.key ?? null;
    const from = at === null ? -1 : visible.indexOf(at);
    const next =
      by > 0
        ? (issues.find((id) => visible.indexOf(id) > from) ?? issues[0]!)
        : ([...issues].reverse().find((id) => visible.indexOf(id) < from) ??
          issues.at(-1)!);
    const reasons = sets.issues.get(next) ?? [];
    const column = (reasons
      .map((reason) => REASON_FIX[reason]?.column)
      .find((entry) => entry && order.includes(entry)) ?? "status") as ColumnId;
    setSelection(new Set([next]));
    grid.current?.focusCell(next, column);
    setSpoken(
      [
        byId.get(next)?.transaction.description ?? "",
        reasons.map((reason) => reasonDetail(t, reason)).join(", "),
      ]
        .filter(Boolean)
        .join(": "),
    );
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.defaultPrevented || event.nativeEvent.isComposing) return;
    if (edit.onKeyDown(event)) {
      event.preventDefault();
      return;
    }
    if (
      event.key === "F8" &&
      (exactly(event) || exactly(event, { shift: true }))
    ) {
      event.preventDefault();
      stepIssue(event.shiftKey ? -1 : 1);
      return;
    }
    if (!exactly(event, { alt: true })) return;
    const kind = (
      { KeyB: "business", KeyP: "personal", KeyM: "mixed" } as const
    )[event.code as "KeyB" | "KeyP" | "KeyM"];
    if (!kind) return;
    // A field keeps its own keys.
    if ((event.target as HTMLElement).closest("input, textarea, select"))
      return;
    event.preventDefault();
    classifySelection(kind);
  };

  // ---- The palette -----------------------------------------------------------
  const latest = useRef<() => Action[]>(() => []);
  useEffect(() => {
    groupCommands.current = {
      classify: (kind, ids) => classifySelection(kind, { ids }),
      category: askCategory,
      select: (ids) => setSelection(new Set(ids)),
    };
    latest.current = () => [
      ...CLASSIFY_KINDS.map((kind): Action => {
        const availability = availabilityOf(kind);
        return {
          id: `ledger.classify.${kind}`,
          label:
            availability.kind === "blocked"
              ? `${t(`desktop.ledger.classify.as_${kind}`)} · ${blockText(t, availability.block)}`
              : t(`desktop.ledger.classify.as_${kind}`),
          group: "ledger",
          icon: "tick",
          enabled: () => availability.kind === "ready",
          run: () => classifySelection(kind),
        };
      }),
      {
        id: "ledger.issue.next",
        label: t("desktop.ledger.issue.next"),
        group: "ledger",
        icon: "alert",
        enabled: () => sets.fix.size > 0,
        run: () => stepIssue(1),
      },
      {
        id: "ledger.issue.previous",
        label: t("desktop.ledger.issue.previous"),
        group: "ledger",
        icon: "alert",
        enabled: () => sets.fix.size > 0,
        run: () => stepIssue(-1),
      },
      {
        id: "ledger.filters.clear",
        label: t("desktop.ledger.filters.clear_all"),
        group: "ledger",
        icon: "filter",
        enabled: () => filters !== NO_FILTERS || search !== "",
        run: () => {
          setFilters(NO_FILTERS);
          setSearch("");
        },
      },
    ];
  });
  useEffect(() => {
    register(() => latest.current());
    return () => register(null);
  }, [register]);

  // ---- Menus -----------------------------------------------------------------
  const [menu, setMenu] = useState<{
    at: MenuAnchor;
    items: ContextMenuItem[];
    run: (id: string) => void;
  } | null>(null);
  const classifyItems = (ids: string[] | null): ContextMenuItem[] =>
    CLASSIFY_KINDS.map((kind) => ({
      id: `classify.${kind}`,
      label: t(`desktop.ledger.classify.as_${kind}`),
      enabled:
        classifyAvailability(
          kind,
          ids ? { ids, hidden: 0, partial } : classifyTarget(),
          byId,
        ).kind === "ready",
      shortcut: `Alt+${kind === "business" ? "B" : kind === "personal" ? "P" : "M"}`,
    }));
  const openMenu = (key: string, column: string | null, at: MenuAnchor) => {
    const group = groups?.find((entry) => entry.key === key);
    const ids = group ? group.rows.map(idOf) : null;
    const draft = drafts.some((found) => found.key === key);
    const staged = draft || stagedMovements(stage.content).has(key);
    setMenu({
      at,
      items: [
        ...(draft ? [] : classifyItems(ids)),
        ...(ids
          ? []
          : [
              { separator: true as const },
              {
                id: "revert.cell",
                label: t("desktop.ledger.edit.revert_cell"),
                enabled: column !== null && edit.cellStaged(key, column),
                shortcut: "Ctrl+Alt+Z",
              },
              {
                id: "revert.movement",
                label: draft
                  ? t("desktop.ledger.draft.remove")
                  : t("desktop.ledger.edit.revert_movement"),
                enabled: staged,
              },
              {
                id: "fill",
                label: t("desktop.ledger.fill.down"),
                enabled: column !== null,
                shortcut: "Ctrl+D",
              },
            ]),
        ...(ids
          ? [
              {
                id: "category",
                label: t("desktop.ledger.group.category"),
                enabled: true,
              },
              {
                id: "select",
                label: t("desktop.ledger.group.select", { count: ids.length }),
                enabled: true,
              },
            ]
          : []),
      ],
      run: (chosen) => {
        if (chosen === "revert.cell" && column)
          edit.revertCell(key, column as ColumnId);
        else if (chosen === "revert.movement") edit.revertMovement(key);
        else if (chosen === "fill" && column)
          edit.onFill({
            rows: drawnRows.filter((id) => id === key || selected.has(id)),
            columns: [column],
          });
        else if (chosen.startsWith("classify."))
          classifySelection(
            chosen.slice("classify.".length) as ClassifyKind,
            ids ? { ids } : undefined,
          );
        else if (chosen === "category" && ids) askCategory(ids);
        else if (chosen === "select" && ids) setSelection(new Set(ids));
      },
    });
  };

  // ---- What the toolbar and banners say --------------------------------------
  const selectedNote =
    selected.size > 0
      ? t("desktop.ledger.selected", { count: numbers.format(selected.size) })
      : "";
  const shownNote = partial
    ? t("desktop.ledger.loaded_of", {
        loaded: numbers.format(rows.length),
        total: numbers.format(held.total),
      })
    : filtered.length === rows.length
      ? t("desktop.ledger.movements_count", {
          count: numbers.format(rows.length),
        })
      : t("desktop.ledger.shown_of", {
          shown: numbers.format(filtered.length),
          total: numbers.format(rows.length),
        });
  const status = [shownNote, selectedNote].filter(Boolean).join(" · ");
  const unsaved = stageTally(stage.content).units;
  const stagedClassify = [...sets.toClassify].filter(
    (id) =>
      stage.content.rows[id]?.business_classification?.kind === "set" ||
      stage.content.actions.some(
        (action) =>
          action.kind === "suggestion" &&
          action.transactionId === id &&
          action.decision === "apply",
      ),
  ).length;
  const groupLabels = useMemo(
    () =>
      [
        ...new Set(
          rows.flatMap((row) => (row.group_label ? [row.group_label] : [])),
        ),
      ].sort(),
    [rows],
  );
  const hiddenByFilters = rows.length - filtered.length;
  const shownPeriod = periodText(t, locale, period);

  return (
    <div
      className="ledger-movements flex min-h-0 flex-1 flex-col gap-2 p-3"
      onKeyDown={onKeyDown}
      onKeyDownCapture={edit.onKeyDownCapture}
    >
      <ReadinessStrip
        readiness={readiness}
        sets={sets}
        filters={filters}
        locale={locale}
        unsaved={unsaved}
        stagedClassify={stagedClassify}
        partial={partial}
        onPill={onPill}
        onReason={onReason}
      />
      <div>
        <MovementsToolbar
          search={search}
          onSearch={setSearch}
          onLeaveSearch={() => {
            const first = visible[0];
            if (first) grid.current?.focusCell(first);
          }}
          filters={filters}
          onFilters={setFilters}
          savedView={savedView}
          onChooseView={chooseView}
          groupBy={groupBy}
          onGroupBy={setGroupBy}
          groupAllowed={(grouping) => complete || grouping === SERVER_GROUPING}
          onFoldAll={(folded) =>
            setCollapsed(
              new Set(folded ? (groups ?? []).map((g) => g.key) : []),
            )
          }
          sort={effectiveSort}
          onSort={setSort}
          sortAllowed={(key) => complete || serverSortField(key) !== null}
          layout={layout}
          onLayout={setLayout}
          density={view.density}
          onDensity={(density) =>
            onViewChange((current) => ({ ...current, density }))
          }
          accounts={accounts}
          onWantAccounts={() => setWantAccounts(true)}
          groupLabels={groupLabels}
          reasons={sets.reasons.map((entry) => entry.reason)}
          status={status}
        />
      </div>
      {membership.kind === "reading" && (
        <p role="status" className="text-sm text-muted-foreground">
          {t("desktop.ledger.filters.reading")}
        </p>
      )}
      {membership.kind === "failed" && (
        <Alert tone="warning" role="alert" icon={<Icon name="alert" />}>
          {t("desktop.ledger.filters.failed")}
        </Alert>
      )}
      {hiddenSelected.length > 0 && (
        <div
          role="alert"
          className="ledger-hidden-selection flex flex-wrap items-center gap-2"
        >
          <Alert
            tone="warning"
            role="none"
            icon={<Icon name="alert" />}
            className="flex-1"
          >
            {t("desktop.ledger.selection.hidden", {
              hidden: hiddenSelected.length,
              selected: selected.size,
            })}
          </Alert>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setFilters(NO_FILTERS);
              setSearch("");
              setCollapsed(new Set());
            }}
          >
            {t("desktop.ledger.selection.show")}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() =>
              setSelection(
                new Set([...selected].filter((id) => visibleSet.has(id))),
              )
            }
          >
            {t("desktop.ledger.selection.keep_visible")}
          </Button>
        </div>
      )}
      {hiddenSelected.length === 0 &&
        selected.size > 1 &&
        extent === "all" &&
        hiddenByFilters > 0 && (
          <p
            role="status"
            className="flex flex-wrap items-center gap-2 text-sm"
          >
            {t("desktop.ledger.selection.all_shown", { count: visible.length })}
            <Button
              variant="link"
              size="xs"
              onClick={() => setSelection(new Set(rows.map(idOf)))}
            >
              {t("desktop.ledger.selection.select_all", {
                count: rows.length,
                period: shownPeriod,
              })}
            </Button>
          </p>
        )}
      {terms.length > 0 && partial && (
        <p
          role="status"
          className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground"
        >
          {t("desktop.ledger.search.loaded", {
            found: filtered.length,
            loaded: rows.length,
          })}
          <Button variant="link" size="xs" onClick={readAll}>
            {t("desktop.ledger.search.load_all", { total: held.total })}
          </Button>
        </p>
      )}
      {elsewhere !== null && elsewhere > 0 && (
        <p
          role="status"
          className="ledger-elsewhere flex flex-wrap items-center gap-2 text-sm text-muted-foreground"
        >
          {t("desktop.ledger.search.elsewhere", { count: elsewhere })}
          <Button variant="link" size="xs" onClick={() => onPeriod(null)}>
            {t("desktop.ledger.search.show")}
          </Button>
        </p>
      )}
      {partial && !terms.length && (
        <p
          role="status"
          className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground"
        >
          {t("desktop.ledger.window.partial")}
          <Button variant="link" size="xs" onClick={readAll}>
            {t("desktop.ledger.search.load_all", { total: held.total })}
          </Button>
        </p>
      )}
      <MovementsGrid
        gridRef={grid}
        order={order}
        context={{ ...columnContext, editing: edit.editing }}
        byId={byId}
        className="ledger-grid rounded-md"
        label={t("desktop.ledger.grid", { period: shownPeriod })}
        rows={drawnGridRows}
        onCommit={edit.onCommit}
        onPaste={edit.onPaste}
        onCopy={edit.onCopy}
        onFill={edit.onFill}
        density={view.density}
        sort={{ column: effectiveSort.key, direction: effectiveSort.direction }}
        onSort={(column) =>
          setSort(
            effectiveSort.key === column
              ? {
                  key: column as ColumnId,
                  direction: effectiveSort.direction === "asc" ? "desc" : "asc",
                }
              : { key: column as ColumnId, direction: "asc" },
          )
        }
        selection={selected}
        onSelectionChange={(next) => setSelection(next)}
        onToggleSection={(key) => {
          const next = new Set(collapsed);
          if (next.has(key)) next.delete(key);
          else next.add(key);
          setCollapsed(next);
        }}
        onMenu={(key, column, at) => openMenu(key, column, at)}
        onColumnResize={(column, width) =>
          onViewChange((current) => ({
            ...current,
            columns: {
              ...current.columns,
              order: current.columns.order.length
                ? current.columns.order
                : [...layout.order],
              hidden: current.columns.order.length
                ? current.columns.hidden
                : [...layout.hidden],
              widths: {
                ...current.columns.widths,
                [column]: Math.round(width * remPx),
              },
            },
          }))
        }
        onColumnOrder={(next) => {
          const shown = next.filter(
            (column): column is ColumnId => column in COLUMN_SPECS,
          );
          const rest = layout.order.filter((column) => !shown.includes(column));
          setLayout([...shown, ...rest], [...layout.hidden]);
        }}
        empty={
          <EmptyState
            className="ledger-filtered-empty"
            icon="search"
            heading={t("desktop.ledger.empty_filtered")}
            description={t("desktop.ledger.empty_filtered_detail", {
              count: hiddenByFilters,
              period: shownPeriod,
            })}
          >
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setFilters(NO_FILTERS);
                setSearch("");
              }}
            >
              {t("desktop.ledger.filters.clear_all")}
            </Button>
          </EmptyState>
        }
      />
      {periodWindow.phase === "reading" && (
        <p role="status" className="text-xs text-muted-foreground">
          {t("desktop.ledger.loading")}
        </p>
      )}
      <div aria-live="polite" className="sr-only">
        {spoken}
      </div>
      {asking && (
        <ClassifyDialog
          kind={asking.kind}
          movements={asking.draft ? 1 : asking.ids.length}
          skipped={asking.skipped}
          partial={asking.partial}
          error={asking.error}
          onCancel={() => setAsking(null)}
          onStage={(answer) => {
            if (asking.draft) {
              // A new movement's classification is filled in, not staged
              // over a stored one: Business with its category, Mixed with
              // its share.
              const key = asking.draft;
              const share =
                answer.share === undefined ? null : parsePercent(answer.share);
              if (share && share.kind !== "value") {
                setAsking({
                  ...asking,
                  error: t("desktop.ledger.classify.share_refused", {
                    raw: answer.share ?? "",
                  }),
                });
                return;
              }
              const edit = (field: DraftField, value: string | null) =>
                onStage({ type: "edit_draft", key, field, value });
              edit(
                "business_classification",
                asking.kind === "mixed" ? "MIXED" : "BUSINESS",
              );
              if (answer.category) edit("category_id", answer.category);
              edit(
                "business_pct",
                share?.kind === "value" ? share.value : null,
              );
              setAsking(null);
              return;
            }
            if (asking.kind === "category") {
              const outcome = categoryCells(
                asking.ids,
                answer.category ?? "",
                byId,
              );
              if (outcome.kind === "staged") {
                onStage(outcome.event);
                setToast(
                  t("desktop.ledger.classify.staged_category", {
                    category: categoryLabel(t, answer.category ?? ""),
                    count: outcome.movements,
                  }),
                );
              }
              setAsking(null);
              return;
            }
            const error = stageClassified(asking.kind, asking.ids, answer);
            if (error) setAsking({ ...asking, error });
            else setAsking(null);
          }}
        />
      )}
      {menu && (
        <ContextMenu
          label={t("desktop.ledger.menu")}
          items={menu.items}
          at={menu.at}
          choose={(id) => {
            const run = menu.run;
            setMenu(null);
            if (id) run(id);
          }}
        />
      )}
      {edit.dialogs}
      <Toast className="ledger-toast">{toast}</Toast>
    </div>
  );
}
