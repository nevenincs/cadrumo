// The words the Assets tab shares: its fixed labels, and the chrome words for
// the tokens the backend states about an element, a year of its plan and an
// event of its timeline. A token this table does not know reads as "other",
// never as the raw token. Nothing here decides anything.

import type { IconName } from "@/components/ui/icon";
import type { Translate } from "../../../shell/strings";
import type { AssetCounts } from "./assetsContract";

/** The labels the tab's parts name directly. */
export const ASSET_KEYS = {
  area: {
    fixed: "desktop.ledger.assets.area.fixed",
    stock: "desktop.ledger.assets.area.stock",
  },
  detail: {
    plan: "desktop.ledger.assets.detail.plan",
    timeline: "desktop.ledger.assets.detail.timeline",
    record: "desktop.ledger.assets.detail.record",
  },
  action: {
    add: "desktop.ledger.assets.action.add",
    describe: "desktop.ledger.assets.action.describe",
    correct: "desktop.ledger.assets.action.correct",
    claim: "desktop.ledger.assets.action.claim",
    dispose: "desktop.ledger.assets.action.dispose",
  },
  list: {
    label: "desktop.ledger.assets.list.label",
    empty: "desktop.ledger.assets.list.empty",
    no_name: "desktop.ledger.assets.list.no_name",
    disposed: "desktop.ledger.assets.list.disposed",
    column: {
      name: "desktop.ledger.assets.list.column.name",
      serial: "desktop.ledger.assets.list.column.serial",
      kind: "desktop.ledger.assets.list.column.kind",
      method: "desktop.ledger.assets.list.column.method",
      in_service: "desktop.ledger.assets.list.column.in_service",
    },
  },
  plan: {
    column: {
      year: "desktop.ledger.assets.plan.column.year",
      status: "desktop.ledger.assets.plan.column.status",
      planned: "desktop.ledger.assets.plan.column.planned",
      claimed: "desktop.ledger.assets.plan.column.claimed",
      days: "desktop.ledger.assets.plan.column.days",
      revision: "desktop.ledger.assets.plan.column.revision",
      matches: "desktop.ledger.assets.plan.column.matches",
      replaced_by: "desktop.ledger.assets.plan.column.replaced_by",
      used_by: "desktop.ledger.assets.plan.column.used_by",
    },
    claims: "desktop.ledger.assets.plan.claims",
    in_effect: "desktop.ledger.assets.plan.in_effect",
    replaced: "desktop.ledger.assets.plan.replaced",
    matches: "desktop.ledger.assets.plan.matches",
    no_match: "desktop.ledger.assets.plan.no_match",
    recorded_zero: "desktop.ledger.assets.plan.recorded_zero",
    election_changed: "desktop.ledger.assets.plan.election_changed",
    projected: "desktop.ledger.assets.plan.projected",
    projected_note: "desktop.ledger.assets.plan.projected_note",
    edition: "desktop.ledger.assets.plan.edition",
    claimable: "desktop.ledger.assets.plan.claimable",
    claimable_none: "desktop.ledger.assets.plan.claimable_none",
    gap: "desktop.ledger.assets.plan.gap",
  },
  timeline: {
    column: {
      sequence: "desktop.ledger.assets.timeline.column.sequence",
      recorded: "desktop.ledger.assets.timeline.column.recorded",
      event: "desktop.ledger.assets.timeline.column.event",
      origin: "desktop.ledger.assets.timeline.column.origin",
      effect: "desktop.ledger.assets.timeline.column.effect",
      changes: "desktop.ledger.assets.timeline.column.changes",
      replaces: "desktop.ledger.assets.timeline.column.replaces",
    },
    time_not_recorded: "desktop.ledger.assets.timeline.time_not_recorded",
    not_in_calculation: "desktop.ledger.assets.timeline.not_in_calculation",
    change: "desktop.ledger.assets.timeline.change",
    change_added: "desktop.ledger.assets.timeline.change_added",
    change_cleared: "desktop.ledger.assets.timeline.change_cleared",
  },
  write: {
    reused: "desktop.ledger.assets.write.reused",
    incomplete: "desktop.ledger.assets.write.incomplete",
    conflict: "desktop.ledger.assets.write.conflict",
    dispose_note: "desktop.ledger.assets.write.dispose_note",
  },
  year: "desktop.ledger.assets.year",
} as const;

const OTHER = "other";

const STATE = {
  claimed: "desktop.ledger.assets.state.claimed",
  missing: "desktop.ledger.assets.state.missing",
  partial: "desktop.ledger.assets.state.partial",
  incomplete: "desktop.ledger.assets.state.incomplete",
  forecast: "desktop.ledger.assets.state.forecast",
  [OTHER]: "desktop.ledger.assets.state.other",
} as const;

