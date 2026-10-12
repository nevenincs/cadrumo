import { useLayoutEffect, useRef, useState } from "react";
import { readPx } from "../../shell/metrics";
import { useStrings } from "../../shell/strings";
import { AgentTextAction } from "./AgentAction";
import { AttachmentTile } from "./AttachmentTile";
import { formatSize } from "./files";
import type { StagedAttachment } from "./types";

/** The rows of tiles the well shows before it folds the rest away. */
const ROWS = 2;

// A tile is two of the largest controls wide, so its name stays legible,
// and the tiles are spaced by the gap the grid below declares.
const TILE_TOKEN = "--spacing-control-lg";
const TILE_CONTROLS = 2;
const GAP_TOKEN = "--spacing";
const GAP_UNITS = 2;

/** How many tiles fit across a width, at least one. */
function columnsIn(width: number): number {
  const tile = readPx(TILE_TOKEN, 36) * TILE_CONTROLS;
  const gap = readPx(GAP_TOKEN, 4) * GAP_UNITS;
  return Math.max(1, Math.floor((width + gap) / (tile + gap)));
}

/**
 * The files staged for the next message, as square tiles in at most two
 * rows. How many go in a row is measured from the well's own width, so it
 * follows the column, not the window. What does not fit folds into a last
 * tile that offers the full list.
 */
export function AttachmentWell({
  attachments,
  locale,
  onRemove,
  onRemoveAll,
  onShowAll,
}: {
  attachments: readonly StagedAttachment[];
  locale: string;
  onRemove?: (id: string) => void;
  onRemoveAll?: () => void;
  /** Open the full list of staged files. */
  onShowAll?: () => void;
}) {
  const t = useStrings();
  const list = useRef<HTMLUListElement>(null);
  const [columns, setColumns] = useState(1);
  const empty = attachments.length === 0;

  useLayoutEffect(() => {
    const el = list.current;
    if (!el) return;
    const fit = () => setColumns(columnsIn(el.clientWidth));
    fit();
    const observer = new ResizeObserver(fit);
    observer.observe(el);
    return () => observer.disconnect();
  }, [empty]);

  if (empty) return null;

  const capacity = columns * ROWS;
  const folds = attachments.length > capacity;
  const shown = folds ? attachments.slice(0, capacity - 1) : attachments;
  const hidden = attachments.length - shown.length;
  const total = attachments.reduce((sum, file) => sum + file.sizeBytes, 0);
  const uploading = attachments.filter(
    (file) => file.state === "uploading" || file.state === "queued",
  ).length;
  const refused = attachments.filter((file) => file.state === "refused").length;

  return (
    <section
      aria-label={t("desktop.agent.attachments")}
      className="grid gap-2 border-t px-2 pt-2 pb-2"
    >
      <ul
        ref={list}
        className="grid gap-2"
        style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}
      >
        {shown.map((file) => (
          <AttachmentTile
            key={file.id}
            attachment={file}
            locale={locale}
            onRemove={onRemove ? () => onRemove(file.id) : undefined}
          />
        ))}
        {folds && (
          <li className="flex aspect-square min-w-0">
            <AgentTextAction
              variant="outline"
              onAction={onShowAll}
              className="size-full flex-col rounded-lg text-sm whitespace-normal"
            >
              {t("desktop.agent.more_files", { count: hidden })}
            </AgentTextAction>
          </li>
        )}
      </ul>
      <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
        <span>
          {t("desktop.agent.files_summary", {
            count: attachments.length,
            size: formatSize(locale, total),
          })}
        </span>
        {uploading > 0 && (
          <span>
            {t("desktop.agent.attachments_uploading", { count: uploading })}
          </span>
        )}
        {refused > 0 && (
          <span className="text-destructive">
            {t("desktop.agent.attachments_refused", { count: refused })}
          </span>
        )}
        <span className="flex-1" />
        <AgentTextAction variant="ghost" size="xs" onAction={onRemoveAll}>
          {t("desktop.agent.remove_all")}
        </AgentTextAction>
      </div>
    </section>
  );
}
