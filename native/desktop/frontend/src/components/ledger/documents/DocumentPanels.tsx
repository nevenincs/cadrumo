import { Fragment, useId, useState, type ReactNode } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty";
import { FieldLabel } from "@/components/ui/field";
import { Icon, type IconName } from "@/components/ui/icon";
import {
  SegmentedControl,
  SegmentedControlItem,
} from "@/components/ui/segmented-control";
import { Spinner } from "@/components/ui/spinner";
import { useTableView, type ViewColumn } from "@/components/ui/table-view";
import { listed } from "../../../shell/compose";
import { useProvisioning } from "../../../shell/provisioning";
import {
  provisionActionOf,
  setupActionOf,
} from "../../../shell/provisioningRecovery";
import type {
  AttachmentReviewItem,
  EvidenceConsentListResult,
  EvidenceRecord,
  FilePick,
  InvoiceKind,
  LedgerPort,
  PickedFile,
} from "../../../shell/ledger";
import { useStrings, type Translate } from "../../../shell/strings";
import { formatTime } from "../../../shared/dateFormats";
import { SetupOffer } from "../../setup/SetupOffer";
import { rowTone } from "../../setup/setupWords";
import { kindChoice } from "../invoices/invoiceWords";
import { applyDocuments, type DocumentsApplied } from "../transfer/importModel";
import { sizeText } from "../transfer/transferWords";
import { write } from "../invoices/invoiceWrites";
import { landingSettle, useWritePause, WriteHold } from "../WritePause";
import { batchStatusLabel, sourceLabel } from "./documentWords";
import { extractionLanding } from "./documentLanding";
import { fileName } from "./documentsModel";
import type { Read } from "./useLedgerRead";

function Failed({
  t,
  read,
  onRetry,
}: {
  t: Translate;
  read: Read<unknown>;
  onRetry(): void;
}) {
  if (read.phase !== "failed") return null;
  return (
    <EmptyState
      className="ledger-documents-failed"
      icon="alert"
      description={
        <span role="alert">{t("desktop.ledger.documents.read_failed")}</span>
      }
    >
      <Button variant="outline" onClick={onRetry}>
        {t("desktop.ledger.retry")}
      </Button>
    </EmptyState>
  );
}
function Reading({ t }: { t: Translate }) {
  return (
    <EmptyState
      className="ledger-documents-loading"
      role="status"
      busy
      description={t("desktop.ledger.loading")}
    />
  );
}

/** A table with its column names, for a panel's rows. Its columns can be
 * dragged to a width, and sorted where they have a way to rank a row. */
function Table<R>({
  label,
  columns,
  rows,
  rowKey,
  renderRow,
}: {
  label: string;
  columns: readonly ViewColumn<R>[];
  rows: readonly R[];
  rowKey(row: R): string;
  renderRow(row: R): ReactNode;
}) {
  const t = useStrings();
  const view = useTableView({
    columns,
    rows,
    resizeLabel: (column) => t("desktop.table.resize_column", { column }),
  });
  return (
    <table aria-label={label} className="w-full text-sm" {...view.tableProps}>
      <thead>
        <tr className="border-b border-border text-left text-muted-foreground">
          {view.headers}
        </tr>
      </thead>
      <tbody>
        {view.rows.map((row) => (
          <Fragment key={rowKey(row)}>{renderRow(row)}</Fragment>
        ))}
      </tbody>
    </table>
  );
}
const cell = "border-b border-border px-2 py-1 align-top";

// ---- Attachments waiting for review -------------------------------------------

/** Stored attachments, from mail or a drive, waiting to be read as
 * invoices. Where each came from is named by its source only. */
