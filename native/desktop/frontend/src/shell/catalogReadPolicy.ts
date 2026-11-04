/** Bounded fallback for collecting service-owned catalog work after admission is busy. */
export const CATALOG_BUSY_RETRIES = 3;
export const CATALOG_BUSY_PAUSE_MS = 2_000;

/** Only these read refusals can recover under the same signed-in owner. */
export const catalogReadBusy = (code: string): boolean =>
  code === "agent_service_busy" || code === "agent_reconnecting";
