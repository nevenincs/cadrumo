import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { SetupRow } from "../../ipc/contract";
import { useStrings } from "../../shell/strings";
import { actionWords, itemName, rowSentence } from "./setupWords";

/** What a feature that could not run needs: the item by name, its state said
 * once by its sentence, and the row's own action when it has one. A
 * row with none, such as one this build or this computer cannot set up, says
 * its sentence and offers only to close: no button leads to a setup that
 * would refuse. */
export function SetupPrompt({
  row,
  takeFocus = true,
  onClose,
  onSetUp,
  onLocalAi,
}: {
  row: SetupRow | null;
  /** False leaves the keyboard where the person is typing: the prompt opens
   * without taking it. */
  takeFocus?: boolean;
  onClose: () => void;
  onSetUp: (row: SetupRow) => void;
  onLocalAi?: () => void;
}) {
  const t = useStrings();
  return (
    <Dialog open={row !== null} onOpenChange={(open) => !open && onClose()}>
      {row && (
        <DialogContent
          className="setup-prompt"
          onOpenAutoFocus={(event) => {
            if (!takeFocus) event.preventDefault();
          }}
        >
          <DialogHeader>
            <DialogTitle>{itemName(t, row.kind)}</DialogTitle>
            <DialogDescription>{rowSentence(t, row)}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            {row.kind === "local_ai" && onLocalAi && (
              <Button variant="outline" size="sm" onClick={onLocalAi}>
                {t("desktop.providers.local_models_title")}
              </Button>
            )}
            {row.recovery === null ? (
              <Button size="sm" onClick={onClose}>
                {t("desktop.setup.close")}
              </Button>
            ) : (
              <>
                <Button variant="outline" size="sm" onClick={onClose}>
                  {t("desktop.setup.not_now")}
                </Button>
                <Button size="sm" onClick={() => onSetUp(row)}>
                  {actionWords(t, row.recovery) ?? t("desktop.setup.open")}
                </Button>
              </>
            )}
          </DialogFooter>
        </DialogContent>
      )}
    </Dialog>
  );
}
