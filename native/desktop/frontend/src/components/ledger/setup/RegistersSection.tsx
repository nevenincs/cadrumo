import { useState } from "react";
import { useStrings } from "../../../shell/strings";
import { AccountsPane } from "./AccountsPane";
import { CapitalGoodsPane } from "./CapitalGoodsPane";
import { ProrrataPane } from "./ProrrataPane";
import { SetupTabs } from "./SetupParts";
import type { SetupProps } from "./setupProps";
import { WithholdingPane } from "./WithholdingPane";

const AREAS = ["accounts", "prorrata", "capital", "withholding"] as const;
type Area = (typeof AREAS)[number];
export type RegistersArea = Area;

/**
 * Setup › Registers: the person's own accounts, the prorrata register,
 * bienes de inversión and the withholding payers took. Each change here is
 * its own write, confirmed in its form. The inventory books and the
 * activity's assets are the Assets tab's.
 */
export function RegistersSection(
  props: SetupProps & {
    /** The area to open on, where another part of the window asked for one. */
    initialArea?: RegistersArea;
  },
) {
  const t = useStrings();
  const [area, setArea] = useState<Area>(props.initialArea ?? "accounts");
  return (
    <div className="ledger-setup-registers flex min-h-0 flex-1 flex-col">
      <SetupTabs<Area>
        label={t("desktop.ledger.registers.areas")}
        owner="ledger/registers"
        value={area}
        onValue={setArea}
        tabs={AREAS.map((value) => ({
          value,
          label: t(`desktop.ledger.registers.area.${value}`),
        }))}
      >
        {area === "accounts" && <AccountsPane {...props} />}
        {area === "prorrata" && <ProrrataPane {...props} />}
        {area === "capital" && <CapitalGoodsPane {...props} />}
        {area === "withholding" && <WithholdingPane {...props} />}
      </SetupTabs>
    </div>
  );
}
