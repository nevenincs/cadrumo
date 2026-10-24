import type { ClassifySelection } from "../../../shell/ledgerCommands";
import type { OwnAccountChoice } from "../../../shell/ledgerMovementReads";

/** What the Movements section tells the inspector beside it: which of the
 * period's movements it draws, what the last check found on each, and the
 * section's own commands, so the inspector classifies through the one
 * classify command and hands focus back to the grid. */
export type SectionInspectorContext = {
  /** The movements the grid draws, as filters, search and folds leave
   * them. */
  visible: ReadonlySet<string>;
  /** The window is read in part, so "every movement" is the loaded ones. */
  partial: boolean;
  /** Whether readiness has been measured. While it has not, `issues` is
   * empty and no movement may be drawn as having none. */
  checked: boolean;
  /** By movement, what the last check found other than a missing
   * classification. */
  issues: ReadonlyMap<string, readonly string[]>;
  accounts: readonly OwnAccountChoice[] | null;
  /** The movements an import flagged as likely duplicates. */
  duplicates: ReadonlySet<string>;
  classify: ClassifySelection;
  /** Focuses the grid's active cell. */
  focusActive: () => void;
  /** Takes off what hides selected movements: filters, search and folds. */
  showHidden: () => void;
};

const sameSet = (left: ReadonlySet<string>, right: ReadonlySet<string>) =>
  left === right ||
  (left.size === right.size && [...left].every((id) => right.has(id)));

/** Whether two contexts say the same: the section's commands are the same
 * commands however often it draws, so only what it shows is compared. */
export function sameInspectorContext(
  left: SectionInspectorContext,
  right: SectionInspectorContext,
): boolean {
  if (
    left.partial !== right.partial ||
    left.checked !== right.checked ||
    left.accounts !== right.accounts
  )
    return false;
  if (!sameSet(left.visible, right.visible)) return false;
  if (!sameSet(left.duplicates, right.duplicates)) return false;
  if (left.issues === right.issues) return true;
  if (left.issues.size !== right.issues.size) return false;
  for (const [id, reasons] of left.issues) {
    const other = right.issues.get(id);
    if (
      !other ||
      other.length !== reasons.length ||
      reasons.some((reason, at) => other[at] !== reason)
    )
      return false;
  }
  return true;
}
