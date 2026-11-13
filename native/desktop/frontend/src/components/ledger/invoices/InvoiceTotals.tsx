import type { ReactNode } from "react";
import { MoneyEditor } from "@/components/editors/MoneyEditor";
import { PercentEditor } from "@/components/editors/PercentEditor";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { formatAmount, heldDecimal } from "../../../shared/numbers";
import type { InvoiceFiguresPreviewRetention } from "../../../shell/ledgerInvoiceContract";
import { compareDecimal } from "../../../shell/ledgerGrammar";
import { useStrings } from "../../../shell/strings";
import { FormField, wired } from "./InvoiceFields";

export function TotalsList({
  locale,
  currency,
  base,
  iva,
  total,
  failed = false,
  updating = false,
  recargo,
}: {
  locale: string;
  currency: string;
  /** Each the ledger's, and null while it has not answered one. */
  base: string | null;
  iva: string | null;
  total: string | null;
  failed?: boolean;
  updating?: boolean;
  recargo: ReactNode;
}) {
  const t = useStrings();
  const row = "flex items-baseline justify-between gap-3";
  const blank = failed ? t("desktop.ledger.invoices.not_available") : "—";
  return (
    <div
      className="ledger-invoice-totals flex flex-col gap-2 text-base"
      data-updating={updating || undefined}
    >
      <dl className="flex flex-col gap-2">
        <div className={row}>
          <dt className="text-muted-foreground">
            {t("desktop.ledger.invoices.base")}
          </dt>
          <dd className="tabular-nums">
            {base === null ? blank : formatAmount(locale, base)}
          </dd>
        </div>
        <div className={row}>
          <dt className="text-muted-foreground">
            {t("desktop.ledger.invoices.iva")}
          </dt>
          <dd className="tabular-nums">
            {iva === null ? blank : formatAmount(locale, iva)}
          </dd>
        </div>
      </dl>
      {recargo}
      <dl>
        <div className={cn(row, "border-t border-border pt-2 font-medium")}>
          <dt>{t("desktop.ledger.invoices.total")}</dt>
          <dd className="ledger-invoice-total tabular-nums">
            {total === null ? blank : formatAmount(locale, total, { currency })}
          </dd>
        </div>
      </dl>
      {updating && (
        <p
          className="ledger-invoice-updating text-xs text-muted-foreground"
          role="status"
        >
          {t("desktop.ledger.invoices.figures_updating")}
        </p>
      )}
    </div>
  );
}

/** Retención, outside the total, typed as the document states it. The ledger
 * says what its rate implies, and what is left to be paid. */
export function Retention({
  locale,
  rate,
  amount,
  answered,
  net,
  withheld,
  rateError,
  amountError,
  onRate,
  onAmount,
  onBlur,
}: {
  locale: string;
  rate: string;
  amount: string;
  /** The ledger's answer to this very retención, or null while none. */
  answered: InvoiceFiguresPreviewRetention | null;
  /** What the ledger says is left to pay, and the retención it took off. */
  net: string | null;
  withheld: string | null;
  rateError: string | null;
  amountError: string | null;
  onRate(value: string): void;
  onAmount(value: string): void;
  onBlur(field: string): void;
}) {
  const t = useStrings();
  const implied = answered?.implied?.decimal ?? null;
  const offerImplied =
    implied !== null &&
    (answered?.amount == null ||
      compareDecimal(answered.amount.decimal, implied) !== 0);
  return (
    <div className="ledger-invoice-retention flex flex-col gap-3 rounded-lg bg-accent p-3">
      <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
        {t("desktop.ledger.invoices.retention")}
      </span>
      <div className="grid grid-cols-2 gap-2">
        <FormField
          label={t("desktop.ledger.invoices.field.retention_rate")}
          error={rateError}
        >
          {(control) => (
            <PercentEditor
              {...wired(control)}
              unit="points"
              controlSize="sm"
              value={rate}
              onChange={onRate}
              onBlur={() => onBlur("retention_rate")}
            />
          )}
        </FormField>
        <FormField
          label={t("desktop.ledger.invoices.field.retention_amount")}
          error={amountError}
        >
          {(control) => (
            <MoneyEditor
              {...wired(control)}
              controlSize="sm"
              value={amount}
              onChange={onAmount}
              onBlur={() => onBlur("retention_amount")}
            />
          )}
        </FormField>
      </div>
      {offerImplied && (
        <p className="ledger-invoice-implied flex flex-wrap items-center gap-2 text-sm tabular-nums">
          {t("desktop.ledger.invoices.retention_implied", {
            amount: formatAmount(locale, implied),
          })}
          <Button
            variant="link"
            size="xs"
            onClick={() => onAmount(heldDecimal(implied))}
          >
            {t("desktop.ledger.invoices.use")}
          </Button>
        </p>
      )}
      {net !== null && (
        <p className="ledger-invoice-to-pay text-sm tabular-nums">
          {withheld !== null
            ? t("desktop.ledger.invoices.to_pay_withheld", {
                amount: formatAmount(locale, net),
                retention: formatAmount(locale, withheld),
              })
            : t("desktop.ledger.invoices.to_pay", {
                amount: formatAmount(locale, net),
              })}
        </p>
      )}
    </div>
  );
}
