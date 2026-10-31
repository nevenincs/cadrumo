import { Icon } from "@/components/ui/icon";
import type { RecordedCalculationNote } from "../../../shell/modeloContract";
import { useStrings, type Translate } from "../../../shell/strings";

/** The catalogue family that states what one note says about its own
 * subject, one sentence for each kind of fact, with its values. */
const FACT_FAMILY = "application.modelo.calc_diagnostic_fact.";
/** The family that says what kind of thing a calculation noticed. */
const KIND_FAMILY = "application.modelo.calc_diagnostic.";

/** The catalogue's word for a key, or null where it has none: a key the
 * generated strings lack is never drawn. */
function worded(t: Translate, key: string, values?: Record<string, string>) {
  const said = t(key, values);
  return said === key ? null : said;
}

/**
 * What the calculation noticed about the filer's assets, as the catalogue
 * states each note with its own values, and what kind of thing it is as a
 * second line. A note is information: it asks for nothing to be filled and
 * is not counted anywhere. Notes of one kind about two elements are two
 * notes, and each is drawn. A note the catalogue has no sentence for is said
 * in general words, never as the key it carries.
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
        {notes.map((note, index) => {
          const message = worded(
            t,
            `${FACT_FAMILY}${note.fact.sentence}`,
            Object.fromEntries(note.fact.values),
          );
          const kind = worded(t, `${KIND_FAMILY}${note.reason}.what`);
          return (
            <li
              key={`${note.reason}-${index}`}
              className="flex flex-col gap-1 px-4 py-3"
            >
              <span className="text-base text-foreground">
                {message ?? kind ?? t("workspace.modelo.notes.unworded")}
              </span>
              {message && kind && (
                <span className="text-sm text-muted-foreground">{kind}</span>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
