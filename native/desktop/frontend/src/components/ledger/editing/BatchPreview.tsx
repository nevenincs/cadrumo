import { useId } from "react";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import {
  batchCounts,
  unwrittenRows,
  type BatchPreview,
} from "../../../shell/ledgerBatch";
import { useStrings } from "../../../shell/strings";
import { batchCountsText, batchRowWords } from "./batchWords";
import { titleOf } from "./reviewLabels";
import { WindowedList } from "./WindowedList";
import type { LedgerTransactionReviewProjection } from "../../../shell/ledgerReadContract";

/**
 * What the ledger answered it would do to each movement saved together,
 * before anything is written: how many rows change, and each row that will
 * not, with why. Partial work is shown as it is: the rows that will be
 * written are saved, the others stay staged.
 */
export function BatchPreviewSection({
  preview,
  rows,
}: {
  preview: BatchPreview;
  rows: ReadonlyMap<string, LedgerTransactionReviewProjection>;
}) {
  const t = useStrings();
  const heading = useId();
  if (preview.kind === "none") return null;
  if (preview.kind === "waiting")
    return (
      <p
        role="status"
        className="ledger-batch-previewing flex items-center gap-2 text-sm text-muted-foreground"
      >
        <Spinner />
        {t("desktop.ledger.batch.previewing")}
      </p>
    );
  if (preview.kind === "failed")
    return (
      <Alert
        tone="danger"
        role="alert"
        icon={<Icon name="alert" />}
        className="ledger-batch-preview-failed"
      >
        <AlertTitle>{t("desktop.ledger.batch.preview_failed")}</AlertTitle>
        <Button
          variant="outline"
          size="xs"
          className="ledger-batch-preview-retry"
          onClick={preview.retry}
        >
          {t("desktop.ledger.retry")}
        </Button>
      </Alert>
    );
  const counts = batchCounts(preview.results);
  const unwritten = [
    ...unwrittenRows(preview.results),
    ...preview.results
      .flatMap((result) => result.rows)
      .filter((row) => row.outcome === "unchanged"),
  ];
  return (
    <section
      className="ledger-batch-preview grid gap-2"
      aria-labelledby={heading}
    >
      <h3
        id={heading}
        className="text-xs font-semibold tracking-wide text-muted-foreground uppercase"
      >
        {t("desktop.ledger.batch.preview_title")}
      </h3>
      {/* Read out as the answer arrives, so the counts are heard without
          moving to them. */}
      <p role="status" className="ledger-batch-counts text-sm">
        {batchCountsText(t, counts)}
      </p>
      {unwritten.length > 0 && (
        <WindowedList
          label={t("desktop.ledger.batch.unwritten")}
          className="ledger-batch-unwritten max-h-60 rounded-md border border-border"
          items={unwritten}
          keyOf={(row) => row.transaction_id}
          render={(row) => (
            <div
              data-batch-row={row.outcome}
              data-cause={row.cause ?? undefined}
              className="flex h-14 items-center gap-2 border-b border-border px-3"
            >
              <Icon
                name={
                  row.outcome === "refused"
                    ? "refused"
                    : row.outcome === "conflict"
                      ? "unknown"
                      : "pending"
                }
                size="xs"
                className={
                  row.outcome === "refused"
                    ? "shrink-0 text-destructive"
                    : row.outcome === "conflict"
                      ? "shrink-0 text-warning"
                      : "shrink-0"
                }
              />
              <span className="grid min-w-0 flex-1">
                <span className="truncate font-medium">
                  {titleOf(t, rows, row.transaction_id)}
                </span>
                <span
                  className="line-clamp-2 text-sm text-muted-foreground"
                  title={batchRowWords(t, row)}
                >
                  {batchRowWords(t, row)}
                </span>
              </span>
            </div>
          )}
        />
      )}
    </section>
  );
}
