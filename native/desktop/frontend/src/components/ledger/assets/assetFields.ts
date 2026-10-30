// The fields of each act's form, and how typed text becomes the values of a
// request. The tab declares which controls it draws and the labels they carry;
// what each may hold comes from the backend: the methods and table classes the
// registry admits for the element's kind and year, the purchases the ledger
// offers, and the facts the register already states. The form decides nothing
// about them, and the backend judges what is sent.

import {
  copyPercent,
  parseDecimal,
  parseIsoDate,
  parseLine,
  parsePercent,
  TAX_AMOUNT_RULE,
  type GrammarRefusal,
  type Parsed,
} from "../../../shell/ledgerGrammar";
import type {
  AssetListRow,
  ActivityAssetRevision,
  DescriptorFacts,
  FormOptions,
  PlanClaim,
  PlanRow,
} from "../../../shell/ledgerSetup";
import type { PublicDecimal } from "../../../shell/ledger";
import type { AssetFamily } from "./assetsWords";

// ---- The tab's forms -------------------------------------------------------

export type FormKind =
  "element" | "descriptor" | "correction" | "claim" | "baja";

/** `candidate` is a choice among the purchases the backend offers, picked
 * and never typed; `share` is a percentage typed, a fraction sent. */
export type FormControl =
  | "text"
  | "date"
  | "amount"
  | "share"
  | "whole"
  | "choice"
  | "flag"
  | "candidate";

/** What a form states, by field key: text, a decimal, a whole number, a
 * choice's token, a flag, or null where nothing was stated. */
export type FormValue = string | number | boolean | PublicDecimal | null;
export type FormValues = Record<string, FormValue>;

/** One choice of a field: the backend's token, worded by the family the
 * token belongs to, or by the text the backend serves with it (a table
 * class's official name). */
export type FieldChoice = {
  token: string;
  family: AssetFamily | null;
  label?: string;
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

const L = "desktop.ledger.assets.field.";

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
const whole = (key: string, label: string, required = false) =>
  field("whole", key, label, required);
const choice = (
  key: string,
  label: string,
  choices: FieldChoice[],
  required = false,
) => field("choice", key, label, required, choices);

const decimalOf = (found: { decimal: string } | null | undefined) =>
  found?.decimal ?? null;

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
};

/**
 * What a form's text says. A full form states every field, null where
 * nothing was typed, so the backend names what is missing. Given `initial`,
 * only the fields changed from it and not emptied are stated, and the rest
 * are left as the record has them.
 */
export function answer(
  fields: readonly FormField[],
  draft: FormDraft,
  initial: FormDraft | null,
): Answered {
  const values: FormValues = {};
  const problems: Record<string, GrammarRefusal> = {};
  for (const found of fields) {
    const raw = draft[found.key] ?? "";
    if (initial !== null && raw === (initial[found.key] ?? "")) continue;
    const parsed = parseField(found, raw);
    if (parsed.kind === "refused") problems[found.key] = parsed.refusal;
    else if (parsed.kind === "value") values[found.key] = parsed.value;
    else if (initial === null) values[found.key] = null;
  }
  return { values, problems };
}

// ---- The fields of an act ------------------------------------------------------

/** What the form for an act is drawn from. */
export type FieldContext = {
  kind: FormKind;
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
});

/** The facts each method of the election takes beyond its method and regime.
 * A method not listed takes none the form can state. */
const METHOD_FACTS: Record<string, readonly string[]> = {
  linear: [
    "authority_class_key",
    "linear_coefficient",
    "used_determination",
    "used_price",
    "used_evidence",
  ],
  constant_percentage: ["authority_class_key", "linear_coefficient"],
  sum_of_digits: ["authority_class_key", "digit_period", "digit_order"],
  low_value_free: ["low_value_election", "low_value_evidence"],
  research_development_free: ["authority_class_key", "research_evidence"],
  research_development_building: ["authority_class_key", "research_evidence"],
  // These take no fact beyond the method itself.
  goodwill: [],
  intangible_indefinite_life: [],
};

/** Whether the form states the facts of this method at all. */
export const methodStated = (method: string): boolean =>
  Object.hasOwn(METHOD_FACTS, method);

/** Whether the form states a fact of the election for the method typed. */
export const methodTakes = (method: string, key: string): boolean =>
  Object.hasOwn(METHOD_FACTS, method) && METHOD_FACTS[method]!.includes(key);

/** The revision's own facts a form field starts from, by the path in the
 * revision. A path through the election, the basis or the opening history
 * names the field that states it. */
