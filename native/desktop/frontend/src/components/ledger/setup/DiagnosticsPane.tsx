import { useState } from "react";
import { DateEditor } from "@/components/editors/DateEditor";
import { PercentEditor } from "@/components/editors/PercentEditor";
import { Button } from "@/components/ui/button";
import {
  parseFractionPercent,
  parseIsoDate,
} from "../../../shell/ledgerGrammar";
import type { LedgerLlmDiagnosticsResult } from "../../../shell/ledgerSetup";
import { useStrings } from "../../../shell/strings";
import {
  formatAmount,
  formatCount,
  formatPercent,
} from "../../../shared/numbers";
import {
  CallLine,
  FormGrid,
  Panel,
  rankDecimal,
  SetupTable,
} from "./SetupParts";
import { EditorField } from "./EditorField";
import type { SetupProps } from "./setupProps";
import { setupCall, type SetupCall } from "./setupModel";
import { grammarText } from "./setupWords";

type Provider =
  LedgerLlmDiagnosticsResult["report"]["confidence_providers"][number];
type Usage = LedgerLlmDiagnosticsResult["report"]["usage_providers"][number];

/**
 * How the model has done over a span: how often it was asked, what it
 * cost, and how sure it was, with what counts as low confidence chosen by
 * the person. A read: nothing changes.
 */
export function DiagnosticsPane({ port, locale }: SetupProps) {
  const t = useStrings();
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");
  const [threshold, setThreshold] = useState("");
  const [report, setReport] =
    useState<SetupCall<LedgerLlmDiagnosticsResult> | null>(null);
  const [reading, setReading] = useState(false);
  const from = parseIsoDate(since);
  const to = parseIsoDate(until);
  const low = parseFractionPercent(threshold);
  const fieldError = (parsed: ReturnType<typeof parseIsoDate>) =>
    parsed.kind === "refused" ? grammarText(t, parsed.refusal) : null;
  const ready =
    from.kind !== "refused" && to.kind !== "refused" && low.kind === "value";

  const read = async () => {
    if (!ready || low.kind !== "value") return;
    setReading(true);
    setReport(
      await setupCall(
        port,
        "ledger.llm-diagnostics",
        {
          since: from.kind === "value" ? from.value : null,
          until: to.kind === "value" ? to.value : null,
          low_confidence_threshold: { decimal: low.value },
        },
        false,
      ),
    );
    setReading(false);
  };
  const found = report?.kind === "done" ? report.result.report : null;
  const decimalPercent = (value: { decimal: string } | null) =>
    value ? formatPercent(locale, value.decimal, { unit: "fraction" }) : "—";
  return (
    <Panel title={t("desktop.ledger.diagnostics.title")}>
      <FormGrid>
        <EditorField
          label={t("desktop.ledger.diagnostics.since")}
          error={fieldError(from)}
        >
          {(control) => (
            <DateEditor
              id={control.id}
              value={since}
              onChange={setSince}
              invalid={control.invalid}
              describedBy={control.describedBy}
            />
          )}
        </EditorField>
        <EditorField
          label={t("desktop.ledger.diagnostics.until")}
          error={fieldError(to)}
        >
          {(control) => (
            <DateEditor
              id={control.id}
              value={until}
              onChange={setUntil}
              invalid={control.invalid}
              describedBy={control.describedBy}
            />
          )}
        </EditorField>
        <EditorField
          label={t("desktop.ledger.diagnostics.threshold")}
          error={low.kind === "refused" ? grammarText(t, low.refusal) : null}
        >
          {(control) => (
            <PercentEditor
              id={control.id}
              unit="fraction"
              value={threshold}
              onChange={setThreshold}
              invalid={control.invalid}
              describedBy={control.describedBy}
              required
            />
          )}
        </EditorField>
      </FormGrid>
      <div>
        <Button
          size="sm"
          variant="outline"
          className="ledger-diagnostics-read"
          aria-disabled={!ready || reading || undefined}
          onClick={() => ready && !reading && void read()}
        >
          {reading
            ? t("desktop.ledger.form.reading")
            : t("desktop.ledger.diagnostics.read")}
        </Button>
      </div>
      <CallLine call={report} />
      {found && (
        <div className="ledger-diagnostics-report flex flex-col gap-3">
          <dl className="grid max-w-md grid-cols-[1fr_auto] gap-x-4 gap-y-1 text-sm">
            <dt>{t("desktop.ledger.diagnostics.calls")}</dt>
            <dd className="text-right tabular-nums">
              {formatCount(locale, found.total_calls)}
            </dd>
            <dt>{t("desktop.ledger.diagnostics.classified")}</dt>
            <dd className="text-right tabular-nums">
              {formatCount(locale, found.total_classified)}
            </dd>
            <dt>{t("desktop.ledger.diagnostics.low")}</dt>
            <dd className="text-right tabular-nums">
              {formatCount(locale, found.total_low_confidence)}
            </dd>
            <dt>{t("desktop.ledger.diagnostics.cost")}</dt>
            <dd className="text-right tabular-nums">
              {found.total_cost_estimate_usd
                ? formatAmount(locale, found.total_cost_estimate_usd.decimal, {
                    currency: "USD",
                  })
                : t("desktop.ledger.diagnostics.unpriced", {
                    count: found.total_unpriced_calls,
                  })}
            </dd>
          </dl>
          <SetupTable<Provider>
            label={t("desktop.ledger.diagnostics.confidence")}
            rows={found.confidence_providers}
            rowKey={(row) => row.provider}
            columns={[
              {
                key: "provider",
                label: t("desktop.ledger.diagnostics.provider"),
                sort: (row) => row.provider,
                cell: (row) => (
                  <code className="font-mono">{row.provider}</code>
                ),
              },
              {
                key: "classified",
                label: t("desktop.ledger.diagnostics.classified"),
                numeric: true,
                sort: (row) => row.classified_count,
                cell: (row) => formatCount(locale, row.classified_count),
              },
              {
                key: "low",
                label: t("desktop.ledger.diagnostics.low"),
                numeric: true,
                sort: (row) => row.low_confidence_count,
                cell: (row) => formatCount(locale, row.low_confidence_count),
              },
              {
                key: "mean",
                label: t("desktop.ledger.diagnostics.mean"),
                numeric: true,
                sort: (row) => rankDecimal(row.mean_confidence?.decimal),
                cell: (row) => decimalPercent(row.mean_confidence),
              },
            ]}
          />
          <SetupTable<Usage>
            label={t("desktop.ledger.diagnostics.usage")}
            rows={found.usage_providers}
            rowKey={(row) => row.provider}
            columns={[
              {
                key: "provider",
                label: t("desktop.ledger.diagnostics.provider"),
                sort: (row) => row.provider,
                cell: (row) => (
                  <code className="font-mono">{row.provider}</code>
                ),
              },
              {
                key: "calls",
                label: t("desktop.ledger.diagnostics.calls"),
                numeric: true,
                sort: (row) => row.calls,
                cell: (row) => formatCount(locale, row.calls),
              },
              {
                key: "tokens",
                label: t("desktop.ledger.diagnostics.tokens"),
                numeric: true,
                sort: (row) => row.total_tokens,
                cell: (row) => formatCount(locale, row.total_tokens),
              },
            ]}
          />
        </div>
      )}
    </Panel>
  );
}
