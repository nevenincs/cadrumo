/** The one closed list of what a data-entry field can hold. */
export type FieldKind =
  | "text"
  | "notes"
  | "date"
  | "year"
  | "money"
  | "decimal"
  | "integer"
  | "percent"
  | "taxId"
  | "iban"
  | "bic"
  | "country"
  | "currency"
  | "choice";

/** A field's kind with what that kind must be told. */
export type FieldSpec =
  | { kind: "text"; mono?: boolean; maxLength?: number }
  | { kind: "notes"; maxLength?: number }
  | { kind: "date"; min?: string; max?: string }
  | { kind: "year" }
  | { kind: "money"; decimals?: number; zero?: boolean }
  | { kind: "decimal"; decimals?: number; zero?: boolean }
  | { kind: "integer" }
  | { kind: "percent"; unit: "fraction" | "points" }
  | { kind: "taxId" }
  | { kind: "iban"; secret?: boolean }
  | { kind: "bic"; secret?: boolean }
  | { kind: "country"; secret?: boolean }
  | { kind: "currency" }
  | {
      kind: "choice";
      choices: readonly { value: string; label: string }[];
    };
