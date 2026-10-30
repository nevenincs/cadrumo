import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Icon } from "@/components/ui/icon";
import type { LedgerPort } from "../../../shell/ledger";
import { QUARTER_CODES } from "../../../shell/ledgerGrammar";
import { useStrings } from "../../../shell/strings";
import { amountText } from "../movements/movementWords";
import {
  CallLine,
  ChoiceField,
  Panel,
  Reading,
  SetupTable,
  useSetupRead,
} from "../setup/SetupParts";
import { callRefusal, Hint } from "./AssetList";
import { ASSET_KEYS, refusalText } from "./assetsWords";

/** The words of the declaration boxes the handoff can name. A box outside
 * this list reads as the generic word, never as the key the backend uses. */
const TARGET_KEYS: Readonly<Record<string, string>> = {
  material_m100: "desktop.ledger.assets.target.material_m100",
  intangible_m100: "desktop.ledger.assets.target.intangible_m100",
  material_m130: "desktop.ledger.assets.target.material_m130",
  intangible_m130: "desktop.ledger.assets.target.intangible_m130",
};

/**
 * Which declaration boxes the claims of a year reach, read only. The year
 * is the pane's; the Modelo 130 quarter is chosen here, and nothing is read
 * until it is. Each row shows the box and the amount the backend states for
 * it. Nothing is added up or worked out here, and an amount the backend does
 * not state is not drawn as zero.
 */
export function FilingHandoffPanel({
  port,
  reader,
  locale,
  year,
}: {
  port: LedgerPort;
  reader: string | null;
  locale: string;
  year: number | null;
}) {
  const t = useStrings();
  const [open, setOpen] = useState(false);
  const [period, setPeriod] = useState("");
  const asked =
    open && reader !== null && year !== null && period !== ""
      ? { tax_year: year, m130_period: period }
      : null;
  const { read } = useSetupRead(
    port,
    reader,
    "ledger.actividad-asset.filing-handoff",
    asked,
    asked ? `${asked.tax_year}:${asked.m130_period}` : "none",
  );

  const note = (key: string) => (
    <p className="text-sm text-muted-foreground">{t(key)}</p>
  );
  const body = () => {
    if (reader === null)
      return note("desktop.ledger.assets.filing.unavailable");
    if (asked === null) return note("desktop.ledger.assets.filing.choose");
    if (read === null) return <Reading label={t("desktop.ledger.loading")} />;
    if (read.kind !== "done")
      return <CallLine call={read} refusal={callRefusal(t, read)} />;
    const { outcome, refusal, filing_handoff: handoff } = read.result;
    if (outcome === "refused")
      return (
        <Alert
          tone="danger"
          role="alert"
          icon={<Icon name="refused" />}
          className="ledger-assets-handoff-refused"
        >
          {refusalText(t, refusal)}
        </Alert>
      );
    if (handoff === null)
      return note("desktop.ledger.assets.filing.unavailable");
    return (
      <SetupTable
        label={t("desktop.ledger.assets.handoff")}
        rows={Object.entries(handoff)}
        rowKey={([target]) => target}
        columns={[
          {
            key: "target",
            label: t("desktop.ledger.assets.column.target"),
            cell: ([target]) =>
              Object.hasOwn(TARGET_KEYS, target)
                ? t(TARGET_KEYS[target]!)
                : t(ASSET_KEYS.unrecognised),
          },
          {
            key: "casilla",
            label: t("desktop.ledger.assets.column.casilla"),
            cell: ([, found]) => found.target_casilla_id,
          },
          {
            key: "amount",
            label: t("desktop.ledger.assets.column.amount"),
            numeric: true,
            // An amount that leaves elements out is marked partial on the
            // amount itself.
            cell: ([, found]) => {
              const left =
                "unavailable_asset_ids" in found
                  ? found.unavailable_asset_ids.length
                  : 0;
              return (
                <span className="inline-flex items-center justify-end gap-1.5 whitespace-nowrap">
                  {left > 0 && (
                    <Hint
                      words={t(ASSET_KEYS.handoff.partial, { count: left })}
                      className="bg-secondary px-2 py-0.5 text-xs font-medium"
                    >
                      <Icon name="alert" size="xs" className="text-warning" />
                      <span aria-hidden="true">{left}</span>
                    </Hint>
                  )}
                  {amountText(locale, found.amount.decimal)}
                </span>
              );
            },
          },
        ]}
        className="ledger-assets-handoff"
      />
    );
  };

  return (
    <Panel
      title={t("desktop.ledger.assets.handoff")}
      open={open}
      onOpen={setOpen}
      className="ledger-assets-handoff-panel"
    >
      <ChoiceField
        label={t("desktop.ledger.assets.quarter")}
        value={period}
        onValue={setPeriod}
        placeholder={t("desktop.ledger.form.choose")}
        options={QUARTER_CODES.map((code) => ({ value: code, label: code }))}
        className="max-w-48"
      />
      {body()}
    </Panel>
  );
}
