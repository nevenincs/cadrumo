import {
  useLayoutEffect,
  useCallback,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
  type RefObject,
} from "react";
import {
  isDockPane,
  type DockLayout,
  type DockMove,
  type DockPane,
} from "../../shell/docking";

export type DockTarget =
  { pane: DockPane; intent: DockMove } | { intent: "empty" };
export type DockHit = {
  target: DockTarget;
  scrolling?: boolean;
  line?: { x: number; y: number; height: number };
};
type Session = {
  pane: DockPane;
  id: number;
  button: HTMLElement;
  focus: HTMLElement | null;
  startX: number;
  startY: number;
  x: number;
  y: number;
  dragging: boolean;
};

export function hitTest(
  surface: HTMLElement,
  x: number,
  y: number,
  source: DockPane,
  scroll: boolean,
): DockHit | null {
  const hit = document.elementFromPoint(x, y);
  if (!hit || !surface.contains(hit)) return null;
  const header = hit.closest<HTMLElement>("[data-dock-header]");
  if (header) {
    const strip = hit.closest<HTMLElement>("[data-dock-tabs]");
    if (!strip || header.hasAttribute("data-floating")) return null;
    const bounds = strip.getBoundingClientRect();
    const previousScroll = strip.scrollLeft;
    if (scroll && strip.scrollWidth > strip.clientWidth) {
      const margin = Math.min(24, bounds.width / 4);
      if (x - bounds.left < margin) strip.scrollLeft -= 8;
      else if (bounds.right - x < margin) strip.scrollLeft += 8;
    }
    const tabs = Array.from(
      strip.querySelectorAll<HTMLElement>("[data-dock-tab]"),
    );
    const anchor =
      tabs.find((tab) => x < tab.getBoundingClientRect().right) ?? tabs.at(-1);
    if (!anchor || !isDockPane(anchor.dataset.dockTab)) return null;
    const rect = anchor.getBoundingClientRect();
    const before = x < (rect.left + rect.right) / 2;
    return {
      target: {
        pane: anchor.dataset.dockTab,
        intent: before ? "before" : "after",
      },
      scrolling: strip.scrollLeft !== previousScroll,
      line: {
        x: Math.min(
          bounds.right - 2,
          Math.max(bounds.left, before ? rect.left : rect.right - 2),
        ),
        y: rect.top,
        height: rect.height,
      },
    };
  }
  const overlay = hit.closest<HTMLElement>("[data-dock-body]");
  const panel = overlay
    ? surface.querySelector<HTMLElement>(
        `[data-dock-pane="${overlay.dataset.dockBody}"]`,
      )
    : hit.closest<HTMLElement>("[data-dock-pane]");
  if (!panel)
    return surface.hasAttribute("data-empty-dock")
      ? { target: { intent: "empty" } }
      : null;
  const active = panel.dataset.dockPane;
  if (!isDockPane(active) || panel.hasAttribute("data-floating")) return null;
  const rect = panel.getBoundingClientRect();
  const chrome = surface.querySelector<HTMLElement>(
    `[data-dock-header="${active}"]`,
  );
  const top = chrome?.getBoundingClientRect().bottom ?? rect.top;
  const dx = (x - rect.left) / rect.width;
  const dy = (y - top) / (rect.bottom - top);
  const edges = [
    ["left", dx],
    ["right", 1 - dx],
    ["top", dy],
    ["bottom", 1 - dy],
  ] as const;
  const closest = edges.reduce((best, edge) =>
    edge[1] < best[1] ? edge : best,
  );
  const intent = closest[1] < 0.25 ? closest[0] : "tab";
  const other = chrome?.querySelector<HTMLElement>(
    `[data-dock-tab]:not([data-dock-tab="${source}"])`,
  )?.dataset.dockTab;
  const pane = active === source && isDockPane(other) ? other : active;
  return { target: { pane, intent } };
}