export function AttachmentQueue({
  port,
  locale,
  read,
  pending,
  onRetry,
  onReview,
}: {
  port: LedgerPort;
  locale: string;
  read: Read<{ rows?: AttachmentReviewItem[] }>;
  /** When each reading waiting for review was drafted, by its reference,
   * for a read not seen to settle to tell its draft from an older one. */
  pending: ReadonlyMap<string, string>;
  onRetry(): void;
  onReview(reference: string): void;
}) {
  const t = useStrings();
  const pause = useWritePause();
  const [reading, setReading] = useState<string | null>(null);
  const [failed, setFailed] = useState<{
    id: string;
    code: string;
    recovery: string | null;
  } | null>(null);
  if (read.phase === "failed")
    return <Failed t={t} read={read} onRetry={onRetry} />;
  if (!read.value) return <Reading t={t} />;
  const rows = read.value.rows ?? [];
  async function readIt(item: AttachmentReviewItem) {
    setReading(item.attachment_id);
    setFailed(null);
    const before = pending.get(item.attachment_id) ?? null;
    const sent = await write(port, "ledger.evidence.extract", {
      attachment_id: item.attachment_id,
    });
    setReading(null);
    if (sent.kind === "unknown") {
      const what = t("desktop.ledger.section.documents");
      pause.hold({
        what,
        outcome: sent.saved ? "saved_unread" : "unknown",
        settle: landingSettle(
          t,
          what,
          extractionLanding(port, item.attachment_id, before),
        ),
      });
    }
    if (sent.kind === "done") onReview(item.attachment_id);
    else
      setFailed({
        id: item.attachment_id,
        code:
          sent.kind === "unknown"
            ? "unknown"
            : sent.kind === "refused"
              ? (sent.reason ?? "refused")
              : sent.code,
        recovery:
          sent.kind === "refused" ? provisionActionOf(sent.detail) : null,
      });
  }
  if (rows.length === 0)
    return (
      <EmptyState
        className="ledger-attachments-empty"
        icon="check"
        description={t("desktop.ledger.documents.attachments_none")}
      />
    );
  const state = (item: AttachmentReviewItem) =>
    item.pending_review
      ? t("desktop.ledger.documents.attachment_waiting")
      : t("desktop.ledger.documents.attachment_linked", {
          count: item.linked_invoice_ids.length,
        });
  const source = t("desktop.ledger.documents.column.source");
  const kind = t("desktop.ledger.documents.column.kind");
  const size = t("desktop.ledger.documents.column.size");
  const captured = t("desktop.ledger.documents.column.captured");
  const stateName = t("desktop.ledger.documents.column.state");
  const action = t("desktop.ledger.documents.column.action");
  const attachmentColumns: ViewColumn<AttachmentReviewItem>[] = [
    {
      id: "source",
      label: source,
      name: source,
      sortValue: (item) => sourceLabel(t, item.source),
    },
    {
      id: "kind",
      label: kind,
      name: kind,
      sortValue: (item) => item.mime_type,
    },
    {
      id: "size",
      label: size,
      name: size,
      sortValue: (item) => item.bytes_size,
    },
    {
      id: "captured",
      label: captured,
      name: captured,
      sortValue: (item) => item.captured_at,
    },
    {
      id: "state",
      label: stateName,
      name: stateName,
      sortValue: state,
    },
    {
      id: "action",
      label: action,
      name: action,
      resizable: false,
    },
  ];
  return (
    <div className="ledger-attachments p-3">
      <Table
        label={t("desktop.ledger.documents.tab.attachments")}
        columns={attachmentColumns}
        rows={rows}
        rowKey={(item) => item.attachment_id}
        renderRow={(item) => (
          <tr className="ledger-attachment">
            <td className={cell}>{sourceLabel(t, item.source)}</td>
            <td className={cell}>{item.mime_type}</td>
            <td className={`${cell} tabular-nums`}>
              {sizeText(locale, item.bytes_size)}
            </td>
            <td className={`${cell} tabular-nums`}>
              {formatTime(locale, item.captured_at)}
            </td>
            <td className={cell}>
              {state(item)}
              {failed?.id === item.attachment_id && (
                <span role="alert" className="block text-destructive">
                  {t("desktop.ledger.form.failed")}
                </span>
              )}
              {failed?.id === item.attachment_id && (
                <SetupOffer action={failed.recovery} className="mt-1" />
              )}
            </td>
            <td className={cell}>
              <WriteHold>
                <Button
                  size="xs"
                  variant="outline"
                  className="ledger-attachment-read"
                  disabled={reading !== null}
                  aria-busy={reading === item.attachment_id || undefined}
                  onClick={() => void readIt(item)}
                >
                  {reading === item.attachment_id && <Spinner />}
                  {t("desktop.ledger.documents.read_here")}
                </Button>
              </WriteHold>
            </td>
          </tr>
        )}
      />
    </div>
  );
}

