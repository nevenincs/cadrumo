import { useEffect, useId, useMemo, useRef, useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import {
  SegmentedControl,
  SegmentedControlItem,
} from "@/components/ui/segmented-control";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import {
  ledgerFailure,
  type LedgerExportFormat,
  type LedgerExportResult,
  type LedgerPort,
  type LedgerRow,
  type LedgerStatusResult,
  type PickedFile,
} from "../../../shell/ledger";
import {
  periodSpan,
  publicPeriod,
  type LedgerPeriod,
} from "../../../shell/ledgerGrammar";
import { readAnswer } from "../../../shell/ledgerWindow";
import { useStrings } from "../../../shell/strings";
import { PeriodSelector } from "../PeriodSelector";
import {
  INVOICE_TSV_COLUMNS,
  MOVEMENT_TSV_COLUMNS,
  invoicesTsv,
  movementsTsv,
} from "./tsv";
import { exportFileName } from "./transferWords";

const FORMATS: readonly LedgerExportFormat[] = ["csv", "jsonl", "xlsx"];

type Status =
  | { kind: "reading" }
  | { kind: "read"; status: LedgerStatusResult }
  | { kind: "failed" };
type Sent =
  | { kind: "idle" }
  | { kind: "sending" }
  | { kind: "done"; result: LedgerExportResult }
  | { kind: "refused"; reason: string }
  /** Sent and not seen to settle: the file may have been written. */
  | { kind: "unknown" };

/**
 * Exports a period of the ledger to a local file: the format, the period
 * and whether to take archived and set-aside movements, then the file,
 * chosen last in the host's save dialog, which asks before replacing one.
 * Only the file's name is shown. Changing the format or the period clears
 * it.
 */
export function ExportDialog({
  port,
  locale,
  period: pagePeriod,
  years,
  fallbackYear,
  format: lastFormat,
  onFormat,
  staged,
  onReviewStaged,
  selection,
  copy,
  onClose,
}: {
  port: LedgerPort;
  locale: string;
  period: LedgerPeriod | null;
  years: readonly number[] | null;
  fallbackYear: number;
  /** The format chosen last time, kept as a presentation preference. */
  format: LedgerExportFormat;
  onFormat(format: LedgerExportFormat): void;
  /** How many changes are staged and not saved. */
  staged: number;
  /** Opens the review of the staged changes, where the page has one. */
  onReviewStaged?: () => void;
  /** The movements selected in the grid, offered as text to copy. */
  selection?: readonly LedgerRow[];
  copy(text: string): Promise<void>;
  onClose(): void;
}) {
  const t = useStrings();
  const ids = useId();
  const heading = useRef<HTMLHeadingElement>(null);
  const numbers = useMemo(() => new Intl.NumberFormat(locale), [locale]);
  const count = (value: number) => numbers.format(value);
  const [format, setFormatNow] = useState<LedgerExportFormat>(lastFormat);
  const [period, setPeriodNow] = useState<LedgerPeriod | null>(pagePeriod);
  const [inactive, setInactive] = useState(false);
  const [target, setTarget] = useState<PickedFile | null>(null);
  const [saveRefused, setSaveRefused] = useState(false);
  const [choosing, setChoosing] = useState(false);
  const [without, setWithout] = useState(false);
  const [status, setStatus] = useState<Status>({ kind: "reading" });
  const [sent, setSent] = useState<Sent>({ kind: "idle" });
  const [copied, setCopied] = useState<string | null>(null);
  /** The token of the file chosen, held for forgetting. */
  const held = useRef(new Set<PickedFile["token"]>());

  const forgetHeld = () => {
    const tokens = [...held.current];
    held.current.clear();
    if (tokens.length > 0) void port.forgetFiles(tokens).catch(() => {});
  };
  // The token goes with the dialog.
  useEffect(() => {
    const tokens = held.current;
    return () => {
      if (tokens.size > 0) void port.forgetFiles([...tokens]).catch(() => {});
    };
  }, [port]);
  const destination = (file: PickedFile | null) => {
    forgetHeld();
    if (file) held.current.add(file.token);
    setTarget(file);
  };
  // The file was chosen for one format and one period's export.
  const setFormat = (next: LedgerExportFormat) => {
    if (next === format) return;
    destination(null);
    setFormatNow(next);
    onFormat(next);
  };
  const setPeriod = (next: LedgerPeriod | null) => {
    destination(null);
    setPeriodNow(next);
  };

  useEffect(() => {
    let active = true;
    setStatus({ kind: "reading" });
    void port
      .submit("ledger.status", { period: period ? publicPeriod(period) : null })
      .then((outcome) => {
        if (!active) return;
        const read = readAnswer(outcome);
        setStatus(
          read.kind === "answer"
            ? { kind: "read", status: read.result }
            : { kind: "failed" },
        );
      })
      .catch(() => active && setStatus({ kind: "failed" }));
    return () => {
      active = false;
    };
  }, [port, period]);

  const choose = async () => {
    setChoosing(true);
    setSaveRefused(false);
    try {
      const picks = await port.saveFile(
        format,
        t(`desktop.ledger.export.filter.${format}`),
        exportFileName(t, period, format),
      );
      const file = picks.files[0] ?? null;
      if (file) destination(file);
      else if (picks.refused > 0) setSaveRefused(true);
    } catch {
      setSaveRefused(true);
    } finally {
      setChoosing(false);
    }
  };

  const send = async () => {
    if (!target) return;
    setSent({ kind: "sending" });
    try {
      const outcome = await port.submit("ledger.export", {
        output_path: target.token,
        export_format: format,
        include_inactive: inactive,
        period: period ? publicPeriod(period) : null,
      });
      if (outcome.kind === "settled")
        setSent({ kind: "done", result: outcome.result });
      else if (outcome.kind === "refused")
        setSent({ kind: "refused", reason: outcome.reason ?? "refused" });
      else setSent({ kind: "unknown" });
    } catch (error) {
      const failure = ledgerFailure(error);
      setSent(
        failure.code === "unknown" || failure.code === "saved_unread"
          ? { kind: "unknown" }
          : { kind: "refused", reason: failure.reason ?? failure.code },
      );
    }
  };

  const copyInvoices = async () => {
    setCopied(null);
    try {
      const read = readAnswer(await port.submit("ledger.invoice.list", {}));
      if (read.kind !== "answer") throw new Error("unread");
      const span = period ? periodSpan(period) : null;
      const invoices = read.result.invoices.filter(
        (invoice) =>
          !span ||
          (invoice.issued_at >= span.from && invoice.issued_at <= span.to),
      );
      await copy(
        invoicesTsv(
          INVOICE_TSV_COLUMNS.map((column) =>
            t(`desktop.ledger.export.tsv.${column}`),
          ),
          invoices,
        ),
      );
      setCopied(
        t("desktop.ledger.export.copied_invoices", { count: invoices.length }),
      );
    } catch {
      setCopied(t("desktop.ledger.export.copy_failed"));
    }
  };
  const copySelection = async () => {
    if (!selection) return;
    setCopied(null);
    try {
      await copy(
        movementsTsv(
          MOVEMENT_TSV_COLUMNS.map((column) =>
            t(`desktop.ledger.export.tsv.${column}`),
          ),
          selection,
        ),
      );
      setCopied(
        t("desktop.ledger.export.copied_movements", {
          count: selection.length,
        }),
      );
    } catch {
      setCopied(t("desktop.ledger.export.copy_failed"));
    }
  };

  const read = status.kind === "read" ? status.status : null;
  const exported = read
    ? inactive
      ? read.total_count
      : read.active_count
    : null;
  const leftOut = read && !inactive ? read.total_count - read.active_count : 0;
  const blockedByStaged = staged > 0 && !without;
  const done = sent.kind === "done";

  return (
    <Dialog
      open
      onOpenChange={(open) => !open && sent.kind !== "sending" && onClose()}
    >
      <DialogContent
        placement="top"
        closeLabel={t("desktop.ledger.export.close")}
        className="ledger-export w-dialog-md overflow-y-auto"
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          heading.current?.focus();
        }}
      >
        <DialogHeader>
          <DialogTitle>{t("desktop.ledger.export.title")}</DialogTitle>
          <DialogDescription>
            {t("desktop.ledger.export.description")}
          </DialogDescription>
        </DialogHeader>
        <h3
          ref={heading}
          tabIndex={-1}
          className="ledger-export-step font-medium text-foreground"
        >
          {t(
            done
              ? "desktop.ledger.export.heading_done"
              : "desktop.ledger.export.heading",
          )}
        </h3>
        {done ? (
          <Alert tone="success" icon={<Icon name="check" />}>
            <AlertTitle>{t("desktop.ledger.export.done")}</AlertTitle>
            <AlertDescription>
              {t("desktop.ledger.export.done_note", {
                count: sent.result.row_count,
                name: sent.result.output_path,
              })}
            </AlertDescription>
          </Alert>
        ) : (
          <div className="grid gap-4">
            {selection && selection.length > 0 && (
              <Alert icon={<Icon name="info" />}>
                <AlertTitle>
                  {t("desktop.ledger.export.selection", {
                    count: selection.length,
                  })}
                </AlertTitle>
                <AlertDescription>
                  {t("desktop.ledger.export.selection_note")}
                </AlertDescription>
                <Button
                  variant="outline"
                  size="xs"
                  className="justify-self-start"
                  onClick={() => void copySelection()}
                >
                  <Icon name="copy" />
                  {t("desktop.ledger.export.copy_selection")}
                </Button>
              </Alert>
            )}
            <Field>
              <FieldLabel id={`${ids}-format`}>
                {t("desktop.ledger.export.format")}
              </FieldLabel>
              <SegmentedControl
                aria-labelledby={`${ids}-format`}
                value={format}
                onValueChange={(next) => setFormat(next as LedgerExportFormat)}
              >
                {FORMATS.map((value) => (
                  <SegmentedControlItem key={value} value={value}>
                    {t(`desktop.ledger.export.format_${value}`)}
                  </SegmentedControlItem>
                ))}
              </SegmentedControl>
            </Field>
            <Field>
              <FieldLabel id={`${ids}-period`}>
                {t("desktop.ledger.export.period")}
              </FieldLabel>
              <PeriodSelector
                value={period}
                onChange={setPeriod}
                label={t("desktop.ledger.export.period")}
                years={years}
                locale={locale}
                fallbackYear={fallbackYear}
                className="justify-self-start"
              />
            </Field>
            <label className="flex items-center gap-2 text-sm">
              <Switch checked={inactive} onCheckedChange={setInactive} />
              {t("desktop.ledger.export.inactive")}
            </label>
            <p
              className="ledger-export-count text-sm text-muted-foreground"
              aria-live="polite"
            >
              {status.kind === "reading" ? (
                <span className="flex items-center gap-2">
                  <Spinner />
                  {t("desktop.ledger.export.counting")}
                </span>
              ) : exported === null ? (
                t("desktop.ledger.export.count_unknown")
              ) : (
                <>
                  {t("desktop.ledger.export.count", {
                    count: exported,
                    shown: count(exported),
                  })}
                  {leftOut > 0 &&
                    read &&
                    ` ${t("desktop.ledger.export.left_out", {
                      archived: count(read.archived_count),
                      aside: count(read.stashed_count),
                      split: count(read.split_count),
                    })}`}
                </>
              )}
            </p>
            {read?.ready === false && (
              <Alert tone="warning" icon={<Icon name="alert" />}>
                <AlertTitle>{t("desktop.ledger.export.not_ready")}</AlertTitle>
                <AlertDescription>
                  {t("desktop.ledger.export.not_ready_note", {
                    count: read.readiness_issue_count,
                  })}
                </AlertDescription>
              </Alert>
            )}
            {staged > 0 && (
              <Alert tone="warning" icon={<Icon name="alert" />}>
                <AlertTitle>
                  {t("desktop.ledger.export.staged", { count: staged })}
                </AlertTitle>
                <AlertDescription>
                  {t("desktop.ledger.export.staged_note")}
                </AlertDescription>
                <div className="flex flex-wrap gap-2">
                  {onReviewStaged && (
                    <Button
                      size="xs"
                      onClick={() => {
                        onClose();
                        onReviewStaged();
                      }}
                    >
                      {t("desktop.ledger.export.review_staged")}
                    </Button>
                  )}
                  <Button
                    size="xs"
                    variant="outline"
                    aria-pressed={without}
                    onClick={() => setWithout(!without)}
                  >
                    {t("desktop.ledger.export.without_staged")}
                  </Button>
                </div>
              </Alert>
            )}
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => void copyInvoices()}
              >
                <Icon name="copy" />
                {t("desktop.ledger.export.copy_invoices")}
              </Button>
              {copied && (
                <span role="status" className="text-sm text-muted-foreground">
                  {copied}
                </span>
              )}
            </div>
            <Field>
              <FieldLabel id={`${ids}-file`}>
                {t("desktop.ledger.export.file")}
              </FieldLabel>
              <div className="flex flex-wrap items-center gap-2">
                <span
                  aria-labelledby={`${ids}-file`}
                  className="ledger-export-file min-w-0 flex-1 font-medium [overflow-wrap:anywhere]"
                >
                  {target?.name ?? (
                    <span className="font-normal text-muted-foreground">
                      {t("desktop.ledger.export.no_file")}
                    </span>
                  )}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  pending={choosing}
                  onClick={() => void choose()}
                >
                  {t(
                    target
                      ? "desktop.ledger.export.change_file"
                      : "desktop.ledger.export.choose_file",
                  )}
                </Button>
              </div>
              <FieldDescription>
                {saveRefused
                  ? t("desktop.ledger.export.save_refused", { format })
                  : t("desktop.ledger.export.file_hint")}
              </FieldDescription>
            </Field>
            {sent.kind === "refused" && (
              <Alert tone="danger" role="alert" icon={<Icon name="refused" />}>
                <AlertTitle>{t("desktop.ledger.export.refused")}</AlertTitle>
                <AlertDescription>
                  <code className="font-mono text-xs">{sent.reason}</code>
                </AlertDescription>
              </Alert>
            )}
            {sent.kind === "unknown" && (
              <Alert tone="danger" role="alert" icon={<Icon name="unknown" />}>
                <AlertTitle>{t("desktop.ledger.export.unknown")}</AlertTitle>
                <AlertDescription>
                  {t("desktop.ledger.export.unknown_note")}
                </AlertDescription>
              </Alert>
            )}
          </div>
        )}
        <DialogFooter>
          {done ? (
            <Button onClick={onClose}>
              {t("desktop.ledger.export.close")}
            </Button>
          ) : (
            <>
              <Button variant="ghost" onClick={onClose}>
                {t("desktop.ledger.export.cancel")}
              </Button>
              <Button
                pending={sent.kind === "sending"}
                disabled={
                  !target ||
                  blockedByStaged ||
                  sent.kind === "unknown" ||
                  exported === null
                }
                onClick={() => void send()}
              >
                {exported === null
                  ? t("desktop.ledger.export.send_unknown")
                  : t("desktop.ledger.export.send", {
                      count: exported,
                      shown: count(exported),
                    })}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
