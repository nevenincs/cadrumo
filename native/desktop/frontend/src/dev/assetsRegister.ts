// The scenario register of the Assets tab, as the real register answers it:
// every element's list row, plan, limits, history, revisions, forecasts and
// baja figures, the register's years and payments, and what the registry admits
// per asset kind and year, recorded in the generated `assetsRegister.json`. The
// recording replays the synthetic scenario committed under
// `dev/fixtures/assets-register-scenario` through the backend's own register
// over the published authority; nothing here works a figure out or states what
// the registry admits.

import type { JsonObject } from "@/shell/ledger";
import type {
  AcquisitionCandidate,
  AssetListRow,
  BasisStageOption,
  ConditionOption,
  DisposalCalculation,
  DisposalFinding,
  DisposalReasonOption,
  ElectionLimits,
  OpeningStatusOption,
  PlanRow,
  TableGroup,
  TimelineEvent,
} from "@/shell/ledgerSetup";
import recorded from "@fixtures/assets-register/assetsRegister.json" with { type: "json" };

/** A baja's figures with no amount stated: what the register works out for a
 * sale on the scenario's date, or for the baja an element records. A stated
 * amount moves only the result. */
export type ScenarioDisposal = Omit<
  DisposalCalculation,
  | "disposal_date"
  | "reason"
  | "transmission_value"
  | "transmission_costs"
  | "result"
  | "route_changed_by_later_affectation"
  | "findings"
> & { findings: Omit<DisposalFinding, "label_key">[] };

export type ScenarioElement = {
  id: string;
  list: AssetListRow;
  rows: PlanRow[];
  limits: ElectionLimits;
  events: TimelineEvent[];
  /** The revisions the register holds of the element, as the backend serves them. */
  revisions: { revision: JsonObject; revision_id: string }[];
  /** The charge for a whole year of service, as the register plans it; the
   * schedule spreads it by days. */
  annual: string;
  /** The charge for each span the plan offers to claim, by `from/until`. */
  forecasts: Record<string, string>;
  /** The whole charge the register answered for each of those spans, with the
   * revision it rests on and the provisions it cites. */
  charges: Record<string, JsonObject>;
  /** Null where the register cannot work the baja out. */
  disposal: ScenarioDisposal | null;
};

/** What the registry admits for one asset kind and tax year. */
type FormOptions = {
  regime: string;
  methods: string[];
  method_facts: { method: string; facts: JsonObject[] }[];
  table_groups: TableGroup[];
  acquisition_shapes: string[];
  declared_activities: string[];
  disposal_reasons: DisposalReasonOption[];
  basis_stages: BasisStageOption[];
  opening_statuses: OpeningStatusOption[];
  acquired_conditions: ConditionOption[];
  further_acquisition_shapes: string[];
};

type RecordedElement = Omit<
  ScenarioElement,
  "id" | "list" | "annual" | "forecasts" | "charges"
> & {
  forecasts: Record<string, JsonObject & { amount: string }>;
};

type Recording = {
  register: {
    today: string;
    list: AssetListRow[];
    years: number[];
    default_year: number | null;
    candidates: AcquisitionCandidate[];
    form_options: {
      asset_kind: string;
      tax_year: number;
      options: FormOptions;
    }[];
    payments: {
      provider_id: string;
      asset_id: string | null;
      transaction_id: string;
      description: string;
    }[];
    vocabulary: {
      table_bound_methods: string[];
      timeline_fact_paths: string[];
      not_applicable_absences: string[];
      remedy_field_keys: Record<string, string>;
      no_table_minimum_key: string;
    };
  };
} & Partial<Record<string, RecordedElement>>;

const recording = recorded as unknown as Recording;
const register = recording.register;

/** The day the scenario stands on. */
export const SCENARIO_TODAY: string = register.today;

/** The register's years and the one it opens on. */
export const REGISTER_YEARS: readonly number[] = register.years;
export const REGISTER_DEFAULT_YEAR: number | null = register.default_year;

/** The ledger payments no element owns, as the register offers them. */
export const SCENARIO_PAYMENTS: readonly AcquisitionCandidate[] =
  register.candidates;

/** Every ledger payment the scenario gave the register, owned or not, under
 * the name the scenario calls it by: the content-derived identifier the ledger
 * itself minted for it, and the description it carries. */
export const SCENARIO_LEDGER_PAYMENTS: readonly {
  provider_id: string;
  asset_id: string | null;
  transaction_id: string;
  description: string;
}[] = register.payments;

