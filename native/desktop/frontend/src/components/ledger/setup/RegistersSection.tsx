import { useState } from "react";
import { useStrings } from "../../../shell/strings";
import { AccountsPane } from "./AccountsPane";
import { CapitalGoodsPane } from "./CapitalGoodsPane";
import { ProrrataPane } from "./ProrrataPane";
import { SetupTabs } from "./SetupParts";
import type { SetupProps } from "./setupProps";

const AREAS = ["accounts", "prorrata", "capital"] as const;
type Area = (typeof AREAS)[number];

/**
 * Setup › Registers: the person's own accounts, the prorrata register and
 * bienes de inversión. Each change here is its own write, confirmed in its
 * form. The inventory books and the activity's assets are the Assets tab's.
 */
export function RegistersSection(props: SetupProps) {
  const t = useStrings();
  const [area, setArea] = useState<Area>("accounts");
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
      </SetupTabs>
    </div>
  );
}