export const REVISION_PATHS: Record<string, readonly string[]> = {
  asset_kind: ["asset_kind"],
  acquisition_shape: ["acquisition_shape"],
  in_service_date: ["in_service_date"],
  acquired_condition: ["acquired_condition"],
  residual_value: ["residual_value"],
  basis_stage: ["basis", "stage"],
  basis_amount: ["basis", "basis_amount"],
  non_deductible_iva: ["basis", "non_deductible_iva"],
  business_use_share: ["basis", "business_use_share"],
  prior_allocation_provenance: ["basis", "prior_allocation_provenance"],
  opening_status: ["opening_history", "status"],
  opening_amount: ["opening_history", "accumulated_amount"],
  opening_through: ["opening_history", "covered_through_tax_year"],
  opening_method: ["opening_history", "amortization_method"],
  method: ["amortization", "method"],
  authority_class_key: ["amortization", "authority_class_key"],
  linear_coefficient: ["amortization", "linear_coefficient"],
  used_determination: ["amortization", "used_original_price", "determination"],
  used_price: ["amortization", "used_original_price", "original_price"],
  used_evidence: ["amortization", "used_original_price", "evidence_reference"],
  digit_period: ["amortization", "sum_of_digits_period_years"],
  digit_order: ["amortization", "digit_order"],
  low_value_election: ["amortization", "low_value", "election_reference"],
  low_value_evidence: [
    "amortization",
    "low_value",
    "new_material_evidence_reference",
  ],
  research_evidence: [
    "amortization",
    "research_development_evidence_reference",
  ],
};

const SHARES = new Set(["business_use_share", "linear_coefficient"]);

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

/** The text a correction's fields start from: what the revision it supersedes
 * states. */
export function revisionDraft(revision: ActivityAssetRevision): FormDraft {
  const draft: FormDraft = {};
  for (const [key, path] of Object.entries(REVISION_PATHS)) {
    const said = stated(revision, path);
    if (said === null) continue;
    draft[key] = SHARES.has(key) ? copyPercent(said) : said;
  }
  return draft;
}

/** The fields of a claim: the span, which starts from the claim being
 * replaced or else the first span the plan says is still claimable, and the
 * amount where the plan says the year's figure is the person's to elect. */
