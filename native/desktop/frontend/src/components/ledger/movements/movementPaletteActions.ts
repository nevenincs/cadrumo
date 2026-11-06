import { facts } from "@/shell/compose";
import type { Action } from "../../../shell/actions";
import {
  CLASSIFY_KINDS,
  type ClassifyAvailability,
  type ClassifyKind,
} from "../../../shell/ledgerCommands";
import type { Translate } from "../../../shell/strings";
import { blockText } from "./movementWords";

/** What the Movements section offers the page's palette: each classify kind,
 * stepping through the movements with an issue, and clearing the filters. */
export function movementPaletteActions({
  t,
  availabilityOf,
  classify,
  hasIssues,
  stepIssue,
  filtering,
  clearFilters,
}: {
  t: Translate;
  availabilityOf: (kind: ClassifyKind) => ClassifyAvailability;
  classify: (kind: ClassifyKind) => void;
  /** Some movement shown has an issue to fix. */
  hasIssues: boolean;
  stepIssue: (by: 1 | -1) => void;
  /** A filter or a search narrows the movements. */
  filtering: boolean;
  clearFilters: () => void;
}): Action[] {
  return [
    ...CLASSIFY_KINDS.map((kind): Action => {
      const availability = availabilityOf(kind);
      return {
        id: `ledger.classify.${kind}`,
        label:
          availability.kind === "blocked"
            ? facts(t, [
                t(`desktop.ledger.classify.as_${kind}`),
                blockText(t, availability.block),
              ])
            : t(`desktop.ledger.classify.as_${kind}`),
        group: "ledger",
        icon: "tick",
        enabled: () => availability.kind === "ready",
        run: () => classify(kind),
      };
    }),
    {
      id: "ledger.issue.next",
      label: t("desktop.ledger.issue.next"),
      group: "ledger",
      icon: "alert",
      enabled: () => hasIssues,
      run: () => stepIssue(1),
    },
    {
      id: "ledger.issue.previous",
      label: t("desktop.ledger.issue.previous"),
      group: "ledger",
      icon: "alert",
      enabled: () => hasIssues,
      run: () => stepIssue(-1),
    },
    {
      id: "ledger.filters.clear",
      label: t("desktop.ledger.filters.clear_all"),
      group: "ledger",
      icon: "filter",
      enabled: () => filtering,
      run: clearFilters,
    },
  ];
}
