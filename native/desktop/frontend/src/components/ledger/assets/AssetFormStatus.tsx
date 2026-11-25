import { Alert } from "@/components/ui/alert";
import { Icon } from "@/components/ui/icon";
import { useStrings } from "../../../shell/strings";
import { CallLine, Reading } from "../setup/SetupParts";
import type { SetupCall } from "../setup/setupModel";
import type { FormField } from "./assetFormValues";
import {
  INCOMPLETE,
  missingLabels,
  neverReused,
  refusalWord,
  viewOf,
} from "./assetWrites";
import { ASSET_KEYS } from "./assetsWords";

/** What stands where an act's options are not yet drawn: the read, or why it
 * did not answer. */
export function OptionsRead({ call }: { call: SetupCall<unknown> | null }) {
  const t = useStrings();
  if (call === null)
    return <Reading label={t("desktop.ledger.form.reading")} />;
  return (
    <CallLine
      call={call}
      refusal={() =>
        call.kind === "refused"
          ? (refusalWord(viewRefusal(call)) ?? t(ASSET_KEYS.write.refused))
          : null
      }
    />
  );
}

const viewRefusal = (call: SetupCall<unknown>) => {
  const view = viewOf(call, neverReused);
  return view.kind === "refused"
    ? view
    : { reasonKey: null, reasonFacts: [], words: null };
};

// ---- How a write ended, in the form ---------------------------------------------

/**
 * The line under a form for how its last call ended: saved or already there,
 * refused with what was kept, incomplete with what to fill in, or a call that
 * failed or was not seen to settle. A refusal is worded by the backend's
 * reason key and facts and never by its English.
 */
export function WriteLine({
  call,
  fields,
  saved,
}: {
  call: SetupCall<unknown> | null;
  fields: readonly FormField[];
  /** The words for a write that landed, new and already there; null where a
   * landing is not worth a line, as for a forecast. */
  saved: {
    done: string;
    reused: string;
    reusedOf: (result: unknown) => boolean;
  } | null;
}) {
  const t = useStrings();
  const view = viewOf(call, saved?.reusedOf ?? neverReused);
  const kept = t("desktop.ledger.assets.write.kept");
  if (view.kind === "none") return null;
  if (view.kind === "saved")
    return saved ? (
      <Alert
        tone="success"
        icon={<Icon name="check" />}
        className="ledger-asset-saved"
      >
        {view.reused ? saved.reused : saved.done}
      </Alert>
    ) : null;
  if (view.kind === "refused") {
    if (view.code === INCOMPLETE && view.missing.length > 0)
      return (
        <Alert
          tone="warning"
          role="alert"
          icon={<Icon name="alert" />}
          className="ledger-asset-incomplete"
        >
          {t(ASSET_KEYS.write.incomplete, {
            fields: missingLabels(t, fields, view.missing),
          })}
        </Alert>
      );
    return (
      <Alert
        tone="danger"
        role="alert"
        icon={<Icon name="refused" />}
        className="ledger-asset-refused"
      >
        <span>{refusalWord(view) ?? t(ASSET_KEYS.write.refused)}</span>
        <span className="text-sm text-muted-foreground">{kept}</span>
      </Alert>
    );
  }
  return (
    <>
      <CallLine call={call} />
      {view.kind === "failed" && (
        <p className="text-sm text-muted-foreground">{kept}</p>
      )}
    </>
  );
}
