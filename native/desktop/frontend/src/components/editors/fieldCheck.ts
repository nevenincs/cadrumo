import { parsePoints } from "@/components/ledger/setup/setupModel";
import type { FieldSpec } from "@/shared/fieldKind";
import { ibanMalformed, ibanText } from "@/shared/iban";
import {
  AMOUNT_RULE,
  parseDecimal,
  parseFractionPercent,
  parseIsoDate,
  parseLine,
  parseYear,
  QUANTITY_RULE,
  TAX_AMOUNT_RULE,
  UNIT_PRICE_RULE,
  type GrammarRefusalKey,
  type Parsed,
} from "@/shell/ledgerGrammar";

const LINE_LIMIT = 4096;

function byShape(
  raw: string,
  shape: RegExp,
  key: GrammarRefusalKey,
): Parsed<string> {
  const text = raw.trim();
  if (text === "") return { kind: "empty" };
  return shape.test(text)
    ? { kind: "value", value: text }
    : { kind: "refused", refusal: { key, raw } };
}

/**
 * Whether what an editor holds is well formed, as the value to send. It checks
 * form alone: which codes exist, what a value may be and every rule with a tax
 * consequence stay the backend's. Limits a field has served come in its `spec`.
 */
export function checkField(field: FieldSpec, raw: string): Parsed<string> {
  switch (field.kind) {
    case "text":
      return parseLine(
        raw,
        field.maxLength === undefined ? LINE_LIMIT : field.maxLength,
      );
    case "notes":
    case "choice":
      return raw.trim() === ""
        ? { kind: "empty" }
        : { kind: "value", value: raw };
    case "date":
      return parseIsoDate(raw);
    case "year": {
      const year = parseYear(raw);
      return year.kind === "value"
        ? { kind: "value", value: String(year.value) }
        : year;
    }
    case "money":
      return parseDecimal(
        raw,
        field.decimals !== undefined
          ? { decimals: field.decimals, zero: field.zero ?? true }
          : field.zero === false
            ? AMOUNT_RULE
            : TAX_AMOUNT_RULE,
      );
    case "decimal":
      return parseDecimal(
        raw,
        field.decimals !== undefined
          ? { decimals: field.decimals, zero: field.zero ?? true }
          : field.zero === false
            ? QUANTITY_RULE
            : UNIT_PRICE_RULE,
      );
    case "integer":
      return byShape(raw, /^\d+$/, "not_a_number");
    case "percent":
      return field.unit === "fraction"
        ? parseFractionPercent(raw)
        : parsePoints(raw);
    case "taxId":
      return parseLine(raw, 64);
    case "iban": {
      const iban = ibanText(raw);
      if (iban === "") return { kind: "empty" };
      return ibanMalformed(iban)
        ? { kind: "refused", refusal: { key: "not_an_iban", raw } }
        : { kind: "value", value: iban };
    }
    case "bic":
      return byShape(raw, /^[A-Z0-9]{8}([A-Z0-9]{3})?$/, "not_a_bic");
    case "country":
      return byShape(raw, /^[A-Z]{2}$/, "not_a_country");
    case "currency":
      return byShape(raw, /^[A-Z]{3}$/, "not_a_currency");
  }
}
