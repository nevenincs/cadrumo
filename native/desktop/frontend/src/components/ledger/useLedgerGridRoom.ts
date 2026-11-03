import { useLayoutEffect, useMemo, useRef, useState } from "react";
import type { LedgerPageProps } from "./LedgerPage";
import { rowFloor } from "./inspector/RightPanel";

/** Measures the grid frame and reports its width requirement beside the inspector. */
export function useLedgerGridRoom({
  gridShown,
  inspectorShown,
  onFloor,
}: {
  gridShown: boolean;
  inspectorShown: boolean;
  onFloor: LedgerPageProps["onFloor"];
}) {
  // The grid keeps the least it needs to show any scrolling column whole,
  // with what its column draws around it, beside the panel or alone; the
  // window makes the room from the agent column rather than squeezing it.
  const row = useRef<HTMLDivElement>(null);
  const [gridLeast, setGridLeast] = useState<number | null>(null);
  const [columnFloor, setColumnFloor] = useState<number | null>(null);
  useLayoutEffect(() => {
    const column = row.current?.firstElementChild;
    const drawn = column?.querySelector<HTMLElement>("[data-slot=data-grid]");
    if (!gridShown || gridLeast === null || !column || !drawn) {
      setColumnFloor(null);
      return;
    }
    // What the column draws around the grid, read from its styles: a
    // measured difference of widths is wrong while the panel opening is
    // still being laid out.
    let frame = 0;
    for (
      let around = drawn.parentElement;
      around && around !== column.parentElement;
      around = around.parentElement
    ) {
      const style = getComputedStyle(around);
      frame +=
        parseFloat(style.paddingLeft) +
        parseFloat(style.paddingRight) +
        parseFloat(style.borderLeftWidth) +
        parseFloat(style.borderRightWidth);
    }
    setColumnFloor(Math.ceil(gridLeast + frame));
  }, [gridShown, gridLeast]);
  const gridRoom = useMemo(
    () => ({ columnFloor, onLeast: setGridLeast }),
    [columnFloor],
  );
  useLayoutEffect(() => {
    if (!onFloor) return;
    onFloor(gridShown ? rowFloor(columnFloor, inspectorShown) : null);
    return () => onFloor(null);
  }, [gridShown, inspectorShown, columnFloor, onFloor]);

  return { row, gridRoom };
}
