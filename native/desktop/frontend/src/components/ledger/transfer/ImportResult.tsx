import { useEffect, useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Spinner } from "@/components/ui/spinner";
import { useTableView, type ViewColumn } from "@/components/ui/table-view";
import { facts } from "../../../shell/compose";
import type {
  LedgerImportResult,
  LedgerPort,
  LedgerTransaction,
  PickedFile,
} from "../../../shell/ledger";
import type { InvoiceImportResult } from "../../../shell/ledgerInvoiceOperations";
import { useStrings, type Translate } from "../../../shell/strings";
import { formatDay } from "../../../shared/dateFormats";
import { formatAmount } from "../../../shared/numbers";
import { listOf } from "../../../shared/lists";
import { SetupOffer } from "../../setup/SetupOffer";
import { FileRow } from "./ImportFileRow";
import {
  readExisting,
  type Attempt,
  type BankApplied,
  type DocumentsApplied,
} from "./importModel";
import { importRefusal } from "./transferWords";

/** What an import's apply answered, by the kind of import. */
export type ImportOutcome =
  | { kind: "bank"; applied: BankApplied[] }
  | { kind: "book"; file: PickedFile; answer: Attempt<InvoiceImportResult> }
  | { kind: "documents"; applied: DocumentsApplied };

/** A likely duplicate as imported, beside what it was flagged against. */
function DuplicateCompare({
  port,
  locale,
  imported,
}: {
  port: LedgerPort;
  locale: string;
  imported: LedgerTransaction;
}) {
  const t = useStrings();
  const [open, setOpen] = useState(false);
  const [existing, setExisting] = useState<LedgerTransaction[] | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (!open || existing !== null || failed) return;
    let active = true;
    void readExisting(port, imported).then((found) => {
      if (!active) return;
      if (found === null) setFailed(true);
      else setExisting(found);
    });
    return () => {
      active = false;
    };
  }, [open, existing, failed, port, imported]);
  const card = (movement: LedgerTransaction) => (
    <div className="grid gap-0.5 rounded-md bg-accent p-2 text-sm">
      <span className="font-medium [overflow-wrap:anywhere]">
        {movement.description}
      </span>
      {movement.counterparty && (
        <span className="text-muted-foreground">{movement.counterparty}</span>
      )}
      <span className="tabular-nums">
        {facts(t, [
          formatAmount(locale, movement.amount, {
            currency: movement.currency,
          }),
          t(
            `desktop.ledger.import.direction.${movement.direction.toLowerCase()}`,
          ),
          formatDay(locale, movement.date),
        ])}
      </span>
    </div>
  );
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="link" size="xs">
          {t("desktop.ledger.import.compare")}
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        aria-label={t("desktop.ledger.import.compare_title")}
        className="ledger-duplicate grid w-dialog gap-2"
      >
        <p className="font-medium">
          {t("desktop.ledger.import.compare_title")}
        </p>
        <div className="grid gap-1">
          <span className="text-xs text-muted-foreground">
            {t("desktop.ledger.import.compare_imported")}
          </span>
          {card(imported)}
        </div>
        <div className="grid gap-1">
          <span className="text-xs text-muted-foreground">
            {t("desktop.ledger.import.compare_existing")}
          </span>
          {failed ? (
            <p role="alert" className="text-sm">
              {t("desktop.ledger.import.compare_failed")}
            </p>
          ) : existing === null ? (
            <Spinner label={t("desktop.ledger.import.compare_reading")} />
          ) : existing.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {t("desktop.ledger.import.compare_none")}
            </p>
          ) : (
            existing.map((movement) => (
              <div key={movement.transaction_id}>{card(movement)}</div>
            ))
          )}
        </div>
        <p className="text-xs text-muted-foreground">
          {t("desktop.ledger.import.compare_note")}
        </p>
      </PopoverContent>
    </Popover>
  );
}

type RefusedRow = InvoiceImportResult["refused"][number];

/** The rows an import refused, each with its reason; the
 * columns can be sorted and dragged to a width. */
