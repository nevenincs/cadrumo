import type {
  ObligationStatus,
  OverviewCalendarScope,
  OverviewFilingStatus,
  OverviewPeriodState,
} from "../../shell/calendarContract";
import type { FilingCalendarServed } from "../../shell/calendarContract";
import type { NotificationsSummary } from "../../shell/views";
import {
  fixtureDay,
  fixtureInstant,
  fixtureMonth,
  fixtureYear,
} from "@/dev/fixtureDates";
import { daysBetween } from "@/shared/dates";

// A filing calendar in the shape the product reports, for the scenario host
// and the stories. The dates are fixed around `TODAY`, so a story looks the
// same on any day; nothing here is a real taxpayer's.

export const FIXTURE_TODAY = fixtureDay(10, 6);

/** The year of `FIXTURE_TODAY`, which its annual obligations belong to. */
const FIXTURE_YEAR = String(fixtureYear);

/** The deadline status a fixture row carries with each reading, unless the
 * row names its own. A reading the product could not place is reported as
 * not applicable; a close it could not work out is set row by row. */
export const FIXTURE_STATUS: Record<OverviewPeriodState, ObligationStatus> = {
  due: "UPCOMING",
  late: "OVERDUE",
  filed: "FILED",
  unknown: "NOT_APPLICABLE",
};

/** What a fixture row sets beyond its Modelo, period and dates: any field of
 * the served row, and any of its filing evidence. */
export type EntryChange = Partial<
  Omit<FilingCalendarServed["entries"][number], "filing_evidence">
> & {
  filing_evidence?: Partial<
    FilingCalendarServed["entries"][number]["filing_evidence"]
  >;
};

/** The fields the product decides from a calendar row rather than stores. */
type ProductDecided =
  | "days_until_close"
  | "filing_status"
  | "filing_status_words"
  | "filing_status_words_language"
  | "scopes";
type ServedRow = Omit<FilingCalendarServed["entries"][number], ProductDecided>;

// The fixture stands in for the product, so it serves these as the
// product's calendar_models decides them: signed days from the evaluated
// day to the binding close, none where the holiday calendar could not fix
// the close; the strongest evidence's one filing status; and every scope
// that holds on the evaluated day. A row may name its own, as a test that
// serves what its dates would not give does.
const productDaysUntilClose = (row: ServedRow): number | null =>
  row.holiday_coverage === "calendar_unavailable"
    ? null
    : daysBetween(row.evaluated_on, row.adjusted_closes_on);

const AEAT_FILING_STATUS: Partial<
  Record<
    FilingCalendarServed["entries"][number]["filing_evidence"]["aeat_submission_state"],
    OverviewFilingStatus
  >
> = {
  justificante_verified: "receipt_verified",
  accepted: "accepted",
  submitted_observed: "submitted",
};
const PERIOD_FILING_STATUS: Record<OverviewPeriodState, OverviewFilingStatus> =
  {
    due: "due",
    late: "overdue",
    unknown: "unknown",
    filed: "evidence_withheld",
  };

function productFilingStatus(row: ServedRow): OverviewFilingStatus {
  const { aeat_submission_state: aeat, local_filing_state: local } =
    row.filing_evidence;
  const observed = AEAT_FILING_STATUS[aeat];
  if (observed) return observed;
  if (local === "external_baseline_imported") return "imported";
  if (local === "ready_to_file") return "recorded_locally";
  return PERIOD_FILING_STATUS[row.user_state];
}

/** The product's scopes in their declaration order, the order it serves them in. */
const SCOPE_ORDER: readonly OverviewCalendarScope[] = [
  "past",
  "ahead",
  "upcoming",
  "overdue",
  "filed",
  "evidence_unknown",
];

function productScopes(row: ServedRow): OverviewCalendarScope[] {
  const closed = row.adjusted_closes_on < row.evaluated_on;
  const held: Record<OverviewCalendarScope, boolean> = {
    past: closed && row.status !== "UNKNOWN",
    ahead: !closed,
    upcoming: !closed && row.user_state === "due",
    overdue: closed && row.user_state === "late",
    filed: row.user_state === "filed",
    // The calendar read never withholds a row's own AEAT axis.
    evidence_unknown: false,
  };
  return SCOPE_ORDER.filter((scope) => held[scope]);
}

/** A served calendar row as the product writes it, due and not filed unless
 * `change` says otherwise. */
