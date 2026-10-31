import { useRef, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { facts } from "../../../shell/compose";
import type {
  ActivityAssetForecast,
  ActivityAssetForecastResult,
  PlanClaim,
  PlanRow,
} from "../../../shell/ledgerSetup";
import { useStrings } from "../../../shell/strings";
import { WriteHold } from "../WritePause";
import { formatDay } from "../../../shared/dateFormats";
import { formatAmount } from "../../../shared/numbers";
import {
  ChoiceField,
  Panel,
  Reading,
  useSetupDraft,
  useSetupWrite,
} from "../setup/SetupParts";
import { setupCall, type SetupCall } from "../setup/setupModel";
import {
  answer,
  claimFields,
  claimSpans,
  draftOf,
  throughOf,
  type FormField,
} from "./assetFields";
import { Remedy } from "./AssetList";
import {
  FieldsGrid,
  OptionsRead,
  useAssetRow,
  useFieldsDraft,
  useFocusOnOpen,
  useLedgerRead,
  WriteLine,
  type ActProps,
} from "./AssetForm";
import {
  CLAIM_CONFLICT,
  CLAIMS_OVERLAP,
  claimLanding,
  claimReused,
  claimInTheWay,
  forecastRequest,
  neverReused,
  viewOf,
} from "./assetWrites";
import { ASSET_KEYS } from "./assetsWords";
import { nothingOpen as nothingOpenWords } from "./planWords";

const NO_FIELDS = new Set<string>();
const NO_CLAIMS: readonly PlanClaim[] = [];
/**
 * Records a year's dotación in two steps: the forecast first, which works
 * out the span and records nothing, then the dotación itself. The year
 * starts on the year the register names for the element, or on the year of
 * the dotación being corrected, and the person can choose another of the
 * plan's years. The span starts from what the plan
 * says is still open, or from the dotación being replaced; its first and last
 * day can be changed, and the last day is sent as typed. The forecast the
 * backend serves is the one claimed, unchanged. A dotación that meets another is refused with the
 * backend's reason and offers to correct the one in the way; one sent again
 * for the same forecast is answered as already recorded. The landing is read
 * from the plan.
 */
export function ClaimFlow({
  port,
  reader,
  locale,
  assetId,
  taxYear,
  initialYear = null,
  supersedes = null,
  onCorrectElement,
  onClose,
  onWritten,
}: ActProps & {
  assetId: string;
  /** The year the page stands on, for an element whose plan has no year yet. */
  taxYear: number;
  /** The year to open on, where the person came from a year of the plan. */
  initialYear?: number | null;
  /** The dotación the new one replaces, in the same write. */
  supersedes?: string | null;
  /** Opens the form that corrects the element, where the plan says which
   * entry to fill in. */
  onCorrectElement?: () => void;
}) {
  const t = useStrings();
  const [replaces, setReplaces] = useState<string | null>(supersedes);
  const [chosenYear, setChosenYear] = useState<number | null>(initialYear);
  const [spanIndex, setSpanIndex] = useState(0);
  const asset = useAssetRow(port, reader, assetId);
  const plan = useLedgerRead(
    port,
    reader,
    "ledger.actividad-asset.plan",
    { asset_id: assetId },
    assetId,
  );
  const rows = plan.read?.kind === "done" ? plan.read.result.rows : null;
  const years = (rows ?? []).map((found) => found.tax_year);
  // The year the register opens a dotación on, else the page's year.
  const year = chosenYear ?? asset.row?.default_claim_year ?? taxYear;
  const row = rows?.find((found) => found.tax_year === year) ?? null;
  const effective = (row?.claims ?? NO_CLAIMS).filter(
    (claim) => claim.effective,
  );
  const replaced =
    effective.find((claim) => claim.claim_id === replaces) ?? null;
  const spans = claimSpans(row, replaced);
  const span = spans[spanIndex] ?? spans[0] ?? null;
  const fields = claimFields(row, replaced, span);
  // A year with no span open, and no dotación being replaced, has nothing to
  // record: the plan's own reason is said instead of blank dates.
  const nothingOpen =
    row !== null && spans.length === 0 ? nothingOpenWords(t, row) : null;
  const form = useFieldsDraft(draftOf(fields));
  const [forecast, setForecast] = useState<ActivityAssetForecast | null>(null);
  const [forecastCall, setForecastCall] =
    useState<SetupCall<ActivityAssetForecastResult> | null>(null);
  const [reading, setReading] = useState(false);
  const name = asset.row?.name ?? t(ASSET_KEYS.list.no_name);
  const write = useSetupWrite(facts(t, [t(ASSET_KEYS.action.claim), name]));
  useSetupDraft(form.dirty);
  const formRef = useRef<HTMLFormElement>(null);
  useFocusOnOpen(formRef, row !== null);

  const answered = answer(fields, form.draft, null);
  const request = forecastRequest(assetId, answered.values, replaces);
  const ready = Object.keys(answered.problems).length === 0 && request !== null;
  const forecastView = viewOf(forecastCall, neverReused);
  const wroteView = viewOf(write.last, claimReused);
  const [tried, setTried] = useState(false);
  const missing = new Set([
    ...(forecastView.kind === "refused" ? forecastView.missing : []),
    ...(tried
      ? fields
          .filter(
            (found) =>
              found.required && (answered.values[found.key] ?? null) === null,
          )
          .map((found) => found.key)
      : []),
  ]);

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
  // A different span, claim or year starts the dates over from that span as
  // the plan serves it, whatever was typed for the one before.
  const startOver = (
    nextRow: PlanRow | null,
    nextReplaces: string | null,
    index: number,
  ) => {
    const nextReplaced =
      (nextRow?.claims ?? NO_CLAIMS).find(
        (claim) => claim.effective && claim.claim_id === nextReplaces,
      ) ?? null;
    const first = claimSpans(nextRow, nextReplaced)[index] ?? null;
    form.set({
      covered_from: first?.from ?? "",
      covered_through: first?.through ?? "",
    });
  };

  // The recorded dotación in the way: the one the refusal names, when it
  // names exactly one that is still in effect.
  const inTheWayId = [forecastView, wroteView].flatMap((view) =>
    view.kind === "refused" &&
    view.code === CLAIM_CONFLICT &&
    view.reasonKey === CLAIMS_OVERLAP
      ? [claimInTheWay(view.reasonFacts)]
      : [],
  )[0];
  const inTheWay =
    effective.find((found) => found.claim_id === inTheWayId) ?? null;

  const preview = async () => {
    if (reading || write.busy) return;
    if (!ready || request === null) {
      setTried(true);
      return;
    }
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

  const chooseYear = (next: number) => {
    setChosenYear(next);
    setReplaces(null);
    setSpanIndex(0);
    startOver(rows?.find((found) => found.tax_year === next) ?? null, null, 0);
    changed();
  };

  const yearChoice = years.length > 1 && (
    <ChoiceField
      label={t(ASSET_KEYS.year)}
      value={String(year)}
      onValue={(value) => chooseYear(Number(value))}
      options={(rows ?? []).map((found) => ({
        value: String(found.tax_year),
        label:
          found.edition?.projected === true
            ? t(ASSET_KEYS.year_estimated, { year: found.tax_year })
            : String(found.tax_year),
      }))}
    />
  );

  const title = t(
    replaces === null
      ? "desktop.ledger.assets.claim_title"
      : "desktop.ledger.assets.correct_claim_title",
    { name, year },
  );

  const closeButton = onClose && (
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
  );

  return (
    <Panel title={title} className="ledger-asset-form ledger-asset-form-claim">
      {row === null ? (
        rows === null ? (
          <OptionsRead call={plan.read} />
        ) : (
          <div className="ledger-asset-no-plan flex flex-col gap-3">
            {yearChoice}
            <p role="status" className="text-sm">
              {t("desktop.ledger.assets.claim_no_plan", { year })}
            </p>
            {onClose && (
              <div className="flex gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={onClose}
                >
                  {t("desktop.ledger.form.close")}
                </Button>
              </div>
            )}
          </div>
        )
      ) : (
        <form
          ref={formRef}
          noValidate
          className="flex flex-col gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            void preview();
          }}
        >
          {nothingOpen !== null && (
            <Alert
              role="status"
              icon={<Icon name="info" />}
              className="ledger-asset-nothing-open"
            >
              <span className="flex flex-col gap-1">
                {nothingOpen.why}
                <Remedy
                  fieldKey={nothingOpen.remedyFieldKey}
                  onCorrect={onCorrectElement}
                />
              </span>
            </Alert>
          )}
          {yearChoice}
          {effective.length > 0 && (
            <ChoiceField
              label={t("desktop.ledger.assets.replace_claim")}
              value={replaces ?? ""}
              onValue={(value) => {
                setReplaces(value === "" ? null : value);
                setSpanIndex(0);
                startOver(row, value === "" ? null : value, 0);
                changed();
              }}
              options={[
                { value: "", label: t("desktop.ledger.assets.replace_none") },
                ...effective.map((found) => ({
                  value: found.claim_id,
                  label: t("desktop.ledger.assets.correct.claim_item", {
                    year,
                    amount: formatAmount(locale, found.amount.decimal),
                    from: formatDay(locale, found.covered_from),
                    until: formatDay(locale, throughOf(found)),
                  }),
                })),
              ]}
            />
          )}
          {spans.length > 1 && (
            <ChoiceField
              label={t("desktop.ledger.assets.claim_period")}
              value={String(spanIndex)}
              onValue={(value) => {
                setSpanIndex(Number(value));
                startOver(row, replaces, Number(value));
                changed();
              }}
              options={spans.map((found, index) => ({
                value: String(index),
                label: t("desktop.ledger.assets.claim_period_option", {
                  from: formatDay(locale, found.from),
                  until: formatDay(locale, found.through),
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
            {closeButton}
            <Button
              type="submit"
              size="sm"
              variant="outline"
              className="ledger-asset-forecast"
              aria-disabled={reading || write.busy || undefined}
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
                    amount: formatAmount(locale, forecast.amount.decimal),
                    days: forecast.service_days,
                    from: formatDay(locale, forecast.covered_from),
                    until: formatDay(locale, throughOf(forecast)),
                  })}
                </span>
                <span className="text-sm">
                  {t("desktop.ledger.assets.forecast_note")}
                </span>
                {rows?.find((found) => found.tax_year === forecast.tax_year)
                  ?.edition?.projected === true && (
                  <span className="inline-flex items-center gap-1.5 text-sm">
                    <Icon name="calendar" size="xs" />
                    {t(ASSET_KEYS.year_estimated_note)}
                  </span>
                )}
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
          {inTheWay !== null && (
            <div className="flex">
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="ledger-asset-correct-that"
                onClick={() => {
                  setReplaces(inTheWay.claim_id);
                  setSpanIndex(0);
                  startOver(row, inTheWay.claim_id, 0);
                  changed();
                }}
              >
                {t("desktop.ledger.assets.correct_that_claim")}
              </Button>
            </div>
          )}
        </form>
      )}
    </Panel>
  );
}
