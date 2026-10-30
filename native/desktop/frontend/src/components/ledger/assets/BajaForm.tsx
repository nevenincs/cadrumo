import { Alert } from "@/components/ui/alert";
import { Icon } from "@/components/ui/icon";
import { useStrings } from "../../../shell/strings";
import { AssetForm, type ActProps } from "./AssetForm";
import { ASSET_KEYS } from "./assetsWords";

/**
 * Takes an element out of service. The date is its last day of service and
 * the reasons are the backend's. The note says what the write does that a
 * reversal does not undo: claims that cross the date are replaced in the same
 * step.
 */
export function BajaForm(props: ActProps & { assetId: string }) {
  const t = useStrings();
  return (
    <AssetForm {...props} kind="baja">
      <Alert icon={<Icon name="info" />} className="ledger-asset-dispose-note">
        {t(ASSET_KEYS.write.dispose_note)}
      </Alert>
    </AssetForm>
  );
}
