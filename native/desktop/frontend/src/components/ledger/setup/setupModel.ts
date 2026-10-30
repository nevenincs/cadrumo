// The Setup sections' pure decisions: how a rule's plain words become the
// pattern the product matches and back, what a rule from a selection starts
// from, where a rule goes in the order and what writes move it there, which
// loaded movements a pattern matches, the shape of an own account number,
// and how a settled call reads. Nothing here writes or draws.

import type {
  JsonObject,
  LedgerDefinitionId,
  LedgerFailureCode,
  LedgerOutcome,
  LedgerPort,
  LedgerRequest,
  LedgerResult,
  LedgerRow,
} from "../../../shell/ledger";
import { ledgerFailure } from "../../../shell/ledger";
import {
  compareDecimal,
  parseDecimal,
  type Parsed,
} from "../../../shell/ledgerGrammar";
import type { RuleSeed } from "../../../shell/ledgerCommands";
import type { LedgerRuleRow } from "../../../shell/ledgerSetup";
import { normalisedDescription } from "../movements/movementsModel";

// ---- Calls ---------------------------------------------------------------

/** How one call to the ledger ended, as a Setup form says it. */
export type SetupCall<Result> =
  | { kind: "done"; result: Result }
  /** Settled without changing anything; `detail` is the refusal's own
   * result, where the definition declares one. */
  | { kind: "refused"; reason: string | null; detail: JsonObject | null }
  /** A write sent and not seen to settle: it may have been saved. */
  | { kind: "unknown" }
  /** A write that saved, whose answer was not read. */
  | { kind: "saved_unread" }
  | { kind: "failed"; code: LedgerFailureCode; reason: string | null };

/** What a settled outcome means for a call that `writes` or only reads. A
 * write still running when the host stops following it may have been
 * saved; a read that did not answer answered nothing. */
export function callOutcome<Result>(
  outcome: LedgerOutcome<Result>,
  writes: boolean,
): SetupCall<Result> {
  if (outcome.kind === "settled")
    return { kind: "done", result: outcome.result };
  if (outcome.kind === "refused")
    return {
      kind: "refused",
      reason: outcome.reason,
      detail: (outcome.detail as JsonObject | null) ?? null,
    };
  return writes
    ? { kind: "unknown" }
    : { kind: "failed", code: "unavailable", reason: null };
}

/** The same for a call that was rejected before it answered. */
export function callFailure<Result>(error: unknown): SetupCall<Result> {
  const failure = ledgerFailure(error);
  if (failure.code === "unknown") return { kind: "unknown" };
  if (failure.code === "saved_unread") return { kind: "saved_unread" };
  return {
    kind: "failed",
    code: failure.code,
    reason: failure.reason ?? null,
  };
}

/** Submits one Setup operation and says how it ended. One attempt: an
 * unknown write is never sent again from here. */
export async function setupCall<D extends LedgerDefinitionId>(
  port: LedgerPort,
  definition: D,
  payload: LedgerRequest<D>,
  writes: boolean,
): Promise<SetupCall<LedgerResult<D>>> {
  try {
    return callOutcome(await port.submit(definition, payload), writes);
  } catch (error) {
    return callFailure(error);
  }
}

// ---- Rule patterns -------------------------------------------------------

const SPECIAL = /[\\^$.*+?()[\]{}|\-/#&~]/g;
const WORD_GAP = "\\s+";

/** The pattern that finds `words` in a description, in that order, with any
 * spacing between them, and nothing else: every character the expression
 * grammar reads as an instruction is written as itself. */
export function wordsPattern(words: string): string {
  return words
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => word.replace(SPECIAL, (found) => `\\${found}`))
    .join(WORD_GAP);
}

/** The plain words a pattern stands for, where it was written from plain
 * words; null for a pattern that uses the expression grammar itself. */
