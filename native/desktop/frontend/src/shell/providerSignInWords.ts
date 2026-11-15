// The closed words a provider sign-in or status read serves for why it did
// not complete and what to do about it. A word outside a set is dropped, as a
// reason outside its set is: nothing the service or a provider wrote as free
// text is ever shown.

import {
  CLI_STATE_CAUSES,
  NEXT_STEPS,
  SIGN_IN_CAUSES,
  type CliStateCause,
  type NextStep,
  type SignInCause,
} from "./providerSignInContract.ts";

export { CLI_STATE_CAUSES, NEXT_STEPS, SIGN_IN_CAUSES };
export type { CliStateCause, NextStep, SignInCause };

const within =
  <Word extends string>(words: readonly Word[]) =>
  (value: unknown): Word | undefined =>
    words.find((word) => word === value);

export const signInCause = within<SignInCause>(SIGN_IN_CAUSES);
export const cliStateCause = within<CliStateCause>(CLI_STATE_CAUSES);
export const nextStep = within<NextStep>(NEXT_STEPS);

const LOG_REF = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;

/** The diagnostic id a host names a failure by in its log, when it is a
 * bounded token; anything else is dropped. */
export function logRef(value: unknown): string | undefined {
  return typeof value === "string" && LOG_REF.test(value) ? value : undefined;
}

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
