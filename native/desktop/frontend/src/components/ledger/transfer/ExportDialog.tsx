import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
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
import {
  checkReadiness,
  readAnswer,
  readinessSnapshot,
  readWindow,
  type Readiness,
} from "../../../shell/ledgerWindow";
import { useStrings } from "../../../shell/strings";
import { formatCount } from "../../../shared/numbers";
import { periodText } from "../ledgerWords";
import { NO_FILTERS, readinessSets } from "../movements/movementsModel";
import { ReadinessStrip } from "../movements/ReadinessStrip";
import { PeriodSelector } from "../PeriodSelector";
import { useWritePause, WriteHold } from "../WritePause";
import {
  INVOICE_TSV_COLUMNS,
  MOVEMENT_TSV_COLUMNS,
  invoicesTsv,
  movementsTsv,
} from "./tsv";
import { exportFileName } from "./transferWords";

const FORMATS: readonly LedgerExportFormat[] = ["csv", "jsonl", "xlsx"];

const samePeriod = (left: LedgerPeriod | null, right: LedgerPeriod | null) =>
  left === right ||
  (left !== null &&
    right !== null &&
    left.year === right.year &&
    left.code === right.code);

/** The movements an export takes, by lifecycle state. */
type Counts = {
  total: number;
  active: number;
  archived: number;
  stashed: number;
  split: number;
};
type Status =
  { kind: "reading" } | { kind: "read"; counts: Counts } | { kind: "failed" };

/** The status read's counts span the whole ledger: they are the counts of
 * "All periods", and of no single period. */
