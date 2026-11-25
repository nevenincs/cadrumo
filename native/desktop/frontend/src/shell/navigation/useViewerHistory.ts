import { useCallback, useEffect, useRef } from "react";
import type { LedgerSection } from "../layout";
import type { Leaving } from "./guards";
import {
  emptyHistory,
  recordPosition,
  stepIndex,
  type ViewerHistory,
  type ViewerPosition,
} from "./history";
import { positionUnmounts } from "./windowViews";

/**
 * The window's back and forward over the positions it has shown. Every
 * position the window comes to, by whatever way, is recorded once it is
 * shown; a step shows a recorded one again through the navigator's guard,
 * so it asks before dropping staged work exactly as the header's back link
 * does. The history belongs to one sign-in and is kept in memory only.
 */
export function useViewerHistory<View extends string>({
  reader,
  position,
  ledgerSection,
  guard,
  show,
}: {
  /** Whose window it is; another sign-in starts a new history. */
  reader: string | null;
  /** Where the viewer is now. */
  position: ViewerPosition<View>;
  ledgerSection: LedgerSection;
  /** The navigator's guard, which lets a step through, refuses it or asks. */
  guard(leaving: Leaving, proceed: () => void): void;
  /** Shows a recorded position. */
  show(position: ViewerPosition<View>): void;
}) {
  const held = useRef<{
    reader: string | null;
    history: ViewerHistory<View>;
  }>({
    reader,
    history: emptyHistory<View>(),
  });
  const now = useRef({ position, ledgerSection, show });
  useEffect(() => {
    now.current = { position, ledgerSection, show };
    const kept = held.current;
    if (kept.reader !== reader)
      held.current = { reader, history: emptyHistory<View>() };
    held.current.history = recordPosition(held.current.history, position);
  });
  const step = useCallback(
    (delta: -1 | 1) => {
      const history = held.current.history;
      const index = stepIndex(history, delta);
      const target = index === null ? undefined : history.entries[index];
      if (index === null || !target) return;
      const shown = now.current;
      guard(
        {
          kind: "navigate",
          unmounted: positionUnmounts(
            shown.position,
            target,
            shown.ledgerSection,
          ),
        },
        () => {
          // A step asked about is taken only if nothing moved meanwhile.
          if (held.current.history.entries[index] !== target) return;
          // Moved before it is shown, so the position shown next is the
          // one stepped to rather than a new one.
          held.current.history = { ...held.current.history, index };
          now.current.show(target);
        },
      );
    },
    [guard],
  );
  const back = useCallback(() => step(-1), [step]);
  const forward = useCallback(() => step(1), [step]);
  return { back, forward };
}
