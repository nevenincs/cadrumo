import { TypedField } from "@/components/editors/TypedField";
import { formatDay } from "../../../shared/dateFormats";
import {
  formatAmount,
  formatDecimal,
  formatPercent,
} from "../../../shared/numbers";
import { facts, labelled } from "../../../shell/compose";
import type { GrammarRefusal } from "../../../shell/ledgerGrammar";
import type {
  AcquisitionCandidate,
  TableGroup,
  FormOptions,
} from "../../../shell/ledgerSetup";
import { useStrings, type Translate } from "../../../shell/strings";
import { EditorField } from "../setup/EditorField";
import { ChoiceField, FormGrid } from "../setup/SetupParts";
import { grammarText } from "../setup/setupWords";
import { specOf, type FormDraft, type FormField } from "./assetFormValues";
import { ASSET_KEYS, tokenWord } from "./assetsWords";

const NO_NOTES: Readonly<Record<string, string | null>> = {};
const NO_KEYS: ReadonlySet<string> = new Set();
/** What the registry allows a table class, as one line: the corridor of its
 * coefficient and its maximum period. */
const corridorText = (t: Translate, locale: string, group: TableGroup) => {
  const text = ASSET_KEYS.plan.limits;
  return facts(t, [
    labelled(
      t,
      t(text.maximum_coefficient),
      formatPercent(locale, group.maximum_coefficient.decimal, {
        unit: "fraction",
      }),
    ),
    labelled(
      t,
      t(text.minimum_coefficient),
      formatPercent(locale, group.minimum_coefficient.decimal, {
        unit: "fraction",
      }),
    ),
    labelled(
      t,
      t(text.maximum_period),
      t(text.period_years, {
        years: formatDecimal(locale, group.maximum_period_years.decimal),
      }),
    ),
  ]);
};

/** A choice's word: the generated word of its family, the catalogue key it
 * names, the text served with it, else the generic word. */
function choiceWord(
  t: Translate,
  option: FormField["choices"][number],
): string {
  if (option.family !== null) return tokenWord(t, option.family, option.token);
  if (option.word !== undefined) {
    const said = t(option.word);
    return said === option.word ? t(ASSET_KEYS.unrecognised) : said;
  }
  return option.label ?? t(ASSET_KEYS.unrecognised);
}

/**
 * The fields of an act, each drawn by its control. The form decides nothing
 * about them: their choices, bounds and starting values are the backend's. A
 * required field still to fill in is marked until something is typed; a
 * field the record cannot do without says so when it is emptied.
 */
export function FieldsGrid({
  fields,
  options,
  draft,
  onField,
  problems,
  missing,
  cleared = NO_KEYS,
  candidates,
  purchaseKnown,
  notes = NO_NOTES,
  locale,
}: {
  fields: readonly FormField[];
  options: FormOptions | null;
  draft: FormDraft;
  onField(field: FormField, value: string): void;
  problems: Record<string, GrammarRefusal>;
  /** The fields to mark as still to fill in. */
  missing: ReadonlySet<string>;
  /** The fields emptied that the record cannot do without. */
  cleared?: ReadonlySet<string>;
  candidates: readonly AcquisitionCandidate[];
  /** Fields the picked purchase does not know. */
  purchaseKnown: ReadonlySet<string>;
  /** What the backend says of a field's value, by field key. */
  notes?: Readonly<Record<string, string | null>>;
  locale: string;
}) {
  const t = useStrings();
  const unstated = (field: FormField) => (draft[field.key] ?? "") === "";
  return (
    <FormGrid>
      {fields.map((field) => {
        const raw = draft[field.key] ?? "";
        const problem = problems[field.key];
        const fillIn = missing.has(field.key) && unstated(field);
        const emptied = cleared.has(field.key);
        const hint =
          [
            field.hint_key ? t(field.hint_key) : null,
            field.key === "amortization.authority_class_key"
              ? (() => {
                  const group = options?.table_groups.find(
                    (found) => found.class_key === raw,
                  );
                  return group ? corridorText(t, locale, group) : null;
                })()
              : null,
            notes[field.key] ?? null,
            purchaseKnown.has(field.key) && unstated(field)
              ? t("desktop.ledger.assets.field.not_known")
              : null,
            field.control === "candidate" && candidates.length === 0
              ? t("desktop.ledger.assets.field.acquisition_none", {
                  movements: t("desktop.ledger.section.movements"),
                  documents: t("desktop.ledger.section.documents"),
                })
              : null,
          ]
            .filter(Boolean)
            .join(" ") || undefined;
        const error = problem
          ? grammarText(t, problem)
          : emptied
            ? t("desktop.ledger.assets.write.cannot_clear")
            : fillIn
              ? t(ASSET_KEYS.write.fill_in)
              : null;
        const label = t(field.label_key);
        const choose = (value: string) => onField(field, value);
        const spec = specOf(field);
        return (
          <div key={field.key} data-field={field.key} className="contents">
            {spec === null ? (
              <ChoiceField
                label={label}
                value={raw}
                onValue={choose}
                placeholder={t("desktop.ledger.form.choose")}
                hint={hint}
                required={field.required}
                error={error}
                options={
                  field.control === "candidate"
                    ? candidates.map((candidate) => ({
                        value: candidate.transaction_id,
                        label: t(
                          "desktop.ledger.assets.field.acquisition_option",
                          {
                            description: candidate.description,
                            date: formatDay(locale, candidate.booked_date),
                            amount: formatAmount(
                              locale,
                              candidate.amount.decimal,
                              { currency: candidate.currency },
                            ),
                          },
                        ),
                      }))
                    : field.control === "flag"
                      ? [
                          { value: "yes", label: t("desktop.ledger.form.yes") },
                          { value: "no", label: t("desktop.ledger.form.no") },
                        ]
                      : field.choices.map((option) => ({
                          value: option.token,
                          label: choiceWord(t, option),
                        }))
                }
              />
            ) : (
              <EditorField label={label} hint={hint} error={error}>
                {(control) => (
                  <TypedField
                    {...control}
                    field={spec}
                    name={field.key}
                    required={field.required}
                    value={raw}
                    onChange={choose}
                    {...field.offers}
                  />
                )}
              </EditorField>
            )}
          </div>
        );
      })}
    </FormGrid>
  );
}
