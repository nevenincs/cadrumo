import { Channel, invoke } from "@tauri-apps/api/core";
import type { ShellToken, TokenHeader } from "../ipc/contract";
import type { HostCall } from "./hostCall";
import type {
  LedgerDropSignal,
  LedgerOutcome,
  LedgerPort,
  LedgerResult,
  LedgerReview,
} from "./ledger";

const TOKEN_HEADER: TokenHeader = "x-cadrumo-token";

/** The ledger port over the desktop host's ledger commands. Nothing here
 * keeps a result, a review, a token's file or an account number. */
export function tauriLedger(
  token: ShellToken | null,
  call: HostCall,
): LedgerPort {
  return {
    async submit(definition, payload) {
      const outcome = await call("ledger_submit", { definition, payload });
      // The runtime decoded the request against this definition's registered
      // contract and published its result under that contract's schema.
      return outcome as LedgerOutcome<LedgerResult<typeof definition>>;
    },
    observe: (operation) => call("ledger_observe", { operation }),
    async review<Review>(operation: string) {
      const review = await call("ledger_review", { operation });
      return review as LedgerReview<Review>;
    },
    answer: (operation, reviewDigest, decision) =>
      call("ledger_answer", { operation, reviewDigest, decision }),
    cancel: (operation, revision) =>
      call("ledger_cancel", { operation, revision }),
    pickFiles: (purpose, pick, filterLabel) =>
      call("ledger_files_pick", { purpose, pick, filterLabel }),
    saveFile: (format, filterLabel, suggestedName) =>
      call("ledger_files_save", {
        format,
        filterLabel,
        suggestedName: suggestedName ?? null,
      }),
    forgetFiles: (tokens) =>
      call("ledger_files_forget", { tokens }).then(() => undefined),
    async observeDrops(purpose, listener) {
      let active = true;
      const updates = new Channel<LedgerDropSignal>();
      updates.onmessage = (signal) => {
        if (active) listener(signal);
      };
      const subscription = await call("ledger_drop_observe", {
        purpose,
        updates,
      });
      return () => {
        active = false;
        void call("ledger_drop_unobserve", { subscription }).catch(
          () => undefined,
        );
      };
    },
    // The change's bytes are the whole raw body, with the token in a header,
    // and are overwritten as soon as the call settles.
    async changeOwnAccount(change) {
      try {
        if (!token) throw new Error("Missing desktop launch token.");
        return await invoke<LedgerOutcome>("ledger_own_account", change, {
          headers: { [TOKEN_HEADER]: token },
        });
      } finally {
        change.fill(0);
      }
    },
  };
}
