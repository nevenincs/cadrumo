// The household the profile states and the imputation election it dates, as
// the host serves them: the product's own groups, leaves, questions and words,
// at the profile revision they were read at. The window decides nothing about
// them. A group says what is known about its people and no more: `unknown`
// means nothing was stated and no person is stored, `none_declared` that the
// profile states a count of zero, `incomplete` that it states more people than
// it records (the recorded people are still served, with the product's words
// for the two numbers), and `not_served` that the product serves no person of
// that group at all. The four are never drawn as the same.

import type { CallPlan } from "./hostCall";

/** What the profile says about one group of people. */
export type HouseholdGroupState =
  "rows" | "incomplete" | "none_declared" | "unknown" | "not_served";

/** One answer of another leaf of the same person that the product asks the
 * leaf after. Served and typed for the contract; the window decides nothing
 * with it: whether a leaf is asked is its served `HouseholdAsk`. Exactly one
 * of `equals` and `contains` is set. */
export type HouseholdLeafCondition = {
  leaf: string;
  equals: string | null;
  contains: string | null;
};

/** One fact a person can state: its stored key, its words and its answer
 * set. `field_type` is the product's closed type token. The group's leaves
 * are also the form of a new person. */
export type HouseholdLeaf = {
  leaf: string;
  label: string;
  help: string | null;
  field_type: string;
  required: boolean;
  choices: { value: string; label: string }[];
  /** The answers the product asks the leaf after. Served and unused: the
   * window shows a leaf by its `HouseholdAsk`. */
  shown_when: HouseholdLeafCondition[];
};

/** Whether the product asks one leaf of a person now. `asked`: the leaf is
 * asked. `not_asked`: it is not, and an answer to it counts for nothing.
 * `awaits_answer`: it is not asked yet because a leaf it is asked after has no
 * answer. The product resolves it; the window never does. */
export type HouseholdAsk = "asked" | "not_asked" | "awaits_answer";

/** The ask the product resolved for one leaf of a person. A list of them is
 * served in the group's leaf order. */
export type HouseholdLeafAsk = { leaf: string; ask: HouseholdAsk };

/** The answers of one person the operator has typed and not saved, by the
 * leaf each answers, which the product reads only to resolve the asks. It is
 * never stored, logged or echoed, and the read it rides has no effect. */
export type HouseholdDraft = {
  /** The `group_key` of the group the person belongs to. */
  group: string;
  facts: { leaf: string; value: string }[];
};

/** What the product answers a draft with: the asks it resolved, and no value.
 * A draft naming a group or leaf it does not serve, or one leaf twice, is
 * refused with `{ code: "invalid_household_draft" }`. */
export type HouseholdDraftAnswer = {
  group_key: string;
  leaf_asks: HouseholdLeafAsk[];
};

/** A control that changes a group's people: its words and the registered
 * operation it submits. */
export type HouseholdRowAction = {
  action_words: string;
  target_operation_ids: string[];
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
  /** The ask of every leaf of the group for this person's stored answers. */
  leaf_asks: HouseholdLeafAsk[];
};

/** One person as a household change states it: the facts it states, each
 * under the `leaf` key its group serves. A leaf left out is not stated, and
 * the product validates every fact. The same shape is the one person added
 * and each person of a whole-family replacement, where a person left out of
 * the set is removed and an empty set states that the group has none. */
export type HouseholdPersonEdit = {
  facts: { field_key: string; value: string }[];
};

export type HouseholdGroup = {
  group_key: string;
  label: string;
  state: HouseholdGroupState;
  /** The count the profile states, where it states one. */
  stated_count: string | null;
  row_count: number;
  /** "N stated, M recorded" in the product's words; only for an `incomplete`
   * group, which is not a complete household. */
  incomplete_words: string | null;
  /** The most people the declaration's design lets the group hold, where it
   * declares one. A group at it takes no more. */
  max_rows: number | null;
  leaves: HouseholdLeaf[];
  /** The ask of every leaf for a person not yet stated. */
  new_row_leaves: HouseholdLeafAsk[];
  /** Adds one person built from `leaves`; null while the group takes no
   * more people. */
  add_row_action: HouseholdRowAction | null;
  /** Removes one served person, named by its `row_index`; null while no
   * person is stored. */
  remove_row_action: HouseholdRowAction | null;
  rows: HouseholdRow[];
};

/** A question the product asks of this household now, in its own words, with
 * the answer the profile states. `saved_value` is the token of a served
 * choice, or null when the profile states nothing: not stated is neither of
 * the choices and is never drawn as one. A question the product does not ask
 * of this household is not served. */
export type HouseholdQuestion = {
  question_id: string;
  /** The stored fact the answer is written to. */
  path: string;
  prompt: string;
  help: string | null;
  saved_value: string | null;
  choices: { value: string; label: string }[];
};

/** The household at the revision it was read at, which an edit of it names
 * as its baseline. */
export type ProfileHousehold = {
  profile_id: string;
  record_revision: number;
  content_digest: string;
  groups: HouseholdGroup[];
  questions: HouseholdQuestion[];
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
 * `not_signed_in` or `unavailable`; a draft read also `invalid_household_draft`
 * with the product's sentence as `refusal_words`. */
export type ProfileCompanionPort = {
  household(language: string, plan?: CallPlan): Promise<ProfileHousehold>;
  /** Which leaves one person with these unsaved answers is asked. No effect. */
  householdDraft(
    language: string,
    draft: HouseholdDraft,
    plan?: CallPlan,
  ): Promise<HouseholdDraftAnswer>;
  imputationElection(
    profile: string,
    taxYear: number,
    language: string,
  ): Promise<ImputationElection>;
};
