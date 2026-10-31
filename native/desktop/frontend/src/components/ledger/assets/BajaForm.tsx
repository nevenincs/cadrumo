import { useEffect, useRef, useState } from "react";
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

/** Lines that say how a send ended. */
const OUTCOMES =
  ".ledger-asset-saved, .ledger-asset-refused, .ledger-asset-incomplete";

/** Brings what a baja came to into view at the top of the slot: the figures
 * and the line under them that says how the send ended. The form is long
 * and its outcome sits at its foot, below where the person is reading. */
function OutcomeInView() {
  const anchor = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const form = anchor.current?.closest("form");
    if (!form) return;
    const shown = new Set<Element>();
    const look = () => {
      const outcome = form.querySelector(OUTCOMES);
      if (outcome === null) {
        shown.clear();
        return;
      }
      if (shown.has(outcome)) return;
      shown.clear();
      shown.add(outcome);
      (form.querySelector(".ledger-asset-figures") ?? outcome).scrollIntoView?.(
        { block: "start" },
      );
    };
    const watch = new MutationObserver(look);
    watch.observe(form, { childList: true, subtree: true });
    look();
    return () => watch.disconnect();
  }, []);
  return <span ref={anchor} hidden />;
}

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
          <OutcomeInView />
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
