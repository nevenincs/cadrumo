import { failureCode } from "../errors";

import type {
  SetupReview,
  SetupPlanEntry,
  SetupOperationReview,
  SetupReviewAnswer,
  SetupReviewCoordinates,
} from "../ipc/contract";

/** The registered operation response path; no lifecycle ownership is offered. */
export type SetupReviewPort = {
  read(operationId: string): Promise<SetupOperationReview>;
  claim(review: SetupReviewCoordinates): Promise<SetupOperationReview>;
  answer(
    review: SetupReviewCoordinates,
    decision: "apply" | "reject",
  ): Promise<SetupReviewAnswer>;
};

export type SetupReviewState = {
  review: SetupOperationReview | null;
  claimed: boolean;
  busy: boolean;
  failed: boolean;
  failureCode: string | null;
  unknownOperationIds: readonly string[];
};

export function coordinates(
  review: SetupOperationReview,
): SetupReviewCoordinates {
  return {
    operation_id: review.operation_id,
    interaction_id: review.interaction_id,
    revision: review.revision,
    review_digest: review.review_digest,
  };
}

/** Authority comes only from the explicit claim reply and is discarded on any failure. */
export class SetupReviewSession {
  state: SetupReviewState = {
    review: null,
    claimed: false,
    busy: false,
    failed: false,
    failureCode: null,
    unknownOperationIds: [],
  };
  private generation = 0;
  private listeners = new Set<() => void>();
  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
  getSnapshot = (): SetupReviewState => this.state;
  constructor(
    private port: SetupReviewPort,
    private changed?: (state: SetupReviewState) => void,
  ) {}
  clear(): void {
    this.generation++;
    this.publish({
      review: null,
      claimed: false,
      busy: false,
      failed: false,
      failureCode: null,
      unknownOperationIds: [],
    });
  }
  resetReview(): void {
    this.generation++;
    this.publish({
      review: null,
      claimed: false,
      busy: false,
      failed: false,
      failureCode: null,
      unknownOperationIds: this.state.unknownOperationIds,
    });
  }
  private publish(state: SetupReviewState): void {
    this.state = state;
    this.changed?.(state);
    for (const listener of this.listeners) listener();
  }
  private async run(
    work: () => Promise<SetupReviewState>,
    uncertainAnswer: string | null = null,
  ): Promise<void> {
    if (this.state.busy) return;
    const generation = ++this.generation;
    this.publish({
      ...this.state,
      busy: true,
      failed: false,
      failureCode: null,
    });
    try {
      const next = await work();
      if (generation === this.generation) this.publish(next);
    } catch (error) {
      if (generation === this.generation)
        this.publish({
          review: null,
          claimed: false,
          busy: false,
          failed: uncertainAnswer === null,
          failureCode: failureCode(error),
          unknownOperationIds:
            uncertainAnswer === null ||
            this.state.unknownOperationIds.includes(uncertainAnswer)
              ? this.state.unknownOperationIds
              : [...this.state.unknownOperationIds, uncertainAnswer],
        });
    }
  }
  async read(operationId: string): Promise<void> {
    if (this.state.busy) return;
    this.resetReview();
    await this.run(async () => {
      const review = await this.port.read(operationId);
      if (
        review.kind !== "operation_review" ||
        review.operation_id !== operationId
      )
        throw new Error("review mismatch");
      return {
        review,
        claimed: false,
        busy: false,
        failed: false,
        failureCode: null,
        unknownOperationIds: this.state.unknownOperationIds,
      };
    });
  }
  async claim(): Promise<void> {
    const displayed = this.state.review;
    if (
      !displayed ||
      this.state.claimed ||
      this.state.unknownOperationIds.includes(displayed.operation_id)
    )
      return;
    await this.run(async () => {
      const review = await this.port.claim(coordinates(displayed));
      if (
        review.kind !== "operation_review_claimed" ||
        review.operation_id !== displayed.operation_id ||
        review.interaction_id !== displayed.interaction_id ||
        ![displayed.revision, displayed.revision + 1].includes(review.revision)
      )
        throw new Error("claim mismatch");
      return {
        review,
        claimed: true,
        busy: false,
        failed: false,
        failureCode: null,
        unknownOperationIds: this.state.unknownOperationIds,
      };
    });
  }
  async answer(decision: "apply" | "reject"): Promise<void> {
    const review = this.state.review;
    if (
      !review ||
      !this.state.claimed ||
      this.state.unknownOperationIds.includes(review.operation_id)
    )
      return;
    await this.run(async () => {
      const answered = await this.port.answer(coordinates(review), decision);
      if (
        answered.kind !== "operation_responded" ||
        answered.operation_id !== review.operation_id ||
        answered.decision !== decision
      )
        throw new Error("answer mismatch");
      return {
        review: null,
        claimed: false,
        busy: false,
        failed: false,
        failureCode: null,
        unknownOperationIds: this.state.unknownOperationIds,
      };
    }, review.operation_id);
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

export function browserVersion(
  document: Readonly<Record<string, unknown>>,
): string | null {
  const plan = record(record(document.projection)?.plan);
  const entry = Array.isArray(plan?.entries) ? record(plan.entries[0]) : null;
  return typeof entry?.target_version === "string"
    ? entry.target_version
    : null;
}

/** A refusal is recovery guidance, never permission to take another person's claim. */
export function reviewFailureKey(code: string | null): string {
  if (code === "review_already_claimed")
    return "desktop.setup_review.claimed_elsewhere";
  if (
    [
      "response_authority_required",
      "session_inactive",
      "session_expired",
      "session_retired",
      "runtime_changed",
      "custody_changed",
      "authority_unavailable",
      "connection_mismatch",
    ].includes(code ?? "")
  )
    return "desktop.setup_review.authority_lost";
  return "desktop.setup_review.failed";
}
