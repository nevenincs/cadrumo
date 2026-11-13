import { useId } from "react";
import { useStrings } from "@/shell/strings";
import type { CalendarSuppressedEntry } from "@/shell/views";

/**
 * The obligations the calendar holds off its schedule, each with the
 * sentence the product served for its verdict, in the language it came in
 * and exactly as it came. They are set apart from the owed entries and
 * carry none of their marks or counts: a row here is never an obligation
 * the person owes, and the window decides nothing about which it is. The
 * section is drawn only where the read served any.
 */
export function CalendarSuppressed({
  entries,
}: {
  entries: readonly CalendarSuppressedEntry[];
}) {
  const t = useStrings();
  const heading = useId();
  if (entries.length === 0) return null;
  return (
    <section
      aria-labelledby={heading}
      className="calendar-suppressed mt-3 border-t"
    >
      <h2
        id={heading}
        className="px-4 pt-3 pb-1.5 text-xs font-semibold tracking-wider text-muted-foreground uppercase"
      >
        {t("desktop.calendar.suppressed")}
      </h2>
      <ul>
        {entries.map((entry) => (
          <li
            key={`${entry.modelo}:${entry.period}`}
            data-suppressed={`${entry.modelo}:${entry.period}`}
            className="grid gap-0.5 border-b px-4 py-2 text-sm"
          >
            <span className="flex flex-wrap items-center gap-x-2">
              <span className="font-medium">
                {t("desktop.calendar.modelo", { modelo: entry.modelo })}
              </span>
              <span className="text-muted-foreground">{entry.period}</span>
            </span>
            {/* A row from a host that did not serve the words shows the
                fields it did serve, and no wording of ours in their place. */}
            {entry.verdict_words && (
              <span
                lang={entry.verdict_words_language}
                className="text-muted-foreground"
              >
                {entry.verdict_words}
              </span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