export function patternWords(pattern: string): string | null {
  // A space written as itself is a gap too, as a rule typed by hand has it.
  const parts = pattern.trim().split(/\\s\+| +/);
  const words: string[] = [];
  for (const part of parts) {
    if (part === "") return null;
    let word = "";
    for (let at = 0; at < part.length; at += 1) {
      const char = part[at]!;
      if (char === "\\") {
        const next = part[at + 1];
        if (next === undefined || !/[\\^$.*+?()[\]{}|\-/#&~]/.test(next))
          return null;
        word += next;
        at += 1;
      } else if (/[\\^$.*+?()[\]{}|]/.test(char) || /\s/.test(char))
        return null;
      else word += char;
    }
    words.push(word);
  }
  return words.join(" ");
}

/** The pattern as this window can try it on loaded movements: the
 * product matches ignoring case, anywhere in the description. Null where
 * the expression uses grammar this window does not read the same way. */
export function patternMatcher(pattern: string): RegExp | null {
  // Named groups and inline flags are spelled differently here.
  if (/\(\?P|\(\?[aiLmsux]+\)/.test(pattern)) return null;
  try {
    return new RegExp(pattern, "iu");
  } catch {
    return null;
  }
}

/** The active movements of `rows` whose description `pattern` finds,
 * whatever their classification. Null where the window cannot try the
 * pattern. */
export function patternHits(
  pattern: string,
  rows: readonly LedgerRow[],
): string[] | null {
  const matcher = patternMatcher(pattern);
  if (!matcher) return null;
  return rows
    .filter(
      (row) =>
        row.transaction.lifecycle_state === "ACTIVE" &&
        matcher.test(row.transaction.description),
    )
    .map((row) => row.transaction.transaction_id);
}

/** The movements of `rows` a rule with `pattern` would classify now: the
 * active ones still to classify whose description it finds. Null where the
 * window cannot try the pattern. */
export function patternMatches(
  pattern: string,
  rows: readonly LedgerRow[],
): string[] | null {
  const hits = patternHits(pattern, rows);
  if (hits === null) return null;
  const pending = new Set(
    rows
      .filter(
        (row) =>
          row.transaction.business_classification === "NOT_YET_PROCESSED",
      )
      .map((row) => row.transaction.transaction_id),
  );
  return hits.filter((id) => pending.has(id));
}

// ---- A rule from a selection ---------------------------------------------

/** The prefilled rule: the words every chosen description shares, and the
 * classification and category they share, where they do. */
export type RulePrefill = {
  words: string;
  classification: string | null;
  categoryId: string | null;
};

const DECIDED = new Set(["BUSINESS", "PERSONAL", "MIXED"]);

/** The longest run of whole words found in every description, without
 * the digits and references that tell one payment from the next. */
export function commonWords(descriptions: readonly string[]): string {
  const split = descriptions
    .map((text) => normalisedDescription(text).split(/\s+/).filter(Boolean))
    .filter((words) => words.length > 0);
  if (split.length === 0) return "";
  const [first, ...rest] = split;
  const has = (words: string[], run: string[]) => {
    outer: for (let at = 0; at + run.length <= words.length; at += 1) {
      for (let k = 0; k < run.length; k += 1)
        if (words[at + k] !== run[k]) continue outer;
      return true;
    }
    return false;
  };
  for (let length = first!.length; length > 0; length -= 1)
    for (let start = 0; start + length <= first!.length; start += 1) {
      const run = first!.slice(start, start + length);
      if (rest.every((words) => has(words, run))) return run.join(" ");
    }
  return "";
}

/** The rule a selection suggests. Nothing is chosen for the person where
 * the movements disagree. */
export function rulePrefill(
  seed: RuleSeed,
  rows: ReadonlyMap<string, LedgerRow>,
): RulePrefill {
  const chosen = seed.ids
    .map((id) => rows.get(id))
    .filter((row): row is LedgerRow => row !== undefined);
  const shared = <T>(read: (row: LedgerRow) => T): T | null => {
    const values = new Set(chosen.map(read));
    return values.size === 1 ? ([...values][0] ?? null) : null;
  };
  const classification = shared(
    (row) => row.transaction.business_classification,
  );
  return {
    words: commonWords(chosen.map((row) => row.transaction.description)),
    classification:
      classification !== null && DECIDED.has(classification)
        ? classification
        : null,
    categoryId: shared((row) => row.transaction.category_id),
  };
}

// ---- Rule order ----------------------------------------------------------

/** The rules in the order they run: the lower priority first, and the
 * older first where two share one. */
export function ruleOrder(rules: readonly LedgerRuleRow[]): LedgerRuleRow[] {
  return [...rules].sort(
    (a, b) =>
      a.priority - b.priority ||
      (a.created_at < b.created_at ? -1 : a.created_at > b.created_at ? 1 : 0),
  );
}

const STEP = 10;

/** The priority that puts a newly written rule at `position` among
 * `others`, already in order: written now, it runs after every rule of
 * the same priority. Null where no number fits between its neighbours. */
export function priorityAt(
  others: readonly LedgerRuleRow[],
  position: number,
): number | null {
  const before = others[position - 1];
  const after = others[position];
  if (!after) return before ? before.priority + STEP : 100;
  // At least the rule before it, which it then follows as the newer, and
  // below the rule after it.
  const lowest = before ? before.priority : 1;
  const highest = after.priority - 1;
  if (highest < lowest) return null;
  return before
    ? Math.min(highest, before.priority + STEP)
    : Math.max(lowest, after.priority - STEP);
}

/** Whether `rules` hold the rule a `ledger.rule.add` sent, at the
 * priority it sent: its pattern, classification and category are its id,
 * so adding the same three again only moves it. */
export function ruleStored(
  rules: readonly LedgerRuleRow[],
  sent: {
    description_pattern: string;
    classification: string;
    category_id?: string | null;
    priority?: number;
  },
): boolean {
  return rules.some(
    (rule) =>
      rule.description_pattern === sent.description_pattern &&
      rule.classification === sent.classification &&
      (rule.category_id ?? null) === (sent.category_id ?? null) &&
      (sent.priority === undefined || rule.priority === sent.priority),
  );
}

/** One rule written again with a new priority: the same pattern,
 * classification and category, so the same rule. */
export type RuleWrite = { rule: LedgerRuleRow; priority: number };

/** The writes that move the rule at `from` to `to` in `ordered`: one where
 * a number fits, otherwise every rule numbered again in steps of ten,
 * leaving out those already on their number. */
export function reorderWrites(
  ordered: readonly LedgerRuleRow[],
  from: number,
  to: number,
): RuleWrite[] {
  if (from === to || !ordered[from] || to < 0 || to >= ordered.length)
    return [];
  const moved = ordered[from]!;
  const others = ordered.filter((_, at) => at !== from);
  const single = priorityAt(others, to);
  if (single !== null) return [{ rule: moved, priority: single }];
  const next = [...others];
  next.splice(to, 0, moved);
  return next
    .map((rule, at) => ({ rule, priority: (at + 1) * STEP }))
    .filter((write) => write.rule.priority !== write.priority);
}

// ---- Own accounts --------------------------------------------------------

/** An account number as the person typed it, without spaces, in capitals. */
export const ibanText = (raw: string) => raw.replace(/\s+/g, "").toUpperCase();

/** Why a typed account number cannot be one, checked here before it is
 * sent: its shape and its control digits. The product checks it again. */
export function ibanProblem(raw: string): "shape" | "check" | null {
  const iban = ibanText(raw);
  if (!/^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$/.test(iban)) return "shape";
  const moved = iban.slice(4) + iban.slice(0, 4);
  let rest = 0;
  for (const char of moved) {
    const digits = /\d/.test(char) ? char : String(char.charCodeAt(0) - 55);
    for (const digit of digits) rest = (rest * 10 + Number(digit)) % 97;
  }
  return rest === 1 ? null : "check";
}

// ---- Numbers -------------------------------------------------------------

/** A percentage written in points, as the registers keep it: `92` is
 * ninety-two per cent, from 0 to 100. */
export function parsePoints(raw: string): Parsed<string> {
  const parsed = parseDecimal(raw.replace(/\s*%$/, ""), {
    decimals: 4,
    zero: true,
  });
  if (parsed.kind === "value" && compareDecimal(parsed.value, "100") > 0)
    return { kind: "refused", refusal: { key: "percent_above_100", raw } };
  return parsed;
}

/** A whole year of four digits, or null. */
export function wholeYear(raw: string): number | null {
  const text = raw.trim();
  return /^\d{4}$/.test(text) ? Number(text) : null;
}

/** A JSON object the person pasted or a picked file held, or why it is
 * not one. */
export function parseObject(
  text: string,
):
  | { kind: "value"; value: JsonObject }
  | { kind: "empty" }
  | { kind: "refused" } {
  if (text.trim() === "") return { kind: "empty" };
  try {
    const value: unknown = JSON.parse(text);
    return typeof value === "object" && value !== null && !Array.isArray(value)
      ? { kind: "value", value: value as JsonObject }
      : { kind: "refused" };
  } catch {
    return { kind: "refused" };
  }
}

/** The fields an activity asset's first revision needs, each left for the
 * person to fill: nothing is assumed. */
export function revisionSkeleton(): JsonObject {
  return {
    asset_id: null,
    revision_number: 1,
    acquisition: {
      observed_transaction_id: null,
      invoice_evidence_id: null,
      evidence_fingerprint: null,
    },
    acquisition_shape: null,
    asset_kind: null,
    basis: { stage: null, basis_amount: null, non_deductible_iva: null },
    residual_value: null,
    in_service_date: null,
    opening_history: { status: null },
    acquired_condition: null,
    amortization: { regime: null, method: null },
  };
}

/** A correction of `latest`: the next revision, naming the one it
 * supersedes, with its facts to change. */
export function correctionOf(latest: JsonObject, latestId: string): JsonObject {
  const number =
    typeof latest.revision_number === "number" ? latest.revision_number : 0;
  return {
    ...latest,
    revision_number: number + 1,
    supersedes_revision_id: latestId,
  };
}
