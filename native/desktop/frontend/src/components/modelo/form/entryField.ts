import type { FieldSpec } from "../../../shared/fieldKind";
import type {
  ModeloEditValueGrammarV1,
  ModeloEditWritableScalarSurfaceEntryV1,
} from "../../../shell/modeloContract";
import type { Translate } from "../../../shell/strings";

// Which editor an address takes, from the grammar the application served for
// it. The editors only hold what is typed: the application reads it.

/** A casilla's data type, as the registry declares it. */
type CasillaDataType = ModeloEditWritableScalarSurfaceEntryV1["data_type"];

const MONO: FieldSpec = { kind: "text", mono: true };

/** Keyed by the generated type, so a type the registry gains does not compile
 * until it is placed here. */
const CASILLA_FIELDS: Record<CasillaDataType, FieldSpec> = {
  decimal: { kind: "decimal" },
  money: { kind: "money" },
  integer: { kind: "integer" },
  ratio: { kind: "decimal" },
  year: { kind: "year" },
  boolean: { kind: "choice", choices: [] },
  date: { kind: "date" },
  text: { kind: "text" },
  nif: { kind: "taxId" },
  period_code: MONO,
  country_code: { kind: "country" },
  iban: { kind: "iban" },
  name: { kind: "text" },
  nif_iva: { kind: "taxId" },
  ccaa_code: MONO,
  province_code: MONO,
  postal_code: MONO,
  municipality_code: MONO,
  bic: { kind: "bic" },
};

/** A binding's token, which is typed as declared. */
const fieldOfType = (dataType: string): FieldSpec | null =>
  dataType === "enum"
    ? MONO
    : Object.hasOwn(CASILLA_FIELDS, dataType)
      ? CASILLA_FIELDS[dataType as CasillaDataType]
      : null;

/** Whether a value can be typed against `grammar`: a channel carries it and
 * its data type is one an editor is known for. */
export const takesEntry = (grammar: ModeloEditValueGrammarV1): boolean =>
  grammar.channel !== "unavailable" && fieldOfType(grammar.data_type) !== null;

/** The editor for an address. A figure the registry declares no percentage
 * for keeps a plain figure: what is typed is read as written, never moved a
 * hundredfold. A yes or no goes as the `1` or `0` every language reads. */
export function entryField(
  t: Translate,
  grammar: ModeloEditValueGrammarV1,
): FieldSpec {
  if (grammar.family === "boolean")
    return {
      kind: "choice",
      choices: [
        { value: "", label: "—" },
        { value: "1", label: t("desktop.ledger.form.yes") },
        { value: "0", label: t("desktop.ledger.form.no") },
      ],
    };
  if (grammar.choices)
    return {
      kind: "choice",
      choices: [
        { value: "", label: "—" },
        ...grammar.choices.map(({ code }) => ({ value: code, label: code })),
      ],
    };
  if (grammar.ratio_unit === "percent")
    return { kind: "percent", unit: "points" };
  return fieldOfType(grammar.data_type) ?? { kind: "text" };
}
