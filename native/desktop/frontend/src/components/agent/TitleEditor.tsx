import { useRef } from "react";
import { cn } from "@/components/ui/cn";
import { Input } from "@/components/ui/input";
import { useStrings } from "../../shell/strings";

/** `MAX_RUN_TITLE_CHARS`: the longest title the agent keeps. */
export const TITLE_MAX = 200;

/**
 * A conversation's title, written over in place. Enter or leaving the field
 * keeps what it holds; Escape, or a title left empty or unchanged, keeps the
 * one it had. Either way it is settled once.
 */
export function TitleEditor({
  title,
  onCommit,
  onCancel,
  className,
}: {
  title: string;
  onCommit: (title: string) => void;
  onCancel: () => void;
  className?: string;
}) {
  const t = useStrings();
  // Enter and Escape settle the field before it loses focus to the redraw;
  // the blur that follows must not settle it again.
  const settled = useRef(false);
  const settle = (value: string | null) => {
    if (settled.current) return;
    settled.current = true;
    const named = value?.trim() ?? "";
    if (named && named !== title.trim()) onCommit(named);
    else onCancel();
  };
  return (
    <Input
      controlSize="sm"
      aria-label={t("desktop.agent.rename_label")}
      defaultValue={title}
      maxLength={TITLE_MAX}
      autoFocus
      onFocus={(event) => event.currentTarget.select()}
      onBlur={(event) => settle(event.currentTarget.value)}
      onKeyDown={(event) => {
        if (event.nativeEvent.isComposing) return;
        if (event.key === "Enter") {
          event.preventDefault();
          settle(event.currentTarget.value);
        } else if (event.key === "Escape") {
          event.preventDefault();
          event.stopPropagation();
          settle(null);
        }
      }}
      // A double click selects words in the field, not the bar's maximize.
      onDoubleClick={(event) => event.stopPropagation()}
      className={cn("font-medium", className)}
    />
  );
}
