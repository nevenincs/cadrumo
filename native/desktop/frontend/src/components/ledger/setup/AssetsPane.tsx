import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import type { JsonObject } from "../../../shell/ledger";
import {
  parseDecimal,
  parseIsoDate,
  QUARTER_CODES,
  TAX_AMOUNT_RULE,
  type Parsed,
} from "../../../shell/ledgerGrammar";
import type {
  ActivityAssetFilingResult,
  ActivityAssetForecast,
  ActivityAssetInspectResult,
  ActivityAssetRefusal,
  ActivityAssetRevision,
} from "../../../shell/ledgerSetup";
import { useStrings } from "../../../shell/strings";
import { WriteHold, type Landing } from "../WritePause";
import { amountText, dateText } from "../movements/movementWords";
import { JsonDocumentField } from "./InventoryPane";
import {
  CallLine,
  ChoiceField,
  FormGrid,
  Panel,
  rankDecimal,
  SetupTable,
  TextField,
  useSetupDraft,
  READ_ONLY,
  useSetupWrite,
} from "./SetupParts";
import type { SetupProps } from "./setupProps";
import {
  correctionOf,
  parseObject,
  revisionSkeleton,
  setupCall,
  wholeYear,
  type SetupCall,
} from "./setupModel";
import { grammarText } from "./setupWords";

type Task = "create" | "correct" | "forecast" | "filing";

const pretty = (value: JsonObject) => JSON.stringify(value, null, 2);

/**
 * The activity's depreciable assets: each a chain of revisions that are
 * never edited, a correction being a new revision that supersedes the
 * last. A forecast works out a span's amortización and records nothing; a
 * claim records it; the filing handoff says which declaration boxes the
 * claims of a year reach.
 */
