import fixtures from "@fixtures/desktop-household/household.json" with { type: "json" };
import type {
  HouseholdAsk,
  HouseholdDraft,
  HouseholdFact,
  HouseholdGroup,
  HouseholdLeaf,
  HouseholdLeafAsk,
  HouseholdPersonEdit,
  HouseholdQuestion,
  HouseholdRowAction,
  ProfileCompanionPort,
  ProfileHousehold,
} from "../shell/profileHousehold";
import type { ProfileChange } from "../shell/userProfile";

// The household the application served for synthetic profiles through the
// `family_rows` page stream of `user-profile.view`, in every language, and the
// details of the refusals an ascendants or descendants replacement settled
// with. Regenerate with dev.desktop_household_fixture; never invent fields
// here. The fixture assembles the stream the way the host does (groups
// followed by their rows, a hidden value replaced by its mask, then the
// questions the product asks of the household), keeps what a replacement, an
// added or removed person, or an answer states and answers the next read with
// it, so a story or a scenario sees a write land. The add and remove controls
// of a group are the ones the application served for the same group in any
// state, offered as it offers them: the add while the group holds fewer people
// than its design admits, the remove while a person is stored.
//
// The asks (`new_row_leaves`, `leaf_asks`, and the answer of a draft read) are
// the product's to resolve. The recorded household does not carry them yet, so
// the fixture stands in for the product here and resolves them from the
// `shown_when` the group serves, by the product's rule: a leaf with no
// condition is asked; a leaf whose condition holds on an asked leaf is asked;
// otherwise it awaits an answer while a leaf it is asked after is asked and
// unanswered, and is not asked when every such leaf is answered. Nothing in
// the window evaluates this; it goes when the recorded household serves asks.

export type HouseholdScenario = keyof typeof fixtures.reads;

/** The states the application served, for a page to choose among. */
export const HOUSEHOLD_SCENARIOS = Object.keys(
  fixtures.reads,
) as HouseholdScenario[];

/** A refusal the application settled a replacement with, as the host carries
 * it to the window: its code and the finished sentence the application served.
 * Each is the recorded detail of a replacement of one group. */
export type HouseholdRefusal = keyof typeof fixtures.refusals;

declare global {
  interface Window {
    __scenarioHousehold?: {
      /** The next change is refused with the application's sentence for it. */
      refuseNext(refusal: HouseholdRefusal): void;
      /** The next change lands but its answer never arrives. */
      loseNextAnswer(): void;
      /** What the changes sent so far stated, in order. */
      writes(): ProfileChange[];
      /** The households read so far. */
      reads(): number;
      /** The drafts read so far, in order. */
      drafts(): HouseholdDraft[];
      /** The next draft read is refused as the product refuses an invalid
       * draft. */
      refuseNextDraft(): void;
    };
  }
}

/** What a hidden fact shows in place of its value, as the host masks it. */
const MASK = "••••••••";

/** The sentence a refused draft is told in. The recorded household carries no
 * such sentence, so this is synthetic, in one language. */
const DRAFT_REFUSAL_WORDS =
  "The answers of this person could not be checked. Try again.";

/** A group as the recorded household serves it: the asks may be absent. */
type ServedGroup = Omit<HouseholdGroup, "rows" | "new_row_leaves"> &
  Partial<Pick<HouseholdGroup, "new_row_leaves">>;

type Item =
  | ({ kind: "family_group" } & ServedGroup)
  | {
      kind: "family_row";
      group_key: string;
      row_index: string;
      facts: HouseholdFact[];
      leaf_asks?: HouseholdLeafAsk[];
    }
  | ({ kind: "family_question" } & HouseholdQuestion);

type Stored = {
  group: ServedGroup;
  rows: {
    row_index: string;
    facts: HouseholdFact[];
    leaf_asks?: HouseholdLeafAsk[];
  }[];
};

const holds = (
  condition: HouseholdLeaf["shown_when"][number],
  answer: string,
): boolean =>
  condition.equals !== null
    ? answer === condition.equals
    : condition.contains !== null &&
      answer
        .split(",")
        .map((token) => token.trim())
        .includes(condition.contains);

