import { useLayoutEffect, useRef, useState, type RefObject } from "react";

/**
 * The room a part of the header has ever needed, so that swapping what it
 * shows (the next step, the busy words, nothing) never shortens the header
 * and moves the tabs under it. The part is measured as drawn and only ever
 * grows; the style keeps the room, capped to what its container offers.
 */
export function useReservedSize<T extends HTMLElement>(): {
  ref: RefObject<T | null>;
  style: { minWidth?: string; minHeight?: number };
} {
  const ref = useRef<T | null>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  useLayoutEffect(() => {
    const node = ref.current;
    if (!node || typeof ResizeObserver === "undefined") return;
    const grow = () => {
      const { width, height } = node.getBoundingClientRect();
      setSize((held) =>
        width > held.width + 0.5 || height > held.height + 0.5
          ? {
              width: Math.max(held.width, Math.ceil(width)),
              height: Math.max(held.height, Math.ceil(height)),
            }
          : held,
      );
    };
    grow();
    const watch = new ResizeObserver(grow);
    watch.observe(node);
    return () => watch.disconnect();
  }, []);
  return {
    ref,
    style: {
      minWidth: size.width > 0 ? `min(${size.width}px, 100%)` : undefined,
      minHeight: size.height > 0 ? size.height : undefined,
    },
  };
}
