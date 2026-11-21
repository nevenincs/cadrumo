import { createContext, useContext } from "react";

// How a page hands one of its records to the agent: the agent column opens
// and stages the record as an attachment of the next message of the
// conversation it shows, starting one where none is open. Nothing is sent:
// the person reads what the attachment holds and who would read it, and
// sends the message or removes the attachment. The window offers the way
// only where its host stores such a record in a conversation.

export type AgentHandoff = {
  /** Shows the agent column with the Libro movement `transactionId` staged
   * on the next message. */
  openMovement(transactionId: string): void;
};

export const AgentHandoffContext = createContext<AgentHandoff | null>(null);

/** The way to the agent column, or null where the window offers none. */
export function useAgentHandoff(): AgentHandoff | null {
  return useContext(AgentHandoffContext);
}
