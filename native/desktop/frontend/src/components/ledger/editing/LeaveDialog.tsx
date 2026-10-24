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

/**
 * Asks before the page's staged work is dropped by leaving it, signing
 * out, switching profile or closing the window: it lives only in this
 * window. Review and save opens the review; Discard leaves; Cancel stays.
 */
export function LeaveDialog({
  units,
  onReview,
  onDiscard,
  onCancel,
}: {
  units: number;
  onReview: () => void;
  onDiscard: () => void;
  onCancel: () => void;
}) {
  const t = useStrings();
  return (
    <Dialog open onOpenChange={(open) => !open && onCancel()}>
      <DialogContent
        className="ledger-leave w-dialog-md"
        closeLabel={t("desktop.ledger.leave.cancel")}
      >
        <DialogHeader>
          <DialogTitle>{t("desktop.ledger.leave.title")}</DialogTitle>
          <DialogDescription>
            {t("desktop.ledger.leave.description", { count: units })}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="ghost" onClick={onCancel}>
            {t("desktop.ledger.leave.cancel")}
          </Button>
          <Button
            variant="outline"
            className="ledger-leave-discard"
            onClick={onDiscard}
          >
            {t("desktop.ledger.leave.discard")}
          </Button>
          <Button autoFocus className="ledger-leave-review" onClick={onReview}>
            {t("desktop.ledger.leave.review")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
