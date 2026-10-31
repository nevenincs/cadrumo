// The fields of each act's form, and how typed text becomes the values of a
// request. The tab declares which controls it draws and the labels they carry;
// what each may hold comes from the backend: the acquisition shapes, methods
// and table classes the registry admits for the element's kind and year, the
// facts each method takes, the purchases the ledger offers, and the facts the
// register already states. The form decides nothing about them, and the
// backend judges what is sent.

import {
  copyDecimal,
  copyPercent,
  parseDecimal,
  parseIsoDate,
  parseLine,
  parsePercent,
  QUANTITY_RULE,
  TAX_AMOUNT_RULE,
  type GrammarRefusal,
  type Parsed,
} from "../../../shell/ledgerGrammar";
import type {
  ActivityAssetRevision,
  AssetListRow,
  DescriptorFacts,
  FormOptions,
  MethodFact,
  PlanClaim,
  PlanRow,
} from "../../../shell/ledgerSetup";
import type { PublicDecimal } from "../../../shell/ledger";
import { ASSET_FAMILY, type AssetFamily } from "./assetsWords";

// ---- The tab's forms -------------------------------------------------------

export type FormKind =
  "element" | "descriptor" | "correction" | "claim" | "baja";

/** The kinds of field set a form draws: the acts, and the change of a baja
 * already recorded. */
export type FieldKind = FormKind | "baja_change";

/** `candidate` is a choice among the purchases the backend offers, picked
 * and never typed; `share` is a percentage typed, a fraction sent;
 * `quantity` is a plain number such as hours or square metres. */
export type FormControl =
  | "text"
  | "date"
  | "amount"
  | "share"
  | "quantity"
  | "whole"
  | "choice"
  | "flag"
  | "candidate";

/** What a form states, by field key: text, a decimal, a whole number, a
 * choice's token, a flag, or null where nothing was stated. */
export type FormValue = string | number | boolean | PublicDecimal | null;
export type FormValues = Record<string, FormValue>;

/** One choice of a field: the backend's token, worded by the family the
 * token belongs to, by the catalogue key `word`, or by the text the backend
 * serves with it (a table class's official name). */
export type FieldChoice = {
  token: string;
  family: AssetFamily | null;
  label?: string;
  word?: string;
};

export type FormField = {
  key: string;
  label_key: string;
  control: FormControl;
  required: boolean;
  choices: FieldChoice[];
  /** What the record states now, as text, where the form starts from it. */
  current?: string | null;
  /** The word that says how to write the value. */
  hint_key?: string | null;
};

/** The text typed into each field of a form, by field key. */
export type FormDraft = Record<string, string>;

const field = (
  control: FormControl,
  key: string,
  label: string,
  required = false,
  choices: FieldChoice[] = [],
): FormField => ({ key, label_key: label, control, required, choices });
const text = (key: string, label: string, required = false) =>
  field("text", key, label, required);
const date = (key: string, label: string, required = false) =>
  field("date", key, label, required);
const amount = (key: string, label: string, required = false) =>
  field("amount", key, label, required);
const share = (key: string, label: string, required = false) =>
  field("share", key, label, required);
const quantity = (key: string, label: string, required = false) =>
  field("quantity", key, label, required);
const whole = (key: string, label: string, required = false) =>
  field("whole", key, label, required);
const flag = (key: string, label: string, required = false) =>
  field("flag", key, label, required);
const choice = (
  key: string,
  label: string,
  choices: FieldChoice[],
  required = false,
) => field("choice", key, label, required, choices);

const decimalOf = (found: { decimal: string } | null | undefined) =>
  found?.decimal ?? null;

// ---- What the backend serves with the options -----------------------------

/** What the registry admits for one kind and year, with the shapes, the
 * activities and the facts of each offered method. */
/** The facts the options serve for a method; none for one they do not list. */
export const factsOf = (
  options: FormOptions | null,
  method: string,
): readonly MethodFact[] =>
  options?.method_facts.find((found) => found.method === method)?.facts ?? [];

/** The label of each fact an election can state, by its path from the
 * election. A fact with no label here cannot be drawn. */
