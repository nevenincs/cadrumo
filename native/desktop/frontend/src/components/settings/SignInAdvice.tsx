import { useStrings } from "../../shell/strings";
import {
  consoleCommand,
  type CliStateCause,
  type NextStep,
  type SignInCause,
} from "../../shell/providerSignInWords";

/** The sentence for each closed cause, in the same words for a sign-in
 * attempt and for a status read. */
const CAUSE_WORDS = {
  profile_missing: "desktop.providers.sign_in_cause.profile_missing",
  unsupported_method: "desktop.providers.sign_in_cause.unsupported_method",
  host_input_invalid: "desktop.providers.sign_in_cause.host_input_invalid",
  host_disconnected: "desktop.providers.sign_in_cause.host_disconnected",
  login_already_running:
    "desktop.providers.sign_in_cause.login_already_running",
  timed_out: "desktop.providers.sign_in_cause.timed_out",
  home_in_git_project: "desktop.providers.sign_in_cause.home_in_git_project",
  home_unavailable: "desktop.providers.sign_in_cause.home_unavailable",
  cli_not_found: "desktop.providers.sign_in_cause.cli_not_found",
  browser_relay_unavailable:
    "desktop.providers.sign_in_cause.browser_relay_unavailable",
  cli_start_failed: "desktop.providers.sign_in_cause.cli_start_failed",
  cli_exited_early: "desktop.providers.sign_in_cause.cli_exited_early",
  cli_protocol_mismatch:
    "desktop.providers.sign_in_cause.cli_protocol_mismatch",
  cli_reported_error: "desktop.providers.sign_in_cause.cli_reported_error",
  login_not_completed: "desktop.providers.sign_in_cause.login_not_completed",
  cleanup_unconfirmed: "desktop.providers.sign_in_cause.cleanup_unconfirmed",
  internal_error: "desktop.providers.sign_in_cause.internal_error",
  helper_start_failed: "desktop.providers.sign_in_cause.helper_start_failed",
  helper_output_invalid:
    "desktop.providers.sign_in_cause.helper_output_invalid",
  helper_ended_without_result:
    "desktop.providers.sign_in_cause.helper_ended_without_result",
  helper_exit_nonzero: "desktop.providers.sign_in_cause.helper_exit_nonzero",
  agent_stop_failed: "desktop.providers.sign_in_cause.agent_stop_failed",
  status_not_confirmed: "desktop.providers.sign_in_cause.status_not_confirmed",
  probe_start_failed: "desktop.providers.sign_in_cause.probe_start_failed",
  probe_timed_out: "desktop.providers.sign_in_cause.probe_timed_out",
  probe_output_unreadable:
    "desktop.providers.sign_in_cause.probe_output_unreadable",
  probe_cleanup_unconfirmed:
    "desktop.providers.sign_in_cause.probe_cleanup_unconfirmed",
  status_read_failed: "desktop.providers.sign_in_cause.status_read_failed",
  status_unreadable: "desktop.providers.sign_in_cause.status_unreadable",
  status_context_unavailable:
    "desktop.providers.sign_in_cause.status_context_unavailable",
} as const satisfies Record<SignInCause | CliStateCause, string>;

const STEP_WORDS = {
  retry: "desktop.providers.next_step.retry",
  install_cli: "desktop.providers.next_step.install_cli",
  move_profile_outside_git:
    "desktop.providers.next_step.move_profile_outside_git",
  close_other_sign_in: "desktop.providers.next_step.close_other_sign_in",
  console_sign_in: "desktop.providers.next_step.console_sign_in",
  update_app: "desktop.providers.next_step.update_app",
} as const satisfies Record<NextStep, string>;

/**
 * Why a sign-in or a status read did not settle, and what to do about it, in
 * the service's closed words. A console sign-in also shows the command to
 * run, with the provider's id in it, as text a person can select.
 */
export function SignInAdvice({
  causes,
  step,
  command,
  provider,
}: {
  /** The causes to say, most general first; a repeat is said once. */
  causes: readonly (SignInCause | CliStateCause | undefined)[];
  step?: NextStep;
  /** The served command template, with its `{provider}` slot. */
  command?: string;
  /** The provider's id, which fills the slot. */
  provider: string;
}) {
  const t = useStrings();
  const said = [...new Set(causes.filter((cause) => cause !== undefined))];
  const line =
    step === "console_sign_in" ? consoleCommand(command, provider) : undefined;
  if (said.length === 0 && !step) return null;
  return (
    <div data-slot="sign-in-advice" className="grid gap-1 text-sm">
      {said.map((cause) => (
        <p key={cause}>{t(CAUSE_WORDS[cause])}</p>
      ))}
      {step && <p>{t(STEP_WORDS[step])}</p>}
      {line && (
        <p className="grid justify-items-start gap-1">
          <span className="text-muted-foreground">
            {t("desktop.providers.console_command_label")}
          </span>
          <code className="rounded bg-muted px-2 py-1 font-mono text-foreground wrap-anywhere select-all">
            {line}
          </code>
        </p>
      )}
    </div>
  );
}
