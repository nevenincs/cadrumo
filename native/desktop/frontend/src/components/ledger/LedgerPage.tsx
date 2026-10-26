import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
  type RefObject,
} from "react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty";
import { Toast } from "@/components/ui/toast";
import { Icon, type IconName } from "@/components/ui/icon";
import type { PaneControl } from "../PaneHeader";
import type { Action } from "../../shell/actions";
import {
  LEDGER_SECTIONS,
  type LedgerSection,
  type LedgerView,
} from "../../shell/layout";
import type { LedgerPort } from "../../shell/ledger";
import {
  periodOf,
  stepPeriod,
  type LedgerPeriod,
} from "../../shell/ledgerGrammar";
import {
  periodCovering,
  type ImportedBatches,
} from "../../shell/ledgerImports";
import { useLedgerReadiness } from "../../shell/ledgerReadiness";
import {
  readinessSnapshot,
  shownRows,
  useLedgerWindow,
  windowProgress,
} from "../../shell/ledgerWindow";
import { useLedgerYears } from "../../shell/ledgerYears";
import {
  EMPTY_STAGE,
  reduceStage,
  stagedMovements,
} from "../../shell/ledgerStage";
import { useStrings } from "../../shell/strings";
import { localDay } from "../../shared/dates";
import {
  HeldButton,
  LedgerHeader,
  type LedgerHeaderAction,
  type SectionCount,
} from "./LedgerHeader";
import {
  SECTION_ICONS,
  TAB_SECTIONS,
  failureCode,
  periodText,
  sectionName,
  sectionTabId,
} from "./ledgerWords";
import { DocumentsSection } from "./documents/DocumentsSection";
import { InvoicesSection } from "./invoices/InvoicesSection";
import type { EditorTarget } from "./invoices/InvoiceEditor";
import { MovementsSection } from "./movements/MovementsSection";
import {
  useMovementsView,
  windowScope,
  type MovementsMemory,
} from "./movements/useMovementsView";
import { PeriodSelector } from "./PeriodSelector";
import { RowRevealNotice, useLinkedRow } from "./RowReveal";
import { ExportDialog } from "./transfer/ExportDialog";
import { useLedgerEditing } from "./editing/LedgerEditing";
import { ImportDialog } from "./transfer/ImportDialog";
import { dayText } from "./transfer/transferWords";
import type { OpenRuleFromSelection } from "../../shell/ledgerCommands";
import { HealthSection } from "./setup/HealthSection";
import { RegistersSection } from "./setup/RegistersSection";
import { RuleDialog, type RuleDialogTarget } from "./setup/RuleDialog";
import { RulesSection, type RulesArea } from "./setup/RulesSection";
import type { SetupProps } from "./setup/setupProps";
import {
  NO_FILTERS,
  TO_CLASSIFY_REASON,
  readinessSets,
} from "./movements/movementsModel";
import { ReadinessStrip } from "./movements/ReadinessStrip";
import { exactly } from "@/components/ui/dataGridModel";
import type { SectionInspectorContext } from "./inspector/inspectorContext";
import type { InspectorSection } from "./inspector/inspectorModel";
import { LedgerInspector } from "./inspector/LedgerInspector";
import type { InspectorFocus } from "./inspector/MovementInspector";
import { rowFloor, type RightPanelMode } from "./inspector/RightPanel";
import { GridRoomContext } from "./gridRoom";
import { MatchQueue } from "./matching/MatchQueue";
import { useSealedMovements } from "./useSealedMovements";
import { PausedBanner, usePagePause, WritePauseContext } from "./WritePause";

/** How long a page toast stays. */
const TOAST_MS = 4000;
/** What the page keeps of itself while it is put away, for one profile:
 * the period it showed and how its movements were looked at. Held in memory
 * only. */
export type LedgerMemory = {
  period?: LedgerPeriod | null;
  movements?: MovementsMemory;
};

/**
 * The Ledger page: a period's movements, invoices and documents, and the
 * ledger's setup, under the pane's own header. What it reads lives in its
 * memory only and goes with the profile; the person's layout of it is kept
 * by the window as presentation, never with a value in it.
 */
