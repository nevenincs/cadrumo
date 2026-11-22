import { useId } from "react";
import { Button } from "@/components/ui/button";
import { formatViewLink } from "@/shell/navigation/links";
import { NAVIGATION } from "@/shell/navigation/projection";
import { useStrings } from "@/shell/strings";
import { PROFILE_EDIT_ACTION_ID } from "@/shell/userProfile";
import type { OverviewSuppressedEntrySnapshot } from "@/shell/calendarContract";

/**
 * The obligations the calendar holds off its schedule, each with the
 * sentence the product served for its verdict, in the language it came in
 * and exactly as it came. They are set apart from the owed entries and
 * carry none of their marks or counts: a row here is never an obligation
 * the person owes, and the window decides nothing about which it is. The
 * section is drawn only where the read served any.
 *
 * A row the product could not decide (`incomplete`) also shows the reason it
 * served, which names what is unanswered, and, where it serves the profile
 * edit as the way on, the door to the profile.
 */
export function CalendarSuppressed({
  entries,
  onNavigate,
}: {
  entries: readonly OverviewSuppressedEntrySnapshot[];
  onNavigate?: (url: string) => void;
}) {
  const t = useStrings();
  const heading = useId();
  if (entries.length === 0) return null;
  const href = formatViewLink(NAVIGATION, "profile");
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
        {entries.map((entry) => {
          const undecided = entry.verdict === "incomplete";
          const door =
            undecided &&
            entry.actions.some(
              (next) => next.action.action_id === PROFILE_EDIT_ACTION_ID,
            );
          return (
            <li
              key={`${entry.modelo}:${entry.period}`}
              data-suppressed={`${entry.modelo}:${entry.period}`}
              data-verdict={entry.verdict}
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
              {undecided && entry.reason && (
                <span data-suppressed-reason="">{entry.reason}</span>
              )}
              {door && onNavigate && (
                <span>
                  <Button variant="link" className="min-h-control-xs" asChild>
                    <a
                      href={href}
                      onClick={(event) => {
                        event.preventDefault();
                        onNavigate(href);
                      }}
                      onAuxClick={(event) => event.preventDefault()}
                    >
                      {t("desktop.profile.notice.open_profile")}
                    </a>
                  </Button>
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
