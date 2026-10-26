import { createContext, useContext } from "react";

// Where the person chooses the model each role reads with: the agent's
// settings, in the agent column. Beside a role that has no model chosen, a
// surface leads there rather than choosing for the person. The window offers
// the way only where its host lets the person read and change the choices.

export type ModelChoice = {
  /** Shows the agent column, where the model of each role is chosen. */
  open(): void;
};

export const ModelChoiceContext = createContext<ModelChoice | null>(null);

/** The way to the model choice, or null where the window offers none. */
export function useModelChoice(): ModelChoice | null {
  return useContext(ModelChoiceContext);
}
