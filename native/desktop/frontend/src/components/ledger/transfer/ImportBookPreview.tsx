import { useId } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Icon } from "@/components/ui/icon";
import { NativeSelect } from "@/components/ui/native-select";
import { Spinner } from "@/components/ui/spinner";
import type { InvoiceKind } from "../../../shell/ledgerInvoiceContract";
import type { Translate } from "../../../shell/strings";
import { listOf } from "../../../shared/lists";
import { formatSize } from "../../../shared/numbers";
import { SetupOffer } from "../../setup/SetupOffer";
import { FileRow } from "./ImportFileRow";
import {
  UNUSED_ROLE,
  missingRoles,
  sourceOfColumn,
  type BookPreview,
  type BookReview,
  type BookRole,
} from "./importModel";
import { bookRefusalWords, failureWords } from "./transferWords";

/** A role in plain words; "not used" is the role of a column that feeds
 * nothing. */
export const roleWord = (t: Translate, role: BookRole) =>
  t(`desktop.ledger.import.role.${role}`);

/** An invoice book's preview: how many rows it holds, the role each of its
 * columns came to hold and who settled it, which the person can change, and
 * the roles the import needs that no column supplies yet. */
export function ImportBookPreview({
  t,
  locale,
  count,
  preview,
  review,
  onAssign,
  bookKind,
  country,
}: {
  t: Translate;
  locale: string;
  count(value: number): string;
  /** Null while the book is being read. */
  preview: BookPreview | null;
  review: BookReview;
  onAssign(column: number, role: BookRole): void;
  bookKind: InvoiceKind | null;
  country: string;
}) {
  const ids = useId();
  if (preview === null)
    return (
      <p role="status" className="flex items-center gap-2 text-sm">
        <Spinner />
        {t("desktop.ledger.import.reading_start")}
      </p>
    );
  if (preview.kind !== "read")
    return (
      <ul
        aria-label={t("desktop.ledger.import.files")}
        className="ledger-import-preview grid gap-1"
      >
        <FileRow name={preview.file.name} refused>
          <span className="text-sm">
            {preview.kind === "refused"
              ? bookRefusalWords(t, preview)
              : `${t("desktop.ledger.import.preview_failed")} ${failureWords(
                  t,
                  preview.code,
                  preview.reason,
                )}`}
          </span>
          {preview.kind === "refused" && (
            <SetupOffer action={preview.setup} className="mt-1" />
          )}
        </FileRow>
      </ul>
    );
  const missing = missingRoles(preview, review);
  const { file } = preview;
  return (
    <>
      <ul
        aria-label={t("desktop.ledger.import.files")}
        className="ledger-import-preview grid gap-1"
      >
        <FileRow name={file.name}>
          <span className="text-sm text-muted-foreground tabular-nums">
            {t("desktop.ledger.import.book_rows", {
              rows: count(preview.rows),
            })}
            {file.bytes !== null && ` · ${formatSize(locale, file.bytes)}`}
          </span>
        </FileRow>
      </ul>
      {preview.readerUnavailable && (
        <Alert
          tone="warning"
          icon={<Icon name="alert" />}
          className="ledger-import-book-reader"
        >
          <AlertTitle>
            {t("desktop.ledger.import.book_reader_unavailable")}
          </AlertTitle>
          <AlertDescription>
            {t("desktop.ledger.import.book_reader_note")}
            <SetupOffer action={preview.setup} className="mt-1" />
          </AlertDescription>
        </Alert>
      )}
      {missing.length > 0 && (
        <Alert
          tone="warning"
          icon={<Icon name="alert" />}
          className="ledger-import-book-missing"
        >
          <AlertTitle>{t("desktop.ledger.import.book_missing")}</AlertTitle>
          <AlertDescription>
            {t("desktop.ledger.import.book_missing_note", {
              roles: listOf(
                locale,
                missing.map((role) => roleWord(t, role.role)),
              ),
            })}
          </AlertDescription>
        </Alert>
      )}
      <table className="ledger-import-columns w-full text-sm">
        <caption className="text-left font-medium">
          {t("desktop.ledger.import.book_columns")}
        </caption>
        <thead>
          <tr className="text-left text-muted-foreground">
            <th scope="col" className="py-1 pr-3 font-normal">
              {t("desktop.ledger.import.book_column")}
            </th>
            <th scope="col" className="py-1 pr-3 font-normal">
              {t("desktop.ledger.import.book_role")}
            </th>
            <th scope="col" className="py-1 font-normal">
              {t("desktop.ledger.import.book_source")}
            </th>
          </tr>
        </thead>
        <tbody>
          {preview.columns.map((column) => {
            const id = `${ids}-${column.column_index}`;
            const role = review.roles[column.column_index] ?? UNUSED_ROLE;
            return (
              <tr
                key={column.column_index}
                className="border-t border-border align-middle"
              >
                <th
                  scope="row"
                  id={id}
                  className="py-1 pr-3 text-left font-medium [overflow-wrap:anywhere]"
                >
                  {column.header}
                </th>
                <td className="py-1 pr-3">
                  <NativeSelect
                    controlSize="sm"
                    aria-labelledby={id}
                    value={role}
                    onChange={(event) =>
                      onAssign(
                        column.column_index,
                        event.target.value as BookRole,
                      )
                    }
                  >
                    <option value={UNUSED_ROLE}>
                      {roleWord(t, UNUSED_ROLE)}
                    </option>
                    {preview.assignable.map((option) => (
                      <option key={option.role} value={option.role}>
                        {roleWord(t, option.role)}
                      </option>
                    ))}
                  </NativeSelect>
                </td>
                <td className="py-1 text-muted-foreground">
                  {t(
                    `desktop.ledger.import.role_source.${sourceOfColumn(column, review)}`,
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="text-sm text-muted-foreground">
        {t("desktop.ledger.import.book_preview_note", {
          kind: t(`desktop.ledger.import.kind_${bookKind}`),
          country: country || t("desktop.ledger.import.country_none"),
        })}
      </p>
    </>
  );
}