export function calendarEntry(
  modelo: string,
  period: string,
  opens: string,
  closes: string,
  change: EntryChange = {},
  evaluatedOn: string = FIXTURE_TODAY,
): FilingCalendarServed["entries"][number] {
  const {
    filing_evidence: evidence = {},
    days_until_close: count,
    filing_status: filingStatus,
    filing_status_words: words,
    filing_status_words_language: wordsLanguage,
    scopes,
    ...row
  } = change;
  const served: ServedRow = {
    modelo,
    period,
    opens_on: opens,
    closes_on: closes,
    adjusted_closes_on: closes,
    shift_reason: "none",
    holiday_refs: [],
    jurisdictions: [],
    // The product reports the holiday calendar unavailable for every close
    // it could not work out.
    holiday_coverage:
      change.status === "UNKNOWN" ? "calendar_unavailable" : "national_only",
    payment_cutoff_on: null,
    evaluated_on: evaluatedOn,
    days_overdue: null,
    status: FIXTURE_STATUS[change.user_state ?? "due"],
    user_state: "due",
    recovery: null,
    recovery_action: null,
    filing_year: null,
    censo_enrolment_state: "not_checked",
    source: "registry_deadline",
    local_work_unit_id: null,
    local_work_unit_name: null,
    local_work_unit_revision_id: null,
    profile_confirmation_required: false,
    missing_profile_information: [],
    ...row,
    filing_evidence: {
      modelo,
      filing_year: null,
      period,
      local_filing_state: "not_ready_to_file",
      local_filing_record_id: null,
      local_calculation_revision_id: null,
      local_filed_at: null,
      aeat_submission_state: "not_observed",
      aeat_submitted_at: null,
      aeat_reference_id: null,
      aeat_snapshot_id: null,
      aeat_evidence_kind: null,
      aeat_evidence_conflict_reference_ids: [],
      aeat_evidence_concerns: [],
      verified_justificante_csv: null,
      justificante_required: true,
      justificante_verified: false,
      evidence_source: null,
      ...evidence,
    },
  };
  const status = filingStatus ?? productFilingStatus(served);
  return {
    ...served,
    days_until_close:
      "days_until_close" in change
        ? (count ?? null)
        : productDaysUntilClose(served),
    filing_status: status,
    // SYNTHETIC: the product serves the words of its locale catalogue; the
    // window does not draw them, so the fixture serves placeholder words.
    filing_status_words:
      words ?? `Synthetic words served for the ${status} filing status.`,
    filing_status_words_language: wordsLanguage ?? "en",
    scopes: scopes ?? productScopes(served),
  };
}

// The product's two orders, as its calendar_models decides them: the list
// by the month a window closes in, known closes before unknown ones, then
// close date and identity; attention by reading (late, due, unknown,
// filed), then the same tie-breaks.
const ATTENTION_RANK: Record<OverviewPeriodState, number> = {
  late: 0,
  due: 1,
  unknown: 2,
  filed: 3,
};
const identity = (row: FilingCalendarServed["entries"][number]): string[] => [
  row.adjusted_closes_on,
  row.modelo,
  row.period,
  row.local_work_unit_id ?? "",
];
const byKey = (a: (string | number)[], b: (string | number)[]): number => {
  for (let at = 0; at < a.length; at += 1) {
    const [left, right] = [a[at]!, b[at]!];
    if (left !== right) return left < right ? -1 : 1;
  }
  return 0;
};
const listKey = (row: FilingCalendarServed["entries"][number]) => [
  row.adjusted_closes_on.slice(0, 7),
  Number(row.status === "UNKNOWN"),
  ...identity(row),
];
const attentionKey = (row: FilingCalendarServed["entries"][number]) => [
  ATTENTION_RANK[row.user_state],
  Number(row.status === "UNKNOWN"),
  ...identity(row),
];

/** A calendar as the product serves it: its entries in list order and its
 * attention order over them, whatever order the fixture wrote them in. */
export function servedCalendar(
  calendar: Omit<FilingCalendarServed, "attention_order">,
): FilingCalendarServed {
  const entries = [...calendar.entries].sort((a, b) =>
    byKey(listKey(a), listKey(b)),
  );
  const attention_order = entries
    .map((_, index) => index)
    .sort((a, b) =>
      byKey(attentionKey(entries[a]!), attentionKey(entries[b]!)),
    );
  return { ...calendar, entries, attention_order };
}

const entry = calendarEntry;

/** Something the product observed, as it serves it to the window. */
export function calendarEvent(
  type: FilingCalendarServed["events"][number]["event_type"],
  on: string,
  summary: string,
  change: Partial<FilingCalendarServed["events"][number]> = {},
): FilingCalendarServed["events"][number] {
  return {
    event_type: type,
    post_filing_kind: null,
    notificacion_estado_servicio: null,
    event_date: on,
    source: type === "filing" ? "filed_declarations" : "notifications",
    summary,
    reference_id: `fixture-${type}-${on}`,
    snapshot_id: null,
    modelo: null,
    filing_year: null,
    period: null,
    status: null,
    aeat_submission_state: null,
    aeat_submitted_at: null,
    justificante_verified: null,
    verified_justificante_csv: null,
    ...change,
  };
}

