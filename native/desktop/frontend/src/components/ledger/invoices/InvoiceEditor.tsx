import type { ReactNode } from "react";
import { Alert } from "@/components/ui/alert";
import { Icon } from "@/components/ui/icon";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import type { CatalogueInvoice } from "../../../shell/ledgerInvoiceOperations";
import type { LedgerPort } from "../../../shell/ledger";
import { useStrings } from "../../../shell/strings";
import {
  Confirmation,
  RemoveConfirmation,
  InvoiceDiscardConfirmation,
} from "./InvoiceConfirmation";
import { InvoiceEditorFooter } from "./InvoiceEditorFooter";
import { PreviewNotes, OutcomeAlert } from "./InvoiceEditorStatus";
import { NewInvoice } from "./NewInvoiceEditor";
import { StoredInvoice } from "./StoredInvoiceEditor";
import { seriesAndNumber, type PlacedFindings } from "./invoiceModel";
import { kindLabel, paymentLabel } from "./invoiceWords";
import { useInvoiceEditor } from "./useInvoiceEditor";

/** Which invoice the editor shows: a new one, or one in the catalogue. */
export type EditorTarget =
  { kind: "new" } | { kind: "open"; invoiceId: string };

/**
 * The invoice editor, a modal sheet. A new invoice starts with nothing
 * assumed: the person says whether they issued or received it, and names
 * its country and currency. Its four requirements are named at the top and
 * ticked as they are met. A stored invoice shows its identity and lines as
 * fixed, with why, and lets the person correct only what the ledger lets
 * them correct. Every write is reviewed first and sent once; an outcome
 * that was not seen is said to be unknown, and nothing more is written
 * until the person checks.
 */
export type InvoiceEditorProps = {
  port: LedgerPort;
  locale: string;
  /** The catalogue as read, for the next number and the stored invoice. */
  invoices: readonly CatalogueInvoice[];
  target: EditorTarget;
  onClose(): void;
  /** An invoice the ledger stored, or null with the id of one it removed. */
  onWritten(invoice: CatalogueInvoice | null, removed?: string): void;
  onOpenInvoice(invoiceId: string): void;
  /** Confirms a write in a toast. */
  say(text: string): void;
};

export function InvoiceEditor({
  port,
  locale,
  invoices,
  target,
  onClose,
  onWritten,
  onOpenInvoice,
  say,
}: InvoiceEditorProps) {
  const t = useStrings();
  const editor = useInvoiceEditor({
    port,
    invoices,
    target,
    onClose,
    onWritten,
    say,
  });
  const {
    stored,
    draft,
    correction,
    stage,
    asking,
    setAsking,
    sending,
    outcome,
    tried,
    touched,
    duplicate,
    pause,
    isNew,
    preview,
    check,
    corrected,
    shown,
    touch,
    edit,
    correct,
    close,
    checkPending,
  } = editor;
  // ---- What the editor shows ---------------------------------------------------

  const title = isNew
    ? t("desktop.ledger.invoices.new")
    : stored
      ? t("desktop.ledger.invoices.title", { number: seriesAndNumber(stored) })
      : t("desktop.ledger.invoices.gone_title");

  let body: ReactNode;
  if (!isNew && (!stored || !correction))
    body = (
      <Alert tone="warning" icon={<Icon name="alert" />}>
        {t("desktop.ledger.invoices.gone")}
      </Alert>
    );
  else if (isNew)
    body = (
      <NewInvoice
        draft={draft}
        check={check}
        preview={preview}
        invoices={invoices}
        locale={locale}
        shown={shown}
        touch={touch}
        tried={tried}
        touched={touched}
        edit={edit}
        duplicate={duplicate}
        onOpenInvoice={onOpenInvoice}
        say={say}
      />
    );
  else
    body = (
      <StoredInvoice
        port={port}
        invoice={stored!}
        preview={preview}
        invoices={invoices}
        correction={correction!}
        locale={locale}
        shown={shown}
        touch={touch}
        correct={correct}
        say={say}
      />
    );

  const changed = corrected?.changed ?? [];
  // A stored invoice asks the ledger about its retención alone, so a read
  // that failed matters there only once a retención is being changed.
  const retentionAsked =
    isNew ||
    changed.includes("retention_rate") ||
    changed.includes("retention_amount");
  return (
    <Sheet open onOpenChange={(open) => !open && close()}>
      <SheetContent
        modalLayer={false}
        closeLabel={t("desktop.ledger.invoices.close")}
        className="ledger-invoice-editor gap-5"
        aria-describedby={undefined}
        onInteractOutside={(event) => {
          if (sending) event.preventDefault();
        }}
      >
        <SheetHeader>
          <SheetTitle>{title}</SheetTitle>
          <SheetDescription>
            {isNew
              ? t("desktop.ledger.invoices.new_note")
              : stored
                ? t("desktop.ledger.invoices.stored_note", {
                    kind: kindLabel(t, stored.kind),
                    payment: paymentLabel(t, stored.payment_status),
                    count: stored.linked_transaction_ids.length,
                  })
                : null}
          </SheetDescription>
        </SheetHeader>

        {asking && (
          <InvoiceDiscardConfirmation
            isNew={isNew}
            onKeep={() => setAsking(false)}
            onDiscard={onClose}
          />
        )}

        <OutcomeAlert
          outcome={outcome}
          sending={sending || pause.rereading}
          onCheck={checkPending}
        />

        <PreviewNotes
          failed={preview.failed && retentionAsked}
          onRetry={preview.retry}
          refusedUnsaid={isNew && check.refusedUnsaid}
          findings={
            isNew ? check.findings : (corrected?.findings ?? NO_FINDINGS)
          }
          slots={preview.shown?.rate_slots ?? []}
        />

        <div
          className="flex flex-col gap-6"
          onBlurCapture={() => preview.commit()}
        >
          {body}
        </div>

        {stage === "confirm" && (
          <Confirmation
            isNew={isNew}
            draftRequest={check.request}
            total={preview.current?.totals.total?.decimal ?? ""}
            stored={stored}
            correction={correction}
            changed={changed}
            locale={locale}
          />
        )}
        {stage === "remove" && stored && (
          <RemoveConfirmation invoice={stored} />
        )}

        <InvoiceEditorFooter editor={editor} />
      </SheetContent>
    </Sheet>
  );
}

const NO_FINDINGS: PlacedFindings = { warnings: {}, general: [] };
