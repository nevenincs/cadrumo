import settings from "virtual:operational-settings";
import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useReducer,
  useRef,
  useState,
} from "react";
import type { IconName } from "@/components/ui/icon";
import { localDay } from "../../shared/dates";
import type { Action } from "../../shell/actions";
import { LEDGER_SECTIONS, type LedgerSection } from "../../shell/layout";
import type { OutputLanguage } from "../../shell/ledger";
import type { OpenRuleFromSelection } from "../../shell/ledgerCommands";
import type { LedgerPeriod } from "../../shell/ledgerGrammar";
import {
  annualCode,
  neighbourPeriod,
  periodsHoldingToday,
  periodsHoldingTodayFailed,
  usePeriods,
} from "../../shell/ledgerPeriods";
import type { ImportedBatches } from "../../shell/ledgerImports";
import { useLedgerLimits } from "../../shell/ledgerLimits";
import { useLedgerReadiness } from "../../shell/ledgerReadiness";
import {
  EMPTY_STAGE,
  reduceStage,
  movementsToTrack,
  reconcileMovementSelection,
  rekeyMovementSelection,
} from "../../shell/ledgerStage";
import {
  readinessSnapshot,
  shownRows,
  useLedgerWindow,
} from "../../shell/ledgerWindow";
import { useLedgerYears } from "../../shell/ledgerYears";
import { useStrings } from "../../shell/strings";
import type { LedgerHeaderAction, SectionCount } from "./LedgerHeader";
import type { LedgerPageProps } from "./LedgerPage";
import { useLinkedRow } from "./RowReveal";
import { usePagePause } from "./WritePause";
import { useLedgerEditing } from "./editing/LedgerEditing";
import type { EditorTarget } from "./invoices/InvoiceEditor";
import { SECTION_ICONS, periodText, sectionName } from "./ledgerWords";
import {
  columnsOfFields,
  readinessSets,
  type ColumnId,
} from "./movements/movementsModel";
import { useMovementsView, windowScope } from "./movements/useMovementsView";
import type { RuleDialogTarget } from "./setup/RuleDialog";
import type { RulesArea } from "./setup/RulesSection";
import type { SetupProps } from "./setup/setupProps";
import { useLedgerGridRoom } from "./useLedgerGridRoom";
import { useLedgerInspector } from "./useLedgerInspector";
import { useSealedMovements } from "./useSealedMovements";