const ledgerCounts = (status: LedgerStatusResult): Counts => ({
  total: status.total_count,
  active: status.active_count,
  archived: status.archived_count,
  stashed: status.stashed_count,
  split: status.split_count,
});
/** A period's counts, from its own movements. */
function periodCounts(rows: readonly LedgerRow[]): Counts {
  const of = (state: string) =>
    rows.filter((row) => row.transaction.lifecycle_state === state).length;
  return {
    total: rows.length,
    active: of("ACTIVE"),
    archived: of("ARCHIVED"),
    stashed: of("STASHED"),
    split: of("SPLIT"),
  };
}
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
  onCloseAutoFocus,
  readiness,
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
  /** Where the focus goes once the dialog has gone. */
  onCloseAutoFocus?: (event: Event) => void;
  /** The page's readiness pills, which count the page's period: shown
   * while the export takes that period, so both say the same. */
  readiness?: ReactNode;
}) {
  const t = useStrings();
  const ids = useId();
  const heading = useRef<HTMLHeadingElement>(null);
  const count = (value: number) => formatCount(locale, value);
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
    const counted: Promise<Counts | null> =
      period === null
        ? port.submit("ledger.status", { period: null }).then((outcome) => {
            const read = readAnswer(outcome);
            return read.kind === "answer" ? ledgerCounts(read.result) : null;
          })
        : readWindow(port, period).then((read) =>
            read.kind === "read" ? periodCounts(read.rows) : null,
          );
    void counted
      .then((counts) => {
        if (!active) return;
        setStatus(counts ? { kind: "read", counts } : { kind: "failed" });
      })
      .catch(() => active && setStatus({ kind: "failed" }));
    return () => {
      active = false;
    };
  }, [port, period]);

  // Another period than the page's is checked here, and said with the same
  // strip; its pills only say, since the grid shows the page's period.
  const otherPeriod = !samePeriod(period, pagePeriod);
  const [own, setOwn] = useState<{
    period: LedgerPeriod | null;
    readiness: Readiness;
  } | null>(null);
  const [checkAgain, setCheckAgain] = useState(0);
  useEffect(() => {
    if (!otherPeriod) return;
    let active = true;
    setOwn((current) => ({
      period,
      readiness: {
        kind: "checking",
        held:
          current && samePeriod(current.period, period)
            ? readinessSnapshot(current.readiness)
            : null,
      },
    }));
    void checkReadiness(port, period, Date.now).then((answer) => {
      if (!active) return;
      setOwn({
        period,
        readiness:
          answer.kind === "checked"
            ? answer
            : { kind: "failed", failure: answer.failure, held: null },
      });
    });
    return () => {
      active = false;
    };
  }, [port, period, otherPeriod, checkAgain]);
  const ownReadiness = useMemo<Readiness>(
    () =>
      own && samePeriod(own.period, period)
        ? own.readiness
        : { kind: "not_checked" },
    [own, period],
  );
  const ownSets = useMemo(
    () => readinessSets([], readinessSnapshot(ownReadiness)),
    [ownReadiness],
  );

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

  const pause = useWritePause();
  /** An export not seen to settle holds every write on the page, this
   * export too. No read of the ledger shows the file, so a re-read cannot
   * settle it: the person checks the file and releases it. */
  const unseen = (file: PickedFile) => {
    setSent({ kind: "unknown" });
    // The hold keeps the file's token to show the file, and forgets it
    // once released: closing the dialog no longer does.
    held.current.delete(file.token);
    pause.hold({
      what: file.name,
      outcome: "unknown",
      settle: async () => ({
        held: [t("desktop.ledger.export.unknown_untold", { file: file.name })],
      }),
      checked: {
        title: t("desktop.ledger.export.unknown_title"),
        release: t("desktop.ledger.export.checked"),
        look: {
          label: t("desktop.ledger.export.show_in_folder"),
          run: async () => {
            try {
              await port.revealFile(file.token);
              return null;
            } catch (error) {
              // Not there is itself an answer: the export did not write it.
              return ledgerFailure(error).code === "file_unavailable"
                ? t("desktop.ledger.export.not_there", { file: file.name })
                : t("desktop.ledger.export.show_failed");
            }
          },
        },
      },
      onReleased: () => {
        void port.forgetFiles([file.token]).catch(() => {});
      },
    });
  };
  const send = async () => {
    if (!target || pause.held !== null) return;
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
      else unseen(target);
    } catch (error) {
      const failure = ledgerFailure(error);
      if (failure.code === "unknown" || failure.code === "saved_unread")
        unseen(target);
      else setSent({ kind: "refused", reason: failure.reason ?? failure.code });
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

  const read = status.kind === "read" ? status.counts : null;
  const exported = read ? (inactive ? read.total : read.active) : null;
  const leftOut = read && !inactive ? read.total - read.active : 0;
  const blockedByStaged = staged > 0 && !without;
  const done = sent.kind === "done";
  // The result is a step of its own: focus moves to its heading.
  useEffect(() => {
    if (done) heading.current?.focus();
  }, [done]);

  return (
    <Dialog
      open
      onOpenChange={(open) => !open && sent.kind !== "sending" && onClose()}
    >
      <DialogContent
        placement="top"
        closeLabel={t("desktop.ledger.export.close")}
        // The body grows to the dialog's height before it scrolls, and only
        // the body scrolls: the actions stay below it, never over it.
        className="ledger-export flex w-dialog-md flex-col"
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          heading.current?.focus();
        }}
        onCloseAutoFocus={onCloseAutoFocus}
        aria-describedby={undefined}
      >
        <DialogHeader>
          <div className="flex items-center gap-1">
            <DialogTitle>{t("desktop.ledger.export.title")}</DialogTitle>
            <IconButton
              label={t("desktop.ledger.export.description")}
              size="xs"
              className="ledger-export-about size-control-xs"
            >
              <Icon name="info" size="xs" />
            </IconButton>
          </div>
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
          <div className="ledger-export-body -mx-5 grid min-h-0 shrink gap-4 overflow-y-auto px-5">
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
              className="ledger-export-count text-sm text-muted-foreground empty:hidden"
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
                leftOut > 0 &&
                read &&
                t("desktop.ledger.export.left_out", {
                  archived: count(read.archived),
                  aside: count(read.stashed),
                  split: count(read.split),
                })
              )}
            </p>
            {!otherPeriod ? (
              readiness && (
                <div className="ledger-export-readiness">{readiness}</div>
              )
            ) : (
              <div className="ledger-export-readiness">
                <ReadinessStrip
                  readiness={ownReadiness}
                  sets={ownSets}
                  filters={NO_FILTERS}
                  locale={locale}
                  unsaved={staged}
                  stagedClassify={0}
                  periodName={periodText(t, locale, period)}
                  onCheck={() => setCheckAgain((count) => count + 1)}
                />
              </div>
            )}
            {staged > 0 && without && (
              <Alert
                icon={<Icon name="alert" />}
                className="ledger-export-staged"
              >
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span className="min-w-0 flex-1">
                    {t("desktop.ledger.export.staged_short", {
                      count: staged,
                    })}
                  </span>
                  {onReviewStaged && (
                    <Button
                      size="xs"
                      variant="ghost"
                      className="shrink-0"
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
                    className="shrink-0"
                    aria-pressed
                    onClick={() => setWithout(false)}
                  >
                    {t("desktop.ledger.export.without_staged")}
                  </Button>
                </div>
              </Alert>
            )}
            {staged > 0 && !without && (
              <Alert
                tone="warning"
                icon={<Icon name="alert" />}
                className="ledger-export-staged"
              >
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
                    aria-pressed={false}
                    onClick={() => setWithout(true)}
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
              <div className="flex items-center gap-1">
                <FieldLabel id={`${ids}-file`}>
                  {t("desktop.ledger.export.file")}
                </FieldLabel>
                <IconButton
                  label={t("desktop.ledger.export.file_hint")}
                  size="xs"
                  className="size-control-xs"
                >
                  <Icon name="info" size="xs" />
                </IconButton>
              </div>
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
              {saveRefused && (
                <FieldDescription>
                  {t("desktop.ledger.export.save_refused", { format })}
                </FieldDescription>
              )}
            </Field>
            {sent.kind === "refused" && (
              <Alert tone="danger" role="alert" icon={<Icon name="refused" />}>
                <AlertTitle>{t("desktop.ledger.export.refused")}</AlertTitle>
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
              <WriteHold>
                <Button
                  className="ledger-export-send"
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
              </WriteHold>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
