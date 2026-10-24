import { Icon, type IconName } from "@/components/ui/icon";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type {
  ModeloFormAttention,
  ModeloFormAttentionCount,
  ModeloFormDeadlineTone,
} from "../../../shell/modeloContract";

// The workspace's succinct marks: a glyph and a count, the read model's
// words in the tooltip and the accessible name.

export const ATTENTION_ICON: Record<ModeloFormAttention, IconName> = {
  blocks: "refused",
  missing: "alert",
  confirm: "pending",
  check: "eye",
  info: "info",
};

export const ATTENTION_TONE: Record<ModeloFormAttention, string> = {
  blocks: "text-destructive",
  missing: "text-destructive",
  confirm: "text-warning",
  check: "text-muted-foreground",
  info: "text-faint",
};

/** How urgently a deadline reads, as the read model's tone says; colour
 * only reinforces the words. */
export const DEADLINE_TONE: Record<ModeloFormDeadlineTone, string> = {
  normal: "text-muted-foreground",
  soon: "text-warning",
  urgent: "text-destructive",
  muted: "text-faint",
};

/** One attention level the read model counted, as a glyph and its count. */
export function AttentionMark({ entry }: { entry: ModeloFormAttentionCount }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          role="img"
          aria-label={entry.words}
          className="inline-flex items-center gap-1 rounded-full bg-secondary px-2 py-0.5 text-xs font-medium tabular-nums text-secondary-foreground"
        >
          <Icon
            name={ATTENTION_ICON[entry.level]}
            size="xs"
            className={ATTENTION_TONE[entry.level]}
          />
          <span aria-hidden="true">{entry.count}</span>
        </span>
      </TooltipTrigger>
      <TooltipContent>{entry.words}</TooltipContent>
    </Tooltip>
  );
}

/** A glyph that says one thing, with its words for the reader. */
export function GlyphMark({
  icon,
  words,
  className,
}: {
  icon: IconName;
  words: string;
  className?: string;
}) {
  return (
    <Icon
      name={icon}
      size="xs"
      role="img"
      aria-label={words}
      className={className}
    />
  );
}
