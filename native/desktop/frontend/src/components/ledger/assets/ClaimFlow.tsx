import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { facts } from "../../../shell/compose";
import type {
  ActivityAssetForecast,
  ActivityAssetForecastResult,
} from "../../../shell/ledgerSetup";
import { useStrings } from "../../../shell/strings";
import { WriteHold } from "../WritePause";
import { amountText, dateText } from "../movements/movementWords";
import {
  ChoiceField,
  Panel,
  Reading,
  useSetupDraft,
  useSetupWrite,
} from "../setup/SetupParts";
import { setupCall, type SetupCall } from "../setup/setupModel";
import { answer, claimFields, draftOf, type FormField } from "./assetFields";
import {
  FieldsGrid,
  OptionsRead,
  useAssetRow,
  useFieldsDraft,
  useLedgerRead,
  WriteLine,
  type ActProps,
} from "./AssetForm";
import {
  claimLanding,
  claimReused,
  forecastRequest,
  neverReused,
  viewOf,
} from "./assetWrites";
import { ASSET_KEYS } from "./assetsWords";

const NO_FIELDS = new Set<string>();

/**
 * Records a year's depreciation in two steps: the forecast first, which works
 * out the span and records nothing, then the claim. The span starts from what
 * the plan says is still claimable, or from the claim being replaced; a claim
 * that overlaps another is refused with the backend's reason, and a claim
 * sent again for the same forecast is answered as already recorded. The
 * claim's landing is read from the plan's claims.
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
  const plan = useLedgerRead(
    port,
    reader,
    "ledger.actividad-asset.plan",
    { asset_id: assetId },
    assetId,
  );
  const rows = plan.read?.kind === "done" ? plan.read.result.rows : null;
  const year = rows?.find((row) => row.tax_year === taxYear) ?? null;
  const effective = (year?.claims ?? []).filter((claim) => claim.effective);
  const replaced =
    effective.find((claim) => claim.claim_id === replaces) ?? null;
  const fields = claimFields(year, replaced);
  const form = useFieldsDraft(draftOf(fields));
  const [forecast, setForecast] = useState<ActivityAssetForecast | null>(null);
  const [forecastCall, setForecastCall] =
    useState<SetupCall<ActivityAssetForecastResult> | null>(null);
  const [reading, setReading] = useState(false);
  const write = useSetupWrite(
    facts(t, [t(ASSET_KEYS.action.claim), asset.row?.name]),
  );
  useSetupDraft(form.dirty);

  const answered = answer(fields, form.draft, null);
  const request = forecastRequest(assetId, answered.values, replaces);
  const ready = Object.keys(answered.problems).length === 0 && request !== null;
  const forecastView = viewOf(forecastCall, neverReused);
  const missing = new Set(
    forecastView.kind === "refused" ? forecastView.missing : [],
  );

  // A different span is a different forecast.
  const changed = () => {
    setForecast(null);
    setForecastCall(null);
    write.clear();
  };
  const onField = (field: FormField, value: string) => {
    form.set({ [field.key]: value });
    changed();
  };

  const preview = async () => {
    if (!ready || request === null || reading || write.busy) return;
    setReading(true);
    setForecast(null);
    write.clear();
    const call = await setupCall(
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
        setupCall(
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
      plan.reload();
      onWritten?.();
    }
  };

  return (
    <Panel
      title={t(
        replaces === null
          ? ASSET_KEYS.action.claim
          : "desktop.ledger.assets.correct_claim_title",
      )}
      className="ledger-asset-form ledger-asset-form-claim"
    >
      {year === null ? (
        <OptionsRead call={plan.read} />
      ) : (
        <form
          noValidate
          className="flex flex-col gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            void preview();
          }}
        >
          {effective.length > 0 && (
            <ChoiceField
              label={t("desktop.ledger.assets.replace_claim")}
              value={replaces ?? ""}
              onValue={(value) => {
                setReplaces(value === "" ? null : value);
                changed();
              }}
              placeholder={t("desktop.ledger.assets.replace_none")}
              options={effective.map((claim) => ({
                value: claim.claim_id,
                label: t("desktop.ledger.assets.correct.claim_item", {
                  year: taxYear,
                  amount: amountText(locale, claim.amount.decimal),
                  from: dateText(locale, claim.covered_from, true),
                  until: dateText(locale, claim.covered_until, true),
                }),
              }))}
            />
          )}
          <FieldsGrid
            fields={fields}
            options={null}
            draft={form.draft}
            onField={onField}
            problems={answered.problems}
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
          <WriteLine call={forecastCall} fields={fields} saved={null} />
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
                      : t(ASSET_KEYS.action.claim)}
                  </Button>
                </WriteHold>
              </div>
            </div>
          )}
          <WriteLine
            call={write.last}
            fields={fields}
            saved={{
              done: t("desktop.ledger.assets.claimed"),
              reused: t("desktop.ledger.assets.claim_reused"),
              reusedOf: claimReused,
            }}
          />
        </form>
      )}
    </Panel>
  );
}
