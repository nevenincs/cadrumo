// The tools the scenario agent's replies call, as the agent serves their
// identity: the raw name its provider gives a call, the server and name it
// reads from it, how far the tool reaches and, on a call that failed, the
// reason it gave. Everything here is synthetic.

import type { ToolCallStatus, ToolReach } from "../shell/agentGatewayContract";
import type { AgentStreamToolCall } from "../shell/agentSession";

/** A tool the fixture serves an identity for: what the agent says of it. */
type ServedTool = {
  server: string;
  name: string;
  reach: ToolReach | null;
  /** The reason a failed call gives. */
  failure: string;
};

const RAW = (server: string, name: string) => `mcp__${server}__${name}`;

const SERVED: readonly ServedTool[] = [
  {
    server: "cadrumo",
    name: "status",
    reach: "local_read",
    failure: "The session is not signed in to a profile.",
  },
  {
    server: "cadrumo_agent_tools",
    name: "web_search",
    reach: "online",
    failure: "The search service did not answer.",
  },
  {
    server: "cadrumo",
    name: "ledger_unheard_of",
    reach: null,
    failure: "No such operation.",
  },
];

/** The messages that make a reply call a tool the agent serves an identity
 * for, as an agent would be asked, and the raw name its provider gives it. */
export const SERVED_TOOL_TRIGGERS: readonly (readonly [RegExp, string])[] = [
  [/estado de la sesión/i, RAW("cadrumo", "status")],
  [/busca en internet/i, RAW("cadrumo_agent_tools", "web_search")],
  [/herramienta sin palabras/i, RAW("cadrumo", "ledger_unheard_of")],
];

/** The title of the tool a reply calls: a served tool's raw name where the
 * message asks for one, else the one the scenario's older replies use. */
export function toolTitle(text: string): string {
  return (
    SERVED_TOOL_TRIGGERS.find(([asked]) => asked.test(text))?.[1] ??
    "ledger_list"
  );
}

/** A call as it first reaches the stream: pending, with the identity the
 * agent reads from its title where it serves one. */
export function toolCall(
  id: string,
  title: string,
  tool_kind: AgentStreamToolCall["tool_kind"],
): AgentStreamToolCall {
  const served = SERVED.find(({ server, name }) => RAW(server, name) === title);
  return {
    id,
    title,
    tool_kind,
    status: "pending",
    ...(served
      ? {
          tool_server: served.server,
          tool_name: served.name,
          ...(served.reach ? { tool_reach: served.reach } : {}),
        }
      : {}),
  };
}

/** The call at `status`: a failed call of a served tool says why. */
export function atState(
  call: AgentStreamToolCall,
  status: ToolCallStatus,
): AgentStreamToolCall {
  const served = SERVED.find(
    ({ server, name }) =>
      server === call.tool_server && name === call.tool_name,
  );
  return {
    ...call,
    status,
    ...(status === "failed" && served
      ? { failure: { message: served.failure } }
      : {}),
  };
}
