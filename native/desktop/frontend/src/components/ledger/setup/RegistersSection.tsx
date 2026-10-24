import { useState } from "react";
import { useStrings } from "../../../shell/strings";
import { AccountsPane } from "./AccountsPane";
import { AssetsPane } from "./AssetsPane";
import { CapitalGoodsPane } from "./CapitalGoodsPane";
import { InventoryPane } from "./InventoryPane";
import { ProrrataPane } from "./ProrrataPane";
import { SetupTabs } from "./SetupParts";
import type { SetupProps } from "./setupProps";

const AREAS = [
  "accounts",
  "prorrata",
  "capital",
  "inventory",
  "assets",
] as const;
type Area = (typeof AREAS)[number];

/**
 * Setup › Registers: the person's own accounts, the prorrata register,
 * bienes de inversión, the inventory books and the activity's assets. Each
 * change here is its own write, confirmed in its form.
 */
export function RegistersSection(props: SetupProps) {
  const t = useStrings();
  const [area, setArea] = useState<Area>("accounts");
  return (
    <div className="ledger-setup-registers flex min-h-0 flex-1 flex-col">
      <SetupTabs<Area>
        label={t("desktop.ledger.registers.areas")}
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
        {area === "inventory" && <InventoryPane {...props} />}
        {area === "assets" && <AssetsPane {...props} />}
      </SetupTabs>
    </div>
  );
}