function RefusedRows({
  t,
  count,
  refused,
}: {
  t: Translate;
  count(value: number): string;
  refused: readonly RefusedRow[];
}) {
  const row = t("desktop.ledger.import.row");
  const reason = t("desktop.ledger.import.reason");
  const columns: ViewColumn<RefusedRow>[] = [
    { id: "row", label: row, name: row, sortValue: (item) => item.row_number },
    {
      id: "reason",
      label: reason,
      name: reason,
      sortValue: (item) => item.reason,
    },
  ];
  const view = useTableView({
    columns,
    rows: refused,
    resizeLabel: (column) => t("desktop.table.resize_column", { column }),
  });
  return (
    <table
      className="ledger-import-refused w-full text-sm"
      {...view.tableProps}
    >
      <caption className="text-left font-medium">
        {t("desktop.ledger.import.refused_rows")}
      </caption>
      <thead>
        <tr className="text-left text-muted-foreground">{view.headers}</tr>
      </thead>
      <tbody>
        {view.rows.map((item) => (
          <tr
            key={`${item.row_number}:${item.field}`}
            className="border-t border-border align-top"
          >
            <td className="py-1 pr-3 tabular-nums">{count(item.row_number)}</td>
            <td className="py-1 [overflow-wrap:anywhere]">{item.reason}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** The import's last step: what each file's apply wrote, refused or left
 * unknown, and the likely duplicates it flagged. */
export function ImportResultStep({
  t,
  locale,
  count,
  port,
  outcome,
  duplicates,
  progressText,
  showFailed,
}: {
  t: Translate;
  locale: string;
  count(value: number): string;
  port: LedgerPort;
  outcome: ImportOutcome;
  duplicates: LedgerTransaction[];
  progressText: string | null;
  showFailed: boolean;
}) {
  const unknown = (names: string[]) => (
    <Alert tone="danger" role="alert" icon={<Icon name="unknown" />}>
      <AlertTitle>{t("desktop.ledger.import.unknown")}</AlertTitle>
      <AlertDescription>
        {t("desktop.ledger.import.unknown_note", {
          names: listOf(locale, names),
        })}
      </AlertDescription>
    </Alert>
  );
  if (outcome.kind === "bank") {
    const imported = outcome.applied.filter(
      (item): item is Extract<BankApplied, { kind: "imported" }> =>
        item.kind === "imported",
    );
    const sum = (pick: (result: LedgerImportResult) => number) =>
      imported.reduce((total, item) => total + pick(item.result), 0);
    const flagged = sum((result) => result.likely_duplicates);
    const unknownFiles = outcome.applied.filter(
      (item) => item.kind === "unknown",
    );
    return (
      <>
        {imported.length > 0 && (
          <Alert tone="success" icon={<Icon name="check" />}>
            <AlertTitle>
              {t("desktop.ledger.import.imported", {
                count: sum((result) => result.imported),
              })}
            </AlertTitle>
            <AlertDescription>
              {t("desktop.ledger.import.imported_note", {
                skipped: sum((result) => result.skipped),
                flagged,
              })}
            </AlertDescription>
          </Alert>
        )}
        {unknownFiles.length > 0 &&
          unknown(unknownFiles.map((item) => item.file.name))}
        {showFailed && (
          <p role="alert" className="text-sm">
            {t("desktop.ledger.import.show_failed")}
          </p>
        )}
        <ul
          aria-label={t("desktop.ledger.import.files")}
          className="ledger-import-result grid gap-1"
        >
          {outcome.applied.map((item) => (
            <FileRow
              key={item.file.token}
              name={item.file.name}
              refused={item.kind === "refused" || item.kind === "changed"}
              icon={
                item.kind === "unknown"
                  ? "unknown"
                  : item.kind === "not_sent"
                    ? "pending"
                    : item.kind === "imported"
                      ? "check"
                      : undefined
              }
            >
              <span className="text-sm">
                {item.kind === "imported"
                  ? t("desktop.ledger.import.file_imported", {
                      fresh: count(item.result.imported),
                      skipped: count(item.result.skipped),
                    })
                  : item.kind === "changed"
                    ? importRefusal(t, "source_changed")
                    : item.kind === "refused"
                      ? importRefusal(t, item.reason, item.setup ?? null)
                      : item.kind === "unknown"
                        ? t("desktop.ledger.import.file_unknown")
                        : t("desktop.ledger.import.file_not_sent")}
              </span>
              {item.kind === "refused" && (
                <SetupOffer action={item.setup ?? null} className="mt-1" />
              )}
            </FileRow>
          ))}
        </ul>
        {flagged > 0 && (
          <section
            aria-label={t("desktop.ledger.import.duplicates")}
            className="grid gap-1"
          >
            <h4 className="text-sm font-medium">
              {t("desktop.ledger.import.duplicates")}
            </h4>
            <ul className="ledger-import-duplicates grid gap-1">
              {duplicates.map((movement) => (
                <li
                  key={movement.transaction_id}
                  className="flex flex-wrap items-center gap-2 text-sm"
                >
                  <Icon name="alert" size="xs" className="text-warning" />
                  <span className="tabular-nums">
                    {facts(t, [
                      formatDay(locale, movement.date),
                      formatAmount(locale, movement.amount, {
                        currency: movement.currency,
                      }),
                    ])}
                  </span>
                  <span className="min-w-0 [overflow-wrap:anywhere]">
                    {movement.description}
                  </span>
                  <DuplicateCompare
                    port={port}
                    locale={locale}
                    imported={movement}
                  />
                </li>
              ))}
            </ul>
            {flagged > duplicates.length && duplicates.length > 0 && (
              <p className="text-xs text-muted-foreground">
                {t("desktop.ledger.import.duplicates_more", {
                  count: flagged - duplicates.length,
                })}
              </p>
            )}
          </section>
        )}
        {progressText && (
          <p role="status" className="text-sm">
            {progressText}
          </p>
        )}
      </>
    );
  }
  if (outcome.kind === "book") {
    const { answer } = outcome;
    if (answer.kind === "failed" && answer.code === "unknown")
      return unknown([outcome.file.name]);
    if (answer.kind !== "settled")
      return (
        <Alert tone="danger" role="alert" icon={<Icon name="refused" />}>
          <AlertTitle>{t("desktop.ledger.import.book_refused")}</AlertTitle>
        </Alert>
      );
    const result = answer.result;
    return (
      <>
        <Alert tone="success" icon={<Icon name="check" />}>
          <AlertTitle>
            {t("desktop.ledger.import.book_created", { count: result.created })}
          </AlertTitle>
          <AlertDescription>
            {t("desktop.ledger.import.book_note", {
              rows: count(result.rows),
              skipped: count(result.skipped_duplicate),
              refused: count(result.refused.length),
            })}
          </AlertDescription>
        </Alert>
        {result.refused.length > 0 && (
          <RefusedRows t={t} count={count} refused={result.refused} />
        )}
        {result.unmapped_column_headers.length > 0 && (
          <p className="text-sm text-muted-foreground">
            {t("desktop.ledger.import.unmapped", {
              columns: listOf(locale, result.unmapped_column_headers),
            })}
          </p>
        )}
      </>
    );
  }
  const { applied } = outcome;
  const by = (status: string) =>
    applied.items.filter((item) => item.status === status).length;
  const refused = applied.items.filter((item) => item.status === "refused");
  return (
    <>
      {applied.items.length > 0 && (
        <Alert tone="success" icon={<Icon name="check" />}>
          <AlertTitle>
            {t("desktop.ledger.import.documents_added", {
              count: by("ingested") + by("pending_review"),
            })}
          </AlertTitle>
          <AlertDescription>
            {t("desktop.ledger.import.documents_result", {
              waiting: count(by("pending_review")),
              held: count(by("no_op")),
              paused: count(by("paused")),
            })}
          </AlertDescription>
        </Alert>
      )}
      {applied.stopped &&
        (applied.stopped.code === "unknown" ? (
          unknown(applied.stopped.files.map((file) => file.name))
        ) : applied.stopped.code === "saved_unread" ? (
          <Alert tone="warning" role="alert" icon={<Icon name="unknown" />}>
            <AlertTitle>
              {t("desktop.ledger.apply.outcome.saved_unread")}
            </AlertTitle>
            <AlertDescription>
              {listOf(
                locale,
                applied.stopped.files.map((file) => file.name),
              )}
            </AlertDescription>
          </Alert>
        ) : (
          <Alert tone="danger" role="alert" icon={<Icon name="refused" />}>
            <AlertTitle>
              {t("desktop.ledger.import.documents_refused")}
            </AlertTitle>
          </Alert>
        ))}
      {applied.paused && (
        <Alert
          tone="warning"
          icon={<Icon name="pause" />}
          className="ledger-batch-paused"
        >
          <AlertDescription>
            {applied.paused.action !== null
              ? t("desktop.ledger.documents.paused_local_ai")
              : t("desktop.ledger.documents.paused_unavailable")}
            <SetupOffer action={applied.paused.action} className="mt-1" />
          </AlertDescription>
        </Alert>
      )}
      {(refused.length > 0 ||
        applied.unresolved.length > 0 ||
        applied.notSent.length > 0) && (
        <ul
          aria-label={t("desktop.ledger.import.files")}
          className="ledger-import-result grid gap-1"
        >
          {refused.map((item) => (
            <FileRow key={item.identity} name={item.source_name} refused>
              <span className="text-sm">
                {t("desktop.ledger.import.refusal.other", {
                  code: item.refusal_code ?? "refused",
                })}
              </span>
            </FileRow>
          ))}
          {applied.unresolved.map((item) => (
            <FileRow
              key={`${item.source_name}:${item.refusal_code}`}
              name={item.source_name}
              refused
            >
              <span className="text-sm">
                {t("desktop.ledger.import.refusal.other", {
                  code: item.refusal_code,
                })}
              </span>
            </FileRow>
          ))}
          {applied.notSent.map((file) => (
            <FileRow key={file.token} name={file.name} icon="pending">
              <span className="text-sm">
                {t("desktop.ledger.import.file_not_sent")}
              </span>
            </FileRow>
          ))}
        </ul>
      )}
    </>
  );
}
