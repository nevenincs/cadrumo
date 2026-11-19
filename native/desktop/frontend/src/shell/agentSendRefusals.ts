import type { CallPlan } from "./hostCall";

// The refusals of a send that name what the person chose and come with a way
// on the column offers. The agent decides the refusal and its code; the
// column only says it and offers the next step.

/** The next step a refused send offers: the local AI's settings, where a
 * model is downloaded or a smaller one is chosen. */
export type SendRefusalStep = "local_models";

/** The next step for the send refused with `code`, where it has one. */
export function sendRefusalStep(code: string | null): SendRefusalStep | null {
  switch (code) {
    // The chosen model is one this computer does not hold: the catalog the
    // column chose from was older than the agent's answer.
    case "agent_gateway_model_not_installed":
      return "local_models";
    // The chosen model is one this computer cannot run: the way on is the
    // same settings, to choose another.
    case "agent_gateway_model_does_not_fit":
      return "local_models";
    default:
      return null;
  }
}

/** Whether a send refused with `code` was refused for a choice the catalog
 * offered, so what is offered is read again: a model this computer lacks or
 * cannot run, or one the signed-in account is not offered. */
export function sendRefusalStaleCatalog(code: string | null): boolean {
  return (
    sendRefusalStep(code) !== null || code === "agent_gateway_model_not_offered"
  );
}

/** The refusals the column answers in place rather than as a failed call:
 * the agent asks the person to confirm a change of model, the conversation
 * runs on another lane than the one sent, or the model chosen is not one the
 * account is offered. */
const ANSWERED = new Set([
  "agent_gateway_selection_change_unacknowledged",
  "agent_gateway_conversation_lane_fixed",
  "agent_gateway_conversation_lane_unreadable",
  "agent_gateway_model_not_offered",
]);

/** How a send's refusal is recorded: one the column words with its next
 * step, or answers in place, is answered, not failed. */
export const SEND_PLAN: CallPlan = {
  answered: (code) => sendRefusalStep(code) !== null || ANSWERED.has(code),
};
