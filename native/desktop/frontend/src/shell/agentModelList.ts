import { createContext, useContext } from "react";

// Where the person picks the model the agent and document reading run with:
// the model picker of the agent column. Beside a reading that has no model to
// read with, a surface leads there. The window offers the way only where its
// host stores the picked model for document reading.

export type ModelList = {
  /** Shows the agent column with its model picker open. */
  open(): void;
};

export const ModelListContext = createContext<ModelList | null>(null);

/** The way to the model list, or null where the window offers none. */
export function useModelList(): ModelList | null {
  return useContext(ModelListContext);
}
