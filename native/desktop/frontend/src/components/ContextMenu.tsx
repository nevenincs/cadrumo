import { useEffect, useRef, useState } from "react";
import type { MenuItem } from "../shell/host";
import { useMetric } from "../shell/metrics";

// Browser stand-in for the native menu. In the desktop application the host
// draws the same item list with the operating system's own menu.
export function ContextMenu({
  items,
  at,
  choose,
}: {
  items: MenuItem[];
  at: { x: number; y: number };
  choose: (id: string | null) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(-1);
  const enabled = items.flatMap((item, index) =>
    "separator" in item || !item.enabled ? [] : [index],
  );
  // Geometry for clamping the menu to the viewport before it ever paints:
  // the CSS rules (.native-menu, .menu-sep) own the real layout, these
  // mirror them in pixels for the position math below.
  const minWidth = useMetric("--menu-min-w", 220);
  const edgeGap = useMetric("--menu-edge-gap", 24);
  const viewportGutter = useMetric("--space-4", 4);
  const itemHeight = useMetric("--control-m", 30);
  const separatorHeight = useMetric("--menu-sep-h", 9);
  const padding = useMetric("--menu-pad", 10);

  useEffect(() => {
    ref.current?.focus();
    const away = (event: PointerEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node))
        choose(null);
    };
    const blur = () => choose(null);
    window.addEventListener("pointerdown", away, true);
    window.addEventListener("blur", blur);
    return () => {
      window.removeEventListener("pointerdown", away, true);
      window.removeEventListener("blur", blur);
    };
  }, [choose]);

  const height = items.reduce(
    (sum, item) => sum + ("separator" in item ? separatorHeight : itemHeight),
    padding,
  );
  const left = Math.max(
    viewportGutter,
    Math.min(at.x, window.innerWidth - (minWidth + edgeGap)),
  );
  const top =
    at.y + height > window.innerHeight
      ? Math.max(viewportGutter, at.y - height)
      : at.y;
  const step = (delta: number) => {
    if (!enabled.length) return;
    const index = enabled.indexOf(active);
    setActive(enabled[(index + delta + enabled.length) % enabled.length] ?? -1);
  };

  return (
    <div
      ref={ref}
      className="native-menu"
      role="menu"
      tabIndex={-1}
      style={{ left, top }}
      onKeyDown={(event) => {
        event.stopPropagation();
        event.preventDefault();
        if (event.key === "Escape") choose(null);
        else if (event.key === "ArrowDown") step(1);
        else if (event.key === "ArrowUp") step(-1);
        else if (event.key === "Enter") {
          const item = items[active];
          if (item && !("separator" in item)) choose(item.id);
        }
      }}
    >
      {items.map((item, index) =>
        "separator" in item ? (
          <div
            key={`separator-${index}`}
            className="menu-sep"
            role="separator"
          />
        ) : (
          <button
            key={item.id}
            role="menuitem"
            className={index === active ? "is-active" : ""}
            disabled={!item.enabled}
            onMouseEnter={() => setActive(index)}
            onClick={() => choose(item.id)}
          >
            <span>{item.label}</span>
            {item.shortcut && <kbd aria-hidden="true">{item.shortcut}</kbd>}
          </button>
        ),
      )}
    </div>
  );
}
