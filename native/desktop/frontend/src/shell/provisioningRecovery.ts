import type { SetupItemId } from "../ipc/contract";
import type { LedgerOutcome, LedgerPort } from "./ledger";
import type { CensoPort, CensoSnapshot } from "./profileCenso";

// A refusal the product recovers by setting a component up says so plainly:
// its registered code, a reading that stood because the local AI could not
// read, a statement file the local AI was needed for, or a batch whose reading
// paused. This module turns each into the `operator.provision.<item>` action
// of the engine's item it needs, so every surface routes it the same way to
// the window's one provisioning panel, where the engine's own row says whether
// setup can act. A host-side refusal that already names the action keeps it.
// The action is an identifier for routing, never shown.

const PROVISION_PREFIX = "operator.provision.";
/** Lower-case letters, digits, `_` and `.`, within the host's token cap. */
const ACTION_TOKEN = /^[a-z0-9_.]{1,128}$/;
/** How deep a refusal's nested shapes are searched. */
const DEPTH = 3;

/** The setup action of the engine's item `item`. */
export const setupActionOf = (item: SetupItemId) =>
  `${PROVISION_PREFIX}${item}`;

/** The registered refusals that stand for a component that is not usable. */
const REFUSED_FOR: ReadonlyMap<string, SetupItemId> = new Map([
  ["REFUSED_BROWSER_NOT_READY", "browser"],
  ["REFUSED_LEDGER_EVIDENCE_READER", "local_ai"],
]);
/** What a reading or a statement file says when the local AI could not read. */
const READER_UNAVAILABLE = "reader_unavailable";

function provisionAction(value: unknown): string | null {
  return typeof value === "string" &&
    ACTION_TOKEN.test(value) &&
    value.startsWith(PROVISION_PREFIX) &&
    value.length > PROVISION_PREFIX.length
    ? value
    : null;
}

function search(value: unknown, depth: number): string | null {
  const direct = provisionAction(value);
  if (direct !== null || depth === 0) return direct;
  if (typeof value !== "object" || value === null || Array.isArray(value))
    return null;
  const held = value as Record<string, unknown>;
  const named = provisionAction(held.recovery_action_id);
  if (named !== null) return named;
  const code = held.error_code ?? held.code;
  const item = typeof code === "string" ? REFUSED_FOR.get(code) : undefined;
  if (item !== undefined) return setupActionOf(item);
  if (
    held.cause === READER_UNAVAILABLE ||
    held.reason_code === READER_UNAVAILABLE
  )
    return setupActionOf("local_ai");
  for (const nested of [held.detail, held.refusal]) {
    const found = search(nested, depth - 1);
    if (found !== null) return found;
  }
  return null;
}

/**
 * The setup action a refusal, error detail, refused file or label-reading
 * fallback stands for, or null when it stands for none. Anything not exactly
 * an action token is no action.
 */
export function provisionActionOf(value: unknown): string | null {
  return search(value, DEPTH);
}

/** The setup action a batch's reading pause stands for: only the local AI
 * pauses a reading. Null for no pause. */
export function pauseActionOf(pause: unknown): string | null {
  return pause === null || pause === undefined
    ? null
    : setupActionOf("local_ai");
}

/**
 * The setup action a settled batch's reading pause stands for. Null for any
 * other result.
 */
export function pausedActionOf(result: unknown): string | null {
  if (typeof result !== "object" || result === null) return null;
  const run = (result as Record<string, unknown>).run;
  if (typeof run !== "object" || run === null) return null;
  return pauseActionOf((run as Record<string, unknown>).inference_pause);
}

/** Hands `offer` the setup action an operation names, once per operation,
 * however many reads observe it: each new operation offers again. */
function oncePerOperation(
  offer: (action: string) => void,
): (operation: string, action: string | null) => void {
  const offered = new Set<string>();
  return (operation, action) => {
    if (action === null || offered.has(operation)) return;
    offered.add(operation);
    offer(action);
  };
}

/**
 * The ledger port, with every refused outcome whose verdict names a setup
 * action, and every settled batch whose reading pause names one, handed to
 * `offer` once per operation, whichever call observed it. The outcome itself
 * reaches the page unchanged.
 */
export function routeProvisioningRefusals(
  port: LedgerPort,
  offer: (action: string) => void,
): LedgerPort {
  const once = oncePerOperation(offer);
  const watched = <Outcome extends LedgerOutcome<unknown>>(
    answer: Promise<Outcome>,
  ): Promise<Outcome> =>
    answer.then((outcome) => {
      if (outcome.kind === "refused")
        once(outcome.operation_id, provisionActionOf(outcome.detail));
      else if (outcome.kind === "settled")
        once(outcome.operation_id, pausedActionOf(outcome.result));
      return outcome;
    });
  return {
    ...port,
    submit: (definition, payload) => watched(port.submit(definition, payload)),
    observe: (operation) => watched(port.observe(operation)),
    answer: (operation, reviewDigest, decision) =>
      watched(port.answer(operation, reviewDigest, decision)),
    cancel: (operation, revision) => watched(port.cancel(operation, revision)),
  };
}

/**
 * The Censo port, with every pull that stopped for want of a component
 * handed to `offer` once per pull, whichever call observed it: a second pull
 * that stops the same way offers again. The snapshot reaches the page
 * unchanged.
 */
export function routeCensoRefusals(
  port: CensoPort,
  offer: (action: string) => void,
): CensoPort {
  const once = oncePerOperation(offer);
  const watched = (answer: Promise<CensoSnapshot>): Promise<CensoSnapshot> =>
    answer.then((snapshot) => {
      if (snapshot.state === "failed")
        once(
          snapshot.operation,
          provisionAction(snapshot.recovery_action_id ?? null),
        );
      return snapshot;
    });
  return {
    ...port,
    start: (profile) => watched(port.start(profile)),
    status: (profile, operation) => watched(port.status(profile, operation)),
    answer: (profile, operation, reviewDigest, decision) =>
      watched(port.answer(profile, operation, reviewDigest, decision)),
  };
}