const FACT_LABEL: Record<string, string> = {
  authority_class_key: "desktop.ledger.assets.field.class",
  linear_coefficient: "desktop.ledger.assets.field.coefficient",
  shift_hours_per_day: "desktop.ledger.assets.field.shift_hours",
  sum_of_digits_period_years: "desktop.ledger.assets.field.digit_period",
  digit_order: "desktop.ledger.assets.field.digit_order",
  "used_original_price.determination":
    "desktop.ledger.assets.field.used_determination",
  "used_original_price.original_price":
    "desktop.ledger.assets.field.used_price",
  "used_original_price.evidence_reference":
    "desktop.ledger.assets.field.used_evidence",
  "small_enterprise.evidence_reference":
    "desktop.ledger.assets.field.small_evidence",
  "small_enterprise.made_available_on":
    "desktop.ledger.assets.field.small_available_on",
  "small_enterprise.prior_period_net_turnover":
    "desktop.ledger.assets.field.small_turnover",
  "useful_life.ends_on": "desktop.ledger.assets.field.useful_life_ends_on",
  "useful_life.evidence_reference":
    "desktop.ledger.assets.field.useful_life_evidence",
  "low_value.election_reference":
    "desktop.ledger.assets.field.low_value_election",
  "low_value.new_material_evidence_reference":
    "desktop.ledger.assets.field.low_value_evidence",
  research_development_evidence_reference:
    "desktop.ledger.assets.field.research_evidence",
  "charging_infrastructure.technical_documentation_reference":
    "desktop.ledger.assets.field.charging_documentation",
  "charging_infrastructure.installation_certificate_reference":
    "desktop.ledger.assets.field.charging_certificate",
  "renewable_self_consumption.purpose":
    "desktop.ledger.assets.field.renewable_purpose",
  "renewable_self_consumption.documentation_kind":
    "desktop.ledger.assets.field.renewable_documentation_kind",
  "renewable_self_consumption.documentation_reference":
    "desktop.ledger.assets.field.renewable_documentation",
  "renewable_self_consumption.made_available_on":
    "desktop.ledger.assets.field.renewable_available_on",
  "renewable_self_consumption.replaces_fossil_installation":
    "desktop.ledger.assets.field.renewable_replaces_fossil",
  "renewable_self_consumption.required_by_building_code":
    "desktop.ledger.assets.field.renewable_building_code",
};

/** The paths of the facts of an election that have no word yet. */
export const unlabelledFacts = (
  options: FormOptions | null,
): readonly string[] => [
  ...new Set(
    (options?.method_facts ?? []).flatMap((entry) =>
      entry.facts
        .filter(
          (fact) =>
            fact.kind !== "rows" &&
            !Object.hasOwn(FACT_LABEL, fact.path.join(".")),
        )
        .map((fact) => fact.path.join(".")),
    ),
  ),
];

/** Whether the form can state every fact the method requires. */
const methodDrawable = (options: FormOptions | null, method: string) =>
  factsOf(options, method).every(
    (fact) =>
      !fact.required ||
      (fact.kind !== "rows" && Object.hasOwn(FACT_LABEL, fact.path.join("."))),
  );

const ELECTION = "amortization.";
/** The form key of a fact of the election: the path the backend names it by. */
export const factKey = (path: readonly string[]) =>
  `${ELECTION}${path.join(".")}`;

/** The shape of an element bought through a purchase the ledger holds. */
const PURCHASE = "primary_purchase";
/** The shape of an element bought before the ledger began. */
export const OUTSIDE = "acquired_outside_ledger";
/** The later ledger payment an element bought outside the ledger owns, and
 * what that payment is. */
export const FURTHER_PURCHASE = "further_purchase";
export const FURTHER_SHAPE = "further_shape";
const SHAPE_WORD: Record<string, string> = {
  [PURCHASE]: "desktop.ledger.assets.field.shape_ledger",
  [OUTSIDE]: "desktop.ledger.assets.field.shape_outside",
};

// ---- Typed text into values ---------------------------------------------------

/** Each field starting from what the record states now. */
export const draftOf = (fields: readonly FormField[]): FormDraft =>
  Object.fromEntries(fields.map((found) => [found.key, found.current ?? ""]));

const empty: Parsed<FormValue> = { kind: "empty" };
const value = (found: FormValue): Parsed<FormValue> => ({
  kind: "value",
  value: found,
});

/** One field's text as the value its control takes. Nothing typed is empty;
 * a refusal says why the text cannot be read. */