const observed = calendarEvent;

/** A profile detail the calendar had to assume: its locale key in `message`,
 * which the window never shows, and the sentence it renders in `text`. */
export function calendarWarning(
  code: string,
  text: string | null,
  affected: string[] = [],
): FilingCalendarServed["warnings"][number] {
  return {
    code,
    message: `cli.overview.warning.${code}`,
    fix_action: {
      action: { action_id: "operator.profile.edit" },
      argument_bindings: [],
    },
    affected_modelos: affected,
    text,
  };
}

export const FIXTURE_CALENDAR: FilingCalendarServed = servedCalendar({
  range: { from_date: fixtureDay(7, 1), to_date: fixtureDay(6, 30, 1) },
  support: {
    floor: fixtureYear - 4,
    horizon: fixtureYear,
    hard_ceiling: null,
    state: "supported",
  },
  evaluated_on: FIXTURE_TODAY,
  generated_at: `${FIXTURE_TODAY}T09:14:05Z`,
  completeness: {
    explicitly_set_keys: [],
    defaulted_keys: [],
    computable_modelos: [],
    defaulted_modelos: [],
  },
  taxpayer_model_declared: true,
  incomplete_reason: null,
  late_count: null,
  applicable_modelos_without_deadline: null,
  suppressed_entries: [],
  entries: [
    entry("303", `${FIXTURE_YEAR}-2T`, fixtureDay(7, 1), fixtureDay(7, 20), {
      user_state: "filed",
      filing_evidence: {
        local_filing_state: "ready_to_file",
        aeat_submission_state: "justificante_verified",
        justificante_verified: true,
      },
    }),
    entry("130", `${FIXTURE_YEAR}-2T`, fixtureDay(7, 1), fixtureDay(7, 20), {
      user_state: "late",
      days_overdue: 78,
      filing_evidence: { local_filing_state: "ready_to_file" },
    }),
    entry("303", `${FIXTURE_YEAR}-3T`, fixtureDay(10, 1), fixtureDay(10, 20), {
      payment_cutoff_on: fixtureDay(10, 15),
      filing_evidence: { local_filing_state: "ready_to_file" },
    }),
    entry("130", `${FIXTURE_YEAR}-3T`, fixtureDay(10, 1), fixtureDay(10, 20)),
    entry("111", `${FIXTURE_YEAR}-3T`, fixtureDay(10, 1), fixtureDay(10, 20), {
      user_state: "filed",
      filing_evidence: {
        aeat_submission_state: "submitted_observed",
        local_filing_state: "external_baseline_imported",
      },
    }),
    // A window that opens on its closing day: that day alone is drawn.
    entry("349", `${FIXTURE_YEAR}-3T`, fixtureDay(10, 20), fixtureDay(10, 20), {
      user_state: "unknown",
    }),
    entry(
      "303",
      `${FIXTURE_YEAR}-4T`,
      fixtureDay(1, 1, 1),
      fixtureDay(1, 30, 1),
      {
        adjusted_closes_on: fixtureDay(2, 1, 1),
        shift_reason: "weekend",
      },
    ),
    entry("390", FIXTURE_YEAR, fixtureDay(1, 1, 1), fixtureDay(1, 30, 1), {
      adjusted_closes_on: fixtureDay(2, 1, 1),
      shift_reason: "weekend",
    }),
    entry("100", FIXTURE_YEAR, fixtureDay(4, 7, 1), fixtureDay(6, 30, 1), {
      payment_cutoff_on: fixtureDay(6, 25, 1),
    }),
  ],
  events: [
    observed(
      "filing",
      fixtureDay(7, 17),
      `Modelo 303 ${FIXTURE_YEAR}-2T filed`,
      {
        status: "presentado",
        aeat_submission_state: "justificante_verified",
        aeat_submitted_at: fixtureInstant(7, 17, "10:42:00Z"),
        justificante_verified: true,
      },
    ),
    observed(
      "message",
      fixtureDay(9, 3),
      "Notification received from the agency",
    ),
    observed(
      "filing",
      fixtureDay(10, 2),
      `Modelo 111 ${FIXTURE_YEAR}-3T filed`,
      {
        status: "presentado",
        aeat_submission_state: "submitted_observed",
        aeat_submitted_at: fixtureInstant(10, 2, "08:15:00Z"),
        justificante_verified: false,
      },
    ),
  ],
  warnings: [
    calendarWarning(
      "profile_key_defaulted",
      "The foral territory is not set, so common-territory dates are used.",
      ["303", "390"],
    ),
  ],
  coverage: {
    surfaced: ["100", "111", "130", "303", "349", "390"],
    confidently_excluded: ["115", "180"],
    advised: [{ modelo: "347", reason: "applicability_undetermined" }],
    out_of_scope: ["720"],
  },
});

