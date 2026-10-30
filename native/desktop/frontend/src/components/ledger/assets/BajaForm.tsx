import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Icon } from "@/components/ui/icon";
import { useStrings } from "../../../shell/strings";
import { Reading } from "../setup/SetupParts";
import {
  AssetForm,
  useAssetRow,
  type ActKind,
  type ActProps,
} from "./AssetForm";
import { DisposalFigures } from "./DisposalFigures";

/**
 * Takes an element out of service on its last day of service, or, where the
 * element already has a baja, changes it or removes it. The form states the
 * baja as the backend takes it; the backend judges the reason and the
 * amounts and says by key why it refuses one. Nothing is sent before the
 * person confirms. The figures preview asks the backend what the baja would
 * come to and writes nothing. The way the form was opened is kept through
 * the write, so what it says of the outcome stays in view.
 */
export function BajaForm(props: ActProps & { assetId: string }) {
  const t = useStrings();
  const { row } = useAssetRow(props.port, props.reader, props.assetId);
  const [mode, setMode] = useState<ActKind | null>(null);
  if (mode === null && row !== null)
    setMode(row.disposal === null ? "baja" : "baja_change");
  if (mode === null)
    return <Reading label={t("desktop.ledger.form.reading")} />;
  return (
    <AssetForm {...props} kind={mode}>
      {({ values, ready }) => (
        <>
          <Alert
            tone="warning"
            icon={<Icon name="alert" />}
            className="ledger-asset-baja-warning"
          >
            {t(
              mode === "baja"
                ? "desktop.ledger.assets.baja.warning"
                : "desktop.ledger.assets.baja.warning_change",
            )}
          </Alert>
          <DisposalFigures
            port={props.port}
            reader={props.reader}
            locale={props.locale}
            assetId={props.assetId}
            values={values}
            ready={ready}
          />
        </>
      )}
    </AssetForm>
  );
}