export function parseField(found: FormField, raw: string): Parsed<FormValue> {
  switch (found.control) {
    case "text":
      return parseLine(raw, 200);
    case "date":
      return parseIsoDate(raw);
    case "amount": {
      const parsed = parseDecimal(raw, TAX_AMOUNT_RULE);
      return parsed.kind === "value"
        ? value({ decimal: parsed.value })
        : parsed;
    }
    case "quantity": {
      const parsed = parseDecimal(raw, QUANTITY_RULE);
      return parsed.kind === "value"
        ? value({ decimal: parsed.value })
        : parsed;
    }
    case "share": {
      const parsed = parsePercent(raw);
      return parsed.kind === "value"
        ? value({ decimal: parsed.value })
        : parsed;
    }
    case "whole": {
      const typed = raw.trim();
      if (typed === "") return { kind: "empty" };
      return /^\d{1,9}$/.test(typed)
        ? value(Number(typed))
        : { kind: "refused", refusal: { key: "not_a_number", raw } };
    }
    case "flag":
      return raw === "yes" ? value(true) : raw === "no" ? value(false) : empty;
    case "choice":
    case "candidate":
      return raw === "" ? empty : value(raw);
  }
}

export type Answered = {
  values: FormValues;
  problems: Record<string, GrammarRefusal>;
  /** Fields emptied that the record cannot do without. */
  cleared: string[];
};

/**
 * What a form's text says. A full form states every field, null where
 * nothing was typed, so the backend names what is missing. Given `initial`,
 * only the fields changed from it are stated: a field emptied is stated as
 * null, which clears it, and one the record cannot do without is named in
 * `cleared` and not stated.
 */
export function answer(
  fields: readonly FormField[],
  draft: FormDraft,
  initial: FormDraft | null,
): Answered {
  const values: FormValues = {};
  const problems: Record<string, GrammarRefusal> = {};
  const cleared: string[] = [];
  for (const found of fields) {
    const raw = draft[found.key] ?? "";
    if (initial !== null && raw === (initial[found.key] ?? "")) continue;
    const parsed = parseField(found, raw);
    if (parsed.kind === "refused") problems[found.key] = parsed.refusal;
    else if (parsed.kind === "value") values[found.key] = parsed.value;
    else if (initial === null) values[found.key] = null;
    else if (found.required) cleared.push(found.key);
    else values[found.key] = null;
  }
  return { values, problems, cleared };
}

// ---- The fields of an act ------------------------------------------------------

/** What the form for an act is drawn from. */
export type FieldContext = {
  kind: FieldKind;
  /** The element acted on, as the register lists it now. */
  row: AssetListRow | null;
  /** The element's descriptor as it stands, for a description. */
  descriptor: DescriptorFacts | null;
  /** The revision a correction supersedes, as the register holds it. */
  revision: ActivityAssetRevision | null;
  /** The tokens of a family the backend serves, from the generated words. */
  tokens: (family: AssetFamily) => readonly string[];
  /** What the registry admits for the chosen kind and year; null until read. */
  options: FormOptions | null;
};

const tokenChoices = (
  context: FieldContext,
  family: AssetFamily,
): FieldChoice[] =>
  context.tokens(family).map((token): FieldChoice => ({ token, family }));

const isFamily = (name: string | null): name is AssetFamily =>
  name !== null && Object.hasOwn(ASSET_FAMILY, name);

/** The choices a fact of the election offers, worded by its token family; a
 * family the shell has no words for reads as the generic word. */
const factChoices = (fact: MethodFact): FieldChoice[] =>
  fact.tokens.map((token): FieldChoice => ({
    token,
    family: isFamily(fact.token_family) ? fact.token_family : null,
  }));

const fromOptions = (options: FormOptions | null) => ({
  methods: (options?.methods ?? []).map((token): FieldChoice => ({
    token,
    family: "method",
  })),
  classes: (options?.table_groups ?? []).map((group): FieldChoice => ({
    token: group.class_key,
    family: null,
    label: group.class_label,
  })),
  shapes: (options?.acquisition_shapes ?? []).map((token): FieldChoice => ({
    token,
    family: "acquisition_shape",
    word: SHAPE_WORD[token],
  })),
  activities: (options?.declared_activities ?? []).map(
    (token): FieldChoice => ({ token, family: "declared_activity" }),
  ),
});

/** The revision's own facts a form field starts from, by the path in the
 * revision. A fact of the election has no entry: its key is its path. */
