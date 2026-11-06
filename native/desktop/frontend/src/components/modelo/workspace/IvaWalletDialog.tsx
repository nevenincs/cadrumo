import { useEffect, useId, useRef, useState } from "react";
import { MoneyEditor } from "@/components/editors/MoneyEditor";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Spinner } from "@/components/ui/spinner";
import { formatAmount } from "../../../shared/numbers";
import { publicPeriod, type LedgerPeriod } from "../../../shell/ledgerGrammar";
import { ledgerPeriod, usePeriods } from "../../../shell/ledgerPeriods";
import type {
  ModeloIvaWalletSeedProjection,
  ModeloIvaWalletCorrectionProjection,
  ModeloIvaWalletOverrideProjection,
} from "../../../shell/modeloContract/modeloIvaWallet";
import { useStrings } from "../../../shell/strings";
import { PeriodSelector } from "../../ledger/PeriodSelector";
import { periodText } from "../../ledger/ledgerWords";
import { ScopedWriteHoldNotice, useModeloOperation } from "../WriteScope";

type Mode = "seed" | "correct" | "override";
type Draft = {
  period: LedgerPeriod;
  amount: string;
  reason: string;
  evidence: string;
};
type WalletResult =
  | ModeloIvaWalletSeedProjection
  | ModeloIvaWalletCorrectionProjection
  | ModeloIvaWalletOverrideProjection;
const modes: readonly Mode[] = ["seed", "correct", "override"];

