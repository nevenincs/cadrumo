import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { ModeloDeclarationListRowV1 } from "../../../shell/modeloContract";
import { useStrings } from "../../../shell/strings";
import { aeatWords } from "./declarationsWords";

// The list row field this dialog reads, which the read model is gaining.
// Once the generated contract carries it, this goes and the row's own type
// is read directly.
type AeatFiling = { notes: string[] };
type RowWithFiling = ModeloDeclarationListRowV1 & {
  aeat_filing?: AeatFiling | null;
};

/**
 * A return the AEAT holds that no local declaration is linked to, to read
 * only: what the list says of it and what the read model notes. Nothing is linked, made or
 * sent from here.
 */
export function AeatFilingDialog({
  row,
  onClose,
}: {
  row: RowWithFiling;
  onClose: () => void;
}) {
  const t = useStrings();
  const aeat = aeatWords(t, row);
  const filing = row.aeat_filing ?? null;
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        className="declarations-aeat-filing"
        closeLabel={t("workspace.modelo.key.close")}
      >
        <DialogHeader>
          <DialogTitle>{row.modelo_title}</DialogTitle>
          {row.period_words && (
            <DialogDescription>{row.period_words}</DialogDescription>
          )}
        </DialogHeader>
        <div className="flex flex-col gap-1 text-base">
          <p className="font-medium">{row.state_words}</p>
          {aeat && <p className="text-muted-foreground">{aeat}</p>}
          {row.result_words && (
            <p className="text-muted-foreground">{row.result_words}</p>
          )}
          {row.advice_words && (
            <p className="text-muted-foreground">{row.advice_words}</p>
          )}
        </div>
        {filing && filing.notes.length > 0 && (
          <div className="flex flex-col gap-2 text-base text-muted-foreground">
            {filing.notes.map((note) => (
              <p key={note}>{note}</p>
            ))}
          </div>
        )}
        <DialogFooter>
          <Button autoFocus onClick={onClose}>
            {t("workspace.modelo.key.close")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