// ---- Folder intake ---------------------------------------------------------------

/** A part whose settlement was not seen: it may have saved, or it saved
 * and its answer was not read. */
const unseenCode = (code: string) =>
  code === "unknown" || code === "saved_unread";

const BATCH_ICONS: Record<string, IconName> = {
  ingested: "check",
  no_op: "tick",
  refused: "refused",
  pending_review: "pending",
  paused: "pause",
};

/** One line of a batch's results: a document and what became of it. */
type BatchRow = {
  key: string;
  status: string;
  name: string;
  /** What the outcome is called, to rank the rows by. */
  label: string;
  outcome: ReactNode;
};

function batchRows(t: Translate, applied: DocumentsApplied): BatchRow[] {
  return [
    ...applied.items.map((item) => ({
      key: item.identity,
      status: item.status,
      name: item.source_name,
      label: batchStatusLabel(t, item.status),
      outcome: (
        <span className="inline-flex items-center gap-1">
          <Icon name={BATCH_ICONS[item.status] ?? "info"} size="xs" />
          {batchStatusLabel(t, item.status)}
        </span>
      ),
    })),
    ...applied.unresolved.map((item) => ({
      key: `${item.source_name}:${item.refusal_code}`,
      status: "refused",
      name: item.source_name,
      label: batchStatusLabel(t, "refused"),
      outcome: (
        <span className="inline-flex items-center gap-1">
          <Icon name="refused" size="xs" />
          {batchStatusLabel(t, "refused")}
        </span>
      ),
    })),
    ...applied.notSent.map((file) => ({
      key: file.token,
      status: "not_sent",
      name: file.name,
      label: t("desktop.ledger.documents.not_sent"),
      outcome: t("desktop.ledger.documents.not_sent"),
    })),
  ];
}

/**
 * Every document in a folder, or several files, added as evidence in one
 * direction, which the person says: there is no default. Each document
 * gets its own outcome.
 */
