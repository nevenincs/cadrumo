import { createContext, useContext } from "react";
import type { AgentOffer } from "./agentOffer";

// What the agent offers, as the agent column worked it out once from its
// reads: every surface inside the column reads it here rather than deriving
// lanes, models or efforts of its own.

export const AgentOfferContext = createContext<AgentOffer | null>(null);

/** The agent's offer, or null while the catalog is unread or outside the
 * agent column. */
export function useAgentOffer(): AgentOffer | null {
  return useContext(AgentOfferContext);
}
