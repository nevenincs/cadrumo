// The document a reading came from, shown beside what was read from it, so
// the person can check a value against the page before confirming it. The
// runtime draws each page as an image; this view never parses the document.
// The image is held in this component's memory only, and goes when the
// panel closes or another document is shown.

import { useEffect, useRef, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { Spinner } from "@/components/ui/spinner";
import type { EvidencePageResult, LedgerPort } from "../../../shell/ledger";
import type { LedgerReadFailure } from "../../../shell/ledgerWindow";
import { useStrings, type Translate } from "../../../shell/strings";
import { failureCode } from "../ledgerWords";
import { referenceFields, type DocumentReference } from "./documentsModel";
import { useLedgerRead } from "./useLedgerRead";

/** Zoom steps, as multiples of the frame's width. */
const ZOOMS = [1, 1.5, 2, 3] as const;
/** Requested widths come in steps, so a resize reads again only when the
 * step changes. */
const WIDTH_STEP = 320;
const MIN_WIDTH = 64;
const MAX_WIDTH = 4096;

/** The page read's refusals, as their registered codes end. */
const REFUSALS = [
  "not_found",
  "digest_mismatch",
  "unsupported_media",
  "too_large",
  "out_of_range",
  "unreadable",
] as const;
const REFUSAL_PREFIX = "REFUSED_LEDGER_EVIDENCE_PAGE_";

/** The widest image worth asking for a frame `cssWidth` pixels wide. */
export function requestedWidth(
  cssWidth: number,
  zoom: number,
  density: number,
) {
  const pixels =
    Math.ceil((cssWidth * zoom * density) / WIDTH_STEP) * WIDTH_STEP;
  return Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, pixels));
}

/** Why a page is not shown, in words where the refusal is one the read
 * declares; otherwise its code. */
function refusalText(t: Translate, failure: LedgerReadFailure): string | null {
  const code = failure.kind === "unsettled" ? null : failure.reason;
  const reason = code?.startsWith(REFUSAL_PREFIX)
    ? code.slice(REFUSAL_PREFIX.length).toLowerCase()
    : null;
  return reason !== null && (REFUSALS as readonly string[]).includes(reason)
    ? t(`desktop.ledger.documents.viewer.refused.${reason}`)
    : null;
}

