// The words the Assets tab shares. Its own labels are chrome under
// the desktop.ledger.assets family. Every word for something the backend states comes
// from the canonical catalogue, by the backend's own token: the members of its
// enums are worded under `ledger.actividad_asset.<family>.<token>`, and a
// refusal or an absence arrives as a catalogue key with the facts that fill it
// in. A token or key the catalogue has no word for reads as a generic word,
// never as the raw token. Nothing here decides anything.

import type { IconName } from "@/components/ui/icon";
import type { Translate } from "../../../shell/strings";
import type {
  AssetCounts,
  ListDisposal,
  ReasonFact,
} from "../../../shell/ledgerSetup";
import { formatDay } from "../../../shared/dateFormats";
import { formatAmount, formatPercent } from "../../../shared/numbers";

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
    baja_reason: "desktop.ledger.assets.detail.baja_reason",
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
    serial_missing: "desktop.ledger.assets.list.serial_missing",
    column: {
      name: "desktop.ledger.assets.list.column.name",
      serial: "desktop.ledger.assets.list.column.serial",
      kind: "desktop.ledger.assets.list.column.kind",
      method: "desktop.ledger.assets.list.column.method",
      in_service: "desktop.ledger.assets.list.column.in_service",
      state: "desktop.ledger.assets.list.column.state",
      basis: "desktop.ledger.assets.list.column.basis",
      accumulated: "desktop.ledger.assets.list.column.accumulated",
      pending: "desktop.ledger.assets.list.column.pending",
    },
  },
  plan: {
    column: {
      year: "desktop.ledger.assets.plan.column.year",
      status: "desktop.ledger.assets.plan.column.status",
      rate: "desktop.ledger.assets.plan.column.rate",
      planned: "desktop.ledger.assets.plan.column.planned",
      claimed: "desktop.ledger.assets.plan.column.claimed",
      days: "desktop.ledger.assets.plan.column.days",
      minimum: "desktop.ledger.assets.plan.column.minimum",
      minimum_note: "desktop.ledger.assets.plan.column.minimum_note",
      replaced_by: "desktop.ledger.assets.plan.column.replaced_by",
      period: "desktop.ledger.assets.plan.column.period",
    },
    claims: "desktop.ledger.assets.plan.claims",
    in_effect: "desktop.ledger.assets.plan.in_effect",
    replaced: "desktop.ledger.assets.plan.replaced",
    recorded_zero: "desktop.ledger.assets.plan.recorded_zero",
    matches: "desktop.ledger.assets.plan.matches",
    no_match: "desktop.ledger.assets.plan.no_match",
    election_changed: "desktop.ledger.assets.plan.election_changed",
    projected_note: "desktop.ledger.assets.plan.projected_note",
    projected_summary: "desktop.ledger.assets.plan.projected_summary",
    from_date: "desktop.ledger.assets.plan.from_date",
    rate_missing: "desktop.ledger.assets.plan.rate_missing",
    planned_missing: "desktop.ledger.assets.plan.planned_missing",
    days_missing: "desktop.ledger.assets.plan.days_missing",
    minimum_missing: "desktop.ledger.assets.plan.minimum_missing",
    correct_this: "desktop.ledger.assets.plan.correct_this",
    stale_fix: "desktop.ledger.assets.plan.stale_fix",
    baja: "desktop.ledger.assets.plan.baja",
    edition: "desktop.ledger.assets.plan.edition",
    claimable: "desktop.ledger.assets.plan.claimable",
    claimable_none: "desktop.ledger.assets.plan.claimable_none",
    gap: "desktop.ledger.assets.plan.gap",
    limits: {
      title: "desktop.ledger.assets.plan.limits.title",
      maximum_coefficient:
        "desktop.ledger.assets.plan.limits.maximum_coefficient",
      minimum_coefficient:
        "desktop.ledger.assets.plan.limits.minimum_coefficient",
      maximum_period: "desktop.ledger.assets.plan.limits.maximum_period",
      period_years: "desktop.ledger.assets.plan.limits.period_years",
      ends_on: "desktop.ledger.assets.plan.limits.ends_on",
      citations: "desktop.ledger.assets.plan.limits.citations",
      citations_partial: "desktop.ledger.assets.plan.limits.citations_partial",
    },
  },
  timeline: {
    column: {
      recorded: "desktop.ledger.assets.timeline.column.recorded",
      event: "desktop.ledger.assets.timeline.column.event",
      effect: "desktop.ledger.assets.timeline.column.effect",
      changes: "desktop.ledger.assets.timeline.column.changes",
    },
    time_not_recorded: "desktop.ledger.assets.timeline.time_not_recorded",
    not_in_calculation: "desktop.ledger.assets.timeline.not_in_calculation",
    used_by: "desktop.ledger.assets.timeline.used_by",
    used_by_one: "desktop.ledger.assets.timeline.used_by_one",
    claim_span: "desktop.ledger.assets.timeline.claim_span",
    effect_missing: "desktop.ledger.assets.timeline.effect_missing",
    no_changes: "desktop.ledger.assets.timeline.no_changes",
    value_changed: "desktop.ledger.assets.timeline.value_changed",
    change_added: "desktop.ledger.assets.timeline.change_added",
    change_cleared: "desktop.ledger.assets.timeline.change_cleared",
  },
  write: {
    reused: "desktop.ledger.assets.write.reused",
    incomplete: "desktop.ledger.assets.write.incomplete",
    refused: "desktop.ledger.assets.refused",
    fill_in: "desktop.ledger.assets.write.fill_in",
  },
  baja: {
    preview: "desktop.ledger.assets.baja.preview",
    figures: "desktop.ledger.assets.baja.figures",
    acquisition_value: "desktop.ledger.assets.baja.acquisition_value",
    deducted: "desktop.ledger.assets.baja.deducted",
    minimum: "tui.ledger.activity_asset.plan_minimum",
    reduction: "desktop.ledger.assets.baja.reduction",
    excess: "desktop.ledger.assets.baja.excess",
    net_value: "desktop.ledger.assets.baja.net_value",
    transmission_value: "desktop.ledger.assets.baja.transmission_value",
    result: "desktop.ledger.assets.baja.result",
    route_changed: "desktop.ledger.assets.baja.route_changed",
    findings: "desktop.ledger.assets.baja.findings",
    effect_missing: "desktop.ledger.assets.baja.effect_missing",
  },
  unrecognised: "desktop.ledger.assets.unrecognised",
  not_known: "desktop.ledger.assets.not_known",
  mark: {
    nothing_recorded: "desktop.ledger.assets.mark.nothing_recorded",
    not_applicable: "desktop.ledger.assets.mark.not_applicable",
  },
  opening_unknown: "desktop.ledger.assets.opening_unknown",
  field_other: "desktop.ledger.assets.field.other",
  handoff: {
    partial: {
      one: "desktop.ledger.assets.handoff_partial_one",
      other: "desktop.ledger.assets.handoff_partial",
    },
    unnamed: {
      one: "desktop.ledger.assets.handoff_gap_unnamed_one",
      other: "desktop.ledger.assets.handoff_gap_unnamed",
    },
  },
  year: "desktop.ledger.assets.year",
  year_estimated: "desktop.ledger.assets.year_estimated",
  year_estimated_note: "desktop.ledger.assets.year_estimated_note",
} as const;

