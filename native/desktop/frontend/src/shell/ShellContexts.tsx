import type { ReactNode } from "react";
import { StringsContext, type Translate } from "./strings";
import { NavigationContext, type NavigationRuntime } from "./navigation/hooks";
import { ProvisioningContext, type ProvisioningStore } from "./provisioning";

/** The window's own contexts: its strings, its navigation runtime and its
 * provisioning store. */
export function ShellContexts({
  t,
  navigation,
  provisioning,
  children,
}: {
  t: Translate;
  navigation: NavigationRuntime;
  provisioning: ProvisioningStore;
  children: ReactNode;
}) {
  return (
    <StringsContext.Provider value={t}>
      <NavigationContext.Provider value={navigation}>
        <ProvisioningContext.Provider value={provisioning}>
          {children}
        </ProvisioningContext.Provider>
      </NavigationContext.Provider>
    </StringsContext.Provider>
  );
}
