import type { ConsoleEnvironmentChange } from "./host";

/** The event the host emits when the console's environment changes. */
export const CONSOLE_ENVIRONMENT_EVENT = "console-environment-changed";

/** A revision is an opaque token: bounded, printable, never a value of the
 * environment it stands for. */
const REVISION = /^[\x21-\x7e]{1,128}$/;

/**
 * The change `payload` reports, or null when it is not exactly
 * `{ revision }` with a revision token: anything more could carry the
 * environment itself, which never reaches the window.
 */
export function parseConsoleEnvironmentChange(
  payload: unknown,
): ConsoleEnvironmentChange | null {
  if (typeof payload !== "object" || payload === null) return null;
  if (Object.getPrototypeOf(payload) !== Object.prototype) return null;
  const keys = Object.keys(payload);
  if (keys.length !== 1 || keys[0] !== "revision") return null;
  const { revision } = payload as { revision: unknown };
  if (typeof revision !== "string" || !REVISION.test(revision)) return null;
  return { revision };
}
