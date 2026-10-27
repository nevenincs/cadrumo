import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import type { SedeViewDialog } from "../../ipc/contract";
import { useStrings } from "../../shell/strings";

/** The most characters of an answer the host takes. */
const ANSWER_LIMIT = 1024;

/**
 * A dialog the page opened (alert, confirm, prompt or leave): the page waits
 * for the person's answer, and so does the view. Closing it any other way is
 * declining. The page's own words are shown as the page wrote them.
 */
export function PageDialog({
  dialog,
  onAnswer,
}: {
  dialog: SedeViewDialog;
  onAnswer: (accept: boolean, promptText?: string) => void;
}) {
  const t = useStrings();
  const [text, setText] = useState(dialog.default_prompt ?? "");
  const leaving = dialog.dialog_kind === "beforeunload";
  const asking = dialog.dialog_kind === "prompt";
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onAnswer(false);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {leaving
              ? t("desktop.browser.dialog.leave_title")
              : t("desktop.browser.dialog.title")}
          </DialogTitle>
          <DialogDescription className="whitespace-pre-wrap [overflow-wrap:anywhere]">
            {leaving
              ? t("desktop.browser.dialog.leave_description")
              : dialog.message}
          </DialogDescription>
        </DialogHeader>
        {asking && (
          <Input
            value={text}
            maxLength={ANSWER_LIMIT}
            aria-label={t("desktop.browser.dialog.prompt_label")}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.nativeEvent.isComposing)
                onAnswer(true, text);
            }}
          />
        )}
        <DialogFooter>
          {dialog.dialog_kind !== "alert" && (
            <Button variant="outline" onClick={() => onAnswer(false)}>
              {leaving
                ? t("desktop.browser.dialog.stay")
                : t("desktop.browser.dialog.cancel")}
            </Button>
          )}
          <Button onClick={() => onAnswer(true, asking ? text : undefined)}>
            {leaving
              ? t("desktop.browser.dialog.leave")
              : t("desktop.browser.dialog.ok")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