export function LedgerPage({
  port,
  reader,
  withheld,
  locale,
  shown,
  page,
  view,
  onViewChange,
  memory,
  pane,
  contribute,
  copy,
  onFloor,
}: {
  port: LedgerPort;
  /** Whose ledger, or null while the account withholds it. */
  reader: string | null;
  /** What stands in the page while the account withholds the ledger. */
  withheld: ReactNode;
  locale: string;
  shown: boolean;
  page: RefObject<HTMLElement | null>;
  view: LedgerView;
  onViewChange(update: (current: LedgerView) => LedgerView): void;
  memory: RefObject<LedgerMemory>;
  /** The pane's title and controls, which the page's header carries. */
  pane: {
    title: string;
    controls: PaneControl[];
    onToggleMaximize(): void;
  };
  /** Hands the window's palette what the page offers, read when it opens. */
  contribute(actions: (() => Action[]) | null): void;
  /** Puts text on the clipboard through the host. */
  copy(text: string): Promise<void>;
  /** Tells the window the least width the page needs beside the agent, in
   * CSS pixels, or null where it needs no more than any pane. */
  onFloor?(width: number | null): void;
}) {
  const t = useStrings();
  const panel = useId();
  const today = localDay();
  const [period, setPeriodNow] = useState<LedgerPeriod | null>(() =>
    memory.current.period !== undefined
      ? memory.current.period
      : periodOf(today, "quarter"),
  );
  const setPeriod = (next: LedgerPeriod | null) => {
    memory.current.period = next;
    setPeriodNow(next);
  };
  const section = view.section;
  // The Rules section's area to open on, where another section asked for
  // one; it is forgotten once the page leaves Rules.
  const [rulesArea, setRulesArea] = useState<RulesArea>();
  const setSection = (next: LedgerSection) => {
    setPeriodOpen(false);
    if (next !== "rules") setRulesArea(undefined);
    onViewChange((current) => ({ ...current, section: next }));
  };
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
    movementsShown,
    windowScope(period === null, movements),
  );
  // What is staged lives here, with the page, so it stays while a section
  // is put away and goes with the profile.
  const [stage, dispatchStage] = useReducer(reduceStage, EMPTY_STAGE);
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

  // The panel beside the grid: the To match queue or the inspector. Alt+I
  // is handled here, once: it opens the inspector and focuses its index,
  // moves focus to the index from the grid, or closes it from inside and
  // hands focus back to the active cell.
  const [inspectorContext, setInspectorContext] =
    useState<SectionInspectorContext | null>(null);
  const [inspectorFocus, setInspectorFocus] = useState<InspectorFocus>({
    section: null,
    index: false,
    tick: 0,
  });
  const [panelMode, setPanelMode] = useState<RightPanelMode>(
    view.savedView === "to_match" ? "match" : "movement",
  );
  // Choosing the To match view opens the panel on its queue, its side
  // list; leaving the view leaves the panel as it is.
  const panelView = useRef(view.savedView);
  useEffect(() => {
    if (panelView.current === view.savedView) return;
    panelView.current = view.savedView;
    if (view.savedView !== "to_match") return;
    setPanelMode("match");
    onViewChange((current) => ({ ...current, inspectorOpen: true }));
  }, [view.savedView, onViewChange]);
  const inspectorPanel = useRef<HTMLElement | null>(null);
  const setInspectorOpen = (inspectorOpen: boolean) =>
    onViewChange((current) => ({ ...current, inspectorOpen }));
  const openInspector = (section: InspectorSection | null, index = false) => {
    setPanelMode("movement");
    setInspectorOpen(true);
    setInspectorFocus((held) => ({ section, index, tick: held.tick + 1 }));
  };
  const closeInspector = () => {
    setInspectorOpen(false);
    inspectorContext?.focusActive();
  };
  const onInspectorKey = (event: KeyboardEvent<HTMLDivElement>) => {
    if (
      event.code !== "KeyI" ||
      !exactly(event, { alt: true }) ||
      event.nativeEvent.isComposing
    )
      return;
    event.preventDefault();
    if (!view.inspectorOpen) openInspector(null, true);
    else if (inspectorPanel.current?.contains(document.activeElement))
      closeInspector();
    else {
      setPanelMode("movement");
      setInspectorFocus((held) => ({
        section: null,
        index: true,
        tick: held.tick + 1,
      }));
    }
  };
  // What an import brought in, as the person asked to see it.
  const [shownImport, setShownImport] = useState<ImportedBatches | null>(null);
  // Read with the page, so the period list never grows under the pointer.
  const { years, refresh: refreshYears } = useLedgerYears(
    port,
    reader,
    readable,
  );
  const numbers = useMemo(() => new Intl.NumberFormat(locale), [locale]);
  const fallbackYear = Number(today.slice(0, 4));
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
    () => [
      ...new Set([...movements.selection, ...stagedMovements(stage.content)]),
    ],
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
  const editing = useLedgerEditing({
    port,
    period,
    rows: periodWindow ? (shownRows(periodWindow)?.rows ?? null) : null,
    stage,
    dispatch: dispatchStage,
    reread,
    onRekey: (from, to) => {
      if (!movements.selection.has(from)) return;
      const next = new Set(movements.selection);
      next.delete(from);
      next.add(to);
      movements.setSelection(next);
    },
    onShowRows: (ids) => {
      setSection("movements");
      movements.setSelection(new Set(ids));
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
    const timer = window.setTimeout(() => setToast(null), TOAST_MS);
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
                const next = period && stepPeriod(period, -1);
                if (next) setPeriod(next);
              },
              { enabled: () => periodShown && period !== null },
            ),
            action(
              "next",
              t("desktop.ledger.period.next"),
              "forward",
              () => {
                const next = period && stepPeriod(period, 1);
                if (next) setPeriod(next);
              },
              { enabled: () => periodShown && period !== null },
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

  const isTab = (TAB_SECTIONS as readonly string[]).includes(section);
  let body: ReactNode;
  if (!readable || periodWindow === null) body = withheld;
  else if (section === "invoices")
    body = (
      <InvoicesSection
        port={port}
        reader={reader}
        locale={locale}
        period={period}
        shown={shown}
        editor={invoiceEditor}
        onEditor={setInvoiceEditor}
        copy={copy}
        onPeriod={setPeriod}
        linked={linkedInvoice}
      />
    );
  else if (section === "rules")
    body = (
      <RulesSection
        {...setupProps}
        onOpenRule={setRuleTarget}
        rulesVersion={rulesVersion}
        initialArea={rulesArea}
      />
    );
  else if (section === "registers") body = <RegistersSection {...setupProps} />;
  else if (section === "health")
    body = (
      <HealthSection
        {...setupProps}
        readiness={readiness}
        onShowReadiness={(filter) => {
          movements.setFilters({ ...NO_FILTERS, readiness: filter });
          setSection("movements");
        }}
        onShowReason={(reason) => {
          // A movement still to classify is its own filter, not a reason.
          movements.setFilters(
            reason === TO_CLASSIFY_REASON
              ? { ...NO_FILTERS, readiness: "to_classify" }
              : { ...NO_FILTERS, reason },
          );
          setSection("movements");
        }}
        onShowInvoices={() => setSection("invoices")}
        onReset={() => {
          reread();
          refreshYears();
        }}
      />
    );
  else if (section === "documents")
    body = (
      <DocumentsSection
        port={port}
        reader={reader}
        locale={locale}
        shown={shown}
        rows={shownRows(periodWindow)?.rows ?? null}
        stage={stage}
        onStage={editing.onStage}
      />
    );
  else if (section !== "movements")
    body = (
      <EmptyState
        className="ledger-placeholder"
        icon={SECTION_ICONS[section]}
        heading={sectionName(t, section)}
      />
    );
  else if (periodWindow.phase === "failed" && periodWindow.failure)
    body = (
      <EmptyState
        className="ledger-failed"
        icon="alert"
        description={
          <span key={periodWindow.generation} role="alert">
            {t("desktop.ledger.failed")}{" "}
            <code className="font-mono text-xs">
              {failureCode(periodWindow.failure)}
            </code>
          </span>
        }
      >
        <Button variant="outline" onClick={reread}>
          {t("desktop.ledger.retry")}
        </Button>
      </EmptyState>
    );
  else {
    const rows = shownRows(periodWindow);
    const progress = windowProgress(periodWindow);
    const reading =
      progress.total === null
        ? t("desktop.ledger.loading")
        : t("desktop.ledger.reading", {
            loaded: numbers.format(progress.loaded),
            total: numbers.format(progress.total),
          });
    if (rows === null)
      body = (
        <EmptyState
          className="ledger-loading"
          role="status"
          busy
          description={reading}
        />
      );
    else if (rows.total === 0 && stage.content.drafts.length === 0)
      body = (
        <EmptyState
          className="ledger-empty"
          icon="ledger"
          description={
            period === null
              ? t("desktop.ledger.empty_all")
              : t("desktop.ledger.empty", { period: shownPeriod })
          }
        >
          <div className="flex flex-wrap justify-center gap-2">
            <HeldButton
              action={importAction}
              name={t("desktop.ledger.action.import")}
            >
              <Icon name="upload" />
              {t("desktop.ledger.action.import")}
            </HeldButton>
            <HeldButton
              action={addAction}
              name={t("desktop.ledger.action.add_movement")}
            >
              <Icon name="plus" />
              {t("desktop.ledger.action.add")}
            </HeldButton>
          </div>
        </EmptyState>
      );
    else
      body = (
        <>
          {shownImport && (
            <p className="ledger-shown-import flex flex-wrap items-center gap-2 px-3 pt-3 text-sm">
              {t("desktop.ledger.import.shown", {
                from: dayText(locale, shownImport.span.from),
                to: dayText(locale, shownImport.span.to),
              })}
              <Button
                variant="link"
                size="xs"
                onClick={() => setShownImport(null)}
              >
                {t("desktop.ledger.import.shown_clear")}
              </Button>
            </p>
          )}
          <MovementsSection
            port={port}
            reader={reader}
            period={period}
            periodWindow={periodWindow}
            readAll={readAll}
            readiness={readiness}
            onCheckReadiness={recheckReadiness}
            movements={movements}
            stage={stage}
            onStage={editing.onStage}
            editing={{
              openReview: editing.openReview,
              focusDraft,
              onDraftFocused: () => setFocusDraft(null),
              sealed,
            }}
            view={view}
            onViewChange={onViewChange}
            locale={locale}
            onPeriod={setPeriod}
            register={registerMovements}
            onMakeRule={openRuleFromSelection}
            onOpenRatios={openRatios}
            onOpenInspector={(at) => openInspector(at)}
            onInspector={setInspectorContext}
            shownImport={shownImport}
            onImportCleared={() => setShownImport(null)}
            linked={linkedMovement}
          />
        </>
      );
  }

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
  // The grid keeps the least it needs to show any scrolling column whole,
  // with what its column draws around it, beside the panel or alone; the
  // window makes the room from the agent column rather than squeezing it.
  const row = useRef<HTMLDivElement>(null);
  const [gridLeast, setGridLeast] = useState<number | null>(null);
  const [columnFloor, setColumnFloor] = useState<number | null>(null);
  useLayoutEffect(() => {
    const column = row.current?.firstElementChild;
    const drawn = column?.querySelector<HTMLElement>("[data-slot=data-grid]");
    if (!gridShown || gridLeast === null || !column || !drawn) {
      setColumnFloor(null);
      return;
    }
    // What the column draws around the grid, read from its styles: a
    // measured difference of widths is wrong while the panel opening is
    // still being laid out.
    let frame = 0;
    for (
      let around = drawn.parentElement;
      around && around !== column.parentElement;
      around = around.parentElement
    ) {
      const style = getComputedStyle(around);
      frame +=
        parseFloat(style.paddingLeft) +
        parseFloat(style.paddingRight) +
        parseFloat(style.borderLeftWidth) +
        parseFloat(style.borderRightWidth);
    }
    setColumnFloor(Math.ceil(gridLeast + frame));
  }, [gridShown, gridLeast]);
  const gridRoom = useMemo(
    () => ({ columnFloor, onLeast: setGridLeast }),
    [columnFloor],
  );
  useLayoutEffect(() => {
    if (!onFloor) return;
    onFloor(gridShown ? rowFloor(columnFloor, inspectorShown) : null);
    return () => onFloor(null);
  }, [gridShown, inspectorShown, columnFloor, onFloor]);

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

  // Export shows the page's own pills for the page's period, so that both
  // count the same movements; a pill there filters the grid to them.
  const exportReadiness =
    transfer === "export" && shownWindow ? (
      <ReadinessStrip
        readiness={readiness}
        sets={pageSets}
        filters={movements.filters}
        locale={locale}
        unsaved={editing.tally.units}
        stagedClassify={0}
        periodName={shownPeriod}
        onCheck={recheckReadiness}
        onPill={(filter) => {
          if (!filter) return;
          movements.setFilters({ ...NO_FILTERS, readiness: filter });
          setSection("movements");
          setTransfer(null);
        }}
        onReason={(reason) => {
          if (!reason) return;
          movements.setFilters(
            reason === TO_CLASSIFY_REASON
              ? { ...NO_FILTERS, readiness: "to_classify" }
              : { ...NO_FILTERS, reason },
          );
          setSection("movements");
          setTransfer(null);
        }}
      />
    ) : undefined;

  return (
    <WritePauseContext.Provider value={pause}>
      {/* The page's own keys reach every part of it, the header included;
          the wrapper draws nothing of its own. */}
      <div data-ledger-root="" className="contents">
        <LedgerHeader
          title={pane.title}
          controls={pane.controls}
          onToggleMaximize={pane.onToggleMaximize}
          section={readable ? section : undefined}
          onSection={setSection}
          counts={counts}
          panel={panel}
          period={
            periodShown && (
              <PeriodSelector
                value={period}
                onChange={setPeriod}
                label={t("desktop.ledger.period.label")}
                years={years}
                locale={locale}
                fallbackYear={fallbackYear}
                open={periodOpen}
                onOpenChange={setPeriodOpen}
              />
            )
          }
          importAction={importAction}
          exportAction={exportAction}
          addAction={
            section === "movements"
              ? addAction
              : section === "invoices"
                ? addInvoiceAction
                : undefined
          }
          addName={
            section === "invoices"
              ? t("desktop.ledger.invoices.action.add")
              : undefined
          }
        />
        <section
          ref={page}
          tabIndex={-1}
          aria-label={t("desktop.ledger.title")}
          aria-busy={periodWindow?.phase === "reading" || undefined}
          className="ledger-page flex min-h-0 flex-1 flex-col overflow-y-auto bg-background focus-visible:-outline-offset-2"
        >
          <div
            id={panel}
            // Withheld, no section is shown: the page says why instead.
            role={readable ? (isTab ? "tabpanel" : "region") : undefined}
            aria-labelledby={
              readable && isTab ? sectionTabId(panel, section) : undefined
            }
            aria-label={
              readable && !isTab ? sectionName(t, section) : undefined
            }
            className="flex min-h-0 flex-1 flex-col"
          >
            {readable && (
              <PausedBanner
                pause={pause}
                onShow={(ids) => {
                  setSection("movements");
                  movements.setSelection(new Set(ids));
                }}
              />
            )}
            <GridRoomContext.Provider value={gridRoom}>
              <div
                ref={row}
                className="flex min-h-0 flex-1"
                onKeyDown={onInspectorKey}
              >
                {/* The grid scrolls within what the panel leaves it; resizing
                the panel keeps it its own width. */}
                <div className="flex min-h-0 min-w-0 flex-1 flex-col">
                  {movementMissing && (
                    <div className="px-3 pt-3">
                      <RowRevealNotice
                        notice={{ kind: "missing" }}
                        dismiss={() => setMovementMissing(false)}
                        hidden={t("desktop.ledger.reveal.movement_hidden")}
                        missing={t("desktop.ledger.reveal.movement_missing")}
                      />
                    </div>
                  )}
                  {body}
                </div>
                {inspectorShown && periodWindow && (
                  <LedgerInspector
                    port={port}
                    reader={reader}
                    rows={shownRows(periodWindow)?.rows ?? []}
                    generation={periodWindow.generation}
                    stage={stage}
                    onStage={editing.onStage}
                    sealed={sealed}
                    unread={unread}
                    selection={movements.selection}
                    onSelection={movements.setSelection}
                    context={inspectorContext}
                    mode={panelMode}
                    onMode={setPanelMode}
                    matchPanel={
                      <MatchQueue
                        port={port}
                        reader={reader}
                        shown={panelMode === "match"}
                        rows={shownRows(periodWindow)?.rows ?? null}
                        generation={
                          periodWindow.phase === "ready"
                            ? periodWindow.generation
                            : null
                        }
                        stage={stage}
                        onStage={editing.onStage}
                        onChoose={(id) => {
                          movements.setSelection(new Set([id]));
                          openInspector("invoice");
                        }}
                        locale={locale}
                      />
                    }
                    width={view.inspectorWidth}
                    onWidth={(inspectorWidth) =>
                      onViewChange((current) => ({
                        ...current,
                        inspectorWidth,
                      }))
                    }
                    focus={inspectorFocus}
                    locale={locale}
                    panelRef={inspectorPanel}
                    onClose={closeInspector}
                    onOpenInvoice={(invoiceId) => {
                      setSection("invoices");
                      setInvoiceEditor({ kind: "open", invoiceId });
                    }}
                    onExport={() => setTransfer("export")}
                    onMakeRule={openRuleFromSelection}
                    copy={copy}
                  />
                )}
              </div>
            </GridRoomContext.Provider>
          </div>
        </section>
        {readable && editing.dock}
        {readable && ruleTarget && (
          <RuleDialog
            port={port}
            reader={reader}
            target={ruleTarget}
            rows={setupProps.rows}
            onStage={editing.onStage}
            onSaved={(_rule, place) => {
              setRulesVersion((value) => value + 1);
              setRuleTarget(null);
              setToast(t("desktop.ledger.rules.saved_toast", { place }));
            }}
            onClose={() => setRuleTarget(null)}
            // Opened from the grid, it hands the keyboard back to the grid's
            // active cell; the Rules section's own opener takes it otherwise.
            onClosed={
              ruleTarget.kind === "seed"
                ? () => inspectorContext?.focusActive()
                : undefined
            }
          />
        )}
        {readable && transfer === "import" && (
          <ImportDialog
            port={port}
            locale={locale}
            period={period}
            years={years}
            fallbackYear={fallbackYear}
            onClose={() => setTransfer(null)}
            onWritten={() => {
              reread();
              refreshYears();
            }}
            onShowImported={(shown) => {
              setShownImport(shown);
              setPeriod(periodCovering(shown.span));
              setSection("movements");
            }}
            onShowDocuments={() => setSection("documents")}
            onCloseAutoFocus={returnTransferFocus}
          />
        )}
        {readable && transfer === "export" && (
          <ExportDialog
            port={port}
            locale={locale}
            period={period}
            years={years}
            fallbackYear={fallbackYear}
            format={view.exportFormat}
            onFormat={(exportFormat) =>
              onViewChange((current) => ({ ...current, exportFormat }))
            }
            staged={editing.tally.units}
            onReviewStaged={editing.openReview}
            readiness={exportReadiness}
            copy={copy}
            onClose={() => setTransfer(null)}
            onCloseAutoFocus={returnTransferFocus}
          />
        )}
        <Toast className="ledger-page-toast">{toast}</Toast>
      </div>
    </WritePauseContext.Provider>
  );
}
