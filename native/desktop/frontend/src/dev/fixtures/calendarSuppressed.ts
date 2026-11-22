import type {
  ApplicabilityVerdict,
  OverviewSuppressedEntrySnapshot,
} from "../../shell/calendarContract";
import type { FilingCalendarServed } from "../../shell/calendarContract";
import { fixtureDay, fixtureYear } from "@/dev/fixtureDates";
import {
  calendarWarning,
  EMPTY_CALENDAR,
  FIXTURE_CALENDAR,
  servedCalendar,
} from "./calendar";

// SYNTHETIC: calendars that carry the rows a read serves when it is asked
// for the obligations it holds off the schedule, typed by the generated wire
// types. The sentences stand in for the ones the worker renders; they state
// no tax meaning, and the verdict they are named after is only a label.

const FIXTURE_YEAR = String(fixtureYear);

function held(
  modelo: string,
  verdict: ApplicabilityVerdict,
): OverviewSuppressedEntrySnapshot {
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
    actions: [],
  };
}

/** The verdicts a read can hold an obligation under, one row each. */
export const SUPPRESSED_ENTRIES: OverviewSuppressedEntrySnapshot[] = [
  held("115", "not_applicable"),
  held("180", "attribution_pass_through"),
  held("347", "incomplete"),
];

/** Owed entries, and beside them the obligations the read held off. */
export const SUPPRESSED_CALENDAR: FilingCalendarServed = {
  ...FIXTURE_CALENDAR,
  suppressed_entries: SUPPRESSED_ENTRIES,
};

/** Nothing owed in the range, and obligations held off it. */
export const SUPPRESSED_ONLY_CALENDAR: FilingCalendarServed = {
  ...EMPTY_CALENDAR,
  suppressed_entries: SUPPRESSED_ENTRIES,
};

/** A read that was asked for the held-off obligations and served none. */
export const NONE_SUPPRESSED_CALENDAR: FilingCalendarServed = {
  ...FIXTURE_CALENDAR,
  suppressed_entries: [],
};

// SYNTHETIC: a profile that claims the IVA block and leaves its four yes/no
// questions unanswered. The read still serves what the answered facts decide;
// each Modelo 303 window the unanswered questions decide is held off the
// schedule as undecided, with the reason naming the question and the profile
// edit as the way on; each question comes as a warning of its own, coded by
// its profile path; and 303 is advised as undetermined. The sentences stand
// in for the ones the worker renders.
const UNANSWERED_IVA_QUESTIONS: [string, string][] = [
  [
    "iva.redeme_enrolled",
    "Your profile does not yet record whether you are registered in the monthly VAT refund register.",
  ],
  [
    "iva.cash_accounting_regime_enrolled",
    "Your profile does not yet record whether you use the special VAT cash accounting scheme.",
  ],
  [
    "iva.voluntary_sii_enrolled",
    "Your profile does not yet record whether you chose to keep your VAT ledgers through the immediate supply of information.",
  ],
  [
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled",
    "Your profile does not yet record whether you are entitled to deduct the VAT advance payment for hydrocarbons released from a tax warehouse.",
  ],
];

/** The sentence a held 303 window serves as its reason: the REDEME question. */
export const UNANSWERED_IVA_REASON = UNANSWERED_IVA_QUESTIONS[0]![1];

/** The served sentence of each unanswered IVA question, in served order. */
export const UNANSWERED_IVA_WARNINGS = UNANSWERED_IVA_QUESTIONS.map(
  ([, text]) => text,
);

/** The third-quarter 303 window, held off the schedule as undecided. */
const UNDECIDED_303 = {
  modelo: "303",
  period: `${FIXTURE_YEAR}-3T`,
  opens_on: fixtureDay(10, 1),
  closes_on: fixtureDay(10, 20),
  adjusted_closes_on: fixtureDay(10, 20),
  verdict: "incomplete",
  verdict_words: "Synthetic words served for the incomplete verdict.",
  verdict_words_language: "en",
  reason: UNANSWERED_IVA_REASON,
  actions: [
    {
      action: { action_id: "operator.profile.edit" },
      argument_bindings: [],
    },
  ],
} satisfies OverviewSuppressedEntrySnapshot;

export const UNANSWERED_IVA_CALENDAR: FilingCalendarServed = servedCalendar({
  ...FIXTURE_CALENDAR,
  entries: FIXTURE_CALENDAR.entries.filter((entry) => entry.modelo !== "303"),
  // Beside it, a window the product did decide to hold off.
  suppressed_entries: [UNDECIDED_303, held("115", "not_applicable")],
  warnings: UNANSWERED_IVA_QUESTIONS.map(([path, text]) =>
    calendarWarning(path, text, ["303"]),
  ),
  coverage: {
    ...FIXTURE_CALENDAR.coverage,
    surfaced: FIXTURE_CALENDAR.coverage.surfaced.filter(
      (modelo) => modelo !== "303",
    ),
    advised: [
      { modelo: "303", reason: "applicability_undetermined" },
      ...FIXTURE_CALENDAR.coverage.advised,
    ],
  },
});