export const REVISION_PATHS: Record<string, readonly string[]> = {
  asset_kind: ["asset_kind"],
  acquisition_shape: ["acquisition_shape"],
  acquisition_reference: ["acquisition", "invoice_evidence_id"],
  declared_acquisition_date: ["declared_acquisition_date"],
  declared_activity: ["declared_activity"],
  in_service_date: ["in_service_date"],
  acquired_condition: ["acquired_condition"],
  building_construction_date: ["building_construction_date"],
  residual_value: ["residual_value"],
  basis_stage: ["basis", "stage"],
  basis_amount: ["basis", "basis_amount"],
  non_deductible_iva: ["basis", "non_deductible_iva"],
  business_use_share: ["basis", "business_use_share"],
  prior_allocation_provenance: ["basis", "prior_allocation_provenance"],
  construction_cost: ["basis", "construction_cost"],
  land_cost: ["basis", "land_cost"],
  ownership_mode: ["basis", "ownership_mode"],
  ownership_share: ["basis", "ownership_share"],
  office_area: ["basis", "office_area"],
  total_area: ["basis", "total_area"],
  opening_status: ["opening_history", "status"],
  opening_amount: ["opening_history", "accumulated_amount"],
  opening_through: ["opening_history", "covered_through_tax_year"],
  opening_method: ["opening_history", "amortization_method"],
  method: ["amortization", "method"],
  vehicle_category: ["vehicle_affectation", "category"],
  vehicle_private_use: ["vehicle_affectation", "private_use"],
  vehicle_listed_use: ["vehicle_affectation", "listed_use"],
  vehicle_in_books: ["vehicle_affectation", "recorded_in_activity_books"],
  vehicle_evidence: ["vehicle_affectation", "evidence_reference"],
  vehicle_propulsion: ["vehicle_affectation", "electric_propulsion"],
};

/** Where in the revision a field's value goes: its own path, or for a fact of
 * the election the path the key names. Null for a field that is no fact. */
export function revisionPathOf(key: string): readonly string[] | null {
  if (Object.hasOwn(REVISION_PATHS, key)) return REVISION_PATHS[key]!;
  return key.startsWith(ELECTION) ? key.split(".") : null;
}

/** The form key a fact named by the backend's path is stated under. */
export function formKeyOf(path: string): string {
  const found = Object.entries(REVISION_PATHS).find(
    ([, steps]) => steps.join(".") === path,
  );
  return found ? found[0] : path;
}

/** The facts stated as a share: the person writes a percentage. */
const SHARES = new Set(["business_use_share", "ownership_share"]);
const FLAGS = new Set(["vehicle_in_books"]);

/** What the options say of whether a class is charged only on a vehicle
 * declaration: true or false for a class they list, null for any other. */
export const requiresVehicle = (
  options: FormOptions | null,
  classKey: string,
): boolean | null =>
  options?.table_groups.find((found) => found.class_key === classKey)
    ?.requires_vehicle_declaration ?? null;

const kindOf = (
  revision: ActivityAssetRevision,
  options: FormOptions | null,
  path: readonly string[],
) => {
  const method = String(
    (revision.amortization as { method?: unknown } | undefined)?.method ?? "",
  );
  return factsOf(options, method).find(
    (fact) => fact.path.join(".") === path.slice(1).join("."),
  )?.kind;
};

/** What a revision states at a path, as the text a form field starts from. */
function stated(revision: ActivityAssetRevision, path: readonly string[]) {
  let at: unknown = revision;
  for (const step of path) {
    if (typeof at !== "object" || at === null) return null;
    at = (at as Record<string, unknown>)[step];
  }
  if (at === null || at === undefined) return null;
  if (typeof at === "object") return decimalOf(at as { decimal: string });
  return String(at);
}

/** The leaf paths below the election's own facts, as the revision states them. */
function electionLeaves(
  election: unknown,
  prefix: readonly string[] = [],
): (readonly string[])[] {
  if (typeof election !== "object" || election === null) return [];
  return Object.entries(election).flatMap(([name, found]) => {
    const path = [...prefix, name];
    if (found === null || found === undefined) return [];
    if (
      typeof found === "object" &&
      !Array.isArray(found) &&
      !("decimal" in found)
    )
      return electionLeaves(found, path);
    return [path];
  });
}

/** The text a correction's fields start from: what the revision it supersedes
 * states. */
export function revisionDraft(
  revision: ActivityAssetRevision,
  options: FormOptions | null = null,
): FormDraft {
  const draft: FormDraft = {};
  for (const [key, path] of Object.entries(REVISION_PATHS)) {
    const said = stated(revision, path);
    if (said === null) continue;
    draft[key] = SHARES.has(key)
      ? copyPercent(said)
      : FLAGS.has(key)
        ? said === "true"
          ? "yes"
          : "no"
        : said;
  }
  for (const leaf of electionLeaves(revision.amortization)) {
    const path = ["amortization", ...leaf];
    const key = path.join(".");
    if (key === "amortization.regime" || key === "amortization.method")
      continue;
    const said = stated(revision, path);
    if (said === null) continue;
    const kind = kindOf(revision, options, path);
    draft[key] =
      kind === "share"
        ? copyPercent(said)
        : kind === "flag"
          ? said === "true"
            ? "yes"
            : "no"
          : kind === "decimal"
            ? copyDecimal(said)
            : said;
  }
  return draft;
}