export function claimFields(
  row: PlanRow | null,
  replaced: PlanClaim | null,
): FormField[] {
  const span =
    replaced !== null
      ? { from: replaced.covered_from, until: replaced.covered_until }
      : row?.claimable_intervals[0]
        ? {
            from: row.claimable_intervals[0].covered_from,
            until: row.claimable_intervals[0].covered_until,
          }
        : null;
  return [
    {
      ...date("covered_from", "desktop.ledger.assets.from", true),
      current: span?.from ?? null,
    },
    {
      ...date("covered_until", "desktop.ledger.assets.until", true),
      current: span?.until ?? null,
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

/** The facts of the revision an element or a correction states. Which of them
 * are drawn follows what the typed text already says. */
function revisionFields(
  context: FieldContext,
  draft: FormDraft,
  creating: boolean,
): FormField[] {
  const { methods, classes } = fromOptions(context.options);
  // A method whose facts the form cannot state is not offered to start with,
  // since the backend would only refuse it as incomplete. A correction keeps
  // offering the method the element already has.
  const current = context.revision?.amortization;
  const kept =
    typeof current === "object" && current !== null
      ? String((current as { method?: unknown }).method)
      : null;
  const offered = methods.filter(
    (choice) => methodStated(choice.token) || choice.token === kept,
  );
  const said = (key: string) => draft[key] ?? "";
  const method = said("method");
  const takes = (key: string) => methodTakes(method, key);
  const known = said("opening_status") === "known";
  const used = said("acquired_condition") === "used";
  const stage = said("basis_stage");
  return [
    ...(creating
      ? [
          choice(
            "asset_kind",
            `${L}kind`,
            tokenChoices(context, "asset_kind"),
            true,
          ),
          text("name", `${L}name`, true),
          text("serial_number", `${L}serial`),
          field("candidate", "acquisition", `${L}acquisition`, true),
          choice(
            "acquisition_shape",
            `${L}acquisition_shape`,
            tokenChoices(context, "acquisition_shape"),
            true,
          ),
        ]
      : []),
    date("in_service_date", `${L}in_service_date`, true),
    choice(
      "acquired_condition",
      `${L}acquired_condition`,
      tokenChoices(context, "acquired_condition"),
      true,
    ),
    choice(
      "basis_stage",
      `${L}basis_stage`,
      tokenChoices(context, "basis_stage"),
      true,
    ),
    amount("basis_amount", `${L}basis`, true),
    {
      ...amount("non_deductible_iva", `${L}non_deductible_iva`, true),
      hint_key: `${L}non_deductible_iva_hint`,
    },
    ...(stage === "taxpayer_owned"
      ? [share("business_use_share", `${L}business_use_share`, true)]
      : []),
    ...(stage === "business_allocated"
      ? [text("prior_allocation_provenance", `${L}allocation_provenance`, true)]
      : []),
    amount("residual_value", `${L}residual_value`),
    choice(
      "opening_status",
      `${L}opening_status`,
      tokenChoices(context, "opening_history_status"),
      true,
    ),
    ...(known
      ? [
          amount("opening_amount", `${L}opening_amount`, true),
          whole("opening_through", `${L}opening_through`),
          choice("opening_method", `${L}opening_method`, methods),
        ]
      : []),
    choice("method", `${L}method`, offered, true),
    ...(takes("authority_class_key")
      ? [
          choice(
            "authority_class_key",
            `${L}class`,
            classes,
            // Free depreciation for research on a material element names its class.
            method !== "research_development_free" ||
              (said("asset_kind") || context.row?.asset_kind) === "material",
          ),
        ]
      : []),
    ...(takes("linear_coefficient")
      ? [share("linear_coefficient", `${L}coefficient`)]
      : []),
    ...(takes("used_determination") && used
      ? [
          choice(
            "used_determination",
            `${L}used_determination`,
            tokenChoices(context, "original_price_determination"),
          ),
          amount("used_price", `${L}used_price`),
          text("used_evidence", `${L}used_evidence`),
        ]
      : []),
    ...(takes("digit_period")
      ? [
          whole("digit_period", `${L}digit_period`, true),
          choice(
            "digit_order",
            `${L}digit_order`,
            tokenChoices(context, "digit_order"),
            true,
          ),
        ]
      : []),
    ...(takes("low_value_election")
      ? [
          text("low_value_election", `${L}low_value_election`, true),
          text("low_value_evidence", `${L}low_value_evidence`, true),
        ]
      : []),
    ...(takes("research_evidence")
      ? [text("research_evidence", `${L}research_evidence`, true)]
      : []),
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
          ...text("name", `${L}name`, true),
          current: descriptor?.name ?? row?.name ?? null,
        },
        {
          ...text("serial_number", `${L}serial`),
          current: descriptor?.serial_number ?? row?.serial_number ?? null,
        },
        {
          ...text("description", `${L}description`),
          current: descriptor?.description ?? null,
        },
        {
          ...choice(
            "document_kind",
            `${L}document_kind`,
            tokens("document_kind").map((token): FieldChoice => ({
              token,
              family: "document_kind",
            })),
          ),
          current: descriptor?.document_kind ?? null,
        },
        {
          ...text("document_number", `${L}document_number`),
          current: descriptor?.document_number ?? null,
        },
        {
          ...text("supplier_name", `${L}supplier_name`),
          current: descriptor?.supplier_name ?? null,
        },
        {
          ...text("supplier_tax_id", `${L}supplier_tax_id`),
          current: descriptor?.supplier_tax_id ?? null,
        },
      ];
    case "baja":
      return [
        date("date", `${L}disposal_date`, true),
        choice(
          "reason",
          `${L}disposal_reason`,
          tokens("disposal_reason").map((token): FieldChoice => ({
            token,
            family: "disposal_reason",
          })),
          true,
        ),
        amount("proceeds", `${L}proceeds`, true),
        amount("transmission_costs", `${L}transmission_costs`, true),
        amount("market_value", `${L}market_value`),
        choice(
          "prior_free_depreciation_regime",
          `${L}prior_regime`,
          tokens("prior_free_depreciation_regime").map(
            (token): FieldChoice => ({
              token,
              family: "prior_free_depreciation_regime",
            }),
          ),
        ),
        date("later_affectation_on", `${L}later_affectation`),
      ];
    case "claim":
      // A claim's fields start from the plan; see `claimFields`.
      return [];
  }
}

/** What an act's form starts from, as text: what the revision a correction
 * supersedes states, what the description states, and for a new element the
 * one acquisition shape the register supports. */
export function initialOf(
  context: FieldContext,
  fields: readonly FormField[],
): FormDraft {
  const base = draftOf(fields);
  if (context.kind === "correction" && context.revision !== null)
    return { ...base, ...revisionDraft(context.revision) };
  // The register supports one shape of acquisition, so a new element starts on it.
  if (context.kind === "element")
    return { ...base, acquisition_shape: "primary_purchase" };
  return base;
}
