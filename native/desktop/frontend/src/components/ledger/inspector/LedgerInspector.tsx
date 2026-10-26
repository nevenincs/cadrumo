import { useEffect, useMemo, useState, type ReactNode, type Ref } from "react";
import { EmptyState } from "@/components/ui/empty";
import { Toast } from "@/components/ui/toast";
import type { LedgerPort, LedgerRow } from "../../../shell/ledger";
import type { OpenRuleFromSelection } from "../../../shell/ledgerCommands";
import { useOwnAccounts } from "../../../shell/ledgerMovementReads";
import type { StageEvent, StageState } from "../../../shell/ledgerStage";
import { useStrings } from "../../../shell/strings";
import { ActionDialog, type ActionRequest } from "./ActionDialog";
import type { SectionInspectorContext } from "./inspectorContext";
import { MovementInspector, type InspectorFocus } from "./MovementInspector";
import { RightPanel, type RightPanelMode } from "./RightPanel";
import { SelectionInspector } from "./SelectionInspector";
import { SplitDialog } from "./SplitDialog";

/** How long a confirmation stays on screen. */
const TOAST_MS = 4000;

/**
 * The panel beside the Movements grid: the To match pair queue, or the
 * inspector of what is selected, one movement or several, with the
 * dialogs its actions open. It shows stored values, and stages every
 * change into the page's changes.
 */
export function LedgerInspector({
  port,
  reader,
  rows,
  generation,
  stage,
  onStage,
  sealed,
  unread,
  selection,
  onSelection,
  context,
  mode,
  onMode,
  matchPanel,
  width,
  onWidth,
  focus,
  locale,
  panelRef,
  onClose,
  onOpenInvoice,
  onExport,
  onMakeRule,
  copy,
}: {
  port: LedgerPort;
  /** Whose ledger it is. */
  reader: string | null;
  rows: readonly LedgerRow[];
  generation: number | string;
  stage: StageState;
  onStage: (event: StageEvent) => void;
  /** Movements a finalized declaration cites, as far as the page read. */
  sealed: ReadonlySet<string>;
  /** Movements whose sealed state the page could not read. */
  unread: ReadonlySet<string>;
  selection: ReadonlySet<string>;
  onSelection: (next: Set<string>) => void;
  context: SectionInspectorContext | null;
  mode: RightPanelMode;
  onMode: (mode: RightPanelMode) => void;
  matchPanel?: ReactNode;
  width: number | null;
  onWidth: (width: number | null) => void;
  focus: InspectorFocus;
  locale: string;
  panelRef?: Ref<HTMLElement>;
  onClose: () => void;
  onOpenInvoice: (invoiceId: string) => void;
  onExport?: () => void;
  onMakeRule?: OpenRuleFromSelection;
  copy: (text: string) => Promise<void>;
}) {
  const t = useStrings();
  const byId = useMemo(
    () => new Map(rows.map((row) => [row.transaction.transaction_id, row])),
    [rows],
  );
  // The own accounts' labels, read once the panel is shown, where the
  // section has not read them.
  const ownAccounts = useOwnAccounts(port, reader, true);
  const accounts = context?.accounts ?? ownAccounts;
  const shared = useMemo(
    () => (context && !context.accounts ? { ...context, accounts } : context),
    [context, accounts],
  );
  const ids = useMemo(
    () => [...selection].filter((id) => byId.has(id)),
    [selection, byId],
  );
  const [action, setAction] = useState<ActionRequest | null>(null);
  const [splitting, setSplitting] = useState<LedgerRow | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), TOAST_MS);
    return () => window.clearTimeout(timer);
  }, [toast]);
  const show = (id: string) => {
    onMode("movement");
    onSelection(new Set([id]));
  };

  const one = ids.length === 1 ? byId.get(ids[0]!)! : null;
  let body: ReactNode;
  if (one)
    body = (
      <MovementInspector
        key={one.transaction.transaction_id}
        port={port}
        row={one}
        rows={rows}
        generation={generation}
        stage={stage}
        onStage={onStage}
        classify={context?.classify ?? null}
        issues={context?.issues.get(one.transaction.transaction_id) ?? []}
        checked={context?.checked ?? false}
        duplicate={
          context?.duplicates.has(one.transaction.transaction_id) ?? false
        }
        accounts={accounts}
        focus={focus}
        locale={locale}
        onClose={onClose}
        onShow={show}
        onOpenInvoice={onOpenInvoice}
        onAction={setAction}
        onSplit={setSplitting}
        onSelectCohort={(cohort) => onSelection(new Set(cohort))}
        copy={copy}
        say={setToast}
      />
    );
  else if (ids.length > 1)
    body = (
      <SelectionInspector
        port={port}
        ids={ids}
        rows={byId}
        context={shared}
        generation={generation}
        stage={stage}
        onStage={onStage}
        sealed={sealed}
        unread={unread}
        locale={locale}
        onClearSelection={() => onSelection(new Set())}
        onKeepVisible={() =>
          onSelection(new Set(ids.filter((id) => context?.visible.has(id))))
        }
        onAction={setAction}
        onShow={show}
        onMakeRule={onMakeRule}
        onExport={onExport}
        copy={copy}
        say={setToast}
      />
    );
  else
    body = (
      <EmptyState
        className="ledger-inspector-empty"
        icon="info"
        description={t("desktop.ledger.inspector.nothing")}
      />
    );

  return (
    <>
      <RightPanel
        mode={mode}
        onMode={onMode}
        matchPanel={matchPanel}
        width={width}
        onWidth={onWidth}
        panelRef={panelRef}
        onKeyDown={(event) => {
          if (
            event.key !== "Escape" ||
            event.defaultPrevented ||
            event.nativeEvent.isComposing ||
            (event.target as HTMLElement).closest(
              "input, textarea, select, [role=menu], [role=listbox], [role=dialog]",
            )
          )
            return;
          event.preventDefault();
          onClose();
        }}
      >
        {body}
      </RightPanel>
      {action && (
        <ActionDialog
          port={port}
          request={action}
          rows={byId}
          sealed={sealed}
          onStage={onStage}
          onClose={() => setAction(null)}
          say={setToast}
        />
      )}
      {splitting && (
        <SplitDialog
          row={splitting}
          locale={locale}
          onStage={onStage}
          onClose={() => setSplitting(null)}
          say={setToast}
        />
      )}
      <Toast className="ledger-inspector-toast">{toast}</Toast>
    </>
  );
}
