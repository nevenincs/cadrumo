// Fixture pages of `user-profile.record-groups` for the record groups element,
// until the host relays the read. Every page has the served model's shape:
// one stream per group kind, each group's head row, then the rows that name
// it, then its linked ledger rows. Every summary, relation, kind, door label,
// concept and refusal sentence is plainly invented fixture text standing for
// the served words; no real taxpayer data appears.

import type {
  ProfileRecordAction,
  ProfileRecordGroupItem,
  ProfileRecordGroupKind,
  ProfileRecordGroupsProjection,
  ProfileRecordGroupStreamItem,
  ProfileRecordLedgerRowItem,
  ProfileRecordMemberItem,
} from "../shell/profileContract";
import type { ServedRefusal } from "../shell/refusal";

const LANGUAGE = "en" as const;
const DIGEST = "0".repeat(64);
const MOVED_DIGEST = "1".repeat(64);

/** The kinds the fixture serves, in the order the read declares them. */
export const FIXTURE_GROUP_KINDS = [
  "rental_property",
  "pension_contribution",
] as const;

const doors = (row: string): ProfileRecordAction[] => [
  {
    door: "edit",
    operation_definition_id: "user-profile.repeatable-row-update",
    label_words: `Fixture edit ${row}`,
    label_words_language: LANGUAGE,
  },
  {
    door: "remove",
    operation_definition_id: "user-profile.repeatable-row-remove",
    label_words: `Fixture remove ${row}`,
    label_words_language: LANGUAGE,
  },
];

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
    payload_kind: "rental_property",
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
    direction: index % 2 === 0 ? "INCOMING" : "OUTGOING",
    description: `Fixture ledger row ${index}`,
    lifecycle_state: "ACTIVE",
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

export type RecordGroupScenario =
  "none" | "one_group" | "paged" | "stale_continuation" | "unlinked";

const STREAMS: Record<RecordGroupScenario, ProfileRecordGroupStreamItem[]> = {
  none: [],
  one_group: oneGroup(2),
  paged: oneGroup(6),
  stale_continuation: oneGroup(6),
  unlinked: oneGroup(0),
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
  const stream = kind === FIXTURE_GROUP_KINDS[0] ? STREAMS[scenario] : [];
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
