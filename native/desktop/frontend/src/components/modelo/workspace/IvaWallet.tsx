import { useEffect, useId, useMemo, useState } from "react";
import { YearEditor } from "@/components/editors/YearEditor";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Spinner } from "@/components/ui/spinner";
import { formatAmount } from "../../../shared/numbers";
import { parseYear, type LedgerPeriod } from "../../../shell/ledgerGrammar";
import {
  declarationWriteKey,
  walletWriteKey,
} from "../../../shell/modeloWriteHolds";
import { useStrings } from "../../../shell/strings";
import {
  ModeloWriteScope,
  ScopedWriteHoldNotice,
  useModeloWriteScope,
  useModeloOperation,
} from "../WriteScope";
import { IvaWalletDialog } from "./IvaWalletDialog";
import { useIvaWalletBalance } from "./ivaWalletRead";

/** A refusal's opening-balance door, taken `count` times, naming the period
 * whose closing balance the refused carry reads. That period is the one the
 * backend served, which can precede the declaration on screen. */
export type OpeningBalanceAsk = { count: number; period: LedgerPeriod };

export function IvaWallet({
  period,
  locale,
  openingBalanceAsk = null,
}: {
  period: LedgerPeriod;
  locale: string;
  /** The opening-balance door as last taken; each rise of its count opens
   * the balance entry at its period. Null while none was. */
  openingBalanceAsk?: OpeningBalanceAsk | null;
}) {
  const scope = useModeloWriteScope();
  const t = useStrings();
  const owner = useMemo(
    () =>
      scope.owner && {
        ...scope.owner,
        label: `${t("workspace.modelo.iva_wallet.title")} · ${scope.owner.label}`,
      },
    [scope.owner, t],
  );
  return (
    <ModeloWriteScope {...scope} target={walletWriteKey} owner={owner}>
      <WalletBalance
        period={period}
        locale={locale}
        openingBalanceAsk={openingBalanceAsk}
      />
    </ModeloWriteScope>
  );
}

function WalletBalance({
  period,
  locale,
  openingBalanceAsk,
}: {
  period: LedgerPeriod;
  locale: string;
  openingBalanceAsk: OpeningBalanceAsk | null;
}) {
  const t = useStrings();
  const { port, holds, hold, owner } = useModeloOperation();
  const yearId = useId();
  const [yearText, setYear] = useState(String(period.year));
  const parsed = parseYear(yearText);
  const year = parsed.kind === "value" ? parsed.value : null;
  const { read, reload } = useIvaWalletBalance(port, holds, year);
  const [managing, setManaging] = useState(false);
  // The period the balance entry opens at: the one a refusal's door served,
  // or the declaration's own when the person opens it themselves.
  const [entryPeriod, setEntryPeriod] = useState(period);
  // A refusal's door asked for the opening-balance entry. It opens unless an
  // operation of this declaration is running, which is what holds the button.
  // Each taking of the door is a new ask, so the same door opens it again.
  useEffect(() => {
    if (openingBalanceAsk && openingBalanceAsk.count > 0 && !hold) {
      setEntryPeriod(openingBalanceAsk.period);
      setManaging(true);
    }
  }, [openingBalanceAsk, hold]);
  const amount = (value: string) =>
    formatAmount(locale, value, { currency: "EUR" });
  const values =
    read.phase === "ready"
      ? [
          ["total_balance", amount(read.result.total_balance)],
          ["active_balance", amount(read.result.active_balance)],
          ["expired_balance", amount(read.result.expired_balance)],
          ["lot_count", String(read.result.lot_count)],
          [
            "next_expiry_year",
            read.result.next_expiry_year === null
              ? t("workspace.modelo.iva_wallet.expiry_not_reported")
              : String(read.result.next_expiry_year),
          ],
          [
            "unallocated_applied_amount",
            amount(read.result.unallocated_applied_amount),
          ],
        ]
      : [];
  return (
    <section
      aria-label={t("workspace.modelo.iva_wallet.title")}
      className="mx-auto flex w-full max-w-3xl flex-col gap-4"
    >
      <div>
        <h2 className="text-xl">{t("workspace.modelo.iva_wallet.title")}</h2>
        <p className="text-sm text-muted-foreground">
          {t("workspace.modelo.iva_wallet.lead")}
        </p>
      </div>
      <ScopedWriteHoldNotice
        exclude={[
          walletWriteKey,
          ...(owner ? [declarationWriteKey(owner.workUnitId)] : []),
        ]}
      />
      <div className="flex flex-wrap items-end gap-3">
        <Field className="w-32" data-invalid={year === null}>
          <FieldLabel htmlFor={yearId}>
            {t("workspace.modelo.iva_wallet.as_of_year")}
          </FieldLabel>
          <YearEditor
            id={yearId}
            value={yearText}
            onChange={setYear}
            invalid={year === null}
            required
          />
          {year === null && yearText !== "" && (
            <FieldError>
              {t("desktop.ledger.edit.refusal.year_not_a_number", {
                raw: yearText,
              })}
            </FieldError>
          )}
        </Field>
        <Button
          variant="outline"
          disabled={
            year === null || read.phase === "reading" || read.phase === "held"
          }
          onClick={reload}
        >
          {t("workspace.modelo.iva_wallet.reload")}
        </Button>
        <Button
          variant="secondary"
          disabled={!!hold}
          onClick={() => {
            setEntryPeriod(period);
            setManaging(true);
          }}
        >
          {t("workspace.modelo.iva_wallet.manage")}
        </Button>
      </div>
      {year !== null &&
        read.phase !== "held" &&
        (read.phase === "reading" ? (
          <p role="status" className="flex items-center gap-2 text-sm">
            <Spinner />
            {t("workspace.modelo.iva_wallet.loading")}
          </p>
        ) : read.phase === "failed" ? (
          <Alert tone="warning" role="alert">
            {read.words ?? t("workspace.modelo.iva_wallet.read_failed")}
          </Alert>
        ) : (
          <dl className="grid grid-cols-1 gap-4 rounded-lg border border-border bg-card p-4 @xl:grid-cols-2">
            {values.map(([key, value]) => (
              <div key={key}>
                <dt className="text-sm text-muted-foreground">
                  {t(`workspace.modelo.iva_wallet.${key}`)}
                </dt>
                <dd className="font-mono tabular-nums">{value}</dd>
              </div>
            ))}
          </dl>
        ))}
      {managing && (
        <IvaWalletDialog
          period={entryPeriod}
          locale={locale}
          onClose={() => setManaging(false)}
        />
      )}
    </section>
  );
}