export function AssetsPane({ port, locale }: SetupProps) {
  const t = useStrings();
  const write = useSetupWrite(t("desktop.ledger.assets.title"));
  const [assetId, setAssetId] = useState("");
  const [inspected, setInspected] =
    useState<SetupCall<ActivityAssetInspectResult> | null>(null);
  const [task, setTask] = useState<Task | null>(null);
  const [revision, setRevision] = useState("");
  const [from, setFrom] = useState("");
  const [until, setUntil] = useState("");
  const [free, setFree] = useState("");
  const [forecast, setForecast] = useState<ActivityAssetForecast | null>(null);
  const [creatingOperation, setCreatingOperation] = useState("");
  const [taxYear, setTaxYear] = useState("");
  const [quarter, setQuarter] = useState("");
  const [handoff, setHandoff] = useState<ActivityAssetFilingResult | null>(
    null,
  );
  // A form with anything typed into it that is not yet written.
  useSetupDraft(
    task !== null &&
      [from, until, free, creatingOperation, taxYear, quarter].some(Boolean),
  );

  const inspect = async (id = assetId) => {
    setInspected(
      await setupCall(
        port,
        "ledger.actividad-asset.inspect",
        { asset_id: id.trim() },
        false,
      ),
    );
  };
  /** How a create or correction landed: the asset read again holds a
   * revision of that number, which revisions are never edited. */
  const revisionLanding =
    (revision: ActivityAssetRevision) => async (): Promise<Landing | null> => {
      if (typeof revision.asset_id !== "string" || revision.asset_id === "")
        return "untold";
      const read = await setupCall(
        port,
        "ledger.actividad-asset.inspect",
        { asset_id: revision.asset_id },
        false,
      );
      if (read.kind === "refused") return "not_saved";
      if (read.kind !== "done") return null;
      return (read.result.revisions ?? []).some(
        (found) => found.revision.revision_number === revision.revision_number,
      )
        ? "saved"
        : "not_saved";
    };
  const revisions =
    inspected?.kind === "done" ? (inspected.result.revisions ?? []) : [];
  const latest = revisions.at(-1);
  const start = (next: Task) => {
    write.clear();
    setTask(task === next ? null : next);
    setForecast(null);
    setHandoff(null);
    if (next === "create") setRevision(pretty(revisionSkeleton()));
    if (next === "correct" && latest)
      setRevision(pretty(correctionOf(latest.revision, latest.revision_id)));
  };
  const document = parseObject(revision);
  const fromDay = parseIsoDate(from);
  const untilDay = parseIsoDate(until);
  const freeAmount = parseDecimal(free, TAX_AMOUNT_RULE);
  const year = wholeYear(taxYear);
  const problem = (parsed: Parsed<unknown>) =>
    parsed.kind === "refused" ? grammarText(t, parsed.refusal) : null;

  const ready =
    task === "create" || task === "correct"
      ? document.kind === "value"
      : task === "forecast"
        ? assetId.trim() !== "" &&
          fromDay.kind === "value" &&
          untilDay.kind === "value" &&
          freeAmount.kind !== "refused"
        : task === "filing"
          ? year !== null && quarter !== ""
          : false;

  const send = async () => {
    if (!ready || !task) return;
    if (task === "create" || task === "correct") {
      if (document.kind !== "value") return;
      const done = await write.run(
        () =>
          setupCall(
            port,
            task === "create"
              ? "ledger.actividad-asset.create"
              : "ledger.actividad-asset.correct",
            { revision: document.value as ActivityAssetRevision },
            true,
          ),
        revisionLanding(document.value as ActivityAssetRevision),
      );
      if (done.kind === "done") {
        setTask(null);
        const id =
          typeof document.value.asset_id === "string"
            ? document.value.asset_id
            : assetId;
        setAssetId(id);
        void inspect(id);
      }
      return;
    }
    if (task === "forecast") {
      const done = await write.run(
        () =>
          setupCall(
            port,
            "ledger.actividad-asset.forecast",
            {
              asset_id: assetId.trim(),
              covered_from: fromDay.kind === "value" ? fromDay.value : "",
              covered_until: untilDay.kind === "value" ? untilDay.value : "",
              requested_free_amount:
                freeAmount.kind === "value"
                  ? { decimal: freeAmount.value }
                  : null,
            },
            false,
          ),
        READ_ONLY,
      );
      if (done.kind === "done") setForecast(done.result.forecast);
      return;
    }
    const done = await write.run(
      () =>
        setupCall(
          port,
          "ledger.actividad-asset.filing-handoff",
          { tax_year: year!, m130_period: quarter },
          false,
        ),
      READ_ONLY,
    );
    if (done.kind === "done") setHandoff(done.result);
  };
  const claim = async () => {
    if (!forecast || !creatingOperation.trim()) return;
    await write.run(
      () =>
        setupCall(
          port,
          "ledger.actividad-asset.claim",
          { forecast, creating_operation: creatingOperation.trim() },
          true,
        ),
      // No read lists an asset's claims; a claim sent again for the same
      // forecast reuses the claim it made (`reused_existing_claim`).
      async () => "repeatable",
    );
  };
  const refusal = () => {
    const last = write.last?.kind === "refused" ? write.last : inspected;
    if (last?.kind !== "refused") return null;
    const found = (
      last.detail as { refusal?: ActivityAssetRefusal | null } | null
    )?.refusal;
    return found
      ? t(`desktop.ledger.assets.refusal.${found.code.toLowerCase()}`)
      : null;
  };
  const claimed =
    write.last?.kind === "done" &&
    (write.last.result as { claim_id?: string | null } | null)?.claim_id
      ? (write.last.result as {
          claim_result?: { reused_existing_claim: boolean } | null;
        })
      : null;

  return (
    <Panel title={t("desktop.ledger.assets.title")}>
      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          if (assetId.trim()) void inspect();
        }}
      >
        <TextField
          label={t("desktop.ledger.assets.asset_id")}
          value={assetId}
          onValue={setAssetId}
          mono
          maxLength={128}
          className="w-64"
        />
        <Button
          type="submit"
          size="sm"
          variant="outline"
          className="ledger-assets-inspect"
          aria-disabled={!assetId.trim() || undefined}
        >
          {t("desktop.ledger.assets.inspect")}
        </Button>
      </form>
      {revisions.length > 0 && (
        <SetupTable
          label={t("desktop.ledger.assets.revisions")}
          rows={revisions}
          rowKey={(found) => found.revision_id}
          columns={[
            {
              key: "number",
              label: t("desktop.ledger.assets.column.number"),
              numeric: true,
              sort: (found) => found.revision.revision_number,
              cell: (found) => found.revision.revision_number,
            },
            {
              key: "service",
              label: t("desktop.ledger.assets.column.in_service"),
              sort: (found) =>
                typeof found.revision.in_service_date === "string"
                  ? found.revision.in_service_date
                  : null,
              cell: (found) =>
                typeof found.revision.in_service_date === "string"
                  ? dateText(locale, found.revision.in_service_date, true)
                  : "—",
            },
            {
              key: "id",
              label: t("desktop.ledger.assets.column.revision"),
              sort: (found) => found.revision_id,
              cell: (found) => (
                <code className="font-mono text-xs">
                  {found.revision_id.slice(0, 12)}
                </code>
              ),
            },
          ]}
          className="ledger-assets-revisions"
        />
      )}
      <div className="flex flex-wrap gap-1">
        {(["create", "correct", "forecast", "filing"] as const).map((value) => {
          const held = value === "correct" && !latest;
          return (
            <Button
              key={value}
              size="xs"
              variant={task === value ? "secondary" : "outline"}
              aria-pressed={task === value}
              aria-disabled={held || undefined}
              className={`ledger-assets-${value}`}
              onClick={() => !held && start(value)}
            >
              {t(`desktop.ledger.assets.task.${value}`)}
            </Button>
          );
        })}
      </div>
      {task && (
        <form
          className="ledger-assets-form flex flex-col gap-3 rounded-md bg-accent p-3"
          onSubmit={(event) => {
            event.preventDefault();
            if (!write.busy) void send();
          }}
        >
          {(task === "create" || task === "correct") && (
            <JsonDocumentField
              label={t(`desktop.ledger.assets.revision.${task}`)}
              value={revision}
              onValue={setRevision}
              hint={t("desktop.ledger.assets.revision_hint")}
              error={
                document.kind === "refused"
                  ? t("desktop.ledger.inventory.authority_unread")
                  : null
              }
            />
          )}
          {task === "forecast" && (
            <FormGrid>
              <TextField
                label={t("desktop.ledger.assets.from")}
                value={from}
                onValue={setFrom}
                hint={t("desktop.ledger.form.date_hint")}
                error={problem(fromDay)}
                required
              />
              <TextField
                label={t("desktop.ledger.assets.until")}
                value={until}
                onValue={setUntil}
                hint={t("desktop.ledger.form.date_hint")}
                error={problem(untilDay)}
                required
              />
              <TextField
                label={t("desktop.ledger.assets.free")}
                value={free}
                onValue={setFree}
                inputMode="decimal"
                hint={t("desktop.ledger.assets.free_hint")}
                error={problem(freeAmount)}
              />
            </FormGrid>
          )}
          {task === "filing" && (
            <FormGrid>
              <TextField
                label={t("desktop.ledger.assets.tax_year")}
                value={taxYear}
                onValue={setTaxYear}
                inputMode="numeric"
                hint={t("desktop.ledger.form.year_hint")}
                required
              />
              <ChoiceField
                label={t("desktop.ledger.assets.quarter")}
                value={quarter}
                onValue={setQuarter}
                placeholder={t("desktop.ledger.form.choose")}
                options={QUARTER_CODES.map((code) => ({
                  value: code,
                  label: code,
                }))}
              />
            </FormGrid>
          )}
          <div className="flex gap-2">
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => setTask(null)}
            >
              {t("desktop.ledger.form.cancel")}
            </Button>
            <WriteHold when={task === "create" || task === "correct"}>
              <Button
                type="submit"
                size="sm"
                className="ledger-assets-submit"
                aria-disabled={!ready || write.busy || undefined}
              >
                {write.busy
                  ? t("desktop.ledger.form.saving")
                  : t(`desktop.ledger.assets.submit.${task}`)}
              </Button>
            </WriteHold>
          </div>
        </form>
      )}
      {forecast && (
        <div className="ledger-assets-forecast flex flex-col gap-2">
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
          <div className="flex flex-wrap items-end gap-2">
            <TextField
              label={t("desktop.ledger.assets.creating_operation")}
              value={creatingOperation}
              onValue={setCreatingOperation}
              hint={t("desktop.ledger.assets.creating_hint")}
              maxLength={256}
              className="w-72"
            />
            <WriteHold>
              <Button
                size="sm"
                className="ledger-assets-claim"
                aria-disabled={
                  !creatingOperation.trim() || write.busy || undefined
                }
                onClick={() => void claim()}
              >
                {t("desktop.ledger.assets.claim")}
              </Button>
            </WriteHold>
          </div>
        </div>
      )}
      {claimed && (
        <Alert tone="success" icon={<Icon name="check" />}>
          {claimed.claim_result?.reused_existing_claim
            ? t("desktop.ledger.assets.claim_reused")
            : t("desktop.ledger.assets.claimed")}
        </Alert>
      )}
      {handoff?.filing_handoff && (
        <SetupTable
          label={t("desktop.ledger.assets.handoff")}
          rows={(
            [
              "material_m100",
              "intangible_m100",
              "material_m130",
              "intangible_m130",
            ] as const
          ).map((key) => ({ key, found: handoff.filing_handoff![key] }))}
          rowKey={(row) => row.key}
          columns={[
            {
              key: "target",
              label: t("desktop.ledger.assets.column.target"),
              sort: (row) => t(`desktop.ledger.assets.target.${row.key}`),
              cell: (row) => t(`desktop.ledger.assets.target.${row.key}`),
            },
            {
              key: "casilla",
              label: t("desktop.ledger.assets.column.casilla"),
              sort: (row) => row.found.target_casilla_id,
              cell: (row) => row.found.target_casilla_id,
            },
            {
              key: "amount",
              label: t("desktop.ledger.assets.column.amount"),
              numeric: true,
              sort: (row) => rankDecimal(row.found.amount.decimal),
              cell: (row) => amountText(locale, row.found.amount.decimal),
            },
            {
              key: "claims",
              label: t("desktop.ledger.assets.column.claims"),
              numeric: true,
              sort: (row) => row.found.claim_ids.length,
              cell: (row) => row.found.claim_ids.length,
            },
          ]}
          className="ledger-assets-handoff"
        />
      )}
      <CallLine call={write.last} refusal={refusal} />
      <CallLine call={inspected} refusal={refusal} />
    </Panel>
  );
}
