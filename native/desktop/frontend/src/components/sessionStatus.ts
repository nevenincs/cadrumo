import { facts } from "../shell/compose";
import { sessionFailedText } from "../shell/sessionWords";
import type { AccountPhase, SignInController } from "../shell/signIn";
import type { Translate } from "../shell/strings";
import { accountLabel } from "./accountWords";
import type { SessionPhase } from "./PaneHeader";
import type { TerminalStatus } from "./TerminalPane";

/** The exit code of a session that has exited, null when it is unknown. */
const exitCode = (status: TerminalStatus): number | null | undefined =>
  status.phase === "exited" ? status.code : undefined;

/** The host's code for why a session could not start or carry on, when it has
 * failed; `sessionFailedText` words it. */
const failure = (status: TerminalStatus): string | undefined =>
  status.phase === "failed" ? status.message : undefined;

/** What a session's header says beside its state: how it ended, or why it
 * could not start. */
export function sessionNote(
  t: Translate,
  status: TerminalStatus,
): string | undefined {
  const reason = failure(status);
  if (reason !== undefined) return sessionFailedText(t, reason);
  const code = exitCode(status);
  if (code === undefined) return undefined;
  return facts(t, [
    t("desktop.session.exited", { code: code ?? "?" }),
    t("desktop.session.enter_restarts"),
  ]);
}

/** The TUI's state as its header and its dock tab say it. While the account
 * withholds the TUI there is no session: the account's phase is said, not
 * the last session's. */
export function tuiStatus(
  t: Translate,
  account: SignInController,
  phase: AccountPhase,
  status: TerminalStatus,
): { phase: SessionPhase; note: string | undefined } {
  return account.gated
    ? {
        phase:
          phase === "checking" ||
          phase === "starting" ||
          account.startingServices
            ? "starting"
            : "unavailable",
        note: t(accountLabel(phase) ?? "desktop.account.unknown"),
      }
    : { phase: status.phase, note: sessionNote(t, status) };
}
