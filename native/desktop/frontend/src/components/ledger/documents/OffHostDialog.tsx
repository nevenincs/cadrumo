import { useId, useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useStrings } from "../../../shell/strings";

/** The only provider a document may be sent off this computer to. */
export const OFF_HOST_PROVIDER = "AGENT";

/**
 * Asks before one document leaves this computer to be read. It names the
 * document and the provider, and its acknowledgement is for this one read:
 * the box starts unticked every time it opens.
 */
export function OffHostDialog({
  fileName,
  onSend,
  onClose,
}: {
  fileName: string;
  onSend(): void;
  onClose(): void;
}) {
  const t = useStrings();
  const [agreed, setAgreed] = useState(false);
  const box = useId();
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        closeLabel={t("desktop.ledger.documents.close")}
        className="ledger-off-host w-dialog-md"
      >
        <DialogHeader>
          <DialogTitle>
            {t("desktop.ledger.documents.off_host.title")}
          </DialogTitle>
          <DialogDescription>
            {t("desktop.ledger.documents.off_host.body", {
              file: fileName,
              provider: OFF_HOST_PROVIDER,
            })}
          </DialogDescription>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          {t("desktop.ledger.documents.off_host.unrecallable")}
        </p>
        <label htmlFor={box} className="flex items-start gap-2 text-sm">
          <Checkbox
            id={box}
            className="ledger-off-host-agree mt-0.5"
            checked={agreed}
            onChange={(event) => setAgreed(event.target.checked)}
          />
          {t("desktop.ledger.documents.off_host.agree", {
            file: fileName,
            provider: OFF_HOST_PROVIDER,
          })}
        </label>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            {t("desktop.ledger.documents.cancel")}
          </Button>
          <Button
            className="ledger-off-host-send"
            disabled={!agreed}
            onClick={onSend}
          >
            {t("desktop.ledger.documents.off_host.send", {
              provider: OFF_HOST_PROVIDER,
            })}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
