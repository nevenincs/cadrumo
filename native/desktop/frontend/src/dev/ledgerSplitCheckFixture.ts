// `ledger.split.check` for the fixtures. Stories type freely over movements whose
// amounts are generated, so a recording cannot hold each question: this stand-in
// works the answer out. the generated `ledgerSplitCheck.json` holds what the real
// backend answered, a test in the owning Python package holds that recording to
// the live answer, and a test here holds this stand-in to the recording.

import type {
  LedgerSplitCheckRequest,
  LedgerSplitCheckResult,
} from "../shell/ledgerMovementOperations";

const MOST_PARTS = 128;
const LONGEST_DESCRIPTION = 1024;
const PLAIN = /^\d+(\.\d{1,2})?$/;

function cents(text: string | null): bigint | null {
  if (text === null || !PLAIN.test(text.trim())) return null;
  const [whole, fraction = ""] = text.trim().split(".");
  return BigInt(whole!) * 100n + BigInt(fraction.padEnd(2, "0"));
}
function spelled(value: bigint): string {
  const fraction = (value % 100n)
    .toString()
    .padStart(2, "0")
    .replace(/0+$/, "");
  const whole = (value / 100n).toString();
  return fraction === "" ? whole : `${whole}.${fraction}`;
}

export function answerSplitCheck(
  parentAmount: string,
  parts: LedgerSplitCheckRequest["parts"],
  profileId: string,
): LedgerSplitCheckResult {
  const none = { index: null, max: null, difference: null, over: null };
  const result = (
    remainder: string | null,
    problem: Partial<NonNullable<LedgerSplitCheckResult["problem"]>> & {
      kind: NonNullable<LedgerSplitCheckResult["problem"]>["kind"];
    },
  ): LedgerSplitCheckResult => ({
    profile_id: profileId,
    remainder,
    problem: { ...none, ...problem },
    children: [],
  });
  const whole = cents(parentAmount)!;
  const open = parts.at(-1)?.amount === null;
  const named = open ? parts.slice(0, -1) : parts;
  const typed = named.map((part) => cents(part.amount ?? null));
  const left = open
    ? typed.every((amount) => amount !== null)
      ? typed.reduce((sum: bigint, amount) => sum - amount!, whole)
      : null
    : null;
  const remainder = left !== null && left > 0n ? spelled(left) : null;
  if (parts.length < 2 || parts.length > MOST_PARTS)
    return result(remainder, { kind: "count", max: MOST_PARTS });
  const unread = typed.indexOf(null);
  if (unread >= 0) return result(remainder, { kind: "amount", index: unread });
  if (open && left === 0n)
    return result(remainder, { kind: "amount", index: parts.length - 1 });
  if (open && left! < 0n)
    return result(remainder, {
      kind: "sum",
      difference: spelled(-left!),
      over: true,
    });
  const trimmed = parts.map((part) => (part.description ?? "").trim());
  const blank = trimmed.indexOf("");
  if (blank >= 0)
    return result(remainder, { kind: "description", index: blank });
  const long = trimmed.findIndex(
    (text) => [...text].length > LONGEST_DESCRIPTION,
  );
  if (long >= 0)
    return result(remainder, {
      kind: "description_long",
      index: long,
      max: LONGEST_DESCRIPTION,
    });
  const amounts: bigint[] = open
    ? [...(typed as bigint[]), left!]
    : (typed as bigint[]);
  const sum = amounts.reduce((total, amount) => total + amount, 0n);
  if (sum !== whole)
    return result(remainder, {
      kind: "sum",
      difference: spelled(sum > whole ? sum - whole : whole - sum),
      over: sum > whole,
    });
  const zero = amounts.indexOf(0n);
  if (zero >= 0) return result(remainder, { kind: "amount", index: zero });
  return {
    profile_id: profileId,
    remainder,
    problem: null,
    children: amounts.map((amount, at) => ({
      amount: spelled(amount),
      description: trimmed[at]!,
    })),
  };
}
