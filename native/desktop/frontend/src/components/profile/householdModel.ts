import type {
  HouseholdGroup,
  HouseholdLeaf,
  HouseholdPersonEdit,
  HouseholdQuestion,
  HouseholdRow,
} from "../../shell/profileHousehold";
import type { ProfileEdit, ProfileField } from "../../shell/userProfile";

// What the household element does with the groups it is served, and nothing
// the product owns: which leaves exist, their words, answer sets, limits and
// states are all served. The window only turns what a person typed into the
// whole-set replacement the product takes, and says which groups it can send.

/** The replacement each served group is written through. A group the window
 * has no replacement for is shown and never written. */
const REPLACEMENT: Readonly<Record<string, "descendants" | "ascendants">> = {
  "renta_family.descendiente": "descendants",
  "renta_family.ascendiente": "ascendants",
};

export const replacementOf = (group: HouseholdGroup) =>
  REPLACEMENT[group.group_key] ?? null;

/** Whether any recorded fact of the group is hidden. A replacement states
 * every person's facts again, and a hidden value cannot be stated again, so
 * such a group is never rewritten from here. */
export const hasHiddenFacts = (group: HouseholdGroup) =>
  group.rows.some((row) => row.facts.some((fact) => fact.masked));

/** Why the group cannot be written from here, or null when it can. */
export function blockedWrite(
  group: HouseholdGroup,
): "not_served" | "hidden" | "no_replacement" | null {
  if (group.state === "not_served") return "not_served";
  if (replacementOf(group) === null) return "no_replacement";
  return hasHiddenFacts(group) ? "hidden" : null;
}

/** Whether the group already holds as many people as its design does. A
 * group that serves no limit is never full here; the product refuses what it
 * cannot hold and says why. */
export const atCap = (group: HouseholdGroup) =>
  group.max_rows !== null && group.rows.length >= group.max_rows;

/** The people of a group in the order the product stores them. */
export const orderedRows = (group: HouseholdGroup): HouseholdRow[] =>
  [...group.rows].sort((a, b) => Number(a.row_index) - Number(b.row_index));

/** What a stored fact reads as: its served choice's words where its leaf has
 * a closed answer set, else the stored text. */
export function factWords(leaf: HouseholdLeaf, value: string): string {
  return leaf.choices.find((choice) => choice.value === value)?.label ?? value;
}

/** One person as the replacement states it: every fact the person has. */
export const personEdit = (row: HouseholdRow): HouseholdPersonEdit => ({
  facts: row.facts.map((fact) => ({ field_key: fact.leaf, value: fact.value })),
});

/** The replacement a change of one person makes: the person at `index` of the
 * ordered people replaced, the person added when `index` is null, or the
 * person removed when `facts` is null. Everyone else is stated as stored. */
export function replacement(
  group: HouseholdGroup,
  index: number | null,
  facts: HouseholdPersonEdit | null,
): ProfileEdit | null {
  const kind = replacementOf(group);
  if (kind === null) return null;
  const people = orderedRows(group).map(personEdit);
  if (index === null) {
    if (facts) people.push(facts);
  } else if (facts) people[index] = facts;
  else people.splice(index, 1);
  return { kind, rows: people };
}

/** The edit that states a household question's answer: the token of a served
 * choice, or null to take the statement back so the profile states nothing
 * again. Anything that is not a choice the product served is not sent. */
export function answerEdit(
  question: HouseholdQuestion,
  value: string | null,
): ProfileEdit | null {
  if (
    value !== null &&
    !question.choices.some((choice) => choice.value === value)
  )
    return null;
  return { kind: "field", path: question.path, value: value ?? "" };
}

/** The choice the profile states for a question, or null when it states
 * nothing. */
export const statedChoice = (question: HouseholdQuestion) =>
  question.choices.find((choice) => choice.value === question.saved_value) ??
  null;

/** The group stated to have no people. */
export const declaredNone = (group: HouseholdGroup): ProfileEdit | null => {
  const kind = replacementOf(group);
  return kind === null ? null : { kind, rows: [] };
};

/** A leaf as the profile's typed editors take it: the same shape as a profile
 * detail, so a date, a number or a choice is entered as it is everywhere
 * else. */
export function leafField(leaf: HouseholdLeaf, value: string): ProfileField {
  return {
    path: leaf.leaf,
    label: leaf.label,
    value: value === "" ? null : value,
    masked: false,
    required: leaf.required,
    field_type: leaf.field_type,
    choices: leaf.choices,
    help: leaf.help ? [leaf.help] : null,
    about: "",
    row_index: null,
  };
}

/** What a person typed for a leaf, as the facts a replacement states: only
 * the leaves that hold something. */
export function typedFacts(
  leaves: HouseholdLeaf[],
  values: Readonly<Record<string, string>>,
): HouseholdPersonEdit {
  return {
    facts: leaves.flatMap((leaf) => {
      const value = (values[leaf.leaf] ?? "").trim();
      return value === "" ? [] : [{ field_key: leaf.leaf, value }];
    }),
  };
}
