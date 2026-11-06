import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { ModeloFormIssueLine } from "../../../shell/modeloContract/modeloWorkForm";
import { useStrings } from "../../../shell/strings";
import { ATTENTION_ICON, ATTENTION_TONE } from "../workspace/Marks";

// What the latest calculation noted about one box, beside the box. Each note
// is the read model's sentence under the read model's level: a note the
// filing gate withholds the file on is served at the blocking level, and one
// that withholds nothing, such as a zero the calculation proved, at its own.
// The window reads no reason code and decides no level.

/** The notes under a box on its own line, each with its level in words. */
export function BoxNoteList({
  notes,
  className,
}: {
  notes: readonly ModeloFormIssueLine[];
  className?: string;
}) {
  const t = useStrings();
  if (notes.length === 0) return null;
  return (
    <ul
      aria-label={t("desktop.modelo.box_notes.label")}
      className={cn("flex flex-col gap-1", className)}
    >
      {notes.map((note, index) => (
        <li
          key={`${note.level}-${index}`}
          data-level={note.level}
          className="flex items-start gap-1.5 text-sm"
        >
          <Icon
            name={ATTENTION_ICON[note.level]}
            size="xs"
            className={cn("mt-0.5 shrink-0", ATTENTION_TONE[note.level])}
          />
          <span className="flex min-w-0 flex-col">
            <span
              className={cn("text-xs font-medium", ATTENTION_TONE[note.level])}
            >
              {t(`workspace.modelo.level.${note.level}`)}
            </span>
            <span className="text-foreground">{note.message}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

/** The notes of a box in a grid, as the glyph of the most urgent one with
 * every note in its tooltip. */
export function BoxNoteMark({
  notes,
}: {
  notes: readonly ModeloFormIssueLine[];
}) {
  const t = useStrings();
  const first = notes[0];
  if (!first) return null;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          tabIndex={0}
          role="img"
          aria-label={t("desktop.modelo.box_notes.label")}
          data-level={first.level}
          className="inline-flex"
        >
          <Icon
            name={ATTENTION_ICON[first.level]}
            size="xs"
            className={ATTENTION_TONE[first.level]}
          />
        </span>
      </TooltipTrigger>
      <TooltipContent className="flex-col items-start">
        {notes.map((note, index) => (
          <span key={`${note.level}-${index}`} className="flex flex-col">
            <span className="text-xs font-medium">
              {t(`workspace.modelo.level.${note.level}`)}
            </span>
            {note.message}
          </span>
        ))}
      </TooltipContent>
    </Tooltip>
  );
}
