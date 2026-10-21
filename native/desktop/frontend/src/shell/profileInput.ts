import type { ProfileField } from "./userProfile";

const AUTOFILL: Readonly<Record<string, string>> = {
  "identity.name": "given-name",
  "identity.surnames": "family-name",
  "identity.legal_name": "organization",
  "identity.email": "email",
  "contact.contact_person_name": "section-contact name",
  "contact.contact_person_phone": "section-contact tel-national",
  "contact.fiscal_address": "street-address",
  "contact.postcode": "postal-code",
  "contact.fiscal_municipality": "address-level2",
  "contact.fiscal_province": "address-level1",
  "contact.fiscal_country": "country",
};

/** Browser hints follow canonical fields, never a guessed current value. */
export function profileInput(field: ProfileField) {
  const secret = field.masked || field.path.startsWith("auth.");
  const autoComplete = secret ? "off" : (AUTOFILL[field.path] ?? "off");
  const type =
    field.field_type === "email"
      ? "email"
      : field.field_type === "date"
        ? "date"
        : autoComplete.endsWith("tel-national")
          ? "tel"
          : "text";
  const inputMode =
    type === "tel"
      ? "tel"
      : type === "email"
        ? "email"
        : field.field_type === "integer"
          ? "numeric"
          : ["decimal", "money"].includes(field.field_type)
            ? "decimal"
            : "text";
  return { name: field.path, autoComplete, type, inputMode } as const;
}