/** The catalogue families the tab words by the backend's token. Each is the
 * head of the keys the generated strings carry for one of its enums. */
export const ASSET_FAMILY = {
  acquired_condition: "ledger.actividad_asset.acquired_condition.",
  acquisition_shape: "ledger.actividad_asset.acquisition_shape.",
  asset_kind: "ledger.actividad_asset.asset_kind.",
  basis_stage: "ledger.actividad_asset.basis_stage.",
  claim_state: "ledger.actividad_asset.claim_state.",
  declared_activity: "ledger.actividad_asset.declared_activity.",
  digit_order: "ledger.actividad_asset.digit_order.",
  disposal_finding: "ledger.actividad_asset.disposal_finding.",
  disposal_reason: "ledger.actividad_asset.disposal_reason.",
  document_kind: "ledger.actividad_asset.document_kind.",
  electric_propulsion: "ledger.actividad_asset.electric_propulsion.",
  event_kind: "ledger.actividad_asset.event_kind.",
  field: "ledger.actividad_asset.field.",
  flag: "ledger.actividad_asset.flag.",
  method: "ledger.actividad_asset.method.",
  non_deductible_iva_state: "ledger.actividad_asset.non_deductible_iva_state.",
  not_table_bound: "ledger.actividad_asset.not_table_bound.",
  opening_history_status: "ledger.actividad_asset.opening_history_status.",
  original_price_determination:
    "ledger.actividad_asset.original_price_determination.",
  ownership_mode: "ledger.actividad_asset.ownership_mode.",
  plan_absence: "ledger.actividad_asset.plan_absence.",
  plan_advisory: "ledger.actividad_asset.plan_advisory.",
  plan_approval_kind: "ledger.actividad_asset.plan_approval_kind.",
  prior_free_depreciation_regime:
    "ledger.actividad_asset.prior_free_depreciation_regime.",
  renewable_documentation_kind:
    "ledger.actividad_asset.renewable_documentation_kind.",
  renewable_installation_purpose:
    "ledger.actividad_asset.renewable_installation_purpose.",
  regime: "ledger.actividad_asset.regime.",
  register_state: "ledger.actividad_asset.register_state.",
  stale_reason: "ledger.actividad_asset.stale_reason.",
  vehicle_category: "ledger.actividad_asset.vehicle_category.",
  vehicle_listed_use: "ledger.actividad_asset.vehicle_listed_use.",
  vehicle_private_use: "ledger.actividad_asset.vehicle_private_use.",
} as const;

