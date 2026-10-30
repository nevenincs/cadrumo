import { useEffect, useMemo, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Toast } from "@/components/ui/toast";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { facts } from "../../../shell/compose";
import type { LedgerPort, LedgerRow } from "../../../shell/ledger";
import type { StageEvent, StageState } from "../../../shell/ledgerStage";
import { useStrings } from "../../../shell/strings";
import { dayText } from "../transfer/transferWords";
import {
  AttachmentQueue,
  ConsentHistory,
  FolderIntake,
  ReaderReadiness,
} from "./DocumentPanels";
import { DraftReview } from "./DraftReview";
import { fileName, referenceOf } from "./documentsModel";
import { reasonLabel } from "./documentWords";
import { EvidenceRecords } from "./EvidenceRecords";
import { useLedgerRead } from "./useLedgerRead";

const TOAST_MS = 4000;
/** The viewer's share of the review's width, in percent, at first. */
const VIEWER_SHARE = 45;
export const DOCUMENT_TABS = [
  "review",
  "records",
  "attachments",
  "folder",
  "sent",
  "readers",
] as const;
export type DocumentTab = (typeof DOCUMENT_TABS)[number];

/**
 * The Documents section: the readings waiting for review, every evidence
 * record, the attachments waiting to be read, folder intake, what left this
 * computer to be read, and what can read documents here. A reading is a
 * proposal: it becomes an invoice only when the person confirms it.
 */
