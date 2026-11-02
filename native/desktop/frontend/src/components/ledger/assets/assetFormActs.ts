import type { LedgerPort } from "../../../shell/ledger";
import type {
  ActivityAssetCorrectRequest,
  ActivityAssetCreateRequest,
  AssetListRow,
} from "../../../shell/ledgerSetup";
import type { LandingCheck } from "../WritePause";
import { setupCall, type SetupCall } from "../setup/setupModel";
import type { FormValues } from "./assetFormValues";
import { bajaRequest, type RevisionBase } from "./assetRevision";
import {
  correctionLanding,
  descriptorLanding,
  describeRequest,
  disposalOf,
  elementLanding,
} from "./assetWrites";
import { ASSET_KEYS } from "./assetsWords";

// ---- The acts --------------------------------------------------------------------

export type ActKind =
  "element" | "descriptor" | "correction" | "baja" | "baja_change";

export type AssetActContext = {
  port: LedgerPort;
  assetId: string;
  asset: AssetListRow | null;
  values: FormValues;
  /** The request the form's values make, where the act builds one. */
  create: ActivityAssetCreateRequest | null;
  correct: ActivityAssetCorrectRequest | null;
  /** The revision a change of the baja supersedes. */
  base: RevisionBase | null;
  /** Whether the baja is to be taken out. */
  removing: boolean;
  /** How many descriptions the element's history holds once this one lands. */
  descriptions: number;
};

type Act = {
  title: string;
  submit: string;
  /** What a write that landed says. */
  done: string;
  /** Only what changed is stated, the rest left as the record has it. */
  delta: boolean;
  /** Asks again before sending: what a baja does is not easily undone. */
  confirms: boolean;
  send(context: AssetActContext): Promise<SetupCall<unknown>>;
  landing(context: AssetActContext): LandingCheck;
};

/** The revision a correction supersedes: the one the element stands at when
 * the form sends it. */
const supersededRevision = (asset: AssetListRow | null) =>
  asset?.revision_number ?? 0;

const never = async (): Promise<SetupCall<unknown>> => ({
  kind: "failed",
  code: "unavailable",
  reason: null,
});

export const ASSET_ACTS: Record<ActKind, Act> = {
  element: {
    title: ASSET_KEYS.action.add,
    submit: "desktop.ledger.assets.submit.create",
    done: "desktop.ledger.assets.write.element_added",
    delta: false,
    confirms: false,
    send: (c) =>
      c.create === null
        ? never()
        : setupCall(c.port, "ledger.actividad-asset.create", c.create, true),
    landing: (c) => elementLanding(c.port, c.assetId),
  },
  descriptor: {
    title: ASSET_KEYS.action.describe,
    submit: "desktop.ledger.form.save",
    done: "desktop.ledger.assets.write.described",
    delta: false,
    confirms: false,
    send: (c) =>
      setupCall(
        c.port,
        "ledger.actividad-asset.describe",
        describeRequest(c.assetId, c.values),
        true,
      ),
    landing: (c) => descriptorLanding(c.port, c.assetId, c.descriptions),
  },
  correction: {
    title: ASSET_KEYS.action.correct,
    submit: "desktop.ledger.assets.submit.correct",
    done: "desktop.ledger.assets.write.corrected",
    delta: true,
    confirms: false,
    send: (c) =>
      c.correct === null
        ? never()
        : setupCall(c.port, "ledger.actividad-asset.correct", c.correct, true),
    landing: (c) =>
      correctionLanding(c.port, c.assetId, supersededRevision(c.asset)),
  },
  baja: {
    title: ASSET_KEYS.action.dispose,
    submit: ASSET_KEYS.action.dispose,
    done: "desktop.ledger.assets.write.baja_recorded",
    delta: false,
    confirms: true,
    send: (c) =>
      setupCall(
        c.port,
        "ledger.actividad-asset.dispose",
        { asset_id: c.assetId, disposal: disposalOf(c.values)! },
        true,
      ),
    landing: (c) =>
      correctionLanding(c.port, c.assetId, supersededRevision(c.asset)),
  },
  baja_change: {
    title: "desktop.ledger.assets.action.change_baja",
    submit: "desktop.ledger.assets.baja.change_submit",
    done: "desktop.ledger.assets.write.baja_changed",
    delta: false,
    confirms: true,
    send: async (c) => {
      const disposal = c.removing ? null : disposalOf(c.values);
      const request = bajaRequest(c.base, disposal);
      return request === null || (!c.removing && disposal === null)
        ? never()
        : setupCall(c.port, "ledger.actividad-asset.correct", request, true);
    },
    landing: (c) =>
      correctionLanding(c.port, c.assetId, supersededRevision(c.asset)),
  },
};