export function IvaWalletDialog({
  period,
  locale,
  onClose,
}: {
  period: LedgerPeriod;
  locale: string;
  onClose(): void;
}) {
  const t = useStrings();
  const scope = useModeloOperation();
  const id = useId();
  const [mode, setMode] = useState<Mode>("seed");
  const [drafts, setDrafts] = useState<Record<Mode, Draft>>(
    () =>
      Object.fromEntries(
        modes.map((key) => [
          key,
          {
            period,
            amount: "",
            reason: "",
            evidence: "",
          },
        ]),
      ) as Record<Mode, Draft>,
  );
  const draft = drafts[mode];
  const [notice, setNotice] = useState<string | null>(null);
  const [written, setWritten] = useState<WalletResult | null>(null);
  // The period recorded, as the periods store holds one, worded once its
  // year is served.
  const writtenPeriod = written ? ledgerPeriod(written.period) : null;
  usePeriods({ years: writtenPeriod ? [writtenPeriod.year] : [] });
  const receiptWords = (value: string) => {
    switch (value) {
      case "operator_seed":
        return t(
          "workspace.modelo.iva_wallet.receipt.provenance.operator_seed",
        );
      case "operator_correction":
        return t(
          "workspace.modelo.iva_wallet.receipt.provenance.operator_correction",
        );
      case "taxpayer_override":
        return t(
          "workspace.modelo.iva_wallet.receipt.authority.taxpayer_override",
        );
      case "override":
        return t("workspace.modelo.iva_wallet.receipt.divergence.override");
      default:
        return value;
    }
  };
  const active = useRef(true);
  const pending = useRef(false);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
    };
  }, []);
  const change = (update: Partial<Draft>) => {
    setDrafts((current) => ({
      ...current,
      [mode]: { ...current[mode], ...update },
    }));
    setWritten(null);
    setNotice(null);
  };
  const quiet = !!scope.hold;
  const complete =
    draft.amount.trim() !== "" &&
    (mode === "seed" || draft.reason.trim() !== "") &&
    (mode !== "override" || draft.evidence.trim() !== "");
  const submit = async () => {
    if (pending.current || quiet || !complete || written || !scope.owner)
      return;
    pending.current = true;
    setNotice(null);
    const common = { period: publicPeriod(draft.period), amount: draft.amount };
    try {
      const outcome = await scope.run<WalletResult>(
        () => {
          if (mode === "seed")
            return scope.port.submit("modelo.iva-wallet.seed", common);
          if (mode === "correct")
            return scope.port.submit("modelo.iva-wallet.correct", {
              ...common,
              reason: draft.reason,
            });
          return scope.port.submit("modelo.iva-wallet.override", {
            ...common,
            reason: draft.reason,
            evidence_locator: draft.evidence,
          });
        },
        () => active.current,
      );
      if (!outcome || !active.current) return;
      if (outcome.kind === "settled") setWritten(outcome.result);
      else if (outcome.kind === "refused")
        setNotice(outcome.words ?? t("workspace.modelo.outcome.refused"));
      else if (outcome.kind === "not_sent")
        setNotice(t("workspace.modelo.outcome.failed"));
      if (outcome.kind === "settled" || outcome.kind === "saved_unread") {
        const hold = scope.holds.get(scope.target);
        if (hold && scope.reloadHold) await scope.reloadHold(hold);
      }
    } finally {
      pending.current = false;
    }
  };
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("workspace.modelo.iva_wallet.title")}</DialogTitle>
          <DialogDescription>
            {t("workspace.modelo.iva_wallet.lead")}
          </DialogDescription>
        </DialogHeader>
        <form
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
        >
          <ScopedWriteHoldNotice />
          <Field>
            <FieldLabel htmlFor={`${id}-action`}>
              {t("workspace.modelo.iva_wallet.action")}
            </FieldLabel>
            <NativeSelect
              id={`${id}-action`}
              value={mode}
              disabled={quiet}
              onChange={(event) => {
                const next = modes.find(
                  (value) => value === event.target.value,
                );
                if (next) {
                  setMode(next);
                  setWritten(null);
                  setNotice(null);
                }
              }}
            >
              {modes.map((value) => (
                <option key={value} value={value}>
                  {t(`workspace.modelo.iva_wallet.mode.${value}`)}
                </option>
              ))}
            </NativeSelect>
          </Field>
          <p id={`${id}-help`} className="text-sm text-muted-foreground">
            {t(`workspace.modelo.iva_wallet.help.${mode}`)}
          </p>
          <fieldset disabled={quiet} className="flex min-w-0 flex-col gap-4">
            <PeriodSelector
              value={draft.period}
              onChange={(next) => {
                if (next) change({ period: next });
              }}
              label={t("workspace.declarations.list.column.period")}
              years={null}
              locale={locale}
              fallbackYear={period.year}
              allowAll={false}
            />
            <Field>
              <FieldLabel htmlFor={`${id}-amount`}>
                {t("workspace.modelo.iva_wallet.amount")}
              </FieldLabel>
              <MoneyEditor
                id={`${id}-amount`}
                value={draft.amount}
                onChange={(amount) => change({ amount })}
                currency="EUR"
                describedBy={`${id}-help`}
                required
              />
            </Field>
            {mode !== "seed" && (
              <Field>
                <FieldLabel htmlFor={`${id}-reason`}>
                  {t("workspace.modelo.iva_wallet.reason")}
                </FieldLabel>
                <Input
                  id={`${id}-reason`}
                  value={draft.reason}
                  onChange={(event) => change({ reason: event.target.value })}
                  required
                />
              </Field>
            )}
            {mode === "override" && (
              <Field>
                <FieldLabel htmlFor={`${id}-evidence`}>
                  {t("workspace.modelo.iva_wallet.evidence_locator")}
                </FieldLabel>
                <Input
                  id={`${id}-evidence`}
                  value={draft.evidence}
                  onChange={(event) => change({ evidence: event.target.value })}
                  required
                />
              </Field>
            )}
          </fieldset>
          {notice && (
            <Alert tone="warning" role="alert">
              {notice}
            </Alert>
          )}
          {written && (
            <div
              role="status"
              className="flex flex-col gap-2 rounded-lg border border-border p-3 text-sm"
            >
              <p>{t("workspace.modelo.iva_wallet.recorded")}</p>
              <dl className="grid grid-cols-2 gap-2 break-words [overflow-wrap:anywhere]">
                <dt>{t("workspace.declarations.list.column.period")}</dt>
                <dd>
                  {writtenPeriod
                    ? periodText(t, locale, writtenPeriod)
                    : `${written.period.filing_year} · ${written.period.code}`}
                </dd>
                <dt>{t("workspace.modelo.iva_wallet.amount")}</dt>
                <dd>
                  {formatAmount(locale, written.amount, { currency: "EUR" })}
                </dd>
                {"previous_amount" in written && (
                  <>
                    <dt>{t("workspace.modelo.iva_wallet.previous_amount")}</dt>
                    <dd>
                      {formatAmount(locale, written.previous_amount, {
                        currency: "EUR",
                      })}
                    </dd>
                  </>
                )}
                {"reason" in written && (
                  <>
                    <dt>{t("workspace.modelo.iva_wallet.reason")}</dt>
                    <dd className="break-words">{written.reason}</dd>
                  </>
                )}
                {"evidence_locator" in written && (
                  <>
                    <dt>{t("workspace.modelo.iva_wallet.evidence_locator")}</dt>
                    <dd className="break-words">{written.evidence_locator}</dd>
                  </>
                )}
                {"provenance" in written && (
                  <>
                    <dt>{t("workspace.modelo.iva_wallet.receipt.source")}</dt>
                    <dd>{receiptWords(written.provenance)}</dd>
                  </>
                )}
                {"register_status" in written && (
                  <>
                    <dt>
                      {t("workspace.modelo.iva_wallet.receipt.register_status")}
                    </dt>
                    <dd>
                      {written.register_status === null
                        ? t("workspace.modelo.iva_wallet.receipt.not_reported")
                        : written.register_status}
                    </dd>
                  </>
                )}
                {"selected_authority" in written && (
                  <>
                    <dt>
                      {t("workspace.modelo.iva_wallet.receipt.selected_source")}
                    </dt>
                    <dd>{receiptWords(written.selected_authority)}</dd>
                  </>
                )}
                {"divergence" in written && (
                  <>
                    <dt>
                      {t(
                        "workspace.modelo.iva_wallet.receipt.reconciliation_outcome",
                      )}
                    </dt>
                    <dd>{receiptWords(written.divergence)}</dd>
                  </>
                )}
              </dl>
            </div>
          )}
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={onClose}>
              {t("workspace.modelo.key.close")}
            </Button>
            <Button
              type="submit"
              disabled={quiet || !complete || !!written || !scope.owner}
            >
              {scope.hold?.phase === "running" && <Spinner />}
              {t(`workspace.modelo.iva_wallet.mode.${mode}`)}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
