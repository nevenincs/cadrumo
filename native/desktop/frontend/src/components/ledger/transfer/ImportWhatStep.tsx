import { useId } from "react";
import { CountryEditor } from "@/components/editors/CountryEditor";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
} from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { NativeSelect } from "@/components/ui/native-select";
import {
  SegmentedControl,
  SegmentedControlItem,
} from "@/components/ui/segmented-control";
import { Switch } from "@/components/ui/switch";
import type {
  FilePick,
  LedgerProvider,
  PickedFile,
} from "../../../shell/ledger";
import type { InvoiceKind } from "../../../shell/ledgerInvoiceOperations";
import type { LedgerPeriod } from "../../../shell/ledgerGrammar";
import { periodsHoldingToday, usePeriods } from "../../../shell/ledgerPeriods";
import type { Translate } from "../../../shell/strings";
import { formatSize } from "../../../shared/numbers";
import { PeriodSelector } from "../PeriodSelector";
import { useFieldSuggestions } from "../suggestions/SuggestionsProvider";
import { FileRow } from "./ImportFileRow";
import { IMPORT_KINDS, LEDGER_PROVIDERS, type ImportKind } from "./importModel";
import { providerName } from "./transferWords";

/**
 * The import's first step: what is imported, the files, picked or dropped,
 * and the options of that kind of import.
 */
