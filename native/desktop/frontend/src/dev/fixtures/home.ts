import type {
  HomeServed,
  HomeZoneState,
  PublicHomeProjectionV1,
} from "../../shell/homeContract";
import { fixtureDay, fixtureInstant, fixtureYear } from "@/dev/fixtureDates";

// Home in the shape the product serves it, for the scenario host and the
// stories: each zone with its own standing, the product's sentences as
// placeholders, and no taxpayer's data. SYNTHETIC: the product serves the
// words of its locale catalogue, and the window draws exactly what is served,
// so the fixture serves words of its own where the product would.

const OBSERVED = fixtureInstant(10, 6, "08:00:00Z");

const zone = (change: Partial<HomeZoneState> = {}): HomeZoneState => ({
  availability: "available",
  observed_at: OBSERVED,
  reason_code: null,
  missing_profile_paths: [],
  reason_words: null,
  reason_words_language: null,
  ...change,
});

/** A zone that is not showing its data, with the product's sentence for why. */
const withheld = (
  availability: Exclude<HomeZoneState["availability"], "available">,
  reason: string,
  words: string | null,
  change: Partial<HomeZoneState> = {},
): HomeZoneState =>
  zone({
    availability,
    observed_at: availability === "stale" ? OBSERVED : null,
    reason_code: reason,
    reason_words: words,
    reason_words_language: words === null ? null : "en",
    ...change,
  });

const PERIOD = { filing_year: fixtureYear, code: "3T" };

const READY: PublicHomeProjectionV1 = {
  generated_at: OBSERVED,
  account: {
    posture: "active",
    profile_label: "Local profile",
    expires_at: null,
  },
  actions_state: zone(),
  actions: [
    {
      rank: 0,
      action: {
        action: { action_id: "synthetic.review" },
        argument_bindings: [],
      },
      reason_code: "synthetic_reason",
      modelo: "000",
      filing_year: PERIOD.filing_year,
      period: PERIOD,
      action_words: "Synthetic: review the calculation",
      reason_words: "Synthetic: a declaration needs review",
      period_words: "Synthetic period",
      words_language: "en",
    },
    {
      rank: 1,
      action: {
        action: { action_id: "synthetic.classify" },
        argument_bindings: [],
      },
      reason_code: "synthetic_reason",
      modelo: null,
      filing_year: null,
      period: null,
      action_words: "Synthetic: classify the pending entries",
      reason_words: "Synthetic: entries are pending",
      period_words: null,
      words_language: "en",
    },
  ],
  declarations_state: zone(),
  declarations: [
    {
      work_unit_id: "a".repeat(64),
      modelo: "000",
      filing_year: PERIOD.filing_year,
      period: PERIOD,
      name: "Synthetic return",
      state: "needs_review",
      revision_id: null,
      state_words: "Synthetic: needs review",
      period_words: "Synthetic period",
      words_language: "en",
    },
    {
      work_unit_id: "b".repeat(64),
      modelo: "000",
      filing_year: PERIOD.filing_year,
      period: { ...PERIOD, code: "2T" },
      name: "Synthetic earlier return",
      state: "filed",
      revision_id: null,
      state_words: "Synthetic: recorded as filed",
      period_words: "Synthetic earlier period",
      words_language: "en",
    },
  ],
  ledger_state: zone(),
  ledger: {
    entries: 40,
    requiring_review: 2,
    unclassified: 1,
    missing_evidence: 3,
    summary_words:
      "Synthetic: 40 entries; 2 need review; 1 unclassified; 3 missing supporting documents",
    words_language: "en",
  },
  agenda_state: zone(),
  agenda_evidence_state: zone(),
  agenda: [
    {
      modelo: "000",
      filing_year: PERIOD.filing_year,
      period: PERIOD,
      due_on: fixtureDay(10, 20),
      period_state: "due",
      local_filing_state: "ready_to_file",
      aeat_submission_state: "not_observed",
      due_on_text: "Synthetic due date",
      period_words: "Synthetic period",
      words_language: "en",
      filing_status_words: "Synthetic: recorded locally",
      filing_status: "recorded_locally",
    },
  ],
  messages_state: zone(),
  messages_requiring_attention: 2,
};

const served = (
  projection: PublicHomeProjectionV1 | null,
  change: Partial<HomeServed> = {},
): HomeServed => ({
  availability: "available",
  observed_at: OBSERVED,
  refusal: null,
  projection,
  ...change,
});

/** Every zone showing its data. */
export const FIXTURE_HOME: HomeServed = served(READY);

/** Zones with nothing to show, known to have nothing: counts of zero. */
export const EMPTY_HOME: HomeServed = served({
  ...READY,
  actions: [],
  declarations: [],
  agenda: [],
  ledger: {
    entries: 0,
    requiring_review: 0,
    unclassified: 0,
    missing_evidence: 0,
    summary_words: "Synthetic: 0 entries",
    words_language: "en",
  },
  messages_requiring_attention: 0,
});

/** The standings a zone can have besides showing its data, each in its own
 * zone: none of them draws as empty or as zero. */
export const PARTIAL_HOME: HomeServed = served({
  ...READY,
  actions_state: withheld(
    "unavailable",
    "synthetic_unavailable",
    "Synthetic: next actions appear once your records are checked",
  ),
  actions: [],
  declarations_state: withheld("never_captured", "synthetic_never", null),
  declarations: [],
  ledger_state: withheld("locked", "synthetic_locked", null),
  ledger: null,
  agenda_state: withheld("stale", "synthetic_stale", null),
  agenda: [],
  agenda_evidence_state: withheld("never_captured", "synthetic_never", null),
  messages_state: withheld("unavailable", "synthetic_unavailable", null),
  messages_requiring_attention: null,
});

/** Home as a whole is not available: no zone is served. */
export const UNAVAILABLE_HOME: HomeServed = served(null, {
  availability: "unavailable",
  observed_at: null,
  refusal: "synthetic.home.unavailable",
});

export const HOME_SHAPES = {
  empty: EMPTY_HOME,
  partial: PARTIAL_HOME,
  unavailable: UNAVAILABLE_HOME,
} as const;
export type HomeShape = keyof typeof HOME_SHAPES;