/** The text a change of a baja starts from: the baja the revision records. */
export function disposalDraft(revision: ActivityAssetRevision): FormDraft {
  const found = revision.disposal;
  if (typeof found !== "object" || found === null) return {};
  const baja = found as Record<string, unknown>;
  const said = (name: string) => stated(revision, ["disposal", name]);
  const draft: FormDraft = {};
  for (const [key, name] of [
    ["date", "disposal_date"],
    ["reason", "reason"],
    ["proceeds", "proceeds"],
    ["transmission_costs", "transmission_costs"],
    ["market_value", "market_value"],
    ["prior_free_depreciation_regime", "prior_free_depreciation_regime"],
    ["later_affectation_on", "later_affectation_on"],
  ] as const) {
    const value = baja[name] === undefined ? null : said(name);
    if (value !== null) draft[key] = value;
  }
  return draft;
}

/** The claim's end for display: the last day it covers. */
export const throughOf = (found: {
  covered_until: string;
  covered_through?: string;
}) => found.covered_through ?? found.covered_until;

/** The span a claim form starts from: the claim being replaced or else a
 * span the plan says is still claimable. Its last day is the one the
 * backend served; the person may type another. */
export type ClaimSpan = {
  from: string;
  through: string;
};

export function claimSpans(
  row: PlanRow | null,
  replaced: PlanClaim | null,
): ClaimSpan[] {
  if (replaced !== null)
    return [
      {
        from: replaced.covered_from,
        through: replaced.covered_through,
      },
    ];
  return (row?.claimable_intervals ?? []).map((interval) => ({
    from: interval.covered_from,
    through: interval.covered_through,
  }));
}

/** The fields of a claim: the first and last day of the span, which begin at
 * the span chosen, and the amount where the plan says the year's figure is
 * the person's to elect. */
export function claimFields(
  row: PlanRow | null,
  replaced: PlanClaim | null,
  span: ClaimSpan | null = claimSpans(row, replaced)[0] ?? null,
): FormField[] {
  return [
    {
      ...date("covered_from", "desktop.ledger.assets.from", true),
      current: span?.from ?? null,
    },
    {
      ...date("covered_through", "desktop.ledger.assets.until", true),
      current: span?.through ?? null,
    },
    ...(row?.absence === "free_election"
      ? [
          {
            ...amount("free_amount", "desktop.ledger.assets.free", true),
            current: decimalOf(replaced?.amount),
            hint_key: "desktop.ledger.assets.free_hint",
          },
        ]
      : []),
  ];
}

/** The facts the options say only the condition chosen states: every fact
 * some condition carries, less those of the chosen one. Without options, or
 * with a condition the options do not list, none is judged. */
export const factsOfOtherConditions = (
  options: FormOptions | null,
  condition: string,
): ReadonlySet<string> => {
  const conditions = options?.acquired_conditions ?? [];
  const chosen = conditions.find((found) => found.condition === condition);
  if (chosen === undefined) return new Set();
  return new Set(
    conditions
      .flatMap((found) => found.facts)
      .filter((name) => !chosen.facts.includes(name)),
  );
};

/** How each fact a condition states outside the election is drawn, by the
 * name the options serve it under. A fact of the election is drawn with the
 * method's. */
const CONDITION_FACT: Record<string, () => FormField> = {
  building_construction_date: () =>
    date(
      "building_construction_date",
      "desktop.ledger.assets.field.building_construction_date",
    ),
};

/** The facts of the condition chosen that sit outside the election. */
function conditionFields(
  context: FieldContext,
  condition: string,
): FormField[] {
  const chosen = context.options?.acquired_conditions.find(
    (found) => found.condition === condition,
  );
  return (chosen?.facts ?? []).flatMap((name) =>
    Object.hasOwn(CONDITION_FACT, name) ? [CONDITION_FACT[name]!()] : [],
  );
}

