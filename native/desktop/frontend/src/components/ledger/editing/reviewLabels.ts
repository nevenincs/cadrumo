import type { LedgerRow } from "../../../shell/ledger";
import type { Translate } from "../../../shell/strings";
import { formatCount } from "../../../shared/numbers";
import type { LockProgress } from "./useLedgerApply";

/** A movement as the review names it. */
export function titleOf(
  t: Translate,
  rows: ReadonlyMap<string, LedgerRow>,
  id: string,
): string {
  return (
    rows.get(id)?.transaction.description ??
    t("desktop.ledger.apply.gone_movement")
  );
}

/** How far a read of the staged movements' locks has got, in words. */
export const lockProgress = (
  t: Translate,
  locale: string,
  locks: LockProgress,
) => {
  return t("desktop.ledger.apply.checking_locks", {
    done: formatCount(locale, locks.done),
    total: formatCount(locale, locks.total),
  });
};
