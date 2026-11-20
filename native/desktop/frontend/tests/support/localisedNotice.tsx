import type { ComponentProps } from "react";
import { LaneSwitchNotice } from "../../src/components/agent/LaneSwitchNotice";
import { StringsContext, translator } from "../../src/shell/strings";

/** The notice over the composer, worded in `locale`: the window's own
 * provider of the words, which markup drawn on its own does not have. */
export function LocalisedNotice({
  locale,
  ...props
}: { locale: string } & ComponentProps<typeof LaneSwitchNotice>) {
  return (
    <StringsContext.Provider value={translator(locale)}>
      <LaneSwitchNotice {...props} />
    </StringsContext.Provider>
  );
}
