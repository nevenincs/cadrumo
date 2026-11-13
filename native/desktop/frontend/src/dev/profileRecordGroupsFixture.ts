// Fixture pages of `user-profile.record-groups` for the record groups element,
// until the host relays the read. Every page has the served model's shape:
// one stream per group kind, each group's head row, then the rows that name
// it, then its linked ledger rows. Every summary, relation, kind, door label,
// concept and refusal sentence is plainly invented fixture text standing for
// the served words; no real taxpayer data appears. Every closed vocabulary the
// rows carry (group kind, door, direction, lifecycle state, reduction outcome
// and refusal) is typed against the generated contract: the generated
// constants where it ships them, otherwise an exhaustive table keyed by the
// generated union, which fails to compile when the union gains a member.

import { DIRECTIONS, LIFECYCLE_STATES } from "../shell/ledgerContract";
import type {
  OutputLanguage,
  ProfileRecordAction,
  ProfileRecordDoor,
  ProfileRecordGroupItem,
  ProfileRecordGroupKind,
  ProfileRecordGroupsProjection,
  ProfileRecordGroupStreamItem,
  ProfileRecordLedgerRowItem,
  ProfileRecordMemberItem,
  ProfileRecordReduction,
  ProfileRecordReductionOutcome,
  ProfileRecordReductionYear,
  RentalReductionRefusal,
} from "../shell/profileContract";
import type { ServedRefusal } from "../shell/refusal";

const LANGUAGE: OutputLanguage = "en";
const DIGEST = "0".repeat(64);
const MOVED_DIGEST = "1".repeat(64);

const keysOf = <Key extends string>(table: Record<Key, unknown>): Key[] =>
  Object.keys(table) as Key[];

const GROUP_KIND_TABLE: Record<ProfileRecordGroupKind, null> = {
  rental_property: null,
  pension_contribution: null,
};

/** The kinds the fixture serves, in the order the read declares them. */
export const FIXTURE_GROUP_KINDS = keysOf(GROUP_KIND_TABLE);

/** The kind that holds the fixture's groups; every other kind is empty. */
const GROUPED_KIND: ProfileRecordGroupKind = FIXTURE_GROUP_KINDS[0]!;

const DOOR_WORDS: Record<ProfileRecordDoor, string> = {
  edit: "Fixture edit",
  remove: "Fixture remove",
};
const FIXTURE_DOORS = keysOf(DOOR_WORDS);

/** The invented operation id a fixture door submits; the element only hands
 * the id to its owner, so no registered operation is named here. */
export const fixtureOperationId = (kind: ProfileRecordDoor): string =>
  `fixture-operation.${kind}`;

function door(
  kind: ProfileRecordDoor,
  row: string,
  fieldKey: string | null = null,
  words: string = DOOR_WORDS[kind],
): ProfileRecordAction {
  return {
    door: kind,
    operation_definition_id: fixtureOperationId(kind),
    label_words: `${words} ${row}`,
    label_words_language: LANGUAGE,
    field_key: fieldKey,
  };
}

const doors = (row: string): ProfileRecordAction[] =>
  FIXTURE_DOORS.map((kind) => door(kind, row));

function head(
  sectionKey: string,
  rowKey: string,
  summary: string,
  counts: { members: number; ledger: number },
): ProfileRecordGroupItem {
  const key = `${sectionKey}.${rowKey}`;
  return {
    kind: "group",
    group_key: key,
    payload_kind: GROUPED_KIND,
    section_key: sectionKey,
    row_key: rowKey,
    summary_words: summary,
    summary_words_language: LANGUAGE,
    member_count: counts.members,
    ledger_row_count: counts.ledger,
    kind_words: "Fixture group kind",
    kind_words_language: LANGUAGE,
    actions: doors("group"),
  };
}

function member(
  groupKey: string,
  sectionKey: string,
  rowKey: string,
  parentRef: string,
  summary: string,
  relation: string,
): ProfileRecordMemberItem {
  return {
    kind: "member",
    group_key: groupKey,
    row_ref: `${sectionKey}.${rowKey}`,
    parent_ref: parentRef,
    section_key: sectionKey,
    row_key: rowKey,
    relation: `${sectionKey}.fixture_reference`,
    relation_words: relation,
    relation_words_language: LANGUAGE,
    summary_words: summary,
    summary_words_language: LANGUAGE,
    kind_words: "Fixture member kind",
    kind_words_language: LANGUAGE,
    actions: doors("member"),
    reduction: null,
    contribution: null,
  };
}

