import { useId } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { NativeSelect } from "@/components/ui/native-select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Spinner } from "@/components/ui/spinner";
import { facts } from "../../../shell/compose";
import type { LedgerImportResult, PickedFile } from "../../../shell/ledger";
import type { InvoiceKind } from "../../../shell/ledgerInvoiceOperations";
import type { Translate } from "../../../shell/strings";
import { formatSize } from "../../../shared/numbers";
import { SetupOffer } from "../../setup/SetupOffer";
import { FileRow } from "./ImportFileRow";
import {
  NO_ACCOUNT,
  accountFact,
  type AccountKey,
  type BankFilePreview,
  type ImportKind,
  type OwnAccount,
} from "./importModel";
import { diagnosticText, importRefusal } from "./transferWords";

export type ReadPreview = Extract<BankFilePreview, { kind: "read" }>;

function Counts({ items }: { items: [string, number][] }) {
  return (
    <dl className="ledger-import-counts flex flex-wrap gap-x-4 gap-y-1 text-sm">
      {items.map(([label, value]) => (
        <div key={label} className="flex gap-1.5">
          <dt className="text-muted-foreground">{label}</dt>
          <dd className="font-medium tabular-nums">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** A preview's likely duplicates as a glyph and a count, opening what
 * happens to them. The preview names no row of its own, so the comparison
 * with the movement already stored waits for the import. */
function DuplicatesChip({
  t,
  count,
  shown,
}: {
  t: Translate;
  count: number;
  shown: string;
}) {
  const name = t("desktop.ledger.import.duplicates_chip", { count: shown });
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="pill"
          size="xs"
          className="ledger-import-duplicates-chip w-fit tabular-nums"
          aria-label={name}
          data-count={count}
        >
          {/* The grid and the strip mark a likely duplicate with the copy
              glyph; the warning glyph is readiness's. */}
          <Icon name="copy" size="xs" className="text-warning" />
          <span aria-hidden="true">{shown}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        aria-label={name}
        className="ledger-import-duplicates-note grid w-dialog gap-1"
      >
        <p className="font-medium">{name}</p>
        <p className="text-sm text-muted-foreground">
          {t("desktop.ledger.import.duplicates_note")}
        </p>
      </PopoverContent>
    </Popover>
  );
}

/** The bank files' preview: each file's counts and the account it imports
 * with, which the person chooses where the file does not say it. */
export function ImportBankPreview({
  t,
  count,
  previews,
  progressText,
  accounts,
  accountFacts,
  choices,
  reading,
  onChoose,
  shown,
  nothingNew,
}: {
  t: Translate;
  count(value: number): string;
  previews: BankFilePreview[];
  progressText: string | null;
  accounts: OwnAccount[];
  accountFacts: Map<string, ReturnType<typeof accountFact>>;
  choices: Record<string, AccountKey>;
  reading: Set<string>;
  onChoose(preview: ReadPreview, account: AccountKey): void;
  shown(preview: ReadPreview): LedgerImportResult;
  nothingNew: boolean;
}) {
  const ids = useId();
  if (previews.length === 0)
    return (
      <p role="status" className="flex items-center gap-2 text-sm">
        <Spinner />
        {progressText ?? t("desktop.ledger.import.reading_start")}
      </p>
    );
  const read = previews.filter(
    (preview): preview is ReadPreview => preview.kind === "read",
  );
  const total = (pick: (result: LedgerImportResult) => number) =>
    read.reduce((sum, preview) => sum + pick(shown(preview)), 0);
  const accountName = (id: string) => {
    const account = accounts.find((held) => held.id === id);
    return account ? facts(t, [account.label, account.masked]) : id;
  };
  return (
    <>
      {nothingNew && (
        <Alert tone="success" icon={<Icon name="check" />}>
          <AlertTitle>{t("desktop.ledger.import.nothing_new")}</AlertTitle>
          <AlertDescription>
            {t("desktop.ledger.import.nothing_new_note")}
          </AlertDescription>
        </Alert>
      )}
      <Counts
        items={[
          [t("desktop.ledger.import.count.rows"), total((r) => r.rows)],
          [t("desktop.ledger.import.count.new"), total((r) => r.imported)],
          [t("desktop.ledger.import.count.skipped"), total((r) => r.skipped)],
          [
            t("desktop.ledger.import.count.duplicates"),
            total((r) => r.likely_duplicates),
          ],
          [
            t("desktop.ledger.import.count.refused"),
            previews.filter((preview) => preview.kind !== "read").length,
          ],
        ].map(([label, value]) => [label as string, value as number])}
      />
      <ul
        aria-label={t("desktop.ledger.import.files")}
        className="ledger-import-preview grid gap-1"
      >
        {previews.map((preview) => {
          if (preview.kind === "refused")
            return (
              <FileRow
                key={preview.file.token}
                name={preview.file.name}
                refused
              >
                <span className="text-sm">
                  {importRefusal(t, preview.reason, preview.setup ?? null)}
                </span>
                <SetupOffer action={preview.setup ?? null} className="mt-1" />
              </FileRow>
            );
          if (preview.kind === "failed")
            return (
              <FileRow
                key={preview.file.token}
                name={preview.file.name}
                refused
              >
                <span className="text-sm">
                  {t("desktop.ledger.import.preview_failed")}
                </span>
              </FileRow>
            );
          const result = shown(preview);
          const fact = accountFacts.get(preview.file.token)!;
          const select = `${ids}-${preview.file.token}`;
          return (
            <FileRow key={preview.file.token} name={preview.file.name}>
              <span className="text-sm text-muted-foreground tabular-nums">
                {reading.has(preview.file.token)
                  ? t("desktop.ledger.import.reading_start")
                  : t("desktop.ledger.import.file_counts", {
                      rows: count(result.rows),
                      fresh: count(result.imported),
                      skipped: count(result.skipped),
                    })}
              </span>
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <label htmlFor={select} className="text-muted-foreground">
                  {t("desktop.ledger.import.account")}
                </label>
                {fact.kind === "choose" || fact.kind === "detected" ? (
                  <NativeSelect
                    id={select}
                    controlSize="sm"
                    required
                    aria-describedby={
                      fact.kind === "detected" ? `${select}-hint` : undefined
                    }
                    aria-invalid={
                      (fact.kind === "choose" &&
                        choices[preview.file.token] === undefined &&
                        result.imported > 0) ||
                      undefined
                    }
                    // A detected account is the choice already made, and
                    // stays changeable.
                    value={
                      choices[preview.file.token] ??
                      (fact.kind === "detected" ? fact.account : "")
                    }
                    onChange={(event) => onChoose(preview, event.target.value)}
                  >
                    <option value="" disabled>
                      {t("desktop.ledger.import.account_choose")}
                    </option>
                    {accounts
                      .filter(
                        (account) => !preview.mismatched.includes(account.id),
                      )
                      .map((account) => (
                        <option key={account.id} value={account.id}>
                          {accountName(account.id)}
                        </option>
                      ))}
                    <option value={NO_ACCOUNT}>
                      {t("desktop.ledger.import.no_account")}
                    </option>
                  </NativeSelect>
                ) : (
                  <span id={select} className="font-medium">
                    {t("desktop.ledger.import.no_account")}
                    <span className="ml-2 text-xs font-normal text-muted-foreground">
                      {t(`desktop.ledger.import.account_${fact.kind}`)}
                    </span>
                  </span>
                )}
                {fact.kind === "detected" && (
                  <span
                    id={`${select}-hint`}
                    className="text-xs text-muted-foreground"
                  >
                    {t("desktop.ledger.import.account_detected")}
                  </span>
                )}
              </div>
              {result.likely_duplicates > 0 && (
                <DuplicatesChip
                  t={t}
                  count={result.likely_duplicates}
                  shown={count(result.likely_duplicates)}
                />
              )}
              {result.diagnostics.map((diagnostic, at) => (
                <span key={at} className="text-sm text-muted-foreground">
                  {diagnosticText(t, diagnostic.message)}
                </span>
              ))}
            </FileRow>
          );
        })}
      </ul>
      {progressText && (
        <p role="status" className="flex items-center gap-2 text-sm">
          <Spinner />
          {progressText}
        </p>
      )}
    </>
  );
}

/** An invoice book's or documents' preview, which reads nothing before the
 * import: the files and what they will be imported as. */
export function ImportPlainPreview({
  t,
  locale,
  kind,
  files,
  bookKind,
  country,
  direction,
}: {
  t: Translate;
  locale: string;
  kind: ImportKind;
  files: PickedFile[];
  bookKind: InvoiceKind | null;
  country: string;
  direction: InvoiceKind | null;
}) {
  return (
    <>
      <ul
        aria-label={t("desktop.ledger.import.files")}
        className="ledger-import-preview grid gap-1"
      >
        {files.map((file) => (
          <FileRow key={file.token} name={file.name}>
            {file.bytes !== null && (
              <span className="text-xs text-muted-foreground">
                {formatSize(locale, file.bytes)}
              </span>
            )}
          </FileRow>
        ))}
      </ul>
      {kind === "book" ? (
        <Alert tone="warning" icon={<Icon name="alert" />}>
          <AlertTitle>{t("desktop.ledger.import.book_no_preview")}</AlertTitle>
          <AlertDescription>
            {t("desktop.ledger.import.book_no_preview_note", {
              kind: t(`desktop.ledger.import.kind_${bookKind}`),
              country: country || t("desktop.ledger.import.country_none"),
            })}
          </AlertDescription>
        </Alert>
      ) : (
        <p className="text-sm text-muted-foreground">
          {t("desktop.ledger.import.documents_note", {
            kind: t(`desktop.ledger.import.kind_${direction}`),
          })}
        </p>
      )}
    </>
  );
}
