import type { ReactNode, RefObject } from "react";
import type { Action } from "../../shell/actions";
import type { LedgerView } from "../../shell/layout";
import type { LedgerPort } from "../../shell/ledger";
import type { LedgerPeriod } from "../../shell/ledgerGrammar";
import { useStrings } from "../../shell/strings";
import type { PaneControl } from "../PaneHeader";
import { LedgerHeader } from "./LedgerHeader";
import { LedgerPageBody } from "./LedgerPageBody";
import { LedgerPageDialogs } from "./LedgerPageDialogs";
import { LedgerPageInspector } from "./LedgerPageInspector";
import { PeriodSelector } from "./PeriodSelector";
import { RowRevealNotice } from "./RowReveal";
import { PausedBanner, WritePauseContext } from "./WritePause";
import { GridRoomContext } from "./gridRoom";
import { TAB_SECTIONS, sectionName, sectionTabId } from "./ledgerWords";
import type { MovementsMemory } from "./movements/useMovementsView";
import type { RegistersArea } from "./setup/RegistersSection";
import type { CounterpartyAsk } from "../../shell/counterpartyAsk";
import { LedgerSuggestions } from "./suggestions/SuggestionsProvider";
import { useLedgerPage } from "./useLedgerPage";

/** What the page keeps of itself while it is put away, for one profile:
 * the period it showed and how its movements were looked at. Held in memory
 * only. */
export type LedgerMemory = {
  period?: LedgerPeriod | null;
  movements?: MovementsMemory;
  /** The Registers area another part of the window asked the page to open
   * on; it is forgotten once the page leaves Registers. */
  registersArea?: RegistersArea;
  /** What a way out elsewhere in the window asked of the counterparties; the
   * page opens Rules › Counterparties on it and forgets it once taken. */
  counterpartyAsk?: CounterpartyAsk;
};

/**
 * The Ledger page: a period's movements, invoices and documents, and the
 * ledger's setup, under the pane's own header. What it reads lives in its
 * memory only and goes with the profile; the person's layout of it is kept
 * by the window as presentation, never with a value in it.
 */
export type LedgerPageProps = {
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
  /** Reads the host's clipboard; without it the grid keeps to the browser's
   * own paste event. */
  paste?(): Promise<string>;
  /** Opens an official address in the system browser, as the window does
   * for any external link. */
  onOpenLink?(url: string): void;
  /** Tells the window the least width the page needs beside the agent, in
   * CSS pixels, or null where it needs no more than any pane. */
  onFloor?(width: number | null): void;
};

export function LedgerPage(props: LedgerPageProps) {
  const t = useStrings();
  const model = useLedgerPage(props);
  const { port, reader, locale, page, pane } = props;
  const {
    panel,
    period,
    periodResolved,
    setPeriod,
    section,
    setSection,
    readable,
    periodShown,
    movements,
    periodWindow,
    stage,
    periodOpen,
    setPeriodOpen,
    onInspectorKey,
    years,
    fallbackYear,
    importAction,
    exportAction,
    pause,
    addAction,
    addInvoiceAction,
    counts,
    drawnRows,
    row,
    gridRoom,
    movementMissing,
    setMovementMissing,
  } = model;
  const isTab = (TAB_SECTIONS as readonly string[]).includes(section);
  return (
    <WritePauseContext.Provider value={pause}>
      <LedgerSuggestions
        port={port}
        reader={reader}
        rows={drawnRows?.rows ?? null}
        stage={stage.content}
        applied={stage.applied}
        locale={locale}
      >
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
                  pending={!periodResolved}
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
            // Its grids take Alt+Left and Alt+Right; the window's back and
            // forward leave them the keys and keep the pointer's buttons.
            data-keeps-alt-arrows=""
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
                    <LedgerPageBody props={props} model={model} />
                  </div>
                  <LedgerPageInspector props={props} model={model} />
                </div>
              </GridRoomContext.Provider>
            </div>
          </section>
          <LedgerPageDialogs props={props} model={model} />
        </div>
      </LedgerSuggestions>
    </WritePauseContext.Provider>
  );
}