/** The glyph a year's state is drawn with; the word sits in its tooltip and
 * accessible name, and colour never carries it alone. */
export const STATE_ICON: Record<keyof typeof STATE, IconName> = {
  claimed: "check",
  missing: "alert",
  partial: "pending",
  incomplete: "unknown",
  forecast: "clock",
  other: "info",
};

const ABSENT = {
  free_method: "desktop.ledger.assets.absent.free_method",
  opening_history_unknown:
    "desktop.ledger.assets.absent.opening_history_unknown",
  not_computed: "desktop.ledger.assets.absent.not_computed",
  [OTHER]: "desktop.ledger.assets.absent.other",
} as const;

const FINDING = {
  claim_stale: "desktop.ledger.assets.finding.claim_stale",
  claim_conflict: "desktop.ledger.assets.finding.claim_conflict",
  opening_history_missing:
    "desktop.ledger.assets.finding.opening_history_missing",
  [OTHER]: "desktop.ledger.assets.finding.other",
} as const;

const EVENT = {
  element_added: "desktop.ledger.assets.event.element_added",
  correction_added: "desktop.ledger.assets.event.correction_added",
  description_added: "desktop.ledger.assets.event.description_added",
  claim_recorded: "desktop.ledger.assets.event.claim_recorded",
  baja_recorded: "desktop.ledger.assets.event.baja_recorded",
  [OTHER]: "desktop.ledger.assets.event.other",
} as const;

const ORIGIN = {
  person: "desktop.ledger.assets.origin.person",
  import: "desktop.ledger.assets.origin.import",
  system: "desktop.ledger.assets.origin.system",
  [OTHER]: "desktop.ledger.assets.origin.other",
} as const;

const FIELD = {
  name: "desktop.ledger.assets.field.name",
  serial: "desktop.ledger.assets.field.serial",
  kind: "desktop.ledger.assets.field.kind",
  method: "desktop.ledger.assets.field.method",
  basis: "desktop.ledger.assets.field.basis",
  in_service_date: "desktop.ledger.assets.field.in_service_date",
  residual_value: "desktop.ledger.assets.field.residual_value",
  amount: "desktop.ledger.assets.field.amount",
  baja_date: "desktop.ledger.assets.field.baja_date",
  baja_reason: "desktop.ledger.assets.field.baja_reason",
  // A claim's span is worded by the claim form's own labels.
  from: "desktop.ledger.assets.from",
  until: "desktop.ledger.assets.until",
  [OTHER]: "desktop.ledger.assets.field.other",
} as const;

const COUNT = {
  missing: "desktop.ledger.assets.count.missing",
  incomplete: "desktop.ledger.assets.count.incomplete",
  conflict: "desktop.ledger.assets.count.conflict",
  stale: "desktop.ledger.assets.count.stale",
} as const satisfies Record<keyof AssetCounts, string>;

/** The glyph each kind of count is drawn with. */
export const COUNT_ICON: Record<keyof AssetCounts, IconName> = {
  missing: "alert",
  incomplete: "unknown",
  conflict: "refused",
  stale: "pending",
};

/** The kinds of count a list row can carry, in the order they are shown. */
export const COUNT_KINDS = Object.keys(COUNT) as (keyof AssetCounts)[];

const known = <Table extends Record<string, string>>(
  table: Table,
  token: string,
): Table[keyof Table] =>
  (Object.hasOwn(table, token)
    ? table[token]
    : table[OTHER]) as Table[keyof Table];

/** The token of a state the glyph table knows, else "other". */
export const stateOf = (token: string): keyof typeof STATE =>
  (Object.hasOwn(STATE, token) ? token : OTHER) as keyof typeof STATE;

export const stateWord = (t: Translate, token: string) =>
  t(known(STATE, token));
export const absentWord = (t: Translate, token: string) =>
  t(known(ABSENT, token));
export const findingWord = (t: Translate, token: string) =>
  t(known(FINDING, token));
export const eventWord = (t: Translate, token: string) =>
  t(known(EVENT, token));
export const originWord = (t: Translate, token: string) =>
  t(known(ORIGIN, token));
export const fieldWord = (t: Translate, token: string) =>
  t(known(FIELD, token));

/** What a count of `kind` says in a tooltip or an accessible name. */
export const countWord = (
  t: Translate,
  kind: keyof AssetCounts,
  count: number,
) => t(COUNT[kind], { count });
