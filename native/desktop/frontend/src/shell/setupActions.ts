import { useMemo } from "react";
import type { SetupItemId, SetupRun } from "@/ipc/componentSetup";
import { itemName } from "../components/setup/setupWords";
import type { Action } from "./actions";
import type { ProvisioningStore } from "./provisioning";
import { liveRunOf, needsSetup, type SetupControl } from "./setup";
import type { Translate } from "./strings";

/** Component setup's: the panel, a check, each element, a retry and a cancel. */
export function useSetupActions({
  t,
  setup,
  setupOffered,
  setupSnapshot,
  setupLive,
  setupRetryable,
  setupCancellable,
  openSetup,
}: {
  t: Translate;
  setup: SetupControl;
  setupOffered: boolean;
  setupSnapshot: SetupControl["snapshot"];
  setupLive: SetupRun[];
  setupRetryable: { item: SetupItemId; resume: boolean }[];
  setupCancellable: SetupRun[];
  openSetup: ProvisioningStore["open"];
}): Action[] {
  return useMemo<Action[]>(
    () => [
      {
        id: "setup.open",
        label: t("desktop.setup.palette_open"),
        group: "setup",
        icon: "download",
        keywords: t("desktop.palette.keywords.setup_open"),
        enabled: () => setupOffered,
        run: () => openSetup(null),
      },
      {
        id: "setup.check",
        label: t("desktop.setup.palette_check"),
        group: "setup",
        icon: "check",
        keywords: t("desktop.palette.keywords.setup_check"),
        enabled: () => setupOffered && setupLive.length === 0,
        run: () => {
          openSetup(null);
          setup.check("full");
        },
      },
      // One way to each element the engine reports: it opens the panel on
      // that element, and sets it up where it can be.
      ...(setupSnapshot?.rows ?? []).map((row): Action => ({
        id: `setup.item.${row.item}`,
        label: t("desktop.setup.palette_item", {
          name: itemName(t, row.item),
        }),
        group: "setup",
        icon: "download",
        enabled: () => setupOffered,
        run: () => {
          openSetup(row.item);
          if (needsSetup(row) && liveRunOf(setupSnapshot, row.item) === null)
            setup.start(row.item, { resume: row.recovery === "resume" });
        },
      })),
      {
        id: "setup.retry",
        label: t("desktop.setup.palette_retry"),
        group: "setup",
        icon: "reset",
        enabled: () => setupOffered && setupRetryable.length > 0,
        run: () => {
          openSetup(null);
          for (const { item, resume } of setupRetryable)
            setup.start(item, { resume });
        },
      },
      {
        id: "setup.cancel",
        label: t("desktop.setup.palette_cancel"),
        group: "setup",
        icon: "stop",
        enabled: () => setupOffered && setupCancellable.length > 0,
        run: () => {
          for (const run of setupCancellable) setup.cancel(run.item);
        },
      },
    ],
    [
      t,
      setup,
      setupOffered,
      setupSnapshot,
      setupLive,
      setupRetryable,
      setupCancellable,
      openSetup,
    ],
  );
}
