import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useReducer,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from "react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty";
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
  shownRows,
  useLedgerWindow,
  windowProgress,
} from "../../shell/ledgerWindow";
import { useLedgerYears } from "../../shell/ledgerYears";
import { EMPTY_STAGE, reduceStage } from "../../shell/ledgerStage";
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
import { ExportDialog } from "./transfer/ExportDialog";
import { useLedgerEditing, type LeaveGuard } from "./editing/LedgerEditing";
import { ImportDialog } from "./transfer/ImportDialog";
import { dayText } from "./transfer/transferWords";
import type { OpenRuleFromSelection } from "../../shell/ledgerCommands";
import { HealthSection } from "./setup/HealthSection";
import { RegistersSection } from "./setup/RegistersSection";
import { RuleDialog, type RuleDialogTarget } from "./setup/RuleDialog";
import { RulesSection } from "./setup/RulesSection";
import type { SetupProps } from "./setup/setupProps";
import { NO_FILTERS, TO_CLASSIFY_REASON } from "./movements/movementsModel";

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
  guardLeave,
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
  /** Hands the shell the guard that asks before staged work is dropped. */
  guardLeave?: (guard: LeaveGuard | null) => void;
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
  const setSection = (next: LedgerSection) => {
    setPeriodOpen(false);
    onViewChange((current) => ({ ...current, section: next }));
  };
  const readable = reader !== null;
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
  const readiness = useLedgerReadiness(
    port,
    reader,
    period,
    periodWindow?.phase === "ready" ? periodWindow.generation : null,
  );
  const [periodOpen, setPeriodOpen] = useState(false);
  // The invoice being added or corrected; it goes with the profile.
  const [invoiceEditor, setInvoiceEditor] = useState<EditorTarget | null>(null);
  useEffect(() => setInvoiceEditor(null), [reader]);
  const [transfer, setTransfer] = useState<"import" | "export" | null>(null);
  // What an import brought in, as the person asked to see it.
  const [shownImport, setShownImport] = useState<ImportedBatches | null>(null);
  const { years, refresh: refreshYears } = useLedgerYears(
    port,
    reader,
    periodOpen ||
      transfer !== null ||
      section === "rules" ||
      section === "registers",
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
    guardLeave,
    locale,
  });
  // The rule dialog opens over whatever section is shown: from Rules, or
  // from a selection or a group of movements.
  const [ruleTarget, setRuleTarget] = useState<RuleDialogTarget | null>(null);
  const [rulesVersion, setRulesVersion] = useState(0);
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
  const toClassify = shownWindow
    ? shownWindow.rows.filter((row) => row.review_status === "pending").length
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
      />
    );
  else if (section === "rules")
    body = (
      <RulesSection
        {...setupProps}
        onOpenRule={setRuleTarget}
        rulesVersion={rulesVersion}
      />
    );
  else if (section === "registers") body = <RegistersSection {...setupProps} />;
  else if (section === "health")
    body = (
      <HealthSection
        {...setupProps}
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
            movements={movements}
            stage={stage}
            onStage={editing.onStage}
            editing={{
              openReview: editing.openReview,
              focusDraft,
              onDraftFocused: () => setFocusDraft(null),
            }}
            view={view}
            onViewChange={onViewChange}
            locale={locale}
            onPeriod={setPeriod}
            register={registerMovements}
            shownImport={shownImport}
            onImportCleared={() => setShownImport(null)}
          />
        </>
      );
  }

  return (
    <>
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
          aria-label={readable && !isTab ? sectionName(t, section) : undefined}
          className="flex min-h-0 flex-1 flex-col"
        >
          {readable && editing.banner}
          {body}
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
          onSaved={() => {
            setRulesVersion((value) => value + 1);
            setRuleTarget(null);
          }}
          onClose={() => setRuleTarget(null)}
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
          copy={copy}
          onClose={() => setTransfer(null)}
        />
      )}
    </>
  );
}
