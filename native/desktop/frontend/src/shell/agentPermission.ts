import type { AgentApprovalOption } from "./agentSession";

// How cadrumo-agent offers a permission, as the column reads it. The agent
// never offers an option it would remember (an "always" answer): such a rule
// would outlive the call it answered, in settings the agent cannot retract,
// and the system answers with the once-only option all the same, so offering
// it would promise what it never does. The one exception is a request that
// offers nothing else: narrowing it to nothing would turn a question a person
// can answer into a refusal that nobody decided.

/** Whether choosing `option` would ask the agent to remember the answer. */
export const remembers = (option: AgentApprovalOption): boolean =>
  option.kind === "allow_always" || option.kind === "reject_always";

/** The options to put to the person: those that answer this call alone,
 * or, when there are none, every option the agent offered. */
export function offeredOptions(
  options: readonly AgentApprovalOption[],
): AgentApprovalOption[] {
  const once = options.filter((option) => !remembers(option));
  return once.length > 0 ? once : [...options];
}
