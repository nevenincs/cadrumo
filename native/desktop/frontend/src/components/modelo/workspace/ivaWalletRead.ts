import { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import type { ModeloPort } from "../../../shell/modelo";
import type { ModeloIvaWalletBalanceProjection } from "../../../shell/modeloContract/modeloIvaWallet";
import type { ModeloWorkbenchFormProjectionV1 } from "../../../shell/modeloContract/modeloWorkForm";
import {
  walletWriteKey,
  type ModeloWriteHolds,
} from "../../../shell/modeloWriteHolds";
import { useModeloBlockingWriteHold } from "../WriteHoldNotice";
import { runOperation } from "../dialogs/operationRun";

/** The backend offers the profile's IVA register and admits each action. */
export const hasIvaWallet = (envelope: ModeloWorkbenchFormProjectionV1) =>
  envelope.form.form.offers_iva_wallet;

type BalanceRead =
  | { phase: "held" }
  | { phase: "reading" }
  | { phase: "ready"; result: ModeloIvaWalletBalanceProjection }
  | { phase: "failed"; words: string | null };

/** Balance reads never settle a write hold. Recovery also needs the owning form. */
export function useIvaWalletBalance(
  port: ModeloPort,
  holds: ModeloWriteHolds,
  year: number | null,
) {
  const [attempt, setAttempt] = useState(0);
  const blocking = useModeloBlockingWriteHold(holds, walletWriteKey);
  const version = useSyncExternalStore(
    holds.subscribe,
    () => holds.admissionVersion(walletWriteKey),
    () => 0,
  );
  const owner = useMemo(
    () => ({ port, holds, year, blocking, version, attempt }),
    [port, holds, year, blocking, version, attempt],
  );
  const [answer, setAnswer] = useState<{
    owner: object;
    read: BalanceRead;
  } | null>(null);
  useEffect(() => {
    if (year === null || blocking) return;
    let active = true;
    void runOperation(
      port,
      () => port.submit("modelo.iva-wallet.balance", { as_of_year: year }),
      () => active,
    ).then((outcome) => {
      if (!active || holds.admissionVersion(walletWriteKey) !== version) return;
      setAnswer({
        owner,
        read:
          outcome.kind === "settled"
            ? { phase: "ready", result: outcome.result }
            : {
                phase: "failed",
                words: outcome.kind === "refused" ? outcome.words : null,
              },
      });
    });
    return () => {
      active = false;
    };
  }, [port, holds, year, owner, version, blocking]);
  const read: BalanceRead = blocking
    ? { phase: "held" }
    : answer?.owner === owner
      ? answer.read
      : { phase: "reading" };
  return { read, reload: () => setAttempt((value) => value + 1) };
}