/** The identifier the ledger minted for the payment the scenario calls
 * `providerId`. */
export const scenarioPaymentId = (providerId: string): string => {
  const found = register.payments.find(
    (payment) => payment.provider_id === providerId,
  );
  if (found === undefined)
    throw new Error(`the recording holds no payment ${providerId}`);
  return found.transaction_id;
};

/** The planned charge of a year the element serves whole, or nothing where no
 * such year has a figure. */
const annualOf = (rows: readonly PlanRow[]): string =>
  rows.find(
    (row) => row.planned !== null && row.service_days === row.calendar_days,
  )?.planned?.decimal ?? "0.00";

export const SCENARIO_ELEMENTS: readonly ScenarioElement[] = register.list.map(
  (list) => {
    const element = recording[list.asset_id];
    if (element === undefined)
      throw new Error(`the recording holds no element ${list.asset_id}`);
    return {
      ...element,
      id: list.asset_id,
      list,
      annual: annualOf(element.rows),
      forecasts: Object.fromEntries(
        Object.entries(element.forecasts).map(([span, charge]) => [
          span,
          charge.amount,
        ]),
      ),
      charges: element.forecasts,
    };
  },
);

/** What the registry admits for an asset kind in a tax year, or undefined for a
 * year the register does not list. */
export const formOptionsFor = (
  assetKind: string,
  taxYear: number,
): FormOptions | undefined =>
  register.form_options.find(
    (found) => found.asset_kind === assetKind && found.tax_year === taxYear,
  )?.options;

const KINDS = [
  ...new Set(register.form_options.map((found) => found.asset_kind)),
];
const openingYear = REGISTER_DEFAULT_YEAR ?? REGISTER_YEARS.at(-1);
const opening = (kind: string): FormOptions => {
  const options =
    openingYear === undefined ? undefined : formOptionsFor(kind, openingYear);
  if (options === undefined)
    throw new Error(`the recording holds no form options for ${kind}`);
  return options;
};
const byKind = <T>(pick: (options: FormOptions) => T): Record<string, T> =>
  Object.fromEntries(KINDS.map((kind) => [kind, pick(opening(kind))]));
const firstKind = KINDS[0];
if (firstKind === undefined)
  throw new Error("the recording holds no form options");
const anyKind = opening(firstKind);

/** What the registry admits per asset kind in the register's opening year. */
export const TABLE_GROUPS: Record<string, readonly TableGroup[]> = byKind(
  (options) => options.table_groups,
);
export const ADMITTED_METHODS: Record<string, readonly string[]> = byKind(
  (options) => options.methods,
);
export const METHOD_FACTS: Record<
  string,
  readonly { method: string; facts: JsonObject[] }[]
> = byKind((options) => options.method_facts);
/** The modality the scenario's taxpayer files in. */
export const SCENARIO_REGIME: string = anyKind.regime;
export const ACQUISITION_SHAPES: readonly string[] = anyKind.acquisition_shapes;
export const DECLARED_ACTIVITIES: readonly string[] =
  anyKind.declared_activities;
export const DISPOSAL_REASONS: readonly DisposalReasonOption[] =
  anyKind.disposal_reasons;
export const BASIS_STAGES: readonly BasisStageOption[] = anyKind.basis_stages;
export const OPENING_STATUSES: readonly OpeningStatusOption[] =
  anyKind.opening_statuses;
export const ACQUIRED_CONDITIONS: readonly ConditionOption[] =
  anyKind.acquired_conditions;
export const FURTHER_ACQUISITION_SHAPES: readonly string[] =
  anyKind.further_acquisition_shapes;

/** The methods whose corridor is the registry's amortization table, so an
 * election of one names a class, as the register declares them. */
export const TABLE_BOUND_METHODS: readonly string[] =
  register.vocabulary.table_bound_methods;
/** The facts a timeline can show a change of, with a repeated row as `[]`. */
export const TIMELINE_FACT_PATHS: readonly string[] =
  register.vocabulary.timeline_fact_paths;
/** The reasons a year has no figure that leave nothing to claim. */
export const NOT_APPLICABLE_ABSENCES: readonly string[] =
  register.vocabulary.not_applicable_absences;
/** The field whose entry settles each reason that names one. */
export const REMEDY_FIELD_KEYS: Record<string, string> =
  register.vocabulary.remedy_field_keys;
/** The reason a minimum has no table, though an edition covers the year. */
export const NO_TABLE_MINIMUM_KEY: string =
  register.vocabulary.no_table_minimum_key;
