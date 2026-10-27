import fixtures from "./fixtures/userProfile.json";
import type { CensoMode } from "./censoFixture";
import type { CensoReadiness } from "../shell/profileCenso";
import type {
  ProfileChange,
  UserProfile,
  UserProfilePort,
} from "../shell/userProfile";

declare global {
  interface Window {
    __scenarioProfile?: {
      update(value: string): void;
      refuse(): void;
      uncertain(): void;
      conflict(): void;
      deferRead(): void;
      releaseRead(): void;
      rejectRead(): void;
      reads(): number;
      writes(): number;
      burst(): void;
      complete(): void;
      completeWithMissing(): void;
      changeIdentity(): void;
      /** The providers whose passphrase or password was saved. */
      credentials(): string[];
      /** How many times a credential save was sent, whatever came of it. */
      credentialAttempts(): number;
      /** The next credential save is refused, or ends unconfirmed. */
      failCredential(outcome: CredentialFailure): void;
      /** The next file dialog picks a file that is not a certificate. */
      failPick(): void;
      /** The certificate file the profile was configured with, by name. */
      certificate(): string | null;
      /** How many times the file dialog was opened. */
      picks(): number;
    };
  }
}

/** How a credential save may end other than saved, as the host words it. */
type CredentialFailure = "refused" | "unknown" | "saved_unread" | "unavailable";

export type ProfileFixture = UserProfilePort & {
  /** What the saved profile and credentials satisfy, as the product reads
   * them for a Censo sync: never a call to AEAT. */
  readiness(profile: string): Promise<CensoReadiness>;
};

/** The facts of the authentication section the host takes as field edits. */
const AUTH_FACTS = [
  "auth.dni_nie",
  "auth.numero_soporte",
  "auth.fecha_validez",
];

/** The certificate file the scenario's dialog picks. */
const PICKED = { token: "c".repeat(64), name: "firma-ana-soler.p12" };

/** Synthetic values, but the complete production schema and localized projection.
 * Regenerate with dev.desktop_profile_fixture; never invent fields here. */
