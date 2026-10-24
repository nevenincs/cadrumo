// The reads the movements grid makes beside its period window: the
// movements the product's own filters keep, how many a search finds in
// other periods, and the own accounts a filter offers. Each answer is for
// one profile and is dropped with it; an answer to a read no longer asked
// for is not shown.

import { useEffect, useState } from "react";
import type { JsonObject, LedgerPort } from "./ledger";
import {
  isPeriodCode,
  periodFilters,
  type LedgerPeriod,
} from "./ledgerGrammar";
import {
  readAnswer,
  readWindow,
  scopeKey,
  scopeOfKey,
  type LedgerReadFailure,
  type LedgerWindowScope,
} from "./ledgerWindow";

/** The movements of a window that the product's filters keep. */
export type Membership =
  | { kind: "none" }
  | { kind: "reading" }
  | { kind: "ready"; ids: ReadonlySet<string> }
  | { kind: "failed"; failure: LedgerReadFailure };

type Asked = [
  reader: string,
  year: number | null,
  code: string | null,
  scopes: string[],
  read: number,
];
const periodOfAsked = (year: number | null, code: string | null) =>
  year !== null && code !== null && isPeriodCode(code) ? { year, code } : null;

/**
 * Reads, for `period`, the movements each of `scopes` keeps, and joins
 * them: a movement any scope keeps is kept. No scope asks for nothing.
 * `read` names the window read the answer belongs to, so a window read
 * again reads its members again.
 */
export function useLedgerMembership(
  port: LedgerPort | undefined,
  reader: string | null,
  period: LedgerPeriod | null,
  scopes: readonly LedgerWindowScope[],
  read: number | null,
): Membership {
  const key =
    scopes.length > 0 && reader !== null && read !== null
      ? JSON.stringify([
          reader,
          period?.year ?? null,
          period?.code ?? null,
          scopes.map(scopeKey),
          read,
        ] satisfies Asked)
      : null;
  const [state, setState] = useState<{ key: string; membership: Membership }>({
    key: "",
    membership: { kind: "none" },
  });
  useEffect(() => {
    if (!port || key === null) return;
    const [, year, code, scoped] = JSON.parse(key) as Asked;
    const within = periodOfAsked(year, code);
    let active = true;
    void (async () => {
      const ids = new Set<string>();
      for (const scope of scoped) {
        const answer = await readWindow(
          port,
          within,
          Infinity,
          scopeOfKey(scope),
        );
        if (!active) return;
        if (answer.kind === "failed") {
          setState({
            key,
            membership: { kind: "failed", failure: answer.failure },
          });
          return;
        }
        for (const row of answer.rows) ids.add(row.transaction.transaction_id);
      }
      if (active) setState({ key, membership: { kind: "ready", ids } });
    })();
    return () => {
      active = false;
    };
  }, [port, key]);
  if (key === null) return { kind: "none" };
  return state.key === key ? state.membership : { kind: "reading" };
}

/** How long a search rests before the product is asked about it. */
const SEARCH_REST_MS = 400;

/**
 * How many movements outside `period` the product's own text filter finds
 * for `text`: every period's count less the period's own. Null while it is
 * not known, and for "All periods", which has no other period.
 */
export function useSearchElsewhere(
  port: LedgerPort | undefined,
  reader: string | null,
  period: LedgerPeriod | null,
  text: string,
): number | null {
  const query = text.trim();
  const key =
    reader !== null && period !== null && query !== ""
      ? JSON.stringify([reader, period.year, period.code, query])
      : null;
  const [state, setState] = useState<{ key: string; count: number | null }>({
    key: "",
    count: null,
  });
  useEffect(() => {
    if (!port || key === null) return;
    const [, year, code, wanted] = JSON.parse(key) as [
      string,
      number,
      string,
      string,
    ];
    const within = periodOfAsked(year, code);
    if (!within) return;
    let active = true;
    const timer = window.setTimeout(() => {
      const total = async (filters: string[]) => {
        try {
          const answer = readAnswer(
            await port.submit("ledger.list", {
              filters,
              limit: 1,
              offset: 0,
            }),
          );
          return answer.kind === "answer" ? answer.result.total : null;
        } catch {
          // An unanswered count is not known: no hint is shown.
          return null;
        }
      };
      void (async () => {
        const clause = `text=${wanted}`;
        const everywhere = await total([clause]);
        const here = await total([...periodFilters(within), clause]);
        if (!active) return;
        setState({
          key,
          count:
            everywhere === null || here === null
              ? null
              : Math.max(0, everywhere - here),
        });
      })();
    }, SEARCH_REST_MS);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [port, key]);
  return key !== null && state.key === key ? state.count : null;
}

/** An own account, as a filter names it. */
export type OwnAccountChoice = { id: string; label: string };

/** The profile's own accounts, read when `wanted` first holds. Null while
 * they are not read, or when they could not be. */
export function useOwnAccounts(
  port: LedgerPort | undefined,
  reader: string | null,
  wanted: boolean,
): OwnAccountChoice[] | null {
  const [state, setState] = useState<{
    reader: string | null;
    accounts: OwnAccountChoice[] | null;
  }>({ reader: null, accounts: null });
  const held = state.reader === reader ? state.accounts : null;
  const ask = wanted && reader !== null && held === null;
  useEffect(() => {
    if (!port || !ask) return;
    let active = true;
    void (async () => {
      let accounts: OwnAccountChoice[] | null = null;
      try {
        const answer = readAnswer(
          await port.submit("ledger.own_account", { action: "list" }),
        );
        if (answer.kind === "answer") accounts = accountsOf(answer.result);
      } catch {
        // Unread, the filter offers no account to choose.
      }
      if (active && accounts) setState({ reader, accounts });
    })();
    return () => {
      active = false;
    };
  }, [port, ask, reader]);
  return held;
}

function accountsOf(result: JsonObject): OwnAccountChoice[] {
  const listed = Array.isArray(result.accounts) ? result.accounts : [];
  const accounts: OwnAccountChoice[] = [];
  for (const entry of listed) {
    if (!entry || typeof entry !== "object" || Array.isArray(entry)) continue;
    const id = entry.own_account_id;
    const label = entry.label;
    if (typeof id === "string" && typeof label === "string")
      accounts.push({ id, label });
  }
  return accounts;
}