/** The asks the product would serve for these answers; see the note above. */
function resolveAsks(
  leaves: HouseholdLeaf[],
  answers: Readonly<Record<string, string>>,
): HouseholdLeafAsk[] {
  const asks = new Map<string, HouseholdAsk>();
  const asked = (leaf: string) => asks.get(leaf) === "asked";
  for (const leaf of leaves) {
    const governing = leaf.shown_when.map((condition) => condition.leaf);
    if (
      leaf.shown_when.length === 0 ||
      leaf.shown_when.some(
        (condition) =>
          asked(condition.leaf) &&
          holds(condition, (answers[condition.leaf] ?? "").trim()),
      )
    )
      asks.set(leaf.leaf, "asked");
    else if (
      governing.some(
        (parent) =>
          asks.get(parent) === "awaits_answer" ||
          (asked(parent) && (answers[parent] ?? "").trim() === ""),
      )
    )
      asks.set(leaf.leaf, "awaits_answer");
    else asks.set(leaf.leaf, "not_asked");
  }
  return leaves.map((leaf) => ({ leaf: leaf.leaf, ask: asks.get(leaf.leaf)! }));
}

const answersOf = (facts: HouseholdFact[]): Record<string, string> =>
  Object.fromEntries(facts.map((fact) => [fact.leaf, fact.value]));

export type HouseholdFixture = {
  reads: Pick<ProfileCompanionPort, "household" | "householdDraft">;
  change(change: ProfileChange): Promise<void>;
  /** Whether an edit is one of the household's: a replacement of a group, or
   * an answer to a question the household is asked. Any other edit of the
   * profile is not the household's to take. */
  takes(edit: ProfileChange["edit"]): boolean;
  /** The changes the fixture took, in order. */
  writes(): ProfileChange[];
  /** Reads answered so far. */
  readCount(): number;
  refuseNext(refusal: HouseholdRefusal): void;
  loseNextAnswer(): void;
  /** The drafts read so far, in order. */
  drafts(): HouseholdDraft[];
  refuseNextDraft(): void;
};

function itemsOf(scenario: HouseholdScenario, language: string): Item[] {
  const byLanguage = fixtures.reads[scenario].items as unknown as Record<
    string,
    Item[]
  >;
  return structuredClone(byLanguage[language] ?? byLanguage.en!);
}

function questionsOf(
  scenario: HouseholdScenario,
  language: string,
): HouseholdQuestion[] {
  return itemsOf(scenario, language).flatMap((item) =>
    item.kind === "family_question"
      ? [
          {
            question_id: item.question_id,
            path: item.path,
            prompt: item.prompt,
            help: item.help,
            saved_value: item.saved_value,
            choices: item.choices,
          },
        ]
      : [],
  );
}

function assemble(items: Item[]): Stored[] {
  const groups: Stored[] = [];
  for (const item of items) {
    if (item.kind === "family_question") continue;
    if (item.kind === "family_group") {
      groups.push({
        group: {
          group_key: item.group_key,
          label: item.label,
          state: item.state,
          stated_count: item.stated_count,
          row_count: item.row_count,
          incomplete_words: item.incomplete_words,
          max_rows: item.max_rows,
          leaves: item.leaves,
          new_row_leaves: item.new_row_leaves,
          add_row_action: item.add_row_action,
          remove_row_action: item.remove_row_action,
        },
        rows: [],
      });
    } else
      groups
        .find((entry) => entry.group.group_key === item.group_key)!
        .rows.push({
          row_index: item.row_index,
          facts: item.facts,
          leaf_asks: item.leaf_asks,
        });
  }
  return groups;
}

/** The add and remove controls the application served for a group in a
 * language, from whichever state served each. */
function servedActions(
  key: string,
  language: string,
): {
  add: HouseholdRowAction | null;
  remove: HouseholdRowAction | null;
} {
  const served = HOUSEHOLD_SCENARIOS.flatMap((scenario) =>
    assemble(itemsOf(scenario, language))
      .filter((entry) => entry.group.group_key === key)
      .map((entry) => entry.group),
  );
  return {
    add: served.find((group) => group.add_row_action)?.add_row_action ?? null,
    remove:
      served.find((group) => group.remove_row_action)?.remove_row_action ??
      null,
  };
}

