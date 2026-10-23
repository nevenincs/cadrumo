// The declaration form exactly as the registered read `modelo.work.form`
// returns it (`ModeloWorkbenchFormProjectionV1`), narrowed to what the
// prototype draws. The application classifies every box; these types carry
// its words and nothing is worked out again here.

export type Disclosure =
  | "localized"
  | "spanish_fallback"
  | "official_spanish"
  | "technical"
  | "unnamed";

export type FormText = { text: string; disclosure: Disclosure };

/** A value on the wire: its kind and its canonical text, or absent. */
export type Scalar = {
  kind: "string" | "integer" | "boolean" | "decimal" | "date" | "null";
  text: string;
} | null;

export type Origin =
  | "not_applicable"
  | "overrides_source"
  | "calculated"
  | "not_calculated_yet"
  | "calculation_failed"
  | "informational"
  | "needs_input"
  | "imported"
  | "not_imported_yet"
  | "optional_empty"
  | "cleared"
  | "default_to_confirm"
  | "entered";

export type Editability =
  | "editable_value"
  | "editable_override"
  | "overridable_source"
  | "locked_source"
  | "source_policy_undecided"
  | "edit_at_profile"
  | "calculated"
  | "design_constant"
  | "informational"
  | "not_writable"
  | "no_admission";

export type SourceFamily =
  | "records"
  | "registers"
  | "profile"
  | "earlier_filings"
  | "aeat_draft"
  | "your_entries"
  | "fixed_by_design";

export type Surface =
  "ledger" | "withholding" | "profile" | "declarations" | "none";

export type Address =
  | { kind: "casilla"; casilla_id: string }
  | { kind: "binding"; binding_id: string };

export type FormBinding = {
  binding_id: string;
  policy: {
    source_kind: string;
    family: SourceFamily;
    override_policy: string;
    surface: Surface;
  };
  resolved: boolean;
};

export type Rate = { ratio: string; unit: "fraction" };

export type FormField = {
  address: Address;
  box: string | null;
  label: FormText;
  help: string | null;
  data_type: string;
  value: Scalar;
  origin: Origin;
  editability: Editability;
  not_writable_reason: string | null;
  required: boolean;
  unattributed: boolean;
  grounded_rate: (Rate & { binding_id: string }) | null;
  printed_rate: (Rate & { literal: string }) | null;
  role: string | null;
  bindings: FormBinding[];
  source: {
    family: SourceFamily;
    binding_id: string | null;
    source_kind: string | null;
    earlier_filings: {
      modelo: string;
      period: { filing_year: number; code: string };
    }[];
  } | null;
  formula_id: string | null;
  formula_operands: string[];
  blockers: { code: string }[];
  constraints: { sign?: string | null } | null;
  legal_refs: string[];
  also_appears_on: string[];
};

export type GridCell = {
  kind: "casilla" | "binding_input" | "design_constant" | "blank";
  field: FormField | null;
  literal: string | null;
};

export type FormBlock =
  | { kind: "field"; id: string; field: FormField }
  | { kind: "context_field"; id: string; label: FormText; value: Scalar }
  | {
      kind: "grid";
      id: string;
      columns: { key: string; heading: FormText }[];
      rows: { key: string; heading: FormText | null; cells: GridCell[] }[];
    }
  | {
      kind: "repeating";
      id: string;
      columns: { key: string; heading: FormText }[];
      column_casilla_ids: (string | null)[];
      column_data_types: string[];
      min_rows: number;
      max_rows: number | null;
      rows_known: boolean;
      rows: { index: number; values: Scalar[] }[];
    }
  | { kind: "binding_inputs"; id: string; fields: FormField[] };

export type FormCounts = {
  total: number;
  needs_input: number;
  entered: number;
  imported: number;
  calculated: number;
  overridden: number;
  default_to_confirm: number;
  not_applicable: number;
  blocked: number;
};

export type FormSection = {
  id: string;
  heading: FormText;
  official_heading: string | null;
  blocks: FormBlock[];
  counts: FormCounts;
};

export type FormPage = {
  id: string;
  heading: FormText;
  official_ref: string | null;
  condition: string;
  applies: boolean | null;
  sections: FormSection[];
  counts: FormCounts;
};

export type ResultDirection =
  | "to_pay"
  | "to_refund"
  | "to_carry_forward"
  | "to_deduct_later"
  | "negative"
  | "nil"
  | "unknown";

export type Attention = "blocks" | "missing" | "confirm" | "check" | "info";

export type FormIssue = {
  finding: {
    kind: string;
    severity: string;
    casilla_id: string | null;
    message_locale_key: string;
    message_facts: Record<string, string | number>;
    legal_refs: string[];
  };
  box: string | null;
  attention: Attention;
  action_locale_key: string;
};

export type HolidayCoverage =
  "complete" | "national_only" | "calendar_unavailable" | string;

export type ModeloForm = {
  modelo: string;
  filing_year: number;
  period: { filing_year: number; code: string };
  registry_revision_id: string;
  work_unit_id: string;
  calculation_revision_id: string | null;
  language: string;
  layout_provenance: "reviewed" | "generated" | "inspection_only";
  inspection_reason: string | null;
  pages: FormPage[];
  working_figures: FormField[];
  unplaced: { field: FormField; reason: string | null }[];
  result_addresses: string[];
  counts: FormCounts;
  progress: {
    state: "complete" | "in_progress" | "blocked" | "undefined";
    materialised_count: number;
    target_count: number;
  };
  operator_entries_known: boolean;
  edit_admitted: boolean;
  verification: "complete" | "incomplete" | "blocked" | null;
  issues: FormIssue[];
  calculation_notes: {
    reason: string;
    attention: Attention;
    casilla_id: string | null;
    box: string | null;
  }[];
  calculation_notes_held: boolean;
  result: {
    casilla_id: string;
    box: string | null;
    value: string | null;
    direction: ResultDirection;
    election_may_change: boolean;
  } | null;
  deadline: {
    closes_on: string;
    nominal_closes_on: string;
    holiday_coverage: HolidayCoverage;
    days_remaining: number | null;
    days_overdue: number | null;
  } | null;
  aeat_data: { snapshot_id: string; imported_at: string | null } | null;
  filing: { recorded_at: string | null } | null;
  last_export: {
    exported_at: string;
    calculation_revision_id: string;
    current: boolean;
  } | null;
  edit_closure: "recorded_as_filed" | null;
};

/** Why a declaration cannot be edited: the application's typed refusal. */
export type EditRefusal = {
  outcome: "refused";
  refusal: {
    kind: string;
    code: string;
    facts: string[];
    reconsideration_condition: string | null;
  };
};

export type FormEnvelope = {
  result_version: 1;
  profile_id: string;
  work_unit_id: string;
  form: { form: ModeloForm; verified: boolean; filed: boolean };
  admitted_baseline: { baseline_id: string; expires_at: string } | null;
  admission_refusal: EditRefusal | null;
  calculation_revision_id: string | null;
  verification_report_id: string | null;
  asks_m303_evidence: boolean;
  asks_modelo_390: boolean;
  registry_revision_id: string;
};

/** One staged edit, as the edit contract names it. A box takes a typed
 * value, a clear or a restore; a binding that feeds a box takes an override
 * or its removal. Confirming an assumed value is a typed value equal to it. */
export type Intent =
  | { kind: "set_typed_value"; text: string; confirms?: true }
  | { kind: "clear_declared_value" }
  | { kind: "restore_source_value" }
  | { kind: "set_override_value"; text: string }
  | { kind: "remove_override" };
