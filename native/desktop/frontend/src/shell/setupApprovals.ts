import { failureCode } from "../errors";

import type {
  SetupOperationReview,
  SetupPlanEntry,
  SetupReview,
  SetupReviewAnswer,
  SetupReviewCoordinates,
} from "../ipc/contract";

/** The runtime's setup reviews this desktop person may claim, and the
 * response path for each. No lifecycle ownership is offered. */
export type SetupApprovalsPort = {
  pending(): Promise<SetupOperationReview[]>;
  claim(review: SetupReviewCoordinates): Promise<SetupOperationReview>;
  answer(
    review: SetupReviewCoordinates,
    decision: "apply" | "reject",
  ): Promise<SetupReviewAnswer>;
};

/** Why the last answer did not go through, in words the person can act on. */
export type SetupApprovalFailure = "changed" | "held_elsewhere" | "unavailable";

export type SetupApprovalsState = {
  reviews: readonly SetupOperationReview[];
  /** The review being answered; every other one waits. */
  busy: string | null;
  failure: SetupApprovalFailure | null;
  /** An answer was sent and its outcome is unknown. */
  uncertain: boolean;
};

function coordinates(review: SetupOperationReview): SetupReviewCoordinates {
  return {
    operation_id: review.operation_id,
    interaction_id: review.interaction_id,
    revision: review.revision,
    review_digest: review.review_digest,
  };
}

/** A refusal is recovery guidance, never permission to take another person's claim. */
function failureOf(code: string | null): SetupApprovalFailure {
  if (code === "review_already_claimed") return "held_elsewhere";
  if (
    [
      "review_claim_stale",
      "review_changed",
      "not_pending",
      "operation_unavailable",
      "response_authority_required",
      "session_inactive",
      "session_expired",
      "session_retired",
      "runtime_changed",
      "custody_changed",
      "authority_unavailable",
      "connection_mismatch",
      "not_signed_in",
    ].includes(code ?? "")
  )
    return "changed";
  return "unavailable";
}

/**
 * The setup reviews waiting on this desktop person. Approving or rejecting
 * one is a single gesture that claims exactly the review shown and answers
 * it with the coordinates the claim returned. Authority comes only from that
 * claim, and an answer whose outcome is lost is never sent again: its review
 * is not offered again in this window.
 */
export class SetupApprovals {
  state: SetupApprovalsState = {
    reviews: [],
    busy: null,
    failure: null,
    uncertain: false,
  };
  private reads = 0;
  private fenced = new Set<string>();
  private listeners = new Set<() => void>();
  constructor(private port: SetupApprovalsPort) {}
  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
  getSnapshot = (): SetupApprovalsState => this.state;
  private publish(state: SetupApprovalsState): void {
    this.state = state;
    for (const listener of this.listeners) listener();
  }
  /** Reads the waiting reviews again. A read that fails shows none: the
   * agent's own words say setup is waiting. */
  async refresh(): Promise<void> {
    if (this.state.busy) return;
    const read = ++this.reads;
    let reviews: SetupOperationReview[];
    try {
      reviews = await this.port.pending();
    } catch {
      reviews = [];
    }
    if (read !== this.reads || this.state.busy) return;
    this.publish({
      ...this.state,
      reviews: reviews.filter(
        (review) =>
          review.kind === "operation_review" &&
          !this.fenced.has(review.operation_id),
      ),
    });
  }
  async decide(
    shown: SetupOperationReview,
    decision: "apply" | "reject",
  ): Promise<void> {
    if (this.state.busy || this.fenced.has(shown.operation_id)) return;
    // A read that started before this answer must not restore its review.
    this.reads++;
    this.publish({
      ...this.state,
      busy: shown.operation_id,
      failure: null,
    });
    let claimed: SetupOperationReview;
    try {
      claimed = await this.port.claim(coordinates(shown));
      const plan = browserPlan(shown.document, "");
      if (
        claimed.kind !== "operation_review_claimed" ||
        claimed.operation_id !== shown.operation_id ||
        claimed.interaction_id !== shown.interaction_id ||
        ![shown.revision, shown.revision + 1].includes(claimed.revision) ||
        // Apply only the exact plan the person saw.
        (decision === "apply" &&
          (plan === null ||
            browserPlan(claimed.document, "")?.plan_digest !==
              plan.plan_digest))
      )
        throw new Error("review_changed");
    } catch (error) {
      const code =
        error instanceof Error && error.message === "review_changed"
          ? "review_changed"
          : failureCode(error);
      this.publish({ ...this.state, busy: null, failure: failureOf(code) });
      await this.refresh();
      return;
    }
    try {
      const answered = await this.port.answer(coordinates(claimed), decision);
      if (
        answered.kind !== "operation_responded" ||
        answered.operation_id !== shown.operation_id ||
        answered.decision !== decision
      )
        throw new Error("answer mismatch");
      this.publish({
        ...this.state,
        reviews: this.state.reviews.filter(
          (review) => review.operation_id !== shown.operation_id,
        ),
        busy: null,
      });
    } catch {
      this.fenced.add(shown.operation_id);
      this.publish({
        ...this.state,
        reviews: this.state.reviews.filter(
          (review) => review.operation_id !== shown.operation_id,
        ),
        busy: null,
        uncertain: true,
      });
    }
  }
}

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}
function bytes(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

/** Render only the supported browser plan; no authority is derived from this projection. */
export function browserPlan(
  document: Readonly<Record<string, unknown>>,
  destination: string,
): SetupReview | null {
  const projection = record(document.projection);
  const plan = record(projection?.plan);
  const space = record(plan?.space);
  if (
    !projection ||
    !plan ||
    !space ||
    plan.contract_version !== 3 ||
    typeof projection.plan_digest !== "string" ||
    !/^[a-f0-9]{64}$/.test(projection.plan_digest) ||
    !Array.isArray(plan.entries) ||
    plan.entries.length !== 1 ||
    !bytes(plan.known_download_bytes) ||
    typeof plan.has_unknown_size !== "boolean" ||
    typeof plan.installs_outside_program !== "boolean" ||
    !bytes(space.required_bytes) ||
    !(space.free_bytes === null || bytes(space.free_bytes)) ||
    typeof space.sufficient !== "boolean"
  )
    return null;
  const entry = record(plan.entries[0]);
  if (
    !entry ||
    entry.item_id !== "browser" ||
    !(entry.download_bytes === null || bytes(entry.download_bytes)) ||
    !Array.isArray(entry.source_hosts) ||
    entry.source_hosts.length === 0 ||
    !entry.source_hosts.every(
      (host) => typeof host === "string" && host.length > 0,
    ) ||
    !(
      entry.destination === null || entry.destination === "playwright-browsers"
    ) ||
    typeof entry.installs_outside_program !== "boolean" ||
    !Array.isArray(entry.parts) ||
    entry.parts.length !== 0 ||
    !(entry.target_version === null || typeof entry.target_version === "string")
  )
    return null;
  const rendered: SetupPlanEntry = {
    item: "browser",
    download_bytes: entry.download_bytes,
    source_hosts: entry.source_hosts.map((host) => String(host)),
    destination: entry.destination === null ? null : destination,
    installs_outside_program: entry.installs_outside_program,
    shares_download_with: null,
    parts: [],
  };
  return {
    plan_digest: projection.plan_digest,
    entries: [rendered],
    known_download_bytes: plan.known_download_bytes,
    has_unknown_size: plan.has_unknown_size,
    installs_outside_program: plan.installs_outside_program,
    required_bytes: space.required_bytes,
    free_bytes: space.free_bytes,
    space_sufficient: space.sufficient,
  };
}
