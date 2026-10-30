import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import type { ActivityAssetForecast } from "../../../shell/ledgerSetup";
import { useStrings } from "../../../shell/strings";
import { WriteHold } from "../WritePause";
import { amountText, dateText } from "../movements/movementWords";
import {
  Panel,
  Reading,
  useSetupDraft,
  useSetupWrite,
} from "../setup/SetupParts";
import type { SetupCall } from "../setup/setupModel";
import {
  OptionsFields,
  OptionsRead,
  useAssetRow,
  useOptionsDraft,
  useProvisionalRead,
  WriteLine,
  type ActProps,
} from "./AssetForm";
import {
  answer,
  claimLanding,
  claimReused,
  draftedCall,
  forecastRequest,
  neverReused,
  viewOf,
} from "./assetWrites";
import type { DraftedResults, FormField } from "./assetsContract";
import { ASSET_KEYS } from "./assetsWords";

const NO_FIELDS = new Set<string>();

/**
 * Records a year's depreciation in two steps: the forecast first, which works
 * out the span and records nothing, then the claim. The span starts from what
 * is still claimable, or from the claim being corrected, as the backend
 * states it. A claim that overlaps another is refused naming it, and offers
 * to correct that one instead; a claim sent again for the same forecast is
 * answered as already recorded. The claim's landing is read from the plan's
 * claims.
 */
export function ClaimFlow({
  port,
  reader,
  locale,
  assetId,
  taxYear,
  supersedes = null,
  onClose,
  onWritten,
}: ActProps & {
  assetId: string;
  taxYear: number;
  /** The claim the new one replaces, in the same write. */
  supersedes?: string | null;
}) {
  const t = useStrings();
  const [replaces, setReplaces] = useState<string | null>(supersedes);
  const asset = useAssetRow(port, reader, assetId);
  const options = useProvisionalRead(
    port,
    reader,
    "ledger.actividad-asset.form-options",
    {
      kind: "claim",
      asset_id: assetId,
      tax_year: taxYear,
      ...(replaces === null ? {} : { supersedes_claim_id: replaces }),
    },
    `claim:${assetId}:${taxYear}:${replaces ?? ""}`,
  );
  const form = useOptionsDraft(
    options.read?.kind === "done" ? options.read.result.options : null,
  );
  const [forecast, setForecast] = useState<ActivityAssetForecast | null>(null);
  const [forecastCall, setForecastCall] = useState<SetupCall<
    DraftedResults["ledger.actividad-asset.forecast"]
  > | null>(null);
  const [reading, setReading] = useState(false);
  const write = useSetupWrite(
    [t(ASSET_KEYS.action.claim), asset.row?.name].filter(Boolean).join(" · "),
  );
  useSetupDraft(form.dirty);

  const answered = form.options ? answer(form.options, form.draft, null) : null;
  const request = answered
    ? forecastRequest(assetId, answered.values, replaces)
    : null;
  const ready =
    answered !== null &&
    Object.keys(answered.problems).length === 0 &&
    request !== null;
  const view = viewOf(write.last, claimReused);
  const forecastView = viewOf(forecastCall, neverReused);
  const missing = new Set(
    forecastView.kind === "refused" ? forecastView.missing : [],
  );

  // A different span is a different forecast.
  const onField = (field: FormField, value: string) => {
    form.set({ [field.key]: value });
    setForecast(null);
    setForecastCall(null);
    write.clear();
  };

  const preview = async () => {
    if (!ready || request === null || reading || write.busy) return;
    setReading(true);
    setForecast(null);
    write.clear();
    const call = await draftedCall(
      port,
      "ledger.actividad-asset.forecast",
      request,
      false,
    );
    setForecastCall(call);
    setReading(false);
    if (call.kind === "done" && call.result.forecast)
      setForecast(call.result.forecast);
  };

  const claim = async () => {
    if (forecast === null || write.busy) return;
    const done = await write.run(
      () =>
        draftedCall(
          port,
          "ledger.actividad-asset.claim",
          { forecast, supersedes_claim_id: replaces },
          true,
        ),
      claimLanding(port, assetId, {
        tax_year: forecast.tax_year,
        from: forecast.covered_from,
        until: forecast.covered_until,
        amount: forecast.amount.decimal,
      }),
    );
    if (viewOf(done, claimReused).kind === "saved") {
      options.reload();
      onWritten?.();
    }
  };

  const supersede = (claimId: string) => {
    setReplaces(claimId);
    setForecast(null);
    setForecastCall(null);
    write.clear();
  };

  const shown = form.options;
  return (
    <Panel
      title={t(
        replaces === null
          ? ASSET_KEYS.action.claim
          : "desktop.ledger.assets.claim.correct_title",
      )}
      className="ledger-asset-form ledger-asset-form-claim"
    >
      {shown === null ? (
        <OptionsRead call={options.read} />
      ) : (
        <form
          noValidate
          className="flex flex-col gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            void preview();
          }}
        >
          <OptionsFields
            options={shown}
            draft={form.draft}
            onField={onField}
            problems={answered?.problems ?? {}}
            missing={missing}
            candidates={[]}
            purchaseKnown={NO_FIELDS}
            locale={locale}
          />
          <div className="flex flex-wrap gap-2">
            {onClose && (
              <Button
                type="button"
                size="sm"
                variant="ghost"
                aria-disabled={write.busy || undefined}
                onClick={() => {
                  if (!write.busy) onClose();
                }}
              >
                {t("desktop.ledger.form.cancel")}
              </Button>
            )}
            <Button
              type="submit"
              size="sm"
              variant="outline"
              className="ledger-asset-forecast"
              aria-disabled={!ready || reading || write.busy || undefined}
            >
              {t("desktop.ledger.assets.submit.forecast")}
            </Button>
          </div>
          {reading && <Reading label={t("desktop.ledger.form.reading")} />}
          <WriteLine
            call={forecastCall}
            locale={locale}
            options={shown}
            saved={null}
          />
          {forecast && (
            <div className="ledger-asset-forecast-result flex flex-col gap-2">
              <Alert icon={<Icon name="info" />}>
                <span className="font-medium tabular-nums">
                  {t("desktop.ledger.assets.forecast", {
                    amount: amountText(locale, forecast.amount.decimal),
                    days: forecast.service_days,
                    from: dateText(locale, forecast.covered_from, true),
                    until: dateText(locale, forecast.covered_until, true),
                  })}
                </span>
                <span className="text-sm">
                  {t("desktop.ledger.assets.forecast_note")}
                </span>
              </Alert>
              <div className="flex gap-2">
                <WriteHold>
                  <Button
                    type="button"
                    size="sm"
                    className="ledger-asset-claim"
                    aria-disabled={write.busy || undefined}
                    onClick={() => void claim()}
                  >
                    {write.busy
                      ? t("desktop.ledger.form.saving")
                      : t("desktop.ledger.assets.claim")}
                  </Button>
                </WriteHold>
              </div>
            </div>
          )}
          <WriteLine
            call={write.last}
            locale={locale}
            options={shown}
            saved={{
              done: t("desktop.ledger.assets.claimed"),
              reused: t("desktop.ledger.assets.claim_reused"),
              reusedOf: claimReused,
            }}
            onSupersede={view.kind === "refused" ? supersede : undefined}
          />
        </form>
      )}
    </Panel>
  );
}
