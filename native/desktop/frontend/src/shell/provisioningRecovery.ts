import { createContext, useContext } from "react";
import type { SetupRow } from "../ipc/contract";
import type { LedgerOutcome, LedgerPort } from "./ledger";

// A refusal the product recovers by setting a component up names that setup
// as an `operator.provision.<item>` action: on an agent tool's refusal, on a
// settled operation's precondition verdict, or on a reading that stood
// without its model fill. This module finds that action in any of those
// shapes, so every surface routes it the same way to the window's one setup
// prompt. The action is an identifier for routing, never shown.

const PROVISION_PREFIX = "operator.provision.";
/** The action that sets up the local AI: its program and every role's
 * model. */
export const LOCAL_AI_SETUP_ACTION = "operator.provision.local_ai";
/** Lower-case letters, digits, `_` and `.`, within the host's token cap. */
const ACTION_TOKEN = /^[a-z0-9_.]{1,128}$/;
/** How deep a refusal's nested shapes are searched for the action. */
const DEPTH = 4;

function provisionAction(value: unknown): string | null {
  return typeof value === "string" &&
    ACTION_TOKEN.test(value) &&
    value.startsWith(PROVISION_PREFIX) &&
    value.length > PROVISION_PREFIX.length
    ? value
    : null;
}

function parsed(text: string): unknown {
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

function search(value: unknown, depth: number): string | null {
  const direct = provisionAction(value);
  if (direct !== null || depth === 0) return direct;
  if (typeof value !== "object" || value === null || Array.isArray(value))
    return null;
  const held = value as Record<string, unknown>;
  // A refusal or a fallback names its recovery; a verdict snapshot names
  // its action; a verdict as the product serializes it holds the action's
  // reference.
  for (const named of [held.recovery_action_id, held.action_id]) {
    const found = provisionAction(named);
    if (found !== null) return found;
  }
  const action = held.action;
  if (typeof action === "object" && action !== null && !Array.isArray(action)) {
    const found = provisionAction(
      (action as Record<string, unknown>).action_id,
    );
    if (found !== null) return found;
  }
  // An error detail carries its verdict as the verdict's own JSON text.
  if (typeof held.precondition_verdict_json === "string") {
    const found = search(parsed(held.precondition_verdict_json), depth - 1);
    if (found !== null) return found;
  }
  for (const nested of [held.precondition_verdict, held.detail, held.refusal]) {
    const found = search(nested, depth - 1);
    if (found !== null) return found;
  }
  return null;
}

/**
 * The setup action a refusal, verdict, error detail or label-reading
 * fallback names as its recovery, or null when it names none or names an
 * action that is not about setup. Anything not exactly an action token is
 * no action.
 */
export function provisionActionOf(value: unknown): string | null {
  return search(value, DEPTH);
}

/** The window's setup, as a feature that could not run asks for it. */
export type ProvisioningRecovery = {
  /** Where `action` leads now: the row of the item it sets up, setup as a
   * whole, or nowhere while this window offers no setup. */
  targetOf(action: string): SetupRow | "general" | null;
  /** Opens the setup prompt on the item `action` sets up, or setup as a
   * whole; false where it leads nowhere. */
  offer(action: string): boolean;
};

const NO_SETUP: ProvisioningRecovery = {
  targetOf: () => null,
  offer: () => false,
};

export const ProvisioningRecoveryContext =
  createContext<ProvisioningRecovery>(NO_SETUP);

export function useProvisioningRecovery(): ProvisioningRecovery {
  return useContext(ProvisioningRecoveryContext);
}

/**
 * The setup action a settled batch's reading pause names: a batch whose
 * reading the missing local AI paused settles, and its run carries the
 * pause's verdict. Null for any other result.
 */
export function pausedActionOf(result: unknown): string | null {
  if (typeof result !== "object" || result === null) return null;
  const run = (result as Record<string, unknown>).run;
  if (typeof run !== "object" || run === null) return null;
  const pause = (run as Record<string, unknown>).inference_pause;
  return pause === null || pause === undefined
    ? null
    : provisionActionOf(pause);
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
  const offered = new Set<string>();
  const watched = <Outcome extends LedgerOutcome<unknown>>(
    answer: Promise<Outcome>,
  ): Promise<Outcome> =>
    answer.then((outcome) => {
      if (
        (outcome.kind === "refused" || outcome.kind === "settled") &&
        !offered.has(outcome.operation_id)
      ) {
        const action =
          outcome.kind === "refused"
            ? provisionActionOf(outcome.detail)
            : pausedActionOf(outcome.result);
        if (action !== null) {
          offered.add(outcome.operation_id);
          offer(action);
        }
      }
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
