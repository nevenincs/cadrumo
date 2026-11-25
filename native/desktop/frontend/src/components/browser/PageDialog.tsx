import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { TextEditor } from "@/components/editors/TextEditor";
import type { SedeViewDialog } from "../../ipc/sedeViewMessages";
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
  pending,
  failed,
  previousText,
}: {
  dialog: SedeViewDialog;
  onAnswer: (accept: boolean, promptText?: string) => Promise<void>;
  pending: boolean | null;
  failed: boolean;
  previousText?: string;
}) {
  const t = useStrings();
  const [text, setText] = useState(previousText ?? dialog.default_prompt ?? "");
  const answer = (accept: boolean, promptText?: string) => {
    if (pending === null) void onAnswer(accept, promptText);
  };
  const leaving = dialog.dialog_kind === "beforeunload";
  const asking = dialog.dialog_kind === "prompt";
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) void answer(false);
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
        {failed && (
          <Alert role="alert" tone="warning">
            {t("desktop.browser.dialog.answer_failed")}
          </Alert>
        )}
        {asking && (
          <TextEditor
            value={text}
            disabled={pending !== null}
            maxLength={ANSWER_LIMIT}
            aria-label={t("desktop.browser.dialog.prompt_label")}
            onChange={setText}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.nativeEvent.isComposing)
                void answer(true, text);
            }}
          />
        )}
        <DialogFooter>
          {dialog.dialog_kind !== "alert" && (
            <Button
              variant="outline"
              disabled={pending !== null}
              pending={pending === false}
              onClick={() => void answer(false)}
            >
              {leaving
                ? t("desktop.browser.dialog.stay")
                : t("desktop.browser.dialog.cancel")}
            </Button>
          )}
          <Button
            disabled={pending !== null}
            pending={pending === true}
            onClick={() => void answer(true, asking ? text : undefined)}
          >
            {leaving
              ? t("desktop.browser.dialog.leave")
              : t("desktop.browser.dialog.ok")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
