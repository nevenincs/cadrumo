import type { CensoPort, CensoSnapshot } from "../shell/profileCenso";
import type { ProfileFixture } from "./userProfileFixture";

declare global {
  interface Window {
    __scenarioCenso?: {
      fail(): void;
      starts(): number;
      /** The pulls the host actually began: a start while one is unfinished
       * answers that one. */
      pulls(): number;
      answers(): number;
      statuses(): number;
      readinessChecks(): number;
      burst(): void;
      /** Holds every answer in flight until `release`. */
      hold(): void;
      release(): void;
      holdReadiness(): void;
      releaseReadiness(): void;
      holdStatus(): void;
      releaseStatus(): void;
      /** The pull begins at the host without this window asking, as the AEAT
       * data run's census item does. */
      begin(): void;
      /** A running pull reaches its review. */
      reachReview(): void;
    };
  }
}
/** How the scenario's Censo pull goes. */
export type CensoMode =
  | "ready"
  | "nie"
  | "uncertain"
  | "refused"
  | "initial_unknown"
  | "browser_missing"
  /** The pull keeps reading until the scenario lets it reach its review. */
  | "running";

/** Browser-only Censo outcomes. Never contacts AEAT. */
export function censoFixture(
  profile: ProfileFixture,
  mode?: CensoMode,
): CensoPort {
  let failure = mode === "uncertain",
    starts = 0,
    pulls = 0,
    answers = 0;
  let snapshot: CensoSnapshot | null = null;
  let releaseStatus = () => {};
  let statusHeld: Promise<void> | null = null;
  const holdStatus = () => {
    statusHeld ??= new Promise<void>((resolve) => {
      releaseStatus = () => {
        statusHeld = null;
        resolve();
      };
    });
  };
  if (mode === "initial_unknown") holdStatus();
  let statuses = 0;
  let readinessChecks = 0;
  const listeners = new Set<() => void>();
  // An answer waits here while held: released by the scenario, not a timer.
  let held: Promise<void> | null = null;
  let release = () => {};
  let readinessHeld: Promise<void> | null = null;
  let releaseReadiness = () => {};
  const controls = {
    fail() {
      failure = true;
    },
    starts: () => starts,
    pulls: () => pulls,
    answers: () => answers,
    statuses: () => statuses,
    readinessChecks: () => readinessChecks,
    burst() {
      for (let i = 0; i < 25; i++) listeners.forEach((listener) => listener());
    },
    hold() {
      held ??= new Promise<void>((resolve) => {
        release = () => {
          held = null;
          resolve();
        };
      });
    },
    release: () => release(),
    holdReadiness() {
      readinessHeld ??= new Promise<void>((resolve) => {
        releaseReadiness = () => {
          readinessHeld = null;
          resolve();
        };
      });
    },
    releaseReadiness: () => releaseReadiness(),
    holdStatus,
    releaseStatus: () => releaseStatus(),
    begin() {
      snapshot ??= began();
      listeners.forEach((listener) => listener());
    },
    reachReview() {
      if (snapshot?.state !== "reading") return;
      snapshot = { ...snapshot, ...reviewing() };
      listeners.forEach((listener) => listener());
    },
  };
  // A pull begins at the host: here from a start, or from the run that
  // starts the same session without this window asking.
  const began = (): CensoSnapshot => {
    pulls++;
    return mode === "running"
      ? {
          operation: "d".repeat(64),
          state: "reading",
          can_cancel: false,
          review_digest: null,
          fields: [],
        }
      : { operation: "a".repeat(64), ...reviewing() };
  };
  const reviewing = (): Omit<CensoSnapshot, "operation"> => ({
    state: "review",
    can_cancel: true,
    review_digest: "b".repeat(64),
    fields: [
      {
        path: "contact.fiscal_address",
        current: "Calle Larios 12, 2 A, Málaga",
        incoming: "Calle Nueva 1, Málaga",
        preserve: true,
      },
      {
        path: "contact.postcode",
        current: "29005",
        incoming: "29001",
        preserve: true,
      },
      {
        path: "contact.fiscal_address_cadastral_reference",
        current: null,
        incoming: "1234567UF7613S0001AB",
        preserve: false,
      },
    ],
  });
  window.__scenarioCenso = controls;
  return {
    async observe(changed) {
      listeners.add(changed);
      return () => {
        listeners.delete(changed);
      };
    },
    async readiness(id) {
      await readinessHeld;
      readinessChecks++;
      // What the profile saved satisfies: the setup the scenario seeded, and
      // whatever the person has entered since.
      return profile.readiness(id);
    },
    async start() {
      starts++;
      if (failure) throw { code: "unknown" };
      // The host answers the pull still going rather than begin another.
      if (
        snapshot &&
        snapshot.state !== "done" &&
        snapshot.state !== "stopped" &&
        snapshot.state !== "failed"
      )
        return structuredClone(snapshot);
      if (mode === "refused")
        throw { code: "refused", reason: "profile_mismatch" };
      // Each pull stops at once for want of the browser, as its recorded
      // verdict says.
      if (mode === "browser_missing") {
        pulls++;
        snapshot = {
          operation: String(starts).padStart(64, "c"),
          state: "failed",
          can_cancel: false,
          review_digest: null,
          recovery_action_id: "operator.provision.browser",
          fields: [],
        };
        return structuredClone(snapshot);
      }
      snapshot = began();
      if (mode === "initial_unknown")
        return {
          ...snapshot,
          state: "unknown",
          can_cancel: false,
          review_digest: null,
          fields: [],
        };
      return structuredClone(snapshot);
    },
    async status() {
      statuses++;
      await statusHeld;
      if (!snapshot || failure) throw { code: "unavailable" };
      return structuredClone(snapshot);
    },
    async answer(_, operation, digest, decision) {
      answers++;
      await held;
      if (failure) throw { code: "unknown" };
      if (
        !snapshot ||
        snapshot.operation !== operation ||
        (decision !== "cancel" && snapshot.review_digest !== digest)
      )
        throw { code: "conflict" };
      if (decision === "apply") {
        const current = await profile.read("en");
        await profile.change({
          profile_id: current.profile_id,
          expected_revision: current.record_revision,
          expected_content_digest: current.content_digest,
          edit: {
            kind: "field",
            path: "contact.fiscal_address_cadastral_reference",
            value: "1234567UF7613S0001AB",
          },
        });
      }
      snapshot = {
        ...snapshot,
        state: decision === "apply" ? "done" : "stopped",
        can_cancel: false,
        review_digest: null,
        fields: [],
      };
      return structuredClone(snapshot);
    },
  };
}
