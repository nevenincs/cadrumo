import { useId, useState, type ReactNode } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty";
import { FieldLabel } from "@/components/ui/field";
import { Icon, type IconName } from "@/components/ui/icon";
import {
  SegmentedControl,
  SegmentedControlItem,
} from "@/components/ui/segmented-control";
import { Spinner } from "@/components/ui/spinner";
import type {
  AttachmentReviewItem,
  EvidenceConsentListResult,
  EvidenceRecord,
  FilePick,
  InvoiceKind,
  LedgerPort,
  PickedFile,
  ReaderReadinessResult,
} from "../../../shell/ledger";
import { useStrings, type Translate } from "../../../shell/strings";
import { kindChoice } from "../invoices/invoiceWords";
import { failureCode } from "../ledgerWords";
import { stampText } from "../movements/movementWords";
import { applyDocuments, type DocumentsApplied } from "../transfer/importModel";
import { sizeText } from "../transfer/transferWords";
import { write } from "../invoices/invoiceWrites";
import { useWritePause, WriteHold } from "../WritePause";
import { batchStatusLabel, sourceLabel } from "./documentWords";
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
        <span role="alert">
          {t("desktop.ledger.documents.read_failed")}{" "}
          <code className="font-mono text-xs">{failureCode(read.failure)}</code>
        </span>
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

/** A table with its column names, for a panel's rows. */
function Table({
  label,
  columns,
  children,
}: {
  label: string;
  columns: string[];
  children: ReactNode;
}) {
  return (
    <table aria-label={label} className="w-full text-sm">
      <thead>
        <tr className="border-b border-border text-left text-muted-foreground">
          {columns.map((column) => (
            <th key={column} scope="col" className="px-2 py-1 font-medium">
              {column}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>{children}</tbody>
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
  onRetry,
  onReview,
}: {
  port: LedgerPort;
  locale: string;
  read: Read<{ rows?: AttachmentReviewItem[] }>;
  onRetry(): void;
  onReview(reference: string): void;
}) {
  const t = useStrings();
  const pause = useWritePause();
  const [reading, setReading] = useState<string | null>(null);
  const [failed, setFailed] = useState<{ id: string; code: string } | null>(
    null,
  );
  if (read.phase === "failed")
    return <Failed t={t} read={read} onRetry={onRetry} />;
  if (!read.value) return <Reading t={t} />;
  const rows = read.value.rows ?? [];
  async function readIt(item: AttachmentReviewItem) {
    setReading(item.attachment_id);
    setFailed(null);
    const sent = await write(port, "ledger.evidence.extract", {
      attachment_id: item.attachment_id,
    });
    setReading(null);
    if (sent.kind === "unknown")
      pause.hold({
        what: t("desktop.ledger.section.documents"),
        outcome: sent.saved ? "saved_unread" : "unknown",
      });
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
  return (
    <div className="ledger-attachments p-3">
      <Table
        label={t("desktop.ledger.documents.tab.attachments")}
        columns={[
          t("desktop.ledger.documents.column.source"),
          t("desktop.ledger.documents.column.kind"),
          t("desktop.ledger.documents.column.size"),
          t("desktop.ledger.documents.column.captured"),
          t("desktop.ledger.documents.column.state"),
          t("desktop.ledger.documents.column.action"),
        ]}
      >
        {rows.map((item) => (
          <tr key={item.attachment_id} className="ledger-attachment">
            <td className={cell}>{sourceLabel(t, item.source)}</td>
            <td className={cell}>{item.mime_type}</td>
            <td className={`${cell} tabular-nums`}>
              {sizeText(locale, item.bytes_size)}
            </td>
            <td className={`${cell} tabular-nums`}>
              {stampText(locale, item.captured_at)}
            </td>
            <td className={cell}>
              {item.pending_review
                ? t("desktop.ledger.documents.attachment_waiting")
                : t("desktop.ledger.documents.attachment_linked", {
                    count: item.linked_invoice_ids.length,
                  })}
              {failed?.id === item.attachment_id && (
                <span role="alert" className="block text-destructive">
                  <code className="font-mono text-xs">{failed.code}</code>
                </span>
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
        ))}
      </Table>
    </div>
  );
}

// ---- Folder intake ---------------------------------------------------------------

const BATCH_ICONS: Record<string, IconName> = {
  ingested: "check",
  no_op: "tick",
  refused: "refused",
  pending_review: "pending",
  paused: "pause",
};

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
    if (done.stopped?.code === "unknown")
      pause.hold({
        what: done.stopped.files.map((file) => file.name).join(", "),
        outcome: "unknown",
      });
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
              tone={applied.stopped.code === "unknown" ? "warning" : "danger"}
              role="alert"
              icon={
                <Icon
                  name={
                    applied.stopped.code === "unknown" ? "unknown" : "refused"
                  }
                />
              }
            >
              <AlertTitle>
                {applied.stopped.code === "unknown"
                  ? t("desktop.ledger.documents.unknown")
                  : t("desktop.ledger.documents.not_done")}
              </AlertTitle>
              <AlertDescription>
                {applied.stopped.files.map((file) => file.name).join(" · ")}
              </AlertDescription>
            </Alert>
          )}
          <Table
            label={t("desktop.ledger.documents.batch_results")}
            columns={[
              t("desktop.ledger.documents.column.document"),
              t("desktop.ledger.documents.column.outcome"),
            ]}
          >
            {applied.items.map((item) => (
              <tr
                key={item.identity}
                className="ledger-batch-item"
                data-status={item.status}
              >
                <td className={cell}>{item.source_name}</td>
                <td className={cell}>
                  <span className="inline-flex items-center gap-1">
                    <Icon name={BATCH_ICONS[item.status] ?? "info"} size="xs" />
                    {batchStatusLabel(t, item.status)}
                    {item.refusal_code && (
                      <code className="font-mono text-xs">
                        {item.refusal_code}
                      </code>
                    )}
                  </span>
                </td>
              </tr>
            ))}
            {applied.unresolved.map((item) => (
              <tr
                key={`${item.source_name}:${item.refusal_code}`}
                className="ledger-batch-item"
                data-status="refused"
              >
                <td className={cell}>{item.source_name}</td>
                <td className={cell}>
                  <span className="inline-flex items-center gap-1">
                    <Icon name="refused" size="xs" />
                    {batchStatusLabel(t, "refused")}
                    <code className="font-mono text-xs">
                      {item.refusal_code}
                    </code>
                  </span>
                </td>
              </tr>
            ))}
            {applied.notSent.map((file) => (
              <tr
                key={file.token}
                className="ledger-batch-item"
                data-status="not_sent"
              >
                <td className={cell}>{file.name}</td>
                <td className={cell}>
                  {t("desktop.ledger.documents.not_sent")}
                </td>
              </tr>
            ))}
          </Table>
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
          columns={[
            t("desktop.ledger.documents.column.when"),
            t("desktop.ledger.documents.column.document"),
            t("desktop.ledger.documents.column.provider"),
            t("desktop.ledger.documents.column.model"),
          ]}
        >
          {dispatches.map((dispatch) => (
            <tr
              key={`${dispatch.recorded_at}:${dispatch.evidence_content_address}`}
              className="ledger-consent-dispatch"
            >
              <td className={`${cell} tabular-nums`}>
                {stampText(locale, dispatch.recorded_at)}
              </td>
              <td className={cell}>
                {named(dispatch.evidence_content_address)}
              </td>
              <td className={cell}>{dispatch.provider}</td>
              <td className={cell}>{dispatch.model}</td>
            </tr>
          ))}
        </Table>
      )}
      {artefacts.length > 0 && (
        <section className="grid gap-2">
          <h3 className="text-sm font-semibold">
            {t("desktop.ledger.documents.derived")}
          </h3>
          <Table
            label={t("desktop.ledger.documents.derived")}
            columns={[
              t("desktop.ledger.documents.column.when"),
              t("desktop.ledger.documents.column.document"),
              t("desktop.ledger.documents.column.stamp"),
            ]}
          >
            {artefacts.map((artefact) => (
              <tr key={`${artefact.drafted_at}:${artefact.evidence_reference}`}>
                <td className={`${cell} tabular-nums`}>
                  {stampText(locale, artefact.drafted_at)}
                </td>
                <td className={cell}>{named(artefact.evidence_reference)}</td>
                <td className={`${cell} font-mono text-xs`}>
                  {artefact.provenance_stamp}
                </td>
              </tr>
            ))}
          </Table>
        </section>
      )}
    </div>
  );
}

