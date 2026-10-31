import { useId, useRef, useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { facts } from "../../../shell/compose";
import {
  EVIDENCE_UPDATE_FIELDS,
  type EvidenceRecord,
  type EvidenceUpdateField,
  type EvidenceUpdateRequest,
  type LedgerPort,
  type LedgerRow,
} from "../../../shell/ledger";
import { readAnswer } from "../../../shell/ledgerWindow";
import { useStrings } from "../../../shell/strings";
import { localDay } from "../../../shared/dates";
import { formatDay } from "../../../shared/dateFormats";
import { formatAmount } from "../../../shared/numbers";
import { write } from "../invoices/invoiceWrites";
import {
  landingSettle,
  useWritePause,
  WriteHold,
  type LandingCheck,
} from "../WritePause";
import { extractionLanding, recordLanding } from "./documentLanding";
import {
  EVIDENCE_SHAPES,
  fieldWidth,
  fileName,
  holdsUpdate,
  recordUpdate,
  recordValue,
} from "./documentsModel";

type Notice =
  | { kind: "saved" }
  | { kind: "refused"; code: string }
  | { kind: "unknown"; asked: "update" | "remove" | "read" }
  | { kind: "checked"; saved: boolean };

/** One record's detail: its correction, its removal, and a reading of it. */
function RecordDetail({
  port,
  locale,
  record,
  attachedTo,
  inReview,
  drafted,
  onWritten,
  onRemoved,
  onReview,
  say,
}: {
  port: LedgerPort;
  locale: string;
  record: EvidenceRecord;
  attachedTo: LedgerRow | null;
  inReview: boolean;
  /** When this record's reading waiting for review was drafted, if one
   * waits. */
  drafted: string | null;
  onWritten(): void;
  onRemoved(): void;
  onReview(reference: string): void;
  say(text: string): void;
}) {
  const t = useStrings();
  const base = useId();
  const [typed, setTyped] = useState<
    Partial<Record<EvidenceUpdateField, string>>
  >({});
  const [busy, setBusy] = useState<"saving" | "removing" | "reading" | null>(
    null,
  );
  const [removing, setRemoving] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [asked, setAsked] = useState<EvidenceUpdateRequest | null>(null);
  const planned = recordUpdate(record, typed);
  const pause = useWritePause();
  const name = fileName(record.source_path);
  const undetermined = (saved: boolean, check: LandingCheck) =>
    pause.hold({
      what: name,
      outcome: saved ? "saved_unread" : "unknown",
      settle: landingSettle(t, name, check),
    });
  const refused = new Set(planned.kind === "refused" ? planned.fields : []);
  const shown = (field: EvidenceUpdateField) =>
    typed[field] ?? recordValue(record, field) ?? "";

  async function save() {
    if (planned.kind !== "update") return;
    setBusy("saving");
    setNotice(null);
    const sent = await write(port, "ledger.evidence.update", planned.request);
    setBusy(null);
    if (sent.kind === "done") {
      setTyped({});
      setNotice({ kind: "saved" });
      say(t("desktop.ledger.documents.record_saved"));
      onWritten();
    } else if (sent.kind === "unknown") {
      setAsked(planned.request);
      setNotice({ kind: "unknown", asked: "update" });
      undetermined(
        sent.saved,
        recordLanding(port, record.evidence_id, planned.request),
      );
    } else
      setNotice({
        kind: "refused",
        code: sent.kind === "refused" ? (sent.reason ?? "refused") : sent.code,
      });
  }
  async function remove() {
    setBusy("removing");
    setNotice(null);
    const sent = await write(port, "ledger.evidence.remove", {
      evidence_id: record.evidence_id,
    });
    setBusy(null);
    setRemoving(false);
    if (sent.kind === "done") {
      say(t("desktop.ledger.documents.record_removed"));
      onRemoved();
    } else if (sent.kind === "unknown") {
      setNotice({ kind: "unknown", asked: "remove" });
      undetermined(sent.saved, recordLanding(port, record.evidence_id, null));
    } else
      setNotice({
        kind: "refused",
        code: sent.kind === "refused" ? (sent.reason ?? "refused") : sent.code,
      });
  }
  async function readIt() {
    setBusy("reading");
    setNotice(null);
    const sent = await write(port, "ledger.evidence.extract", {
      evidence_id: record.evidence_id,
    });
    setBusy(null);
    if (sent.kind === "done") onReview(record.evidence_id);
    else if (sent.kind === "unknown") {
      setNotice({ kind: "unknown", asked: "read" });
      undetermined(
        sent.saved,
        extractionLanding(port, record.evidence_id, drafted),
      );
    } else
      setNotice({
        kind: "refused",
        code: sent.kind === "refused" ? (sent.reason ?? "refused") : sent.code,
      });
  }
  /** Learns what an unseen outcome came to by reading the record back. */
  async function check() {
    if (notice?.kind !== "unknown") return;
    try {
      const answer = readAnswer(
        await port.submit("ledger.evidence.view", {
          evidence_id: record.evidence_id,
        }),
      );
      if (answer.kind !== "answer") return;
      const outcome = answer.result.outcome;
      if (notice.asked === "remove")
        setNotice({ kind: "checked", saved: outcome.kind === "refused" });
      else if (notice.asked === "update" && asked && outcome.kind === "success")
        setNotice({
          kind: "checked",
          saved: holdsUpdate(outcome.record, asked),
        });
      onWritten();
    } catch {
      // The outcome stays unknown.
    }
  }

  return (
    <div className="ledger-record grid gap-3 p-3">
      <div className="flex flex-wrap items-start gap-2">
        <div className="grid min-w-0 flex-1 gap-0.5">
          <h3 className="text-md font-semibold [overflow-wrap:anywhere]">
            {fileName(record.source_path)}
          </h3>
          <span className="text-sm text-muted-foreground">
            {t("desktop.ledger.documents.added_on", {
              kind: t(`desktop.ledger.documents.media.${record.media_kind}`),
              date: formatDay(locale, localDay(new Date(record.created_at))),
            })}
          </span>
        </div>
        {inReview ? (
          <Button
            size="sm"
            variant="outline"
            onClick={() => onReview(record.evidence_id)}
          >
            {t("desktop.ledger.documents.open_review")}
          </Button>
        ) : (
          <WriteHold>
            <Button
              size="sm"
              variant="outline"
              className="ledger-record-read"
              disabled={busy !== null}
              aria-busy={busy === "reading" || undefined}
              onClick={() => void readIt()}
            >
              {busy === "reading" ? <Spinner /> : <Icon name="sync" />}
              {t("desktop.ledger.documents.read_here")}
            </Button>
          </WriteHold>
        )}
      </div>
      <p className="text-sm">
        {attachedTo
          ? t("desktop.ledger.documents.attached_to", {
              description: attachedTo.transaction.description,
              amount: formatAmount(locale, attachedTo.transaction.amount),
            })
          : t("desktop.ledger.documents.not_attached")}
      </p>
      {notice?.kind === "refused" && (
        <Alert tone="danger" role="alert" icon={<Icon name="refused" />}>
          <AlertTitle>{t("desktop.ledger.documents.not_done")}</AlertTitle>
        </Alert>
      )}
      {notice?.kind === "unknown" && (
        <Alert tone="warning" role="alert" icon={<Icon name="unknown" />}>
          <AlertTitle>{t("desktop.ledger.documents.unknown")}</AlertTitle>
          <AlertDescription className="flex flex-wrap items-center gap-2">
            {t("desktop.ledger.documents.unknown_note")}
            {notice.asked !== "read" && (
              <Button
                size="xs"
                variant="outline"
                onClick={() => {
                  void check();
                  if (!pause.rereading) pause.reread();
                }}
              >
                {t("desktop.ledger.documents.check")}
              </Button>
            )}
          </AlertDescription>
        </Alert>
      )}
      {notice?.kind === "checked" && (
        <Alert icon={<Icon name="info" />}>
          {notice.saved
            ? t("desktop.ledger.documents.checked_saved")
            : t("desktop.ledger.documents.checked_not_saved")}
        </Alert>
      )}
      <div className="grid grid-cols-2 gap-3">
        {EVIDENCE_UPDATE_FIELDS.filter((field) => field !== "notes").map(
          (field) => (
            <Field key={field} data-invalid={refused.has(field) || undefined}>
              <FieldLabel htmlFor={`${base}-${field}`}>
                {t(`desktop.ledger.documents.record.${field}`)}
              </FieldLabel>
              <Input
                id={`${base}-${field}`}
                controlSize="sm"
                className={`ledger-record-input tabular-nums ${fieldWidth(
                  EVIDENCE_SHAPES[field],
                  field === "supplier",
                )}`}
                maxLength={1024}
                aria-invalid={refused.has(field) || undefined}
                value={shown(field)}
                onChange={(event) =>
                  setTyped((held) => ({ ...held, [field]: event.target.value }))
                }
              />
              {refused.has(field) && (
                <FieldError>
                  {t("desktop.ledger.documents.record_refused")}
                </FieldError>
              )}
            </Field>
          ),
        )}
        <Field className="col-span-2">
          <FieldLabel htmlFor={`${base}-notes`}>
            {t("desktop.ledger.documents.record.notes")}
          </FieldLabel>
          <Input
            id={`${base}-notes`}
            controlSize="sm"
            maxLength={16384}
            value={shown("notes")}
            onChange={(event) =>
              setTyped((held) => ({ ...held, notes: event.target.value }))
            }
          />
        </Field>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <WriteHold>
          <Button
            size="sm"
            className="ledger-record-save"
            disabled={planned.kind !== "update" || busy !== null}
            aria-busy={busy === "saving" || undefined}
            onClick={() => void save()}
          >
            {busy === "saving" && <Spinner />}
            {t("desktop.ledger.documents.save")}
          </Button>
        </WriteHold>
        <Button
          size="sm"
          variant="ghost"
          className="ledger-record-remove"
          aria-disabled={attachedTo !== null || busy !== null || undefined}
          aria-describedby={attachedTo ? `${base}-why` : undefined}
          onClick={() => {
            if (attachedTo === null && busy === null) setRemoving(true);
          }}
        >
          <Icon name="trash" />
          {t("desktop.ledger.documents.remove")}
        </Button>
        {attachedTo && (
          <span id={`${base}-why`} className="text-sm text-muted-foreground">
            {t("desktop.ledger.documents.remove_attached")}
          </span>
        )}
      </div>
      {removing && (
        <Alert
          tone="warning"
          role="alert"
          icon={<Icon name="alert" />}
          className="ledger-record-removing"
        >
          <AlertTitle>{t("desktop.ledger.documents.remove_title")}</AlertTitle>
          <AlertDescription className="grid gap-2">
            {t("desktop.ledger.documents.remove_note")}
            <span className="flex gap-2">
              <WriteHold>
                <Button
                  size="xs"
                  variant="destructive"
                  className="ledger-record-remove-confirm"
                  disabled={busy !== null}
                  onClick={() => void remove()}
                >
                  {t("desktop.ledger.documents.remove")}
                </Button>
              </WriteHold>
              <Button
                size="xs"
                variant="ghost"
                onClick={() => setRemoving(false)}
              >
                {t("desktop.ledger.documents.keep")}
              </Button>
            </span>
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}

/**
 * Every evidence record: added, corrected, read and removed one at a
 * time. Files are shown by name only.
 */
export function EvidenceRecords({
  port,
  locale,
  records,
  rows,
  inReview,
  pending,
  selected,
  onSelect,
  onWritten,
  onReview,
  say,
}: {
  port: LedgerPort;
  locale: string;
  records: EvidenceRecord[];
  rows: LedgerRow[] | null;
  inReview: ReadonlySet<string>;
  /** When each reading waiting for review was drafted, by reference. */
  pending: ReadonlyMap<string, string>;
  selected: string | null;
  onSelect(id: string | null): void;
  onWritten(): void;
  onReview(reference: string): void;
  say(text: string): void;
}) {
  const t = useStrings();
  const pause = useWritePause();
  const [adding, setAdding] = useState(false);
  const [addFailed, setAddFailed] = useState<string | null>(null);
  // The key of an add not seen to settle, by its file's name. Adding a file
  // of that name again sends the same key, and the product resolves a
  // repeated key to the record it already made, or refuses it when the
  // content differs: so the add is repeatable and never doubles a record.
  const unsettledKeys = useRef(new Map<string, string>());
  const record =
    records.find((found) => found.evidence_id === selected) ?? null;

  async function add() {
    setAdding(true);
    setAddFailed(null);
    try {
      const picks = await port.pickFiles(
        "documents",
        "file",
        t("desktop.ledger.import.filter.documents"),
      );
      const file = picks.files[0];
      if (!file) return;
      const key = unsettledKeys.current.get(file.name) ?? crypto.randomUUID();
      const sent = await write(port, "ledger.evidence.add", {
        source_path: file.token,
        idempotency_key: key,
      });
      if (sent.kind === "unknown") {
        unsettledKeys.current.set(file.name, key);
        pause.hold({
          what: file.name,
          outcome: sent.saved ? "saved_unread" : "unknown",
          // Repeatable by the key kept above; the list answering says the
          // ledger can be read again.
          settle: landingSettle(t, file.name, async () => {
            const read = await port
              .submit("ledger.evidence.list", {})
              .catch(() => null);
            return read?.kind === "settled" ? "repeatable" : null;
          }),
        });
      } else unsettledKeys.current.delete(file.name);
      await port.forgetFiles([file.token]).catch(() => undefined);
      if (sent.kind === "done") {
        say(t("desktop.ledger.documents.record_added"));
        onWritten();
        onSelect(sent.result.record.evidence_id);
      } else
        setAddFailed(
          sent.kind === "unknown"
            ? "unknown"
            : sent.kind === "refused"
              ? (sent.reason ?? "refused")
              : sent.code,
        );
    } catch {
      setAddFailed("unavailable");
    } finally {
      setAdding(false);
    }
  }

  return (
    <div className="ledger-records flex min-h-0 flex-1">
      <div className="flex min-h-0 w-1/3 shrink-0 flex-col border-r border-border">
        <div className="flex items-center gap-2 p-2">
          <WriteHold>
            <Button
              size="sm"
              variant="outline"
              className="ledger-record-add"
              disabled={adding}
              aria-busy={adding || undefined}
              onClick={() => void add()}
            >
              {adding ? <Spinner /> : <Icon name="plus" />}
              {t("desktop.ledger.documents.add_one")}
            </Button>
          </WriteHold>
        </div>
        {addFailed && (
          <Alert tone="danger" role="alert" icon={<Icon name="refused" />}>
            {addFailed === "unknown"
              ? t("desktop.ledger.documents.unknown")
              : t("desktop.ledger.documents.not_done")}
          </Alert>
        )}
        {records.length === 0 ? (
          <p className="px-3 py-2 text-sm text-muted-foreground">
            {t("desktop.ledger.documents.no_records")}
          </p>
        ) : (
          <ul
            className="ledger-record-list min-h-0 flex-1 overflow-y-auto"
            aria-label={t("desktop.ledger.documents.records")}
          >
            {records.map((found) => (
              <li key={found.evidence_id}>
                <button
                  type="button"
                  className="ledger-record-item grid w-full cursor-pointer gap-0.5 border-b border-border px-3 py-2 text-left hover-wash aria-[current=true]:bg-selected"
                  aria-current={found.evidence_id === selected || undefined}
                  onClick={() => onSelect(found.evidence_id)}
                >
                  <span className="flex min-w-0 items-center gap-2">
                    <Icon
                      name={found.media_kind === "image" ? "image" : "page"}
                      size="xs"
                    />
                    <span className="min-w-0 flex-1 truncate font-medium">
                      {fileName(found.source_path)}
                    </span>
                    {inReview.has(found.evidence_id) && (
                      <Badge variant="warning">
                        {t("desktop.ledger.documents.in_review")}
                      </Badge>
                    )}
                  </span>
                  <span className="truncate text-sm text-muted-foreground">
                    {facts(t, [
                      found.supplier,
                      found.invoice_number,
                      found.invoice_date,
                    ]) || t("desktop.ledger.documents.nothing_stated")}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="min-h-0 min-w-0 flex-1 overflow-y-auto">
        {record ? (
          <RecordDetail
            key={record.evidence_id}
            port={port}
            locale={locale}
            record={record}
            attachedTo={
              rows?.find(
                (row) =>
                  row.transaction.purchase_invoice_evidence_id ===
                  record.evidence_id,
              ) ?? null
            }
            inReview={inReview.has(record.evidence_id)}
            drafted={pending.get(record.evidence_id) ?? null}
            onWritten={onWritten}
            onRemoved={() => {
              onSelect(null);
              onWritten();
            }}
            onReview={onReview}
            say={say}
          />
        ) : (
          <EmptyState
            className="ledger-record-none"
            icon="page"
            description={t("desktop.ledger.documents.choose_record")}
          />
        )}
      </div>
    </div>
  );
}
