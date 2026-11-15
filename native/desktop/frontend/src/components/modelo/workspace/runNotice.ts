import type { Translate } from "../../../shell/strings";
import type { OperationRun } from "../dialogs/operationRun";
import type { HistoryNotice } from "./HistoryView";

/** What an operation came to, said for the person; null when it settled. */
export function runNotice(
  t: Translate,
  run: OperationRun<unknown>,
): HistoryNotice {
  switch (run.kind) {
    case "settled":
    case "saved_unread":
      return null;
    case "refused":
      // The backend words why; the window shows it as served, with the
      // movement it names one step away.
      return {
        tone: "warning",
        words: run.words ?? t("workspace.modelo.outcome.refused"),
        ...(run.step?.kind === "open_movement"
          ? {
              movement: {
                transactionId: run.step.transaction_id,
                words: run.step.words,
              },
            }
          : {}),
        ...(run.step?.kind === "open_iva_wallet_opening_balance"
          ? {
              openingBalance: {
                modelo: run.step.modelo,
                filingYear: run.step.filing_year,
                periodCode: run.step.period_code,
                words: run.step.words,
              },
            }
          : {}),
        ...(run.step?.kind === "open_iva_wallet"
          ? {
              ivaWallet: {
                workUnitId: run.step.work_unit_id,
                words: run.step.words,
              },
            }
          : {}),
      };
    case "not_sent":
      return {
        tone: "warning",
        words: t("workspace.modelo.outcome.failed"),
      };
    case "unknown":
      return null;
  }
}
