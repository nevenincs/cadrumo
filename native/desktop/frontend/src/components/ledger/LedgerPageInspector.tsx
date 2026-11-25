import { useState } from "react";
import type { PropertySet } from "../../shell/ledgerPlan";
import { shownRows } from "../../shell/ledgerWindow";
import type { LedgerPageProps } from "./LedgerPage";
import { LedgerInspector } from "./inspector/LedgerInspector";
import { MatchQueue } from "./matching/MatchQueue";
import type { LedgerPageState } from "./useLedgerPage";

/** The optional inspector or matching queue beside the movement grid. */
export function LedgerPageInspector({
  props,
  model,
}: {
  props: LedgerPageProps;
  model: LedgerPageState;
}) {
  const { port, reader, locale, view, onViewChange, copy } = props;
  const {
    setSection,
    movements,
    periodWindow,
    stage,
    setInvoiceEditor,
    setTransfer,
    inspectorContext,
    inspectorFocus,
    panelMode,
    setPanelMode,
    inspectorPanel,
    openInspector,
    closeInspector,
    sealed,
    unread,
    editing,
    openRuleFromSelection,
    inspectorShown,
    reread,
  } = model;
  // Properties copied from one movement, kept for the page's life so they
  // can be pasted after the inspector has closed and another selection made.
  const [copied, setCopied] = useState<PropertySet | null>(null);
  return (
    <>
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
                periodWindow.phase === "ready" ? periodWindow.generation : null
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
          onWritten={reread}
          copy={copy}
          copied={copied}
          onCopied={setCopied}
        />
      )}
    </>
  );
}