const DAY_MS = 86_400_000;

/** A synthetic booking day, `index` days before the fixture is read. */
const fixtureDay = (index: number): string =>
  new Date(Date.now() - index * DAY_MS).toISOString().slice(0, 10);

function ledgerRow(
  groupKey: string,
  linkedRef: string,
  index: number,
  total: number,
  concept: boolean,
): ProfileRecordLedgerRowItem {
  return {
    kind: "ledger_row",
    group_key: groupKey,
    linked_ref: linkedRef,
    transaction_id: `fixture-transaction-${index}`,
    booked_date: fixtureDay(index),
    amount: { decimal: `${100 + index}.00` },
    currency: "EUR",
    direction: DIRECTIONS[index % DIRECTIONS.length]!,
    description: `Fixture ledger row ${index}`,
    lifecycle_state: LIFECYCLE_STATES[0],
    concept: concept ? "fixture_concept" : null,
    concept_words: concept ? "Fixture expense concept" : null,
    concept_words_language: concept ? LANGUAGE : null,
    kind_words: "Fixture ledger row kind",
    kind_words_language: LANGUAGE,
    ledger_row_index: index,
    ledger_row_total: total,
  };
}

const PRINCIPAL = "fixture_head.0";
const ACCESSORY = "fixture_head.1";

/** One principal row with two members naming it, an accessory row naming it
 * with a member of its own, and linked ledger rows, one stating a concept. */
function oneGroup(ledger: number): ProfileRecordGroupStreamItem[] {
  return [
    head("fixture_head", "0", "Fixture principal record", {
      members: 3,
      ledger,
    }),
    member(
      PRINCIPAL,
      "fixture_member",
      "0",
      PRINCIPAL,
      "Fixture member record A",
      "Fixture relation to the principal",
    ),
    member(
      PRINCIPAL,
      "fixture_head",
      "1",
      PRINCIPAL,
      "Fixture accessory record",
      "Fixture accessory relation",
    ),
    member(
      PRINCIPAL,
      "fixture_member",
      "1",
      ACCESSORY,
      "Fixture member record B",
      "Fixture relation to the accessory",
    ),
    ...Array.from({ length: ledger }, (_, index) =>
      ledgerRow(
        PRINCIPAL,
        index === 0 ? PRINCIPAL : ACCESSORY,
        index,
        ledger,
        index === 0,
      ),
    ),
  ];
}

const REDUCTION_OUTCOME_TABLE: Record<ProfileRecordReductionOutcome, null> = {
  applies: null,
  does_not_apply: null,
  not_determinable: null,
};

/** The outcomes a fixture year can serve, in the order the read declares
 * them. */
export const FIXTURE_REDUCTION_OUTCOMES = keysOf(REDUCTION_OUTCOME_TABLE);

/** The refusal a fixture year that cannot be determined states, typed against
 * the generated union. */
const FIXTURE_REFUSAL: RentalReductionRefusal = "uso_vivienda_unstated";

/** The invented field of the lease the missing fact names. */
export const FIXTURE_MISSING_FIELD = "fixture_missing_field";

/** The invented field of the lease its end door opens on. */
export const FIXTURE_END_FIELD = "fixture_end_field";

/** The first year the fixture's reductions name; later years follow it. */
const FIXTURE_FIRST_YEAR = Number(fixtureDay(0).slice(0, 4));

function reductionYear(
  outcome: ProfileRecordReductionOutcome,
  index: number,
): ProfileRecordReductionYear {
  const determined = outcome !== "not_determinable";
  const tiered = outcome === "applies";
  return {
    ejercicio: determined ? FIXTURE_FIRST_YEAR - index : null,
    outcome,
    tier: tiered ? "fixture_tier" : null,
    tier_words: tiered ? "Fixture reduction tier" : null,
    tier_words_language: tiered ? LANGUAGE : null,
    refusal_code: determined ? null : FIXTURE_REFUSAL,
    outcome_words: `Fixture outcome words ${index}`,
    outcome_words_language: LANGUAGE,
    missing_fact: determined
      ? null
      : {
          field_key: FIXTURE_MISSING_FIELD,
          fact_words: "Fixture fact the lease does not state",
          fact_words_language: LANGUAGE,
          way_out: door(
            "edit",
            "lease",
            FIXTURE_MISSING_FIELD,
            "Fixture state",
          ),
        },
  };
}

