import type { IconName } from "@/components/ui/icon";
import type { AeatSyncOutcome } from "../../shell/aeatSync";

/** The icon that stands for how a read of AEAT data ended; an area's outcome
 * and a part's outcome are the same four words. */
export const OUTCOME_ICONS: Record<AeatSyncOutcome, IconName> = {
  brought: "check",
  nothing_found: "info",
  failed: "alert",
  unknown: "unknown",
};