/** The family every reason key the backend serves belongs to. */
export const ASSET_REASON_FAMILY = "ledger.actividad_asset.errors.";

export type AssetFamily = keyof typeof ASSET_FAMILY;

/** A value worded by the catalogue key the backend served with it, else the
 * value as stated. A key outside the families, or one the generated strings
 * lack, is never drawn raw: the value stands. */
export function keyedText(
  t: Translate,
  key: string | null | undefined,
  value: string,
): string {
  if (
    key === null ||
    key === undefined ||
    !Object.values(ASSET_FAMILY).some((family) => key.startsWith(family))
  )
    return value;
  const said = t(key);
  return said === key ? value : said;
}

/** The word for a token of a family, else the generic word: never the raw
 * token or key. */
export function tokenWord(
  t: Translate,
  family: AssetFamily,
  token: string | null,
): string {
  if (token === null) return t(ASSET_KEYS.unrecognised);
  const key = `${ASSET_FAMILY[family]}${token}`;
  const said = t(key);
  return said === key ? t(ASSET_KEYS.unrecognised) : said;
}

/** A fact as the person reads it, drawn by the kind the backend served with
 * it: a date in the language of the interface, an amount to the cent, a
 * percent as a percentage. A count, such as a tax year, and a text stand as
 * they are, so a year never gets a thousands separator. */
export function factText(t: Translate, fact: ReasonFact): string {
  const locale = t.locale ?? "en";
  switch (fact.kind) {
    case "date":
      return formatDay(locale, fact.value);
    case "amount":
      return formatAmount(locale, fact.value);
    case "percent":
      return formatPercent(locale, fact.value, { unit: "fraction" });
    case "count":
    case "text":
      return fact.value;
  }
}

/** Whether a key is one the backend words a reason with: a refusal's own
 * family, or one of the token families, such as a finding. */
const inReasonFamilies = (key: string) =>
  key.startsWith(ASSET_REASON_FAMILY) ||
  Object.values(ASSET_FAMILY).some((family) => key.startsWith(family));

/** Facts a refusal carries for a screen to act on, never to say: the
 * recorded dotaciones an overlap meets. */
const NOT_DRAWN_FACTS: ReadonlySet<string> = new Set(["conflicting_claim_ids"]);

/**
 * A reason in words: the catalogue sentence of the key the backend gave,
 * filled in with the facts it gave. Null where the sentence cannot be said
 * whole: no key, a key outside the reason families or that the generated
 * strings lack, or a fact the sentence needs that was not given. The caller
 * then shows its own generic word.
 */
export function reasonText(
  t: Translate,
  key: string | null,
  facts: readonly ReasonFact[] = [],
): string | null {
  if (key === null || !inReasonFamilies(key)) return null;
  const said = t(
    key,
    Object.fromEntries(
      facts
        .filter((fact) => !NOT_DRAWN_FACTS.has(fact.key))
        .map((fact) => [fact.key, factText(t, fact)]),
    ),
  );
  return said === key || /\{\w+\}/.test(said) ? null : said;
}

/** A refusal in words: its reason, else the generic refused word. */
export function refusalText(
  t: Translate,
  refusal: {
    code?: string;
    reason_key?: string | null;
    reason_facts?: readonly ReasonFact[];
  } | null,
): string {
  return (
    reasonText(t, refusal?.reason_key ?? null, refusal?.reason_facts ?? []) ??
    t(ASSET_KEYS.write.refused)
  );
}

/** The glyph a year's claim state is drawn with; the word sits in its tooltip
 * and accessible name, and colour never carries it alone. */
