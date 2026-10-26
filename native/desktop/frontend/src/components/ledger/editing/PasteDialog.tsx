import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useStrings } from "../../../shell/strings";
import type { PastePlan } from "./editingModel";
import { refusalText } from "./editingWords";

/**
 * What a paste of several rows, or one that touches a movement's identity,
 * would stage, before anything is staged: the target columns and how many
 * cells change, are refused, fall past the grid or are left blank, and how
 * many movements take a new reference. Paste stages it; Cancel leaves the
 * grid as it was.
 */
export function PasteDialog({
  plan,
  columns,
  singleWrites,
  onPaste,
  onCancel,
  onCloseAutoFocus,
}: {
  plan: PastePlan;
  /** The target columns' names, in drawn order. */
  columns: string[];
  /** Saves one at a time the paste adds to the next apply. */
  singleWrites: number;
  onPaste: () => void;
  onCancel: () => void;
  /** Where the focus goes once the dialog has gone. */
  onCloseAutoFocus?: (event: Event) => void;
}) {
  const t = useStrings();
  const rows: [string, string][] = [
    [t("desktop.ledger.paste.changes"), String(plan.changes)],
    [t("desktop.ledger.paste.refused"), String(plan.refused.length)],
    [t("desktop.ledger.paste.dropped"), String(plan.dropped)],
    [t("desktop.ledger.paste.blanks"), String(plan.blanks)],
    [t("desktop.ledger.paste.new_identity"), String(plan.newIdentity)],
  ];
  if (singleWrites > 0)
    rows.push([t("desktop.ledger.paste.single_writes"), String(singleWrites)]);
  // The first refusal says why, in the column's own name.
  const first = plan.refused[0];
  const firstIndex = first ? plan.columns.indexOf(first.column) : -1;
  const pastes = plan.changes > 0;
  return (
    <Dialog open onOpenChange={(open) => !open && onCancel()}>
      <DialogContent
        className="ledger-paste w-dialog-md"
        closeLabel={t("desktop.ledger.paste.cancel")}
        onCloseAutoFocus={onCloseAutoFocus}
      >
        <DialogHeader>
          <DialogTitle>
            {t("desktop.ledger.paste.title_into", {
              columns: columns.join(", "),
            })}
          </DialogTitle>
          <DialogDescription>
            {t("desktop.ledger.paste.description", { rows: plan.rows })}
          </DialogDescription>
        </DialogHeader>
        <dl className="grid grid-cols-[1fr_auto] gap-x-6 gap-y-1.5 text-base">
          {rows.map(([term, value]) => (
            <div key={term} className="contents">
              <dt className="text-muted-foreground">{term}</dt>
              <dd className="text-end tabular-nums">{value}</dd>
            </div>
          ))}
        </dl>
        {first && (
          <p className="ledger-paste-refusal text-sm text-foreground">
            {t("desktop.ledger.paste.first_refusal", {
              column: columns[firstIndex] ?? first.column,
              reason: refusalText(t, first.refusal),
            })}
          </p>
        )}
        {plan.blanks > 0 && (
          <p className="text-sm text-muted-foreground">
            {t("desktop.ledger.paste.blanks_note")}
          </p>
        )}
        {plan.newIdentity > 0 && (
          <p className="text-sm text-muted-foreground">
            {t("desktop.ledger.paste.identity_note")}
          </p>
        )}
        <DialogFooter>
          {/* With nothing to change, Cancel is the one way on. */}
          <Button variant="ghost" autoFocus={!pastes} onClick={onCancel}>
            {t("desktop.ledger.paste.cancel")}
          </Button>
          <Button
            autoFocus={pastes}
            className="ledger-paste-apply"
            aria-disabled={pastes ? undefined : true}
            onClick={() => {
              if (pastes) onPaste();
            }}
          >
            {t("desktop.ledger.paste.apply", { count: plan.changes })}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/**
 * The cost of a change that adds more than a few saves one at a time: each
 * loads and saves the whole ledger. Stage anyway or leave it unstaged.
 */
export function CostDialog({
  singleWrites,
  seconds,
  onStage,
  onCancel,
  onCloseAutoFocus,
}: {
  singleWrites: number;
  seconds: number;
  onStage: () => void;
  onCancel: () => void;
  /** Where the focus goes once the dialog has gone. */
  onCloseAutoFocus?: (event: Event) => void;
}) {
  const t = useStrings();
  const minutes = Math.max(1, Math.round(seconds / 60));
  return (
    <Dialog open onOpenChange={(open) => !open && onCancel()}>
      <DialogContent
        className="ledger-cost w-dialog-md"
        closeLabel={t("desktop.ledger.cost.cancel")}
        onCloseAutoFocus={onCloseAutoFocus}
      >
        <DialogHeader>
          <DialogTitle>
            {t("desktop.ledger.cost.title", { count: singleWrites })}
          </DialogTitle>
          <DialogDescription>
            {t("desktop.ledger.cost.description", { minutes })}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="ghost" onClick={onCancel}>
            {t("desktop.ledger.cost.cancel")}
          </Button>
          <Button autoFocus className="ledger-cost-stage" onClick={onStage}>
            {t("desktop.ledger.cost.stage")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
