import { useState } from "react";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { Icon } from "@/components/ui/icon";
import { Kbd } from "@/components/ui/kbd";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { chordAria, chordText } from "@/shared/chords";
import { REVIEW_CHORD, UNDO_CHORD } from "../ledgerChords";
import { described, facts } from "../../../shell/compose";
import { useStrings } from "../../../shell/strings";
import type { StageTally } from "./editingModel";

/** Staged changes at which the tray suggests saving in parts. */
export const SAVE_IN_PARTS_AT = 50;

/** The staged changes in words: "15 edits on 9 movements · 1 new". */
export function tallyText(
  t: ReturnType<typeof useStrings>,
  tally: StageTally,
): string {
  return facts(t, [
    tally.movements
      ? t("desktop.ledger.tray.edits", {
          edits: tally.edits,
          movements: tally.movements,
        })
      : null,
    tally.drafts ? t("desktop.ledger.tray.new", { count: tally.drafts }) : null,
    tally.actions
      ? t("desktop.ledger.tray.actions", { count: tally.actions })
      : null,
  ]);
}

/**
 * The page-wide tray of what is staged, docked at the foot of every
 * section: "10 · Review" at rest, counted in the page's one unit. Opened,
 * it says what the count holds and offers undo and discard. While a write's
 * outcome is unknown, saving waits for a re-read.
 */
export function ChangesTray({
  tally,
  paused,
  canUndo,
  onUndo,
  onDiscard,
  onReview,
}: {
  tally: StageTally;
  /** Why saving waits, while the page's writes are paused. */
  paused: string | null;
  canUndo: boolean;
  onUndo: () => void;
  onDiscard: () => void;
  onReview: () => void;
}) {
  const t = useStrings();
  const [open, setOpen] = useState(false);
  const what = tallyText(t, tally);
  const name = t("desktop.ledger.tray.name", {
    count: tally.units,
    what,
  });
  return (
    <div
      role="region"
      aria-label={t("desktop.ledger.tray.region")}
      data-open={open || undefined}
      className="ledger-tray flex min-h-control-lg shrink-0 flex-wrap items-center gap-2 bg-chrome px-3 py-1.5 shadow-docked"
    >
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            className="ledger-tray-toggle relative ps-3 tabular-nums before:absolute before:inset-y-1 before:start-1 before:border-s-(length:--mark-edge) before:border-dashed before:border-foreground"
            aria-expanded={open}
            aria-label={name}
            onClick={() => setOpen(!open)}
          >
            <span aria-hidden="true">{tally.units}</span>
            {paused && (
              <Icon name="unknown" size="xs" className="text-warning" />
            )}
            <Icon name={open ? "chevronDown" : "chevronUp"} size="xs" />
          </Button>
        </TooltipTrigger>
        <TooltipContent>
          {facts(t, [what, t("desktop.ledger.tray.window_only")])}
        </TooltipContent>
      </Tooltip>
      {open ? (
        <span className="ledger-tray-detail flex min-w-0 flex-1 flex-wrap items-center gap-x-2 text-sm">
          <span>{what}</span>
          {tally.units >= SAVE_IN_PARTS_AT && (
            <span className="text-muted-foreground">
              {t("desktop.ledger.tray.in_parts")}
            </span>
          )}
          {paused && (
            <span className="text-muted-foreground">
              {t("desktop.ledger.tray.paused")}
            </span>
          )}
        </span>
      ) : (
        <span className="flex-1" />
      )}
      {open && (
        <>
          <IconButton
            label={t("desktop.ledger.tray.undo")}
            shortcut={chordText(UNDO_CHORD)}
            aria-keyshortcuts={chordAria(UNDO_CHORD)}
            size="sm"
            aria-disabled={canUndo ? undefined : true}
            onClick={() => {
              if (canUndo) onUndo();
            }}
          >
            <Icon name="reset" />
          </IconButton>
          <Button
            variant="ghost"
            size="sm"
            className="ledger-tray-discard"
            onClick={onDiscard}
          >
            {t("desktop.ledger.tray.discard")}
          </Button>
        </>
      )}
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            size="sm"
            className="ledger-tray-review"
            aria-keyshortcuts={chordAria(REVIEW_CHORD)}
            aria-disabled={paused || tally.units === 0 ? true : undefined}
            aria-label={
              paused
                ? described(t, t("desktop.ledger.tray.review"), paused)
                : t("desktop.ledger.tray.review_count", { count: tally.units })
            }
            onClick={() => {
              if (!paused && tally.units > 0) onReview();
            }}
          >
            {t("desktop.ledger.tray.review")}
          </Button>
        </TooltipTrigger>
        <TooltipContent>
          {paused ? (
            paused
          ) : (
            <>
              {t("desktop.ledger.tray.review_count", { count: tally.units })}
              <Kbd>{chordText(REVIEW_CHORD)}</Kbd>
            </>
          )}
        </TooltipContent>
      </Tooltip>
    </div>
  );
}
