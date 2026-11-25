import { useRef, type ReactNode } from "react";
import { ResizeHandle } from "@/components/ui/resize-handle";
import { useStrings } from "../../../shell/strings";

/** The viewer's share of the review's width, in percent: its limits and a
 * keyboard step. */
const VIEWER_MIN = 25;
const VIEWER_MAX = 70;
const VIEWER_STEP = 5;
const clampShare = (share: number) =>
  Math.min(VIEWER_MAX, Math.max(VIEWER_MIN, share));

/**
 * The document beside what was read from it: the viewer on the left keeps
 * its place while the reading, the questions and the confirmation scroll
 * on the right, so the page is on screen next to the question it answers.
 */
export function ReviewColumns({
  viewer,
  share,
  onShare,
  className,
  children,
}: {
  viewer: ReactNode;
  share: number;
  onShare(share: number): void;
  className: string;
  children: ReactNode;
}) {
  const t = useStrings();
  const columns = useRef<HTMLDivElement>(null);
  return (
    <div ref={columns} className="ledger-draft flex min-h-0 min-w-0 flex-1">
      <div
        className="ledger-draft-viewer flex min-h-0 shrink-0 flex-col p-3"
        style={{ width: `${share}%` }}
      >
        {viewer}
      </div>
      <ResizeHandle
        orientation="vertical"
        className="ledger-draft-resize"
        aria-label={t("desktop.ledger.documents.viewer.resize")}
        value={share}
        onDrag={({ x }) => {
          const box = columns.current?.getBoundingClientRect();
          if (box && box.width > 0)
            onShare(clampShare(((x - box.left) / box.width) * 100));
        }}
        onStep={(direction) =>
          onShare(clampShare(share + direction * VIEWER_STEP))
        }
        onLimit={(limit) => onShare(limit === "min" ? VIEWER_MIN : VIEWER_MAX)}
      />
      <div className={`min-h-0 min-w-0 flex-1 overflow-y-auto ${className}`}>
        {children}
      </div>
    </div>
  );
}
