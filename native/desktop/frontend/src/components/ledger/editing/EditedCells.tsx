import type { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { facts } from "@/shell/compose";
import { useStrings } from "../../../shell/strings";

/**
 * A cell with a staged change: what will be saved after an arrow, with
 * what is stored behind it in the tooltip and in words. The stored value is
 * what the grid counts; this is drawn beside it, never instead of it.
 */
export function StagedValue({
  stored,
  staged,
  identity,
  cannot,
}: {
  /** The stored value in words, or null where it is empty. */
  stored: string | null;
  /** What will be saved, in words; null is a clear. */
  staged: string | null;
  /** The change gives the movement a new reference. */
  identity: boolean;
  /** Why the staged change cannot be saved as it is, if it cannot. */
  cannot?: string;
}) {
  const t = useStrings();
  const was = stored ?? t("desktop.ledger.edit.empty");
  const now = staged ?? t("desktop.ledger.edit.cleared");
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          data-staged=""
          className="ledger-staged relative flex h-full min-w-0 items-center gap-1 ps-1.5 before:absolute before:inset-y-1 before:start-0 before:border-s-(length:--mark-edge) before:border-dashed before:border-foreground forced-colors:before:border-[CanvasText]"
        >
          <Icon
            name="arrow"
            size="xs"
            className="shrink-0 text-muted-foreground"
          />
          <span className="min-w-0 truncate">{now}</span>
          {identity && (
            <Icon
              name="key"
              size="xs"
              className="shrink-0 text-muted-foreground"
            />
          )}
          {cannot && (
            <Icon name="alert" size="xs" className="shrink-0 text-warning" />
          )}
          <span className="sr-only">
            {facts(t, [
              t("desktop.ledger.edit.changed_was", { was }),
              identity ? t("desktop.ledger.edit.new_identity") : "",
              cannot,
            ])}
          </span>
        </span>
      </TooltipTrigger>
      <TooltipContent>
        {facts(t, [
          t("desktop.ledger.edit.not_saved_was", { was }),
          identity ? t("desktop.ledger.edit.new_identity") : "",
          cannot,
        ])}
      </TooltipContent>
    </Tooltip>
  );
}

/** A value the grammar refused, kept as typed with why. */
export function RefusedValue({ raw, reason }: { raw: string; reason: string }) {
  return (
    <span
      data-refused=""
      className="ledger-refused relative flex h-full min-w-0 items-center gap-1 ps-1.5 text-foreground before:absolute before:inset-y-1 before:start-0 before:border-s-(length:--mark-edge) before:border-destructive forced-colors:before:border-[CanvasText]"
    >
      <Icon name="refused" size="xs" className="shrink-0 text-destructive" />
      <span className="min-w-0 truncate">{raw}</span>
      <span className="sr-only">{reason}</span>
    </span>
  );
}

/** A new movement's cell: what was filled in, or that it is still needed. */
export function DraftValue({
  text,
  required,
}: {
  text: ReactNode | null;
  required: boolean;
}) {
  const t = useStrings();
  if (text !== null && text !== "")
    return <span className="min-w-0 truncate">{text}</span>;
  if (!required) return null;
  return (
    <span data-required="" className="text-muted-foreground">
      {t("desktop.ledger.draft.required")}
    </span>
  );
}

/** A new movement's status: new, not saved, with a way to drop it. */
export function DraftStatus({ onRemove }: { onRemove: () => void }) {
  const t = useStrings();
  return (
    <span className="ledger-draft-status flex min-w-0 items-center gap-1">
      <Badge>
        <Icon name="plus" size="xs" />
        {t("desktop.ledger.draft.new")}
      </Badge>
      <Button
        variant="ghost"
        size="icon-xs"
        tabIndex={-1}
        aria-label={t("desktop.ledger.draft.remove")}
        onClick={(event) => {
          event.stopPropagation();
          onRemove();
        }}
      >
        <Icon name="close" size="xs" />
      </Button>
    </span>
  );
}

/** The leading edge of a row with something staged, beside the selection
 * edge: dashed ink, never the warning tone. */
export function UnsavedEdge({ label }: { label: string }) {
  return (
    <span
      data-unsaved=""
      className="ledger-unsaved-edge pointer-events-none absolute inset-y-0 start-0 border-s-(length:--mark-edge) border-dashed border-foreground forced-colors:border-[CanvasText]"
    >
      <span className="sr-only">{label}</span>
    </span>
  );
}
