import { useState, type ReactNode } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import type { LedgerPort } from "../../../shell/ledger";
import { useStrings } from "../../../shell/strings";
import { dateText } from "../movements/movementWords";
import { CallLine, Reading } from "../setup/SetupParts";
import { setupCall, type SetupCall } from "../setup/setupModel";
import { callRefusal } from "./AssetList";
import { disposalOf } from "./assetWrites";
import type {
  ActivityAssetDisposalCalculateResult,
  DisposalCalculation,
} from "../../../shell/ledgerSetup";
import type { FormValues } from "./assetFields";
import {
  ASSET_KEYS,
  fieldWord,
  keyedText,
  refusalText,
  tokenWord,
} from "./assetsWords";
import { DASH, figureText } from "./planWords";

type Calculation = ActivityAssetDisposalCalculateResult;

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 text-right tabular-nums">{children}</dd>
    </>
  );
}

/** The figures the backend works out for a baja, drawn as served. A figure
 * the reason does not compute is left out, never drawn as zero. */
function Figures({
  locale,
  calculation,
}: {
  locale: string;
  calculation: DisposalCalculation;
}) {
  const t = useStrings();
  const text = ASSET_KEYS.baja;
  const rows: [string, ReturnType<typeof figureText>][] = [
    [text.acquisition_value, figureText(locale, calculation.acquisition_value)],
    [text.deducted, figureText(locale, calculation.deducted)],
    [text.minimum, figureText(locale, calculation.minimum)],
    [text.reduction, figureText(locale, calculation.reduction)],
    [text.excess, figureText(locale, calculation.excess)],
    [text.net_value, figureText(locale, calculation.net_value)],
    [
      text.transmission_value,
      figureText(locale, calculation.transmission_value),
    ],
    [
      fieldWord(t, "disposal.transmission_costs"),
      figureText(locale, calculation.transmission_costs),
    ],
    [text.result, figureText(locale, calculation.result)],
  ];
  return (
    <section
      aria-label={t(text.figures)}
      className="ledger-asset-figures flex flex-col gap-2 text-sm"
    >
      <h4 className="font-medium">{t(text.figures)}</h4>
      <p className="text-muted-foreground">
        {tokenWord(t, "disposal_reason", calculation.reason)} ·{" "}
        {dateText(locale, calculation.disposal_date, true)}
      </p>
      <dl className="grid grid-cols-[1fr_max-content] gap-x-4 gap-y-0.5">
        {rows
          // A figure the reason does not compute is left out; the minimum is
          // always drawn, and is said to be not worked out where it is null.
          .filter(([label, said]) => said !== null || label === text.minimum)
          .map(([label, said]) => (
            <Fact key={label} label={t(label)}>
              {said ?? t("desktop.ledger.assets.column.unavailable")}
            </Fact>
          ))}
      </dl>
      {calculation.route_changed_by_later_affectation && (
        <Alert icon={<Icon name="info" />}>{t(text.route_changed)}</Alert>
      )}
      {calculation.findings.length > 0 && (
        <ul
          aria-label={t(text.findings)}
          className="flex flex-col gap-0.5 text-muted-foreground"
        >
          {calculation.findings.map((finding, at) => (
            <li
              key={`${finding.kind}:${finding.tax_year ?? ""}:${at}`}
              className="inline-flex flex-wrap items-center gap-x-1.5"
            >
              <Icon name="alert" size="xs" className="text-warning" />
              {keyedText(t, finding.label_key, t(ASSET_KEYS.unrecognised))}
              {finding.tax_year !== null && (
                <span className="tabular-nums">{finding.tax_year}</span>
              )}
              <span className="tabular-nums">
                {figureText(locale, finding.effect_on_cost) ?? DASH}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/**
 * Previews a baja: asks the backend for the figures of the baja the form
 * states and draws what it answers. It writes nothing. A preview belongs to
 * what was stated when it was asked, and is dropped when the form changes.
 */
export function DisposalFigures({
  port,
  reader,
  locale,
  assetId,
  values,
  ready,
}: {
  port: LedgerPort;
  reader?: string | null;
  locale: string;
  assetId: string;
  values: FormValues;
  ready: boolean;
}) {
  const t = useStrings();
  const stated = disposalOf(values);
  const signature = JSON.stringify(stated);
  const [asked, setAsked] = useState<{
    signature: string;
    call: SetupCall<Calculation> | null;
  } | null>(null);
  const shown = asked !== null && asked.signature === signature ? asked : null;
  const preview = async () => {
    if (!ready || stated === null || reader === null) return;
    setAsked({ signature, call: null });
    const call = await setupCall(
      port,
      "ledger.actividad-asset.disposal-calculate",
      { asset_id: assetId, disposal: stated },
      false,
    );
    setAsked({ signature, call });
  };
  const body = () => {
    if (shown === null) return null;
    if (shown.call === null)
      return <Reading label={t("desktop.ledger.form.reading")} />;
    if (shown.call.kind !== "done")
      return (
        <CallLine call={shown.call} refusal={callRefusal(t, shown.call)} />
      );
    const { outcome, refusal, calculation } = shown.call.result;
    if (outcome === "refused" || calculation === null)
      return (
        <Alert
          tone="danger"
          role="alert"
          icon={<Icon name="refused" />}
          className="ledger-asset-figures-refused"
        >
          {refusalText(t, refusal)}
        </Alert>
      );
    return <Figures locale={locale} calculation={calculation} />;
  };
  return (
    <div className="flex flex-col gap-2">
      <div>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="ledger-asset-preview"
          aria-disabled={!ready || undefined}
          onClick={() => void preview()}
        >
          {t(ASSET_KEYS.baja.preview)}
        </Button>
      </div>
      {body()}
    </div>
  );
}
