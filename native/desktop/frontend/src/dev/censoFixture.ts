import type { CensoPort, CensoSnapshot } from "../shell/profileCenso";
import type { UserProfilePort } from "../shell/userProfile";

declare global {
  interface Window {
    __scenarioCenso?: {
      ready(): void;
      fail(): void;
      starts(): number;
      answers(): number;
      statuses(): number;
      readinessChecks(): number;
      burst(): void;
      /** Holds every answer in flight until `release`. */
      hold(): void;
      release(): void;
      holdReadiness(): void;
      releaseReadiness(): void;
      releaseStatus(): void;
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
  | "browser_missing";

/** Browser-only Censo outcomes. Never contacts AEAT. */
export function censoFixture(
  profile: UserProfilePort & { peek(path: string): string | null },
  mode?: CensoMode,
): CensoPort {
  let ready =
      mode === "ready" ||
      mode === "uncertain" ||
      mode === "refused" ||
      mode === "initial_unknown" ||
      mode === "browser_missing",
    failure = mode === "uncertain",
    starts = 0,
    answers = 0;
  let snapshot: CensoSnapshot | null = null;
  let releaseStatus = () => {};
  const statusHeld =
    mode === "initial_unknown"
      ? new Promise<void>((resolve) => {
          releaseStatus = resolve;
        })
      : null;
  let statuses = 0;
  let readinessChecks = 0;
  const listeners = new Set<() => void>();
  // An answer waits here while held: released by the scenario, not a timer.
  let held: Promise<void> | null = null;
  let release = () => {};
  let readinessHeld: Promise<void> | null = null;
  let releaseReadiness = () => {};
  const controls = {
    ready() {
      ready = true;
    },
    fail() {
      failure = true;
    },
    starts: () => starts,
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
    releaseStatus: () => releaseStatus(),
  };
  return {
    async observe(changed) {
      listeners.add(changed);
      return () => {
        listeners.delete(changed);
      };
    },
    async readiness() {
      window.__scenarioCenso = controls;
      await readinessHeld;
      readinessChecks++;
      const taxId = profile.peek("identity.tax_id");
      const requirements = [
        {
          field: "identity.tax_id",
          satisfied: ready || mode === "nie" || !!taxId,
          reason: "profile_tax_id_required",
          secret: false,
        },
        {
          field: "auth.provider",
          satisfied: ready || mode === "nie",
          reason: "auth_method_required",
          secret: false,
        },
        ...(mode !== "nie"
          ? []
          : [
              {
                field: "auth.numero_soporte",
                satisfied: false,
                reason: "nie_support_required",
                secret: false,
              },
            ]),
      ];
      return {
        provider: ready || mode === "nie" ? "clave_movil" : "",
        route: "app_request",
        ready: requirements.every((r) => r.satisfied),
        requirements,
      };
    },
    async start() {
      starts++;
      if (failure) throw { code: "unknown" };
      if (mode === "refused")
        throw { code: "refused", reason: "profile_mismatch" };
      // Each pull stops at once for want of the browser, as its recorded
      // verdict says.
      if (mode === "browser_missing") {
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
      snapshot = {
        operation: "a".repeat(64),
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
      };
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
