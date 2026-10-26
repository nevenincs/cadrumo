import fixtures from "./fixtures/userProfile.json";
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
    };
  }
}

/** Synthetic values, but the complete production schema and localized projection.
 * Regenerate with dev.desktop_profile_fixture; never invent fields here. */
export function userProfileFixture(
  censoSetup?: "ready" | "nie" | "uncertain" | "refused" | "initial_unknown",
): UserProfilePort & {
  /** A saved value, as the fixture's other ports read it: not a page read. */
  peek(path: string): string | null;
} {
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
    reads: () => reads,
    writes: () => writes,
    burst() {
      for (let i = 0; i < 25; i++) listeners.forEach((listener) => listener());
    },
  };
  return {
    peek: (path) =>
      data.sections
        .flatMap((section) => section.fields)
        .find((field) => field.path === path)?.value ?? null,
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
        const target = data.sections
          .flatMap((section) => section.fields)
          .find((entry) => entry.path === edit.path);
        if (!target) throw { code: "refused" };
        target.value = edit.value || null;
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
  };
}
