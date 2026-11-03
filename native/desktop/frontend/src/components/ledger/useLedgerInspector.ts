import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { chordMatches } from "@/shared/chords";
import type { LedgerPageProps } from "./LedgerPage";
import type { InspectorFocus } from "./inspector/MovementInspector";
import type { RightPanelMode } from "./inspector/RightPanel";
import type { SectionInspectorContext } from "./inspector/inspectorContext";
import type { InspectorSection } from "./inspector/inspectorModel";
import { INSPECTOR_CHORD } from "./ledgerChords";

/** Inspector and matching-panel focus follow the saved view and Alt+I gesture. */
export function useLedgerInspector({
  view,
  onViewChange,
}: Pick<LedgerPageProps, "view" | "onViewChange">) {
  // The panel beside the grid: the To match queue or the inspector. Alt+I
  // is handled here, once: it opens the inspector and focuses its index,
  // moves focus to the index from the grid, or closes it from inside and
  // hands focus back to the active cell.
  const [inspectorContext, setInspectorContext] =
    useState<SectionInspectorContext | null>(null);
  const [inspectorFocus, setInspectorFocus] = useState<InspectorFocus>({
    section: null,
    index: false,
    tick: 0,
  });
  const [panelMode, setPanelMode] = useState<RightPanelMode>(
    view.savedView === "to_match" ? "match" : "movement",
  );
  // Choosing the To match view opens the panel on its queue, its side
  // list; leaving the view leaves the panel as it is.
  const panelView = useRef(view.savedView);
  useEffect(() => {
    if (panelView.current === view.savedView) return;
    panelView.current = view.savedView;
    if (view.savedView !== "to_match") return;
    setPanelMode("match");
    onViewChange((current) => ({ ...current, inspectorOpen: true }));
  }, [view.savedView, onViewChange]);
  const inspectorPanel = useRef<HTMLElement | null>(null);
  const setInspectorOpen = (inspectorOpen: boolean) =>
    onViewChange((current) => ({ ...current, inspectorOpen }));
  const openInspector = (section: InspectorSection | null, index = false) => {
    setPanelMode("movement");
    setInspectorOpen(true);
    setInspectorFocus((held) => ({ section, index, tick: held.tick + 1 }));
  };
  const closeInspector = () => {
    setInspectorOpen(false);
    inspectorContext?.focusActive();
  };
  const onInspectorKey = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!chordMatches(INSPECTOR_CHORD, event) || event.nativeEvent.isComposing)
      return;
    event.preventDefault();
    if (!view.inspectorOpen) openInspector(null, true);
    else if (inspectorPanel.current?.contains(document.activeElement))
      closeInspector();
    else {
      setPanelMode("movement");
      setInspectorFocus((held) => ({
        section: null,
        index: true,
        tick: held.tick + 1,
      }));
    }
  };

  return {
    inspectorContext,
    setInspectorContext,
    inspectorFocus,
    panelMode,
    setPanelMode,
    inspectorPanel,
    openInspector,
    closeInspector,
    onInspectorKey,
  };
}
