import type { CallPlan } from "./hostCall";

/** Bounded fallback for collecting service-owned catalog work after admission is busy. */
export const CATALOG_BUSY_RETRIES = 3;
export const CATALOG_BUSY_PAUSE_MS = 2_000;

/** Only these read refusals can recover under the same signed-in owner. */
export const catalogReadBusy = (code: string): boolean =>
  code === "agent_service_busy" || code === "agent_reconnecting";

/** A catalog read whose busy refusals the caller answers by reading again
 * while `scheduled` says another read is coming. */
export const catalogReadRetry = (scheduled: () => boolean): CallPlan => ({
  retryable: catalogReadBusy,
  scheduled,
});
