import { useState, type ReactNode } from "react";
import type { LedgerPort } from "../../../shell/ledger";
import { useStrings } from "../../../shell/strings";
import { SetupTabs } from "../setup/SetupParts";
import { ASSET_KEYS } from "./assetsWords";
import { FixedAssetsPane } from "./FixedAssetsPane";

type Area = "fixed" | "stock";

/**
 * The Assets tab of the Ledger: Fixed assets, the register of elements that
 * amortize, and Stock, which another part draws and which is offered only
 * once it is given. The section keeps no choice of its own past the area; a
 * year and a selection are the pane's and are not remembered.
 */
export function AssetsSection({
  port,
  reader,
  locale,
  stock,
  onOpenLink,
}: {
  port: LedgerPort;
  /** Whose ledger; null while the account withholds it. */
  reader: string | null;
  locale: string;
  /** The Stock area's content. */
  stock?: ReactNode;
  /** Opens an official address in the system browser, as the window does for
   * any external link; where it is not given, a citation is text only. */
  onOpenLink?: (url: string) => void;
}) {
  const t = useStrings();
  const [area, setArea] = useState<Area>("fixed");
  const tabs: { value: Area; label: string }[] = [
    { value: "fixed", label: t(ASSET_KEYS.area.fixed) },
    ...(stock
      ? [{ value: "stock" as const, label: t(ASSET_KEYS.area.stock) }]
      : []),
  ];
  return (
    <div className="ledger-assets flex min-h-0 flex-1 flex-col">
      <SetupTabs<Area>
        label={t("desktop.ledger.assets.areas")}
        owner="ledger/assets"
        value={stock ? area : "fixed"}
        onValue={setArea}
        tabs={tabs}
      >
        {(!stock || area === "fixed") && (
          <FixedAssetsPane
            port={port}
            reader={reader}
            locale={locale}
            onOpenLink={onOpenLink}
          />
        )}
        {stock && area === "stock" && stock}
      </SetupTabs>
    </div>
  );
}
