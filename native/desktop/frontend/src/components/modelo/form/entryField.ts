import type { FieldSpec } from "../../../shared/fieldKind";
import type {
  ModeloEditValueGrammarV1,
  ModeloEditWritableScalarSurfaceEntryV1,
} from "../../../shell/modeloContract/modeloEditWork";
import type { PublicModeloFormField } from "../../../shell/modeloContract/modeloWorkForm";
import type { Translate } from "../../../shell/strings";

// Which editor an address takes, from the grammar the application served for
// it. The editors only hold what is typed: the application reads it.

/** A casilla's data type, as the registry declares it. */
type CasillaDataType = ModeloEditWritableScalarSurfaceEntryV1["data_type"];

const MONO: FieldSpec = { kind: "text", mono: true };

/** Keyed by the generated type, so a type the registry gains does not compile
 * until it is placed here. A yes or no has no box of its own: `readsYesNo`
 * places it from the grammar. */
const CASILLA_FIELDS: Record<CasillaDataType, FieldSpec | null> = {
  decimal: { kind: "decimal" },
  money: { kind: "money" },
  integer: { kind: "integer" },
  ratio: { kind: "decimal" },
  year: { kind: "year" },
  boolean: null,
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

/** Whether the application reads the entry as a number. A corrected box always
 * is, whatever the box prints, because a filed declaration holds figures. */
const readsFigure = (grammar: ModeloEditValueGrammarV1): boolean =>
  grammar.family === "decimal" || grammar.family === "integer";

/** Whether the entry is a yes or a no: read as one, or as the figure 1 or 0 a
 * corrected box holds. */
const readsYesNo = (grammar: ModeloEditValueGrammarV1): boolean =>
  grammar.family === "boolean" ||
  (grammar.data_type === "boolean" && readsFigure(grammar));

/** The editors whose text the application reads as a number. */
const FIGURE_KINDS: ReadonlySet<FieldSpec["kind"]> = new Set([
  "decimal",
  "integer",
  "money",
  "year",
]);

/** Whether a value can be typed against `grammar`: a channel carries it and
 * its data type is one an editor is known for. */
export const takesEntry = (grammar: ModeloEditValueGrammarV1): boolean =>
  grammar.channel !== "unavailable" &&
  (readsYesNo(grammar) || fieldOfType(grammar.data_type) !== null);

/** Why a box takes no value here, in the application's words; null for a box
 * that says so otherwise, as a calculated box or a value from a source does. */
export const readOnlyReason = (field: PublicModeloFormField): string | null =>
  field.editability === "not_writable" ? field.editability_words : null;

/** The editor for an address. A figure the registry declares no percentage
 * for keeps a plain figure: what is typed is read as written, never moved a
 * hundredfold. A yes or no goes as the `1` or `0` every language reads. A box
 * read as a number never takes an editor whose text is not one, such as a
 * date's. */
export function entryField(
  t: Translate,
  grammar: ModeloEditValueGrammarV1,
): FieldSpec {
  if (readsYesNo(grammar))
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
      // A box's design may declare the blank as a choice; the first row is it.
      choices: [
        { value: "", label: "—" },
        ...grammar.choices
          .filter(({ code }) => code !== "")
          .map(({ code, word }) => ({
            value: code,
            label: word ? `${code} · ${t(word)}` : code,
          })),
      ],
    };
  if (grammar.ratio_unit === "percent")
    return { kind: "percent", unit: "points" };
  const field = fieldOfType(grammar.data_type) ?? { kind: "text" };
  return readsFigure(grammar) && !FIGURE_KINDS.has(field.kind)
    ? { kind: "decimal" }
    : field;
}
