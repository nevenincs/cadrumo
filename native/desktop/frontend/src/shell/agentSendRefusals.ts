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

/** How a send's refusal is recorded: one the column words with its next
 * step is answered, not failed. */
export const SEND_PLAN: CallPlan = {
  answered: (code) => sendRefusalStep(code) !== null,
};