/** The facts of the method chosen, as the options serve them. */
function methodFacts(context: FieldContext, draft: FormDraft): FormField[] {
  const method = draft.method ?? "";
  const { classes } = fromOptions(context.options);
  const said = (key: string) => draft[key] ?? "";
  const elsewhere = factsOfOtherConditions(
    context.options,
    said("acquired_condition"),
  );
  const grouped = (group: string) =>
    Object.entries(draft).some(
      ([key, typed]) => key.startsWith(`${ELECTION}${group}.`) && typed !== "",
    );
  return factsOf(context.options, method).flatMap((fact): FormField[] => {
    const dotted = fact.path.join(".");
    const label = FACT_LABEL[dotted];
    if (label === undefined || fact.kind === "rows") return [];
    // A fact only another condition states is not asked.
    if (elsewhere.has(fact.path[0]!)) return [];
    const required =
      fact.required || (fact.required_with_group && grouped(fact.path[0]!));
    const key = factKey(fact.path);
    switch (fact.kind) {
      case "class":
        return [choice(key, label, classes, required)];
      case "choice":
        return [choice(key, label, factChoices(fact), required)];
      case "flag":
        return [flag(key, label, required)];
      case "date":
        return [date(key, label, required)];
      case "whole":
        return [whole(key, label, required)];
      case "amount":
        return [amount(key, label, required)];
      case "share":
        return [share(key, label, required)];
      case "decimal":
        return [quantity(key, label, required)];
      default:
        return [text(key, label, required)];
    }
  });
}

/** The vehicle declaration of a class the registry says is charged only on
 * one: it is stated, with no question whether it applies. Any other class
 * shows nothing. */
function vehicleFields(context: FieldContext, draft: FormDraft): FormField[] {
  const chosen = draft[factKey(["authority_class_key"])] ?? "";
  if (requiresVehicle(context.options, chosen) !== true) return [];
  return [
    choice(
      "vehicle_category",
      "desktop.ledger.assets.field.vehicle_category",
      tokenChoices(context, "vehicle_category"),
      true,
    ),
    choice(
      "vehicle_private_use",
      "desktop.ledger.assets.field.vehicle_private_use",
      tokenChoices(context, "vehicle_private_use"),
      true,
    ),
    choice(
      "vehicle_listed_use",
      "desktop.ledger.assets.field.vehicle_listed_use",
      tokenChoices(context, "vehicle_listed_use"),
    ),
    flag(
      "vehicle_in_books",
      "desktop.ledger.assets.field.vehicle_in_books",
      true,
    ),
    text(
      "vehicle_evidence",
      "desktop.ledger.assets.field.vehicle_evidence",
      true,
    ),
    choice(
      "vehicle_propulsion",
      "desktop.ledger.assets.field.vehicle_propulsion",
      tokenChoices(context, "electric_propulsion"),
    ),
  ];
}

/** How each fact a basis stage states is drawn. Which facts a stage states
 * is the options' to say; a served fact with no entry here cannot be drawn. */
const BASIS_FACT: Record<string, (context: FieldContext) => FormField> = {
  business_use_share: () =>
    share(
      "business_use_share",
      "desktop.ledger.assets.field.business_use_share",
      true,
    ),
  prior_allocation_provenance: () =>
    text(
      "prior_allocation_provenance",
      "desktop.ledger.assets.field.allocation_provenance",
      true,
    ),
  construction_cost: () =>
    amount(
      "construction_cost",
      "desktop.ledger.assets.field.construction_cost",
      true,
    ),
  land_cost: () =>
    amount("land_cost", "desktop.ledger.assets.field.land_cost", true),
  ownership_mode: (context) =>
    choice(
      "ownership_mode",
      "desktop.ledger.assets.field.ownership_mode",
      tokenChoices(context, "ownership_mode"),
      true,
    ),
  ownership_share: () =>
    share(
      "ownership_share",
      "desktop.ledger.assets.field.ownership_share",
      true,
    ),
  office_area: () =>
    quantity("office_area", "desktop.ledger.assets.field.office_area", true),
  total_area: () =>
    quantity("total_area", "desktop.ledger.assets.field.total_area", true),
};

/** How each fact an opening history states is drawn, by the name the options
 * serve it under; the method is chosen among the methods offered. */
const OPENING_FACT: Record<
  string,
  (methods: readonly FieldChoice[]) => FormField
> = {
  accumulated_amount: () =>
    amount(
      "opening_amount",
      "desktop.ledger.assets.field.opening_amount",
      true,
    ),
  covered_through_tax_year: () => ({
    ...whole("opening_through", "desktop.ledger.assets.field.opening_through"),
    hint_key: "desktop.ledger.form.year_hint",
  }),
  amortization_method: (methods) =>
    choice("opening_method", "desktop.ledger.assets.field.opening_method", [
      ...methods,
    ]),
};

/** The names of the basis and opening facts the options serve that the form
 * has no control for. */
