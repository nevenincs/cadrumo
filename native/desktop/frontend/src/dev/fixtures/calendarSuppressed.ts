import type { ApplicabilityVerdict } from "../../shell/calendarContract";
import type {
  CalendarSuppressedEntry,
  FilingCalendar,
} from "../../shell/views";
import { fixtureDay, fixtureYear } from "@/dev/fixtureDates";
import { EMPTY_CALENDAR, FIXTURE_CALENDAR } from "./calendar";

// SYNTHETIC: calendars that carry the rows a read serves when it is asked
// for the obligations it holds off the schedule, typed by the generated wire
// types. The sentences stand in for the ones the worker renders; they state
// no tax meaning, and the verdict they are named after is only a label.

const FIXTURE_YEAR = String(fixtureYear);

function held(
  modelo: string,
  verdict: ApplicabilityVerdict,
): CalendarSuppressedEntry {
  return {
    modelo,
    period: `${FIXTURE_YEAR}-3T`,
    opens_on: fixtureDay(10, 1),
    closes_on: fixtureDay(10, 20),
    adjusted_closes_on: fixtureDay(10, 20),
    verdict,
    verdict_words: `Synthetic words served for the ${verdict} verdict.`,
    verdict_words_language: "en",
    reason: `Synthetic registry reason for ${modelo}.`,
  };
}

/** The verdicts a read can hold an obligation under, one row each. */
export const SUPPRESSED_ENTRIES: CalendarSuppressedEntry[] = [
  held("115", "not_applicable"),
  held("180", "attribution_pass_through"),
  held("347", "incomplete"),
];

/** Owed entries, and beside them the obligations the read held off. */
export const SUPPRESSED_CALENDAR: FilingCalendar = {
  ...FIXTURE_CALENDAR,
  suppressed_entries: SUPPRESSED_ENTRIES,
};

/** Nothing owed in the range, and obligations held off it. */
export const SUPPRESSED_ONLY_CALENDAR: FilingCalendar = {
  ...EMPTY_CALENDAR,
  suppressed_entries: SUPPRESSED_ENTRIES,
};

/** A read that was asked for the held-off obligations and served none. */
export const NONE_SUPPRESSED_CALENDAR: FilingCalendar = {
  ...FIXTURE_CALENDAR,
  suppressed_entries: [],
};