export function userProfileFixture(censoSetup?: CensoMode): ProfileFixture {
  const data = structuredClone(fixtures.en) as UserProfile;
  if (censoSetup) {
    const values: Record<string, string> = {
      "identity.tax_id": "X1234567L",
      "auth.provider": "clave_movil",
      "auth.clave_movil_route": "app_request",
      "auth.dni_nie": "••••",
      ...(censoSetup === "nie" ? {} : { "auth.numero_soporte": "••••" }),
    };
    for (const field of data.sections.flatMap((section) => section.fields)) {
      if (field.path in values) {
        field.value = values[field.path]!;
        if (
          field.path === "auth.dni_nie" ||
          field.path === "auth.numero_soporte"
        )
          field.masked = true;
      }
    }
    data.missing_required = data.missing_required.filter(
      (path) => path !== "identity.tax_id",
    );
  }
  const listeners = new Set<() => void>();
  let reads = 0,
    writes = 0;
  let refuse: "refused" | "unknown" | "conflict" | null = null;
  let deferred = false;
  let release: (() => void) | undefined;
  let reject: (() => void) | undefined;
  const credentials = new Set<string>();
  let certificate: string | null = null;
  let picks = 0;
  let attempts = 0;
  let credentialFailure: CredentialFailure | null = null;
  let pickFailure = false;
  const fieldOf = (path: string) =>
    data.sections
      .flatMap((section) => section.fields)
      .find((entry) => entry.path === path);
  const changed = () => {
    data.record_revision++;
    data.content_digest = String(data.record_revision).padStart(64, "0");
    data.missing_required = data.sections
      .flatMap((section) => section.fields)
      .filter((field) => field.required && !field.value)
      .map((field) => field.path);
    listeners.forEach((listener) => listener());
  };
  const controls = {
    changeIdentity() {
      data.profile_id = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
      listeners.forEach((listener) => listener());
    },
    completeWithMissing() {
      data.setup_state = "complete";
      data.valid = true;
      listeners.forEach((listener) => listener());
    },
    complete() {
      data.setup_state = "complete";
      data.valid = true;
      data.missing_required = [];
      data.notices = [];
      listeners.forEach((listener) => listener());
    },
    update(value: string) {
      data.sections
        .flatMap((section) => section.fields)
        .find((field) => field.path === "identity.name")!.value = value;
      changed();
    },
    refuse() {
      refuse = "refused";
    },
    uncertain() {
      refuse = "unknown";
    },
    conflict() {
      data.record_revision++;
      data.content_digest = String(data.record_revision).padStart(64, "0");
      refuse = "conflict";
    },
    deferRead() {
      deferred = true;
    },
    releaseRead() {
      release?.();
    },
    rejectRead() {
      reject?.();
    },
    credentials: () => [...credentials],
    credentialAttempts: () => attempts,
    failCredential(outcome: CredentialFailure) {
      credentialFailure = outcome;
    },
    failPick() {
      pickFailure = true;
    },
    certificate: () => certificate,
    picks: () => picks,
    reads: () => reads,
    writes: () => writes,
    burst() {
      for (let i = 0; i < 25; i++) listeners.forEach((listener) => listener());
    },
  };
  return {
    async read(language) {
      window.__scenarioProfile = controls;
      reads++;
      const snapshot = structuredClone(data);
      const localized =
        fixtures[language as keyof typeof fixtures] ?? fixtures.en;
      snapshot.sections = snapshot.sections.map((section) => {
        const translated = localized.sections.find(
          (entry) => entry.key === section.key,
        )!;
        return {
          ...section,
          title: translated.title,
          summary: translated.summary,
          fields: section.fields.map((field) => {
            const template = translated.fields.find(
              (entry) =>
                entry.path.split(".").at(-1) === field.path.split(".").at(-1),
            );
            return template
              ? {
                  ...field,
                  label: template.label,
                  help: template.help,
                  about: template.about,
                  choices: template.choices,
                }
              : field;
          }),
        };
      });
      if (deferred) {
        deferred = false;
        await new Promise<void>((resolve, refused) => {
          release = resolve;
          reject = () => refused({ code: "unavailable" });
        });
      }
      await new Promise((resolve) => setTimeout(resolve, 40));
      return snapshot;
    },
    async observe(listener) {
      window.__scenarioProfile = controls;
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    async change(change: ProfileChange) {
      writes++;
      if (refuse) {
        const code = refuse;
        refuse = null;
        throw { code };
      }
      if (
        change.expected_revision !== data.record_revision ||
        change.expected_content_digest !== data.content_digest
      )
        throw { code: "conflict" };
      const edit = change.edit;
      if (edit.kind === "field") {
        const target = fieldOf(edit.path);
        // The host takes the method only as one sign-in method: of the
        // authentication section, only its facts are field edits.
        if (
          !target ||
          (edit.path.startsWith("auth.") && !AUTH_FACTS.includes(edit.path))
        )
          throw { code: "refused" };
        // A masked detail is read back masked, as the host reads it.
        target.value = edit.value
          ? target.masked
            ? "••••"
            : edit.value
          : null;
      } else if (edit.kind === "auth_method") {
        const provider = fieldOf("auth.provider")!;
        if (
          !provider.choices.some((choice) => choice.value === edit.provider) ||
          (edit.certificate !== null && edit.certificate !== PICKED.token)
        )
          throw { code: "refused" };
        provider.value = edit.provider;
        fieldOf("auth.clave_movil_route")!.value = edit.clave_movil_route;
        if (edit.certificate !== null) certificate = PICKED.name;
      } else if (edit.kind === "complete") data.setup_state = "complete";
      else {
        const section = data.sections.find(
          (item) => item.key === edit.section_key,
        )!;
        const template = fixtures.en.sections.find(
          (item) => item.key === section.key,
        )!;
        if (edit.kind === "add_row") {
          const index = String(
            Math.max(
              -1,
              ...section.fields.map((field) =>
                field.row_index === null ? -1 : Number(field.row_index),
              ),
            ) + 1,
          );
          const fields = template.fields.map((field) => ({
            ...structuredClone(field),
            path: `${section.key}.${index}.${field.path.split(".").at(-1)}`,
            row_index: index,
            value:
              edit.values.find(
                (entry) => entry.field_key === field.path.split(".").at(-1),
              )?.value ?? null,
          }));
          section.fields = [
            ...section.fields.filter((field) => field.row_index !== null),
            ...fields,
          ];
        } else if (edit.kind === "remove_row") {
          section.fields = section.fields.filter(
            (field) => field.row_index !== edit.row_key,
          );
          if (!section.fields.length)
            section.fields = structuredClone(template.fields);
        } else {
          for (const field of section.fields.filter(
            (field) => field.row_index === edit.row_key,
          )) {
            const key = field.path.split(".").at(-1)!;
            const value = edit.values.find((value) => value.field_key === key);
            if (value) field.value = value.value;
            else if (edit.clear_fields.includes(key)) field.value = null;
          }
        }
      }
      changed();
    },
    aeat: {
      async pickCertificate() {
        window.__scenarioProfile = controls;
        picks++;
        if (pickFailure) {
          pickFailure = false;
          throw { code: "invalid" };
        }
        return { ...PICKED };
      },
      async saveCredential(credential) {
        attempts++;
        if (credentialFailure) {
          const code = credentialFailure;
          credentialFailure = null;
          throw { code };
        }
        if (credential.profile_id !== data.profile_id || !credential.password)
          throw { code: "refused" };
        credentials.add(credential.provider);
      },
    },
    async readiness(profile) {
      if (profile !== data.profile_id) throw { code: "refused" };
      const value = (path: string) => fieldOf(path)?.value ?? "";
      const provider = value("auth.provider");
      const route =
        provider === "clave_movil"
          ? value("auth.clave_movil_route") || "app_request"
          : "";
      const need = (
        field: string,
        satisfied: boolean,
        reason: string,
        secret = false,
      ) => ({ field, satisfied, reason, secret });
      const requirements = [
        need(
          "identity.tax_id",
          !!value("identity.tax_id"),
          "profile_tax_id_required",
        ),
        need("auth.provider", !!provider, "auth_method_required"),
      ];
      if (provider === "certificate")
        requirements.push(
          need(
            "certificate.file",
            certificate !== null,
            "certificate_file_required",
          ),
          need(
            "certificate.passphrase",
            credentials.has("certificate"),
            "certificate_passphrase_required",
            true,
          ),
        );
      else if (provider === "clave_movil" || provider === "clave_permanente") {
        requirements.push(
          need(
            "auth.dni_nie",
            !!value("auth.dni_nie"),
            "clave_identity_required",
          ),
        );
        if (route === "app_request") {
          const nie = /^[XYZ]/i.test(value("identity.tax_id"));
          requirements.push(
            nie
              ? need(
                  "auth.numero_soporte",
                  !!value("auth.numero_soporte"),
                  "nie_support_required",
                )
              : need(
                  "auth.fecha_validez",
                  !!value("auth.fecha_validez"),
                  "dni_validity_required",
                ),
          );
        }
        if (provider === "clave_permanente")
          requirements.push(
            need(
              "auth.password",
              credentials.has("clave_permanente"),
              "clave_password_required",
              true,
            ),
          );
      }
      return {
        provider,
        route,
        ready: requirements.every((item) => item.satisfied),
        requirements,
      };
    },
  };
}