export function DocumentsSection({
  port,
  reader,
  locale,
  shown,
  rows,
  stage,
  onStage,
}: {
  port: LedgerPort;
  reader: string | null;
  locale: string;
  shown: boolean;
  /** The period's movements as read, for the links a confirmation offers
   * and the records attached to them. */
  rows: LedgerRow[] | null;
  stage: StageState;
  onStage(event: StageEvent): void;
}) {
  const t = useStrings();
  const [tab, setTab] = useState<DocumentTab>("review");
  const [current, setCurrent] = useState<string | null>(null);
  const [record, setRecord] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  // Readings confirmed here, kept in the list until another is chosen so
  // the confirmation and its link offer stay on screen.
  const [done, setDone] = useState<ReadonlySet<string>>(new Set());
  const queueList = useRef<HTMLUListElement>(null);
  // With a document open the list folds to a rail of its documents and
  // their open findings, so the page and what was read get the width.
  const [listOpen, setListOpen] = useState(false);
  // The viewer's share of the review's width, kept while documents change.
  const [viewerShare, setViewerShare] = useState(VIEWER_SHARE);
  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), TOAST_MS);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const queue = useLedgerRead(
    port,
    reader,
    shown,
    "ledger.evidence.review.list",
    {},
  );
  const pending = useMemo(
    () =>
      new Map(
        (queue.read.value?.rows ?? []).map((row) => [
          row.evidence_reference,
          row.drafted_at,
        ]),
      ),
    [queue.read.value],
  );
  const records = useLedgerRead(
    port,
    reader,
    shown,
    "ledger.evidence.list",
    {},
  );
  const invoices = useLedgerRead(
    port,
    reader,
    shown && tab === "review",
    "ledger.invoice.list",
    {},
  );
  const attachments = useLedgerRead(
    port,
    reader,
    shown && tab === "attachments",
    "ledger.evidence.attachment_queue",
    {},
  );
  const consent = useLedgerRead(
    port,
    reader,
    shown && tab === "sent",
    "ledger.evidence.consent.list",
    {},
  );
  const rereadAll = () => {
    queue.reread();
    records.reread();
    invoices.reread();
  };

  const waiting = useMemo(
    () => queue.read.value?.rows ?? [],
    [queue.read.value],
  );
  const recordList = useMemo(
    () => records.read.value?.rows ?? [],
    [records.read.value],
  );
  const inReview = useMemo(
    () =>
      new Set(
        waiting
          .map((row) => row.evidence_reference)
          .filter((reference) => !done.has(reference)),
      ),
    [waiting, done],
  );
  const choose = (reference: string) => {
    if (done.size) {
      setDone(new Set());
      queue.reread();
    }
    setCurrent(reference);
  };
  const selected =
    waiting.find((row) => row.evidence_reference === current) ??
    waiting[0] ??
    null;
  const nameOf = (reference: string) => {
    const found = recordList.find(
      (found) =>
        found.evidence_id === reference || found.attachment_id === reference,
    );
    if (found) return fileName(found.source_path);
    // A document with no name is told apart by its place in the queue.
    const place = waiting.findIndex(
      (row) => row.evidence_reference === reference,
    );
    return t("desktop.ledger.documents.attachment_named", {
      n: place >= 0 ? place + 1 : waiting.length + 1,
    });
  };
  /** Moves the focus on to the next document still to review after the
   * one shown, wrapping round; with none left, to the one shown. */
  const focusNext = () => {
    const items = [
      ...(queueList.current?.querySelectorAll<HTMLElement>(
        ".ledger-review-item",
      ) ?? []),
    ];
    const at = items.findIndex(
      (item) => item.dataset.reference === selected?.evidence_reference,
    );
    const after = [...items.slice(at + 1), ...items.slice(0, Math.max(at, 0))];
    const next =
      after.find((item) => !done.has(item.dataset.reference ?? "")) ??
      items[at] ??
      null;
    next?.focus();
  };
  const openReview = (reference: string) => {
    rereadAll();
    setDone(new Set());
    setCurrent(reference);
    setTab("review");
  };

  let review;
  if (queue.read.phase === "failed" || records.read.phase === "failed") {
    review = (
      <EmptyState
        className="ledger-documents-failed"
        icon="alert"
        description={
          <span role="alert">{t("desktop.ledger.documents.read_failed")}</span>
        }
      >
        <Button variant="outline" onClick={rereadAll}>
          {t("desktop.ledger.retry")}
        </Button>
      </EmptyState>
    );
  } else if (!queue.read.value || !records.read.value)
    review = (
      <EmptyState
        className="ledger-documents-loading"
        role="status"
        busy
        description={t("desktop.ledger.loading")}
      />
    );
  else if (waiting.length === 0)
    review = (
      <EmptyState
        className="ledger-review-empty"
        icon="check"
        description={t("desktop.ledger.documents.nothing_to_review")}
      >
        <Button variant="outline" onClick={() => setTab("folder")}>
          <Icon name="upload" />
          {t("desktop.ledger.documents.add_documents")}
        </Button>
      </EmptyState>
    );
  else
    review = (
      <div className="flex min-h-0 flex-1">
        <div
          className={`ledger-review-list flex min-h-0 shrink-0 flex-col border-r border-border ${
            listOpen ? "w-1/3" : "w-rail"
          }`}
          data-open={listOpen || undefined}
        >
          <div
            className={`flex border-b border-border p-1 ${listOpen ? "justify-end" : "justify-center"}`}
          >
            <IconButton
              className="ledger-review-list-toggle"
              label={
                listOpen
                  ? t("desktop.ledger.documents.list_hide")
                  : t("desktop.ledger.documents.list_show")
              }
              aria-expanded={listOpen}
              onClick={() => setListOpen(!listOpen)}
            >
              <Icon name={listOpen ? "back" : "forward"} size="sm" />
            </IconButton>
          </div>
          <ul
            ref={queueList}
            className="ledger-review-queue min-h-0 flex-1 overflow-y-auto"
            aria-label={t("desktop.ledger.documents.queue")}
          >
            {waiting.map((row) => {
              const name = nameOf(row.evidence_reference);
              const confirmedHere = done.has(row.evidence_reference);
              const state = confirmedHere ? (
                <span className="inline-flex items-center gap-1">
                  <Icon name="check" size="xs" className="text-success" />
                  {listOpen && t("desktop.ledger.documents.confirmed_short")}
                </span>
              ) : row.blocking_count > 0 ? (
                <Badge
                  variant="warning"
                  aria-label={t("desktop.ledger.documents.findings_open", {
                    count: row.blocking_count,
                  })}
                  title={facts(
                    t,
                    (row.reasons ?? []).map((reason) => reasonLabel(t, reason)),
                  )}
                >
                  <Icon name="alert" size="xs" />
                  {row.blocking_count}
                </Badge>
              ) : listOpen ? (
                <span>{t("desktop.ledger.documents.ready_to_confirm")}</span>
              ) : (
                <span className="sr-only">
                  {t("desktop.ledger.documents.ready_to_confirm")}
                </span>
              );
              const item = (
                <button
                  type="button"
                  className={`ledger-review-item grid w-full cursor-pointer gap-0.5 border-b border-border text-left hover-wash aria-[current=true]:bg-selected ${
                    listOpen ? "px-3 py-2" : "justify-items-center px-1 py-2"
                  }`}
                  aria-current={
                    row.evidence_reference === selected?.evidence_reference ||
                    undefined
                  }
                  data-reference={row.evidence_reference}
                  onClick={() => choose(row.evidence_reference)}
                >
                  {listOpen ? (
                    <>
                      <span className="truncate font-medium">{name}</span>
                      <span className="flex flex-wrap items-center gap-1 text-sm text-muted-foreground">
                        {state}
                        <span className="ml-auto tabular-nums">
                          {dayText(locale, row.drafted_at.slice(0, 10))}
                        </span>
                      </span>
                    </>
                  ) : (
                    <>
                      <Icon name="page" size="sm" />
                      <span className="sr-only">{name}</span>
                      {state}
                    </>
                  )}
                </button>
              );
              return (
                <li key={row.evidence_reference}>
                  {listOpen ? (
                    item
                  ) : (
                    <Tooltip>
                      <TooltipTrigger asChild>{item}</TooltipTrigger>
                      <TooltipContent side="right">{name}</TooltipContent>
                    </Tooltip>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
        <div className="flex min-h-0 min-w-0 flex-1">
          {selected && (
            <DraftReview
              key={selected.evidence_reference}
              port={port}
              reader={reader}
              locale={locale}
              evidenceReference={selected.evidence_reference}
              reference={referenceOf(selected.evidence_reference, recordList)}
              record={
                recordList.find(
                  (found) => found.evidence_id === selected.evidence_reference,
                ) ?? null
              }
              fileName={nameOf(selected.evidence_reference)}
              invoices={invoices.read.value?.invoices ?? null}
              rows={rows}
              stage={stage}
              onStage={onStage}
              onWritten={() => {
                records.reread();
                invoices.reread();
              }}
              onConfirmed={(reference) =>
                setDone((held) => new Set([...held, reference]))
              }
              onLinkStaged={focusNext}
              viewerShare={viewerShare}
              onViewerShare={setViewerShare}
              say={setToast}
            />
          )}
        </div>
      </div>
    );

  return (
    <Tabs
      value={tab}
      onValueChange={(value) => setTab(value as DocumentTab)}
      className="ledger-documents flex min-h-0 flex-1 flex-col"
    >
      <TabsList
        aria-label={t("desktop.ledger.documents.tabs")}
        className="ledger-documents-tabs overflow-x-auto border-b border-border px-2"
      >
        {DOCUMENT_TABS.map((value) => (
          <TabsTrigger key={value} value={value} className="text-sm">
            {t(`desktop.ledger.documents.tab.${value}`)}
            {value === "review" && inReview.size > 0 && (
              <Badge
                className="tabular-nums"
                aria-label={t("desktop.ledger.documents.to_review", {
                  count: inReview.size,
                })}
              >
                {inReview.size}
              </Badge>
            )}
          </TabsTrigger>
        ))}
      </TabsList>
      <TabsContent value="review" className="flex min-h-0 flex-col">
        {review}
      </TabsContent>
      <TabsContent value="records" className="flex min-h-0 flex-col">
        {records.read.value ? (
          <EvidenceRecords
            port={port}
            locale={locale}
            records={recordList}
            rows={rows}
            inReview={inReview}
            pending={pending}
            selected={record}
            onSelect={setRecord}
            onWritten={rereadAll}
            onReview={openReview}
            say={setToast}
          />
        ) : (
          review
        )}
      </TabsContent>
      <TabsContent value="attachments" className="overflow-y-auto">
        <AttachmentQueue
          port={port}
          locale={locale}
          read={attachments.read}
          pending={pending}
          onRetry={attachments.reread}
          onReview={openReview}
        />
      </TabsContent>
      <TabsContent value="folder" className="overflow-y-auto">
        <FolderIntake port={port} onWritten={rereadAll} />
      </TabsContent>
      <TabsContent value="sent" className="overflow-y-auto">
        <ConsentHistory
          locale={locale}
          read={consent.read}
          records={recordList}
          onRetry={consent.reread}
        />
      </TabsContent>
      <TabsContent value="readers" className="overflow-y-auto">
        <ReaderReadiness />
      </TabsContent>
      <Toast className="ledger-documents-toast">{toast}</Toast>
    </Tabs>
  );
}
