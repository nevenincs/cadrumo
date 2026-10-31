import { heldDecimal } from "@/shared/numbers";
import { parseIsoDate } from "./ledgerGrammar";
import type { ProfileField } from "./userProfile";

const PHONE_FIELDS: ReadonlySet<string> = new Set([
  "contact.contact_person_phone",
]);

/** The kinds of detail the profile enters with a typed editor; anything else
 * is a line of text. */
export type ProfileEntryKind =
  "date" | "integer" | "decimal" | "money" | "tax_id" | "text";

/** Which editor a detail is entered in. Every detail asks the browser to
 * remember nothing: taxpayer facts are kept only in the profile's encrypted
 * custody, never in browser form history. */
export function profileInput(field: ProfileField) {
  const kind: ProfileEntryKind =
    field.path === "auth.dni_nie" || field.path === "identity.tax_id"
      ? "tax_id"
      : field.field_type === "date" ||
          field.field_type === "integer" ||
          field.field_type === "decimal" ||
          field.field_type === "money"
        ? field.field_type
        : "text";
  const type =
    field.field_type === "email"
      ? "email"
      : PHONE_FIELDS.has(field.path)
        ? "tel"
        : "text";
  return { name: field.path, autoComplete: "off", kind, type } as const;
}

/** The text typed in a date detail that names no day, or null when the detail
 * is not a date, is empty, or holds a day. Such text stays in the field and
 * blocks the save: it is never read as an empty date, which would clear what
 * is stored. */
export function unreadDate(field: ProfileField, value: string): string | null {
  if (field.field_type !== "date" || value.trim() === "") return null;
  return parseIsoDate(value).kind === "value" ? null : value;
}

const DECIMAL_KINDS: ReadonlySet<string> = new Set(["decimal", "money"]);

/** What a decimal detail's editor starts as for a stored value: text that
 * could mean thousands or decimals is held with a trailing zero, so the field
 * shows the number that is stored. */
export function seededValue(field: ProfileField, stored: string): string {
  return DECIMAL_KINDS.has(field.field_type) ? heldDecimal(stored) : stored;
}

/** What is saved for an editor's text: the stored spelling when the person
 * left a seeded decimal as it came. */
export function savedValue(field: ProfileField, value: string): string {
  const stored = field.value ?? "";
  return DECIMAL_KINDS.has(field.field_type) &&
    value === heldDecimal(stored) &&
    stored !== ""
    ? stored
    : value;
}
