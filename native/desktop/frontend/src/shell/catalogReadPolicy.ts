import type { CallPlan } from "./hostCall";

/** The first pause before a busy catalog read is asked again. */
export const CATALOG_BUSY_PAUSE_MS = 2_000;

/** How many busy reads the Local AI lanes follow before they show a failure
 * with its own Retry. */
export const CATALOG_BUSY_RETRIES = 3;

/** The ceiling of the agent column's pauses. It stays under the five seconds
 * the service keeps the outcome of a read that outlived its request, so the
 * read that follows is served that outcome instead of starting the work
 * again. */
export const CATALOG_BUSY_PAUSE_CEILING_MS = 4_000;

/** The agent column's pause after `pauses` pauses since its read was last
 * asked afresh: the first pause, doubling up to the ceiling. The column asks a
 * busy service again until it answers; there is no last read. */
export const catalogBusyPause = (pauses: number): number =>
  Math.min(CATALOG_BUSY_PAUSE_CEILING_MS, CATALOG_BUSY_PAUSE_MS * 2 ** pauses);

/** The pause before a busy provider status read is asked again. That read is
 * the service's own store read and waits on nothing; busy only means the host
 * has not yet admitted the service, which takes a moment, so it is asked again
 * soon while the wait stays within `CATALOG_BUSY_QUIET_MS`. */
export const STATUS_BUSY_PAUSE_MS = 250;

/** Only these read refusals can recover under the same signed-in owner. */
export const catalogReadBusy = (code: string): boolean =>
  code === "agent_service_busy" || code === "agent_reconnecting";

/** How long the agent column waits on a busy service before the wait is
 * noted as a warning. A normal agent start, its first model load included,
 * ends well within it. */
export const CATALOG_BUSY_QUIET_MS = 90_000;

/** A catalog read whose busy refusals the caller answers by reading again
 * while `scheduled` says another read is coming, and notes below a warning
 * while `expected` says the wait is still the one it expects. */
export const catalogReadRetry = (
  scheduled: () => boolean,
  expected?: () => boolean,
): CallPlan => ({
  retryable: catalogReadBusy,
  scheduled,
  ...(expected ? { expected } : {}),
});
