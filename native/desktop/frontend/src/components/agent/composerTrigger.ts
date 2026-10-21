/** Where a token being typed begins in the text before the caret, and what
 * has been typed of it after its trigger. */
export type TriggerMatch = { start: number; query: string };

/** Finds the token a suggestion list answers in the text before the caret. */
export type TriggerMatcher = (before: string) => TriggerMatch | null;

/**
 * A token that starts with `char` at the start of the field or after
 * whitespace and runs, with no whitespace in it, up to the caret. Its query
 * is what follows the trigger, which may be nothing yet.
 */
export function charTrigger(char: string): TriggerMatcher {
  return (before) => {
    const start = before.lastIndexOf(char);
    if (start < 0) return null;
    if (start > 0 && !/\s/.test(before[start - 1] ?? "")) return null;
    const query = before.slice(start + char.length);
    return /\s/.test(query) ? null : { start, query };
  };
}