/** Counts from a capture earlier the same morning. */
export const FIXTURE_NOTIFICATIONS: NotificationsSummary = {
  captured_at: `${FIXTURE_TODAY}T07:02:11Z`,
  row_count: 7,
  unread: 3,
};

/** A profile whose notifications were never captured: not known to be none. */
export const NEVER_CAPTURED: NotificationsSummary = {
  captured_at: null,
  row_count: 0,
  unread: 0,
};

const without = (
  keep: (entry: FilingCalendarServed["entries"][number]) => boolean,
): FilingCalendarServed =>
  servedCalendar({
    ...FIXTURE_CALENDAR,
    entries: FIXTURE_CALENDAR.entries.filter(keep),
    warnings: [],
  });

/** Only what is behind today: the mark for today closes the list. */
export const BEHIND_CALENDAR = without(
  (item) => item.adjusted_closes_on < FIXTURE_TODAY,
);

/** Only what is ahead: the mark for today opens the list. */
export const AHEAD_CALENDAR = without(
  (item) => item.adjusted_closes_on >= FIXTURE_TODAY,
);

/** Today falls between two dates of one month: the month is split by it. */
export const STRADDLING_CALENDAR: FilingCalendarServed = servedCalendar({
  ...AHEAD_CALENDAR,
  entries: [
    entry("216", fixtureMonth(9), fixtureDay(9, 21), fixtureDay(10, 1), {
      user_state: "filed",
      filing_evidence: {
        local_filing_state: "ready_to_file",
        aeat_submission_state: "accepted",
      },
    }),
    ...AHEAD_CALENDAR.entries,
  ],
});

/** Windows whose close the product could not work out, beside known ones:
 * one whose earliest close is still ahead of today, among the closes of its
 * month, and one whose earliest close has passed, which is not known to be
 * late. Their dates are only the earliest each can close. */
export const CLOSE_UNKNOWN_CALENDAR: FilingCalendarServed = servedCalendar({
  ...FIXTURE_CALENDAR,
  warnings: [],
  entries: [
    ...FIXTURE_CALENDAR.entries,
    entry("115", `${FIXTURE_YEAR}-2T`, fixtureDay(7, 1), fixtureDay(7, 20), {
      status: "UNKNOWN",
      user_state: "unknown",
    }),
    entry("123", `${FIXTURE_YEAR}-3T`, fixtureDay(10, 1), fixtureDay(10, 20), {
      status: "UNKNOWN",
      user_state: "unknown",
    }),
  ],
});

/** The same calendar with nothing due: an empty range is not a failed read. */
export const EMPTY_CALENDAR: FilingCalendarServed = {
  ...FIXTURE_CALENDAR,
  entries: [],
  attention_order: [],
  events: [],
  warnings: [],
  coverage: { ...FIXTURE_CALENDAR.coverage, surfaced: [], advised: [] },
};

/** Each reason the local projection can leave a modelo without a window. */
export const ADVISED_CALENDAR: FilingCalendarServed = {
  ...FIXTURE_CALENDAR,
  coverage: {
    ...FIXTURE_CALENDAR.coverage,
    advised: [
      { modelo: "123", reason: "applicable_window_missing" },
      { modelo: "347", reason: "applicability_undetermined" },
      { modelo: "720", reason: "registry_unmodeled" },
      { modelo: "216", reason: "applicable_window_missing" },
    ],
    out_of_scope: [],
  },
};

/** No dated entries does not mean no possible obligations. */
export const ADVICE_ONLY_CALENDAR: FilingCalendarServed = {
  ...EMPTY_CALENDAR,
  coverage: { ...ADVISED_CALENDAR.coverage, surfaced: [] },
};

// SYNTHETIC: built by hand from the served shape (code "deadline.windows_unavailable.<year>"
// and the sentence of its locale key), not seeded from a host. Replace on the next reseed.
const WINDOWS_UNAVAILABLE_WARNING = calendarWarning(
  `deadline.windows_unavailable.${FIXTURE_YEAR}`,
  "The registry has no deadline windows for part of this range, so nothing is known about the obligations that fall in it. Check the overview status; an empty list here does not mean nothing is due.",
);

/** A year with no deadline windows and so no rows: unknown, not nothing due. */
export const UNKNOWN_YEAR_EMPTY_CALENDAR: FilingCalendarServed = {
  ...EMPTY_CALENDAR,
  warnings: [WINDOWS_UNAVAILABLE_WARNING],
};

/** One year resolved and another not: the rows are shown, the gap is said. */
export const UNKNOWN_YEAR_CALENDAR: FilingCalendarServed = {
  ...FIXTURE_CALENDAR,
  warnings: [WINDOWS_UNAVAILABLE_WARNING],
};
