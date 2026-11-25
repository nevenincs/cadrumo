import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { SheetFooter } from "@/components/ui/sheet";
import { useStrings } from "../../../shell/strings";
import { WriteHold } from "../WritePause";
import type { InvoiceEditorState } from "./useInvoiceEditor";

/** Review, back, close and send actions for the current sheet stage. */
export function InvoiceEditorFooter({
  editor,
}: {
  editor: Pick<
    InvoiceEditorState,
    | "unknown"
    | "isNew"
    | "stage"
    | "check"
    | "corrected"
    | "stored"
    | "sending"
    | "add"
    | "update"
    | "remove"
    | "preview"
    | "setTried"
    | "setWantsReview"
    | "setStage"
    | "close"
  >;
}) {
  const t = useStrings();
  const {
    unknown,
    isNew,
    stage,
    check,
    corrected,
    stored,
    sending,
    add,
    update,
    remove,
    preview,
    setTried,
    setWantsReview,
    setStage,
    close,
  } = editor;
  const changed = corrected?.changed ?? [];
  const primary = (): ReactNode => {
    if (unknown) return null;
    if (isNew) {
      if (stage === "confirm" && check.request)
        return (
          <WriteHold>
            <Button
              size="sm"
              pending={sending}
              onClick={() => void add(check.request!, check.invoiceId)}
            >
              {t("desktop.ledger.invoices.add")}
            </Button>
          </WriteHold>
        );
      return (
        <Button
          size="sm"
          onClick={() => {
            setTried(true);
            preview.commit();
            setWantsReview(true);
          }}
        >
          {t("desktop.ledger.invoices.review")}
        </Button>
      );
    }
    if (!stored || !corrected) return null;
    if (stage === "confirm" && corrected.request)
      return (
        <WriteHold>
          <Button
            size="sm"
            pending={sending}
            onClick={() => void update(corrected.request!)}
          >
            {t("desktop.ledger.invoices.save")}
          </Button>
        </WriteHold>
      );
    if (stage === "remove") return null;
    return (
      <Button
        size="sm"
        aria-disabled={changed.length === 0 ? true : undefined}
        onClick={() => {
          if (changed.length === 0) return;
          setTried(true);
          preview.commit();
          setWantsReview(true);
        }}
      >
        {t("desktop.ledger.invoices.review_changes", { count: changed.length })}
      </Button>
    );
  };

  return (
    <SheetFooter className="border-t border-border pt-3">
      {!isNew && stored && stage !== "remove" && !unknown && (
        <Button
          size="sm"
          variant="ghost"
          className="mr-auto"
          onClick={() => setStage("remove")}
        >
          <Icon name="trash" />
          {t("desktop.ledger.invoices.remove")}
        </Button>
      )}
      {stage === "remove" && stored && (
        <>
          <Button
            size="sm"
            variant="ghost"
            className="mr-auto"
            autoFocus
            onClick={() => setStage("edit")}
          >
            {t("desktop.ledger.invoices.keep_it")}
          </Button>
          {stored.linked_transaction_ids.length === 0 && !unknown && (
            <WriteHold>
              <Button
                size="sm"
                variant="destructive"
                pending={sending}
                onClick={() => void remove(stored.invoice_id)}
              >
                {t("desktop.ledger.invoices.remove_confirm")}
              </Button>
            </WriteHold>
          )}
        </>
      )}
      {stage === "confirm" && (
        <Button size="sm" variant="ghost" onClick={() => setStage("edit")}>
          {t("desktop.ledger.invoices.back")}
        </Button>
      )}
      {stage !== "remove" && (
        <Button size="sm" variant="ghost" onClick={close}>
          {t(
            isNew
              ? "desktop.ledger.invoices.cancel"
              : "desktop.ledger.invoices.close",
          )}
        </Button>
      )}
      {primary()}
    </SheetFooter>
  );
}
