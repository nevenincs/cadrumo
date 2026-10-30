import { AssetForm, type ActProps } from "./AssetForm";
import { DisposalFigures } from "./DisposalFigures";

/**
 * Takes an element out of service on its last day of service. The form states
 * the baja as the backend takes it; the backend judges the reason and the
 * amounts and says by key why it refuses one, a donation among them. The
 * figures preview asks the backend what the baja would come to and writes
 * nothing.
 */
export function BajaForm(props: ActProps & { assetId: string }) {
  return (
    <AssetForm {...props} kind="baja">
      {({ values, ready }) => (
        <DisposalFigures
          port={props.port}
          reader={props.reader}
          locale={props.locale}
          assetId={props.assetId}
          values={values}
          ready={ready}
        />
      )}
    </AssetForm>
  );
}
