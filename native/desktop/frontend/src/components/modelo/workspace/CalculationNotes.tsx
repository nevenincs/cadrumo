import { Icon } from "@/components/ui/icon";
import type { RecordedCalculationNote } from "../../../shell/modeloContract";
import { useStrings } from "../../../shell/strings";

/**
 * What the calculation noticed about the filer's assets, each note as the
 * backend words it, and what kind of thing it is as a second line. A note is
 * information: it asks for nothing to be filled and is not counted anywhere.
 * Notes of one kind about two elements are two notes, and each is drawn.
 */
export function CalculationNotes({
  notes,
}: {
  notes: readonly RecordedCalculationNote[];
}) {
  const t = useStrings();
  if (notes.length === 0) return null;
  return (
    <section
      aria-label={t("workspace.modelo.notes.title")}
      className="flex flex-col gap-2"
    >
      <h3 className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
        <Icon name="info" size="xs" />
        {t("workspace.modelo.notes.title")}
      </h3>
      <p className="text-sm text-muted-foreground">
        {t("workspace.modelo.notes.lead")}
      </p>
      <ul className="flex flex-col divide-y divide-border rounded-lg border border-border bg-card">
        {notes.map((note, index) => (
          <li
            key={`${note.reason}-${index}`}
            className="flex flex-col gap-1 px-4 py-3"
          >
            <span className="text-base text-foreground">{note.message}</span>
            <span className="text-sm text-muted-foreground">{note.detail}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
