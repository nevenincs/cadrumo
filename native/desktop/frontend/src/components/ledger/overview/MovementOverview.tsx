import type { LedgerPort, LedgerRow } from "../../../shell/ledger";
import { isTransactionPrefix } from "../../../shell/ledgerGrammar";
import type { OwnAccountChoice } from "../../../shell/ledgerMovementReads";
import { useStrings } from "../../../shell/strings";
import { useLedgerRead } from "../inspector/useInspectorReads";
import { EntryOverview, type OverviewAction } from "./EntryOverview";
import { movementOverview } from "./movementOverviewModel";

/**
 * The overview of one stored movement. It reads where the movement came
 * from and which declarations cite it, as the inspector does; everything
 * else is what the page already holds of it.
 */
export function MovementOverview({
  port,
  row,
  generation,
  issues,
  duplicate,
  accounts,
  unsaved,
  locale,
  action,
  onClose,
  onClosed,
}: {
  port: LedgerPort;
  row: LedgerRow;
  /** Which read of the window `row` comes from. */
  generation: number | string;
  /** What readiness found on it; null until readiness was measured. */
  issues: readonly string[] | null;
  duplicate: boolean;
  accounts: readonly OwnAccountChoice[] | null;
  /** Changes to it staged and not saved. */
  unsaved: number;
  locale: string;
  action: OverviewAction | null;
  onClose: () => void;
  onClosed?: (acted: boolean) => void;
}) {
  const t = useStrings();
  const id = row.transaction.transaction_id;
  const prefix = isTransactionPrefix(id) ? { transaction_prefix: id } : null;
  const track = useLedgerRead(
    port,
    "ledger.track",
    prefix,
    `${id}:${generation}`,
    true,
  );
  return (
    <EntryOverview
      model={movementOverview({
        t,
        locale,
        row,
        issues,
        duplicate,
        accounts,
        unsaved,
        track,
      })}
      action={action}
      onClose={onClose}
      {...(onClosed ? { onClosed } : {})}
    />
  );
}
