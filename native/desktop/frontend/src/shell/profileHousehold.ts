// The household the profile states and the imputation election it dates, as
// the host serves them: the product's own groups, leaves, questions and words,
// at the profile revision they were read at. The window decides nothing about
// them. A group says what is known about its people and no more: `unknown`
// means nothing was stated and no person is stored, `none_declared` that the
// profile states a count of zero, and `not_served` that the product serves no
// person of that group at all. The three are never drawn as the same.

/** What the profile says about one group of people. */
export type HouseholdGroupState =
  "rows" | "none_declared" | "unknown" | "not_served";

/** One fact a person can state: its stored key, its words and its answer
 * set. `field_type` is the product's closed type token. */
export type HouseholdLeaf = {
  leaf: string;
  label: string;
  help: string | null;
  field_type: string;
  required: boolean;
  choices: { value: string; label: string }[];
};

/** One stored fact of a person. A leaf the person does not state is absent,
 * never zero. A masked value arrives already hidden. */
export type HouseholdFact = {
  leaf: string;
  path: string;
  value: string;
  masked: boolean;
};

export type HouseholdRow = {
  /** The person's index in the stored family, as the product writes it. */
  row_index: string;
  facts: HouseholdFact[];
};

export type HouseholdGroup = {
  group_key: string;
  label: string;
  state: HouseholdGroupState;
  /** The count the profile states, where it states one. */
  stated_count: string | null;
  row_count: number;
  leaves: HouseholdLeaf[];
  rows: HouseholdRow[];
};

/** The household at the revision it was read at, which an edit of it names
 * as its baseline. */
export type ProfileHousehold = {
  profile_id: string;
  record_revision: number;
  content_digest: string;
  groups: HouseholdGroup[];
  pages: number;
};

/** What the profile states for one question of one ejercicio: a value only
 * when it is declared. An undeclared or contradictory ejercicio is never one
 * of the choices. */
export type ElectionAnswer =
  | { state: "declared"; value: string }
  | { state: "undeclared" | "contradictory"; value: null };

/** One setup question in the words the setup wizard asks it. */
export type ElectionQuestion = {
  question_id: string;
  path: string | null;
  prompt: string;
  help: string | null;
  choices: { value: string; label: string; description: string | null }[];
};

/** The imputation election of one ejercicio. `record_revision` and
 * `content_digest` are the baseline an `imputation_election` edit names. */
export type ImputationElection = {
  profile_id: string;
  record_revision: number;
  content_digest: string;
  tax_year: number;
  criterion: ElectionAnswer;
  codigo_comercio_accounting: ElectionAnswer;
  /** The criterion each ejercicio states, in ejercicio order. */
  criterion_statements: { ejercicio: number; value: string }[];
  criterion_question: ElectionQuestion;
  year_question: ElectionQuestion;
  accounting_question: ElectionQuestion;
  /** The criterion tokens under which the accounting question is asked. */
  accounting_asked_for_criteria: string[];
  words_language: string;
};

/** The profile's companion reads. A rejection carries `{ code }`: one of
 * `not_signed_in` or `unavailable`. */
export type ProfileCompanionPort = {
  household(language: string): Promise<ProfileHousehold>;
  imputationElection(
    profile: string,
    taxYear: number,
    language: string,
  ): Promise<ImputationElection>;
};
