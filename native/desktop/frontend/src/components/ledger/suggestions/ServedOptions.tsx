// The options of a native select whose values the ledger serves. A stored
// value the list does not carry stays on offer so it is never lost, shown as
// itself while the list is not served. While the list is being read or could
// not be, the select says so instead of offering a list of its own.

import { useStrings } from "../../../shell/strings";
import { vocabularyEmpty } from "../movements/movementWords";
import { useVocabulary } from "./SuggestionsProvider";

export function ServedOptions({
  values,
  stored,
  label,
}: {
  values: readonly string[];
  /** The value the field holds now, if any. */
  stored?: string | null;
  label(value: string): string;
}) {
  const t = useStrings();
  const vocabulary = useVocabulary();
  const held = stored && !values.includes(stored) ? stored : null;
  return (
    <>
      {held !== null && (
        <option value={held}>
          {vocabulary.state === "ready" ? label(held) : held}
        </option>
      )}
      {values.length === 0 && vocabulary.state !== "ready" && (
        <option value="" disabled>
          {vocabularyEmpty(t, vocabulary, "", 0)}
        </option>
      )}
      {values.map((value) => (
        <option key={value} value={value}>
          {label(value)}
        </option>
      ))}
    </>
  );
}
