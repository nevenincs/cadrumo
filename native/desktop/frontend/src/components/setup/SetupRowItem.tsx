import { useId } from "react";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import type { SetupRow } from "../../ipc/contract";
import { useStrings } from "../../shell/strings";
import { formatSize } from "../agent/files";
import { actionWords, itemName, rowSentence, rowTone } from "./setupWords";

/** A row's state said once: its sentence, marked by a glyph that repeats
 * nothing. */
export function RowState({ row }: { row: SetupRow }) {
  const t = useStrings();
  const tone = rowTone(row);
  return (
    <p className="flex items-start gap-2 text-sm text-foreground">
      {tone === "working" ? (
        <Spinner className="mt-0.5" />
      ) : (
        <Icon
          name={tone === "ready" ? "check" : "info"}
          className={
            tone === "ready" ? "mt-0.5 text-success" : "mt-0.5 text-faint"
          }
        />
      )}
      <span data-setup-sentence>{rowSentence(t, row)}</span>
    </p>
  );
}

/** One component: its name, then its state said once -- its sentence, marked
 * by a glyph that repeats nothing -- its size where it has one, and the one
 * button that would move it on. */
export function SetupRowItem({
  row,
  locale,
  disabled,
  onAct,
}: {
  row: SetupRow;
  locale: string;
  disabled?: boolean;
  onAct?: (row: SetupRow) => void;
}) {
  const t = useStrings();
  const headingId = useId();
  const tone = rowTone(row);
  const action = actionWords(t, row.recovery);
  return (
    <li
      data-setup-row={row.item}
      data-setup-tone={tone}
      aria-labelledby={headingId}
      className="grid gap-1 rounded-lg bg-accent p-3"
    >
      <h4
        id={headingId}
        className="min-w-0 font-medium wrap-anywhere text-foreground"
      >
        {itemName(t, row.kind)}
      </h4>
      <RowState row={row} />
      {row.size_bytes !== null && row.state !== "ready" && (
        <p className="text-sm text-muted-foreground">
          {formatSize(locale, row.size_bytes)}
        </p>
      )}
      {onAct && action && (
        <Button
          variant="outline"
          size="xs"
          className="justify-self-start"
          disabled={disabled}
          onClick={() => onAct(row)}
        >
          {action}
        </Button>
      )}
    </li>
  );
}
