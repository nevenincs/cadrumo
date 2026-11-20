import type { ReactNode } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import { formatInstantDay } from "../../shared/dateFormats";
import { formatAmount } from "../../shared/numbers";
import { useStrings } from "../../shell/strings";
import type {
  RetencionSoportadaAbsenceRowProjection,
  RetencionSoportadaAmountColumnProjection,
  RetencionSoportadaRowProjection,
} from "../../shell/ledgerWithholdingContract";
import type { SetupCall } from "../ledger/setup/setupModel";
import {
  rankDecimal,
  SetupTable,
  type Column,
} from "../ledger/setup/SetupParts";
import { servedAmount } from "../ledger/setup/withholdingFigures";

/** What stands for a read that has not answered. */
export function Reading({ label }: { label: string }) {
  return (
    <p
      role="status"
      data-withholding-reading=""
      className="flex items-center gap-2 text-sm text-muted-foreground"
    >
      <Spinner />
      {label}
    </p>
  );
}

/** The code a read that did not answer is told by: the runtime's own for a
 * failure, the operation's for a refusal. A read has no unknown outcome of
 * its own, so one that arrives as such is a failure with that name. */
export function readCode(call: Exclude<SetupCall<unknown>, { kind: "done" }>) {
  switch (call.kind) {
    case "failed":
      return call.code;
    case "refused":
      return call.reason ?? call.kind;
    default:
      return call.kind;
  }
}

/** A read that failed or was refused, said with its code. It is never drawn
 * as an empty list, and it is read again only when the person asks. */
export function Unavailable({
  call,
  onReadAgain,
}: {
  call: Exclude<SetupCall<unknown>, { kind: "done" }>;
  onReadAgain: () => void;
}) {
  const t = useStrings();
  const code = readCode(call);
  return (
    <Alert role="alert" tone="danger" icon={<Icon name="refused" />}>
      <span data-withholding-failed={code}>
        {t("desktop.withholding.failed", { code })}{" "}
        <Button variant="link" size="xs" onClick={onReadAgain}>
          {t("desktop.withholding.read_again")}
        </Button>
      </span>
    </Alert>
  );
}

/** One list of the page: its heading and, under it, the list or the
 * standing of the read that was to serve it. */
export function Block({
  name,
  heading,
  children,
}: {
  name: "records" | "absences";
  heading: string;
  children: ReactNode;
}) {
  return (
    <section
      aria-label={heading}
      data-withholding={name}
      className="flex flex-col gap-2 rounded-lg border bg-card p-3"
    >
      <h3 className="text-base font-semibold text-foreground">{heading}</h3>
      {children}
    </section>
  );
}

const NONE = "—";

/** The payers' certificates of one ejercicio, each under the words and
 * amounts the ledger served for it, the amount columns being the served
 * ones. */
export function RecordsTable({
  rows,
  amountColumns,
  locale,
}: {
  rows: readonly RetencionSoportadaRowProjection[];
  amountColumns: readonly RetencionSoportadaAmountColumnProjection[];
  locale: string;
}) {
  const t = useStrings();
  const amountOf = (
    found: RetencionSoportadaRowProjection,
    column: RetencionSoportadaAmountColumnProjection,
  ) => {
    const value = servedAmount(found, column);
    return value ? formatAmount(locale, value.decimal) : "";
  };
  const columns: Column<RetencionSoportadaRowProjection>[] = [
    {
      key: "class",
      label: t("desktop.withholding.column.class"),
      sort: (found) => found.income_class_label,
      cell: (found) => found.income_class_label,
    },
    {
      key: "payer",
      label: t("desktop.withholding.column.payer"),
      sort: (found) => found.payer_display_name,
      cell: (found) => found.payer_display_name,
    },
    {
      key: "origin",
      label: t("desktop.withholding.column.origin"),
      keepWords: true,
      sort: (found) => found.origin_label,
      cell: (found) => found.origin_label,
    },
    ...amountColumns.map((column): Column<RetencionSoportadaRowProjection> => ({
      key: column.field,
      label: column.label,
      numeric: true,
      sort: (found) => rankDecimal(servedAmount(found, column)?.decimal),
      cell: (found) => amountOf(found, column),
    })),
  ];
  return (
    <SetupTable
      label={t("desktop.withholding.records.title")}
      rows={rows}
      rowKey={(found) => `${found.income_class}:${found.payer_ref}`}
      columns={columns}
      className="withholding-records"
    />
  );
}

/** The statements that an income class had no withholding, active or
 * withdrawn, in the words served with each. */
export function AbsencesTable({
  rows,
  withdrawn,
  label,
  locale,
}: {
  rows: readonly RetencionSoportadaAbsenceRowProjection[];
  /** The rows were withdrawn: the day each was is shown. */
  withdrawn: boolean;
  label: string;
  locale: string;
}) {
  const t = useStrings();
  const columns: Column<RetencionSoportadaAbsenceRowProjection>[] = [
    {
      key: "class",
      label: t("desktop.withholding.column.class"),
      sort: (found) => found.income_class_label,
      cell: (found) => found.income_class_label,
    },
    {
      key: "state",
      label: t("desktop.withholding.column.state"),
      keepWords: true,
      sort: (found) => found.state_label,
      cell: (found) => found.state_label,
    },
    {
      key: "stated_on",
      label: t("desktop.withholding.column.stated_on"),
      keepWords: true,
      sort: (found) => found.attested_at,
      cell: (found) => formatInstantDay(locale, found.attested_at),
    },
    ...(withdrawn
      ? [
          {
            key: "withdrawn_on",
            label: t("desktop.withholding.column.withdrawn_on"),
            keepWords: true,
            sort: (found: RetencionSoportadaAbsenceRowProjection) =>
              found.withdrawn_at ?? "",
            cell: (found: RetencionSoportadaAbsenceRowProjection) =>
              found.withdrawn_at
                ? formatInstantDay(locale, found.withdrawn_at)
                : NONE,
          },
        ]
      : []),
    {
      key: "note",
      label: t("desktop.withholding.column.note"),
      cell: (found) => found.note,
    },
  ];
  return (
    <SetupTable
      label={label}
      rows={rows}
      rowKey={(found) => `${found.ejercicio}:${found.income_class}`}
      columns={columns}
      className={withdrawn ? "withholding-withdrawn" : "withholding-attested"}
    />
  );
}