/** Keep all pointer movement speculative until release. The trigger handles normal clicks. */
export function useDockTitleDrag(
  surface: RefObject<HTMLDivElement | null>,
  layout: DockLayout,
  visible: readonly DockPane[],
  expanded: DockPane | null,
  cancelled: boolean,
  commit: (pane: DockPane, target: DockTarget) => void,
  announce: (kind: "started" | "cancelled", pane: DockPane) => void,
) {
  const held = useRef<Session | null>(null);
  const [preview, setPreview] = useState<{
    pane: DockPane;
    x: number;
    y: number;
    hit: DockHit | null;
  } | null>(null);
  const frame = useRef(0);
  const suppress = useRef(false);
  const announcement = useRef(announce);
  useLayoutEffect(() => {
    announcement.current = announce;
  }, [announce]);
  const refresh = () => {
    const session = held.current;
    if (!session?.dragging || !surface.current) return;
    const { pane, x, y } = session;
    const hit = hitTest(surface.current, x, y, pane, true);
    setPreview({ pane, x, y, hit });
    if (hit?.scrolling) frame.current = requestAnimationFrame(refresh);
  };
  const finish = useCallback((cancel: boolean) => {
    const session = held.current;
    if (!session) return;
    held.current = null;
    if (session.dragging || cancel) suppress.current = true;
    cancelAnimationFrame(frame.current);
    if (session.button.hasPointerCapture(session.id))
      session.button.releasePointerCapture(session.id);
    setPreview(null);
    if (cancel && session.dragging) {
      announcement.current("cancelled", session.pane);
      if (
        session.focus?.isConnected &&
        !document.querySelector('[role="dialog"]')
      )
        session.focus.focus({ preventScroll: true });
    }
  }, []);
  const signature = JSON.stringify([layout, visible, expanded, cancelled]);
  useLayoutEffect(() => {
    finish(true);
  }, [signature, finish]);
  useLayoutEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (event.key === "Escape" && held.current) {
        event.preventDefault();
        event.stopImmediatePropagation();
        finish(true);
      }
    };
    const blur = () => finish(true);
    const modal = (event: FocusEvent) => {
      if (
        event.target instanceof Element &&
        event.target.closest('[role="dialog"],[role="alertdialog"]')
      )
        finish(true);
    };
    window.addEventListener("focusin", modal, true);
    window.addEventListener("keydown", key, true);
    window.addEventListener("blur", blur);
    return () => {
      window.removeEventListener("focusin", modal, true);
      window.removeEventListener("keydown", key, true);
      window.removeEventListener("blur", blur);
      finish(true);
    };
  }, [finish]);
  const handlers = (pane: DockPane) => ({
    onPointerDown(event: ReactPointerEvent<HTMLButtonElement>) {
      if (
        event.button !== 0 ||
        !event.isPrimary ||
        event.ctrlKey ||
        cancelled ||
        held.current
      )
        return;
      suppress.current = false;
      event.preventDefault();
      const button = event.currentTarget;
      button.setPointerCapture(event.pointerId);
      held.current = {
        pane,
        id: event.pointerId,
        button,
        focus:
          document.activeElement instanceof HTMLElement
            ? document.activeElement
            : null,
        startX: event.clientX,
        startY: event.clientY,
        x: event.clientX,
        y: event.clientY,
        dragging: false,
      };
    },
    onPointerMove(event: ReactPointerEvent<HTMLButtonElement>) {
      const session = held.current;
      if (!session || session.id !== event.pointerId) return;
      session.x = event.clientX;
      session.y = event.clientY;
      if (!session.dragging) {
        if (
          Math.hypot(session.x - session.startX, session.y - session.startY) < 5
        )
          return;
        session.dragging = true;
        announce("started", pane);
      }
      cancelAnimationFrame(frame.current);
      refresh();
    },
    onPointerUp(event: ReactPointerEvent<HTMLButtonElement>) {
      const session = held.current;
      if (!session || session.id !== event.pointerId) return;
      const hit =
        session.dragging &&
        surface.current &&
        hitTest(surface.current, event.clientX, event.clientY, pane, false);
      if (session.dragging) suppress.current = true;
      finish(session.dragging && !hit);
      if (hit) commit(pane, hit.target);
    },
    onPointerCancel() {
      finish(true);
    },
    onLostPointerCapture() {
      finish(true);
    },
  });
  return {
    preview,
    handlers,
    takeClick: () => {
      const value = suppress.current;
      suppress.current = false;
      return value;
    },
  };
}
