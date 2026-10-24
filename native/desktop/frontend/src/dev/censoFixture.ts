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
      burst(): void;
      /** Holds every answer in flight until `release`. */
      hold(): void;
      release(): void;
    };
  }
}
/** Browser-only Censo outcomes. Never contacts AEAT. */
export function censoFixture(
  profile: UserProfilePort & { peek(path: string): string | null },
  mode?: "ready" | "nie" | "uncertain",
): CensoPort {
  let ready = mode === "ready" || mode === "uncertain",
    failure = mode === "uncertain",
    starts = 0,
    answers = 0;
  let snapshot: CensoSnapshot | null = null;
  let statuses = 0;
  const listeners = new Set<() => void>();
  // An answer waits here while held: released by the scenario, not a timer.
  let held: Promise<void> | null = null;
  let release = () => {};
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
      return structuredClone(snapshot);
    },
    async status() {
      statuses++;
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
