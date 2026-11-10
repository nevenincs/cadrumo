import type { AgentEngineHealth, AgentEngineReason } from "./agentSession";
import { noted } from "./compose";
import type { Translate } from "./strings";

// The words for a local engine that does not run: the service's own reason
// token and door id, each named by a whole key so the shell's key check sees
// every one. A token the window has no words for says nothing: there is no
// fallback wording.

const REASON_WORDS = {
  no_answer_in_time: "desktop.agent.engine_reason_no_answer_in_time",
  not_reachable: "desktop.agent.engine_reason_not_reachable",
  answer_unreadable: "desktop.agent.engine_reason_answer_unreadable",
} as const satisfies Record<AgentEngineReason, string>;

/** The door ids the window opens, with the words on each one's button. */
const DOOR_WORDS = {
  local_ai_setup: "desktop.agent.engine_door_local_ai_setup",
} as const;

export type EngineDoorId = keyof typeof DOOR_WORDS;

/** Whether `door` is a way the window knows how to open. */
export const isEngineDoor = (door: string): door is EngineDoorId =>
  Object.hasOwn(DOOR_WORDS, door);

/** The words on `door`'s button; null for a door the window does not know. */
export function engineDoorWords(t: Translate, door: string): string | null {
  return isEngineDoor(door) ? t(DOOR_WORDS[door]) : null;
}

/** That the engine does not run and why; null for a running engine. */
export function engineNotRunningWords(
  t: Translate,
  engine: AgentEngineHealth,
): string | null {
  if (engine.state !== "not_running") return null;
  return noted(
    t,
    t("desktop.agent.engine_not_running"),
    t(REASON_WORDS[engine.reason]),
  );
}
