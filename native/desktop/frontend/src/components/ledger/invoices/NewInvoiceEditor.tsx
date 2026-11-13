import { CountryEditor } from "@/components/editors/CountryEditor";
import { CurrencyEditor } from "@/components/editors/CurrencyEditor";
import { DateEditor } from "@/components/editors/DateEditor";
import { MoneyEditor } from "@/components/editors/MoneyEditor";
import { TaxIdEditor } from "@/components/editors/TaxIdEditor";
import { TextEditor } from "@/components/editors/TextEditor";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { NativeSelect } from "@/components/ui/native-select";
import {
  SegmentedControl,
  SegmentedControlItem,
} from "@/components/ui/segmented-control";
import type { Suggestion } from "@/components/ui/suggestions";
import { localDay } from "../../../shared/dates";
import type {
  CatalogueInvoiceSnapshot,
  InvoiceKind,
} from "../../../shell/ledgerInvoiceContract";
import { useStrings } from "../../../shell/strings";
import { wordOrToken } from "../../../shell/tokenWords";
import { ServedOptions } from "../suggestions/ServedOptions";
import {
  useServedCodes,
  useVocabulary,
} from "../suggestions/SuggestionsProvider";
import {
  emptyFills,
  invoiceCountryOptions,
  invoiceCurrencyOptions,
  invoiceNumberOptions,
  lineDescriptionOptions,
  partyNameOptions,
  partyTaxIdOptions,
  referenciaCatastralOptions,
  seriesOptions,
} from "../suggestions/ledgerSuggestions";
import {
  IvaCategoryField,
  OperationTypeField,
  NotesField,
} from "./InvoiceClassificationFields";
import { EditorSection, FormField, wired } from "./InvoiceFields";
import { DraftLines } from "./InvoiceLines";
import { TotalsList, Retention } from "./InvoiceTotals";
import { nextLineKey } from "./invoiceEditorDraft";
import {
  CREATION_INVARIANTS,
  checkDraft,
  emptyLine,
  suggestNumber,
  type InvoiceDraft,
} from "./invoiceModel";
import type { PreviewView } from "./invoicePreview";
import { classLabel, findingText, kindChoice } from "./invoiceWords";

// ---- A new invoice -----------------------------------------------------------------