export function FolderIntake({
  port,
  onWritten,
}: {
  port: LedgerPort;
  onWritten(): void;
}) {
  const t = useStrings();
  const pause = useWritePause();
  const label = useId();
  const [direction, setDirection] = useState<InvoiceKind | null>(null);
  const [files, setFiles] = useState<PickedFile[]>([]);
  const [refusedCount, setRefusedCount] = useState(0);
  const [busy, setBusy] = useState<"picking" | "adding" | null>(null);
  const [progress, setProgress] = useState(0);
  const [applied, setApplied] = useState<DocumentsApplied | null>(null);

  const batchColumns: ViewColumn<BatchRow>[] = [
    {
      id: "document",
      label: t("desktop.ledger.documents.column.document"),
      name: t("desktop.ledger.documents.column.document"),
      sortValue: (row) => row.name,
    },
    {
      id: "outcome",
      label: t("desktop.ledger.documents.column.outcome"),
      name: t("desktop.ledger.documents.column.outcome"),
      sortValue: (row) => row.label,
    },
  ];

  async function pick(how: FilePick) {
    setBusy("picking");
    try {
      const picks = await port.pickFiles(
        "documents",
        how,
        t("desktop.ledger.import.filter.documents"),
      );
      setFiles(picks.files);
      setRefusedCount(picks.refused);
      setApplied(null);
    } catch {
      setFiles([]);
    } finally {
      setBusy(null);
    }
  }
  async function add() {
    if (!direction || files.length === 0) return;
    setBusy("adding");
    setProgress(0);
    const done = await applyDocuments(port, files, direction, setProgress);
    setBusy(null);
    setApplied(done);
    const unseen = done.stopped?.code;
    if (unseen === "unknown" || unseen === "saved_unread") {
      const what = listed(
        t,
        done.stopped!.files.map((file) => file.name),
      );
      pause.hold({
        what,
        outcome: unseen,
        // A batch is repeatable: a document the profile already holds by
        // its content address comes back as a no_op, so sending the batch
        // again adds only what did not land. The evidence list answering
        // is what says the ledger can be read again.
        settle: landingSettle(t, what, async () => {
          const read = await port
            .submit("ledger.evidence.list", {})
            .catch(() => null);
          return read?.kind === "settled" ? "repeatable" : null;
        }),
      });
    }
    await port
      .forgetFiles(files.map((file) => file.token))
      .catch(() => undefined);
    setFiles([]);
    onWritten();
  }

  return (
    <div className="ledger-folder grid gap-3 p-3">
      <div className="grid gap-1.5">
        <FieldLabel id={label}>
          {t("desktop.ledger.documents.these_are")}
        </FieldLabel>
        <SegmentedControl
          aria-labelledby={label}
          value={direction ?? ""}
          onValueChange={(value) => setDirection(value as InvoiceKind)}
          className="ledger-folder-direction w-fit"
        >
          {(["received", "issued"] as const).map((kind) => (
            <SegmentedControlItem key={kind} value={kind} className="text-sm">
              {kindChoice(t, kind)}
            </SegmentedControlItem>
          ))}
        </SegmentedControl>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          size="sm"
          variant="outline"
          className="ledger-folder-pick"
          disabled={busy !== null}
          onClick={() => void pick("folder")}
        >
          <Icon name="folder" />
          {t("desktop.ledger.documents.choose_folder")}
        </Button>
        <Button
          size="sm"
          variant="outline"
          className="ledger-folder-files"
          disabled={busy !== null}
          onClick={() => void pick("files")}
        >
          <Icon name="page" />
          {t("desktop.ledger.documents.choose_files")}
        </Button>
        <span className="text-sm text-muted-foreground">
          {t("desktop.ledger.documents.not_recursive")}
        </span>
      </div>
      {files.length > 0 && (
        <div className="grid gap-2">
          <ul
            className="ledger-folder-chosen grid gap-0.5 text-sm"
            aria-label={t("desktop.ledger.documents.chosen")}
          >
            {files.map((file) => (
              <li key={file.token} className="flex items-center gap-2">
                <Icon name="page" size="xs" />
                {file.name}
              </li>
            ))}
          </ul>
          {refusedCount > 0 && (
            <p className="text-sm text-muted-foreground">
              {t("desktop.ledger.documents.left_out", { count: refusedCount })}
            </p>
          )}
          <div className="flex flex-wrap items-center gap-2">
            <WriteHold>
              <Button
                size="sm"
                className="ledger-folder-add"
                aria-disabled={direction === null || busy !== null || undefined}
                aria-busy={busy === "adding" || undefined}
                onClick={() => void add()}
              >
                {busy === "adding" && <Spinner />}
                {t("desktop.ledger.documents.add_count", {
                  count: files.length,
                })}
              </Button>
            </WriteHold>
            {direction === null && (
              <span className="text-sm text-muted-foreground">
                {t("desktop.ledger.documents.say_direction")}
              </span>
            )}
            {busy === "adding" && (
              <span
                className="text-sm text-muted-foreground tabular-nums"
                role="status"
              >
                {t("desktop.ledger.documents.adding", {
                  done: progress,
                  total: files.length,
                })}
              </span>
            )}
          </div>
        </div>
      )}
      {applied && (
        <div className="grid gap-2">
          {applied.stopped && (
            <Alert
              tone={unseenCode(applied.stopped.code) ? "warning" : "danger"}
              role="alert"
              icon={
                <Icon
                  name={
                    unseenCode(applied.stopped.code) ? "unknown" : "refused"
                  }
                />
              }
            >
              <AlertTitle>
                {applied.stopped.code === "unknown"
                  ? t("desktop.ledger.documents.unknown")
                  : applied.stopped.code === "saved_unread"
                    ? t("desktop.ledger.apply.outcome.saved_unread")
                    : t("desktop.ledger.documents.not_done")}
              </AlertTitle>
              <AlertDescription>
                {listed(
                  t,
                  applied.stopped.files.map((file) => file.name),
                )}
              </AlertDescription>
            </Alert>
          )}
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
          <Table
            label={t("desktop.ledger.documents.batch_results")}
            columns={batchColumns}
            rows={batchRows(t, applied)}
            rowKey={(row) => row.key}
            renderRow={(row) => (
              <tr className="ledger-batch-item" data-status={row.status}>
                <td className={cell}>{row.name}</td>
                <td className={cell}>{row.outcome}</td>
              </tr>
            )}
          />
        </div>
      )}
    </div>
  );
}