export const undrawableFacts = (options: FormOptions | null): string[] => [
  ...new Set([
    ...(options?.basis_stages ?? [])
      .flatMap((stage) => stage.facts)
      .filter((name) => !Object.hasOwn(BASIS_FACT, name)),
    ...(options?.opening_statuses ?? [])
      .flatMap((status) => status.facts)
      .filter((name) => !Object.hasOwn(OPENING_FACT, name)),
    ...(options?.acquired_conditions ?? [])
      .flatMap((condition) => condition.facts)
      .filter(
        (name) =>
          !Object.hasOwn(CONDITION_FACT, name) &&
          !(options?.method_facts ?? []).some((entry) =>
            entry.facts.some((fact) => fact.path[0] === name),
          ),
      ),
  ]),
];

/** The facts of the basis the stage chosen states, as the options serve them. */
function basisFields(context: FieldContext, stage: string): FormField[] {
  const served =
    context.options?.basis_stages.find((found) => found.stage === stage)
      ?.facts ?? [];
  return served.flatMap((name) =>
    Object.hasOwn(BASIS_FACT, name) ? [BASIS_FACT[name]!(context)] : [],
  );
}

/** The facts of the opening history the status chosen can state. */
function openingFields(
  context: FieldContext,
  status: string,
  methods: readonly FieldChoice[],
): FormField[] {
  const served =
    context.options?.opening_statuses.find((found) => found.status === status)
      ?.facts ?? [];
  return served.flatMap((name) =>
    Object.hasOwn(OPENING_FACT, name) ? [OPENING_FACT[name]!(methods)] : [],
  );
}

/** The facts of the revision an element or a correction states. Which of them
 * are drawn follows what the typed text already says. */
function revisionFields(
  context: FieldContext,
  draft: FormDraft,
  creating: boolean,
): FormField[] {
  const { methods, shapes, activities } = fromOptions(context.options);
  // A method whose facts the form cannot state is not offered, since the
  // backend would only refuse it as incomplete. A correction keeps offering
  // the method the element already has.
  const current = context.revision?.amortization;
  const kept =
    typeof current === "object" && current !== null
      ? String((current as { method?: unknown }).method)
      : null;
  const offered = methods.filter((found) =>
    methodDrawable(context.options, found.token),
  );
  if (kept !== null && !offered.some((found) => found.token === kept))
    offered.push({ token: kept, family: "method" });
  const said = (key: string) => draft[key] ?? "";
  const outside = said("acquisition_shape") === OUTSIDE;
  return [
    ...(creating
      ? [
          choice(
            "asset_kind",
            "desktop.ledger.assets.field.kind",
            tokenChoices(context, "asset_kind"),
            true,
          ),
          text("name", "desktop.ledger.assets.field.name", true),
          text("serial_number", "desktop.ledger.assets.field.serial"),
        ]
      : []),
    date(
      "in_service_date",
      "desktop.ledger.assets.field.in_service_date",
      true,
    ),
    ...(creating
      ? [
          choice(
            "acquisition_shape",
            "desktop.ledger.assets.field.acquisition_shape",
            shapes,
            true,
          ),
          ...(outside
            ? [
                date(
                  "declared_acquisition_date",
                  "desktop.ledger.assets.field.declared_acquisition_date",
                  true,
                ),
                choice(
                  "declared_activity",
                  "desktop.ledger.assets.field.declared_activity",
                  activities,
                  true,
                ),
                text(
                  "acquisition_reference",
                  "desktop.ledger.assets.field.acquisition_reference",
                  true,
                ),
                {
                  ...field(
                    "candidate",
                    FURTHER_PURCHASE,
                    "desktop.ledger.assets.field.further_purchase",
                  ),
                  hint_key: "desktop.ledger.assets.field.further_purchase_hint",
                },
                ...(said(FURTHER_PURCHASE) === ""
                  ? []
                  : [
                      choice(
                        FURTHER_SHAPE,
                        "desktop.ledger.assets.field.further_shape",
                        (context.options?.further_acquisition_shapes ?? []).map(
                          (token): FieldChoice => ({
                            token,
                            family: "acquisition_shape",
                          }),
                        ),
                        true,
                      ),
                    ]),
              ]
            : [
                field(
                  "candidate",
                  "acquisition",
                  "desktop.ledger.assets.field.acquisition",
                  true,
                ),
              ]),
        ]
      : []),
    choice(
      "acquired_condition",
      "desktop.ledger.assets.field.acquired_condition",
      tokenChoices(context, "acquired_condition"),
      true,
    ),
    ...conditionFields(context, said("acquired_condition")),
    choice(
      "basis_stage",
      "desktop.ledger.assets.field.basis_stage",
      (context.options?.basis_stages ?? []).map(({ stage }): FieldChoice => ({
        token: stage,
        family: "basis_stage",
      })),
      true,
    ),
    amount("basis_amount", "desktop.ledger.assets.field.basis", true),
    {
      ...amount(
        "non_deductible_iva",
        "desktop.ledger.assets.field.non_deductible_iva",
        true,
      ),
      hint_key: "desktop.ledger.assets.field.non_deductible_iva_hint",
    },
    ...basisFields(context, said("basis_stage")),
    amount("residual_value", "desktop.ledger.assets.field.residual_value"),
    choice(
      "opening_status",
      "desktop.ledger.assets.field.opening_status",
      (context.options?.opening_statuses ?? []).map(
        ({ status }): FieldChoice => ({
          token: status,
          family: "opening_history_status",
        }),
      ),
      true,
    ),
    ...openingFields(context, said("opening_status"), methods),
    choice("method", "desktop.ledger.assets.field.method", offered, true),
    ...methodFacts(context, draft),
    ...vehicleFields(context, draft),
  ];
}