// ---- What can read documents here ---------------------------------------------------

/** What can read documents on this computer, role by role. */
export function ReaderReadiness({
  read,
  onRetry,
}: {
  read: Read<ReaderReadinessResult>;
  onRetry(): void;
}) {
  const t = useStrings();
  if (read.phase === "failed")
    return <Failed t={t} read={read} onRetry={onRetry} />;
  if (!read.value) return <Reading t={t} />;
  const ready = read.value;
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
      <ul aria-label={t("desktop.ledger.documents.tab.readers")}>
        {line(
          ready.extraction_ready,
          t("desktop.ledger.documents.reader.extraction"),
          ready.document_readiness === "all_documents"
            ? t("desktop.ledger.documents.reader.all_documents")
            : t("desktop.ledger.documents.reader.text_only"),
        )}
        {line(
          ready.host.available,
          t("desktop.ledger.documents.reader.host"),
          ready.host.available
            ? ready.host.version_withheld || !ready.host.version
              ? t("desktop.ledger.documents.reader.available")
              : t("desktop.ledger.documents.reader.version", {
                  version: ready.host.version,
                })
            : t("desktop.ledger.documents.reader.unavailable"),
        )}
        {ready.roles.map((role) => (
          <li
            key={role.role}
            className="ledger-reader-role flex items-start gap-2 border-b border-border py-2"
          >
            <Icon
              name={role.ready ? "check" : "unplug"}
              size="sm"
              className={role.ready ? "text-success" : "text-warning"}
            />
            <span className="grid min-w-0 flex-1">
              <span className="font-medium">{role.role}</span>
              {role.model && (
                <span className="text-sm text-muted-foreground">
                  {role.model}
                </span>
              )}
            </span>
            <span className="flex flex-wrap items-center gap-1 text-sm text-muted-foreground">
              {role.ready
                ? t("desktop.ledger.documents.reader.ready")
                : t("desktop.ledger.documents.reader.not_ready")}
              {role.contention_causes?.map((cause) => (
                <Badge key={cause}>{cause}</Badge>
              ))}
            </span>
          </li>
        ))}
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
