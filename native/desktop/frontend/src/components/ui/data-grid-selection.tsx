import * as React from "react";
import { Checkbox } from "./checkbox";
import { exactly } from "./dataGridModel";
import { GridSelectionContext } from "./dataGridSelection";

/** A row's selection box, the pointer's way to the keyboard's Space. Shift
 * extends from the last row chosen. */
export function DataGridRowCheckbox({
  rowKey,
  label,
}: {
  rowKey: string;
  label: string;
}) {
  const grid = React.useContext(GridSelectionContext);
  if (!grid) return null;
  return (
    <Checkbox
      tabIndex={-1}
      aria-label={label}
      checked={grid.isSelected(rowKey)}
      onClick={(event) => event.stopPropagation()}
      onChange={(event) =>
        grid.toggle(rowKey, (event.nativeEvent as MouseEvent).shiftKey)
      }
    />
  );
}

/** The header's box: every row, or none. */
export function DataGridSelectAll({ label }: { label: string }) {
  const grid = React.useContext(GridSelectionContext);
  const box = React.useRef<HTMLInputElement>(null);
  // The change event carries no modifiers; the click before it does.
  const adding = React.useRef(false);
  React.useEffect(() => {
    if (box.current) box.current.indeterminate = grid?.extent === "some";
  }, [grid?.extent]);
  if (!grid) return null;
  return (
    <Checkbox
      ref={box}
      tabIndex={-1}
      aria-label={label}
      checked={grid.extent === "all"}
      onClick={(event) => {
        event.stopPropagation();
        adding.current = exactly(event, { primary: true });
      }}
      onChange={() => {
        grid.toggleAll(adding.current);
        adding.current = false;
      }}
    />
  );
}
