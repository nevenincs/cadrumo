import { useRef, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import type { LedgerPort } from "../../../shell/ledger";
import { useStrings } from "../../../shell/strings";
import { landingSettle, useWritePause, WriteHold } from "../WritePause";
import { EditorSection } from "./InvoiceFields";
import { write } from "./invoiceWrites";

/**
 * Stores the invoice's own document, its PDF or e-invoice, with the invoice.
 * The deduction a received invoice declares rests on that document, so the
 * check sends the person here when it is missing. Sending the same file again
 * changes nothing: the document is kept by its content.
 */
export function InvoiceDocument({
  port,
  invoiceId,
  say,
}: {
  port: LedgerPort;
  invoiceId: string;
  say(text: string): void;
}) {
  const t = useStrings();
  const pause = useWritePause();
  const [adding, setAdding] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const tokens = useRef<string[]>([]);

  async function attach() {
    setAdding(true);
    setFailed(null);
    try {
      const picks = await port.pickFiles(
        "documents",
        "file",
        t("desktop.ledger.import.filter.documents"),
      );
      const file = picks.files[0];
      if (!file) return;
      tokens.current = [file.token];
      const sent = await write(port, "ledger.invoice.attach_document", {
        invoice_id: invoiceId,
        source_path: file.token,
      });
      if (sent.kind === "unknown")
        pause.hold({
          what: file.name,
          outcome: sent.saved ? "saved_unread" : "unknown",
          // The document is kept by its content, so sending it again is safe.
          settle: landingSettle(t, file.name, async () => "repeatable"),
        });
      await port.forgetFiles(tokens.current).catch(() => undefined);
      tokens.current = [];
      if (sent.kind === "done")
        say(
          t(
            sent.result.already_linked
              ? "desktop.ledger.invoices.document_already"
              : "desktop.ledger.invoices.document_attached",
          ),
        );
      else
        setFailed(
          sent.kind === "unknown"
            ? "unknown"
            : sent.kind === "refused"
              ? (sent.reason ?? "refused")
              : sent.code,
        );
    } catch {
      setFailed("unavailable");
    } finally {
      setAdding(false);
    }
  }

  return (
    <EditorSection title={t("desktop.ledger.invoices.source_document")}>
      <p className="text-xs text-muted-foreground">
        {t("desktop.ledger.invoices.source_document_hint")}
      </p>
      <WriteHold>
        <Button
          size="sm"
          variant="outline"
          data-invoice-action="attach_document"
          disabled={adding}
          aria-busy={adding || undefined}
          onClick={() => void attach()}
        >
          {adding ? <Spinner /> : <Icon name="plus" />}
          {t("desktop.ledger.invoices.attach_document")}
        </Button>
      </WriteHold>
      {failed && (
        <Alert tone="danger" role="alert" icon={<Icon name="refused" />}>
          {failed === "unknown"
            ? t("desktop.ledger.documents.unknown")
            : t("desktop.ledger.documents.not_done")}
        </Alert>
      )}
    </EditorSection>
  );
}
