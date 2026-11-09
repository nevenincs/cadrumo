import { useState } from "react";
import { Button } from "@/components/ui/button";
import type { LedgerCounterpartyResult } from "../../../shell/ledgerClassificationSetup";
import { useStrings } from "../../../shell/strings";
import { WriteHold, type Landing } from "../WritePause";
import { CallLine, ChoiceField, useSetupWrite } from "./SetupParts";
import type { SetupProps } from "./setupProps";
import { setupCall } from "./setupModel";

/**
 * The province of a counterparty's domicilio fiscal, stated once for it and
 * declared by Modelo 347 on every record of that counterparty. The provinces
 * and their names are the ones the backend serves; nothing is listed here.
 */
export function CounterpartyProvincia({
  port,
  result,
  country,
  actor,
  onSaved,
}: Pick<SetupProps, "port"> & {
  result: LedgerCounterpartyResult;
  country: string;
  /** Who states it, as typed for the counterparty's other answers. */
  actor: string;
  onSaved(): Promise<void> | void;
}) {
  const t = useStrings();
  const write = useSetupWrite(t("desktop.ledger.counterparty.provincia"));
  const stated = result.provincia_code;
  const [picked, setPicked] = useState(stated ?? "");
  const choices = result.provincia_choices;
  const statedName = choices.find((choice) => choice.code === stated)?.name;
  const canSave =
    picked !== "" && picked !== stated && actor.trim() !== "" && !write.busy;
  // A view re-reads the stored provincia, so an uncertain write is told by it.
  const untold = async (): Promise<Landing> => "untold";

  const save = async () => {
    if (!canSave) return;
    const done = await write.run(
      () =>
        setupCall(
          port,
          "ledger.counterparty",
          {
            action: "provincia",
            tax_identifier: result.tax_identifier,
            country_code: country || null,
            provincia_code: picked,
            asserted_by: actor.trim(),
          },
          true,
        ),
      untold,
    );
    if (done.kind === "done") await onSaved();
  };

  if (choices.length === 0) return null;
  return (
    <div className="ledger-counterparty-provincia flex flex-wrap items-end gap-2">
      <ChoiceField
        className="w-64"
        label={t("desktop.ledger.counterparty.provincia")}
        hint={statedName ?? t("desktop.ledger.counterparty.provincia_unstated")}
        value={picked}
        onValue={setPicked}
        placeholder={t("desktop.ledger.form.choose")}
        options={choices.map((choice) => ({
          value: choice.code,
          label: choice.name,
        }))}
      />
      <WriteHold>
        <Button
          size="sm"
          variant="outline"
          className="ledger-counterparty-provincia-save"
          aria-disabled={!canSave || undefined}
          onClick={() => canSave && void save()}
        >
          {t("desktop.ledger.counterparty.provincia_save")}
        </Button>
      </WriteHold>
      <CallLine call={write.last} onReread={() => void onSaved()} />
    </div>
  );
}