const STATE_ICON: Record<string, IconName> = {
  edition_unavailable: "unknown",
  claimed: "check",
  superseded: "check",
  missing: "alert",
  partial: "pending",
  not_due: "clock",
};
export const stateIcon = (token: string): IconName =>
  Object.hasOwn(STATE_ICON, token) ? STATE_ICON[token]! : "info";

/** The word of the fields the tab names itself, by the path the backend names
 * them with. A path this table does not know reads as the generic word,
 * never raw. The fields of a change on the timeline are not worded here: the
 * backend serves the catalogue key of each. */
const FIELD: Record<string, string> = {
  name: "desktop.ledger.assets.field.name",
  serial_number: "desktop.ledger.assets.field.serial",
  asset_kind: "desktop.ledger.assets.field.kind",
  "opening_history.accumulated_amount":
    "desktop.ledger.assets.field.opening_amount",
  in_service_date: "desktop.ledger.assets.field.in_service_date",
  "disposal.disposal_date": "desktop.ledger.assets.field.disposal_date",
  "disposal.transmission_costs":
    "desktop.ledger.assets.field.transmission_costs",
  "basis.basis_amount": "desktop.ledger.assets.field.basis",
  "amortization.method": "desktop.ledger.assets.field.method",
  "amortization.authority_class_key": "desktop.ledger.assets.field.class",
};
/** A field path without the index of a repeated row. */
export const unindexed = (path: string) => path.replace(/\[\d+\]/g, "[]");

export const fieldWord = (t: Translate, path: string) =>
  Object.hasOwn(FIELD, unindexed(path))
    ? t(FIELD[unindexed(path)]!)
    : t(ASSET_KEYS.field_other);

/** The word of a changed fact on the timeline: the catalogue word of the key
 * the backend served for it. Without a key, or where the catalogue has no
 * word for it, the generic word. */
export const changeFieldWord = (t: Translate, key: string | null) =>
  wordOfKey(t, key) ?? t(ASSET_KEYS.field_other);

/** The baja an element records, said by its day and its reason. */
export function bajaText(
  t: Translate,
  locale: string,
  disposal: ListDisposal,
): string {
  return t(ASSET_KEYS.plan.baja, {
    date: formatDay(locale, disposal.disposal_date),
    reason:
      wordOfKey(t, disposal.reason_key) ??
      tokenWord(t, "disposal_reason", disposal.reason),
  });
}

/** What to do when the amortization already deducted is not known: where to
 * enter it, by the word of that field. */
export const openingRemedy = (t: Translate, fieldKey: string | null) => {
  const field = wordOfKey(t, fieldKey);
  return field === null ? null : t(ASSET_KEYS.opening_unknown, { field });
};

/** The word the catalogue has for a key the backend served with a value, or
 * null where the key is outside the register's families or has no word. */
export function wordOfKey(
  t: Translate,
  key: string | null | undefined,
): string | null {
  if (
    key === null ||
    key === undefined ||
    !Object.values(ASSET_FAMILY).some((family) => key.startsWith(family))
  )
    return null;
  const said = t(key);
  return said === key ? null : said;
}

const COUNT = {
  missing: "desktop.ledger.assets.count.missing",
  incomplete: "desktop.ledger.assets.count.incomplete",
  conflict: "desktop.ledger.assets.count.conflict",
  unsupported: "desktop.ledger.assets.count.unsupported",
  without_tables: "desktop.ledger.assets.count.without_tables",
  stale: "desktop.ledger.assets.count.stale",
} as const satisfies Record<keyof AssetCounts, string>;

/** The glyph each kind of count is drawn with; no two share one. */
export const COUNT_ICON: Record<keyof AssetCounts, IconName> = {
  missing: "alert",
  incomplete: "unknown",
  conflict: "refused",
  unsupported: "unplug",
  without_tables: "book",
  stale: "reset",
};

/** The kinds of count a list row can carry, in the order they are shown. */
export const COUNT_KINDS = Object.keys(COUNT) as (keyof AssetCounts)[];

/** What a count of `kind` says in a tooltip or an accessible name. */
export const countWord = (
  t: Translate,
  kind: keyof AssetCounts,
  count: number,
) => t(COUNT[kind], { count });

/** The sentence of a count, in its singular form for one and its plural form
 * otherwise, filled in with the count. */
export const countSentence = (
  t: Translate,
  words: { one: string; other: string },
  count: number,
) => t(count === 1 ? words.one : words.other, { count });