const refusalWords = (refusal: HouseholdRefusal, language: string): string => {
  const details = fixtures.refusals[refusal] as Record<
    string,
    { refusal_words?: string }
  >;
  return (details[language] ?? details.en)?.refusal_words ?? "";
};

/**
 * A household fixture that starts in `scenario`. `language` is the one the
 * words of a refusal are served in; reads carry their own.
 */
export function householdFixture(
  scenario: HouseholdScenario = "unknown",
  language = "en",
): HouseholdFixture {
  const start = fixtures.reads[scenario];
  // What each group states now: a write replaces it, and every language's
  // read is drawn from it.
  const standing = new Map(
    assemble(itemsOf(scenario, language)).map((entry) => [
      entry.group.group_key,
      {
        state: entry.group.state,
        stated_count: entry.group.stated_count,
        incomplete_words: entry.group.incomplete_words,
        rows: entry.rows,
      },
    ]),
  );
  // The answer each question states now; a write replaces it.
  const answers = new Map(
    questionsOf(scenario, language).map((question) => [
      question.path,
      question.saved_value,
    ]),
  );
  let revision = start.record_revision;
  const taken: ProfileChange[] = [];
  let reads = 0;
  let refusal: HouseholdRefusal | null = null;
  let lost = false;
  let refuseDraft = false;
  const draftsRead: HouseholdDraft[] = [];
  const digest = () => `d${revision.toString(16).padStart(63, "0")}`;

  const household = (asked: string): ProfileHousehold => ({
    profile_id: fixtures.profile_id,
    record_revision: revision,
    content_digest: digest(),
    groups: assemble(itemsOf(scenario, asked)).map(({ group }) => {
      const now = standing.get(group.group_key)!;
      const actions = servedActions(group.group_key, asked);
      return {
        ...group,
        add_row_action:
          group.max_rows !== null && now.rows.length < group.max_rows
            ? actions.add
            : null,
        remove_row_action: now.rows.length > 0 ? actions.remove : null,
        new_row_leaves: group.new_row_leaves ?? resolveAsks(group.leaves, {}),
        state: now.state,
        stated_count: now.stated_count,
        incomplete_words: now.incomplete_words,
        row_count: now.rows.length,
        rows: now.rows.map((row) => ({
          row_index: row.row_index,
          facts: row.facts.map((fact) =>
            fact.masked ? { ...fact, value: MASK } : { ...fact },
          ),
          leaf_asks:
            row.leaf_asks ?? resolveAsks(group.leaves, answersOf(row.facts)),
        })),
      };
    }),
    questions: questionsOf(scenario, asked).map((question) => ({
      ...question,
      saved_value: answers.get(question.path) ?? null,
    })),
    pages: 1,
  });

  const fixture: HouseholdFixture = {
    reads: {
      household: async (asked) => {
        reads += 1;
        return household(asked);
      },
      householdDraft: async (asked, draft) => {
        draftsRead.push(structuredClone(draft));
        const served = household(asked).groups.find(
          (entry) => entry.group_key === draft.group,
        );
        const known = new Set(served?.leaves.map((leaf) => leaf.leaf));
        const stated = draft.facts.map((fact) => fact.leaf);
        if (
          refuseDraft ||
          !served ||
          stated.some((leaf) => !known.has(leaf)) ||
          new Set(stated).size !== stated.length
        ) {
          refuseDraft = false;
          throw {
            code: "refused",
            reason: "invalid_household_draft",
            refusal_words: DRAFT_REFUSAL_WORDS,
          };
        }
        return {
          group_key: served.group_key,
          leaf_asks: resolveAsks(
            served.leaves,
            Object.fromEntries(
              draft.facts.map((fact) => [fact.leaf, fact.value]),
            ),
          ),
        };
      },
    },
    async change(change) {
      taken.push(change);
      if (refusal) {
        const settled = refusal;
        refusal = null;
        throw {
          code: "refused",
          refusal_words: refusalWords(settled, language),
        };
      }
      const edit = change.edit;
      if (
        change.expected_revision !== revision ||
        change.expected_content_digest !== digest()
      )
        throw { code: "conflict" };
      if (edit.kind === "field") {
        // An answer to a question the product asks: one of its served
        // choices, or the empty token that takes the statement back.
        const asked = questionsOf(scenario, language).find(
          (question) => question.path === edit.path,
        );
        if (
          !asked ||
          (edit.value !== "" &&
            !asked.choices.some((choice) => choice.value === edit.value))
        )
          throw { code: "refused" };
        answers.set(asked.path, edit.value === "" ? null : edit.value);
        revision += 1;
        if (lost) {
          lost = false;
          throw { code: "unknown" };
        }
        return;
      }
      if (edit.kind !== "descendants" && edit.kind !== "ascendants")
        throw { code: "refused" };
      const key =
        edit.kind === "descendants"
          ? "renta_family.descendiente"
          : "renta_family.ascendiente";
      const group = assemble(itemsOf(scenario, language)).find(
        (entry) => entry.group.group_key === key,
      )!.group;
      const leaves = new Map<string, HouseholdLeaf>(
        group.leaves.map((leaf) => [leaf.leaf, leaf]),
      );
      // As the product composes it: the whole set, or the people stored
      // with one added or one removed. A stored person is kept with every
      // fact it states, a hidden one too.
      const stored = standing.get(key)!.rows;
      const asStored = (row: (typeof stored)[number]) => ({
        facts: row.facts,
        person: null as HouseholdPersonEdit | null,
      });
      let people: {
        facts: HouseholdFact[];
        person: HouseholdPersonEdit | null;
      }[];
      if ("rows" in edit)
        people = edit.rows.map((person) => ({ facts: [], person }));
      else if ("add_row" in edit)
        people = [...stored.map(asStored), { facts: [], person: edit.add_row }];
      else {
        const index = edit.remove_row_index;
        // No person is stored at that index: the product refuses it and
        // writes nothing.
        if (!stored.some((row) => row.row_index === index))
          throw { code: "refused" };
        people = stored.filter((row) => row.row_index !== index).map(asStored);
      }
      const sent = people.flatMap((entry) =>
        entry.person ? [entry.person] : [],
      );
      // The sentences are the ones the application recorded for the same
      // two refusals of the group being replaced.
      if (group.max_rows !== null && people.length > group.max_rows)
        throw {
          code: "refused",
          refusal_words: refusalWords(`${edit.kind}_over_limit`, language),
        };
      if (
        sent.some((row) =>
          row.facts.some((fact) => !leaves.has(fact.field_key)),
        )
      )
        throw {
          code: "refused",
          refusal_words: refusalWords(
            `${edit.kind}_fact_unsupported`,
            language,
          ),
        };
      standing.set(key, {
        state: people.length > 0 ? "rows" : "none_declared",
        stated_count: String(people.length),
        incomplete_words: null,
        rows: people.map((entry, index) => ({
          row_index: String(index),
          facts: entry.person
            ? entry.person.facts.map((fact) => ({
                leaf: fact.field_key,
                path: `${key}.${index}.${fact.field_key}`,
                value: fact.value,
                masked: false,
              }))
            : entry.facts.map((fact) => ({
                ...fact,
                path: `${key}.${index}.${fact.leaf}`,
              })),
        })),
      });
      revision += 1;
      if (lost) {
        lost = false;
        throw { code: "unknown" };
      }
    },
    takes: (edit) =>
      edit.kind === "descendants" ||
      edit.kind === "ascendants" ||
      (edit.kind === "field" && answers.has(edit.path)),
    writes: () => taken,
    readCount: () => reads,
    refuseNext(next) {
      refusal = next;
    },
    loseNextAnswer() {
      lost = true;
    },
    drafts: () => draftsRead,
    refuseNextDraft() {
      refuseDraft = true;
    },
  };
  if (typeof window !== "undefined")
    window.__scenarioHousehold = {
      refuseNext: fixture.refuseNext,
      loseNextAnswer: fixture.loseNextAnswer,
      writes: fixture.writes,
      reads: fixture.readCount,
      drafts: fixture.drafts,
      refuseNextDraft: fixture.refuseNextDraft,
    };
  return fixture;
}
