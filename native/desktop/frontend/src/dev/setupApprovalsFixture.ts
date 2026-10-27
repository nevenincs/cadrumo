// The scenario host's setup reviews: setups an assistant started that wait on
// the person. Once the window first reads them, the tests raise one through
// `window.__scenarioSetupReviews`, as the agent's tool call would, and read back what the person answered. Claim
// and answer hold the runtime's checks in small: an answer needs the claim's
// own coordinates, and a review that changed refuses its claim.

import type {
  SetupOperationReview,
  SetupReviewCoordinates,
} from "../ipc/contract";
import type { SetupApprovalsPort } from "../shell/setupApprovals";

export type SetupReviewControls = {
  /** An assistant's setup now waits on the person. */
  raise(): void;
  /** The waiting review changes under the person, as a new plan would. */
  change(): void;
  /** The next answer's reply is lost: the runtime may have taken it. */
  loseNextAnswer(): void;
  /** What the person answered, in order. */
  answers: ("apply" | "reject")[];
};

declare global {
  interface Window {
    __scenarioSetupReviews?: SetupReviewControls;
  }
}

const hex = (digit: string) => digit.repeat(64);

function document(plan: string): Record<string, unknown> {
  return {
    projection: {
      plan_digest: plan,
      plan: {
        contract_version: 3,
        entries: [
          {
            item_id: "browser",
            download_bytes: 180_000_000,
            source_hosts: ["cdn.playwright.dev"],
            destination: "playwright-browsers",
            installs_outside_program: false,
            parts: [],
            target_version: "1.55.0",
          },
        ],
        known_download_bytes: 180_000_000,
        has_unknown_size: false,
        installs_outside_program: false,
        space: {
          required_bytes: 600_000_000,
          free_bytes: 50_000_000_000,
          sufficient: true,
        },
      },
    },
  };
}

function refusal(code: string): Error & { code: string } {
  return Object.assign(new Error(code), { code });
}

export function setupApprovalsFixture(
  say: (call: string) => void,
): SetupApprovalsPort {
  let waiting: SetupOperationReview | null = null;
  let raised = 0;
  let loseAnswer = false;
  const controls: SetupReviewControls = {
    raise() {
      raised += 1;
      waiting = {
        kind: "operation_review",
        operation_id: hex(String(raised % 10)),
        interaction_id: hex("b"),
        revision: 3,
        review_digest: hex("c"),
        expires_at: null,
        document: document(hex("d")),
      };
    },
    change() {
      if (waiting)
        waiting = {
          ...waiting,
          review_digest: hex("e"),
          document: document(hex("f")),
        };
    },
    loseNextAnswer() {
      loseAnswer = true;
    },
    answers: [],
  };
  const same = (a: SetupReviewCoordinates, b: SetupReviewCoordinates) =>
    a.operation_id === b.operation_id &&
    a.interaction_id === b.interaction_id &&
    a.revision === b.revision &&
    a.review_digest === b.review_digest;
  return {
    pending() {
      say("setupReviewPending");
      // The host the window uses is the one it reads from: a host built and
      // discarded beside it never takes the controls.
      window.__scenarioSetupReviews = controls;
      return Promise.resolve(
        waiting && waiting.kind === "operation_review" ? [waiting] : [],
      );
    },
    claim(review) {
      say("setupReviewClaim");
      if (!waiting || waiting.kind !== "operation_review")
        return Promise.reject(refusal("not_pending"));
      if (!same(review, waiting))
        return Promise.reject(refusal("review_claim_stale"));
      waiting = {
        ...waiting,
        kind: "operation_review_claimed",
        revision: waiting.revision + 1,
        review_digest: hex("a"),
      };
      return Promise.resolve(waiting);
    },
    answer(review, decision) {
      say(`setupReviewAnswer:${decision}`);
      if (
        !waiting ||
        waiting.kind !== "operation_review_claimed" ||
        !same(review, waiting)
      )
        return Promise.reject(refusal("response_authority_required"));
      const operationId = waiting.operation_id;
      waiting = null;
      controls.answers.push(decision);
      if (loseAnswer) {
        loseAnswer = false;
        return Promise.reject(refusal("unavailable"));
      }
      return Promise.resolve({
        kind: "operation_responded",
        operation_id: operationId,
        decision,
      });
    },
  };
}
