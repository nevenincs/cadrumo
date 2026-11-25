/** Only these read refusals can recover under the same signed-in owner. */
export const catalogReadBusy = (code: string): boolean =>
  code === "agent_service_busy" || code === "agent_reconnecting";

/** How long the provider settings wait on a busy service before the wait is
 * noted as a warning. A normal agent start, its first model load included,
 * ends well within it. */
export const CATALOG_BUSY_QUIET_MS = 90_000;
