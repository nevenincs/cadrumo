import type { ReactNode } from "react";
import type {
  ProjectUnresolvedBindingProjection,
  ProjectUnresolvedCasillaProjection,
} from "../../../shell/modeloContract/modelo";

// The inputs and boxes the application could not give a value for, with the
// words it served for each, whether it said them for a projection or for a
// calculation. The window names the box by the number the read model serves
// for it, none for a working figure the form does not print, with the form's
// label, and words nothing else: a box listed here has no figure, and is never
// drawn as a zero.

/** A box as the read model names it: its id, to find the form's field, and
 * the number the form prints for it, if any. */
export type UnresolvedBox = { casilla_id: string | null; box: string | null };

/** The name of a language, in the window's own. */
export function languageName(locale: string, code: string): string {
  try {
    return (
      new Intl.DisplayNames([locale], { type: "language" }).of(code) ?? code
    );
  } catch {
    return code;
  }
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section aria-label={title} className="flex flex-col gap-2">
      <h4 className="text-sm font-medium text-muted-foreground">{title}</h4>
      {children}
    </section>
  );
}

export function UnresolvedFindings({
  bindings,
  casillas,
  bindingsTitle,
  casillasTitle,
  boxName,
}: {
  bindings: readonly ProjectUnresolvedBindingProjection[];
  casillas: readonly ProjectUnresolvedCasillaProjection[];
  bindingsTitle: string;
  casillasTitle: string;
  /** A box as the window names it, by its served number and the form's
   * label. */
  boxName(box: UnresolvedBox): ReactNode;
}) {
  // Boxes left without a figure for one reason share the sentence that says it.
  const reasons = new Map<string, ProjectUnresolvedCasillaProjection[]>();
  for (const row of casillas)
    reasons.set(row.reason_words, [
      ...(reasons.get(row.reason_words) ?? []),
      row,
    ]);
  return (
    <>
      {bindings.length > 0 && (
        <Section title={bindingsTitle}>
          <ul className="flex flex-col divide-y divide-border rounded-lg border border-border bg-card">
            {bindings.map((row) => (
              <li
                key={row.binding_id}
                data-unresolved-credit={row.casilla_id ?? row.binding_id}
                className="flex flex-col gap-1 px-4 py-3"
              >
                {boxName(row)}
                {row.source_words && (
                  <span className="text-sm text-faint">{row.source_words}</span>
                )}
                <span className="text-sm text-muted-foreground">
                  {row.words}
                </span>
              </li>
            ))}
          </ul>
        </Section>
      )}
      {reasons.size > 0 && (
        <Section title={casillasTitle}>
          {[...reasons].map(([words, boxes]) => (
            <div
              key={words}
              className="flex flex-col gap-2 rounded-lg border border-border bg-card px-4 py-3"
            >
              <ul className="flex flex-col gap-1.5">
                {boxes.map((row) => (
                  <li key={row.casilla_id} data-unresolved-box={row.casilla_id}>
                    {boxName(row)}
                  </li>
                ))}
              </ul>
              <span className="text-sm text-muted-foreground">{words}</span>
            </div>
          ))}
        </Section>
      )}
    </>
  );
}
