// The closed words a provider sign-in or status read serves for why it did
// not complete and what to do about it. A word outside a set is dropped, as a
// reason outside its set is: nothing the service or a provider wrote as free
// text is ever shown.

/** Why a sign-in attempt did not succeed: the helper's and the service's words. */
export const SIGN_IN_CAUSES = [
  "profile_missing",
  "unsupported_method",
  "host_input_invalid",
  "host_disconnected",
  "login_already_running",
  "timed_out",
  "home_in_git_project",
  "home_unavailable",
  "cli_not_found",
  "browser_relay_unavailable",
  "cli_start_failed",
  "cli_exited_early",
  "cli_protocol_mismatch",
  "cli_reported_error",
  "login_not_completed",
  "cleanup_unconfirmed",
  "internal_error",
  "helper_start_failed",
  "helper_output_invalid",
  "helper_ended_without_result",
  "helper_exit_nonzero",
  "agent_stop_failed",
  "status_not_confirmed",
] as const;
export type SignInCause = (typeof SIGN_IN_CAUSES)[number];

/** Why a command-line app's state is not established. */
export const CLI_STATE_CAUSES = [
  "cli_not_found",
  "home_in_git_project",
  "home_unavailable",
  "probe_start_failed",
  "probe_timed_out",
  "probe_output_unreadable",
  "probe_cleanup_unconfirmed",
  "status_read_failed",
  "status_unreadable",
  "status_context_unavailable",
] as const;
export type CliStateCause = (typeof CLI_STATE_CAUSES)[number];

/** What a person can do about a cause. */
export const NEXT_STEPS = [
  "retry",
  "install_cli",
  "move_profile_outside_git",
  "close_other_sign_in",
  "console_sign_in",
  "update_app",
] as const;
export type NextStep = (typeof NEXT_STEPS)[number];

const within =
  <Word extends string>(words: readonly Word[]) =>
  (value: unknown): Word | undefined =>
    words.find((word) => word === value);

export const signInCause = within<SignInCause>(SIGN_IN_CAUSES);
export const cliStateCause = within<CliStateCause>(CLI_STATE_CAUSES);
export const nextStep = within<NextStep>(NEXT_STEPS);

const COMMAND_LIMIT = 200;
const SLOT = "{provider}";
const PROVIDER_ID = /^[a-z][a-z0-9_]{0,39}$/;

/** The served console command, when it is a bounded printable template with
 * the provider slot once and no path in it. */
export function consoleCommandTemplate(value: unknown): string | undefined {
  return typeof value === "string" &&
    value.length <= COMMAND_LIMIT &&
    value.split(SLOT).length === 2 &&
    /^[ -~]+$/.test(value) &&
    !/[\\/]/.test(value)
    ? value
    : undefined;
}

/** The command to run for `provider`, or nothing where the template is not
 * served or the provider is not a plain id. */
export function consoleCommand(
  template: string | undefined,
  provider: string,
): string | undefined {
  const checked = consoleCommandTemplate(template);
  return checked !== undefined && PROVIDER_ID.test(provider)
    ? checked.replace(SLOT, provider)
    : undefined;
}