export function NewInvoice({
  draft,
  check,
  preview,
  invoices,
  locale,
  shown,
  touch,
  tried,
  touched,
  edit,
  duplicate,
  onOpenInvoice,
  say,
}: {
  draft: InvoiceDraft;
  check: ReturnType<typeof checkDraft>;
  preview: PreviewView;
  invoices: readonly CatalogueInvoiceSnapshot[];
  locale: string;
  shown(field: string): string | null;
  touch(field: string): void;
  tried: boolean;
  touched: ReadonlySet<string>;
  edit<K extends keyof InvoiceDraft>(key: K, value: InvoiceDraft[K]): void;
  duplicate: string | null;
  onOpenInvoice(invoiceId: string): void;
  say(text: string): void;
}) {
  const t = useStrings();
  const vocabulary = useVocabulary();
  const servedCountries = useServedCodes("country");
  const servedCurrencies = useServedCodes("currency");
  const bind = (key: keyof InvoiceDraft, field: string) => ({
    value: draft[key] as string,
    onChange: (value: string) => edit(key, value as never),
    onBlur: () => touch(field),
  });
  const issued = draft.kind === "issued";
  const partyScope = { kind: draft.kind };
  // A pick fills only what is still empty, and the person sees it before
  // anything is saved.
  const fillParty = (picked: Suggestion) => {
    const filled = emptyFills<"counterpartyName" | "taxId" | "country">(
      picked.fills,
      {
        counterpartyName: draft.counterpartyName,
        taxId: draft.taxId,
        country: draft.country,
      },
      { name: "counterpartyName", tax_id: "taxId", country: "country" },
    );
    for (const [key, value] of filled) edit(key, value);
    if (filled.length > 0) say(t("desktop.ledger.suggestions.filled"));
  };
  const year = /^\d{4}-\d{2}-\d{2}$/.test(draft.issuedAt.trim())
    ? Number(draft.issuedAt.trim().slice(0, 4))
    : Number(localDay().slice(0, 4));
  const suggestion = suggestNumber(invoices, {
    kind: draft.kind,
    invoiceClass: draft.invoiceClass,
    correctiveClass: vocabulary.correctiveClass,
    series: draft.series,
    year,
  });
  const rectificativa = draft.invoiceClass === vocabulary.correctiveClass;
  const numberHint =
    suggestion && draft.number.trim() !== suggestion.number ? (
      <span className="flex flex-wrap items-center gap-2">
        {t("desktop.ledger.invoices.next_number", {
          series: suggestion.series,
          number: suggestion.number,
        })}
        <Button
          variant="link"
          size="xs"
          aria-label={t("desktop.ledger.invoices.use_number", {
            number: suggestion.number,
          })}
          onClick={() => {
            edit("number", suggestion.number);
            if (!draft.series.trim()) edit("series", suggestion.series);
          }}
        >
          {t("desktop.ledger.invoices.use")}
        </Button>
      </span>
    ) : issued && rectificativa && !draft.series.trim() ? (
      t("desktop.ledger.invoices.next_number_series")
    ) : undefined;
  const numberError =
    duplicate !== null
      ? t("desktop.ledger.invoices.duplicate")
      : shown("invoice_number");
  const lineShown = (key: string, field: string) => {
    const place = `line:${key}:${field}`;
    const problem = check.problems[place];
    return (
      tried ||
      problem?.kind === "finding" ||
      (touched.has(place) && problem?.kind === "grammar")
    );
  };
  const served = preview.shown;
  const warned = (place: string) => {
    const finding = check.findings.warnings[place];
    return finding && served
      ? findingText(t, finding, served.rate_slots)
      : undefined;
  };

  return (
    <>
      <div
        role="group"
        aria-labelledby="ledger-invoice-kind"
        className="flex flex-col gap-1.5"
      >
        <span
          id="ledger-invoice-kind"
          className="text-sm font-medium text-muted-foreground"
        >
          {t("desktop.ledger.invoices.this_is")}
        </span>
        <SegmentedControl
          aria-labelledby="ledger-invoice-kind"
          aria-required
          aria-invalid={shown("kind") ? true : undefined}
          aria-describedby={
            shown("kind") ? "ledger-invoice-kind-error" : undefined
          }
          value={draft.kind ?? ""}
          onValueChange={(value) => edit("kind", value as InvoiceKind)}
          className="ledger-invoice-kind max-w-md"
        >
          {(["issued", "received"] as const).map((kind) => (
            <SegmentedControlItem key={kind} value={kind}>
              {kindChoice(t, kind)}
            </SegmentedControlItem>
          ))}
        </SegmentedControl>
        {shown("kind") && (
          <p
            id="ledger-invoice-kind-error"
            role="alert"
            className="flex items-start gap-1.5 text-sm text-destructive"
          >
            <Icon name="alert" size="xs" className="mt-0.5" />
            {shown("kind")}
          </p>
        )}
      </div>

      <Invariants held={check.invariants} />

      <EditorSection title={t("desktop.ledger.invoices.party")}>
        <div className="grid grid-cols-2 gap-3">
          <FormField
            label={t("desktop.ledger.invoices.field.counterparty_name")}
            required
            error={shown("counterparty_name")}
            className="col-span-2"
          >
            {(control) => (
              <TextEditor
                {...wired(control)}
                {...bind("counterpartyName", "counterparty_name")}
                suggestions={partyNameOptions(invoices, partyScope)}
                onPick={fillParty}
              />
            )}
          </FormField>
          <FormField
            label={t("desktop.ledger.invoices.field.counterparty_tax_id")}
            hint={
              issued && draft.invoiceClass === vocabulary.simplifiedClass
                ? t("desktop.ledger.invoices.hint.tax_id_optional")
                : undefined
            }
            error={shown("counterparty_tax_id")}
          >
            {(control) => (
              <TaxIdEditor
                {...wired(control)}
                {...bind("taxId", "counterparty_tax_id")}
                suggestions={partyTaxIdOptions(invoices, partyScope)}
                onPick={fillParty}
              />
            )}
          </FormField>
          <FormField
            label={t("desktop.ledger.invoices.field.counterparty_country")}
            required
            error={shown("counterparty_country")}
          >
            {(control) => (
              <CountryEditor
                {...wired(control)}
                {...bind("country", "counterparty_country")}
                suggestions={invoiceCountryOptions(
                  invoices,
                  locale,
                  servedCountries,
                )}
              />
            )}
          </FormField>
        </div>
      </EditorSection>

      <EditorSection title={t("desktop.ledger.invoices.document")}>
        <div className="grid grid-cols-2 gap-3">
          <FormField label={t("desktop.ledger.invoices.field.invoice_class")}>
            {(control) => (
              <NativeSelect
                {...control}
                value={draft.invoiceClass}
                onChange={(event) =>
                  edit(
                    "invoiceClass",
                    event.target.value as InvoiceDraft["invoiceClass"],
                  )
                }
              >
                <ServedOptions
                  values={vocabulary.invoiceClasses}
                  stored={draft.invoiceClass}
                  label={(token) => classLabel(t, token)}
                />
              </NativeSelect>
            )}
          </FormField>
          <FormField
            label={t("desktop.ledger.invoices.field.series")}
            required={rectificativa}
            error={shown("series")}
          >
            {(control) => (
              <TextEditor
                {...wired(control)}
                {...bind("series", "series")}
                suggestions={seriesOptions(invoices, {
                  kind: draft.kind,
                  invoiceClass: draft.invoiceClass,
                })}
                opensEmpty
              />
            )}
          </FormField>
          <FormField
            label={t("desktop.ledger.invoices.field.invoice_number")}
            required
            hint={numberHint}
            error={numberError}
          >
            {(control) => (
              <TextEditor
                {...wired(control)}
                {...bind("number", "invoice_number")}
                suggestions={[
                  ...(suggestion
                    ? [
                        {
                          value: suggestion.number,
                          label: suggestion.number,
                          note: suggestion.series,
                          fills: { series: suggestion.series },
                        },
                      ]
                    : []),
                  ...(issued
                    ? []
                    : invoiceNumberOptions(
                        invoices,
                        {
                          kind: draft.kind,
                          party: draft.counterpartyName,
                        },
                        locale,
                      ).map(({ value, label, note }) => ({
                        value,
                        label,
                        note,
                      }))),
                ]}
                onPick={(picked) => {
                  const series = picked.fills?.series;
                  if (series && !draft.series.trim()) edit("series", series);
                }}
              />
            )}
          </FormField>
          <FormField
            label={t("desktop.ledger.invoices.field.issued_at")}
            required
            error={shown("issued_at")}
          >
            {(control) => (
              <DateEditor
                {...wired(control)}
                {...bind("issuedAt", "issued_at")}
              />
            )}
          </FormField>
          <FormField
            label={t("desktop.ledger.invoices.field.operation_date")}
            hint={t("desktop.ledger.invoices.hint.operation_date")}
            error={shown("operation_date")}
          >
            {(control) => (
              <DateEditor
                {...wired(control)}
                {...bind("operationDate", "operation_date")}
              />
            )}
          </FormField>
          <FormField
            label={t("desktop.ledger.invoices.field.currency")}
            required
            error={shown("currency")}
          >
            {(control) => (
              <CurrencyEditor
                {...wired(control)}
                {...bind("currency", "currency")}
                suggestions={invoiceCurrencyOptions(
                  invoices,
                  locale,
                  servedCurrencies,
                )}
              />
            )}
          </FormField>
          {rectificativa && (
            <FormField
              label={t(
                "desktop.ledger.invoices.field.rectifies_invoice_number",
              )}
              required
              error={shown("rectifies_invoice_number")}
            >
              {(control) => (
                <TextEditor
                  {...wired(control)}
                  {...bind("rectifies", "rectifies_invoice_number")}
                  suggestions={invoiceNumberOptions(
                    invoices,
                    { kind: draft.kind, party: draft.counterpartyName },
                    locale,
                  )}
                  onPick={fillParty}
                />
              )}
            </FormField>
          )}
          <IvaCategoryField
            value={draft.ivaCategory}
            onChange={(value) => edit("ivaCategory", value)}
            unset={t("desktop.ledger.invoices.from_lines")}
          />
          <OperationTypeField
            value={draft.operationType}
            onChange={(value) => edit("operationType", value)}
          />
        </div>
        {duplicate && (
          <div>
            <Button
              variant="link"
              size="xs"
              onClick={() => onOpenInvoice(duplicate)}
            >
              {t("desktop.ledger.invoices.open_duplicate")}
            </Button>
          </div>
        )}
      </EditorSection>

      <EditorSection title={t("desktop.ledger.invoices.lines")}>
        {shown("lines") && (
          <p
            role="alert"
            className="flex items-start gap-1.5 text-sm text-destructive"
          >
            <Icon name="alert" size="xs" className="mt-0.5" />
            {shown("lines")}
          </p>
        )}
        <DraftLines
          descriptions={lineDescriptionOptions(
            invoices,
            draft.counterpartyName,
          )}
          lines={draft.lines}
          figures={served?.lines ?? []}
          slots={served?.rate_slots ?? []}
          kind={draft.kind}
          locale={locale}
          problems={check.problems}
          shown={lineShown}
          onChange={(key, field, value) => {
            edit(
              "lines",
              draft.lines.map((line) =>
                line.key === key ? { ...line, [field]: value } : line,
              ),
            );
          }}
          onAdd={() =>
            edit("lines", [...draft.lines, emptyLine(nextLineKey())])
          }
          onRemove={(key) =>
            edit(
              "lines",
              draft.lines.filter((line) => line.key !== key),
            )
          }
        />
        <p className="text-xs text-muted-foreground">
          {t("desktop.ledger.invoices.lines_note")}
        </p>
      </EditorSection>

      <EditorSection title={t("desktop.ledger.invoices.totals")}>
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-3 rounded-lg bg-accent p-3">
            <TotalsList
              locale={locale}
              currency={draft.currency.trim().toUpperCase()}
              base={served?.totals.base?.decimal ?? null}
              iva={served?.totals.iva?.decimal ?? null}
              total={served?.totals.total?.decimal ?? null}
              failed={preview.failed}
              updating={preview.updating && served !== null}
              recargo={
                <FormField
                  label={t("desktop.ledger.invoices.field.recargo")}
                  hint={warned("recargo")}
                  error={shown("recargo")}
                >
                  {(control) => (
                    <MoneyEditor
                      {...wired(control)}
                      {...bind("recargo", "recargo")}
                      controlSize="sm"
                    />
                  )}
                </FormField>
              }
            />
            <FormField
              label={t("desktop.ledger.invoices.field.printed_total")}
              hint={
                warned("printed") ??
                t("desktop.ledger.invoices.hint.printed_total")
              }
              error={shown("printed")}
            >
              {(control) => (
                <MoneyEditor
                  {...wired(control)}
                  {...bind("printedTotal", "printed")}
                  controlSize="sm"
                />
              )}
            </FormField>
          </div>
          <Retention
            locale={locale}
            rate={draft.retentionRate}
            amount={draft.retentionAmount}
            answered={preview.current?.retention ?? null}
            net={served?.totals.net_of_retention?.decimal ?? null}
            withheld={served?.retention.amount?.decimal ?? null}
            rateError={shown("retention_rate")}
            amountError={shown("retention_amount")}
            onRate={(value) => edit("retentionRate", value)}
            onAmount={(value) => edit("retentionAmount", value)}
            onBlur={touch}
          />
        </div>
      </EditorSection>

      {issued && (
        <EditorSection title={t("desktop.ledger.invoices.lease")}>
          <label className="flex items-center gap-2 text-base">
            <Checkbox
              checked={draft.lease}
              onChange={(event) => edit("lease", event.target.checked)}
            />
            {t("desktop.ledger.invoices.field.lease")}
          </label>
          {draft.lease && (
            <div className="grid grid-cols-2 gap-3">
              <FormField label={t("desktop.ledger.invoices.field.situacion")}>
                {(control) => (
                  <NativeSelect
                    {...control}
                    value={draft.situacion}
                    onChange={(event) => edit("situacion", event.target.value)}
                  >
                    <option value="">
                      {t("desktop.ledger.invoices.not_stated")}
                    </option>
                    <ServedOptions
                      values={vocabulary.premisesSituations}
                      stored={draft.situacion}
                      label={(code) =>
                        wordOrToken(
                          t,
                          "desktop.ledger.invoices.situacion.s",
                          code,
                        )
                      }
                    />
                  </NativeSelect>
                )}
              </FormField>
              <FormField
                label={t("desktop.ledger.invoices.field.referencia")}
                error={shown("referencia")}
              >
                {(control) => (
                  <TextEditor
                    {...wired(control)}
                    {...bind("referencia", "referencia")}
                    suggestions={referenciaCatastralOptions(invoices)}
                    mono
                  />
                )}
              </FormField>
            </div>
          )}
        </EditorSection>
      )}

      <NotesField
        value={draft.notes}
        onChange={(value) => edit("notes", value)}
      />
    </>
  );
}

/** The four requirements of every new invoice, each ticked once met. */
function Invariants({ held }: { held: Record<string, boolean> }) {
  const t = useStrings();
  return (
    <ul
      className="ledger-invoice-invariants flex flex-wrap gap-x-4 gap-y-1 text-sm"
      aria-label={t("desktop.ledger.invoices.needs")}
    >
      {CREATION_INVARIANTS.map((invariant) => {
        const met = held[invariant] === true;
        return (
          <li
            key={invariant}
            data-invariant={invariant}
            data-met={met || undefined}
            className={cn(
              "flex items-center gap-1.5",
              met ? "text-foreground" : "text-muted-foreground",
            )}
          >
            <Icon
              name={met ? "tick" : "pending"}
              size="xs"
              className={met ? "text-success" : undefined}
            />
            {t(`desktop.ledger.invoices.invariant.${invariant}`)}
            <span className="sr-only">
              {t(
                met
                  ? "desktop.ledger.invoices.met"
                  : "desktop.ledger.invoices.not_met",
              )}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