export function ImportWhatStep({
  t,
  locale,
  kind,
  kindName,
  onKind,
  files,
  leftOut,
  over,
  picking,
  pickFailed,
  onPick,
  onRemove,
  provider,
  onProvider,
  onlyPeriod,
  onOnlyPeriod,
  pagePeriod,
  years,
  fallbackYear,
  verify,
  onVerify,
  bookKind,
  onBookKind,
  country,
  countryValid,
  onCountry,
  direction,
  onDirection,
}: {
  t: Translate;
  locale: string;
  kind: ImportKind;
  kindName: string;
  onKind(kind: ImportKind): void;
  files: PickedFile[];
  leftOut: number;
  over: boolean;
  picking: boolean;
  pickFailed: boolean;
  onPick(how: FilePick): void;
  onRemove(file: PickedFile): void;
  provider: LedgerProvider;
  onProvider(provider: LedgerProvider): void;
  onlyPeriod: LedgerPeriod | null;
  onOnlyPeriod(period: LedgerPeriod | null): void;
  pagePeriod: LedgerPeriod | null;
  years: readonly number[] | null;
  fallbackYear: number;
  verify: boolean;
  onVerify(verify: boolean): void;
  bookKind: InvoiceKind | null;
  onBookKind(kind: InvoiceKind): void;
  country: string;
  countryValid: boolean;
  onCountry(country: string): void;
  direction: InvoiceKind | null;
  onDirection(direction: InvoiceKind): void;
}) {
  const ids = useId();
  // The quarter that holds today is served; the switch offers it once it is.
  usePeriods();
  const countries = useFieldSuggestions("country");
  const directionChoice = (
    value: InvoiceKind | null,
    onChange: (next: InvoiceKind) => void,
    label: string,
  ) => (
    <Field>
      <FieldLabel id={`${ids}-${label}`}>{t(label)}</FieldLabel>
      <SegmentedControl
        aria-labelledby={`${ids}-${label}`}
        value={value ?? ""}
        onValueChange={(next) => onChange(next as InvoiceKind)}
      >
        <SegmentedControlItem value="received">
          {t("desktop.ledger.import.kind_received")}
        </SegmentedControlItem>
        <SegmentedControlItem value="issued">
          {t("desktop.ledger.import.kind_issued")}
        </SegmentedControlItem>
      </SegmentedControl>
    </Field>
  );
  return (
    <>
      <Field>
        {/* The step's heading already says this on screen; the control
            keeps its name. */}
        <FieldLabel id={kindName} className="sr-only">
          {t("desktop.ledger.import.what")}
        </FieldLabel>
        <SegmentedControl
          aria-labelledby={kindName}
          value={kind}
          onValueChange={(next) => onKind(next as ImportKind)}
        >
          {IMPORT_KINDS.map((value) => (
            <SegmentedControlItem key={value} value={value} disabled={picking}>
              {t(`desktop.ledger.import.kind.${value}`)}
            </SegmentedControlItem>
          ))}
        </SegmentedControl>
      </Field>
      <div
        data-over={over || undefined}
        className={cn(
          "ledger-import-drop grid justify-items-center gap-2 rounded-lg border-2 p-4 text-center",
          over
            ? "border-solid border-foreground"
            : "border-dashed border-border-strong",
        )}
      >
        <Icon name="upload" size="lg" className="text-muted-foreground" />
        <p>{t(`desktop.ledger.import.drop.${kind}`)}</p>
        <div className="flex flex-wrap justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            pending={picking}
            onClick={() => onPick(kind === "book" ? "file" : "files")}
          >
            {t(
              kind === "book"
                ? "desktop.ledger.import.choose_file"
                : "desktop.ledger.import.choose_files",
            )}
          </Button>
          {kind !== "book" && (
            <Button
              variant="ghost"
              size="sm"
              disabled={picking}
              onClick={() => onPick("folder")}
            >
              {t("desktop.ledger.import.choose_folder")}
            </Button>
          )}
        </div>
        <p className="text-xs text-muted-foreground">
          {t(`desktop.ledger.import.accepts.${kind}`)}
        </p>
      </div>
      {pickFailed && (
        <p role="alert" className="text-sm">
          {t("desktop.ledger.import.pick_failed")}
        </p>
      )}
      {leftOut > 0 && (
        <p role="status" className="text-sm text-muted-foreground">
          {t("desktop.ledger.import.left_out", { count: leftOut })}
        </p>
      )}
      {files.length > 0 && (
        <ul
          aria-label={t("desktop.ledger.import.chosen")}
          className="ledger-import-files grid gap-1"
        >
          {files.map((file) => (
            <FileRow
              key={file.token}
              name={file.name}
              action={
                <IconButton
                  label={t("desktop.ledger.import.remove", { name: file.name })}
                  onClick={() => onRemove(file)}
                >
                  <Icon name="close" />
                </IconButton>
              }
            >
              {file.bytes !== null && (
                <span className="text-xs text-muted-foreground">
                  {formatSize(locale, file.bytes)}
                </span>
              )}
            </FileRow>
          ))}
        </ul>
      )}
      {kind === "bank" && (
        <div className="grid gap-3">
          <Field>
            <FieldLabel htmlFor={`${ids}-provider`}>
              {t("desktop.ledger.import.provider_label")}
            </FieldLabel>
            <NativeSelect
              id={`${ids}-provider`}
              value={provider}
              onChange={(event) =>
                onProvider(event.target.value as LedgerProvider)
              }
            >
              {LEDGER_PROVIDERS.map((value) => (
                <option key={value} value={value}>
                  {providerName(t, value)}
                </option>
              ))}
            </NativeSelect>
          </Field>
          <div className="grid gap-1.5">
            <label className="flex items-center gap-2 text-sm">
              <Switch
                checked={onlyPeriod !== null}
                onCheckedChange={(on) =>
                  onOnlyPeriod(
                    on
                      ? (pagePeriod ?? periodsHoldingToday()?.quarterly ?? null)
                      : null,
                  )
                }
              />
              {t("desktop.ledger.import.only_period")}
            </label>
            {onlyPeriod ? (
              <PeriodSelector
                value={onlyPeriod}
                onChange={(next) => next && onOnlyPeriod(next)}
                label={t("desktop.ledger.import.period")}
                years={years}
                locale={locale}
                fallbackYear={fallbackYear}
                allowAll={false}
                className="justify-self-start"
              />
            ) : (
              <p className="text-xs text-muted-foreground">
                {t("desktop.ledger.import.any_date")}
              </p>
            )}
          </div>
          <label className="flex items-center gap-2 text-sm">
            <Switch checked={verify} onCheckedChange={onVerify} />
            {t("desktop.ledger.import.verify")}
          </label>
          <p className="text-sm text-muted-foreground">
            {t("desktop.ledger.import.account_later")}
          </p>
        </div>
      )}
      {kind === "book" && (
        <div className="grid gap-3">
          {directionChoice(
            bookKind,
            onBookKind,
            "desktop.ledger.import.book_kind",
          )}
          <Field data-invalid={!countryValid || undefined}>
            <FieldLabel htmlFor={`${ids}-country`}>
              {t("desktop.ledger.import.country")}
            </FieldLabel>
            <CountryEditor
              id={`${ids}-country`}
              value={country}
              maxLength={2}
              invalid={!countryValid || undefined}
              describedBy={`${ids}-country-hint`}
              className="w-control-lg"
              onChange={onCountry}
              {...countries}
            />
            {countryValid ? (
              <FieldDescription id={`${ids}-country-hint`}>
                {t("desktop.ledger.import.country_purpose")}
              </FieldDescription>
            ) : (
              <FieldError id={`${ids}-country-hint`}>
                {t("desktop.ledger.import.country_invalid", { value: country })}
              </FieldError>
            )}
          </Field>
        </div>
      )}
      {kind === "documents" &&
        directionChoice(
          direction,
          onDirection,
          "desktop.ledger.import.documents_kind",
        )}
    </>
  );
}
