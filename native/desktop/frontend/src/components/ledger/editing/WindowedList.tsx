import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { cn } from "@/components/ui/cn";

/** Rows drawn above and below what is in view. */
const OVERSCAN = 6;

/**
 * A long list drawn a window at a time: only the items in view are in the
 * document, each the height of the first one drawn. Items keep their place
 * in the list's count for assistive technology.
 */
export function WindowedList<T>({
  items,
  keyOf,
  render,
  label,
  className,
}: {
  items: readonly T[];
  keyOf: (item: T) => string;
  render: (item: T) => ReactNode;
  label: string;
  className?: string;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const probe = useRef<HTMLLIElement>(null);
  const [height, setHeight] = useState(0);
  const [top, setTop] = useState(0);
  const [view, setView] = useState(0);
  useLayoutEffect(() => {
    if (!height && probe.current) setHeight(probe.current.offsetHeight);
    if (scroller.current) setView(scroller.current.clientHeight);
  }, [height, items.length]);
  const size = height || 1;
  const first = height ? Math.max(0, Math.floor(top / size) - OVERSCAN) : 0;
  const last = height
    ? Math.min(items.length, Math.ceil((top + view) / size) + OVERSCAN)
    : Math.min(items.length, 1);
  return (
    <div
      ref={scroller}
      tabIndex={items.length ? 0 : undefined}
      aria-label={label}
      role="region"
      className={cn(
        "ledger-windowed relative overflow-y-auto overscroll-contain",
        className,
      )}
      onScroll={(event) => setTop(event.currentTarget.scrollTop)}
    >
      <ul
        aria-label={label}
        className="relative"
        style={{ height: height ? items.length * height : undefined }}
      >
        {items.slice(first, last).map((item, offset) => {
          const at = first + offset;
          return (
            <li
              key={keyOf(item)}
              ref={at === first ? probe : undefined}
              aria-setsize={items.length}
              aria-posinset={at + 1}
              className={height ? "absolute inset-x-0" : undefined}
              style={height ? { top: at * height } : undefined}
            >
              {render(item)}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
