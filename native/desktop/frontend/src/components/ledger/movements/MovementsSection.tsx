import settings from "virtual:operational-settings";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type Dispatch,
  type KeyboardEvent,
  type SetStateAction,
} from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type { DataGridHandle, GridRow } from "@/components/ui/dataGridTypes";
import { exactly } from "@/components/ui/dataGridModel";
import { EmptyState } from "@/components/ui/empty";
import { Icon } from "@/components/ui/icon";
import { Toast } from "@/components/ui/toast";
import { facts, labelled, listed } from "@/shell/compose";
import {
  ContextMenu,
  type MenuAnchor,
  type MenuEntry,
} from "../../ContextMenu";
import type { Action } from "../../../shell/actions";
import type { LedgerView } from "../../../shell/layout";
import type { LedgerPort, LedgerRow } from "../../../shell/ledger";
import {
  classifyAvailability,
  type ClassifyKind,
  type OpenRuleFromSelection,
} from "../../../shell/ledgerCommands";
import { useLedgerClassifications } from "../../../shell/ledgerClassifications";
import { takesChanges } from "../../../shell/ledgerContract";
import { useConfiguredRatios } from "../setup/useConfiguredRatios";
import { ActionDialog, type ActionRequest } from "../inspector/ActionDialog";
import {
  sameInspectorContext,
  type SectionInspectorContext,
} from "../inspector/inspectorContext";
import type { LedgerPeriod } from "../../../shell/ledgerGrammar";
import {
  servedDraftCurrency,
  useLedgerMembership,
  useOwnAccounts,
  useSearchElsewhere,
} from "../../../shell/ledgerMovementReads";
import {
  stagedMovements,
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
import { useStrings } from "../../../shell/strings";
import { useVocabulary } from "../suggestions/SuggestionsProvider";
import { monthNames } from "../../../shared/dateFormats";
import { formatCount } from "../../../shared/numbers";
import { draftRow, stageTally } from "../editing/editingModel";
import { useMovementEditing } from "../editing/MovementEditing";
import { periodText } from "../ledgerWords";
import { SelectionActions, type GroupCommands } from "./ClassifyMenus";
import { MovementClassifyDialog } from "./MovementClassifyDialog";
import { movementMenuItems } from "./movementMenuItems";
import { movementPaletteActions } from "./movementPaletteActions";
import { MovementsGrid } from "./MovementsGrid";
import {
  COLUMN_SPECS,
  DEFAULT_SORT,
  NO_FILTERS,
  REASON_FIX,
  SERVER_GROUPING,
  columnLayout,
  keepsRow,
  matchesSearch,
  presetHidden,
  readinessSets,
  searchTerms,
  serverFilters,
  serverSortField,
  shownColumns,
  sortRows,
  stagedClassifyCount,
  statusMarks,
  type ColumnId,
  type GroupingId,
  type MovementFilters,
  type ReadinessFilter,
  type SortLabels,
} from "./movementsModel";
import { MovementsToolbar } from "./MovementsToolbar";
import { MovementWindowNotices } from "./MovementWindowNotices";
import {
  accountLabel,
  categoryLabel,
  classificationText,
  classifiedByLabel,
  directionLabel,
  irpfCategoryLabel,
  ivaCategoryLabel,
  lifecycleLabel,
  reasonDetail,
  statusLabel,
  statusWord,
} from "./movementWords";
import { ReadinessStrip } from "./ReadinessStrip";
import { useClassifyChords } from "./useClassifyChords";
import { useClassifyCommand } from "./useClassifyCommand";
import { useMovementColumns } from "./useMovementColumns";
import { useMovementGroupRows } from "./MovementGroupRows";
import { useFocusTarget } from "../../../shell/navigation/hooks";
import { RowRevealNotice, useRowReveal, type LinkedRow } from "../RowReveal";
import { movementHiding, withoutHiding } from "./movementReveal";
import type { MovementsView } from "./useMovementsView";
import type { ImportedBatches } from "../../../shell/ledgerImports";

const idOf = (row: LedgerRow) => row.transaction.transaction_id;

/** The list read that keeps the movements an import flagged as likely
 * duplicates. */
const DUPLICATE_SCOPES = [{ filters: ["issue=duplicate"] }] as const;

/** What staged editing on the section needs from the page. */
export type SectionEditing = {
  openReview: () => void;
  /** A new movement to focus once it is drawn. */
  focusDraft: string | null;
  onDraftFocused: () => void;
  /** The movements and the column a refusal's door led to, to select and
   * focus once they are drawn. */
  shownFields?: { column: ColumnId; ids: readonly string[] } | null;
  onFieldsShown?: () => void;
  /** Movements a finalized declaration cites, where the page knows. */
  sealed?: ReadonlySet<string>;
};
const NO_SEALED: ReadonlySet<string> = new Set();

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
  onCheckReadiness,
  movements,
  stage,
  onStage,
  view,
  onViewChange,
  locale,
  onPeriod,
  onOpenInspector,
  onInspector,
  register,
  shownImport,
  onImportCleared,
  editing: pageEditing,
  linked,
  onMakeRule,
  onOpenRatios,
}: {
  port: LedgerPort;
  reader: string;
  period: LedgerPeriod | null;
  periodWindow: LedgerWindow;
  readAll: () => void;
  readiness: Readiness;
  /** Runs the period's readiness check again. */
  onCheckReadiness?: () => void;
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
  /** Hands the inspector what the section draws and its commands. */
  onInspector?: Dispatch<SetStateAction<SectionInspectorContext | null>>;
  /** Hands the page's palette what the section offers. */
  register: (actions: (() => Action[]) | null) => void;
  /** An import's movements, which the grid shows when asked. */
  shownImport: ImportedBatches | null;
  /** The person took the import's filter off. */
  onImportCleared?: () => void;
  editing: SectionEditing;
  /** The movement a link selects, held by the page. */
  linked: LinkedRow;
  /** Opens the rule dialog prefilled from movements, where the page has
   * one. */
  onMakeRule?: OpenRuleFromSelection;
  /** Opens the business-use ratios, where the page has them. */
  onOpenRatios?: () => void;
}) {
  const t = useStrings();
  const grid = useRef<DataGridHandle>(null);
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
  // A new movement's currency is the one the profile's own accounts are kept
  // in, as the backend serves it: the visible field is filled in, so the saved
  // movement carries its currency explicitly rather than taking a writer's
  // default. A currency already typed is never overwritten, and where the
  // accounts disagree the person says which. With no account naming one, the
  // ledger's functional currency, as served, is offered.
  const vocabulary = useVocabulary();
  const draftCurrency = servedDraftCurrency(
    accounts,
    vocabulary.defaultCurrency,
  );
  useEffect(() => {
    if (!draftCurrency) return;
    for (const draft of stage.content.drafts)
      if (!draft.fields.currency)
        onStage({
          type: "edit_draft",
          key: draft.key,
          field: "currency",
          value: draftCurrency,
        });
  }, [draftCurrency, stage.content.drafts, onStage]);

  const elsewhere = useSearchElsewhere(port, reader, period, search);
  // What an import flagged as a likely duplicate: the product keeps it as an
  // import diagnostic, which the list reads by its issue filter. A movement
  // archived since is no longer marked.
  const flagged = useLedgerMembership(
    port,
    reader,
    period,
    DUPLICATE_SCOPES,
    periodWindow.phase === "ready" ? periodWindow.generation : null,
  );
  const duplicates = useMemo(() => {
    if (flagged.kind !== "ready") return new Set<string>();
    return new Set(
      rows
        .filter(
          (row) =>
            flagged.ids.has(idOf(row)) &&
            takesChanges(row.transaction.lifecycle_state),
        )
        .map(idOf),
    );
  }, [flagged, rows]);
  const currencySlot = useMemo(
    () => rows.some((row) => row.transaction.currency !== "EUR"),
    [rows],
  );
  const marks = useMemo(
    () => statusMarks(rows, duplicates),
    [rows, duplicates],
  );
  // The business-use ratios configured for the years of the window's
  // movements, which the Mixed step stages with its share.
  const years = useMemo(
    () => [
      ...new Set(rows.map((row) => Number(row.transaction.date.slice(0, 4)))),
    ],
    [rows],
  );
  const { ratios } = useConfiguredRatios(port, reader, years);
  // The words for a classification with its share depend on what the backend
  // serves for it, so the section is drawn again once that arrives.
  useLedgerClassifications();

  // ---- What is shown ---------------------------------------------------------
  const labels = useMemo<SortLabels>(
    () => ({
      category: (id) => categoryLabel(t, id),
      ivaCategory: (id) => ivaCategoryLabel(t, id),
      irpfCategory: (id) => irpfCategoryLabel(t, id),
      classification: (row) => classificationText(t, locale, row.transaction),
      direction: (direction) => directionLabel(t, direction),
      lifecycle: (state) => lifecycleLabel(t, state),
      classifiedBy: (source) => classifiedByLabel(t, source),
      account: (id) => accountLabel(t, accounts, id),
      status: (row) => {
        const issues = sets.checked
          ? (sets.issues.get(idOf(row))?.length ?? 0)
          : null;
        return statusLabel(t, statusWord(row.review_status, issues), issues);
      },
    }),
    [t, locale, sets, accounts],
  );
  const terms = useMemo(() => searchTerms(search), [search]);
  const months = useMemo(() => {
    return [monthNames(locale, "long"), monthNames(locale)];
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

  // The group headers' buttons act on the state of the moment they are
  // pressed.
  const groupCommands = useRef<GroupCommands>({
    classify: () => undefined,
    category: () => undefined,
    select: () => undefined,
    makeRule: null,
  });
  const { groups, gridRows } = useMovementGroupRows({
    sorted,
    grouping,
    collapsed,
    complete,
    savedView,
    sort: effectiveSort,
    locale,
    accounts,
    vocabulary,
    commands: groupCommands,
  });
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

  // ---- A link's row ------------------------------------------------------------
  // A link that selects a movement reveals it once the grid draws it; one
  // the person's own view hides is announced with what shows it.
  const within = useRef<HTMLDivElement>(null);
  useFocusTarget(
    "ledger/movements",
    () =>
      within.current?.querySelector<HTMLElement>(
        '[role="grid"] [tabindex="0"]',
      ) ?? null,
  );
  const reveal = useRowReveal(linked, {
    shown: (id) => visibleSet.has(id),
    hiding: (id) => {
      const row = byId.get(id);
      if (!row || membership.kind === "reading") return null;
      const hiding = movementHiding(row, {
        filters,
        sets,
        members,
        terms,
        search: { months, category: labels.category },
        grouping,
        collapsed,
        vocabulary,
      });
      if (!hiding) return null;
      return () => {
        if (hiding.filters.length) setFilters(withoutHiding(filters, hiding));
        if (hiding.search) setSearch("");
        if (hiding.group !== null)
          setCollapsed(
            new Set([...collapsed].filter((key) => key !== hiding.group)),
          );
      };
    },
    settled: periodWindow.phase === "ready" && membership.kind !== "reading",
    reveal: (id, focus) => {
      setSelection(new Set([id]));
      if (focus) grid.current?.focusCell(id);
      else grid.current?.scrollToKey(id, "center");
    },
    drawn: visible,
    within,
  });

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
    const timer = window.setTimeout(
      () => setToast(null),
      settings.ledger_toast_ms,
    );
    return () => window.clearTimeout(timer);
  }, [toast]);
  const [spoken, setSpoken] = useState("");

  // What the live regions last said described a staged cell: "unsaved, the
  // taxable base is missing". Once the stage is gone -- saved or dropped --
  // that sentence is about a state the grid no longer holds, and a screen
  // reader asked to repeat it would read saved work as still unsaved. Both
  // regions are emptied, and the next keyboard move says the row as it is.
  const stagedUnits =
    stage.content.drafts.length +
    Object.keys(stage.content.rows).length +
    stage.content.actions.length;
  const wasStaging = useRef(stagedUnits);
  useEffect(() => {
    const before = wasStaging.current;
    wasStaging.current = stagedUnits;
    if (before === 0 || stagedUnits > 0) return;
    grid.current?.clearAnnouncement();
    setSpoken("");
  }, [stagedUnits]);

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
  const drafting = stage.content.drafts.length > 0;
  const { layout, remPx, widths, drawnLayout, order } = useMovementColumns({
    view,
    within,
    marks,
    withYear: period === null,
    drafting,
  });
  const missing = filters.reason
    ? (() => {
        const column = REASON_FIX[filters.reason]?.column ?? null;
        return column ? { column, reason: filters.reason } : null;
      })()
    : null;
  // A refusal's door leads to the column the missing fact is typed in: once
  // that column is shown and the movements it holds are drawn, the first of
  // them takes the keyboard there, so the person lands on the cell to fill in.
  const shownFields = pageEditing.shownFields ?? null;
  const onFieldsShown = pageEditing.onFieldsShown;
  useEffect(() => {
    if (!shownFields || membership.kind === "reading") return;
    if (!order.includes(shownFields.column)) return;
    const first = shownFields.ids.find((id) => visible.includes(id));
    onFieldsShown?.();
    if (!first) return;
    setSelection(new Set(shownFields.ids));
    grid.current?.focusCell(first, shownFields.column);
  }, [
    shownFields,
    onFieldsShown,
    order,
    visible,
    membership.kind,
    setSelection,
  ]);

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

  // ---- Staged editing and the classify command -------------------------------
  const classify = useClassifyCommand({
    t,
    port,
    byId,
    stage,
    ratios,
    partial,
    selected,
    hiddenSelected: hiddenSelected.length,
    grid,
    stageChecked: (event, then) => edit.stageChecked(event, then),
    say: setToast,
  });
  const {
    asking,
    classifySelection,
    askCategory,
    availabilityOf,
    classifyTarget,
  } = classify;
  const edit = useMovementEditing({
    t,
    locale,
    grid,
    port,
    byId,
    stage,
    onStage,
    sealed: pageEditing.sealed ?? NO_SEALED,
    drawnRows,
    drawnColumns: order,
    withYear: period === null,
    accounts,
    classify: (kind, ids) => classifySelection(kind, { ids }),
    askDraft: (kind, key) => void classify.askDraftClassification(kind, key),
    say: (text) => setToast(text),
    openReview: pageEditing.openReview,
    focusDraft: pageEditing.focusDraft,
    onDraftFocused: pageEditing.onDraftFocused,
  });

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
    const description = byId.get(next)?.transaction.description ?? "";
    const found = listed(
      t,
      reasons.map((reason) => reasonDetail(t, reason)),
      "plain",
    );
    setSpoken(
      description && found
        ? labelled(t, description, found)
        : description || found,
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
  };

  useClassifyChords((kind) => classifySelection(kind));

  // ---- The palette -----------------------------------------------------------
  const latest = useRef<() => Action[]>(() => []);
  useEffect(() => {
    groupCommands.current = {
      classify: (kind, ids) => classifySelection(kind, { ids }),
      category: askCategory,
      select: (ids) => setSelection(new Set(ids)),
      makeRule: onMakeRule ? (ids) => onMakeRule({ ids }) : null,
    };
    latest.current = () =>
      movementPaletteActions({
        t,
        availabilityOf,
        classify: (kind) => classifySelection(kind),
        hasIssues: sets.fix.size > 0,
        stepIssue,
        filtering: filters !== NO_FILTERS || search !== "",
        clearFilters: () => {
          setFilters(NO_FILTERS);
          setSearch("");
        },
      });
  });
  useEffect(() => {
    register(() => latest.current());
    return () => register(null);
  }, [register]);

  // ---- The inspector beside the grid ------------------------------------------
  const inspectorCommands = useRef({
    classify: classifySelection,
    focusActive: () => undefined as void,
    showHidden: () => undefined as void,
  });
  useEffect(() => {
    inspectorCommands.current = {
      classify: classifySelection,
      focusActive: () => {
        const active = grid.current?.activeCell();
        const key = active?.key ?? [...selected][0] ?? visible[0];
        // With no cell active, the movement's description takes the focus,
        // not the selection box before it.
        if (key) grid.current?.focusCell(key, active?.column ?? "description");
      },
      showHidden: () => {
        setFilters(NO_FILTERS);
        setSearch("");
        setCollapsed(new Set());
      },
    };
  });
  const inspectorContext = useMemo<SectionInspectorContext>(
    () => ({
      visible: visibleSet,
      partial,
      checked: sets.checked,
      issues: sets.issues,
      accounts,
      duplicates,
      classify: (kind, scope) =>
        inspectorCommands.current.classify(kind, scope),
      focusActive: () => inspectorCommands.current.focusActive(),
      showHidden: () => inspectorCommands.current.showHidden(),
    }),
    [visibleSet, partial, sets, accounts, duplicates],
  );
  // The page hears of a change only: the section draws often.
  const sentContext = useRef<SectionInspectorContext | null>(null);
  useEffect(() => {
    const last = sentContext.current;
    if (last && sameInspectorContext(last, inspectorContext)) return;
    sentContext.current = inspectorContext;
    onInspector?.(inspectorContext);
  }, [onInspector, inspectorContext]);
  // Going, the section takes back only what it sent, since a section drawn
  // in its place may have sent its own already; and it forgets having sent
  // it, so that one still here sends it again.
  useEffect(
    () => () => {
      const mine = sentContext.current;
      sentContext.current = null;
      onInspector?.((current) => (current === mine ? null : current));
    },
    [onInspector],
  );

  // ---- Menus -----------------------------------------------------------------
  const [acting, setActing] = useState<ActionRequest | null>(null);
  /** Focus goes back to the grid's active cell as a dialog it opened
   * closes. */
  const backToGrid = () => inspectorCommands.current.focusActive();
  const [menu, setMenu] = useState<{
    at: MenuAnchor;
    items: MenuEntry[];
    run: (id: string) => void;
  } | null>(null);
  const openMenu = (key: string, column: string | null, at: MenuAnchor) => {
    const group = groups?.find((entry) => entry.key === key);
    const ids = group ? group.rows.map(idOf) : null;
    const draft = drafts.some((found) => found.key === key);
    const staged = draft || stagedMovements(stage.content).has(key);
    setMenu({
      at,
      items: movementMenuItems({
        t,
        ids,
        draft,
        staged,
        column,
        cellStaged: () => column !== null && edit.cellStaged(key, column),
        duplicate: duplicates.has(key),
        makeRule: !!onMakeRule,
        classifyEnabled: (kind) =>
          classifyAvailability(
            kind,
            ids ? { ids, hidden: 0, partial } : classifyTarget(),
            byId,
          ).kind === "ready",
      }),
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
        else if (chosen === "make_rule" && ids) onMakeRule?.({ ids });
        else if (chosen === "duplicate.archive")
          // The menu hands focus back to the grid as it closes; the dialog
          // opens after that, or it would take the move as a press outside.
          window.requestAnimationFrame(() =>
            setActing({
              kind: "archive",
              ids: [key],
              reason: t("desktop.ledger.import_issue.duplicate"),
            }),
          );
      },
    });
  };

  // ---- What the toolbar and banners say --------------------------------------
  const selectedNote =
    selected.size > 0
      ? t("desktop.ledger.selected", {
          count: formatCount(locale, selected.size),
        })
      : "";
  const shownNote = partial
    ? t("desktop.ledger.loaded_of", {
        loaded: formatCount(locale, rows.length),
        total: formatCount(locale, held.total),
      })
    : filtered.length === rows.length
      ? t("desktop.ledger.movements_count", {
          count: formatCount(locale, rows.length),
        })
      : t("desktop.ledger.shown_of", {
          shown: formatCount(locale, filtered.length),
          total: formatCount(locale, rows.length),
        });
  const status = facts(t, [shownNote, selectedNote]);
  const unsaved = stageTally(stage.content).units;
  const stagedClassify = stagedClassifyCount(sets.toClassify, stage.content);
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
  const selectionActions =
    selected.size > 1 ? (
      <SelectionActions
        availabilityOf={availabilityOf}
        classify={(kind) => classifySelection(kind)}
        hidden={hiddenSelected.length > 0}
        onMakeRule={
          onMakeRule ? () => onMakeRule({ ids: [...selected] }) : undefined
        }
      />
    ) : null;

  return (
    <div
      ref={within}
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
        onCheck={onCheckReadiness}
        onPill={onPill}
        onReason={onReason}
        duplicates={duplicates.size}
        duplicatesShown={filters.importIssue === "duplicate"}
        onDuplicates={(show) =>
          show
            ? leadTo({ ...NO_FILTERS, importIssue: "duplicate" }, "status")
            : setFilters({ ...filters, importIssue: null })
        }
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
          layout={drawnLayout}
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
          selectionActions={selectionActions}
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
      {flagged.kind === "failed" && (
        // Unread is not "none": without this the marks would just vanish.
        <Alert
          tone="warning"
          role="alert"
          icon={<Icon name="alert" />}
          className="ledger-duplicates-failed"
        >
          {t("desktop.ledger.duplicate.failed")}
        </Alert>
      )}
      <RowRevealNotice
        {...reveal}
        hidden={t("desktop.ledger.reveal.movement_hidden")}
        missing={t("desktop.ledger.reveal.movement_missing")}
      />
      <MovementWindowNotices
        hiddenSelected={hiddenSelected.length}
        selected={selected.size}
        allShownSelected={extent === "all"}
        hiddenByFilters={hiddenByFilters}
        shown={visible.length}
        loaded={rows.length}
        total={held.total}
        found={filtered.length}
        searching={terms.length > 0}
        partial={partial}
        elsewhere={elsewhere}
        period={shownPeriod}
        onShowHidden={() => {
          setFilters(NO_FILTERS);
          setSearch("");
          setCollapsed(new Set());
        }}
        onKeepVisible={() =>
          setSelection(
            new Set([...selected].filter((id) => visibleSet.has(id))),
          )
        }
        onSelectAll={() => setSelection(new Set(rows.map(idOf)))}
        readAll={readAll}
        onElsewhere={() => onPeriod(null)}
      />
      <MovementsGrid
        gridRef={grid}
        order={order}
        context={{
          ...columnContext,
          duplicates,
          currencySlot,
          statusMarks: marks,
          drafting,
          editing: edit.editing,
        }}
        byId={byId}
        moreColumnsLabel={(count) =>
          t("desktop.ledger.columns.more_name", { count })
        }
        earlierColumnsLabel={(count) =>
          t("desktop.ledger.columns.earlier_name", { count })
        }
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
        <MovementClassifyDialog
          asking={asking}
          command={classify}
          byId={byId}
          ratios={ratios}
          onOpenRatios={onOpenRatios}
          onStage={onStage}
          onSelect={(ids) => setSelection(new Set(ids))}
          say={setToast}
          backToGrid={backToGrid}
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
      {acting && (
        <ActionDialog
          port={port}
          request={acting}
          rows={byId}
          sealed={pageEditing.sealed ?? NO_SEALED}
          onStage={onStage}
          onClose={() => setActing(null)}
          onClosed={backToGrid}
          say={setToast}
        />
      )}
      {edit.dialogs}
      <Toast className="ledger-toast">{toast}</Toast>
    </div>
  );
}
