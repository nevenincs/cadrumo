import type {
  HouseholdGroup,
  HouseholdLeaf,
  HouseholdPersonEdit,
  HouseholdQuestion,
  HouseholdRow,
  HouseholdRowAction,
} from "../../shell/profileHousehold";
import type {
  HouseholdChange,
  ProfileEdit,
  ProfileField,
} from "../../shell/userProfile";

// What the household element does with the groups it is served, and nothing
// the product owns: which leaves exist, their words, answer sets, the answers
// each leaf is asked after, limits, states and the controls that add or
// remove a person are all served. The window only turns what a person typed
// into the change the product takes, and says which groups it can send.

/** The replacement each served group is written through. A group the window
 * has no replacement for is shown and never written. */
const REPLACEMENT: Readonly<Record<string, "descendants" | "ascendants">> = {
  "renta_family.descendiente": "descendants",
  "renta_family.ascendiente": "ascendants",
};

export const replacementOf = (group: HouseholdGroup) =>
  REPLACEMENT[group.group_key] ?? null;

/** A household change of the descendants or the ascendants. */
const householdEdit = (
  kind: "descendants" | "ascendants",
  change: HouseholdChange,
): ProfileEdit =>
  kind === "descendants" ? { kind, ...change } : { kind, ...change };

/** The change a served add or remove control submits, by the registered
 * operation it names. A control naming any other operation, or more than
 * one, is not one the window can send. */
const ROW_CHANGE: Readonly<Record<string, "descendants" | "ascendants">> = {
  "user-profile.descendants": "descendants",
  "user-profile.ascendants": "ascendants",
};

export function rowChangeOf(
  action: HouseholdRowAction | null,
): "descendants" | "ascendants" | null {
  if (action === null || action.target_operation_ids.length !== 1) return null;
  return ROW_CHANGE[action.target_operation_ids[0]!] ?? null;
}

/** Whether any recorded fact of the group is hidden. Editing a person states
 * every person's facts again, and a hidden value cannot be stated again, so
 * no person of such a group is edited from here. Adding or removing one
 * person resends nobody, so a hidden value does not stop either. */
export const hasHiddenFacts = (group: HouseholdGroup) =>
  group.rows.some((row) => row.facts.some((fact) => fact.masked));

/** Why the group's people cannot be edited from here, or null when they
 * can. */
export function blockedWrite(
  group: HouseholdGroup,
): "not_served" | "hidden" | "no_replacement" | null {
  if (group.state === "not_served") return "not_served";
  if (replacementOf(group) === null) return "no_replacement";
  return hasHiddenFacts(group) ? "hidden" : null;
}

/** The change that adds one person, through the group's served add control,
 * or null when the group serves none the window can send. */
export function addition(
  group: HouseholdGroup,
  person: HouseholdPersonEdit,
): ProfileEdit | null {
  const kind = rowChangeOf(group.add_row_action);
  return kind === null ? null : householdEdit(kind, { add_row: person });
}

/** The change that removes the served person `row`, named by the index the
 * read served it at, or null when the group serves no remove control the
 * window can send. */
export function removal(
  group: HouseholdGroup,
  row: HouseholdRow,
): ProfileEdit | null {
  const kind = rowChangeOf(group.remove_row_action);
  return kind === null
    ? null
    : householdEdit(kind, { remove_row_index: row.row_index });
}

/** Whether a served condition holds for what the person has answered. */
function holds(
  condition: HouseholdLeaf["shown_when"][number],
  answer: string,
): boolean {
  if (condition.equals !== null) return answer === condition.equals;
  if (condition.contains !== null)
    return answer
      .split(",")
      .map((token) => token.trim())
      .includes(condition.contains);
  return false;
}

/** The leaves asked of a person with these answers, in served order: a leaf
 * with no condition always, any other while one of its conditions holds on a
 * leaf that is itself asked. An answer to a leaf no longer asked counts for
 * nothing. */
export function shownLeaves(
  leaves: HouseholdLeaf[],
  values: Readonly<Record<string, string>>,
): HouseholdLeaf[] {
  const byKey = new Map(leaves.map((leaf) => [leaf.leaf, leaf]));
  const asked = new Map<string, boolean>();
  const isAsked = (leaf: HouseholdLeaf, seen: Set<string>): boolean => {
    const known = asked.get(leaf.leaf);
    if (known !== undefined) return known;
    if (seen.has(leaf.leaf)) return false;
    seen.add(leaf.leaf);
    const shown =
      leaf.shown_when.length === 0 ||
      leaf.shown_when.some((condition) => {
        const other = byKey.get(condition.leaf);
        return (
          other !== undefined &&
          isAsked(other, seen) &&
          holds(condition, (values[condition.leaf] ?? "").trim())
        );
      });
    asked.set(leaf.leaf, shown);
    return shown;
  };
  return leaves.filter((leaf) => isAsked(leaf, new Set()));
}

/** Whether the group already holds as many people as its design does. A
 * group that serves no limit is never full here. The product serves no add
 * control for a full group. */
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

/** The replacement an edit of one person makes: the person at `index` of the
 * ordered people replaced, and everyone else stated as stored. */
export function replacement(
  group: HouseholdGroup,
  index: number,
  facts: HouseholdPersonEdit,
): ProfileEdit | null {
  const kind = replacementOf(group);
  if (kind === null) return null;
  const people = orderedRows(group).map(personEdit);
  people[index] = facts;
  return householdEdit(kind, { rows: people });
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
  return kind === null ? null : householdEdit(kind, { rows: [] });
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
