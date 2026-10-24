import type { IconName } from "@/components/ui/icon";
import type { LedgerFailure } from "../../../shell/ledger";
import type { ModeloDeclarationListRowV1 } from "../../../shell/modeloContract";
import type { Translate } from "../../../shell/strings";

// Catalogue keys for the read model's closed tokens, and the glyph each
// group wears. A token says what the read model decided; the page only names
// it, and decides nothing from it.

/** What was seen at the AEAT for a row, said beside its local state. */
export function aeatWords(
  t: Translate,
  row: ModeloDeclarationListRowV1,
): string | null {
  const state = row.aeat_submission_state;
  if (state === null) return null;
  const word = t(`workspace.declarations.calendar.aeat.${state}`);
  return row.evidence_conflicted
    ? `${word} · ${t("workspace.declarations.calendar.evidence.disagrees")}`
    : word;
}

export type Mark = { icon: IconName; tone: string };

/** The glyph a row's state wears, by the group the read model put it in and
 * whether it said the AEAT side needs checking. */
export function rowMark(row: ModeloDeclarationListRowV1): Mark | null {
  if (row.aeat_needs_check) return { icon: "alert", tone: "text-warning" };
  switch (row.group) {
    case "attention":
      return { icon: "alert", tone: "text-destructive" };
    case "aeat_unlinked":
      return { icon: "office", tone: "text-warning" };
    case "ready":
      return { icon: "check", tone: "text-muted-foreground" };
    case "recorded":
      return { icon: "tick", tone: "text-muted-foreground" };
    default:
      return null;
  }
}

/** The code a failed call names, shown beside the sentence. */
export const failureText = (failure: LedgerFailure) =>
  failure.reason ?? failure.code;
