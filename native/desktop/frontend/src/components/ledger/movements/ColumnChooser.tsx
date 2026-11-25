import { useId } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  SegmentedControl,
  SegmentedControlItem,
} from "@/components/ui/segmented-control";
import { useStrings } from "../../../shell/strings";
import {
  COLUMN_IDS,
  PRESET_IDS,
  moveColumn,
  presetHidden,
  presetOf,
  type ColumnId,
  type PresetId,
} from "./movementsModel";

/**
 * The columns: a preset to start from, and each column shown or hidden and
 * moved up or down among the shown ones, by keyboard as by pointer. What
 * it changes is presentation only.
 */
export function ColumnChooser({
  layout,
  onLayout,
}: {
  layout: { order: readonly ColumnId[]; hidden: ReadonlySet<ColumnId> };
  onLayout: (order: ColumnId[], hidden: ColumnId[]) => void;
}) {
  const t = useStrings();
  const presetsId = useId();
  const preset = presetOf(layout);
  const name = (column: ColumnId) => t(`desktop.ledger.column.${column}`);
  const hidden = [...layout.hidden];
  return (
    <Popover>
      <PopoverTrigger asChild>
        <IconButton
          label={t("desktop.ledger.columns.title")}
          hint={
            preset
              ? t(`desktop.ledger.columns.preset.${preset}`)
              : t("desktop.ledger.columns.preset.custom")
          }
          size="sm"
        >
          <Icon name="columns" />
        </IconButton>
      </PopoverTrigger>
      <PopoverContent
        align="end"
        aria-label={t("desktop.ledger.columns.title")}
        className="ledger-columns grid w-settings gap-3"
      >
        <div className="grid gap-1.5">
          <span
            id={presetsId}
            className="text-xs font-medium text-muted-foreground"
          >
            {t("desktop.ledger.columns.presets")}
          </span>
          <SegmentedControl
            aria-labelledby={presetsId}
            value={preset ?? ""}
            onValueChange={(value) =>
              onLayout([...layout.order], presetHidden(value as PresetId))
            }
          >
            {PRESET_IDS.map((choice) => (
              <SegmentedControlItem key={choice} value={choice}>
                {t(`desktop.ledger.columns.preset.${choice}`)}
              </SegmentedControlItem>
            ))}
          </SegmentedControl>
        </div>
        <ul
          aria-label={t("desktop.ledger.columns.list")}
          className="grid max-h-80 gap-0.5 overflow-y-auto"
        >
          {layout.order
            .filter((column) => column !== "select")
            .map((column) => {
              const shown = !layout.hidden.has(column);
              const up = shown ? moveColumn(layout, column, -1) : null;
              const down = shown ? moveColumn(layout, column, 1) : null;
              return (
                <li
                  key={column}
                  data-column={column}
                  className="flex items-center gap-2"
                >
                  <label className="flex min-w-0 flex-1 items-center gap-2 text-sm">
                    <Checkbox
                      checked={shown}
                      onChange={() =>
                        onLayout(
                          [...layout.order],
                          shown
                            ? [...hidden, column]
                            : hidden.filter((entry) => entry !== column),
                        )
                      }
                    />
                    <span className="truncate">{name(column)}</span>
                  </label>
                  <IconButton
                    label={t("desktop.ledger.columns.move_up", {
                      column: name(column),
                    })}
                    aria-disabled={up ? undefined : true}
                    onClick={() => up && onLayout(up, hidden)}
                  >
                    <Icon name="chevronUp" size="xs" />
                  </IconButton>
                  <IconButton
                    label={t("desktop.ledger.columns.move_down", {
                      column: name(column),
                    })}
                    aria-disabled={down ? undefined : true}
                    onClick={() => down && onLayout(down, hidden)}
                  >
                    <Icon name="chevronDown" size="xs" />
                  </IconButton>
                </li>
              );
            })}
        </ul>
        <Button
          variant="ghost"
          size="xs"
          className="justify-self-start"
          onClick={() => onLayout([...COLUMN_IDS], presetHidden("review"))}
        >
          <Icon name="reset" size="xs" />
          {t("desktop.ledger.columns.reset")}
        </Button>
      </PopoverContent>
    </Popover>
  );
}
