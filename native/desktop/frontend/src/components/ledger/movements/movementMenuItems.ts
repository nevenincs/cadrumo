import { FILL_DOWN_CHORD } from "@/components/ui/dataGridModel";
import type { MenuEntry } from "../../ContextMenu";
import {
  CLASSIFY_KINDS,
  type ClassifyKind,
} from "../../../shell/ledgerCommands";
import type { Translate } from "../../../shell/strings";
import { REVERT_CELL_CHORD } from "../editing/MovementEditing";
import { CLASSIFY_CHORDS } from "./useClassifyChords";

/**
 * The items of a movements grid row's context menu. A group header's items
 * act on the group, which the chords, acting on the selection, do not: only
 * a movement's items show them. A new movement takes no classify item, and
 * a movement an import flagged as a likely duplicate offers its archiving.
 */
export function movementMenuItems({
  t,
  ids,
  draft,
  staged,
  column,
  cellStaged,
  duplicate,
  makeRule,
  classifyEnabled,
}: {
  t: Translate;
  /** The group's movements, where the menu is a group header's. */
  ids: string[] | null;
  /** The row is a new movement. */
  draft: boolean;
  /** The row holds a staged change, or is new. */
  staged: boolean;
  /** The column the menu was opened on, where it was a cell's. */
  column: string | null;
  /** Whether the cell the menu was opened on holds a staged change. */
  cellStaged: () => boolean;
  /** An import flagged the row as a likely duplicate. */
  duplicate: boolean;
  /** The page has a rule dialog. */
  makeRule: boolean;
  /** Whether classifying the menu's target as `kind` can run. */
  classifyEnabled: (kind: ClassifyKind) => boolean;
}): MenuEntry[] {
  const classifyItems = (): MenuEntry[] =>
    CLASSIFY_KINDS.map((kind) => ({
      id: `classify.${kind}`,
      label: t(`desktop.ledger.classify.as_${kind}`),
      enabled: classifyEnabled(kind),
      icon: "tick",
      ...(ids ? {} : { chord: CLASSIFY_CHORDS[kind] }),
    }));
  return [
    ...(draft ? [] : classifyItems()),
    ...(ids
      ? []
      : [
          { separator: true as const },
          {
            id: "revert.cell",
            label: t("desktop.ledger.edit.revert_cell"),
            icon: "reset" as const,
            chord: REVERT_CELL_CHORD,
            enabled: column !== null && cellStaged(),
          },
          {
            id: "revert.movement",
            label: draft
              ? t("desktop.ledger.draft.remove")
              : t("desktop.ledger.edit.revert_movement"),
            icon: draft ? ("trash" as const) : ("reset" as const),
            enabled: staged,
          },
          {
            id: "fill",
            label: t("desktop.ledger.fill.down"),
            icon: "fillDown" as const,
            chord: FILL_DOWN_CHORD,
            enabled: column !== null,
          },
          ...(duplicate
            ? [
                { separator: true as const },
                {
                  id: "duplicate.archive",
                  label: `${t("desktop.ledger.duplicate.archive")}…`,
                  icon: "archive" as const,
                  enabled: true,
                },
              ]
            : []),
        ]),
    ...(ids
      ? [
          {
            id: "category",
            label: t("desktop.ledger.group.category"),
            icon: "group" as const,
            enabled: true,
          },
          ...(makeRule
            ? [
                {
                  id: "make_rule",
                  label: `${t("desktop.ledger.group.make_rule")}…`,
                  icon: "filter" as const,
                  enabled: true,
                },
              ]
            : []),
          {
            id: "select",
            label: t("desktop.ledger.group.select", { count: ids.length }),
            icon: "selectAll" as const,
            enabled: true,
          },
        ]
      : []),
  ];
}
