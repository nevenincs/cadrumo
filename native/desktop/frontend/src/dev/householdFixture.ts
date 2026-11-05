import fixtures from "@fixtures/desktop-household/household.json";
import type {
  HouseholdFact,
  HouseholdGroup,
  HouseholdLeaf,
  HouseholdQuestion,
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
// questions the product asks of the household), keeps what a replacement or an
// answer states and answers the next read with it, so a story or a scenario
// sees a write land.

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
    };
  }
}

/** What a hidden fact shows in place of its value, as the host masks it. */
const MASK = "••••••••";

type Item =
  | ({ kind: "family_group" } & Omit<HouseholdGroup, "rows">)
  | {
      kind: "family_row";
      group_key: string;
      row_index: string;
      facts: HouseholdFact[];
    }
  | ({ kind: "family_question" } & HouseholdQuestion);

type Stored = {
  group: Omit<HouseholdGroup, "rows">;
  rows: { row_index: string; facts: HouseholdFact[] }[];
};

export type HouseholdFixture = {
  reads: Pick<ProfileCompanionPort, "household">;
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
        },
        rows: [],
      });
    } else
      groups
        .find((entry) => entry.group.group_key === item.group_key)!
        .rows.push({ row_index: item.row_index, facts: item.facts });
  }
  return groups;
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
  const digest = () => `d${revision.toString(16).padStart(63, "0")}`;

  const household = (asked: string): ProfileHousehold => ({
    profile_id: fixtures.profile_id,
    record_revision: revision,
    content_digest: digest(),
    groups: assemble(itemsOf(scenario, asked)).map(({ group }) => {
      const now = standing.get(group.group_key)!;
      return {
        ...group,
        state: now.state,
        stated_count: now.stated_count,
        incomplete_words: now.incomplete_words,
        row_count: now.rows.length,
        rows: now.rows.map((row) => ({
          row_index: row.row_index,
          facts: row.facts.map((fact) =>
            fact.masked ? { ...fact, value: MASK } : { ...fact },
          ),
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
      // The sentences are the ones the application recorded for the same
      // two refusals of the group being replaced.
      if (group.max_rows !== null && edit.rows.length > group.max_rows)
        throw {
          code: "refused",
          refusal_words: refusalWords(`${edit.kind}_over_limit`, language),
        };
      if (
        edit.rows.some((row) =>
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
        state: edit.rows.length > 0 ? "rows" : "none_declared",
        stated_count: String(edit.rows.length),
        incomplete_words: null,
        rows: edit.rows.map((row, index) => ({
          row_index: String(index),
          facts: row.facts.map((fact) => ({
            leaf: fact.field_key,
            path: `${key}.${index}.${fact.field_key}`,
            value: fact.value,
            masked: false,
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
  };
  if (typeof window !== "undefined")
    window.__scenarioHousehold = {
      refuseNext: fixture.refuseNext,
      loseNextAnswer: fixture.loseNextAnswer,
      writes: fixture.writes,
      reads: fixture.readCount,
    };
  return fixture;
}