// ---- What left this computer ------------------------------------------------------

/** Every document sent off this computer to be read, and what was made
 * from one. What was sent cannot be recalled. */
export function ConsentHistory({
  locale,
  read,
  records,
  onRetry,
}: {
  locale: string;
  read: Read<EvidenceConsentListResult>;
  records: EvidenceRecord[];
  onRetry(): void;
}) {
  const t = useStrings();
  if (read.phase === "failed")
    return <Failed t={t} read={read} onRetry={onRetry} />;
  if (!read.value) return <Reading t={t} />;
  const survey = read.value.survey;
  const dispatches = survey.consented_dispatches ?? [];
  const artefacts = survey.cloud_derived_artefacts ?? [];
  const named = (address: string) => {
    const found = records.find(
      (record) =>
        record.source_sha256 === address ||
        record.evidence_id === address ||
        record.attachment_id === address,
    );
    return found ? fileName(found.source_path) : address.slice(0, 12);
  };
  const when = t("desktop.ledger.documents.column.when");
  const documentName = t("desktop.ledger.documents.column.document");
  const dispatchColumns: ViewColumn<(typeof dispatches)[number]>[] = [
    {
      id: "when",
      label: when,
      name: when,
      sortValue: (dispatch) => dispatch.recorded_at,
    },
    {
      id: "document",
      label: documentName,
      name: documentName,
      sortValue: (dispatch) => named(dispatch.evidence_content_address),
    },
    {
      id: "provider",
      label: t("desktop.ledger.documents.column.provider"),
      name: t("desktop.ledger.documents.column.provider"),
      sortValue: (dispatch) => dispatch.provider,
    },
    {
      id: "model",
      label: t("desktop.ledger.documents.column.model"),
      name: t("desktop.ledger.documents.column.model"),
      sortValue: (dispatch) => dispatch.model,
    },
  ];
  const artefactColumns: ViewColumn<(typeof artefacts)[number]>[] = [
    {
      id: "when",
      label: when,
      name: when,
      sortValue: (artefact) => artefact.drafted_at,
    },
    {
      id: "document",
      label: documentName,
      name: documentName,
      sortValue: (artefact) => named(artefact.evidence_reference),
    },
    {
      id: "stamp",
      label: t("desktop.ledger.documents.column.stamp"),
      name: t("desktop.ledger.documents.column.stamp"),
      sortValue: (artefact) => artefact.provenance_stamp,
    },
  ];
  return (
    <div className="ledger-consent grid gap-4 p-3">
      <p className="text-sm text-muted-foreground">
        {t("desktop.ledger.documents.consent_note")}
      </p>
      {dispatches.length === 0 ? (
        <p className="ledger-consent-none text-sm">
          {t("desktop.ledger.documents.consent_none")}
        </p>
      ) : (
        <Table
          label={t("desktop.ledger.documents.tab.sent")}
          columns={dispatchColumns}
          rows={dispatches}
          rowKey={(dispatch) =>
            `${dispatch.recorded_at}:${dispatch.evidence_content_address}`
          }
          renderRow={(dispatch) => (
            <tr className="ledger-consent-dispatch">
              <td className={`${cell} tabular-nums`}>
                {formatTime(locale, dispatch.recorded_at)}
              </td>
              <td className={cell}>
                {named(dispatch.evidence_content_address)}
              </td>
              <td className={cell}>{dispatch.provider}</td>
              <td className={cell}>{dispatch.model}</td>
            </tr>
          )}
        />
      )}
      {artefacts.length > 0 && (
        <section className="grid gap-2">
          <h3 className="text-sm font-semibold">
            {t("desktop.ledger.documents.derived")}
          </h3>
          <Table
            label={t("desktop.ledger.documents.derived")}
            columns={artefactColumns}
            rows={artefacts}
            rowKey={(artefact) =>
              `${artefact.drafted_at}:${artefact.evidence_reference}`
            }
            renderRow={(artefact) => (
              <tr>
                <td className={`${cell} tabular-nums`}>
                  {formatTime(locale, artefact.drafted_at)}
                </td>
                <td className={cell}>{named(artefact.evidence_reference)}</td>
                <td className={`${cell} font-mono text-xs`}>
                  {artefact.provenance_stamp}
                </td>
              </tr>
            )}
          />
        </section>
      )}
    </div>
  );
}

