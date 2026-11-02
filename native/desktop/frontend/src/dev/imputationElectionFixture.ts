import fixtures from "./fixtures/imputationElection.json";
import type {
  ElectionAnswer,
  ImputationElection,
  ProfileCompanionPort,
} from "../shell/profileHousehold";
import type { ProfileChange } from "../shell/userProfile";

// The imputation election the application read for synthetic profiles through
// `user-profile.imputation-election.read`, in every language, and the details
// of the refusals its change settled with. Regenerate with
// dev.desktop_imputation_election_fixture; never invent fields here. The
// fixture keeps what a change states and answers the next read with it, so a
// story or a scenario sees a write land.

export type ElectionScenario = keyof typeof fixtures.reads;

/** The states the application read, for a page to choose among. */
export const ELECTION_SCENARIOS = Object.keys(
  fixtures.reads,
) as ElectionScenario[];

declare global {
  interface Window {
    __scenarioElection?: {
      /** The next change is refused with the application's sentence for it. */
      refuseNext(refusal: ElectionRefusal): void;
      /** The next change lands but its answer never arrives. */
      loseNextAnswer(): void;
      /** What the changes sent so far stated, in order. */
      writes(): ProfileChange[];
      /** The elections read so far. */
      reads(): number;
    };
  }
}

/** A refusal the application settled the change with, as the host carries it
 * to the window: its code and the finished sentence the application served. */
export type ElectionRefusal = keyof typeof fixtures.refusals;

type Statement = { ejercicio: number; value: string };

export type ElectionFixture = {
  reads: Pick<ProfileCompanionPort, "imputationElection">;
  change(change: ProfileChange): Promise<void>;
  /** The changes the fixture took, in order. */
  writes(): ProfileChange[];
  /** Reads answered so far. */
  readCount(): number;
  /** The next change is rejected with this refusal and changes nothing. */
  refuseNext(refusal: ElectionRefusal): void;
  /** The next change lands but its answer never arrives: the outcome is
   * unknown to the window. */
  loseNextAnswer(): void;
};

function read(scenario: ElectionScenario, language: string) {
  const byLanguage = fixtures.reads[scenario] as Record<string, unknown>;
  return structuredClone(
    (byLanguage[language] ?? byLanguage.en) as ImputationElection,
  );
}

function answer(token: string | null): ElectionAnswer {
  return token === null
    ? { state: "undeclared", value: null }
    : { state: "declared", value: token };
}

/** The refusal's sentence in the language the profile page speaks. */
function refusalWords(refusal: ElectionRefusal, language: string): string {
  const details = fixtures.refusals[refusal] as Record<
    string,
    { refusal_words?: string }
  >;
  return (details[language] ?? details.en)?.refusal_words ?? "";
}

/**
 * An election fixture that starts in `scenario`. `language` is the one the
 * words of a refusal are served in; reads carry their own.
 */
export function imputationElectionFixture(
  scenario: ElectionScenario = "undeclared",
  language = "en",
): ElectionFixture {
  const start = read(scenario, language);
  let revision = start.record_revision;
  let criterion = start.criterion;
  let accounting = start.codigo_comercio_accounting;
  let statements: Statement[] = start.criterion_statements.map((s) => ({
    ...s,
  }));
  const taken: ProfileChange[] = [];
  let reads = 0;
  let refusal: ElectionRefusal | null = null;
  let lost = false;
  // The witness the application read the profile at, then one per change.
  let witness = start.content_digest;

  const fixture: ElectionFixture = {
    reads: {
      imputationElection: async (_profile, taxYear, asked) => {
        reads += 1;
        const election = read(scenario, asked);
        return {
          ...election,
          tax_year: taxYear,
          record_revision: revision,
          content_digest: witness,
          criterion,
          codigo_comercio_accounting: accounting,
          criterion_statements: statements,
        };
      },
    },
    async change(change) {
      taken.push(change);
      if (refusal) {
        const settled = refusal;
        refusal = null;
        throw {
          code: settled === "stale" ? "conflict" : "refused",
          refusal_words: refusalWords(settled, language),
        };
      }
      if (change.edit.kind !== "imputation_election") throw { code: "refused" };
      if (
        change.expected_revision !== revision ||
        change.expected_content_digest !== witness
      )
        throw { code: "conflict" };
      const { criterion: next, codigo_comercio_accounting: nextAccounting } =
        change.edit;
      const year = change.edit.tax_year;
      if (next !== null) {
        criterion = answer(next === "" ? null : next);
        statements = statements.filter((s) => s.ejercicio !== year);
        if (next !== "")
          statements = [...statements, { ejercicio: year, value: next }].sort(
            (a, b) => a.ejercicio - b.ejercicio,
          );
      }
      if (nextAccounting !== null)
        accounting = answer(nextAccounting === "" ? null : nextAccounting);
      revision += 1;
      witness = `e${revision.toString(16).padStart(63, "0")}`;
      if (lost) {
        lost = false;
        throw { code: "unknown" };
      }
    },
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
    window.__scenarioElection = {
      refuseNext: fixture.refuseNext,
      loseNextAnswer: fixture.loseNextAnswer,
      writes: fixture.writes,
      reads: fixture.readCount,
    };
  return fixture;
}
