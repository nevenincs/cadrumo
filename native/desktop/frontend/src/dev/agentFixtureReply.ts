// What a scenario reply is and what it waits on: the state the scenario agent
// keeps for each reply, and the request it is parked on.

import type {
  AgentQuestionnaireAnswer,
  AgentStreamEvent,
} from "../shell/agentSession";
import type {
  AgentApproval,
  AgentApprovalOption,
  AgentQuestionnaire,
} from "../shell/agentSnapshotContract";
import type { FixtureRun } from "./fixtures/agent";

export type Reply = {
  conversationId: string;
  run: FixtureRun;
  timers: number[];
  /** The frames the agent retains for the run, from its first: what a new
   * watch is replayed. */
  frames: AgentStreamEvent[];
  /** The sequence of the last frame. */
  sequence: number;
  /** The message being written: its id, and its text so far. The agent
   * records it when its turn ends. */
  message: { id: string; text: string } | null;
  /** The stream has been lost once, as `stream=gap` asks. */
  lost: boolean;
};

export type Waiting =
  | {
      kind: "questions";
      questionnaire: AgentQuestionnaire;
      then: (answer: AgentQuestionnaireAnswer) => void;
    }
  | {
      kind: "approval";
      approval: AgentApproval;
      then: (option: AgentApprovalOption) => void;
    };