/** The reasons the backend serves, each worded by the key it served. */
const bajaReasons = (context: FieldContext): FieldChoice[] =>
  (context.options?.disposal_reasons ?? []).map((option): FieldChoice => ({
    token: option.reason,
    family: null,
    word: option.label_key,
  }));

/** The fields of a baja, new or changed. */
function bajaFields(context: FieldContext): FormField[] {
  const { tokens } = context;
  return [
    date("date", "desktop.ledger.assets.field.disposal_date", true),
    choice(
      "reason",
      "desktop.ledger.assets.field.disposal_reason",
      bajaReasons(context),
      true,
    ),
    {
      ...amount("proceeds", "desktop.ledger.assets.field.proceeds", true),
      hint_key: "desktop.ledger.assets.field.disposal_amount_hint",
    },
    {
      ...amount(
        "transmission_costs",
        "desktop.ledger.assets.field.transmission_costs",
        true,
      ),
      hint_key: "desktop.ledger.assets.field.disposal_amount_hint",
    },
    amount("market_value", "desktop.ledger.assets.field.market_value"),
    choice(
      "prior_free_depreciation_regime",
      "desktop.ledger.assets.field.prior_regime",
      tokens("prior_free_depreciation_regime").map((token): FieldChoice => ({
        token,
        family: "prior_free_depreciation_regime",
      })),
    ),
    date(
      "later_affectation_on",
      "desktop.ledger.assets.field.later_affectation",
    ),
  ];
}

/** The fields of an act on an element, drawn from the context and the text
 * typed so far. */
export function fieldsFor(
  context: FieldContext,
  draft: FormDraft = {},
): FormField[] {
  const { kind, row, descriptor, tokens } = context;
  switch (kind) {
    case "element":
      return revisionFields(context, draft, true);
    case "correction":
      return revisionFields(context, draft, false);
    case "descriptor":
      return [
        {
          ...text("name", "desktop.ledger.assets.field.name", true),
          current: descriptor?.name ?? row?.name ?? null,
        },
        {
          ...text("serial_number", "desktop.ledger.assets.field.serial"),
          current: descriptor?.serial_number ?? row?.serial_number ?? null,
        },
        {
          ...text("description", "desktop.ledger.assets.field.description"),
          current: descriptor?.description ?? null,
        },
        {
          ...choice(
            "document_kind",
            "desktop.ledger.assets.field.document_kind",
            tokens("document_kind").map((token): FieldChoice => ({
              token,
              family: "document_kind",
            })),
          ),
          current: descriptor?.document_kind ?? null,
        },
        {
          ...text(
            "document_number",
            "desktop.ledger.assets.field.document_number",
          ),
          current: descriptor?.document_number ?? null,
        },
        {
          ...text("supplier_name", "desktop.ledger.assets.field.supplier_name"),
          current: descriptor?.supplier_name ?? null,
        },
        {
          ...text(
            "supplier_tax_id",
            "desktop.ledger.assets.field.supplier_tax_id",
          ),
          current: descriptor?.supplier_tax_id ?? null,
        },
      ];
    case "baja":
    case "baja_change":
      return bajaFields(context);
    case "claim":
      // A claim's fields start from the plan; see `claimFields`.
      return [];
  }
}

/** What an act's form starts from, as text: what the revision a correction
 * supersedes states, what the description states, the baja a change starts
 * from. */
export function initialOf(
  context: FieldContext,
  fields: readonly FormField[],
): FormDraft {
  const base = draftOf(fields);
  if (context.kind === "correction" && context.revision !== null)
    return { ...base, ...revisionDraft(context.revision, context.options) };
  if (context.kind === "baja_change" && context.revision !== null)
    return { ...base, ...disposalDraft(context.revision) };
  return base;
}