/** Coordinates profile-bound ledger reads, staged work and cross-section actions. */
export function useLedgerPage({
  port,
  reader,
  locale,
  shown,
  page,
  view,
  onViewChange,
  memory,
  contribute,
  onFloor,
}: Pick<
  LedgerPageProps,
  | "port"
  | "reader"
  | "locale"
  | "shown"
  | "page"
  | "view"
  | "onViewChange"
  | "memory"
  | "contribute"
  | "onFloor"
>) {
  const t = useStrings();
  // What was typed before the limits arrived is read again when they do.
  useLedgerLimits();
  const panel = useId();
  // The period the page opens on is the quarter that holds today, as served;
  // until it is served, and until one is chosen, the period is unresolved and
  // nothing is read for it. Where the backend could not say which it is, every
  // period is shown rather than one made up.
  usePeriods();
  const todaysPeriods = periodsHoldingToday();
  const [chosen, setChosen] = useState<LedgerPeriod | null | undefined>(
    () => memory.current.period,
  );
  const periodResolved =
    chosen !== undefined ||
    todaysPeriods !== null ||
    periodsHoldingTodayFailed();
  const period: LedgerPeriod | null =
    chosen !== undefined ? chosen : (todaysPeriods?.quarterly ?? null);
  const setPeriod = (next: LedgerPeriod | null) => {
    memory.current.period = next;
    setChosen(next);
  };
  const section = view.section;
  // The Rules section's area to open on, where another section asked for
  // one; it is forgotten once the page leaves Rules.
  const [rulesArea, setRulesArea] = useState<RulesArea>();
  const setSection = (next: LedgerSection) => {
    setPeriodOpen(false);
    if (next !== "rules") setRulesArea(undefined);
    if (next !== "registers") memory.current.registersArea = undefined;
    onViewChange((current) => ({ ...current, section: next }));
  };
  // An area asked for belongs to the visit it was asked for.
  useEffect(
    () => () => {
      memory.current.registersArea = undefined;
    },
    [memory],
  );
  const openRatios = () => {
    setRulesArea("ratios");
    setSection("rules");
  };
  const readable = reader !== null;
  const linkedMovement = useLinkedRow("ledger/movements");
  const linkedInvoice = useLinkedRow("ledger/invoices");
  // Only the sections that show a period's records have a period to choose.
  const periodShown =
    section === "movements" || section === "invoices" || section === "health";
  const movementsShown = shown && readable && section === "movements";
  const movements = useMovementsView(memory, view, onViewChange);
  const {
    window: periodWindow,
    reread,
    readAll,
  } = useLedgerWindow(
    port,
    reader,
    period,
    movementsShown && periodResolved,
    windowScope(period === null, movements, locale as OutputLanguage),
  );
  // What is staged lives here, with the page, so it stays while a section
  // is put away and goes with the profile.
  const [stage, dispatchStage] = useReducer(reduceStage, EMPTY_STAGE);
  useEffect(() => {
    const next = reconcileMovementSelection(
      movements.selection,
      stage.content.drafts,
    );
    if (next.size !== movements.selection.size) movements.setSelection(next);
  }, [movements, stage.content.drafts]);
  // What the movements section offers the palette.
  const movementActions = useRef<(() => Action[]) | null>(null);
  const registerMovements = useCallback((actions: (() => Action[]) | null) => {
    movementActions.current = actions;
  }, []);
  const { readiness, recheck: recheckReadiness } = useLedgerReadiness(
    port,
    reader,
    period,
    periodWindow?.phase === "ready" ? periodWindow.generation : null,
  );
  const [periodOpen, setPeriodOpen] = useState(false);
  // The invoice being added or corrected; it goes with the profile.
  const [invoiceEditor, setInvoiceEditor] = useState<EditorTarget | null>(null);
  useEffect(() => setInvoiceEditor(null), [reader]);
  const [transfer, setTransferNow] = useState<"import" | "export" | null>(null);
  // The dialogs mount only while open, so they have no trigger to hand the
  // focus back to: the page keeps what had it when one opened.
  const transferOpener = useRef<HTMLElement | null>(null);
  const setTransfer = (next: "import" | "export" | null) => {
    if (next !== null && transfer === null)
      transferOpener.current =
        document.activeElement instanceof HTMLElement
          ? document.activeElement
          : null;
    setTransferNow(next);
  };
  // Back to the opener, unless what the dialog led to took the focus.
  const returnTransferFocus = (event: Event) => {
    event.preventDefault();
    const active = document.activeElement;
    if (active !== null && active !== document.body) return;
    const opener = transferOpener.current;
    transferOpener.current = null;
    if (opener?.isConnected) opener.focus();
    else page.current?.focus();
  };

  const {
    inspectorContext,
    setInspectorContext,
    inspectorFocus,
    panelMode,
    setPanelMode,
    inspectorPanel,
    openInspector,
    closeInspector,
    onInspectorKey,
  } = useLedgerInspector({ view, onViewChange });
  // What an import brought in, as the person asked to see it.
  const [shownImport, setShownImport] = useState<ImportedBatches | null>(null);
  // Read with the page, so the period list never grows under the pointer.
  // The walk counts each year under the code the backend names the year by.
  const { years, refresh: refreshYears } = useLedgerYears(
    port,
    reader,
    readable && annualCode() !== null,
  );
  // Where the period dropdown opens while every period is shown: the year
  // that holds today as served, else the calendar year the window is in.
  const fallbackYear =
    todaysPeriods?.annual.year ?? Number(localDay().slice(0, 4));
  const shownPeriod = periodText(t, locale, period);

  // Nothing the header offers runs yet where the page has no way to do it:
  // it says so instead of doing nothing.
  const unavailable = (): LedgerHeaderAction => ({
    reason: t("desktop.ledger.unavailable"),
  });
  const importAction: LedgerHeaderAction = readable
    ? { run: () => setTransfer("import") }
    : unavailable();
  const exportAction: LedgerHeaderAction = readable
    ? { run: () => setTransfer("export") }
    : unavailable();
  // One pause for every write on the page: a write whose outcome was not
  // observed holds them all until a re-read settles it.
  const pause = usePagePause({ reader, afterReread: reread });
  // The movements the page acts on, whose participation it reads to know
  // which a finalized declaration seals.
  const sealedWanted = useMemo(
    () => movementsToTrack(stage.content, movements.selection),
    [movements.selection, stage.content],
  );
  const { sealed, unread, sealedOf } = useSealedMovements(
    port,
    reader,
    periodWindow?.phase === "ready" ? periodWindow.generation : null,
    sealedWanted,
  );
  // The staged work of every section: the tray, the review and apply,
  // and the guard before leaving.
  const [focusDraft, setFocusDraft] = useState<string | null>(null);
  // The movements and the column a refusal led to, until the grid has shown
  // them. Each lead replaces the last.
  const [shownFields, setShownFields] = useState<{
    column: ColumnId;
    ids: readonly string[];
  } | null>(null);
  const editing = useLedgerEditing({
    port,
    period,
    rows: periodWindow ? (shownRows(periodWindow)?.rows ?? null) : null,
    stage,
    dispatch: dispatchStage,
    reread,
    onRekey: (from, to) => {
      movements.setSelection((current) =>
        rekeyMovementSelection(current, from, to),
      );
    },
    onShowRows: (ids, fields) => {
      setSection("movements");
      movements.setSelection(new Set(ids));
      // A refusal that names a field leads to the column it is typed in,
      // which the person's own column choice or a preset may be hiding.
      const wanted = columnsOfFields(fields ?? []);
      if (wanted.length === 0) return;
      onViewChange((current) => {
        const hidden = current.columns.hidden.filter(
          (column) => !(wanted as readonly string[]).includes(column),
        );
        return hidden.length === current.columns.hidden.length
          ? current
          : { ...current, columns: { ...current.columns, hidden } };
      });
      setShownFields({ column: wanted[0]!, ids: [...ids] });
    },
    onGoToDraft: (key) => {
      setSection("movements");
      setFocusDraft(key);
    },
    locale,
    pause,
    sealedOf,
    returnFocus: () => {
      if (section !== "movements" || !inspectorContext) return false;
      inspectorContext.focusActive();
      return true;
    },
  });
  // The rule dialog opens over whatever section is shown: from Rules, or
  // from a selection or a group of movements.
  const [ruleTarget, setRuleTarget] = useState<RuleDialogTarget | null>(null);
  const [rulesVersion, setRulesVersion] = useState(0);
  // A short word on what the page's own dialogs saved.
  const [toast, setToast] = useState<string | null>(null);
  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(
      () => setToast(null),
      settings.ledger_toast_ms,
    );
    return () => window.clearTimeout(timer);
  }, [toast]);
  useEffect(() => setRuleTarget(null), [reader]);
  const openRuleFromSelection: OpenRuleFromSelection = useCallback(
    (seed) => setRuleTarget({ kind: "seed", seed }),
    [],
  );
  const setupProps: SetupProps = {
    port,
    reader,
    locale,
    rows: periodWindow ? (shownRows(periodWindow)?.rows ?? null) : null,
    stage: stage.content,
    onStage: editing.onStage,
    years,
    fallbackYear,
    period,
  };
  const addAction: LedgerHeaderAction = readable
    ? {
        run: () => {
          setSection("movements");
          setFocusDraft(editing.addDraft());
        },
      }
    : unavailable();
  const addInvoiceAction: LedgerHeaderAction = readable
    ? { run: () => setInvoiceEditor({ kind: "new" }) }
    : unavailable();

  const shownWindow = periodWindow ? shownRows(periodWindow) : null;
  // The tab counts what the period's own check counts, never the rows the
  // page holds, which may be another period's while another section shows.
  const pageSets = useMemo(
    () => readinessSets(shownWindow?.rows ?? [], readinessSnapshot(readiness)),
    [shownWindow, readiness],
  );
  const toClassify =
    readiness.kind !== "failed" && pageSets.counts
      ? pageSets.counts.toClassify
      : 0;
  const counts: Partial<Record<LedgerSection, SectionCount>> =
    toClassify > 0
      ? {
          movements: {
            count: toClassify,
            label: t("desktop.ledger.count.to_classify", {
              count: toClassify,
            }),
          },
        }
      : {};

  // The palette asks for these when it opens.
  const latest = useRef<() => Action[]>(() => []);
  useEffect(() => {
    const action = (
      id: string,
      label: string,
      icon: IconName,
      run: () => void,
      extra: Partial<Action> = {},
    ): Action => ({
      id: `ledger.${id}`,
      label,
      group: "ledger",
      icon,
      run,
      ...extra,
    });
    const runs = (headerAction: LedgerHeaderAction) => () =>
      headerAction.run !== undefined;
    latest.current = () =>
      shown && readable
        ? [
            action(
              "period",
              t("desktop.ledger.action.go_to_period"),
              "calendar",
              () => setPeriodOpen(true),
              { enabled: () => periodShown },
            ),
            action(
              "previous",
              t("desktop.ledger.period.previous"),
              "back",
              () => {
                const next = period && neighbourPeriod(period, -1);
                if (next) setPeriod(next);
              },
              {
                enabled: () =>
                  periodShown &&
                  period !== null &&
                  neighbourPeriod(period, -1) !== null,
              },
            ),
            action(
              "next",
              t("desktop.ledger.period.next"),
              "forward",
              () => {
                const next = period && neighbourPeriod(period, 1);
                if (next) setPeriod(next);
              },
              {
                enabled: () =>
                  periodShown &&
                  period !== null &&
                  neighbourPeriod(period, 1) !== null,
              },
            ),
            action(
              "import",
              t("desktop.ledger.action.import"),
              "upload",
              () => importAction.run?.(),
              { enabled: runs(importAction) },
            ),
            action(
              "export",
              t("desktop.ledger.action.export"),
              "download",
              () => exportAction.run?.(),
              { enabled: runs(exportAction) },
            ),
            action(
              "add",
              t("desktop.ledger.action.add_movement"),
              "plus",
              () => addAction.run?.(),
              { enabled: runs(addAction) },
            ),
            action(
              "add_invoice",
              t("desktop.ledger.invoices.action.add"),
              "plus",
              () => {
                setSection("invoices");
                addInvoiceAction.run?.();
              },
              { enabled: runs(addInvoiceAction) },
            ),
            action(
              "rule_from_selection",
              t("desktop.ledger.rules.from_selection"),
              "filter",
              () => openRuleFromSelection({ ids: [...movements.selection] }),
              { enabled: () => movements.selection.size > 0 },
            ),
            ...LEDGER_SECTIONS.map((value) =>
              action(
                `section.${value}`,
                t("desktop.ledger.action.section", {
                  section: sectionName(t, value),
                }),
                SECTION_ICONS[value],
                () => {
                  setSection(value);
                  page.current?.focus();
                },
                { enabled: () => value !== section },
              ),
            ),
            ...(section === "movements"
              ? (movementActions.current?.() ?? [])
              : []),
          ]
        : [];
  });
  useEffect(() => {
    contribute(() => latest.current());
    return () => contribute(null);
  }, [contribute]);

  // The panel stands beside the movements only while the grid is drawn.
  const drawnRows = periodWindow ? shownRows(periodWindow) : null;
  const gridShown =
    readable &&
    section === "movements" &&
    periodWindow !== null &&
    !(periodWindow.phase === "failed" && periodWindow.failure) &&
    drawnRows !== null &&
    !(drawnRows.total === 0 && stage.content.drafts.length === 0);
  const inspectorShown = view.inspectorOpen && gridShown;
  const { row, gridRoom } = useLedgerGridRoom({
    gridShown,
    inspectorShown,
    onFloor,
  });
  // A link's movement is asked of the page, which holds it until the grid
  // draws it. A read that ends empty or fails draws no grid, so the page
  // says the movement is not here; while it reads, the ask waits.
  const noMovementsGrid =
    readable &&
    section === "movements" &&
    periodWindow !== null &&
    ((periodWindow.phase === "failed" && !!periodWindow.failure) ||
      (drawnRows !== null &&
        drawnRows.total === 0 &&
        stage.content.drafts.length === 0));
  const [movementMissing, setMovementMissing] = useState(false);
  const { ask: movementAsk, done: movementDone } = linkedMovement;
  useEffect(() => {
    if (!movementAsk) return;
    setMovementMissing(noMovementsGrid);
    if (noMovementsGrid) movementDone();
  }, [movementAsk, movementDone, noMovementsGrid]);
  useEffect(() => {
    if (!noMovementsGrid) setMovementMissing(false);
  }, [noMovementsGrid]);
  // An ask for a section put away by the person goes with it.
  const { done: invoiceDone } = linkedInvoice;
  useEffect(() => {
    if (section !== "movements") {
      movementDone();
      setMovementMissing(false);
    }
    if (section !== "invoices") invoiceDone();
  }, [section, movementDone, invoiceDone]);

  return {
    panel,
    period,
    periodResolved,
    setPeriod,
    section,
    setSection,
    rulesArea,
    openRatios,
    readable,
    linkedMovement,
    linkedInvoice,
    periodShown,
    movements,
    periodWindow,
    reread,
    readAll,
    stage,
    registerMovements,
    readiness,
    recheckReadiness,
    periodOpen,
    setPeriodOpen,
    invoiceEditor,
    setInvoiceEditor,
    transfer,
    setTransfer,
    returnTransferFocus,
    inspectorContext,
    setInspectorContext,
    inspectorFocus,
    panelMode,
    setPanelMode,
    inspectorPanel,
    openInspector,
    closeInspector,
    onInspectorKey,
    shownImport,
    setShownImport,
    years,
    refreshYears,
    fallbackYear,
    shownPeriod,
    importAction,
    exportAction,
    pause,
    sealed,
    unread,
    focusDraft,
    setFocusDraft,
    shownFields,
    setShownFields,
    editing,
    ruleTarget,
    setRuleTarget,
    rulesVersion,
    setRulesVersion,
    toast,
    setToast,
    openRuleFromSelection,
    setupProps,
    addAction,
    addInvoiceAction,
    shownWindow,
    pageSets,
    counts,
    drawnRows,
    inspectorShown,
    row,
    gridRoom,
    movementMissing,
    setMovementMissing,
  };
}

export type LedgerPageState = ReturnType<typeof useLedgerPage>;