// ---- What can read documents here ---------------------------------------------------

/** What can read documents on this computer, as the setup engine's local AI
 * row states it: whether its program is usable, and the way into its setup
 * while it is not. Which model reads, and whether it can, is the agent's to
 * say when a reading is refused. */
export function ReaderReadiness() {
  const t = useStrings();
  const row = useProvisioning().localAiRow;
  const usable = row !== null && rowTone(row) === "ready";
  const version = row?.version ?? null;
  const line = (ok: boolean, label: string, detail: string) => (
    <li className="flex items-start gap-2 border-b border-border py-2">
      <Icon
        name={ok ? "check" : "unplug"}
        size="sm"
        className={ok ? "text-success" : "text-warning"}
      />
      <span className="min-w-0 flex-1 font-medium">{label}</span>
      <span className="text-sm text-muted-foreground">{detail}</span>
    </li>
  );
  return (
    <div className="ledger-readers grid gap-3 p-3">
      {row !== null && !usable && (
        <SetupOffer
          action={row.recovery_action_id ?? setupActionOf(row.item)}
          className="ledger-readers-set-up justify-self-start"
        />
      )}
      <ul aria-label={t("desktop.ledger.documents.tab.readers")}>
        {line(
          usable,
          t("desktop.ledger.documents.reader.host"),
          !usable
            ? t("desktop.ledger.documents.reader.unavailable")
            : version
              ? t("desktop.ledger.documents.reader.version", { version })
              : t("desktop.ledger.documents.reader.available"),
        )}
        <li className="flex items-start gap-2 border-b border-border py-2">
          <Icon name="lock" size="sm" className="text-muted-foreground" />
          <span className="min-w-0 flex-1 font-medium">
            {t("desktop.ledger.documents.reader.off_host")}
          </span>
          <span className="text-sm text-muted-foreground">
            {t("desktop.ledger.documents.reader.off_host_note")}
          </span>
        </li>
      </ul>
    </div>
  );
}
