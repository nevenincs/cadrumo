import type { ReactNode } from "react";
import { StringsContext, type Translate } from "./strings";
import { NavigationContext, type NavigationRuntime } from "./navigation/hooks";
import { ProvisioningContext, type ProvisioningStore } from "./provisioning";
import {
  BackgroundTasksContext,
  type BackgroundTasks,
} from "./backgroundTasks";

/** The window's own contexts: its strings, its navigation runtime, its
 * provisioning store and the profile's background jobs. */
export function ShellContexts({
  t,
  navigation,
  provisioning,
  backgroundTasks,
  children,
}: {
  t: Translate;
  navigation: NavigationRuntime;
  provisioning: ProvisioningStore;
  backgroundTasks: BackgroundTasks;
  children: ReactNode;
}) {
  return (
    <StringsContext.Provider value={t}>
      <NavigationContext.Provider value={navigation}>
        <ProvisioningContext.Provider value={provisioning}>
          <BackgroundTasksContext.Provider value={backgroundTasks}>
            {children}
          </BackgroundTasksContext.Provider>
        </ProvisioningContext.Provider>
      </NavigationContext.Provider>
    </StringsContext.Provider>
  );
}