/** A reduction whose years serve the given outcomes, one year each; `stated`
 * is whether the fixture's second fact is stated. */
function reduction(
  outcomes: readonly ProfileRecordReductionOutcome[],
  stated: boolean,
): ProfileRecordReduction {
  return {
    title_words: "Fixture reduction of the lease",
    title_words_language: LANGUAGE,
    facts: [
      {
        field_key: "fixture_fact_stated",
        fact_words: "Fixture fact the lease states",
        fact_words_language: LANGUAGE,
        stated: true,
      },
      {
        field_key: FIXTURE_MISSING_FIELD,
        fact_words: "Fixture fact the lease does not state",
        fact_words_language: LANGUAGE,
        stated,
      },
    ],
    years: outcomes.map((outcome, index) => reductionYear(outcome, index)),
  };
}

const LEASE_HEAD = "fixture_lease_head.0";

/** A property whose lease members each state a reduction: one determined for
 * a year of each outcome that names a year, one that cannot be determined,
 * with the missing fact and its way out, and an open lease with its end door
 * among its own. */
function reductionGroup(): ProfileRecordGroupStreamItem[] {
  const determined = FIXTURE_REDUCTION_OUTCOMES.filter(
    (outcome) => outcome !== "not_determinable",
  );
  const lease = (rowKey: string, summary: string) =>
    member(
      LEASE_HEAD,
      "fixture_lease",
      rowKey,
      LEASE_HEAD,
      summary,
      "Fixture relation to the property",
    );
  return [
    head("fixture_lease_head", "0", "Fixture property with leases", {
      members: 3,
      ledger: 0,
    }),
    {
      ...lease("0", "Fixture lease with a stated reduction"),
      reduction: reduction(determined, true),
    },
    {
      ...lease("1", "Fixture lease with a missing fact"),
      reduction: reduction(["not_determinable"], false),
    },
    {
      ...lease("2", "Fixture open lease"),
      actions: [
        ...doors("lease"),
        door("edit", "lease", FIXTURE_END_FIELD, "Fixture end"),
      ],
      reduction: reduction(["applies"], true),
    },
  ];
}

export type RecordGroupScenario =
  | "none"
  | "one_group"
  | "paged"
  | "stale_continuation"
  | "unlinked"
  | "reductions";

const STREAMS: Record<RecordGroupScenario, ProfileRecordGroupStreamItem[]> = {
  none: [],
  one_group: oneGroup(2),
  paged: oneGroup(6),
  stale_continuation: oneGroup(6),
  unlinked: oneGroup(0),
  reductions: reductionGroup(),
};

/** How many items one fixture page holds, small so paging shows. */
export const FIXTURE_PAGE_SIZE = 6;

/** The page the fixture read serves for `kind` at `cursor`; the stale
 * scenario refuses every continuation as the read refuses one whose profile
 * moved. Only the first kind holds groups. */
export function fixtureRecordGroupsPage(
  scenario: RecordGroupScenario,
  kind: ProfileRecordGroupKind,
  cursor: number,
): ProfileRecordGroupsProjection {
  const stream = kind === GROUPED_KIND ? STREAMS[scenario] : [];
  const common = {
    profile_id: "00000000-0000-4000-8000-000000000000",
    group_kind: kind,
    record_revision: 1,
    content_digest: DIGEST,
    ledger_digest: DIGEST,
    cursor,
  };
  if (scenario === "stale_continuation" && cursor > 0)
    return {
      ...common,
      outcome: "refused",
      refusal_code: "stale_revision",
      refusal_words:
        "Fixture refusal: the list moved since it was read. Read it again.",
      refusal_words_language: LANGUAGE,
      ledger_digest: MOVED_DIGEST,
      next_cursor: null,
      total_items: 0,
      items: [],
    };
  const end = Math.min(cursor + FIXTURE_PAGE_SIZE, stream.length);
  return {
    ...common,
    outcome: "page",
    refusal_code: null,
    refusal_words: null,
    refusal_words_language: null,
    next_cursor: end < stream.length ? end : null,
    total_items: stream.length,
    items: stream.slice(cursor, end),
  };
}

/** A removal refused because ledger rows still name the row, as the row
 * operation's refusal would be served. */
export const REMOVAL_REFUSED: ServedRefusal = {
  refusal_words: "Fixture refusal: ledger rows still name this record.",
  refusal_words_language: LANGUAGE,
  verdict: null,
};
