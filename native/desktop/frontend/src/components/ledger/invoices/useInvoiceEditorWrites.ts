import { useEffect, useRef, useState } from "react";
import type {
  CatalogueInvoice,
  InvoiceAddRequest,
  InvoiceAddResult,
  InvoiceUpdateRequest,
} from "../../../shell/ledgerInvoiceOperations";
import { type LedgerPort, servedRefusalWords } from "../../../shell/ledger";
import { useStrings } from "../../../shell/strings";
import { useWritePause } from "../WritePause";
import { seriesAndNumber } from "./invoiceModel";
import {
  addLanded,
  removeLanded,
  updateLanded,
  write,
  type Landed,
} from "./invoiceWrites";

/** A write the editor sent and did not see settle. */
export type Pending =
  | { what: "add"; request: InvoiceAddRequest; invoiceId: string | null }
  | { what: "update"; request: InvoiceUpdateRequest }
  | { what: "remove"; invoiceId: string };

export type Outcome =
  | { kind: "refused"; text: string }
  | { kind: "failed"; code: string }
  | { kind: "unknown"; pending: Pending; checked: boolean }
  | { kind: "not_saved" };

const numberOf = (invoice: CatalogueInvoice | null) =>
  invoice ? seriesAndNumber(invoice) : "";

/** Sends each reviewed write once and settles unread outcomes through the page hold. */
export function useInvoiceEditorWrites({
  port,
  stored,
  onClose,
  onWritten,
  say,
  backToEdit,
  setDuplicate,
}: {
  port: LedgerPort;
  stored: CatalogueInvoice | null;
  onClose(): void;
  onWritten(invoice: CatalogueInvoice | null, removed?: string): void;
  say(text: string): void;
  backToEdit(): void;
  setDuplicate(value: string | null): void;
}) {
  const t = useStrings();
  const [sending, setSending] = useState(false);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const pause = useWritePause();
  // A write the page settles after this editor closed says nothing here.
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  // ---- Writes ----------------------------------------------------------------

  const settled = (landed: Landed, pending: Pending) => {
    if (landed.kind === "unreadable") {
      setOutcome({ kind: "unknown", pending, checked: true });
      return;
    }
    if (landed.kind === "not_saved") {
      setOutcome({ kind: "not_saved" });
      backToEdit();
      return;
    }
    if (pending.what === "remove") {
      say(t("desktop.ledger.invoices.removed", { number: numberOf(stored) }));
      onWritten(null, pending.invoiceId);
    } else {
      const invoice = landed.invoice;
      say(
        t(
          pending.what === "add"
            ? "desktop.ledger.invoices.added"
            : "desktop.ledger.invoices.saved",
          { number: invoice ? seriesAndNumber(invoice) : numberOf(stored) },
        ),
      );
      onWritten(invoice);
    }
    onClose();
  };

  /** Reads whether `pending` landed. */
  const landedOf = (pending: Pending): Promise<Landed> =>
    pending.what === "add"
      ? addLanded(port, pending.invoiceId)
      : pending.what === "update"
        ? updateLanded(port, pending.request)
        : removeLanded(port, pending.invoiceId);

  /** A write not seen to settle: the editor says so, and every write on
   * the page waits until the page's re-read reads whether it landed. */
  const undetermined = (pending: Pending, saved: boolean) => {
    setOutcome({ kind: "unknown", pending, checked: false });
    const what = t("desktop.ledger.invoices.title", {
      number:
        pending.what === "add"
          ? pending.request.invoice_number
          : numberOf(stored),
    });
    pause.hold({
      what,
      outcome: saved ? "saved_unread" : "unknown",
      settle: async () => {
        const landed = await landedOf(pending);
        if (mounted.current) settled(landed, pending);
        if (landed.kind === "unreadable") return null;
        return [
          t(
            landed.kind === "saved"
              ? "desktop.ledger.paused.found_saved"
              : "desktop.ledger.paused.unsaved",
            { movement: what },
          ),
        ];
      },
    });
  };

  /** Why a write was refused: the sentence the backend served, else the
   * page's own generic notice. */
  const refusedText = (detail: unknown = null) =>
    servedRefusalWords(detail) ?? t("desktop.ledger.invoices.refused");

  const add = async (request: InvoiceAddRequest, invoiceId: string | null) => {
    setSending(true);
    const answer = await write(port, "ledger.invoice.add", request);
    setSending(false);
    if (answer.kind === "done") {
      const result = answer.result;
      if (result.outcome === "created" && result.invoice) {
        say(
          result.euro_value_pending
            ? t("desktop.ledger.invoices.added_no_rate", {
                number: seriesAndNumber(result.invoice),
              })
            : t("desktop.ledger.invoices.added", {
                number: seriesAndNumber(result.invoice),
              }),
        );
        onWritten(result.invoice);
        onClose();
        return;
      }
      refuseAdd(result);
      return;
    }
    if (answer.kind === "refused") {
      const detail = answer.detail as Partial<InvoiceAddResult> | null;
      if (detail && detail.outcome === "validation_error")
        refuseAdd(detail as InvoiceAddResult);
      else setOutcome({ kind: "refused", text: refusedText(answer.detail) });
      backToEdit();
      return;
    }
    if (answer.kind === "unknown")
      undetermined({ what: "add", request, invoiceId }, answer.saved);
    else setOutcome({ kind: "failed", code: answer.code });
  };
  const refuseAdd = (
    result: Pick<
      InvoiceAddResult,
      "validation_code" | "invoice_id" | "refusal_words"
    >,
  ) => {
    backToEdit();
    if (result.validation_code === "duplicate_invoice") {
      setDuplicate(result.invoice_id ?? "");
      setOutcome(null);
    } else
      setOutcome({
        kind: "refused",
        text:
          servedRefusalWords(result) ?? t("desktop.ledger.invoices.invalid"),
      });
  };

  const update = async (request: InvoiceUpdateRequest) => {
    setSending(true);
    const answer = await write(port, "ledger.invoice.update", request);
    setSending(false);
    if (answer.kind === "done") {
      say(
        t("desktop.ledger.invoices.saved", {
          number: seriesAndNumber(answer.result.invoice),
        }),
      );
      onWritten(answer.result.invoice);
      onClose();
    } else if (answer.kind === "refused") {
      setOutcome({ kind: "refused", text: refusedText(answer.detail) });
      backToEdit();
    } else if (answer.kind === "unknown")
      undetermined({ what: "update", request }, answer.saved);
    else setOutcome({ kind: "failed", code: answer.code });
  };

  const remove = async (invoiceId: string) => {
    setSending(true);
    const answer = await write(port, "ledger.invoice.remove", {
      invoice_id: invoiceId,
    });
    setSending(false);
    if (answer.kind === "done") {
      say(t("desktop.ledger.invoices.removed", { number: numberOf(stored) }));
      onWritten(null, invoiceId);
      onClose();
    } else if (answer.kind === "refused") {
      setOutcome({ kind: "refused", text: refusedText(answer.detail) });
      backToEdit();
    } else if (answer.kind === "unknown")
      undetermined({ what: "remove", invoiceId }, answer.saved);
    else setOutcome({ kind: "failed", code: answer.code });
  };

  // Checking is the page's one re-read: it settles this write and every
  // other one the page holds.
  const checkPending = () => {
    if (!pause.rereading) pause.reread();
  };

  return {
    sending,
    outcome,
    setOutcome,
    pause,
    add,
    update,
    remove,
    checkPending,
  };
}
