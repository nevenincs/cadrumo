import type { SuggestionProps } from "@/components/editors/editorProps";
import type { FieldSpec } from "../../../shared/fieldKind";
import { heldDecimal } from "../../../shared/numbers";
import type { PublicDecimal } from "../../../shell/ledger";
import {
  canonicalDecimal,
  parseDecimal,
  parseFractionPercent,
  parseIsoDate,
  parseLine,
  QUANTITY_RULE,
  TAX_AMOUNT_RULE,
  type GrammarRefusal,
  type Parsed,
} from "../../../shell/ledgerGrammar";
import { REGISTER_CURRENCY, type AssetFamily } from "./assetsWords";

/** `candidate` is a choice among the purchases the backend offers, picked
 * and never typed; `share` is a percentage typed, a fraction sent;
 * `quantity` is a plain number such as hours or square metres. */
export type FormControl =
  | "text"
  | "taxid"
  | "date"
  | "amount"
  | "share"
  | "quantity"
  | "whole"
  | "year"
  | "choice"
  | "flag"
  | "candidate";

/** What a form states, by field key: text, a decimal, a whole number, a
 * choice's token, a flag, or null where nothing was stated. */
export type FormValue = string | number | boolean | PublicDecimal | null;
export type FormValues = Record<string, FormValue>;

/** One choice of a field: the backend's token, worded by the family the
 * token belongs to, by the catalogue key `word`, or by the text the backend
 * serves with it (a table class's official name). */
export type FieldChoice = {
  token: string;
  family: AssetFamily | null;
  label?: string;
  word?: string;
};

export type FormField = {
  key: string;
  label_key: string;
  control: FormControl;
  required: boolean;
  choices: FieldChoice[];
  /** What the record states now, as text, where the form starts from it. */
  current?: string | null;
  /** The word that says how to write the value. */
  hint_key?: string | null;
  /** The text the field offers as it is typed in, where the form holds any. */
  offers?: SuggestionProps;
};

/** The text typed into each field of a form, by field key. */
export type FormDraft = Record<string, string>;

// ---- Typed text into values ---------------------------------------------------

/** The kind of editor a control is drawn on; none for a choice, which the
 * form draws as a list. */
export function specOf(found: FormField): FieldSpec | null {
  switch (found.control) {
    case "text":
      return { kind: "text" };
    case "taxid":
      return { kind: "taxId" };
    case "date":
      return { kind: "date" };
    case "amount":
      return { kind: "money", currency: REGISTER_CURRENCY };
    case "share":
      return { kind: "percent", unit: "fraction" };
    case "quantity":
      return { kind: "decimal" };
    case "whole":
      return { kind: "integer" };
    case "year":
      return { kind: "year" };
    case "choice":
    case "flag":
    case "candidate":
      return null;
  }
}

const NUMBER_CONTROLS: ReadonlySet<FormControl> = new Set([
  "amount",
  "quantity",
  "share",
]);

/** A draft with each stated number held as an editor holds it: the canonical
 * decimal text, a share as the fraction the backend states. */
export const seedDraft = (
  fields: readonly FormField[],
  draft: FormDraft,
): FormDraft =>
  Object.fromEntries(
    Object.entries(draft).map(([key, text]) => {
      const control = fields.find((found) => found.key === key)?.control;
      const number = control !== undefined && NUMBER_CONTROLS.has(control);
      return [
        key,
        number && text !== ""
          ? heldDecimal(canonicalDecimal(text) ?? text)
          : text,
      ];
    }),
  );

/** Each field starting from what the record states now. */
export const draftOf = (fields: readonly FormField[]): FormDraft =>
  seedDraft(
    fields,
    Object.fromEntries(fields.map((found) => [found.key, found.current ?? ""])),
  );

const empty: Parsed<FormValue> = { kind: "empty" };
const value = (found: FormValue): Parsed<FormValue> => ({
  kind: "value",
  value: found,
});

/** One field's text as the value its control takes. Nothing typed is empty;
 * a refusal says why the text cannot be read. */
export function parseField(found: FormField, raw: string): Parsed<FormValue> {
  switch (found.control) {
    case "text":
    case "taxid":
      return parseLine(raw);
    case "date":
      return parseIsoDate(raw);
    case "amount": {
      const parsed = parseDecimal(raw, TAX_AMOUNT_RULE);
      return parsed.kind === "value"
        ? value({ decimal: parsed.value })
        : parsed;
    }
    case "quantity": {
      const parsed = parseDecimal(raw, QUANTITY_RULE);
      return parsed.kind === "value"
        ? value({ decimal: parsed.value })
        : parsed;
    }
    case "share": {
      const parsed = parseFractionPercent(raw);
      return parsed.kind === "value"
        ? value({ decimal: parsed.value })
        : parsed;
    }
    case "whole":
    case "year": {
      const typed = raw.trim();
      if (typed === "") return { kind: "empty" };
      return /^\d{1,9}$/.test(typed)
        ? value(Number(typed))
        : { kind: "refused", refusal: { key: "not_a_number", raw } };
    }
    case "flag":
      return raw === "yes" ? value(true) : raw === "no" ? value(false) : empty;
    case "choice":
    case "candidate":
      return raw === "" ? empty : value(raw);
  }
}

export type Answered = {
  values: FormValues;
  problems: Record<string, GrammarRefusal>;
  /** Fields emptied that the record cannot do without. */
  cleared: string[];
};

/**
 * What a form's text says. A full form states every field, null where
 * nothing was typed, so the backend names what is missing. Given `initial`,
 * only the fields changed from it are stated: a field emptied is stated as
 * null, which clears it, and one the record cannot do without is named in
 * `cleared` and not stated.
 */
export function answer(
  fields: readonly FormField[],
  draft: FormDraft,
  initial: FormDraft | null,
): Answered {
  const values: FormValues = {};
  const problems: Record<string, GrammarRefusal> = {};
  const cleared: string[] = [];
  for (const found of fields) {
    const raw = draft[found.key] ?? "";
    if (initial !== null && raw === (initial[found.key] ?? "")) continue;
    const parsed = parseField(found, raw);
    if (parsed.kind === "refused") problems[found.key] = parsed.refusal;
    else if (parsed.kind === "value") values[found.key] = parsed.value;
    else if (initial === null) values[found.key] = null;
    else if (found.required) cleared.push(found.key);
    else values[found.key] = null;
  }
  return { values, problems, cleared };
}
