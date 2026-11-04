// The sentences the activity-asset register serves, for the scenario register:
// what the backend said for each reason with its facts, each remedy, each
// handoff interval and each reason a handoff leaves elements out, in each
// language, recorded in `fixtures/assetsServedWords.json` and looked up by
// exactly what was asked. This decides and words nothing: a question not
// recorded answers undefined, as a sentence the backend could not say whole,
// and is told to the hook that records it. A test in the owning Python package
// holds every recorded sentence equal to the backend's own and records the
// questions the fixtures could not answer.

import type { OutputLanguage } from "../shell/ledger";
import type { ReasonFact } from "../shell/ledgerSetup";
import recorded from "./fixtures/assetsServedWords.json" with { type: "json" };

/** What the register is asked to say. */
export type WordsQuestion =
  | { kind: "reason"; key: string; facts: ReasonFact[] }
  | { kind: "remedy"; field_key: string }
  | {
      kind: "gap";
      gap_kind: string;
      name: string | null;
      covered_from: string;
      covered_through: string;
      accrued: string | null;
    }
  | { kind: "partial"; count: number }
  | {
      kind: "left_out";
      reason: string;
      /** The name the register holds for each element, null for one it holds none for. */
      names: (string | null)[];
    };

/** Told of each question the recording does not hold, so it can be recorded. */
type Unrecorded = (question: WordsQuestion) => void;
const unrecordedHook = () =>
  (globalThis as { __assetWordsUnrecorded?: Unrecorded })
    .__assetWordsUnrecorded;

const entries = recorded.entries as unknown as Record<
  string,
  Record<string, string | null>
>;

/** The question as it is keyed in the recording: facts in the order served. */
export const keyOf = (question: WordsQuestion): string =>
  JSON.stringify(question);

/** The sentence recorded for `question` in `language`: a string; null where
 * the backend served none; undefined where the recording holds no answer. */
export function said(
  question: WordsQuestion,
  language: OutputLanguage,
): string | null | undefined {
  const found = entries[keyOf(question)];
  if (found === undefined) {
    unrecordedHook()?.(question);
    return undefined;
  }
  return found[language];
}