export function DocumentViewer({
  port,
  reader,
  reference,
  fileName,
}: {
  port: LedgerPort;
  reader: string | null;
  reference: DocumentReference;
  fileName: string;
}) {
  const t = useStrings();
  const [page, setPage] = useState(1);
  const [zoom, setZoom] = useState(0);
  const frame = useRef<HTMLDivElement>(null);
  const [frameWidth, setFrameWidth] = useState(0);
  useEffect(() => {
    const at = frame.current;
    if (!at) return;
    setFrameWidth(at.clientWidth);
    const observer = new ResizeObserver(() => setFrameWidth(at.clientWidth));
    observer.observe(at);
    return () => observer.disconnect();
  }, []);

  const scale = ZOOMS[zoom] ?? 1;
  const width =
    frameWidth > 0
      ? requestedWidth(frameWidth, scale, window.devicePixelRatio || 1)
      : null;
  const { read, reread } = useLedgerRead(
    port,
    reader,
    width !== null,
    "ledger.evidence.page",
    width === null
      ? null
      : { ...referenceFields(reference), page, max_width: width },
    `${reference.kind}:${reference.id}:${page}:${width}`,
  );
  // While a sharper drawing of the same page is read, the one already
  // drawn stays on screen.
  const [kept, setKept] = useState<EvidencePageResult | null>(null);
  useEffect(() => {
    if (read.phase === "ready") setKept(read.value);
  }, [read]);
  const shown =
    read.value ?? (kept !== null && kept.page === page ? kept : null);
  const count = shown?.page_count ?? kept?.page_count ?? null;
  const reading = read.phase === "reading";
  const refusal = read.phase === "failed" ? refusalText(t, read.failure) : null;

  return (
    <section
      aria-label={t("desktop.ledger.documents.viewer.label")}
      className="ledger-document flex min-h-0 flex-1 flex-col gap-2"
    >
      <div className="flex flex-wrap items-center gap-1">
        {count !== null && count > 1 && (
          <>
            <IconButton
              className="ledger-document-previous"
              label={t("desktop.ledger.documents.viewer.previous")}
              disabled={page <= 1}
              onClick={() => setPage((at) => Math.max(1, at - 1))}
            >
              <Icon name="back" size="sm" />
            </IconButton>
            <span className="ledger-document-page text-sm tabular-nums">
              {t("desktop.ledger.documents.viewer.page", { page, count })}
            </span>
            <IconButton
              className="ledger-document-next"
              label={t("desktop.ledger.documents.viewer.next")}
              disabled={page >= count}
              onClick={() => setPage((at) => Math.min(count, at + 1))}
            >
              <Icon name="forward" size="sm" />
            </IconButton>
          </>
        )}
        <span className="flex-1" />
        <IconButton
          className="ledger-document-zoom-out"
          label={t("desktop.ledger.documents.viewer.zoom_out")}
          disabled={zoom <= 0}
          onClick={() => setZoom((at) => Math.max(0, at - 1))}
        >
          <Icon name="zoomOut" size="sm" />
        </IconButton>
        <span className="ledger-document-zoom text-sm text-muted-foreground tabular-nums">
          {t("desktop.ledger.documents.viewer.zoom", {
            percent: Math.round(scale * 100),
          })}
        </span>
        <IconButton
          className="ledger-document-zoom-in"
          label={t("desktop.ledger.documents.viewer.zoom_in")}
          disabled={zoom >= ZOOMS.length - 1}
          onClick={() => setZoom((at) => Math.min(ZOOMS.length - 1, at + 1))}
        >
          <Icon name="zoomIn" size="sm" />
        </IconButton>
        <IconButton
          className="ledger-document-fit"
          label={t("desktop.ledger.documents.viewer.fit")}
          disabled={zoom === 0}
          onClick={() => setZoom(0)}
        >
          <Icon name="maximize" size="sm" />
        </IconButton>
      </div>
      <div
        ref={frame}
        // The page can be wider than its frame: the keyboard scrolls it too.
        tabIndex={0}
        className="ledger-document-frame relative min-h-0 flex-1 overflow-auto rounded-md border bg-muted"
        aria-busy={reading || undefined}
      >
        {shown && (
          <img
            className="ledger-document-image block max-w-none"
            style={{ width: `${scale * 100}%` }}
            src={shown.image_data_url}
            alt={t("desktop.ledger.documents.viewer.image", {
              file: shown.file_name ?? fileName,
              page: shown.page,
            })}
            draggable={false}
          />
        )}
        {reading && (
          <div
            role="status"
            className="ledger-document-reading flex items-center gap-2 p-3 text-sm text-muted-foreground"
          >
            <Spinner />
            {t("desktop.ledger.documents.viewer.reading")}
          </div>
        )}
        {read.phase === "failed" && (
          <Alert
            tone={refusal ? "warning" : "danger"}
            role="alert"
            icon={<Icon name={refusal ? "refused" : "alert"} />}
            className="ledger-document-refused m-2"
          >
            <AlertDescription className="flex flex-wrap items-center gap-2">
              {refusal ?? (
                <>
                  {t("desktop.ledger.documents.viewer.failed")}
                  <code className="font-mono text-xs">
                    {failureCode(read.failure)}
                  </code>
                </>
              )}
              {!refusal && (
                <Button size="xs" variant="outline" onClick={reread}>
                  {t("desktop.ledger.retry")}
                </Button>
              )}
            </AlertDescription>
          </Alert>
        )}
      </div>
    </section>
  );
}
