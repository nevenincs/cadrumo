import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Icon } from "@/components/ui/icon";
import type { LedgerPort, PublicDecimal } from "../../../shell/ledger";
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
import { handoffRequest } from "./assetWrites";
import { leftOutNotes } from "./handoffWords";
import { ASSET_KEYS, countSentence, refusalText } from "./assetsWords";

/** One box the handoff states: its casilla, its amount, and how many
 * elements its amount leaves out. */
type Stated = {
  casilla: string;
  amount: PublicDecimal;
  left: number;
};

/**
 * Which declaration boxes the claims of a year reach, read only. The year
 * is the pane's, and it alone reads the Modelo 100 boxes; the Modelo 130
 * quarter is chosen here from the quarters the registry serves for that
 * year, and only a chosen quarter is sent and adds the Modelo 130 rows. Each
 * row shows the box by its casilla and the amount the backend states for it.
 * Nothing is added up or worked out here, and an amount the backend does not
 * state is not drawn as zero.
 */
export function FilingHandoffPanel({
  port,
  reader,
  locale,
  year,
  assetKind,
  names,
}: {
  port: LedgerPort;
  reader: string | null;
  locale: string;
  year: number | null;
  /** The kind of any element the register lists, which the registry's
   * options for the year are read under; null while there is none. */
  assetKind: string | null;
  /** The elements' names by their ids, from the list the pane holds; an
   * element without a name is absent. */
  names: ReadonlyMap<string, string>;
}) {
  const t = useStrings();
  const [open, setOpen] = useState(false);
  const [typedPeriod, setPeriod] = useState("");
  // The quarters the registry serves for the year; a quarter chosen for
  // another year is not asked of this one.
  const options = useSetupRead(
    port,
    reader,
    "ledger.actividad-asset.form-options",
    open && year !== null && assetKind !== null
      ? { asset_kind: assetKind, tax_year: year }
      : null,
    open ? `${assetKind ?? ""}:${year ?? ""}` : "closed",
  );
  const periods =
    options.read?.kind === "done"
      ? (options.read.result.options?.m130_periods ?? [])
      : [];
  const period = periods.includes(typedPeriod) ? typedPeriod : "";
  const asked =
    open && reader !== null && year !== null
      ? handoffRequest(year, period)
      : null;
  const { read } = useSetupRead(
    port,
    reader,
    "ledger.actividad-asset.filing-handoff",
    asked,
    asked ? `${asked.tax_year}:${asked.m130_period ?? ""}` : "none",
  );

  const note = (key: string) => (
    <p className="text-sm text-muted-foreground">{t(key)}</p>
  );
  const body = () => {
    if (reader === null)
      return note("desktop.ledger.assets.filing.unavailable");
    if (asked === null) return note("desktop.ledger.assets.filing.choose_year");
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
    // A box the backend does not state, because no quarter was asked, is not
    // drawn: it is not unknown, and it is not zero.
    const stated: Stated[] = [
      ...[handoff.material_m100, handoff.intangible_m100].map((found) => ({
        casilla: found.target_casilla_id,
        amount: found.amount,
        left: 0,
      })),
      ...[handoff.material_m130, handoff.intangible_m130].flatMap((found) =>
        found === null
          ? []
          : [
              {
                casilla: found.target_casilla_id,
                amount: found.amount,
                left: found.unavailable_asset_ids.length,
              },
            ],
      ),
    ];
    const left = leftOutNotes(t, locale, handoff, names);
    return (
      <>
        <SetupTable
          label={t("desktop.ledger.assets.handoff")}
          rows={stated}
          rowKey={(found) => String(stated.indexOf(found))}
          columns={[
            {
              key: "casilla",
              label: t("desktop.ledger.assets.column.casilla"),
              cell: (found) => found.casilla,
            },
            {
              key: "amount",
              label: t("desktop.ledger.assets.column.amount"),
              numeric: true,
              // An amount that leaves elements out is marked partial on the
              // amount itself.
              cell: (found) => {
                const left = found.left;
                return (
                  <span className="inline-flex items-center justify-end gap-1.5 whitespace-nowrap">
                    {left > 0 && (
                      <Hint
                        words={countSentence(
                          t,
                          ASSET_KEYS.handoff.partial,
                          left,
                        )}
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
        {left.length > 0 && (
          <section
            aria-label={t("desktop.ledger.assets.handoff_left_out")}
            className="ledger-assets-handoff-left-out flex flex-col gap-1.5"
          >
            <h4 className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
              <Icon name="info" size="xs" />
              {t("desktop.ledger.assets.handoff_left_out")}
            </h4>
            <ul className="flex flex-col gap-1.5">
              {left.map((words) => (
                <li key={words} className="text-sm text-foreground">
                  {words}
                </li>
              ))}
            </ul>
          </section>
        )}
      </>
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
        options={[
          { value: "", label: t("desktop.ledger.assets.quarter_none") },
          ...periods.map((code) => ({ value: code, label: code })),
        ]}
        className="max-w-48"
      />
      {body()}
    </Panel>
  );
}
